"""
UWB class for representing anchors and tags with positioning logic
"""
import math
from config import RED, BLACK


class UWB:
    """Represents a UWB anchor or tag"""
    
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
        """Set the location and mark as active"""
        self.x = x
        self.y = y
        self.status = True

    def cal(self, anchors):
        """
        Calculate position using trilateration with multiple anchor pairs.
        Requires at least 3 valid anchor ranges.
        """
        count = 0
        anc_id_list = []
        for range_val in self.list:
            if range_val != 0:
                anc_id_list.append(count)
            count += 1
        
        if len(anc_id_list) >= 3:
            x, y = 0.0, 0.0
            temp_x, temp_y = self.three_point_uwb(anchors, anc_id_list[0], anc_id_list[1])
            x += temp_x
            y += temp_y
            temp_x, temp_y = self.three_point_uwb(anchors, anc_id_list[0], anc_id_list[2])
            x += temp_x
            y += temp_y
            temp_x, temp_y = self.three_point_uwb(anchors, anc_id_list[2], anc_id_list[1])
            x += temp_x
            y += temp_y
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

    def three_point_uwb(self, anchors, a_id, b_id):
        """Calculate position using two anchors"""
        return self.three_point(
            anchors[a_id].x, anchors[a_id].y,
            anchors[b_id].x, anchors[b_id].y,
            self.list[a_id], self.list[b_id]
        )

    def three_point(self, x1, y1, x2, y2, r1, r2):
        """
        Trilateration calculation using two anchor points and distances.
        Returns calculated (x, y) position.
        """
        temp_x, temp_y = 0.0, 0.0
        p2p = math.sqrt((x1 - x2)**2 + (y1 - y2)**2)
        if p2p == 0:
            return (x1, y1)  # Avoid division by zero
        if r1 + r2 <= p2p:
            temp_x = x1 + (x2 - x1) * r1 / (r1 + r2)
            temp_y = y1 + (y2 - y1) * r1 / (r1 + r2)
        else:
            dr = p2p / 2 + (r1**2 - r2**2) / (2 * p2p)
            temp_x = x1 + (x2 - x1) * dr / p2p
            temp_y = y1 + (y2 - y1) * dr / p2p
        return temp_x, temp_y

