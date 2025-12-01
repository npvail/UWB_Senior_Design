"""
Main Flask application for UWB tracking system
"""
import logging
import threading
from functools import wraps
from flask import Flask, render_template, jsonify, request
from flask_socketio import SocketIO, emit
from uwb import UWB
from serial_reader import SerialReader
from zone_manager import ZoneManager
from state_store import load_state, save_state
from config import (
    ANC_COUNT, TAG_COUNT, A0X, A0Y, A1X, A1Y, A2X, A2Y,
    MAP_WIDTH_CM, MAP_HEIGHT_CM, FLASK_HOST, FLASK_PORT, ADMIN_IPS
)

logging.basicConfig(level=logging.INFO)


def validate_configuration():
    if ANC_COUNT < 3:
        raise ValueError("ANC_COUNT must be at least 3 (got %s)" % ANC_COUNT)
    if TAG_COUNT < 1:
        raise ValueError("TAG_COUNT must be at least 1 (got %s)" % TAG_COUNT)
    if MAP_WIDTH_CM <= 0 or MAP_HEIGHT_CM <= 0:
        raise ValueError("Map dimensions must be positive (got %sx%s)" % (MAP_WIDTH_CM, MAP_HEIGHT_CM))


validate_configuration()


# Initialize Flask app and SocketIO
app = Flask(__name__)
socketio = SocketIO(
    app,
    cors_allowed_origins="*",
    async_mode='threading',
    engineio_logger=False,
    socketio_logger=False,
    ping_timeout=60,
    ping_interval=25
)

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

# Global map dimensions (can be updated)
map_width_cm = MAP_WIDTH_CM
map_height_cm = MAP_HEIGHT_CM
map_lock = threading.Lock()
anchor_lock = threading.Lock()
tag_lock = threading.Lock()
ADMIN_IP_WHITELIST = set(ADMIN_IPS)

# Log admin IPs on startup
logger = logging.getLogger(__name__)
logger.info("Admin IP whitelist: %s", ADMIN_IP_WHITELIST)


def _get_remote_addr():
    """Get the real remote address, handling proxies and forwarding."""
    forwarded = request.headers.get('X-Forwarded-For')
    if forwarded:
        # X-Forwarded-For can be a comma-separated list; take the first one
        return forwarded.split(',')[0].strip()
    return request.remote_addr or ''


def is_admin_request():
    """Check if the requesting IP/hostname is in the admin whitelist."""
    remote = _get_remote_addr()
    is_admin = remote in ADMIN_IP_WHITELIST
    
    # Log for debugging - helps identify why admin access is denied
    if not is_admin:
        app.logger.warning(
            "Non-admin access attempt from: %s (whitelist: %s)",
            remote,
            ADMIN_IP_WHITELIST
        )
    
    return is_admin


def require_admin(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        if not is_admin_request():
            return jsonify({
                "status": "error",
                "message": "Write access restricted to the host running this service."
            }), 403
        return func(*args, **kwargs)
    return wrapper


# Tracking data helpers
def build_tracking_payload(new_entries=None):
    """Assemble the latest tracking snapshot for clients."""
    anchor_data = [{"name": a.name, "x": a.x, "y": a.y, "status": a.status} for a in anc]
    tag_data = [{"name": t.name, "x": t.x, "y": t.y, "status": t.status, "ranges": t.list} for t in tag]
    zone_data = zone_manager.get_zones()
    current_alerts = zone_manager.get_alerts()

    with map_lock:
        current_width = map_width_cm
        current_height = map_height_cm

    return {
        "anchors": anchor_data,
        "tags": tag_data,
        "zones": zone_data,
        "alerts": current_alerts,
        "new_entries": new_entries or {},
        "map_width_cm": current_width,
        "map_height_cm": current_height
    }


def persist_state():
    """Persist anchors, zones, and map dimensions to disk."""
    with map_lock:
        current_width = map_width_cm
        current_height = map_height_cm
    try:
        save_state(anc, tag, zone_manager, current_width, current_height)
    except OSError as exc:
        app.logger.error("Failed to persist state: %s", exc)


def apply_persisted_state():
    """Load any persisted state from disk on startup."""
    global map_width_cm, map_height_cm
    state = load_state()
    if not state:
        persist_state()
        return

    anchor_data = state.get("anchors", [])
    with anchor_lock:
        if anchor_data and len(anchor_data) != len(anc):
            app.logger.warning(
                "Persisted anchor count (%s) does not match config (%s)",
                len(anchor_data),
                len(anc)
            )
        for stored_anchor in anchor_data:
            name = stored_anchor.get("name")
            match = next((anchor for anchor in anc if anchor.name == name), None)
            if match is None:
                continue
            try:
                match.set_location(
                    float(stored_anchor.get("x", match.x)),
                    float(stored_anchor.get("y", match.y)),
                    apply_smoothing=False
                )
            except (TypeError, ValueError):
                continue

    tag_data = state.get("tags", [])
    with tag_lock:
        if tag_data and len(tag_data) != len(tag):
            app.logger.warning(
                "Persisted tag count (%s) does not match config (%s)",
                len(tag_data),
                len(tag)
            )
        for stored_tag in tag_data:
            try:
                index = int(stored_tag.get("index", -1))
            except (TypeError, ValueError):
                continue
            if index < 0 or index >= len(tag):
                app.logger.warning("Skipping tag entry with invalid index: %s", stored_tag)
                continue
            name = stored_tag.get("name")
            if isinstance(name, str) and name:
                tag[index].name = name

    zone_manager.load_zones(state.get("zones", []), state.get("zone_id_counter"))

    map_state = state.get("map", {})
    with map_lock:
        try:
            map_width_cm = int(map_state.get("width_cm", map_width_cm))
            map_height_cm = int(map_state.get("height_cm", map_height_cm))
        except (TypeError, ValueError):
            pass

    persist_state()


def broadcast_update(new_entries=None):
    """Push the latest tracking payload to all connected clients."""
    payload = build_tracking_payload(new_entries)
    socketio.emit('tracking_update', payload)


def handle_serial_update():
    """Called when a new serial reading updates tag positions."""
    new_entries = zone_manager.check_zone_alerts(tag)
    broadcast_update(new_entries)


apply_persisted_state()

# Initialize serial reader with realtime callback
serial_reader = SerialReader(anc, tag, on_update=handle_serial_update)


# Flask Routes
@app.route('/')
def index():
    """Main page route"""
    return render_template('index.html')


@app.route('/data')
def get_data():
    """Get current tracking data"""
    new_entries = zone_manager.check_zone_alerts(tag)
    payload = build_tracking_payload(new_entries)
    payload["can_modify"] = is_admin_request()
    return jsonify(payload)


@app.route('/update_anchors', methods=['POST'])
@require_admin
def update_anchor_positions():
    """Update anchor positions"""
    data = request.get_json()
    updated = False
    with anchor_lock:
        for anchor_data in data:
            name = anchor_data.get('name')
            try:
                new_x = float(anchor_data.get('x'))
                new_y = float(anchor_data.get('y'))
            except (TypeError, ValueError):
                continue
            for anchor_obj in anc:
                if anchor_obj.name == name:
                    anchor_obj.set_location(new_x, new_y)
                    updated = True
                    break
    if updated:
        persist_state()
        broadcast_update()
    return jsonify({"status": "success", "message": "Anchors updated"})


@app.route('/rename_tag', methods=['POST'])
@require_admin
def rename_tag():
    """Rename a tag"""
    data = request.get_json()
    old_name = data.get('old_name')
    new_name = data.get('new_name')

    if not old_name or not new_name:
        return jsonify({"status": "error", "message": "Missing name fields"}), 400

    tag_found = False
    with tag_lock:
        for tag_obj in tag:
            if tag_obj.name == old_name:
                tag_obj.name = new_name
                tag_found = True
                break
    
    if tag_found:
        persist_state()
        broadcast_update()
        return jsonify({"status": "success", "message": f"Tag renamed to {new_name}"})
    else:
        return jsonify({"status": "error", "message": f"Tag '{old_name}' not found"}), 404


@app.route('/update_area', methods=['POST'])
@require_admin
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
    persist_state()
    broadcast_update()
    
    return jsonify({"status": "success", "message": "Area dimensions updated"})


@app.route('/create_zone', methods=['POST'])
@require_admin
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
    persist_state()
    broadcast_update()
    return jsonify({"status": "success", "message": "Zone created", "zone": zone})


@app.route('/update_zone', methods=['POST'])
@require_admin
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
        persist_state()
        broadcast_update()
        return jsonify({"status": "success", "message": "Zone updated"})
    else:
        return jsonify({"status": "error", "message": "Zone not found or invalid data"}), 404


@app.route('/delete_zone', methods=['POST'])
@require_admin
def delete_zone():
    """Delete a zone"""
    data = request.get_json()
    zone_id = data.get('id')
    
    if zone_id is None:
        return jsonify({"status": "error", "message": "Missing zone ID"}), 400
    
    success = zone_manager.delete_zone(zone_id)
    
    if success:
        persist_state()
        broadcast_update()
        return jsonify({"status": "success", "message": "Zone deleted"})
    else:
        return jsonify({"status": "error", "message": "Zone not found"}), 404


@app.route('/get_zones', methods=['GET'])
def get_zones():
    """Get all zones"""
    zones = zone_manager.get_zones()
    return jsonify({"status": "success", "zones": zones})


@socketio.on('connect')
def handle_connect():
    """Send the latest snapshot immediately after a client connects."""
    payload = build_tracking_payload()
    payload["can_modify"] = is_admin_request()
    emit('tracking_update', payload)


@app.route('/permissions', methods=['GET'])
def get_permissions():
    """Return whether the current requester can modify settings."""
    return jsonify({"can_modify": is_admin_request()})


if __name__ == '__main__':
    # Start the serial reader thread
    if serial_reader.start():
        print("Serial reader started successfully")
    else:
        print("WARNING: Failed to start serial reader. Continuing without serial connection.")
    
    # Start the Flask server
    socketio.run(app, host=FLASK_HOST, port=FLASK_PORT, debug=False)

