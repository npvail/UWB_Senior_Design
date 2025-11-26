// ==========================================
// UWB TRACKING SYSTEM - CLIENT SCRIPT
// ==========================================

// Default dimensions in Centimeters (will be updated from server)
let mapWidthCm = 1000; 
let mapHeightCm = 1000;

// DOM Elements
const canvas = document.getElementById('map-canvas');
const ctx = canvas.getContext('2d');
const mapContainer = document.getElementById('map-container');
const statusMessageEl = document.getElementById('status-message');

// Global Scale Factor (Pixels per Centimeter)
// We calculate ONE scale factor and use it for both X and Y to prevent stretching.
let pixelsPerCm = 1;

// Global State
let socket = null;
let pollingIntervalId = null;
const FALLBACK_INTERVAL_MS = 500;
let canModifySettings = true;
let statusMessageTimeout = null;
let lastSidebarSignature = null;

// Zone Drawing State
let isDrawingZone = false;
let isResizingZone = false;
let resizingZoneId = null;
let zoneStartX = 0, zoneStartY = 0;
let currentZoneRect = null;
let zoneCounter = 1;

// ==========================================
// 1. MAPPING & RESIZE LOGIC (CRITICAL FIX)
// ==========================================

function resizeCanvas() {
    const mainContent = document.getElementById('main-content');
    
    // 1. Determine available space on screen
    const availableWidth = Math.max(mainContent.clientWidth - 40, 300); // Padding
    const availableHeight = window.innerHeight - 140; // Header + Padding

    // 2. Determine Real World Aspect Ratio (Based on CM)
    const safeW = mapWidthCm || 1000;
    const safeH = mapHeightCm || 1000;
    const mapAspectRatio = safeW / safeH;

    // 3. Calculate Canvas Size to "Fit" inside available space without distortion
    // Start by trying to fit the width
    let finalWidth = availableWidth;
    let finalHeight = finalWidth / mapAspectRatio;

    // If the calculated height is too tall for the screen, scale down based on height instead
    if (finalHeight > availableHeight) {
        finalHeight = availableHeight;
        finalWidth = finalHeight * mapAspectRatio;
    }

    // 4. Apply Dimensions to HTML
    mapContainer.style.width = `${finalWidth}px`;
    mapContainer.style.height = `${finalHeight}px`;
    canvas.width = finalWidth;
    canvas.height = finalHeight;

    // 5. Calculate Uniform Scale Factor (1 cm = ? pixels)
    // This ensures 100cm Horizontal looks exactly the same length as 100cm Vertical
    pixelsPerCm = finalWidth / safeW;

    // Redraw if we have data to ensure dots stay in correct place
    if (window.lastData) {
        draw(window.lastData);
    }
}

// Helper: Convert Real World CM -> Screen Pixels
function toScreen(cm) {
    return cm * pixelsPerCm;
}

// Helper: Convert Screen Pixels -> Real World CM
function toWorld(px) {
    return px / pixelsPerCm;
}

// ==========================================
// 2. DRAWING LOGIC
// ==========================================

function draw(data) {
    // Clear screen
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    
    // A. Draw Zones
    if (data.zones) {
        data.zones.forEach(zone => {
            const x1 = toScreen(zone.x1);
            const y1 = toScreen(zone.y1);
            const x2 = toScreen(zone.x2);
            const y2 = toScreen(zone.y2);
            
            // Calculate Width/Height based on screen coordinates
            const width = x2 - x1;
            const height = y2 - y1;
            
            const isAlerted = data.alerts && Object.values(data.alerts).some(zoneIds => zoneIds.includes(zone.id));
            const severity = zone.severity || 'WARNING';
            const hexColor = zone.color || '#ff0000';
            
            // Convert hex to RGB for opacity
            const r = parseInt(hexColor.slice(1, 3), 16);
            const g = parseInt(hexColor.slice(3, 5), 16);
            const b = parseInt(hexColor.slice(5, 7), 16);
            
            if (isAlerted) {
                ctx.fillStyle = severity === 'ALERT' ? 'rgba(220, 53, 69, 0.4)' : 'rgba(255, 193, 7, 0.4)';
                ctx.strokeStyle = severity === 'ALERT' ? '#dc3545' : '#ffc107';
                ctx.lineWidth = 3;
            } else {
                ctx.fillStyle = `rgba(${r}, ${g}, ${b}, 0.2)`;
                ctx.strokeStyle = hexColor;
                ctx.lineWidth = 2;
            }
            
            ctx.fillRect(x1, y1, width, height);
            ctx.strokeRect(x1, y1, width, height);
            
            // Label
            ctx.fillStyle = '#000';
            ctx.font = 'bold 12px Arial';
            ctx.fillText(zone.name, x1 + 5, y1 + 15);
        });
    }
    
    // B. Draw Anchors (Blue)
    data.anchors.forEach(anchor => {
        if (anchor.status) {
            const x = toScreen(anchor.x);
            const y = toScreen(anchor.y);
            
            ctx.fillStyle = 'rgba(0, 123, 255, 0.8)';
            ctx.beginPath(); 
            ctx.arc(x, y, 8, 0, 2 * Math.PI); 
            ctx.fill();
            
            ctx.fillStyle = '#000'; 
            ctx.font = '12px Arial';
            
            // Keep text on screen if dot is near right edge
            let tx = x + 12;
            let ty = y + 4;
            if (x > canvas.width - 50) tx = x - 70;
            
            ctx.fillText(`${anchor.name} (${Math.round(anchor.x)},${Math.round(anchor.y)})`, tx, ty);
        }
    });

    // C. Draw Tags (Red)
    data.tags.forEach(tag => {
        if (tag.status) {
            const x = toScreen(tag.x);
            const y = toScreen(tag.y);
            
            ctx.fillStyle = 'rgba(255, 0, 0, 0.9)';
            ctx.beginPath(); 
            ctx.arc(x, y, 10, 0, 2 * Math.PI); 
            ctx.fill();
            
            ctx.strokeStyle = 'white';
            ctx.lineWidth = 2; 
            ctx.stroke();
            
            ctx.fillStyle = '#000'; 
            ctx.font = 'bold 14px Arial';
            ctx.fillText(tag.name, x + 15, y + 5);
        }
    });

    // D. Draw Current Zone (Preview)
    if (currentZoneRect && (isDrawingZone || isResizingZone)) {
        const x1 = toScreen(currentZoneRect.x1);
        const y1 = toScreen(currentZoneRect.y1);
        const x2 = toScreen(currentZoneRect.x2);
        const y2 = toScreen(currentZoneRect.y2);
        
        const w = x2 - x1;
        const h = y2 - y1;
        
        ctx.strokeStyle = '#ff0000';
        ctx.lineWidth = 2;
        ctx.setLineDash([5, 5]);
        ctx.strokeRect(x1, y1, w, h);
        ctx.setLineDash([]);
    }
}

// ==========================================
// 3. DATA HANDLING & UI UPDATES
// ==========================================

function updateMapDimensions(data) {
    const newWidth = data.map_width_cm;
    const newHeight = data.map_height_cm;

    // Only resize if dimensions actually changed
    if (newWidth !== mapWidthCm || newHeight !== mapHeightCm) {
        mapWidthCm = newWidth;
        mapHeightCm = newHeight;
        resizeCanvas();
    }
    
    // Update Inputs (Convert CM to Meters for display)
    if (document.activeElement.id !== 'area-width') {
        document.getElementById('area-width').value = (mapWidthCm / 100).toFixed(1);
    }
    if (document.activeElement.id !== 'area-height') {
        document.getElementById('area-height').value = (mapHeightCm / 100).toFixed(1);
    }
}

function handleTrackingData(data) {
    if (!data) return;
    window.lastData = data;
    
    updateMapDimensions(data);
    
    // Check if we need to update the sidebar (expensive DOM operation)
    const currentSig = JSON.stringify({
        anc: data.anchors, 
        tags: data.tags.map(t => t.name), 
        zones: data.zones, 
        alerts: data.alerts
    });
    
    if (currentSig !== lastSidebarSignature) {
        lastSidebarSignature = currentSig;
        updateSidebar(data);
    }
    
    draw(data);
}

// ==========================================
// 4. MOUSE INTERACTION (DRAWING)
// ==========================================

// 1. Start Drawing
document.getElementById('draw-zone-btn').addEventListener('click', function() {
    if (!ensureCanModify()) return;
    
    if (isResizingZone) {
        isResizingZone = false;
        resizingZoneId = null;
        isDrawingZone = false;
    } else {
        isDrawingZone = !isDrawingZone;
    }
    
    const form = document.getElementById('draw-zone-form');
    if (isDrawingZone) {
        this.textContent = isResizingZone ? 'Cancel Resize' : 'Cancel Drawing';
        this.className = 'btn-danger';
        canvas.style.cursor = 'crosshair';
        if (!isResizingZone) form.classList.add('active');
    } else {
        this.textContent = 'Draw Zone';
        this.className = 'btn-warning';
        canvas.style.cursor = 'default';
        form.classList.remove('active');
        currentZoneRect = null;
    }
});

// 2. Mouse Down
canvas.addEventListener('mousedown', e => {
    if (!canModifySettings) return;
    if (!isDrawingZone && !isResizingZone) return;
    
    const rect = canvas.getBoundingClientRect();
    // Convert Screen Pixel -> Real World CM
    zoneStartX = toWorld(e.clientX - rect.left);
    zoneStartY = toWorld(e.clientY - rect.top);
    
    currentZoneRect = { x1: zoneStartX, y1: zoneStartY, x2: zoneStartX, y2: zoneStartY };
});

// 3. Mouse Move
canvas.addEventListener('mousemove', e => {
    if (!currentZoneRect) return;
    const rect = canvas.getBoundingClientRect();
    
    currentZoneRect.x2 = toWorld(e.clientX - rect.left);
    currentZoneRect.y2 = toWorld(e.clientY - rect.top);
    
    if (window.lastData) {
        draw(window.lastData); // Redraw to show box
    }
});

// 4. Mouse Up (Finish)
canvas.addEventListener('mouseup', async e => {
    if (!currentZoneRect) return;
    const rect = canvas.getBoundingClientRect();
    
    const x2 = toWorld(e.clientX - rect.left);
    const y2 = toWorld(e.clientY - rect.top);
    
    // Check size (must be > 10cm to count)
    if (Math.abs(x2 - zoneStartX) > 10 && Math.abs(y2 - zoneStartY) > 10) {
        const name = document.getElementById('zone-name-input').value || `Zone ${zoneCounter}`;
        const color = document.getElementById('zone-color-input').value;
        const severity = document.getElementById('zone-severity-input').value;
        
        // Normalize coordinates (min/max) so x1 is always top-left
        const payload = {
            name, color, severity,
            x1: Math.min(zoneStartX, x2), y1: Math.min(zoneStartY, y2),
            x2: Math.max(zoneStartX, x2), y2: Math.max(zoneStartY, y2)
        };
        
        if (isResizingZone && resizingZoneId) {
            payload.id = resizingZoneId;
            await fetch('/update_zone', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(payload)});
        } else {
            zoneCounter++;
            await fetch('/create_zone', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(payload)});
            document.getElementById('zone-name-input').value = '';
        }
        setStatusMessage("Zone Saved");
    }
    
    // Reset
    isDrawingZone = false;
    isResizingZone = false;
    currentZoneRect = null;
    resizingZoneId = null;
    
    const btn = document.getElementById('draw-zone-btn');
    btn.textContent = 'Draw Zone';
    btn.className = 'btn-warning';
    document.getElementById('draw-zone-form').classList.remove('active');
    canvas.style.cursor = 'default';
});

// ==========================================
// 5. SIDEBAR UTILITIES
// ==========================================

function setStatusMessage(message, duration = 3000) {
    if (!statusMessageEl) return;
    statusMessageEl.textContent = message;
    if (statusMessageTimeout) clearTimeout(statusMessageTimeout);
    if (duration > 0 && message) {
        statusMessageTimeout = setTimeout(() => {
            statusMessageEl.textContent = '';
        }, duration);
    }
}

function updateSidebar(data) {
    // Anchors Input
    const anchorDiv = document.getElementById('anchor-controls');
    if (anchorDiv.children.length === 0 || anchorDiv.children.length !== data.anchors.length) {
        anchorDiv.innerHTML = '<h3>Anchor Positions (cm)</h3>';
        data.anchors.forEach(a => {
            const d = document.createElement('div');
            d.className = 'anchor-input';
            d.innerHTML = `<label>${a.name}:</label>
                <input type="number" id="${a.name}-x" value="${a.x}" step="1">
                <input type="number" id="${a.name}-y" value="${a.y}" step="1">`;
            anchorDiv.appendChild(d);
        });
        applyAdminStateToDynamicElements();
    }

    // Tags Info
    const tagDiv = document.getElementById('tag-positions');
    tagDiv.innerHTML = '<h3>Tag Data</h3>';
    data.tags.forEach(tag => {
        const box = document.createElement('div');
        box.className = 'tag-info-box';
        let html = `<p>${tag.name}: (${Math.round(tag.x)}, ${Math.round(tag.y)}) cm</p><ul>`;
        
        if (tag.ranges && tag.ranges.length) {
            tag.ranges.forEach((r, i) => {
                if (data.anchors[i]) {
                    html += `<li>${data.anchors[i].name}: ${r} cm</li>`;
                }
            });
        } else {
            html += '<li>No range data</li>';
        }
        html += '</ul>';
        box.innerHTML = html;
        tagDiv.appendChild(box);
    });
    
    // Dropdown
    const sel = document.getElementById('tag-select-dropdown');
    if (sel.options.length !== data.tags.length) {
        const val = sel.value;
        sel.innerHTML = '';
        data.tags.forEach(t => {
            const opt = document.createElement('option');
            opt.value = t.name;
            opt.textContent = t.name;
            sel.appendChild(opt);
        });
        if(val) sel.value = val;
    }

    // Zones & Alerts
    updateZoneList(data.zones || []);
    updateAlerts(data.alerts || {}, data.new_entries || {}, data.zones || []);
}

// Zone List Management
const openEditForms = new Set();

function updateZoneList(zones) {
    const list = document.getElementById('zone-list');
    if (document.activeElement && document.activeElement.closest('.zone-edit-form')) return;

    // Avoid redraw if data matches
    const currentIds = zones.map(z => z.id).join(',');
    const existingIds = Array.from(list.querySelectorAll('.save-zone-btn')).map(b => b.getAttribute('data-zone-id')).join(',');
    if (currentIds === existingIds && list.children.length > 0) return;

    list.innerHTML = '';
    zones.forEach(z => {
        const item = document.createElement('div');
        item.className = 'zone-item';
        const isOpen = openEditForms.has(String(z.id));
        
        item.innerHTML = `
            <div class="zone-item-header">
                <div><span class="zone-item-name">${z.name}</span> <span class="zone-item-severity severity-${z.severity.toLowerCase()}">${z.severity}</span></div>
                <div class="zone-item-controls">
                    <button class="zone-item-edit" onclick="toggleEdit('${z.id}')">Edit</button>
                    <button class="zone-item-delete" onclick="deleteZone(${z.id})">Delete</button>
                </div>
            </div>
            <div class="zone-edit-form ${isOpen ? 'active' : ''}" id="edit-form-${z.id}">
                <label>Name:</label><input type="text" id="edit-name-${z.id}" value="${z.name}">
                <label>Color:</label><input type="color" id="edit-color-${z.id}" value="${z.color}">
                <label>Severity:</label>
                <select id="edit-severity-${z.id}">
                    <option value="WARNING" ${z.severity==='WARNING'?'selected':''}>WARNING</option>
                    <option value="ALERT" ${z.severity==='ALERT'?'selected':''}>ALERT</option>
                </select>
                <label>Boundaries (cm):</label>
                <div style="display:grid; grid-template-columns:1fr 1fr; gap:5px">
                    <input type="number" id="edit-x1-${z.id}" value="${z.x1}">
                    <input type="number" id="edit-y1-${z.id}" value="${z.y1}">
                    <input type="number" id="edit-x2-${z.id}" value="${z.x2}">
                    <input type="number" id="edit-y2-${z.id}" value="${z.y2}">
                </div>
                <button class="resize-zone-btn" onclick="startResize(${z.id})">Resize on Map</button>
                <button class="save-zone-btn" onclick="saveZone(${z.id})">Save</button>
            </div>
        `;
        list.appendChild(item);
    });
    applyAdminStateToDynamicElements();
}

// Global Handlers for Dynamic Elements
window.toggleEdit = (id) => {
    const f = document.getElementById(`edit-form-${id}`);
    f.classList.toggle('active');
    if(f.classList.contains('active')) openEditForms.add(String(id));
    else openEditForms.delete(String(id));
};

window.deleteZone = async (id) => {
    await fetch('/delete_zone', {
        method: 'POST', headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({id: id})
    });
};

window.saveZone = async (id) => {
    const name = document.getElementById(`edit-name-${id}`).value;
    const color = document.getElementById(`edit-color-${id}`).value;
    const severity = document.getElementById(`edit-severity-${id}`).value;
    const x1 = parseFloat(document.getElementById(`edit-x1-${id}`).value);
    const y1 = parseFloat(document.getElementById(`edit-y1-${id}`).value);
    const x2 = parseFloat(document.getElementById(`edit-x2-${id}`).value);
    const y2 = parseFloat(document.getElementById(`edit-y2-${id}`).value);
    
    await fetch('/update_zone', {
        method: 'POST', headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({id, name, color, severity, x1, y1, x2, y2})
    });
    openEditForms.add(String(id));
};

window.startResize = (id) => {
    isDrawingZone = true;
    isResizingZone = true;
    resizingZoneId = id;
    
    const btn = document.getElementById('draw-zone-btn');
    btn.textContent = 'Cancel Resize';
    btn.className = 'btn-danger';
    canvas.style.cursor = 'crosshair';
    setStatusMessage("Drag on map to resize zone");
};

function updateAlerts(alerts, newEntries, zones) {
    const container = document.getElementById('alert-container');
    const sig = JSON.stringify(alerts);
    if (container.getAttribute('data-sig') === sig && Object.keys(newEntries).length === 0) return;
    container.setAttribute('data-sig', sig);
    
    container.innerHTML = '';
    Object.keys(alerts).forEach(tagName => {
        alerts[tagName].forEach(zid => {
            const z = zones.find(z => z.id === zid);
            if (z) {
                const div = document.createElement('div');
                const cls = z.severity.toLowerCase();
                div.className = `alert-item ${cls}`;
                div.innerHTML = `<p><span class="alert-severity-badge ${cls}">${z.severity}</span> ${tagName} in ${z.name}</p>`;
                container.appendChild(div);
            }
        });
    });
    
    // Audio Alerts
    Object.keys(newEntries).forEach(tag => {
        newEntries[tag].forEach(zid => {
            const z = zones.find(z => z.id === zid);
            if (z) {
                try {
                    const ctx = new (window.AudioContext || window.webkitAudioContext)();
                    const osc = ctx.createOscillator();
                    const gain = ctx.createGain();
                    osc.connect(gain);
                    gain.connect(ctx.destination);
                    osc.frequency.value = z.severity === 'ALERT' ? 880 : 440;
                    gain.gain.exponentialRampToValueAtTime(0.00001, ctx.currentTime + 0.5);
                    osc.start();
                    osc.stop(ctx.currentTime + 0.5);
                } catch(e) {}
            }
        });
    });
}

// ==========================================
// 6. PERMISSIONS & INIT
// ==========================================

function toggleInteractiveElements(selectors, enabled) {
    selectors.forEach(sel => document.querySelectorAll(sel).forEach(el => {
        if('disabled' in el) el.disabled = !enabled;
        el.classList.toggle('disabled-control', !enabled);
    }));
}
function applyAdminStateToDynamicElements() {
    toggleInteractiveElements(['.zone-item button', '.zone-edit-form input', '.zone-edit-form select', '.zone-edit-form button'], canModifySettings);
}
function updateReadOnlyState(canModify) {
    canModifySettings = canModify;
    document.body.classList.toggle('read-only-mode', !canModify);
    toggleInteractiveElements(['#save-anchors-btn', '#rename-tag-btn', '#save-area-btn', '#draw-zone-btn', '#select-image-btn', '.anchor-input input', '#new-tag-name', '#area-width', '#area-height', '#zone-name-input', '#zone-severity-input', '#zone-color-input'], canModify);
}
function ensureCanModify() {
    if(canModifySettings) return true;
    setStatusMessage("Read-only mode"); return false;
}

// Button Listeners
document.getElementById('save-anchors-btn').addEventListener('click', async () => {
    if (!ensureCanModify()) return;
    const anchors = [];
    document.querySelectorAll('.anchor-input').forEach(div => {
        const name = div.querySelector('label').innerText.replace(':','');
        const inputs = div.querySelectorAll('input');
        anchors.push({ name, x: inputs[0].value, y: inputs[1].value });
    });
    await fetch('/update_anchors', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(anchors)});
    setStatusMessage("Anchors Updated");
});

document.getElementById('save-area-btn').addEventListener('click', async () => {
    if (!ensureCanModify()) return;
    const w = parseFloat(document.getElementById('area-width').value) * 100; // M -> CM
    const h = parseFloat(document.getElementById('area-height').value) * 100; // M -> CM
    await fetch('/update_area', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({width:w, height:h})});
    setStatusMessage("Map Size Updated");
});

document.getElementById('rename-tag-btn').addEventListener('click', async () => {
    if (!ensureCanModify()) return;
    const oldName = document.getElementById('tag-select-dropdown').value;
    const newName = document.getElementById('new-tag-name').value;
    if (newName) {
        await fetch('/rename_tag', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({old_name:oldName, new_name:newName})});
        document.getElementById('new-tag-name').value = '';
        setStatusMessage("Tag Renamed");
    }
});

// UI Toggles
document.getElementById('sidebar-toggle').addEventListener('click', () => {
    document.getElementById('sidebar').classList.toggle('collapsed');
    document.getElementById('main-content').classList.toggle('centered');
    setTimeout(resizeCanvas, 300);
});
document.querySelectorAll('.accordion-header').forEach(h => {
    h.addEventListener('click', () => {
        h.classList.toggle('active');
        document.getElementById(`accordion-${h.getAttribute('data-section')}`).classList.toggle('active');
    });
});
document.getElementById('select-image-btn').addEventListener('click', () => document.getElementById('image-upload').click());
document.getElementById('image-upload').addEventListener('change', (e) => {
    const f = e.target.files[0];
    if (f) {
        const r = new FileReader();
        r.onload = (ev) => mapContainer.style.backgroundImage = `url(${ev.target.result})`;
        r.readAsDataURL(f);
    }
});

// Network
function initializeRealtimeUpdates() {
    if (typeof io === 'undefined') {
        console.warn("SocketIO missing, polling.");
        startPolling();
        return;
    }
    socket = io({transports: ['websocket', 'polling']});
    socket.on('connect', stopPolling);
    socket.on('tracking_update', handleTrackingData);
    socket.on('disconnect', startPolling);
}
function startPolling() {
    if (pollingIntervalId) return;
    fetchSnapshot();
    pollingIntervalId = setInterval(fetchSnapshot, FALLBACK_INTERVAL_MS);
}
function stopPolling() {
    if (pollingIntervalId) clearInterval(pollingIntervalId);
    pollingIntervalId = null;
}
async function fetchSnapshot() {
    try {
        const r = await fetch('/data');
        handleTrackingData(await r.json());
    } catch(e){}
}

// Boot
window.addEventListener('resize', resizeCanvas);
resizeCanvas();
(async function init() {
    try {
        const r = await fetch('/permissions');
        const p = await r.json();
        updateReadOnlyState(p.can_modify);
    } catch(e){}
    initializeRealtimeUpdates();
    fetchSnapshot();
})();
