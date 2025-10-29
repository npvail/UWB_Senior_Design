# Import necessary libraries
import serial
import serial.tools.list_ports
import time
import math
import threading
from flask import Flask, render_template_string, jsonify, request

# ============================================================================
# === BACKEND LOGIC (Synced with your final Pygame script) ===================
# ============================================================================

# Define colors (used for data, not display)
RED = [255, 0, 0]
BLACK = [255, 255, 255] # Changed to white for better contrast if needed

# --- UWB class to represent anchors and tags (EXACT COPY) ---
class UWB:
    def __init__(self, name, type):
        self.name = name
        self.type = type
        self.x = 0
        self.y = 0
        self.status = False
        self.list = []
        self.position_history = []
        self.smoothing_window = 10

        if self.type == 1:
            self.color = RED
        else:
            self.color = BLACK

    def set_location(self, x, y):
        self.x = x
        self.y = y
        self.status = True

    def cal(self):
        count = 0
        anc_id_list = []
        for range_val in self.list:
            if range_val != 0:
                anc_id_list.append(count)
            count += 1
        
        if len(anc_id_list) >= 3:
            x, y = 0.0, 0.0
            temp_x, temp_y = self.three_point_uwb(anc_id_list[0], anc_id_list[1])
            x += temp_x; y += temp_y
            temp_x, temp_y = self.three_point_uwb(anc_id_list[0], anc_id_list[2])
            x += temp_x; y += temp_y
            temp_x, temp_y = self.three_point_uwb(anc_id_list[2], anc_id_list[1])
            x += temp_x; y += temp_y
            x = int(x / 3)
            y = int(y / 3)

            self.position_history.append((x, y))
            if len(self.position_history) > self.smoothing_window:
                self.position_history.pop(0)
            
            sum_x = sum(pos[0] for pos in self.position_history)
            sum_y = sum(pos[1] for pos in self.position_history)
            
            smoothed_x = int(sum_x / len(self.position_history))
            smoothed_y = int(sum_y / len(self.position_history))

            self.set_location(smoothed_x, smoothed_y)
            self.status = True

    def three_point_uwb(self, a_id, b_id):
        return self.three_point(anc[a_id].x, anc[a_id].y, anc[b_id].x, anc[b_id].y, self.list[a_id], self.list[b_id])

    def three_point(self, x1, y1, x2, y2, r1, r2):
        temp_x, temp_y = 0.0, 0.0
        p2p = math.sqrt((x1 - x2)**2 + (y1 - y2)**2)
        if p2p == 0: return (x1, y1) # Avoid division by zero
        if r1 + r2 <= p2p:
            temp_x = x1 + (x2 - x1) * r1 / (r1 + r2)
            temp_y = y1 + (y2 - y1) * r1 / (r1 + r2)
        else:
            dr = p2p / 2 + (r1**2 - r2**2) / (2 * p2p)
            temp_x = x1 + (x2 - x1) * dr / p2p
            temp_y = y1 + (y2 - y1) * dr / p2p
        return temp_x, temp_y

# --- Serial Port Function (EXACT COPY) ---
def get_frist_com():
    port_list = serial.tools.list_ports.comports()
    for port in port_list:
        if "usbserial" in port.device or "usbmodem" in port.device or "CH340" in port.description or "wchusbserial" in port.device or "1A86:7523" in port.hwid:
            print(f"Found compatible port: {port.device}")
            return port.device
    print("WARNING: No compatible serial port found.")
    return None

# --- Data Reading Function (EXACT COPY) ---
def read_data():
    line = ser.readline().decode('UTF-8', errors='ignore').strip()
    if not line:
        return
    try:
        if line.startswith("AT+RANGE="):
            start_index = line.find("range:(")
            if start_index == -1: return
            end_index = line.find(")", start_index)
            if end_index == -1: return
            ranges_str = line[start_index + len("range:("):end_index]
            range_values = [int(r) for r in ranges_str.split(',')]
            tid = 0
            tag[tid].list = range_values
            valid_ranges = [r for r in range_values if r > 0]
            if len(valid_ranges) >= 3:
                tag[tid].cal()
        elif "nge:" in line:
            ranges = line.split("nge:(")[1].split(")")[0]
            range_values = [int(r) if r != "0" else 0 for r in ranges.split(",")]
            tid = 0
            tag[tid].list = range_values
            valid_ranges = [r for r in range_values if r > 0]
            if len(valid_ranges) >= 3:
                tag[tid].cal()
    except Exception as e:
        print(f"[ERROR] Failed to process line: '{line}', Error: {e}")

# --- Background Thread Wrapper for read_data ---
def serial_loop():
    """ This function runs in a background thread to call read_data continuously. """
    while True:
        read_data()
        time.sleep(0.01) # Small delay to be friendly to the CPU

# --- Global Variables for UWB Objects ---
anc = []
tag = []
anc_count = 3
tag_count = 1

# Anchor positions (SYNCED WITH YOUR FINAL BACKEND)
A0X, A0Y = 0, 0
A1X, A1Y = 200, 0
A2X, A2Y = 330, 330

for i in range(anc_count):
    name = "ANC " + str(i)
    anc.append(UWB(name, 0))
for i in range(tag_count):
    name = "TAG " + str(i)
    tag.append(UWB(name, 1))

anc[0].set_location(A0X, A0Y)
anc[1].set_location(A1X, A1Y)
anc[2].set_location(A2X, A2Y)

# --- Serial Port Initialization ---
ser = serial.Serial(get_frist_com(), 115200)
ser.write("begin".encode('UTF-8'))
ser.reset_input_buffer()
MAP_WIDTH_CM = 1000
MAP_HEIGHT_CM = 800
# ============================================================================
# === FLASK WEB SERVER (The UI Part) =========================================
# ============================================================================

app = Flask(__name__)

# --- Function to change anchor positions ---
@app.route('/update_anchors', methods=['POST'])
def update_anchor_positions():
    data = request.get_json()
    with threading.Lock():
        for anchor_data in data:
            name, new_x, new_y = anchor_data.get('name'), float(anchor_data.get('x')), float(anchor_data.get('y'))
            for anchor_obj in anc:
                if anchor_obj.name == name:
                    anchor_obj.set_location(new_x, new_y)
                    break
    return jsonify({"status": "success", "message": "Anchors updated"})

@app.route('/rename_tag', methods=['POST'])
def rename_tag():
    """
    Receives an old and new tag name and updates the corresponding tag object.
    """
    data = request.get_json()
    old_name = data.get('old_name')
    new_name = data.get('new_name')

    if not old_name or not new_name:
        return jsonify({"status": "error", "message": "Missing name fields"}), 400

    tag_found = False
    with threading.Lock():
        for tag_obj in tag: # The global 'tag' list
            if tag_obj.name == old_name:
                tag_obj.name = new_name
                tag_found = True
                break
    
    if tag_found:
        return jsonify({"status": "success", "message": f"Tag renamed to {new_name}"})
    else:
        return jsonify({"status": "error", "message": f"Tag '{old_name}' not found"}), 404

@app.route('/update_area', methods=['POST'])
def update_area():
    global MAP_WIDTH_CM, MAP_HEIGHT_CM
    data = request.get_json()
    new_width = data.get('width')
    new_height = data.get('height')

    if not new_width or not new_height:
        return jsonify({"status": "error", "message": "Missing dimensions"}), 400
    
    with threading.Lock():
        MAP_WIDTH_CM = int(new_width)
        MAP_HEIGHT_CM = int(new_height)
    
    return jsonify({"status": "success", "message": "Area dimensions updated"})

# --- Main Flask Routes ---
@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route('/data')
def get_data():
    # Create dictionaries on the fly to keep UWB class clean
    anchor_data = [{"name": a.name, "x": a.x, "y": a.y, "status": a.status} for a in anc]
    tag_data = [{"name": t.name, "x": t.x, "y": t.y, "status": t.status, "ranges": t.list} for t in tag]
    return jsonify({"anchors": anchor_data, "tags": tag_data, "map_width_cm": MAP_WIDTH_CM, "map_height_cm": MAP_HEIGHT_CM})

# --- HTML, CSS, and JavaScript for the UI ---
HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>UWB Object Tracking UI</title>
    <style>
        .wrapper {
            display: flex;
            max-width: 1400px; /* Set a max width for the whole UI */
            width: 100%;
            margin: 0 auto; /* Center the layout on the page */
            gap: 20px;
        }
        body { font-family: system-ui, sans-serif; display: flex; padding: 20px; gap: 20px; background-color: #f0f2f5; margin: 20px; }
        .main-content { flex-grow: 1; }
        .sidebar { width: 350px; flex-shrink: 0; background-color: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,0.1); }
        h1, h2, h3 { color: #333; border-bottom: 1px solid #ddd; padding-bottom: 10px; margin-top: 20px; margin-bottom: 15px; }
        h1:first-child, h2:first-child, h3:first-child { margin-top: 0; }
        
        #map-container { position: relative; border: 2px solid #ccc; background-image: url('/static/factory_map.png'); background-size: cover; background-repeat: no-repeat; background-position: center; box-shadow: 0 4px 12px rgba(0,0,0,0.15); }
        #map-canvas { position: absolute; top: 0; left: 0; width: 100%; height: 100%; }

        .anchor-controls .anchor-input { display: flex; gap: 10px; align-items: center; margin-bottom: 10px; }
        .anchor-controls label { font-weight: bold; width: 60px; }
        .anchor-controls input { width: 80px; padding: 5px; border: 1px solid #ccc; border-radius: 4px; }
        .sidebar button {
            color: white;
            border: none;
            padding: 10px 15px;
            border-radius: 5px;
            cursor: pointer;
            margin-top: 10px;
            transition: background-color 0.2s;
            width: 100%; /* Make all buttons the same width */
            font-size: 0.9em;
            text-align: center;
        }
        .btn-primary {
            background-color: #007bff;
        }
        .btn-primary:hover {
            background-color: #0056b3;
        }
        .btn-secondary {
            background-color: #6c757d;
        }
        .btn-secondary:hover {
            background-color: #5a6268;
        }
        #status-message { margin-top: 10px; font-style: italic; color: green; height: 1em; }
        
        .info-section p { margin: 5px 0; }
        .tag-info-box { border: 1px solid #eee; padding: 10px; margin-bottom: 10px; border-radius: 5px; }
        .tag-info-box p { font-size: 1.1em; font-weight: bold; }
        .tag-info-box ul { list-style: none; padding-left: 15px; margin: 5px 0 0 0; font-family: monospace; font-size: 0.9em; }
    </style>
</head>
<body>
    <div class="wrapper">
        <div class="main-content">
            <h1>Find My Tools</h1>
            <div id="map-container"><canvas id="map-canvas"></canvas></div>
        </div>
        <div class="sidebar">
            <h2>Settings</h2>
            <div class="info-section">
                <h3>Tracking Area</h3>
                <div class="control-input">
                    <label for="area-width">Width (m):</label>
                    <input type="number" id="area-width" step="0.1">
                </div>
                <div class="control-input">
                    <label for="area-height">Height (m):</label>
                    <input type="number" id="area-height" step="0.1">
                </div>
                <button id="save-area-btn" class="btn-secondary">Save Area</button>
            </div>
            <div id="anchor-controls" class="anchor-controls">
                <h3>Anchor Positions (cm)</h3>
            </div>
            <button id="save-anchors-btn" class="btn-primary">Save Anchor Positions</button>
            <div id="status-message"></div>
            <div class="tag-rename-controls">
                <h3>Rename Tag</h3>
                <div class="control-input">
                    <label for="tag-select-dropdown">Select Tag:</label>
                    <select id="tag-select-dropdown"></select>
                </div>
                <div class="control-input">
                    <label for="new-tag-name">New Name:</label>
                    <input type="text" id="new-tag-name" placeholder="e.g., Forklift 1">
                </div>
                <button id="rename-tag-btn" class="btn-secondary">Rename Tag</button>
            </div>
            <h2>Live Data</h2>
            <div id="tag-positions"></div>
        </div>
    </div>
    <script>
        let mapWidthCm = 1000;;
        let mapHeightCm = 800;
        const canvas = document.getElementById('map-canvas');
        const ctx = canvas.getContext('2d');
        const mapContainer = document.getElementById('map-container');

        function resizeCanvas() {
            const containerWidth = mapContainer.parentElement.clientWidth;
            const aspectRatio = mapWidthCm / mapHeightCm;
            mapContainer.style.width = containerWidth + 'px';
            mapContainer.style.height = (containerWidth / aspectRatio) + 'px';
            canvas.width = containerWidth;
            canvas.height = containerWidth / aspectRatio;
        }

        function draw(data) {
            ctx.clearRect(0, 0, canvas.width, canvas.height);
            const pixelsPerCm = canvas.width / mapWidthCm;
            data.anchors.forEach(anchor => {
                if (anchor.status) {
                    const x = anchor.x * pixelsPerCm; const y = anchor.y * pixelsPerCm;
                    ctx.fillStyle = 'rgba(0, 123, 255, 0.8)';
                    ctx.beginPath(); ctx.arc(x, y, 8, 0, 2 * Math.PI); ctx.fill();
                    ctx.fillStyle = '#000'; ctx.font = '12px Arial';
                    ctx.fillText(`${anchor.name} (${anchor.x}, ${anchor.y})`, x + 12, y + 4);
                }
            });
            data.tags.forEach(tag => {
                if (tag.status) {
                    const x = tag.x * pixelsPerCm; const y = tag.y * pixelsPerCm;
                    ctx.fillStyle = 'rgba(255, 0, 0, 0.9)';
                    ctx.beginPath(); ctx.arc(x, y, 10, 0, 2 * Math.PI); ctx.fill();
                    ctx.strokeStyle = 'rgba(255, 255, 255, 0.8)';
                    ctx.lineWidth = 2; ctx.stroke();
                    ctx.fillStyle = '#000'; ctx.font = 'bold 14px Arial';
                    ctx.fillText(tag.name, x + 15, y + 5);
                }
            });
        }

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
        
        document.getElementById('save-anchors-btn').addEventListener('click', async () => {
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
                const statusMsg = document.getElementById('status-message');
                statusMsg.textContent = result.message;
                setTimeout(() => statusMsg.textContent = '', 3000);
            } catch (error) {
                document.getElementById('status-message').textContent = 'Error saving.';
            }
        });

        document.getElementById('rename-tag-btn').addEventListener('click', async () => {
            const oldName = document.getElementById('tag-select-dropdown').value;
            const newName = document.getElementById('new-tag-name').value;
            const statusMsg = document.getElementById('status-message');

            if (!oldName || !newName) {
                statusMsg.textContent = 'Please provide both names.';
                return;
            }

            try {
                const response = await fetch('/rename_tag', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ old_name: oldName, new_name: newName })
                });
                const result = await response.json();
                
                statusMsg.textContent = result.message;
                // Clear inputs on success
                document.getElementById('new-tag-name').value = '';
                setTimeout(() => statusMsg.textContent = '', 3000);
            } catch (error) {
                statusMsg.textContent = 'Error renaming tag.';
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
        async function mainLoop() {
            try {
                const response = await fetch('/data');
                const data = await response.json();
                updateMapDimensions(data);
                // The rest of the function remains the same
                updateSidebar(data);
                draw(data);
            } catch (error) { console.error("Failed to fetch data:", error); }
        }

        document.getElementById('save-area-btn').addEventListener('click', async () => {
            const widthM = parseFloat(document.getElementById('area-width').value);
            const heightM = parseFloat(document.getElementById('area-height').value);
            const statusMsg = document.getElementById('status-message');

            try {
                const response = await fetch('/update_area', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ width: widthM * 100, height: heightM * 100 }) // Convert to cm for backend
                });
                const result = await response.json();
                statusMsg.textContent = result.message;
                // The mainLoop will automatically handle the visual update
                setTimeout(() => statusMsg.textContent = '', 3000);
            } catch (error) {
                statusMsg.textContent = 'Error saving area.';
            }
        });
        
        window.addEventListener('resize', resizeCanvas);
        resizeCanvas();
        setInterval(mainLoop, 500);
        mainLoop();
    </script>
</body>
</html>
"""

if __name__ == '__main__':
    # Start the background thread for reading UWB data
    serial_thread = threading.Thread(target=serial_loop, daemon=True)
    serial_thread.start()
    app.run(host='0.0.0.0', port=2405)
