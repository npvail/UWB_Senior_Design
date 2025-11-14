# Import necessary libraries
import serial
import serial.tools.list_ports
import time
import math
import threading
from flask import Flask, render_template_string, jsonify, request

# ============================================================================
# === BACKEND LOGIC (Synced with Pygame script) ===================
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

# --- Zone Management ---
zones = []  # List of zones: {id, name, x1, y1, x2, y2, color, severity}
zone_id_counter = 0
zone_lock = threading.Lock()
tag_zone_alerts = {}  # Track which tags are in which zones: {tag_name: [zone_ids]}

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

@app.route('/create_zone', methods=['POST'])
def create_zone():
    """Create a new zone with rectangular coordinates"""
    global zone_id_counter
    data = request.get_json()
    name = data.get('name', f'Zone {zone_id_counter + 1}')
    x1 = float(data.get('x1', 0))
    y1 = float(data.get('y1', 0))
    x2 = float(data.get('x2', 0))
    y2 = float(data.get('y2', 0))
    color = data.get('color', '#ff0000')
    severity = data.get('severity', 'WARNING')  # Default to WARNING
    
    # Validate severity
    if severity not in ['WARNING', 'ALERT']:
        severity = 'WARNING'
    
    with zone_lock:
        zone_id_counter += 1
        zone = {
            'id': zone_id_counter,
            'name': name,
            'x1': min(x1, x2),
            'y1': min(y1, y2),
            'x2': max(x1, x2),
            'y2': max(y1, y2),
            'color': color,
            'severity': severity
        }
        zones.append(zone)
    
    return jsonify({"status": "success", "message": "Zone created", "zone": zone})

@app.route('/update_zone', methods=['POST'])
def update_zone():
    """Update zone properties (name, color, severity, and/or coordinates)"""
    data = request.get_json()
    zone_id = data.get('id')
    name = data.get('name')
    color = data.get('color')
    severity = data.get('severity')
    x1 = data.get('x1')
    y1 = data.get('y1')
    x2 = data.get('x2')
    y2 = data.get('y2')
    
    if zone_id is None:
        return jsonify({"status": "error", "message": "Missing zone ID"}), 400
    
    # Validate severity if provided
    if severity and severity not in ['WARNING', 'ALERT']:
        return jsonify({"status": "error", "message": "Invalid severity. Must be WARNING or ALERT"}), 400
    
    # Validate name if provided
    if name is not None and (not name or len(name.strip()) == 0):
        return jsonify({"status": "error", "message": "Zone name cannot be empty"}), 400
    
    # Validate coordinates if provided
    coords_provided = x1 is not None and y1 is not None and x2 is not None and y2 is not None
    if coords_provided:
        try:
            x1 = float(x1)
            y1 = float(y1)
            x2 = float(x2)
            y2 = float(y2)
        except (ValueError, TypeError):
            return jsonify({"status": "error", "message": "Invalid coordinate values"}), 400
    
    with zone_lock:
        zone_found = False
        for zone in zones:
            if zone['id'] == zone_id:
                if name is not None:
                    zone['name'] = name.strip()
                if color is not None:
                    zone['color'] = color
                if severity is not None:
                    zone['severity'] = severity
                if coords_provided:
                    zone['x1'] = min(x1, x2)
                    zone['y1'] = min(y1, y2)
                    zone['x2'] = max(x1, x2)
                    zone['y2'] = max(y1, y2)
                zone_found = True
                break
        
        if not zone_found:
            return jsonify({"status": "error", "message": "Zone not found"}), 404
    
    return jsonify({"status": "success", "message": "Zone updated"})

@app.route('/delete_zone', methods=['POST'])
def delete_zone():
    """Delete a zone by ID"""
    data = request.get_json()
    zone_id = data.get('id')
    
    if zone_id is None:
        return jsonify({"status": "error", "message": "Missing zone ID"}), 400
    
    with zone_lock:
        global zones
        zones = [z for z in zones if z['id'] != zone_id]
        # Clean up alerts for this zone
        for tag_name in list(tag_zone_alerts.keys()):
            if zone_id in tag_zone_alerts[tag_name]:
                tag_zone_alerts[tag_name].remove(zone_id)
                if not tag_zone_alerts[tag_name]:
                    del tag_zone_alerts[tag_name]
    
    return jsonify({"status": "success", "message": "Zone deleted"})

@app.route('/get_zones', methods=['GET'])
def get_zones():
    """Get all zones"""
    with zone_lock:
        return jsonify({"status": "success", "zones": zones})

def is_point_in_zone(x, y, zone):
    """Check if a point (x, y) is inside a rectangular zone"""
    return zone['x1'] <= x <= zone['x2'] and zone['y1'] <= y <= zone['y2']

def check_zone_alerts():
    """Check all tags against all zones and update alerts"""
    global tag_zone_alerts
    current_alerts = {}
    
    with zone_lock:
        for tag_obj in tag:
            if not tag_obj.status:
                continue
            tag_in_zones = []
            for zone in zones:
                if is_point_in_zone(tag_obj.x, tag_obj.y, zone):
                    tag_in_zones.append(zone['id'])
            if tag_in_zones:
                current_alerts[tag_obj.name] = tag_in_zones
        
        # Detect new entries (tags entering zones)
        new_entries = {}
        for tag_name, zone_ids in current_alerts.items():
            if tag_name not in tag_zone_alerts:
                # Tag just entered zones
                new_entries[tag_name] = zone_ids
            else:
                # Check for new zone entries
                new_zones = [zid for zid in zone_ids if zid not in tag_zone_alerts[tag_name]]
                if new_zones:
                    new_entries[tag_name] = new_zones
        
        tag_zone_alerts = current_alerts.copy()
        return new_entries

# --- Main Flask Routes ---
@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route('/data')
def get_data():
    # Check for zone alerts
    new_entries = check_zone_alerts()
    
    # Create dictionaries on the fly to keep UWB class clean
    anchor_data = [{"name": a.name, "x": a.x, "y": a.y, "status": a.status} for a in anc]
    tag_data = [{"name": t.name, "x": t.x, "y": t.y, "status": t.status, "ranges": t.list} for t in tag]
    
    # Get current zone data
    with zone_lock:
        zone_data = zones.copy()
    
    # Get current alerts
    with zone_lock:
        current_alerts = {tag_name: zone_ids.copy() for tag_name, zone_ids in tag_zone_alerts.items()}
    
    return jsonify({
        "anchors": anchor_data,
        "tags": tag_data,
        "zones": zone_data,
        "alerts": current_alerts,
        "new_entries": new_entries,
        "map_width_cm": MAP_WIDTH_CM,
        "map_height_cm": MAP_HEIGHT_CM
    })

# --- HTML, CSS, and JavaScript for the UI ---
HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>UWB Object Tracking UI</title>
    <style>
        body { 
            font-family: system-ui, sans-serif; 
            margin: 0; 
            padding: 0; 
            background-color: #f0f2f5; 
            overflow-x: hidden;
        }
        .wrapper {
            display: flex;
            height: 100vh;
            gap: 0;
            position: relative;
            width: 100%;
        }
        .main-content { 
            flex: 1;
            display: flex;
            flex-direction: column;
            padding: 20px;
            transition: all 0.3s ease;
            align-items: flex-start; /* Left align when sidebar is visible */
            min-width: 0; /* Allow flex item to shrink */
        }
        .main-content.centered {
            align-items: center; /* Center when sidebar is hidden */
            justify-content: flex-start;
        }
        .main-content.centered h1 {
            text-align: center;
            width: 100%;
            margin-bottom: 20px;
            transition: text-align 0.3s ease;
        }
        .main-content h1 {
            transition: text-align 0.3s ease;
        }
        /* Map container positioning - use margin for smooth animation */
        #map-container {
            transition: margin-left 0.3s ease, margin-right 0.3s ease, max-width 0.3s ease;
            margin-left: 0; /* Left aligned by default */
            margin-right: 0;
        }
        .main-content.centered #map-container {
            margin-left: auto;
            margin-right: auto; /* Center the map container */
            max-width: calc(100vw - 40px); /* Account for padding */
        }
        .sidebar-toggle {
            position: fixed;
            top: 20px;
            right: 20px;
            z-index: 1000;
            background-color: #007bff;
            color: white;
            border: none;
            padding: 12px 16px;
            border-radius: 8px;
            cursor: pointer;
            box-shadow: 0 2px 8px rgba(0,0,0,0.2);
            font-size: 14px;
            font-weight: bold;
            transition: background-color 0.2s;
        }
        .sidebar-toggle:hover {
            background-color: #0056b3;
        }
        .sidebar {
            width: 380px;
            flex-shrink: 0;
            background-color: white;
            box-shadow: -2px 0 8px rgba(0,0,0,0.1);
            overflow-y: auto;
            overflow-x: hidden;
            transition: all 0.3s ease;
            display: flex;
            flex-direction: column;
            height: 100vh;
            position: relative;
        }
        .sidebar.collapsed {
            transform: translateX(100%);
            width: 0;
            min-width: 0;
            overflow: hidden;
        }
        .sidebar-content {
            padding: 20px;
        }
        h1 { 
            color: #333; 
            margin: 0 0 20px 0;
            font-size: 24px;
        }
        h2 { 
            color: #333; 
            margin: 0 0 15px 0;
            font-size: 18px;
            font-weight: 600;
        }
        h3 { 
            color: #333; 
            margin: 0 0 10px 0;
            font-size: 14px;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }
        
        /* Accordion/Collapsible Sections */
        .accordion-section {
            margin-bottom: 15px;
            border: 1px solid #e0e0e0;
            border-radius: 6px;
            overflow: hidden;
            background-color: #fafafa;
        }
        .accordion-header {
            padding: 12px 15px;
            background-color: #f5f5f5;
            cursor: pointer;
            display: flex;
            justify-content: space-between;
            align-items: center;
            user-select: none;
            transition: background-color 0.2s;
            border-bottom: 1px solid #e0e0e0;
        }
        .accordion-header:hover {
            background-color: #eeeeee;
        }
        .accordion-header.active {
            background-color: #e3f2fd;
            border-bottom: 2px solid #2196f3;
        }
        .accordion-icon {
            transition: transform 0.3s ease;
            font-size: 12px;
            color: #666;
        }
        .accordion-header.active .accordion-icon {
            transform: rotate(90deg);
        }
        .accordion-content {
            max-height: 0;
            overflow: hidden;
            transition: max-height 0.3s ease;
            background-color: white;
        }
        .accordion-content.active {
            max-height: 2000px;
            padding: 15px;
        }
        
        /* Priority sections - always visible */
        .priority-section {
            background-color: white;
            padding: 15px;
            margin-bottom: 15px;
            border-radius: 6px;
            box-shadow: 0 1px 3px rgba(0,0,0,0.1);
        }
        
        #map-container { 
            position: relative; 
            border: 2px solid #ccc; 
            background-size: cover; 
            background-repeat: no-repeat; 
            background-position: center; 
            box-shadow: 0 4px 12px rgba(0,0,0,0.15); 
            background-color: #f5f5f5;
            flex-grow: 1;
            min-height: 400px;
            border-radius: 8px;
        }
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
        
        .zone-controls { margin-bottom: 15px; }
        .zone-controls input { width: 100%; padding: 5px; margin-bottom: 5px; border: 1px solid #ccc; border-radius: 4px; }
        .zone-controls select { width: 100%; padding: 5px; margin-bottom: 5px; border: 1px solid #ccc; border-radius: 4px; }
        .zone-list { max-height: 300px; overflow-y: auto; margin-top: 10px; }
        .zone-item { padding: 10px; margin-bottom: 8px; background-color: #f8f9fa; border-radius: 4px; border: 1px solid #dee2e6; }
        .zone-item-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; }
        .zone-item-name { flex-grow: 1; font-weight: bold; }
        .zone-item-severity { display: inline-block; padding: 2px 8px; border-radius: 3px; font-size: 0.75em; font-weight: bold; margin-left: 8px; }
        .severity-warning { background-color: #ffc107; color: #000; }
        .severity-alert { background-color: #dc3545; color: #fff; }
        .zone-item-controls { display: flex; gap: 5px; align-items: center; }
        .zone-item-delete { background-color: #dc3545; color: white; border: none; padding: 4px 8px; border-radius: 3px; cursor: pointer; font-size: 0.8em; }
        .zone-item-delete:hover { background-color: #c82333; }
        .zone-item-edit { background-color: #6c757d; color: white; border: none; padding: 4px 8px; border-radius: 3px; cursor: pointer; font-size: 0.8em; }
        .zone-item-edit:hover { background-color: #5a6268; }
        .zone-edit-form { display: none; margin-top: 8px; padding-top: 8px; border-top: 1px solid #dee2e6; }
        .zone-edit-form.active { display: block; }
        .zone-edit-form input[type="text"] { width: 100%; padding: 5px; border: 1px solid #ccc; border-radius: 4px; margin-bottom: 8px; box-sizing: border-box; }
        .zone-edit-form input[type="color"] { width: 60px; height: 30px; border: 1px solid #ccc; border-radius: 4px; cursor: pointer; margin-bottom: 8px; }
        .zone-edit-form label { display: block; margin-top: 5px; margin-bottom: 3px; font-size: 0.9em; font-weight: bold; }
        .zone-edit-form select { width: 100%; padding: 5px; border: 1px solid #ccc; border-radius: 4px; margin-bottom: 8px; box-sizing: border-box; }
        .zone-edit-form button { margin-top: 8px; padding: 5px 10px; background-color: #007bff; color: white; border: none; border-radius: 3px; cursor: pointer; font-size: 0.85em; }
        .zone-edit-form button:hover { background-color: #0056b3; }
        
        .alert-container { margin-top: 10px; max-height: 200px; overflow-y: auto; min-height: 50px; }
        .alert-item { padding: 10px; margin-bottom: 8px; border-radius: 4px; animation: slideIn 0.3s ease-out; }
        .alert-item.warning { background-color: #fff3cd; border-left: 4px solid #ffc107; }
        .alert-item.alert { background-color: #f8d7da; border-left: 4px solid #dc3545; }
        .alert-item p { margin: 0; font-weight: bold; }
        .alert-item.warning p { color: #856404; }
        .alert-item.alert p { color: #721c24; }
        .alert-severity-badge { display: inline-block; padding: 2px 6px; border-radius: 3px; font-size: 0.75em; font-weight: bold; margin-right: 6px; }
        .alert-severity-badge.warning { background-color: #ffc107; color: #000; }
        .alert-severity-badge.alert { background-color: #dc3545; color: #fff; }
        @keyframes slideIn { from { opacity: 0; transform: translateX(-10px); } to { opacity: 1; transform: translateX(0); } }
        .btn-danger { background-color: #dc3545; }
        .btn-danger:hover { background-color: #c82333; }
        .btn-warning { background-color: #ffc107; color: #000; }
        .btn-warning:hover { background-color: #e0a800; }
        .draw-zone-form { margin-top: 10px; padding: 10px; background-color: #f8f9fa; border-radius: 4px; border: 1px solid #dee2e6; display: none; }
        .draw-zone-form.active { display: block; }
        .draw-zone-form label { display: block; margin-top: 5px; margin-bottom: 3px; font-size: 0.9em; font-weight: bold; }
        .draw-zone-form input, .draw-zone-form select { width: 100%; padding: 5px; border: 1px solid #ccc; border-radius: 4px; margin-bottom: 8px; }
        .draw-zone-form input[type="color"] { width: 60px; height: 30px; cursor: pointer; }
    </style>
</head>
<body>
    <button class="sidebar-toggle" id="sidebar-toggle">⚙️ Settings</button>
    <div class="wrapper">
        <div class="main-content" id="main-content">
            <h1>Find My Tools</h1>
            <div id="map-container"><canvas id="map-canvas"></canvas></div>
        </div>
        <div class="sidebar" id="sidebar">
            <div class="sidebar-content">
                <!-- Priority Sections - Always Visible -->
                <div class="priority-section">
                    <h2>🚨 Alerts</h2>
                    <div id="alert-container" class="alert-container"></div>
                </div>
                
                <div class="priority-section">
                    <h2>📊 Live Data</h2>
                    <div id="tag-positions"></div>
                </div>
                
                <!-- Collapsible Settings Sections -->
                <div class="accordion-section">
                    <div class="accordion-header" data-section="zones">
                        <span><strong>📍 Zones</strong></span>
                        <span class="accordion-icon">▶</span>
                    </div>
                    <div class="accordion-content" id="accordion-zones">
                        <div class="zone-controls">
                            <button id="draw-zone-btn" class="btn-warning">Draw Zone</button>
                            <div id="draw-zone-form" class="draw-zone-form">
                                <label for="zone-name-input">Zone Name:</label>
                                <input type="text" id="zone-name-input" placeholder="Enter zone name">
                                <label for="zone-severity-input">Severity:</label>
                                <select id="zone-severity-input">
                                    <option value="WARNING">WARNING</option>
                                    <option value="ALERT">ALERT</option>
                                </select>
                                <label for="zone-color-input">Color:</label>
                                <input type="color" id="zone-color-input" value="#ff0000">
                            </div>
                            <div id="zone-list" class="zone-list"></div>
                        </div>
                    </div>
                </div>
                
                <div class="accordion-section">
                    <div class="accordion-header" data-section="map-settings">
                        <span><strong>🗺️ Map Settings</strong></span>
                        <span class="accordion-icon">▶</span>
                    </div>
                    <div class="accordion-content" id="accordion-map-settings">
                        <div class="info-section">
                            <h3>Map Background</h3>
                            <input type="file" id="image-upload" accept="image/*" style="display: none;">
                            <button id="select-image-btn" class="btn-secondary">Select Background Image</button>
                        </div>
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
                    </div>
                </div>
                
                <div class="accordion-section">
                    <div class="accordion-header" data-section="anchors">
                        <span><strong>📡 Anchor Configuration</strong></span>
                        <span class="accordion-icon">▶</span>
                    </div>
                    <div class="accordion-content" id="accordion-anchors">
                        <div id="anchor-controls" class="anchor-controls">
                            <h3>Anchor Positions (cm)</h3>
                        </div>
                        <button id="save-anchors-btn" class="btn-primary">Save Anchor Positions</button>
                        <div id="status-message"></div>
                    </div>
                </div>
                
                <div class="accordion-section">
                    <div class="accordion-header" data-section="tags">
                        <span><strong>🏷️ Tag Management</strong></span>
                        <span class="accordion-icon">▶</span>
                    </div>
                    <div class="accordion-content" id="accordion-tags">
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
                    </div>
                </div>
            </div>
        </div>
    </div>
    <script>
        let mapWidthCm = 1000;;
        let mapHeightCm = 800;
        const canvas = document.getElementById('map-canvas');
        const ctx = canvas.getContext('2d');
        const mapContainer = document.getElementById('map-container');

        function resizeCanvas() {
            const mainContent = document.getElementById('main-content');
            const containerWidth = mainContent.clientWidth - 40; // Account for padding
            const aspectRatio = mapWidthCm / mapHeightCm;
            const containerHeight = mainContent.clientHeight - 100; // Account for header and padding
            
            // Use the smaller dimension to maintain aspect ratio
            let finalWidth = containerWidth;
            let finalHeight = containerWidth / aspectRatio;
            
            if (finalHeight > containerHeight) {
                finalHeight = containerHeight;
                finalWidth = containerHeight * aspectRatio;
            }
            
            mapContainer.style.width = finalWidth + 'px';
            mapContainer.style.height = finalHeight + 'px';
            canvas.width = finalWidth;
            canvas.height = finalHeight;
        }

        function draw(data) {
            ctx.clearRect(0, 0, canvas.width, canvas.height);
            const pixelsPerCm = canvas.width / mapWidthCm;
            
            // Draw zones first (behind other elements)
            if (data.zones) {
                data.zones.forEach(zone => {
                    const x1 = zone.x1 * pixelsPerCm;
                    const y1 = zone.y1 * pixelsPerCm;
                    const x2 = zone.x2 * pixelsPerCm;
                    const y2 = zone.y2 * pixelsPerCm;
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
                    const x = anchor.x * pixelsPerCm; const y = anchor.y * pixelsPerCm;
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

        // Zone drawing state
        let isDrawingZone = false;
        let isResizingZone = false;
        let resizingZoneId = null;
        let zoneStartX = 0, zoneStartY = 0;
        let currentZoneRect = null;
        let zoneCounter = 1;

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
                    alert(`Click and drag on the map to resize zone. The zone will be updated when you release the mouse.`);
                });
            });
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
                window.lastData = data; // Store for zone drawing preview
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
            if (!isDrawingZone && !isResizingZone) return;
            const rect = canvas.getBoundingClientRect();
            const pixelsPerCm = canvas.width / mapWidthCm;
            zoneStartX = (e.clientX - rect.left) / pixelsPerCm;
            zoneStartY = (e.clientY - rect.top) / pixelsPerCm;
            currentZoneRect = { x1: zoneStartX, y1: zoneStartY, x2: zoneStartX, y2: zoneStartY };
        });
        
        canvas.addEventListener('mousemove', (e) => {
            if ((!isDrawingZone && !isResizingZone) || !currentZoneRect) return;
            const rect = canvas.getBoundingClientRect();
            const pixelsPerCm = canvas.width / mapWidthCm;
            currentZoneRect.x2 = (e.clientX - rect.left) / pixelsPerCm;
            currentZoneRect.y2 = (e.clientY - rect.top) / pixelsPerCm;
            // Trigger a redraw to show the preview
            if (window.lastData) {
                draw(window.lastData);
            }
        });
        
        canvas.addEventListener('mouseup', async (e) => {
            if ((!isDrawingZone && !isResizingZone) || !currentZoneRect) return;
            const rect = canvas.getBoundingClientRect();
            const pixelsPerCm = canvas.width / mapWidthCm;
            const x2 = (e.clientX - rect.left) / pixelsPerCm;
            const y2 = (e.clientY - rect.top) / pixelsPerCm;
            
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
                const pixelsPerCm = canvas.width / mapWidthCm;
                const x1 = currentZoneRect.x1 * pixelsPerCm;
                const y1 = currentZoneRect.y1 * pixelsPerCm;
                const x2 = currentZoneRect.x2 * pixelsPerCm;
                const y2 = currentZoneRect.y2 * pixelsPerCm;
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
            // Resize canvas after sidebar toggle
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
