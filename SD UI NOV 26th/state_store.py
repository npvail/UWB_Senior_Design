"""JSON-backed persistence helpers for anchors, zones, tags, and map dimensions."""
import json
import logging
import os
import threading
from typing import List

from uwb import UWB
from zone_manager import ZoneManager

STATE_FILE = os.path.join(os.path.dirname(__file__), 'state.json')
_state_lock = threading.Lock()
_LOGGER = logging.getLogger(__name__)


def _serialize_anchors(anchors: List[UWB]):
    return [
        {
            'name': anchor.name,
            'x': anchor.x,
            'y': anchor.y
        }
        for anchor in anchors
    ]


def _serialize_tags(tags: List[UWB]):
    return [
        {
            'name': tag.name,
            'index': index
        }
        for index, tag in enumerate(tags)
    ]


def load_state():
    """Load persisted state from disk, if available."""
    if not os.path.exists(STATE_FILE):
        return None

    with _state_lock:
        try:
            with open(STATE_FILE, 'r', encoding='utf-8') as state_file:
                return json.load(state_file)
        except (json.JSONDecodeError, OSError) as exc:
            _LOGGER.warning("Failed to read state file '%s': %s", STATE_FILE, exc)
            return None


def save_state(
    anchors: List[UWB],
    tags: List[UWB],
    zone_manager: ZoneManager,
    map_width_cm: int,
    map_height_cm: int
):
    """Persist the current in-memory state to disk."""
    zone_snapshot = zone_manager.get_zone_state()
    payload = {
        'anchors': _serialize_anchors(anchors),
        'tags': _serialize_tags(tags),
        'map': {
            'width_cm': map_width_cm,
            'height_cm': map_height_cm
        },
        'zones': zone_snapshot.get('zones', []),
        'zone_id_counter': zone_snapshot.get('zone_id_counter', 0)
    }

    os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)

    with _state_lock:
        temp_path = f"{STATE_FILE}.tmp"
        with open(temp_path, 'w', encoding='utf-8') as state_file:
            json.dump(payload, state_file, indent=2)
        os.replace(temp_path, STATE_FILE)

