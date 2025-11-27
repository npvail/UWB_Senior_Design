"""
Main Flask application for UWB tracking system
"""
import threading
import socket
from flask import Flask, render_template, jsonify, request
from uwb import UWB
from serial_reader import SerialReader
from zone_manager import ZoneManager
from config import (
    ANC_COUNT, TAG_COUNT, A0X, A0Y, A1X, A1Y, A2X, A2Y,
    A0Z, A1Z, A2Z, TAG_HEIGHT,
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

# Set initial anchor positions and Z-heights
anc[0].set_location(A0X, A0Y)
anc[0].z = A0Z
anc[1].set_location(A1X, A1Y)
anc[1].z = A1Z
anc[2].set_location(A2X, A2Y)
anc[2].z = A2Z

# Set initial tag Z-height
tag[0].z = TAG_HEIGHT

# Global map dimensions (can be updated)
map_width_cm = MAP_WIDTH_CM
map_height_cm = MAP_HEIGHT_CM
map_lock = threading.Lock()

# Global height values (can be updated)
anchor_z_heights = [A0Z, A1Z, A2Z]
tag_height = TAG_HEIGHT
height_lock = threading.Lock()

# Initialize zone manager
zone_manager = ZoneManager()

# Create height getter function for serial reader
def get_heights():
    """Get current anchor Z-heights and tag height"""
    with height_lock:
        return (anchor_z_heights.copy(), tag_height)

# Function to sync heights to UWB objects
def sync_heights_to_objects():
    """Sync the global height values to the actual UWB anchor and tag objects"""
    with height_lock:
        # Update anchor Z-heights
        for i, height in enumerate(anchor_z_heights):
            if i < len(anc):
                anc[i].z = height
        # Update tag Z-heights
        for t in tag:
            t.z = tag_height

# Initialize serial reader with height getter
serial_reader = SerialReader(anc, tag, height_getter=get_heights)

# Sync initial heights to UWB objects
sync_heights_to_objects()


def get_server_ip_addresses():
    """
    Get all IP addresses of the machine running this server.
    This includes localhost and the primary network interface IP.
    
    Returns:
        Set of IP addresses (strings)
    """
    ip_addresses = set()
    
    # Always include localhost addresses
    ip_addresses.add('127.0.0.1')
    ip_addresses.add('::1')
    ip_addresses.add('localhost')
    
    try:
        # Get hostname
        hostname = socket.gethostname()
        ip_addresses.add(hostname)
        
        # Get IP by hostname
        try:
            host_ip = socket.gethostbyname(hostname)
            ip_addresses.add(host_ip)
        except:
            pass
        
        # Get local network IP by connecting to external address
        # This determines which interface would be used for external connections
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            try:
                # Connect to a remote address (doesn't actually send data)
                s.connect(('8.8.8.8', 80))
                local_ip = s.getsockname()[0]
                ip_addresses.add(local_ip)
                print(f"Detected server local IP: {local_ip}")
            except:
                pass
            finally:
                s.close()
        except:
            pass
        
        # Also get all IPs from hostname_ex
        try:
            hostname_ex = socket.getfqdn()
            if hostname_ex != hostname:
                ip_addresses.add(hostname_ex)
                try:
                    host_ip_ex = socket.gethostbyname(hostname_ex)
                    ip_addresses.add(host_ip_ex)
                except:
                    pass
        except:
            pass
    except Exception as e:
        print(f"Warning: Could not determine all server IPs: {e}")
    
    return ip_addresses


# Cache server IP addresses (calculated once at startup)
_server_ips = None


def is_admin_request():
    """
    Check if the request is from the machine running this server (admin/host machine).
    Only the host machine can make editing changes.
    
    Returns:
        True if request is from the host machine, False otherwise
    """
    global _server_ips
    
    # Initialize server IPs cache if not done
    if _server_ips is None:
        _server_ips = get_server_ip_addresses()
        print(f"Server IP addresses (admin allowed): {_server_ips}")
    
    # Get the remote address
    remote_addr = str(request.remote_addr)
    
    # Check if it's one of the server's IP addresses
    if remote_addr in _server_ips:
        return True
    
    # Also check X-Forwarded-For header in case of reverse proxy
    forwarded_for = request.headers.get('X-Forwarded-For', '')
    if forwarded_for:
        # X-Forwarded-For can contain multiple IPs, get the first one
        first_ip = forwarded_for.split(',')[0].strip()
        if first_ip in _server_ips:
            return True
    
    # Additional check: if remote_addr matches any server IP (case-insensitive string comparison)
    remote_addr_lower = remote_addr.lower()
    for server_ip in _server_ips:
        if remote_addr_lower == str(server_ip).lower():
            return True
    
    return False


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
    anchor_data = [{"name": a.name, "x": a.x, "y": a.y, "z": a.z, "status": a.status} for a in anc]
    tag_data = [{"name": t.name, "x": t.x, "y": t.y, "z": t.z, "status": t.status, "ranges": t.list} for t in tag]
    
    # Get current zone data
    zone_data = zone_manager.get_zones()
    
    # Get current alerts
    current_alerts = zone_manager.get_alerts()
    
    with map_lock:
        current_width = map_width_cm
        current_height = map_height_cm
    
    with height_lock:
        current_anchor_heights = anchor_z_heights.copy()
        current_tag_height = tag_height
    
    return jsonify({
        "anchors": anchor_data,
        "tags": tag_data,
        "zones": zone_data,
        "alerts": current_alerts,
        "new_entries": new_entries,
        "map_width_cm": current_width,
        "map_height_cm": current_height,
        "anchor_z_heights": current_anchor_heights,
        "tag_height": current_tag_height
    })


@app.route('/update_anchors', methods=['POST'])
def update_anchor_positions():
    """Update anchor positions - Admin only"""
    if not is_admin_request():
        return jsonify({"status": "error", "message": "Unauthorized: Only host machine can edit settings"}), 403
    
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
    """Rename a tag - Admin only"""
    if not is_admin_request():
        return jsonify({"status": "error", "message": "Unauthorized: Only host machine can edit settings"}), 403
    
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
    """Update map area dimensions - Admin only"""
    if not is_admin_request():
        return jsonify({"status": "error", "message": "Unauthorized: Only host machine can edit settings"}), 403
    
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
    """Create a new zone - Admin only"""
    if not is_admin_request():
        return jsonify({"status": "error", "message": "Unauthorized: Only host machine can edit settings"}), 403
    
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
    """Update zone properties - Admin only"""
    if not is_admin_request():
        return jsonify({"status": "error", "message": "Unauthorized: Only host machine can edit settings"}), 403
    
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
    """Delete a zone - Admin only"""
    if not is_admin_request():
        return jsonify({"status": "error", "message": "Unauthorized: Only host machine can edit settings"}), 403
    
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


@app.route('/check_admin', methods=['GET'])
def check_admin():
    """Check if current request is from admin (host machine)"""
    is_admin = is_admin_request()
    return jsonify({"is_admin": is_admin})


@app.route('/update_heights', methods=['POST'])
def update_heights():
    """Update anchor Z-heights and tag height - Admin only"""
    if not is_admin_request():
        return jsonify({"status": "error", "message": "Unauthorized: Only host machine can edit settings"}), 403
    
    global anchor_z_heights, tag_height
    data = request.get_json()
    
    if not data:
        return jsonify({"status": "error", "message": "No data provided"}), 400
    
    # Update anchor Z-heights
    if 'anchor_z_heights' in data:
        new_heights = data['anchor_z_heights']
        if isinstance(new_heights, list):
            # Ensure we have the correct number of heights
            while len(new_heights) < ANC_COUNT:
                new_heights.append(0.0)
            # Take only the first ANC_COUNT values
            new_heights = new_heights[:ANC_COUNT]
            with height_lock:
                anchor_z_heights = [float(h) for h in new_heights]
                # Update the actual anchor objects' z values
                for i, height in enumerate(anchor_z_heights):
                    if i < len(anc):
                        anc[i].z = height
            print(f"Updated anchor Z-heights: {anchor_z_heights}")
        else:
            return jsonify({"status": "error", "message": "anchor_z_heights must be a list"}), 400
    
    # Update tag height
    if 'tag_height' in data:
        new_tag_height = data.get('tag_height')
        if new_tag_height is not None:
            with height_lock:
                tag_height = float(new_tag_height)
                # Update the actual tag objects' z values
                for t in tag:
                    t.z = tag_height
            print(f"Updated tag height: {tag_height}")
    
    # Sync heights to UWB objects (redundant but safe)
    sync_heights_to_objects()
    
    return jsonify({"status": "success", "message": "Heights updated successfully"})


@app.route('/get_heights', methods=['GET'])
def get_heights():
    """Get current anchor Z-heights and tag height"""
    with height_lock:
        current_anchor_heights = anchor_z_heights.copy()
        current_tag_height = tag_height
    
    return jsonify({
        "status": "success",
        "anchor_z_heights": current_anchor_heights,
        "tag_height": current_tag_height
    })


if __name__ == '__main__':
    # Start the serial reader thread
    if serial_reader.start():
        print("Serial reader started successfully")
    else:
        print("WARNING: Failed to start serial reader. Continuing without serial connection.")
    
    # Start the Flask server
    app.run(host=FLASK_HOST, port=FLASK_PORT, debug=False)

