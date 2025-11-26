let mapWidthCm = 1000;
let mapHeightCm = 800;
const canvas = document.getElementById('map-canvas');
const ctx = canvas.getContext('2d');
const mapContainer = document.getElementById('map-container');
const statusMessageEl = document.getElementById('status-message');

function getSafeMapWidth() {
    return mapWidthCm > 0 ? mapWidthCm : 1;
}

function getSafeMapHeight() {
    return mapHeightCm > 0 ? mapHeightCm : 1;
}

function cmToCanvasX(valueCm) {
    const normalized = Math.min(Math.max(valueCm / getSafeMapWidth(), 0), 1);
    return normalized * canvas.width;
}

function cmToCanvasY(valueCm) {
    const normalized = Math.min(Math.max(valueCm / getSafeMapHeight(), 0), 1);
    return normalized * canvas.height;
}

function canvasPxToCmX(px, referenceWidth = canvas.width) {
    const widthPx = referenceWidth || 1;
    const normalized = px / widthPx;
    return normalized * getSafeMapWidth();
}

function canvasPxToCmY(px, referenceHeight = canvas.height) {
    const heightPx = referenceHeight || 1;
    const normalized = px / heightPx;
    return normalized * getSafeMapHeight();
}

function setStatusMessage(message, duration = 3000) {
    if (!statusMessageEl) {
        return;
    }
    statusMessageEl.textContent = message;
    if (statusMessageTimeout) {
        clearTimeout(statusMessageTimeout);
    }
    if (duration > 0 && message) {
        statusMessageTimeout = setTimeout(() => {
            statusMessageEl.textContent = '';
            statusMessageTimeout = null;
        }, duration);
    }
}

function toggleInteractiveElements(selectors, enabled) {
    selectors.forEach(selector => {
        document.querySelectorAll(selector).forEach(element => {
            if ('disabled' in element) {
                element.disabled = !enabled;
            }
            element.classList.toggle('disabled-control', !enabled);
        });
    });
}

function applyAdminStateToDynamicElements() {
    const selectors = [
        '.zone-item button',
        '.zone-edit-form input',
        '.zone-edit-form select',
        '.zone-edit-form button'
    ];
    toggleInteractiveElements(selectors, canModifySettings);
}

function updateReadOnlyState(canModify) {
    canModifySettings = canModify;
    const isReadOnly = !canModify;
    document.body.classList.toggle('read-only-mode', isReadOnly);
    const staticSelectors = [
        '#save-anchors-btn',
        '#rename-tag-btn',
        '#save-area-btn',
        '#draw-zone-btn',
        '#select-image-btn',
        '.anchor-input input',
        '#new-tag-name',
        '#area-width',
        '#area-height',
        '#zone-name-input',
        '#zone-severity-input',
        '#zone-color-input',
        '#zone-list button',
        '#draw-zone-form input',
        '#draw-zone-form select'
    ];
    toggleInteractiveElements(staticSelectors, canModifySettings);
    applyAdminStateToDynamicElements();
}

function ensureCanModify() {
    if (canModifySettings) {
        return true;
    }
    setStatusMessage('Read-only mode: changes are disabled on this device.', 4000);
    return false;
}

function resizeCanvas() {
    const mainContent = document.getElementById('main-content');
    const availableWidth = Math.max(mainContent.clientWidth - 20, 320);
    const aspectRatio = getSafeMapWidth() / getSafeMapHeight();

    // Determine the maximum width that can fit in the available space
    const maxWidth = availableWidth;
    const maxHeightBasedOnWindow = window.innerHeight - 120; // Account for title, padding, top bar
    
    // Calculate dimensions while preserving aspect ratio
    let containerWidth = maxWidth;
    let containerHeight = containerWidth / aspectRatio;
    
    // If calculated height exceeds max, constrain by height instead
    if (containerHeight > maxHeightBasedOnWindow) {
        containerHeight = maxHeightBasedOnWindow;
        containerWidth = containerHeight * aspectRatio;
    }

    mapContainer.style.width = `${containerWidth}px`;
    mapContainer.style.maxWidth = `${availableWidth}px`;
    mapContainer.style.height = `${containerHeight}px`;
    
    canvas.width = containerWidth;
    canvas.height = containerHeight;
    
    if (window.lastData) {
        draw(window.lastData);
    }
}

function draw(data) {
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    
    // Draw zones first (behind other elements)
    if (data.zones) {
        data.zones.forEach(zone => {
            const x1 = cmToCanvasX(zone.x1);
            const y1 = cmToCanvasY(zone.y1);
            const x2 = cmToCanvasX(zone.x2);
            const y2 = cmToCanvasY(zone.y2);
            const width = x2 - x1;
            const height = y2 - y1;
            
            // Check if any tag is in this zone
            const isAlerted = data.alerts && Object.values(data.alerts).some(zoneIds => zoneIds.includes(zone.id));
            const severity = zone.severity || 'WARNING';
            
            // Convert hex color to rgba for fill
            const hexColor = zone.color || '#ff0000';
            const r = parseInt(hexColor.slice(1, 3), 16);
            const g = parseInt(hexColor.slice(3, 5), 16);
            const b = parseInt(hexColor.slice(5, 7), 16);
            
            // Draw zone rectangle with severity-based styling
            if (isAlerted) {
                // When alerted, use severity-based colors
                if (severity === 'ALERT') {
                    ctx.fillStyle = 'rgba(220, 53, 69, 0.4)'; // Red for ALERT
                    ctx.strokeStyle = '#dc3545';
                } else {
                    ctx.fillStyle = 'rgba(255, 193, 7, 0.4)'; // Yellow for WARNING
                    ctx.strokeStyle = '#ffc107';
                }
            } else {
                // Normal state - use zone color
                ctx.fillStyle = `rgba(${r}, ${g}, ${b}, 0.2)`;
                ctx.strokeStyle = hexColor;
            }
            ctx.fillRect(x1, y1, width, height);
            ctx.lineWidth = severity === 'ALERT' ? 3 : 2; // Thicker border for ALERT
            ctx.strokeRect(x1, y1, width, height);
            
            // Draw zone label with severity indicator
            ctx.fillStyle = '#000';
            ctx.font = 'bold 12px Arial';
            const labelText = `${zone.name} [${severity}]`;
            ctx.fillText(labelText, x1 + 5, y1 + 15);
        });
    }
    
    data.anchors.forEach(anchor => {
        if (anchor.status) {
            const x = cmToCanvasX(anchor.x); 
            const y = cmToCanvasY(anchor.y);
            ctx.fillStyle = 'rgba(0, 123, 255, 0.8)';
            ctx.beginPath(); ctx.arc(x, y, 8, 0, 2 * Math.PI); ctx.fill();
            ctx.fillStyle = '#000'; ctx.font = '12px Arial';
            const labelText = `${anchor.name} (${anchor.x}, ${anchor.y})`;
            const textMetrics = ctx.measureText(labelText);
            const textWidth = textMetrics.width;
            const textHeight = 12; // Approximate text height
            // Adjust label position to stay within canvas bounds
            let labelX = x + 12;
            let labelY = y + 4;
            // Check right edge
            if (labelX + textWidth > canvas.width) {
                labelX = x - textWidth - 12;
            }
            // Check left edge
            if (labelX < 0) {
                labelX = 5;
            }
            // Check bottom edge
            if (labelY + textHeight > canvas.height) {
                labelY = y - textHeight - 4;
            }
            // Check top edge
            if (labelY < textHeight) {
                labelY = textHeight + 4;
            }
            ctx.fillText(labelText, labelX, labelY);
        }
    });
    data.tags.forEach(tag => {
        if (tag.status) {
            const x = cmToCanvasX(tag.x); 
            const y = cmToCanvasY(tag.y);
            ctx.fillStyle = 'rgba(255, 0, 0, 0.9)';
            ctx.beginPath(); ctx.arc(x, y, 10, 0, 2 * Math.PI); ctx.fill();
            ctx.strokeStyle = 'rgba(255, 255, 255, 0.8)';
            ctx.lineWidth = 2; ctx.stroke();
            ctx.fillStyle = '#000'; ctx.font = 'bold 14px Arial';
            ctx.fillText(tag.name, x + 15, y + 5);
        }
    });
}

// Zone drawing state
let isDrawingZone = false;
let isResizingZone = false;
let resizingZoneId = null;
let zoneStartX = 0, zoneStartY = 0;
let currentZoneRect = null;
let zoneCounter = 1;
let socket = null;
let pollingIntervalId = null;
const FALLBACK_INTERVAL_MS = 1000;
let canModifySettings = true;
let statusMessageTimeout = null;

function updateSidebar(data) {
    const anchorControlsDiv = document.getElementById('anchor-controls');
    if (anchorControlsDiv.children.length <= 1) { 
        data.anchors.forEach(anchor => {
            const div = document.createElement('div');
            div.className = 'anchor-input';
            div.innerHTML = `<label for="${anchor.name}">${anchor.name}:</label>
                <input type="number" id="${anchor.name}-x" value="${anchor.x}" step="1">
                <input type="number" id="${anchor.name}-y" value="${anchor.y}" step="1">`;
            anchorControlsDiv.appendChild(div);
        });
    }
    const tagSelect = document.getElementById('tag-select-dropdown');
    const currentlySelected = tagSelect.value; // Remember what was selected
    tagSelect.innerHTML = ''; // Clear old options
    data.tags.forEach(tag => {
        const option = document.createElement('option');
        option.value = tag.name;
        option.textContent = tag.name;
        tagSelect.appendChild(option);
    });
    // If the previously selected tag still exists, re-select it
    if (currentlySelected) {
        tagSelect.value = currentlySelected;
    }
    
    // Update zone list
    updateZoneList(data.zones || []);
    
    // Update alerts
    updateAlerts(data.alerts || {}, data.new_entries || {}, data.zones || []);
    
    const tagPositionsDiv = document.getElementById('tag-positions');
    tagPositionsDiv.innerHTML = '<h3>Tag Data</h3>';
    data.tags.forEach(tag => {
        const tagBox = document.createElement('div');
        tagBox.className = 'tag-info-box';
        let rangesHTML = '<ul><li>No range data</li></ul>';
        if (tag.ranges && tag.ranges.length > 0) {
            rangesHTML = '<ul>';
            tag.ranges.forEach((range, index) => {
                if (index < data.anchors.length) { // Ensure we don't go out of bounds
                   rangesHTML += `<li>Range to ${data.anchors[index].name}: ${range} cm</li>`;
                }
            });
            rangesHTML += '</ul>';
        }
        tagBox.innerHTML = `<p>${tag.name}: (${tag.x}, ${tag.y}) cm</p>${rangesHTML}`;
        tagPositionsDiv.appendChild(tagBox);
    });
}

// Track which edit forms are open
const openEditForms = new Set();

function updateZoneList(zones) {
    const zoneListDiv = document.getElementById('zone-list');
    
    // Check if user is currently interacting with any edit form
    const activeElement = document.activeElement;
    const isEditing = activeElement && (
        activeElement.classList.contains('zone-edit-form') ||
        activeElement.closest('.zone-edit-form') !== null ||
        activeElement.id && activeElement.id.startsWith('edit-')
    );
    
    // If user is editing, don't update to avoid disrupting their input
    if (isEditing) {
        return;
    }
    
    // Preserve which edit forms are currently open
    const currentlyOpen = new Set();
    document.querySelectorAll('.zone-edit-form.active').forEach(form => {
        const zoneId = form.id.replace('edit-form-', '');
        currentlyOpen.add(zoneId);
    });
    
    // Only update if zones actually changed (to avoid closing open forms)
    const currentZoneIds = new Set(zones.map(z => z.id.toString()));
    const existingZoneIds = new Set(Array.from(zoneListDiv.querySelectorAll('.zone-item')).map(item => {
        const editBtn = item.querySelector('.zone-item-edit');
        return editBtn ? editBtn.getAttribute('data-zone-id') : null;
    }).filter(id => id !== null));
    
    // Check if zones have actually changed
    const zonesChanged = zones.length !== existingZoneIds.size || 
        !zones.every(z => existingZoneIds.has(z.id.toString()));
    
    // Check if name fields exist (for zones created before name editing was added)
    let needsRebuild = false;
    if (!zonesChanged && zoneListDiv.children.length > 0) {
        zones.forEach(zone => {
            const nameInput = document.getElementById(`edit-name-${zone.id}`);
            if (!nameInput) {
                needsRebuild = true; // Force rebuild if name field is missing
            }
        });
    }
    
    // Only rebuild if zones changed or if we need to update values
    if (!zonesChanged && !needsRebuild && zoneListDiv.children.length > 0) {
        // Just update the severity badges and values without rebuilding
        zones.forEach(zone => {
            const severity = zone.severity || 'WARNING';
            const severityClass = severity.toLowerCase();
            const editForm = document.getElementById(`edit-form-${zone.id}`);
            if (editForm) {
                // Only update if form is not active (user not editing)
                if (!editForm.classList.contains('active')) {
                    // Update name input if it exists
                    const nameInput = document.getElementById(`edit-name-${zone.id}`);
                    if (nameInput && nameInput.value !== zone.name) {
                        nameInput.value = zone.name;
                    }
                    // Update color input if it exists
                    const colorInput = document.getElementById(`edit-color-${zone.id}`);
                    if (colorInput && colorInput.value !== zone.color) {
                        colorInput.value = zone.color || '#ff0000';
                    }
                    // Update severity select if it exists
                    const severitySelect = document.getElementById(`edit-severity-${zone.id}`);
                    if (severitySelect && severitySelect.value !== severity) {
                        severitySelect.value = severity;
                    }
                    // Update coordinate inputs if they exist
                    const x1Input = document.getElementById(`edit-x1-${zone.id}`);
                    const y1Input = document.getElementById(`edit-y1-${zone.id}`);
                    const x2Input = document.getElementById(`edit-x2-${zone.id}`);
                    const y2Input = document.getElementById(`edit-y2-${zone.id}`);
                    if (x1Input) x1Input.value = zone.x1;
                    if (y1Input) y1Input.value = zone.y1;
                    if (x2Input) x2Input.value = zone.x2;
                    if (y2Input) y2Input.value = zone.y2;
                }
                // Update zone name and severity badge (always safe to update)
                const zoneNameSpan = editForm.parentElement.querySelector('.zone-item-name');
                if (zoneNameSpan) {
                    zoneNameSpan.textContent = zone.name;
                }
                const severityBadge = editForm.parentElement.querySelector('.zone-item-severity');
                if (severityBadge) {
                    severityBadge.textContent = severity;
                    severityBadge.className = `zone-item-severity severity-${severityClass}`;
                }
            }
        });
        return; // Don't rebuild, just return
    }
    
    // Rebuild the list
    zoneListDiv.innerHTML = '';
    zones.forEach(zone => {
        const zoneItem = document.createElement('div');
        zoneItem.className = 'zone-item';
        const severity = zone.severity || 'WARNING';
        const severityClass = severity.toLowerCase();
        const isOpen = currentlyOpen.has(zone.id.toString());
        zoneItem.innerHTML = `
            <div class="zone-item-header">
                <div>
                    <span class="zone-item-name">${zone.name}</span>
                    <span class="zone-item-severity severity-${severityClass}">${severity}</span>
                </div>
                <div class="zone-item-controls">
                    <button class="zone-item-edit" data-zone-id="${zone.id}">Edit</button>
                    <button class="zone-item-delete" data-zone-id="${zone.id}">Delete</button>
                </div>
            </div>
            <div class="zone-edit-form ${isOpen ? 'active' : ''}" id="edit-form-${zone.id}">
                <label>Zone Name:</label>
                <input type="text" id="edit-name-${zone.id}" value="${zone.name}" placeholder="Enter zone name">
                <label>Color:</label>
                <input type="color" id="edit-color-${zone.id}" value="${zone.color || '#ff0000'}">
                <label>Severity:</label>
                <select id="edit-severity-${zone.id}">
                    <option value="WARNING" ${severity === 'WARNING' ? 'selected' : ''}>WARNING</option>
                    <option value="ALERT" ${severity === 'ALERT' ? 'selected' : ''}>ALERT</option>
                </select>
                <label style="margin-top: 10px; border-top: 1px solid #ddd; padding-top: 10px;">Boundary (cm):</label>
                <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 5px; margin-bottom: 5px;">
                    <div>
                        <label style="font-size: 0.8em;">X1:</label>
                        <input type="number" id="edit-x1-${zone.id}" value="${zone.x1}" step="1" style="width: 100%;">
                    </div>
                    <div>
                        <label style="font-size: 0.8em;">Y1:</label>
                        <input type="number" id="edit-y1-${zone.id}" value="${zone.y1}" step="1" style="width: 100%;">
                    </div>
                    <div>
                        <label style="font-size: 0.8em;">X2:</label>
                        <input type="number" id="edit-x2-${zone.id}" value="${zone.x2}" step="1" style="width: 100%;">
                    </div>
                    <div>
                        <label style="font-size: 0.8em;">Y2:</label>
                        <input type="number" id="edit-y2-${zone.id}" value="${zone.y2}" step="1" style="width: 100%;">
                    </div>
                </div>
                <button class="resize-zone-btn" data-zone-id="${zone.id}" style="margin-top: 5px; padding: 5px 10px; background-color: #28a745; color: white; border: none; border-radius: 3px; cursor: pointer; font-size: 0.85em; width: 100%;">Resize on Map</button>
                <button class="save-zone-btn" data-zone-id="${zone.id}">Save</button>
            </div>
        `;
        zoneListDiv.appendChild(zoneItem);
    });
    
    // Add delete event listeners
    document.querySelectorAll('.zone-item-delete').forEach(btn => {
        btn.addEventListener('click', async (e) => {
            e.stopPropagation(); // Prevent event bubbling
            const zoneId = parseInt(btn.getAttribute('data-zone-id'));
            try {
                const response = await fetch('/delete_zone', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ id: zoneId })
                });
                const result = await response.json();
                if (result.status === 'success') {
                    // Zone list will be updated on next data fetch
                }
            } catch (error) {
                console.error('Error deleting zone:', error);
            }
        });
    });
    
    // Add edit toggle listeners
    document.querySelectorAll('.zone-item-edit').forEach(btn => {
        btn.addEventListener('click', (e) => {
            e.stopPropagation(); // Prevent event bubbling
            const zoneId = btn.getAttribute('data-zone-id');
            const editForm = document.getElementById(`edit-form-${zoneId}`);
            editForm.classList.toggle('active');
            if (editForm.classList.contains('active')) {
                openEditForms.add(zoneId);
            } else {
                openEditForms.delete(zoneId);
            }
        });
    });
    
    // Add save listeners
    document.querySelectorAll('.save-zone-btn').forEach(btn => {
        btn.addEventListener('click', async (e) => {
            e.stopPropagation(); // Prevent event bubbling
            const zoneId = parseInt(btn.getAttribute('data-zone-id'));
            const name = document.getElementById(`edit-name-${zoneId}`).value.trim();
            const color = document.getElementById(`edit-color-${zoneId}`).value;
            const severity = document.getElementById(`edit-severity-${zoneId}`).value;
            const x1 = parseFloat(document.getElementById(`edit-x1-${zoneId}`).value);
            const y1 = parseFloat(document.getElementById(`edit-y1-${zoneId}`).value);
            const x2 = parseFloat(document.getElementById(`edit-x2-${zoneId}`).value);
            const y2 = parseFloat(document.getElementById(`edit-y2-${zoneId}`).value);
            
            // Validate name
            if (!name) {
                alert('Zone name cannot be empty');
                return;
            }
            
            // Validate coordinates
            if (isNaN(x1) || isNaN(y1) || isNaN(x2) || isNaN(y2)) {
                alert('All coordinate values must be valid numbers');
                return;
            }
            
            try {
                const response = await fetch('/update_zone', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ 
                        id: zoneId, 
                        name: name, 
                        color: color, 
                        severity: severity,
                        x1: x1,
                        y1: y1,
                        x2: x2,
                        y2: y2
                    })
                });
                const result = await response.json();
                if (result.status === 'success') {
                    // Keep form open after save
                    openEditForms.add(zoneId.toString());
                    // Zone list will be updated on next data fetch
                } else {
                    alert(result.message || 'Error updating zone');
                }
            } catch (error) {
                console.error('Error updating zone:', error);
                alert('Error updating zone. Please try again.');
            }
        });
    });
    
    // Add resize on map listeners
    document.querySelectorAll('.resize-zone-btn').forEach(btn => {
        btn.addEventListener('click', (e) => {
            e.stopPropagation(); // Prevent event bubbling
            const zoneId = parseInt(btn.getAttribute('data-zone-id'));
            
            // Enter resize mode for this zone
            isDrawingZone = true;
            isResizingZone = true;
            resizingZoneId = zoneId;
            
            const drawBtn = document.getElementById('draw-zone-btn');
            drawBtn.textContent = 'Cancel Resize';
            drawBtn.classList.remove('btn-warning');
            drawBtn.classList.add('btn-danger');
            canvas.style.cursor = 'crosshair';
            
            // Show message
            setStatusMessage('Click and drag on the map to resize the zone.', 4000);
        });
    });

    applyAdminStateToDynamicElements();
}

function updateAlerts(currentAlerts, newEntries, zones) {
    const alertContainer = document.getElementById('alert-container');
    
    // Clear old alerts that are no longer active
    const activeZoneIds = new Set();
    Object.values(currentAlerts).forEach(zoneIds => {
        zoneIds.forEach(zid => activeZoneIds.add(zid));
    });
    
    // Remove alerts for zones that are no longer active
    Array.from(alertContainer.children).forEach(alertItem => {
        const zoneId = parseInt(alertItem.getAttribute('data-zone-id'));
        if (!activeZoneIds.has(zoneId)) {
            alertItem.remove();
        }
    });
    
    // Update existing alerts to show current state
    Object.keys(currentAlerts).forEach(tagName => {
        currentAlerts[tagName].forEach(zoneId => {
            const zone = zones.find(z => z.id === zoneId);
            if (zone) {
                const severity = zone.severity || 'WARNING';
                const severityClass = severity.toLowerCase();
                
                // Check if alert already exists
                const existingAlert = Array.from(alertContainer.children).find(item => {
                    return item.getAttribute('data-tag-name') === tagName && 
                           parseInt(item.getAttribute('data-zone-id')) === zoneId;
                });
                
                if (!existingAlert) {
                    // Create new alert
                    const alertItem = document.createElement('div');
                    alertItem.className = `alert-item ${severityClass}`;
                    alertItem.setAttribute('data-zone-id', zoneId);
                    alertItem.setAttribute('data-tag-name', tagName);
                    alertItem.innerHTML = `
                        <p>
                            <span class="alert-severity-badge ${severityClass}">${severity}</span>
                            ⚠️ ${tagName} entered ${zone.name}
                        </p>
                    `;
                    alertContainer.insertBefore(alertItem, alertContainer.firstChild);
                } else {
                    // Update existing alert if severity changed
                    existingAlert.className = `alert-item ${severityClass}`;
                    existingAlert.innerHTML = `
                        <p>
                            <span class="alert-severity-badge ${severityClass}">${severity}</span>
                            ⚠️ ${tagName} entered ${zone.name}
                        </p>
                    `;
                }
            }
        });
    });
    
    // Add new entry alerts with sound
    Object.keys(newEntries).forEach(tagName => {
        newEntries[tagName].forEach(zoneId => {
            const zone = zones.find(z => z.id === zoneId);
            if (zone) {
                const severity = zone.severity || 'WARNING';
                const severityClass = severity.toLowerCase();
                
                // Play alert sound (different frequency for ALERT vs WARNING)
                try {
                    const audioContext = new (window.AudioContext || window.webkitAudioContext)();
                    const oscillator = audioContext.createOscillator();
                    const gainNode = audioContext.createGain();
                    oscillator.connect(gainNode);
                    gainNode.connect(audioContext.destination);
                    
                    // Different frequencies for different severities
                    oscillator.frequency.value = severity === 'ALERT' ? 1000 : 800;
                    oscillator.type = 'sine';
                    gainNode.gain.setValueAtTime(severity === 'ALERT' ? 0.5 : 0.3, audioContext.currentTime);
                    gainNode.gain.exponentialRampToValueAtTime(0.01, audioContext.currentTime + (severity === 'ALERT' ? 0.8 : 0.5));
                    oscillator.start(audioContext.currentTime);
                    oscillator.stop(audioContext.currentTime + (severity === 'ALERT' ? 0.8 : 0.5));
                } catch (e) {
                    // Fallback: just log if audio context fails
                    console.log(`[${severity}] Alert: ${tagName} entered ${zone.name}`);
                }
            }
        });
    });
}

document.getElementById('save-anchors-btn').addEventListener('click', async () => {
    if (!ensureCanModify()) {
        return;
    }
    const updatedAnchors = Array.from(document.querySelectorAll('.anchor-input')).map(div => ({
        name: div.querySelector('label').htmlFor,
        x: document.getElementById(`${div.querySelector('label').htmlFor}-x`).value,
        y: document.getElementById(`${div.querySelector('label').htmlFor}-y`).value,
    }));
    try {
        const response = await fetch('/update_anchors', {
            method: 'POST', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(updatedAnchors)
        });
        const result = await response.json();
        setStatusMessage(result.message);
    } catch (error) {
        setStatusMessage('Error saving anchors.');
    }
});

document.getElementById('rename-tag-btn').addEventListener('click', async () => {
    const oldName = document.getElementById('tag-select-dropdown').value;
    const newName = document.getElementById('new-tag-name').value;

    if (!oldName || !newName) {
        setStatusMessage('Please provide both names.');
        return;
    }
    if (!ensureCanModify()) {
        return;
    }

    try {
        const response = await fetch('/rename_tag', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ old_name: oldName, new_name: newName })
        });
        const result = await response.json();
        
        setStatusMessage(result.message);
        // Clear inputs on success
        document.getElementById('new-tag-name').value = '';
    } catch (error) {
        setStatusMessage('Error renaming tag.');
        console.error('Error renaming tag:', error);
    }
});

function updateMapDimensions(data) {
    const newWidth = data.map_width_cm;
    const newHeight = data.map_height_cm;

    // Only update and resize if the dimensions have actually changed
    if (newWidth !== mapWidthCm || newHeight !== mapHeightCm) {
        mapWidthCm = newWidth;
        mapHeightCm = newHeight;
        resizeCanvas(); // Resize canvas only when dimensions change
    }
    const activeElementId = document.activeElement.id;
    if (activeElementId !== 'area-width' && activeElementId !== 'area-height') {
        document.getElementById('area-width').value = (mapWidthCm / 100).toFixed(1);
        document.getElementById('area-height').value = (mapHeightCm / 100).toFixed(1);
    }
}

function handleTrackingData(data) {
    if (!data) {
        return;
    }
    window.lastData = data; // Store for zone drawing preview and zone drawing overlay
    updateMapDimensions(data);
    // Always refresh sidebar so live range values and tag data update every tick
    updateSidebar(data);
    draw(data);
}

async function fetchSnapshot() {
    try {
        const response = await fetch('/data');
        const data = await response.json();
        handleTrackingData(data);
    } catch (error) {
        console.error("Failed to fetch data:", error);
    }
}

function startFallbackPolling() {
    if (pollingIntervalId) {
        return;
    }
    console.warn("Socket unavailable, reverting to polling.");
    fetchSnapshot();
    pollingIntervalId = setInterval(fetchSnapshot, FALLBACK_INTERVAL_MS);
}

function stopFallbackPolling() {
    if (!pollingIntervalId) {
        return;
    }
    clearInterval(pollingIntervalId);
    pollingIntervalId = null;
}

function initializeRealtimeUpdates() {
    if (typeof io === 'undefined') {
        console.warn('Socket.IO library not loaded, using polling fallback.');
        startFallbackPolling();
        return;
    }

    // Configure Socket.IO connection with polling-only transport (compatible with Flask dev server)
    socket = io({
        reconnection: true,
        reconnectionDelay: 1000,
        reconnectionDelayMax: 5000,
        reconnectionAttempts: Infinity,
        transports: ['polling'],
        upgrade: false
    });
    
    socket.on('connect', () => {
        console.info('✓ Connected to realtime tracking updates (polling).');
    });
    
    socket.on('tracking_update', handleTrackingData);
    
    socket.on('disconnect', () => {
        console.warn('✗ Realtime connection lost. Falling back to polling.');
        startFallbackPolling();
    });
    
    socket.on('connect_error', (error) => {
        console.warn('✗ Socket.IO connection error:', error);
        startFallbackPolling();
    });
    
    socket.on('error', (error) => {
        console.error('✗ Socket.IO error:', error);
    });
}

document.getElementById('save-area-btn').addEventListener('click', async () => {
    const widthM = parseFloat(document.getElementById('area-width').value);
    const heightM = parseFloat(document.getElementById('area-height').value);

    if (!ensureCanModify()) {
        return;
    }

    try {
        const response = await fetch('/update_area', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ width: widthM * 100, height: heightM * 100 }) // Convert to cm for backend
        });
        const result = await response.json();
        setStatusMessage(result.message);
    } catch (error) {
        setStatusMessage('Error saving area.');
    }
});

// Handle image selection
document.getElementById('select-image-btn').addEventListener('click', () => {
    document.getElementById('image-upload').click();
});

document.getElementById('image-upload').addEventListener('change', (event) => {
    const file = event.target.files[0];
    if (file) {
        const reader = new FileReader();
        reader.onload = (e) => {
            const imageUrl = e.target.result;
            mapContainer.style.backgroundImage = `url(${imageUrl})`;
        };
        reader.readAsDataURL(file);
    }
});

// Zone drawing functionality
document.getElementById('draw-zone-btn').addEventListener('click', () => {
    if (!ensureCanModify()) {
        return;
    }
    if (isResizingZone) {
        // Cancel resize mode
        isResizingZone = false;
        resizingZoneId = null;
        isDrawingZone = false;
    } else {
        isDrawingZone = !isDrawingZone;
    }
    const btn = document.getElementById('draw-zone-btn');
    const form = document.getElementById('draw-zone-form');
    if (isDrawingZone || isResizingZone) {
        btn.textContent = isResizingZone ? 'Cancel Resize' : 'Cancel Drawing';
        btn.classList.remove('btn-warning');
        btn.classList.add('btn-danger');
        canvas.style.cursor = 'crosshair';
        if (!isResizingZone) {
            form.classList.add('active');
        }
    } else {
        btn.textContent = 'Draw Zone';
        btn.classList.remove('btn-danger');
        btn.classList.add('btn-warning');
        canvas.style.cursor = 'default';
        form.classList.remove('active');
        currentZoneRect = null;
    }
});

canvas.addEventListener('mousedown', (e) => {
    if (!canModifySettings) return;
    if (!isDrawingZone && !isResizingZone) return;
    const rect = canvas.getBoundingClientRect();
    const relativeX = e.clientX - rect.left;
    const relativeY = e.clientY - rect.top;
    zoneStartX = canvasPxToCmX(relativeX, rect.width);
    zoneStartY = canvasPxToCmY(relativeY, rect.height);
    currentZoneRect = { x1: zoneStartX, y1: zoneStartY, x2: zoneStartX, y2: zoneStartY };
});

canvas.addEventListener('mousemove', (e) => {
    if (!canModifySettings) return;
    if ((!isDrawingZone && !isResizingZone) || !currentZoneRect) return;
    const rect = canvas.getBoundingClientRect();
    const relativeX = e.clientX - rect.left;
    const relativeY = e.clientY - rect.top;
    currentZoneRect.x2 = canvasPxToCmX(relativeX, rect.width);
    currentZoneRect.y2 = canvasPxToCmY(relativeY, rect.height);
    // Trigger a redraw to show the preview
    if (window.lastData) {
        draw(window.lastData);
    }
});

canvas.addEventListener('mouseup', async (e) => {
    if (!canModifySettings) return;
    if ((!isDrawingZone && !isResizingZone) || !currentZoneRect) return;
    const rect = canvas.getBoundingClientRect();
    const relativeX = e.clientX - rect.left;
    const relativeY = e.clientY - rect.top;
    const x2 = canvasPxToCmX(relativeX, rect.width);
    const y2 = canvasPxToCmY(relativeY, rect.height);
    
    // Only proceed if it has meaningful size
    if (Math.abs(x2 - zoneStartX) > 10 && Math.abs(y2 - zoneStartY) > 10) {
        if (isResizingZone && resizingZoneId) {
            // Update existing zone
            try {
                const response = await fetch('/update_zone', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        id: resizingZoneId,
                        x1: zoneStartX,
                        y1: zoneStartY,
                        x2: x2,
                        y2: y2
                    })
                });
                const result = await response.json();
                if (result.status === 'success') {
                    // Update the input fields in the edit form
                    document.getElementById(`edit-x1-${resizingZoneId}`).value = Math.min(zoneStartX, x2);
                    document.getElementById(`edit-y1-${resizingZoneId}`).value = Math.min(zoneStartY, y2);
                    document.getElementById(`edit-x2-${resizingZoneId}`).value = Math.max(zoneStartX, x2);
                    document.getElementById(`edit-y2-${resizingZoneId}`).value = Math.max(zoneStartY, y2);
                }
            } catch (error) {
                console.error('Error resizing zone:', error);
                alert('Error resizing zone. Please try again.');
            }
        } else if (isDrawingZone) {
            // Create new zone
            const zoneName = document.getElementById('zone-name-input').value || `Zone ${zoneCounter}`;
            const zoneSeverity = document.getElementById('zone-severity-input').value || 'WARNING';
            const zoneColor = document.getElementById('zone-color-input').value || '#ff0000';
            
            if (zoneName) {
                zoneCounter++;
                try {
                    const response = await fetch('/create_zone', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({
                            name: zoneName,
                            x1: zoneStartX,
                            y1: zoneStartY,
                            x2: x2,
                            y2: y2,
                            color: zoneColor,
                            severity: zoneSeverity
                        })
                    });
                    const result = await response.json();
                    if (result.status === 'success') {
                        // Reset form
                        document.getElementById('zone-name-input').value = '';
                        document.getElementById('zone-severity-input').value = 'WARNING';
                        document.getElementById('zone-color-input').value = '#ff0000';
                        // Zone will be updated on next data fetch
                    }
                } catch (error) {
                    console.error('Error creating zone:', error);
                }
            }
        }
    }
    
    currentZoneRect = null;
    isDrawingZone = false;
    isResizingZone = false;
    resizingZoneId = null;
    const btn = document.getElementById('draw-zone-btn');
    const form = document.getElementById('draw-zone-form');
    btn.textContent = 'Draw Zone';
    btn.classList.remove('btn-danger');
    btn.classList.add('btn-warning');
    form.classList.remove('active');
    canvas.style.cursor = 'default';
});

// Draw current zone being drawn
function drawCurrentZone() {
    if (currentZoneRect && (isDrawingZone || isResizingZone)) {
        const x1 = cmToCanvasX(currentZoneRect.x1);
        const y1 = cmToCanvasY(currentZoneRect.y1);
        const x2 = cmToCanvasX(currentZoneRect.x2);
        const y2 = cmToCanvasY(currentZoneRect.y2);
        const width = x2 - x1;
        const height = y2 - y1;
        
        ctx.strokeStyle = '#ff0000';
        ctx.lineWidth = 2;
        ctx.setLineDash([5, 5]);
        ctx.strokeRect(x1, y1, width, height);
        ctx.setLineDash([]);
    }
}

// Override draw to include current zone being drawn
const originalDraw = draw;
draw = function(data) {
    originalDraw(data);
    drawCurrentZone();
};

// Sidebar toggle functionality
const sidebar = document.getElementById('sidebar');
const sidebarToggle = document.getElementById('sidebar-toggle');
const mainContent = document.getElementById('main-content');
let sidebarOpen = true;

sidebarToggle.addEventListener('click', () => {
    sidebarOpen = !sidebarOpen;
    if (sidebarOpen) {
        sidebar.classList.remove('collapsed');
        mainContent.classList.remove('centered');
        sidebarToggle.textContent = '⚙️ Settings';
    } else {
        sidebar.classList.add('collapsed');
        mainContent.classList.add('centered');
        sidebarToggle.textContent = '⚙️';
    }
    // Resize canvas after sidebar animation completes (300ms matches CSS transition)
    setTimeout(resizeCanvas, 300);
});

// Accordion functionality
document.querySelectorAll('.accordion-header').forEach(header => {
    header.addEventListener('click', () => {
        const section = header.getAttribute('data-section');
        const content = document.getElementById(`accordion-${section}`);
        const isActive = header.classList.contains('active');
        
        // Toggle active state
        header.classList.toggle('active');
        content.classList.toggle('active');
    });
});

// Open Zones section by default (most commonly used)
document.querySelector('[data-section="zones"]').classList.add('active');
document.getElementById('accordion-zones').classList.add('active');

window.addEventListener('resize', resizeCanvas);
resizeCanvas();
async function refreshPermissions() {
    try {
        const response = await fetch('/permissions');
        if (!response.ok) {
            throw new Error('Failed to fetch permissions');
        }
        const result = await response.json();
        updateReadOnlyState(!!result.can_modify);
        if (!result.can_modify) {
            setStatusMessage('Read-only mode: this device cannot modify settings.', 5000);
        }
    } catch (error) {
        console.warn('Unable to determine permissions:', error);
    }
}

refreshPermissions().finally(() => {
    initializeRealtimeUpdates();
    // Start periodic polling immediately as a fallback for realtime updates
    startFallbackPolling();
    // Also fetch once right away to avoid initial delay
    fetchSnapshot();
});

