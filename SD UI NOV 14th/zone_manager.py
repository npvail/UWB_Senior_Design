"""
Zone management for tracking tag locations within defined zones
"""
import threading


class ZoneManager:
    """Manages zones and tag-zone intersection detection"""
    
    def __init__(self):
        self.zones = []  # List of zones: {id, name, x1, y1, x2, y2, color, severity}
        self.zone_id_counter = 0
        self.zone_lock = threading.Lock()
        self.tag_zone_alerts = {}  # Track which tags are in which zones: {tag_name: [zone_ids]}
    
    def create_zone(self, name, x1, y1, x2, y2, color='#ff0000', severity='WARNING'):
        """
        Create a new zone with rectangular coordinates.
        
        Args:
            name: Zone name
            x1, y1, x2, y2: Zone boundaries
            color: Zone color (hex)
            severity: 'WARNING' or 'ALERT'
        
        Returns:
            Created zone dictionary
        """
        # Validate severity
        if severity not in ['WARNING', 'ALERT']:
            severity = 'WARNING'
        
        with self.zone_lock:
            self.zone_id_counter += 1
            zone = {
                'id': self.zone_id_counter,
                'name': name,
                'x1': min(x1, x2),
                'y1': min(y1, y2),
                'x2': max(x1, x2),
                'y2': max(y1, y2),
                'color': color,
                'severity': severity
            }
            self.zones.append(zone)
            return zone
    
    def update_zone(self, zone_id, name=None, color=None, severity=None, 
                    x1=None, y1=None, x2=None, y2=None):
        """
        Update zone properties.
        
        Returns:
            True if zone was found and updated, False otherwise
        """
        # Validate severity if provided
        if severity and severity not in ['WARNING', 'ALERT']:
            return False
        
        # Validate name if provided
        if name is not None and (not name or len(name.strip()) == 0):
            return False
        
        with self.zone_lock:
            zone_found = False
            for zone in self.zones:
                if zone['id'] == zone_id:
                    if name is not None:
                        zone['name'] = name.strip()
                    if color is not None:
                        zone['color'] = color
                    if severity is not None:
                        zone['severity'] = severity
                    if x1 is not None and y1 is not None and x2 is not None and y2 is not None:
                        try:
                            zone['x1'] = min(float(x1), float(x2))
                            zone['y1'] = min(float(y1), float(y2))
                            zone['x2'] = max(float(x1), float(x2))
                            zone['y2'] = max(float(y1), float(y2))
                        except (ValueError, TypeError):
                            return False
                    zone_found = True
                    break
            
            return zone_found
    
    def delete_zone(self, zone_id):
        """
        Delete a zone by ID.
        
        Returns:
            True if zone was found and deleted, False otherwise
        """
        with self.zone_lock:
            original_count = len(self.zones)
            self.zones = [z for z in self.zones if z['id'] != zone_id]
            
            # Clean up alerts for this zone
            for tag_name in list(self.tag_zone_alerts.keys()):
                if zone_id in self.tag_zone_alerts[tag_name]:
                    self.tag_zone_alerts[tag_name].remove(zone_id)
                    if not self.tag_zone_alerts[tag_name]:
                        del self.tag_zone_alerts[tag_name]
            
            return len(self.zones) < original_count
    
    def get_zones(self):
        """Get all zones"""
        with self.zone_lock:
            return self.zones.copy()
    
    def is_point_in_zone(self, x, y, zone):
        """Check if a point (x, y) is inside a rectangular zone"""
        return zone['x1'] <= x <= zone['x2'] and zone['y1'] <= y <= zone['y2']
    
    def check_zone_alerts(self, tags):
        """
        Check all tags against all zones and update alerts.
        
        Args:
            tags: List of UWB tag objects
        
        Returns:
            Dictionary of new zone entries: {tag_name: [zone_ids]}
        """
        current_alerts = {}
        
        with self.zone_lock:
            for tag_obj in tags:
                if not tag_obj.status:
                    continue
                tag_in_zones = []
                for zone in self.zones:
                    if self.is_point_in_zone(tag_obj.x, tag_obj.y, zone):
                        tag_in_zones.append(zone['id'])
                if tag_in_zones:
                    current_alerts[tag_obj.name] = tag_in_zones
            
            # Detect new entries (tags entering zones)
            new_entries = {}
            for tag_name, zone_ids in current_alerts.items():
                if tag_name not in self.tag_zone_alerts:
                    # Tag just entered zones
                    new_entries[tag_name] = zone_ids
                else:
                    # Check for new zone entries
                    new_zones = [zid for zid in zone_ids if zid not in self.tag_zone_alerts[tag_name]]
                    if new_zones:
                        new_entries[tag_name] = new_zones
            
            self.tag_zone_alerts = current_alerts.copy()
            return new_entries
    
    def get_alerts(self):
        """Get current tag-zone alerts"""
        with self.zone_lock:
            return {tag_name: zone_ids.copy() for tag_name, zone_ids in self.tag_zone_alerts.items()}

