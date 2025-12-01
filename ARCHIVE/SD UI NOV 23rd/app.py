"""
Main Flask application for UWB tracking system
"""
import threading
from flask import Flask, render_template, jsonify, request
from uwb import UWB
from serial_reader import SerialReader
from zone_manager import ZoneManager
from config import (
    ANC_COUNT, TAG_COUNT, A0X, A0Y, A1X, A1Y, A2X, A2Y,
    MAP_WIDTH_CM, MAP_HEIGHT_CM, FLASK_HOST, FLASK_PORT
)


# Initialize Flask app
app = Flask(__name__)

# Initialize UWB objects
anc = []
tag = []

for i in range(ANC_COUNT):
    name = "ANC " + str(i)
    anc.append(UWB(name, 0))

for i in range(TAG_COUNT):
    name = "TAG " + str(i)
    tag.append(UWB(name, 1))

# Set initial anchor positions
anc[0].set_location(A0X, A0Y)
anc[1].set_location(A1X, A1Y)
anc[2].set_location(A2X, A2Y)

# Initialize zone manager
zone_manager = ZoneManager()

# Initialize serial reader
serial_reader = SerialReader(anc, tag)

# Global map dimensions (can be updated)
map_width_cm = MAP_WIDTH_CM
map_height_cm = MAP_HEIGHT_CM
map_lock = threading.Lock()


# Flask Routes
@app.route('/')
def index():
    """Main page route"""
    return render_template('index.html')


@app.route('/data')
def get_data():
    """Get current tracking data"""
    # Check for zone alerts
    new_entries = zone_manager.check_zone_alerts(tag)
    
    # Create dictionaries on the fly to keep UWB class clean
    anchor_data = [{"name": a.name, "x": a.x, "y": a.y, "status": a.status} for a in anc]
    tag_data = [{"name": t.name, "x": t.x, "y": t.y, "status": t.status, "ranges": t.list} for t in tag]
    
    # Get current zone data
    zone_data = zone_manager.get_zones()
    
    # Get current alerts
    current_alerts = zone_manager.get_alerts()
    
    with map_lock:
        current_width = map_width_cm
        current_height = map_height_cm
    
    return jsonify({
        "anchors": anchor_data,
        "tags": tag_data,
        "zones": zone_data,
        "alerts": current_alerts,
        "new_entries": new_entries,
        "map_width_cm": current_width,
        "map_height_cm": current_height
    })


@app.route('/update_anchors', methods=['POST'])
def update_anchor_positions():
    """Update anchor positions"""
    data = request.get_json()
    with threading.Lock():
        for anchor_data in data:
            name = anchor_data.get('name')
            new_x = float(anchor_data.get('x'))
            new_y = float(anchor_data.get('y'))
            for anchor_obj in anc:
                if anchor_obj.name == name:
                    anchor_obj.set_location(new_x, new_y)
                    break
    return jsonify({"status": "success", "message": "Anchors updated"})


@app.route('/rename_tag', methods=['POST'])
def rename_tag():
    """Rename a tag"""
    data = request.get_json()
    old_name = data.get('old_name')
    new_name = data.get('new_name')

    if not old_name or not new_name:
        return jsonify({"status": "error", "message": "Missing name fields"}), 400

    tag_found = False
    with threading.Lock():
        for tag_obj in tag:
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
    """Update map area dimensions"""
    global map_width_cm, map_height_cm
    data = request.get_json()
    new_width = data.get('width')
    new_height = data.get('height')

    if not new_width or not new_height:
        return jsonify({"status": "error", "message": "Missing dimensions"}), 400
    
    with map_lock:
        map_width_cm = int(new_width)
        map_height_cm = int(new_height)
    
    return jsonify({"status": "success", "message": "Area dimensions updated"})


@app.route('/create_zone', methods=['POST'])
def create_zone():
    """Create a new zone"""
    data = request.get_json()
    name = data.get('name', 'Zone')
    x1 = float(data.get('x1', 0))
    y1 = float(data.get('y1', 0))
    x2 = float(data.get('x2', 0))
    y2 = float(data.get('y2', 0))
    color = data.get('color', '#ff0000')
    severity = data.get('severity', 'WARNING')
    
    zone = zone_manager.create_zone(name, x1, y1, x2, y2, color, severity)
    return jsonify({"status": "success", "message": "Zone created", "zone": zone})


@app.route('/update_zone', methods=['POST'])
def update_zone():
    """Update zone properties"""
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
    
    success = zone_manager.update_zone(zone_id, name, color, severity, x1, y1, x2, y2)
    
    if success:
        return jsonify({"status": "success", "message": "Zone updated"})
    else:
        return jsonify({"status": "error", "message": "Zone not found or invalid data"}), 404


@app.route('/delete_zone', methods=['POST'])
def delete_zone():
    """Delete a zone"""
    data = request.get_json()
    zone_id = data.get('id')
    
    if zone_id is None:
        return jsonify({"status": "error", "message": "Missing zone ID"}), 400
    
    success = zone_manager.delete_zone(zone_id)
    
    if success:
        return jsonify({"status": "success", "message": "Zone deleted"})
    else:
        return jsonify({"status": "error", "message": "Zone not found"}), 404


@app.route('/get_zones', methods=['GET'])
def get_zones():
    """Get all zones"""
    zones = zone_manager.get_zones()
    return jsonify({"status": "success", "zones": zones})


if __name__ == '__main__':
    # Start the serial reader thread
    if serial_reader.start():
        print("Serial reader started successfully")
    else:
        print("WARNING: Failed to start serial reader. Continuing without serial connection.")
    
    # Start the Flask server
    app.run(host=FLASK_HOST, port=FLASK_PORT, debug=False)

