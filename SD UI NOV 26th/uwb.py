# """
# UWB class for representing anchors and tags with positioning logic
# """
# import math
# import time
# from typing import Optional, Tuple

# import numpy as np
# from config import RED, BLACK


# class KalmanFilter2D:
#     """
#     Constant-velocity Kalman filter for 2D tracking.

#     State vector: [x, y, vx, vy]^T
#     """

#     def __init__(self, process_variance: float = 50.0, measurement_variance: float = 100.0):
#         self.process_variance = process_variance
#         self.measurement_variance = measurement_variance
#         self.state: Optional[np.ndarray] = None
#         self.covariance: Optional[np.ndarray] = None

#     def reset(self):
#         self.state = None
#         self.covariance = None

#     def _ensure_initialized(self, measurement: Tuple[float, float]):
#         if self.state is None:
#             self.state = np.array([[measurement[0]], [measurement[1]], [0.0], [0.0]], dtype=float)
#             self.covariance = np.eye(4, dtype=float) * 1000.0

#     def _get_f_matrix(self, dt: float) -> np.ndarray:
#         return np.array([
#             [1.0, 0.0, dt, 0.0],
#             [0.0, 1.0, 0.0, dt],
#             [0.0, 0.0, 1.0, 0.0],
#             [0.0, 0.0, 0.0, 1.0],
#         ], dtype=float)

#     def _get_q_matrix(self, dt: float) -> np.ndarray:
#         dt2 = dt * dt
#         dt3 = dt2 * dt
#         dt4 = dt3 * dt
#         q = self.process_variance
#         return q * np.array([
#             [dt4 / 4.0, 0.0, dt3 / 2.0, 0.0],
#             [0.0, dt4 / 4.0, 0.0, dt3 / 2.0],
#             [dt3 / 2.0, 0.0, dt2, 0.0],
#             [0.0, dt3 / 2.0, 0.0, dt2],
#         ], dtype=float)

#     def predict(self, dt: float):
#         if self.state is None:
#             return
#         F = self._get_f_matrix(dt)
#         Q = self._get_q_matrix(dt)
#         self.state = F @ self.state
#         self.covariance = F @ self.covariance @ F.T + Q

#     def update(self, measurement: Tuple[float, float], dt: Optional[float]):
#         """
#         Incorporate a new measurement and return the filtered position.
#         """
#         dt = max(dt if dt and dt > 0 else 0.1, 1e-3)
#         self._ensure_initialized(measurement)
#         self.predict(dt)

#         H = np.array([
#             [1.0, 0.0, 0.0, 0.0],
#             [0.0, 1.0, 0.0, 0.0]
#         ], dtype=float)
#         R = np.eye(2, dtype=float) * self.measurement_variance
#         z = np.array([[measurement[0]], [measurement[1]]], dtype=float)

#         y = z - (H @ self.state)
#         S = H @ self.covariance @ H.T + R
#         K = self.covariance @ H.T @ np.linalg.inv(S)
#         self.state = self.state + K @ y
#         identity = np.eye(4, dtype=float)
#         self.covariance = (identity - K @ H) @ self.covariance

#         return self.state[0, 0], self.state[1, 0]


# class UWB:
#     """Represents a UWB anchor or tag"""
    
#     def __init__(self, name, type):
#         self.name = name
#         self.type = type
#         self.x = 0
#         self.y = 0
#         self.status = False
#         self.list = []
#         self.last_update_timestamp: Optional[float] = None

#         if self.type == 1:
#             self.color = RED
#             self.position_filter = KalmanFilter2D()
#         else:
#             self.color = BLACK
#             self.position_filter = None

#     def set_location(self, x, y, apply_smoothing=True):
#         """
#         Set the location and mark as active.

#         For tags, a Kalman filter is applied by default to stabilize motion while preserving responsiveness.
#         """
#         now = time.time()
#         if self.type == 1 and apply_smoothing and self.position_filter:
#             filtered_x, filtered_y = self.position_filter.update(
#                 (float(x), float(y)),
#                 dt=(now - self.last_update_timestamp) if self.last_update_timestamp else None
#             )
#             self.x = int(filtered_x)
#             self.y = int(filtered_y)
#         else:
#             self.x = x
#             self.y = y
#             if self.position_filter:
#                 self.position_filter.reset()
        
#         self.last_update_timestamp = now
#         self.status = True

#     def cal(self, anchors):
#         """
#         Calculate position using trilateration with multiple anchor pairs.
#         Requires at least 3 valid anchor ranges.
#         Uses improved trilateration that considers all anchors simultaneously.
#         """
#         count = 0
#         anc_id_list = []
#         for range_val in self.list:
#             if range_val != 0:
#                 anc_id_list.append(count)
#             count += 1

#         # Need at least 2 valid anchors to estimate a 2D position.
#         if len(anc_id_list) >= 3:
#             # Collect valid anchor positions and ranges
#             anchor_positions = []
#             anchor_ranges = []
#             for anc_id in anc_id_list:
#                 anchor_positions.append((anchors[anc_id].x, anchors[anc_id].y))
#                 anchor_ranges.append(self.list[anc_id])
            
#             # Use linear least squares trilateration (standard and most accurate method)
#             # Subtract first anchor's equation from others to get linear system
#             ref_x, ref_y = anchor_positions[0]
#             ref_r = anchor_ranges[0]
            
#             # Build linear system: 2*(xi-x0)*x + 2*(yi-y0)*y = (xi^2+yi^2-x0^2-y0^2) - (ri^2-r0^2)
#             A = []
#             b = []
            
#             for i in range(1, len(anchor_positions)):
#                 ax, ay = anchor_positions[i]
#                 r = anchor_ranges[i]
                
#                 # Linear equation: 2*(ax-ref_x)*x + 2*(ay-ref_y)*y = (ax^2+ay^2-ref_x^2-ref_y^2) - (r^2-ref_r^2)
#                 A.append([
#                     2 * (ax - ref_x),
#                     2 * (ay - ref_y)
#                 ])
#                 b.append(
#                     (ax**2 + ay**2 - ref_x**2 - ref_y**2) - (r**2 - ref_r**2)
#                 )
            
#             # Solve the linear system directly - this is the most accurate method
#             x, y = 0.0, 0.0  # Default fallback
            
#             if len(A) >= 2:
#                 a11, a12 = A[0]
#                 a21, a22 = A[1]
#                 b1, b2 = b[0], b[1]
                
#                 det = a11 * a22 - a12 * a21
#                 if abs(det) > 1e-6:  # Avoid division by zero
#                     x_ls = (b1 * a22 - b2 * a12) / det
#                     y_ls = (a11 * b2 - a21 * b1) / det
                    
#                     # Use linear least squares solution directly (most accurate)
#                     if not (math.isnan(x_ls) or math.isnan(y_ls) or 
#                            math.isinf(x_ls) or math.isinf(y_ls)):
#                         x, y = x_ls, y_ls
#                 else:
#                     # If determinant is zero, use fallback method
#                     x1, y1 = anchor_positions[0]
#                     x2, y2 = anchor_positions[1]
#                     x3, y3 = anchor_positions[2]
#                     r1, r2, r3 = anchor_ranges[0], anchor_ranges[1], anchor_ranges[2]
                    
#                     p1a, p1b = self.get_intersection_points(x1, y1, x2, y2, r1, r2)
#                     if p1a and p1b:
#                         dist1 = math.sqrt((p1a[0] - x3)**2 + (p1a[1] - y3)**2)
#                         dist2 = math.sqrt((p1b[0] - x3)**2 + (p1b[1] - y3)**2)
#                         if abs(dist1 - r3) < abs(dist2 - r3):
#                             x, y = p1a
#                         else:
#                             x, y = p1b
#                     elif p1a:
#                         x, y = p1a
            
#             # Fine-tune with a few gradient descent iterations to account for measurement errors
#             # But use very small steps to avoid diverging
#             for iteration in range(5):
#                 grad_x, grad_y = 0.0, 0.0
                
#                 for (ax, ay), r in zip(anchor_positions, anchor_ranges):
#                     dist = math.sqrt((x - ax)**2 + (y - ay)**2)
#                     if dist > 0.001:  # Avoid division by zero
#                         error = dist - r
#                         # Gradient components (normalized by distance)
#                         grad_x += error * (x - ax) / dist
#                         grad_y += error * (y - ay) / dist
                
#                 # Very small learning rate for fine-tuning only
#                 learning_rate = 0.05 / (len(anchor_positions) * (iteration + 1))
#                 x -= learning_rate * grad_x
#                 y -= learning_rate * grad_y
            
#             x = int(x)
#             y = int(y)

#             self.set_location(x, y)
#             self.status = True
#         elif len(anc_id_list) == 2:
#             # Fallback: use two-anchor trilateration when exactly two ranges are valid.
#             a_id, b_id = anc_id_list[0], anc_id_list[1]
#             x, y = self.three_point_uwb(anchors, a_id, b_id)
#             x = int(x)
#             y = int(y)

#             self.set_location(x, y)
#             self.status = True

#     def three_point_uwb(self, anchors, a_id, b_id):
#         """Calculate position using two anchors"""
#         return self.three_point(
#             anchors[a_id].x, anchors[a_id].y,
#             anchors[b_id].x, anchors[b_id].y,
#             self.list[a_id], self.list[b_id]
#         )
    
#     def get_intersection_points(self, x1, y1, x2, y2, r1, r2):
#         """
#         Calculate both intersection points of two circles.
#         Returns (point1, point2) where each point is (x, y) or None if circles don't intersect.
#         """
#         # Calculate distance between circle centers
#         p2p = math.sqrt((x2 - x1)**2 + (y2 - y1)**2)
        
#         # Handle edge cases
#         if p2p == 0:
#             return (None, None)  # Circles have same center
        
#         # Check if circles intersect
#         if r1 + r2 < p2p or abs(r1 - r2) > p2p:
#             return (None, None)  # Circles don't intersect
        
#         # Calculate the intersection point using proper circle-circle intersection formula
#         # Distance from circle 1 center to the line perpendicular to the line connecting centers
#         # that passes through the intersection points
#         a = (r1**2 - r2**2 + p2p**2) / (2 * p2p)
        
#         # Distance from the line connecting centers to the intersection points
#         h_squared = r1**2 - a**2
#         if h_squared < 0:
#             # Handle floating point errors - circles are tangent
#             h_squared = 0
#         h = math.sqrt(h_squared)
        
#         # Point on the line connecting centers that is perpendicular to intersection points
#         p0_x = x1 + a * (x2 - x1) / p2p
#         p0_y = y1 + a * (y2 - y1) / p2p
        
#         # Perpendicular vector to the line connecting centers
#         perp_x = -h * (y2 - y1) / p2p
#         perp_y = h * (x2 - x1) / p2p
        
#         # Two intersection points
#         point1 = (p0_x + perp_x, p0_y + perp_y)
#         point2 = (p0_x - perp_x, p0_y - perp_y) if h > 0 else None
        
#         return (point1, point2)

#     def three_point(self, x1, y1, x2, y2, r1, r2):
#         """
#         Trilateration calculation using two anchor points and distances.
#         Returns calculated (x, y) position using proper circle-circle intersection.
#         """
#         # Calculate distance between anchors
#         p2p = math.sqrt((x2 - x1)**2 + (y2 - y1)**2)
        
#         # Handle edge cases
#         if p2p == 0:
#             return (x1, y1)  # Anchors are at same location
        
#         # Check if circles intersect
#         if r1 + r2 < p2p:
#             # Circles don't intersect - place point on line between them
#             temp_x = x1 + (x2 - x1) * r1 / (r1 + r2)
#             temp_y = y1 + (y2 - y1) * r1 / (r1 + r2)
#             return temp_x, temp_y
        
#         if abs(r1 - r2) > p2p:
#             # One circle is completely inside the other
#             temp_x = x1 + (x2 - x1) * r1 / (r1 + r2)
#             temp_y = y1 + (y2 - y1) * r1 / (r1 + r2)
#             return temp_x, temp_y
        
#         # Calculate the intersection point using proper circle-circle intersection formula
#         # Distance from anchor 1 to the line perpendicular to the line connecting anchors
#         # that passes through the intersection points
#         a = (r1**2 - r2**2 + p2p**2) / (2 * p2p)
        
#         # Distance from the line connecting anchors to the intersection points
#         h_squared = r1**2 - a**2
#         if h_squared < 0:
#             h_squared = 0  # Handle floating point errors
#         h = math.sqrt(h_squared)
        
#         # Point on the line connecting anchors that is perpendicular to intersection points
#         p0_x = x1 + a * (x2 - x1) / p2p
#         p0_y = y1 + a * (y2 - y1) / p2p
        
#         # Calculate the two possible intersection points
#         # We choose the one that's more reasonable (typically the one further from origin if both anchors are in positive quadrant)
#         # For now, we'll return the first intersection point and let averaging handle selection
        
#         # Perpendicular vector to the line connecting anchors
#         perp_x = -h * (y2 - y1) / p2p
#         perp_y = h * (x2 - x1) / p2p
        
#         # First intersection point
#         temp_x = p0_x + perp_x
#         temp_y = p0_y + perp_y
        
#         return temp_x, temp_y

# """
# UWB class for representing anchors and tags with positioning logic
# """
# import math
# import time
# from typing import Optional, Tuple

# import numpy as np
# from config import RED, BLACK


# class KalmanFilter2D:
#     """Constant-velocity Kalman filter for 2D tracking."""
#     def __init__(self, process_variance: float = 50.0, measurement_variance: float = 150.0):
#         # Increased measurement_variance slightly to reduce jitter
#         self.process_variance = process_variance
#         self.measurement_variance = measurement_variance
#         self.state: Optional[np.ndarray] = None
#         self.covariance: Optional[np.ndarray] = None

#     def reset(self):
#         self.state = None
#         self.covariance = None

#     def _ensure_initialized(self, measurement: Tuple[float, float]):
#         if self.state is None:
#             self.state = np.array([[measurement[0]], [measurement[1]], [0.0], [0.0]], dtype=float)
#             self.covariance = np.eye(4, dtype=float) * 1000.0

#     def update(self, measurement: Tuple[float, float], dt: Optional[float]):
#         dt = max(dt if dt and dt > 0 else 0.1, 1e-3)
#         self._ensure_initialized(measurement)

#         # Predict
#         F = np.array([[1, 0, dt, 0], [0, 1, 0, dt], [0, 0, 1, 0], [0, 0, 0, 1]], dtype=float)
#         Q = np.eye(4) * self.process_variance * dt # Simplified Q scaling
#         self.state = F @ self.state
#         self.covariance = F @ self.covariance @ F.T + Q

#         # Update
#         H = np.array([[1, 0, 0, 0], [0, 1, 0, 0]], dtype=float)
#         R = np.eye(2, dtype=float) * self.measurement_variance
#         z = np.array([[measurement[0]], [measurement[1]]], dtype=float)

#         y = z - (H @ self.state)
#         S = H @ self.covariance @ H.T + R
#         K = self.covariance @ H.T @ np.linalg.inv(S)
#         self.state = self.state + K @ y
#         self.covariance = (np.eye(4) - K @ H) @ self.covariance

#         return self.state[0, 0], self.state[1, 0]


# class UWB:
#     """Represents a UWB anchor or tag"""
#     def __init__(self, name, type):
#         self.name = name
#         self.type = type
#         self.x = 0
#         self.y = 0
#         self.status = False
#         self.list = []
#         self.last_update_timestamp: Optional[float] = None

#         if self.type == 1:
#             self.color = RED
#             self.position_filter = KalmanFilter2D()
#         else:
#             self.color = BLACK
#             self.position_filter = None

#     def set_location(self, x, y, apply_smoothing=True):
#         now = time.time()
#         if self.type == 1 and apply_smoothing and self.position_filter:
#             filtered_x, filtered_y = self.position_filter.update(
#                 (float(x), float(y)),
#                 dt=(now - self.last_update_timestamp) if self.last_update_timestamp else None
#             )
#             self.x = int(filtered_x)
#             self.y = int(filtered_y)
#         else:
#             self.x = int(x)
#             self.y = int(y)
#             if self.position_filter:
#                 self.position_filter.reset()
        
#         self.last_update_timestamp = now
#         self.status = True

#     def cal(self, anchors):
#         count = 0
#         anc_id_list = []
#         for range_val in self.list:
#             if range_val > 0:
#                 anc_id_list.append(count)
#             count += 1

#         if len(anc_id_list) >= 3:
#             # --- 3+ Anchors: Linear Least Squares (Best Accuracy) ---
#             anchor_positions = []
#             anchor_ranges = []
#             for anc_id in anc_id_list:
#                 anchor_positions.append((anchors[anc_id].x, anchors[anc_id].y))
#                 anchor_ranges.append(self.list[anc_id])
            
#             ref_x, ref_y = anchor_positions[0]
#             ref_r = anchor_ranges[0]
#             A = []
#             b = []
            
#             for i in range(1, len(anchor_positions)):
#                 ax, ay = anchor_positions[i]
#                 r = anchor_ranges[i]
#                 A.append([2 * (ax - ref_x), 2 * (ay - ref_y)])
#                 b.append((ax**2 + ay**2 - ref_x**2 - ref_y**2) - (r**2 - ref_r**2))
            
#             if len(A) >= 2:
#                 # Use Numpy for robust solving
#                 try:
#                     result = np.linalg.lstsq(A, b, rcond=None)[0]
#                     self.set_location(result[0], result[1])
#                     return
#                 except Exception:
#                     pass # Fallback if matrix singular

#         if len(anc_id_list) >= 2:
#             # --- 2 Anchors: Circle Intersection (Smart Selection) ---
#             # We take the first two available anchors
#             a_id, b_id = anc_id_list[0], anc_id_list[1]
#             x, y = self.three_point_uwb(anchors, a_id, b_id)
#             self.set_location(x, y)

#     def three_point_uwb(self, anchors, a_id, b_id):
#         return self.three_point(
#             anchors[a_id].x, anchors[a_id].y,
#             anchors[b_id].x, anchors[b_id].y,
#             self.list[a_id], self.list[b_id]
#         )
    
#     def three_point(self, x1, y1, x2, y2, r1, r2):
#         """
#         Calculates intersection of two circles and intelligently picks the best point.
#         """
#         d = math.sqrt((x2 - x1)**2 + (y2 - y1)**2)
        
#         # 1. Check if circles are too far apart or one is inside another
#         if d > r1 + r2 or d < abs(r1 - r2) or d == 0:
#             # Fallback: midpoint weighted by radius
#             ratio = r1 / (r1 + r2)
#             return x1 + (x2 - x1) * ratio, y1 + (y2 - y1) * ratio

#         # 2. Calculate Intersection
#         a = (r1**2 - r2**2 + d**2) / (2 * d)
#         h = math.sqrt(max(0, r1**2 - a**2))
        
#         x0 = x1 + a * (x2 - x1) / d
#         y0 = y1 + a * (y2 - y1) / d
        
#         rx = -(y2 - y1) * (h / d)
#         ry = (x2 - x1) * (h / d)
        
#         # The two possible points
#         px1 = x0 + rx
#         py1 = y0 + ry
#         px2 = x0 - rx
#         py2 = y0 - ry

#         # 3. Smart Selection Logic
#         score1 = 0
#         score2 = 0
        
#         # Criteria A: Prefer positive coordinates (Assuming map is 0,0 to X,Y)
#         if px1 >= 0 and py1 >= 0: score1 += 1
#         if px2 >= 0 and py2 >= 0: score2 += 1
        
#         # Criteria B: Prefer point closest to last known position (tracking continuity)
#         # This prevents the tag from "flipping" to the mirror image
#         if self.status: # If we have a previous position
#             dist1 = (px1 - self.x)**2 + (py1 - self.y)**2
#             dist2 = (px2 - self.x)**2 + (py2 - self.y)**2
#             if dist1 < dist2: score1 += 2
#             else: score2 += 2
            
#         if score1 >= score2:
#             return px1, py1
#         else:
#             return px2, py2


"""
UWB class for representing anchors and tags with positioning logic.
HYBRID EDITION: Combines Kalman Filter (Physics) with Heuristic Stability (Static/Outlier detection).
"""
import math
import time
from typing import Optional, Tuple

import numpy as np
from config import RED, BLACK


class KalmanFilter2D:
    """Constant-velocity Kalman filter for 2D tracking."""
    def __init__(self, process_variance: float = 20.0, measurement_variance: float = 100.0):
        # process_variance: How fast we expect the object to change speed (Higher = more responsive)
        # measurement_variance: How much noise is in the raw UWB data (Higher = smoother/less jitter)
        self.process_variance = process_variance
        self.measurement_variance = measurement_variance
        self.state: Optional[np.ndarray] = None
        self.covariance: Optional[np.ndarray] = None

    def reset(self):
        self.state = None
        self.covariance = None

    def _ensure_initialized(self, measurement: Tuple[float, float]):
        if self.state is None:
            # Initial state [x, y, vx, vy]
            self.state = np.array([[measurement[0]], [measurement[1]], [0.0], [0.0]], dtype=float)
            self.covariance = np.eye(4, dtype=float) * 500.0

    def update(self, measurement: Tuple[float, float], dt: Optional[float]):
        dt = max(dt if dt and dt > 0 else 0.1, 1e-3)
        self._ensure_initialized(measurement)

        # 1. Predict next state based on physics (Velocity)
        F = np.array([[1, 0, dt, 0], [0, 1, 0, dt], [0, 0, 1, 0], [0, 0, 0, 1]], dtype=float)
        Q = np.eye(4) * self.process_variance * dt 
        self.state = F @ self.state
        self.covariance = F @ self.covariance @ F.T + Q

        # 2. Update with real measurement
        H = np.array([[1, 0, 0, 0], [0, 1, 0, 0]], dtype=float)
        R = np.eye(2, dtype=float) * self.measurement_variance
        z = np.array([[measurement[0]], [measurement[1]]], dtype=float)

        y = z - (H @ self.state)
        S = H @ self.covariance @ H.T + R
        K = self.covariance @ H.T @ np.linalg.inv(S)
        self.state = self.state + K @ y
        self.covariance = (np.eye(4) - K @ H) @ self.covariance

        return self.state[0, 0], self.state[1, 0]


class UWB:
    """Represents a UWB anchor or tag"""
    def __init__(self, name, type):
        self.name = name
        self.type = type # 0 = Anchor, 1 = Tag
        self.x = 0
        self.y = 0
        self.status = False
        self.list = []
        self.last_update_timestamp: Optional[float] = None
        
        # --- STABILITY SETTINGS  ---
        self.static_threshold = 10.0   # If moved < 10cm, ignore (reduces jitter)
        self.outlier_threshold = 300.0 # If moved > 300cm instantly, ignore (glitch)
        
        if self.type == 1:
            self.color = RED
            self.position_filter = KalmanFilter2D()
        else:
            self.color = BLACK
            self.position_filter = None

    def set_location(self, x, y, apply_smoothing=True):
        now = time.time()
        
        # --- HYBRID FILTERING LOGIC ---
        if self.type == 1 and apply_smoothing and self.position_filter:
            
            # 1. Calculate raw movement distance
            raw_dist = math.sqrt((x - self.x)**2 + (y - self.y)**2)
            
            # 2. Outlier Check 
            # If the tag "teleported" 3 meters in 0.1 seconds, it's probably a glitch.
            if self.status and raw_dist > self.outlier_threshold:
                # Ignore this reading, keep old position
                self.last_update_timestamp = now
                return 

            # 3. Static Check 
            # If the tag moved less than 10cm, assume it's standing still.
            # This prevents the dot from "dancing" when you place it on a table.
            if self.status and raw_dist < self.static_threshold:
                # Just update timestamp, don't move X/Y
                self.last_update_timestamp = now
                return

            # 4. Kalman Filter (Your Logic - Physics based)
            # If we passed the checks, the movement is real. Smooth it.
            dt = (now - self.last_update_timestamp) if self.last_update_timestamp else None
            filtered_x, filtered_y = self.position_filter.update(
                (float(x), float(y)),
                dt=dt
            )
            self.x = int(filtered_x)
            self.y = int(filtered_y)
        else:
            # Anchors or raw mode
            self.x = int(x)
            self.y = int(y)
            if self.position_filter:
                self.position_filter.reset()
        
        self.last_update_timestamp = now
        self.status = True

    def cal(self, anchors):
        """Calculate position based on ranges."""
        # Find which anchors have valid data (>0)
        count = 0
        anc_id_list = []
        for range_val in self.list:
            if range_val > 0:
                anc_id_list.append(count)
            count += 1

        # --- 3+ Anchors: Linear Least Squares (Standard High Accuracy) ---
        if len(anc_id_list) >= 3:
            anchor_positions = []
            anchor_ranges = []
            for anc_id in anc_id_list:
                anchor_positions.append((anchors[anc_id].x, anchors[anc_id].y))
                anchor_ranges.append(self.list[anc_id])
            
            ref_x, ref_y = anchor_positions[0]
            ref_r = anchor_ranges[0]
            A = []
            b = []
            
            for i in range(1, len(anchor_positions)):
                ax, ay = anchor_positions[i]
                r = anchor_ranges[i]
                A.append([2 * (ax - ref_x), 2 * (ay - ref_y)])
                b.append((ax**2 + ay**2 - ref_x**2 - ref_y**2) - (r**2 - ref_r**2))
            
            if len(A) >= 2:
                try:
                    result = np.linalg.lstsq(A, b, rcond=None)[0]
                    self.set_location(result[0], result[1])
                    return
                except Exception:
                    pass 

        # --- 2 Anchors: Circle Intersection (With Smart Selection) ---
        if len(anc_id_list) >= 2:
            a_id, b_id = anc_id_list[0], anc_id_list[1]
            x, y = self.three_point_uwb(anchors, a_id, b_id)
            self.set_location(x, y)

    def three_point_uwb(self, anchors, a_id, b_id):
        return self.three_point(
            anchors[a_id].x, anchors[a_id].y,
            anchors[b_id].x, anchors[b_id].y,
            self.list[a_id], self.list[b_id]
        )
    
    def three_point(self, x1, y1, x2, y2, r1, r2):
        d = math.sqrt((x2 - x1)**2 + (y2 - y1)**2)
        
        if d > r1 + r2 or d < abs(r1 - r2) or d == 0:
            ratio = r1 / (r1 + r2)
            return x1 + (x2 - x1) * ratio, y1 + (y2 - y1) * ratio

        a = (r1**2 - r2**2 + d**2) / (2 * d)
        h = math.sqrt(max(0, r1**2 - a**2))
        
        x0 = x1 + a * (x2 - x1) / d
        y0 = y1 + a * (y2 - y1) / d
        
        rx = -(y2 - y1) * (h / d)
        ry = (x2 - x1) * (h / d)
        
        px1 = x0 + rx
        py1 = y0 + ry
        px2 = x0 - rx
        py2 = y0 - ry

        # Smart Selection: Pick point closest to last known position
        score1 = 0
        score2 = 0
        
        if px1 >= 0 and py1 >= 0: score1 += 1
        if px2 >= 0 and py2 >= 0: score2 += 1
        
        if self.status:
            dist1 = (px1 - self.x)**2 + (py1 - self.y)**2
            dist2 = (px2 - self.x)**2 + (py2 - self.y)**2
            if dist1 < dist2: score1 += 2
            else: score2 += 2
            
        if score1 >= score2:
            return px1, py1
        else:
            return px2, py2