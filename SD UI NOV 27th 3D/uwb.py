"""
UWB class for representing anchors and tags with positioning logic
"""
import math
import numpy as np
from config import RED, BLACK


class KalmanFilter2D:
    """2D Kalman Filter for position tracking"""
    
    def __init__(self, process_noise=0.1, measurement_noise=10.0):
        # State: [x, y, vx, vy] (position and velocity)
        self.state = np.zeros(4)
        self.covariance = np.eye(4) * 100.0
        self.Q = np.eye(4) * process_noise
        self.R = np.eye(2) * measurement_noise
        dt = 0.5
        self.F = np.array([
            [1, 0, dt, 0],
            [0, 1, 0, dt],
            [0, 0, 1, 0],
            [0, 0, 0, 1]
        ])
        self.H = np.array([
            [1, 0, 0, 0],
            [0, 1, 0, 0]
        ])
        self.initialized = False
    
    def predict(self):
        if not self.initialized: return
        self.state = self.F @ self.state
        self.covariance = self.F @ self.covariance @ self.F.T + self.Q
    
    def update(self, measurement):
        measurement = np.array(measurement)
        if not self.initialized:
            self.state[0] = measurement[0]
            self.state[1] = measurement[1]
            self.state[2] = 0
            self.state[3] = 0
            self.initialized = True
            return
        self.predict()
        y = measurement - self.H @ self.state
        S = self.H @ self.covariance @ self.H.T + self.R
        K = self.covariance @ self.H.T @ np.linalg.inv(S)
        self.state = self.state + K @ y
        self.covariance = (np.eye(4) - K @ self.H) @ self.covariance
    
    def get_position(self):
        if not self.initialized: return None
        return (self.state[0], self.state[1])


class UWB:
    """Represents a UWB anchor or tag"""
    
    def __init__(self, name, type):
        self.name = name
        self.type = type
        self.x = 0
        self.y = 0
        self.z = 0.0  # Height initialized to 0
        self.status = False
        self.list = []
        
        # Smoothing variables
        self.smoothed_x = None
        self.smoothed_y = None
        self.smoothing_alpha = 0.4
        self.position_history = []
        self.max_history_size = 5
        self.static_threshold = 5.0
        self.outlier_threshold_multiplier = 3.0
        self.raw_position_history = []
        self.convergence_threshold = 30.0
        self.use_hybrid = True
        self.hybrid_weight_kalman = 0.6
        self.hybrid_weight_ema = 0.4

        if self.type == 1:
            self.kalman = KalmanFilter2D(process_noise=0.5, measurement_noise=15.0)
            self.color = RED
        else:
            self.kalman = None
            self.color = BLACK

    def set_location(self, x, y, apply_smoothing=True):
        if self.type == 1 and apply_smoothing:
            if self.smoothed_x is None or self.smoothed_y is None:
                self.smoothed_x = float(x)
                self.smoothed_y = float(y)
                self.x = int(self.smoothed_x)
                self.y = int(self.smoothed_y)
                self.position_history = [(self.smoothed_x, self.smoothed_y)]
            else:
                self.raw_position_history.append((float(x), float(y)))
                if len(self.raw_position_history) > 5:
                    self.raw_position_history.pop(0)
                
                jump_distance = math.sqrt((x - self.smoothed_x)**2 + (y - self.smoothed_y)**2)
                raw_jump_distance = jump_distance
                needs_convergence = False
                convergence_boost = 1.0
                was_reset = False
                convergence_error = 0.0
                
                if len(self.raw_position_history) >= 3:
                    avg_raw_x = sum(p[0] for p in self.raw_position_history) / len(self.raw_position_history)
                    avg_raw_y = sum(p[1] for p in self.raw_position_history) / len(self.raw_position_history)
                    convergence_error = math.sqrt((avg_raw_x - self.smoothed_x)**2 + (avg_raw_y - self.smoothed_y)**2)
                    
                    if convergence_error > self.convergence_threshold:
                        needs_convergence = True
                        convergence_boost = min(1.0 + (convergence_error / self.convergence_threshold) * 0.5, 2.5)
                        if convergence_error > 50:
                            self.smoothed_x = avg_raw_x
                            self.smoothed_y = avg_raw_y
                            self.position_history = [(self.smoothed_x, self.smoothed_y)]
                            was_reset = True
                            jump_distance = math.sqrt((x - self.smoothed_x)**2 + (y - self.smoothed_y)**2)
                            raw_jump_distance = jump_distance
                
                is_static = False
                recent_max_movement = 0.0
                if len(self.position_history) >= 2:
                    movements = []
                    for i in range(len(self.position_history) - 1):
                        px, py = self.position_history[i]
                        nx, ny = self.position_history[i + 1]
                        movements.append(math.sqrt((nx - px)**2 + (ny - py)**2))
                    
                    if movements:
                        recent_max_movement = max(movements)
                        avg_movement = sum(movements) / len(movements)
                        is_static = avg_movement < self.static_threshold
                        is_likely_movement = raw_jump_distance > 25 and raw_jump_distance > recent_max_movement * 2.5
                        
                        if is_static and not is_likely_movement and not needs_convergence:
                            outlier_threshold = max(self.static_threshold * self.outlier_threshold_multiplier, 
                                                  recent_max_movement * self.outlier_threshold_multiplier, 25.0)
                            if jump_distance > outlier_threshold:
                                self.status = True
                                return

                        if is_likely_movement or needs_convergence:
                            is_static = False
                
                if was_reset:
                    alpha = min(0.7 + (convergence_error / 100.0), 0.9)
                elif is_static:
                    if jump_distance > 30: alpha = 0.05
                    elif jump_distance > 15: alpha = 0.1
                    else: alpha = 0.15
                else:
                    if needs_convergence:
                        if jump_distance > 50: alpha = min(0.6 * convergence_boost, 0.8)
                        elif jump_distance > 30: alpha = min(0.5 * convergence_boost, 0.7)
                        else: alpha = min(0.45 * convergence_boost, 0.65)
                    else:
                        if jump_distance > 80: alpha = 0.5
                        elif jump_distance > 50: alpha = 0.35
                        elif jump_distance > 30: alpha = 0.4
                        elif jump_distance > 15: alpha = 0.45
                        else: alpha = self.smoothing_alpha
                
                self.smoothed_x = alpha * x + (1 - alpha) * self.smoothed_x
                self.smoothed_y = alpha * y + (1 - alpha) * self.smoothed_y
                
                if self.kalman is not None:
                    self.kalman.update([float(x), float(y)])
                    kalman_pos = self.kalman.get_position()
                    if kalman_pos and self.use_hybrid:
                        if is_static:
                            k_weight, e_weight = 0.7, 0.3
                        else:
                            k_weight, e_weight = self.hybrid_weight_kalman, self.hybrid_weight_ema
                        self.smoothed_x = k_weight * kalman_pos[0] + e_weight * self.smoothed_x
                        self.smoothed_y = k_weight * kalman_pos[1] + e_weight * self.smoothed_y
                    elif kalman_pos:
                        self.smoothed_x, self.smoothed_y = kalman_pos
                
                self.position_history.append((self.smoothed_x, self.smoothed_y))
                if len(self.position_history) > self.max_history_size: self.position_history.pop(0)
                
                self.x = int(self.smoothed_x)
                self.y = int(self.smoothed_y)
        else:
            self.x = x
            self.y = y
            if not apply_smoothing and self.type == 1:
                self.smoothed_x = None
                self.smoothed_y = None
                if self.kalman is not None:
                    self.kalman = KalmanFilter2D(process_noise=0.5, measurement_noise=15.0)
        
        self.status = True

    def cal(self, anchors):
        """
        Calculate position using trilateration with HEIGHT CORRECTION.
        """
        count = 0
        anc_id_list = []
        for range_val in self.list:
            if range_val != 0:
                anc_id_list.append(count)
            count += 1
        
        if len(anc_id_list) >= 3:
            anchor_positions = []
            anchor_ranges = []
            
            # --- START CORRECTED LOOP ---
            for anc_id in anc_id_list:
                # 1. Get Coordinates of this Anchor
                ax = anchors[anc_id].x
                ay = anchors[anc_id].y
                az = anchors[anc_id].z  # Get Anchor Height
                
                # 2. Get Raw Distance from Sensor
                raw_range = self.list[anc_id]
                
                # 3. Calculate Height Difference (Anchor Height - Tag Height)
                height_diff = abs(az - self.z)
                
                # 4. Calculate Corrected Ground Distance (Pythagorean)
                ground_dist = 0.0
                if raw_range > height_diff:
                    ground_dist = math.sqrt(raw_range**2 - height_diff**2)
                else:
                    ground_dist = 0.0
                
                # 5. Store ONLY the corrected 2D data
                anchor_positions.append((ax, ay))
                anchor_ranges.append(ground_dist)
            # --- END CORRECTED LOOP ---
            
            # The rest of the calculation uses the 'anchor_ranges' we just corrected
            
            ref_x, ref_y = anchor_positions[0]
            ref_r = anchor_ranges[0]
            
            A = []
            b = []
            
            for i in range(1, len(anchor_positions)):
                ax, ay = anchor_positions[i]
                r = anchor_ranges[i]
                A.append([2 * (ax - ref_x), 2 * (ay - ref_y)])
                b.append((ax**2 + ay**2 - ref_x**2 - ref_y**2) - (r**2 - ref_r**2))
            
            x, y = 0.0, 0.0
            
            if len(A) >= 2:
                a11, a12 = A[0]
                a21, a22 = A[1]
                b1, b2 = b[0], b[1]
                det = a11 * a22 - a12 * a21
                
                if abs(det) > 1e-6:
                    x_ls = (b1 * a22 - b2 * a12) / det
                    y_ls = (a11 * b2 - a21 * b1) / det
                    if not (math.isnan(x_ls) or math.isnan(y_ls) or math.isinf(x_ls) or math.isinf(y_ls)):
                        x, y = x_ls, y_ls
                else:
                    # Fallback
                    x1, y1 = anchor_positions[0]
                    x2, y2 = anchor_positions[1]
                    x3, y3 = anchor_positions[2]
                    r1, r2, r3 = anchor_ranges[0], anchor_ranges[1], anchor_ranges[2]
                    p1a, p1b = self.get_intersection_points(x1, y1, x2, y2, r1, r2)
                    if p1a and p1b:
                        dist1 = math.sqrt((p1a[0] - x3)**2 + (p1a[1] - y3)**2)
                        dist2 = math.sqrt((p1b[0] - x3)**2 + (p1b[1] - y3)**2)
                        if abs(dist1 - r3) < abs(dist2 - r3): x, y = p1a
                        else: x, y = p1b
                    elif p1a: x, y = p1a
            
            # Gradient descent fine-tuning
            for iteration in range(5):
                grad_x, grad_y = 0.0, 0.0
                for (ax, ay), r in zip(anchor_positions, anchor_ranges):
                    dist = math.sqrt((x - ax)**2 + (y - ay)**2)
                    if dist > 0.001:
                        error = dist - r
                        grad_x += error * (x - ax) / dist
                        grad_y += error * (y - ay) / dist
                learning_rate = 0.05 / (len(anchor_positions) * (iteration + 1))
                x -= learning_rate * grad_x
                y -= learning_rate * grad_y
            
            x = int(x)
            y = int(y)
            self.set_location(x, y)
            self.status = True

    def three_point_uwb(self, anchors, a_id, b_id):
        # NOTE: This uses raw ranges. For production, apply Z correction here too if strictly needed.
        return self.three_point(
            anchors[a_id].x, anchors[a_id].y,
            anchors[b_id].x, anchors[b_id].y,
            self.list[a_id], self.list[b_id]
        )
    
    def get_intersection_points(self, x1, y1, x2, y2, r1, r2):
        p2p = math.sqrt((x2 - x1)**2 + (y2 - y1)**2)
        if p2p == 0: return (None, None)
        if r1 + r2 < p2p or abs(r1 - r2) > p2p: return (None, None)
        
        a = (r1**2 - r2**2 + p2p**2) / (2 * p2p)
        h_squared = r1**2 - a**2
        if h_squared < 0: h_squared = 0
        h = math.sqrt(h_squared)
        
        p0_x = x1 + a * (x2 - x1) / p2p
        p0_y = y1 + a * (y2 - y1) / p2p
        perp_x = -h * (y2 - y1) / p2p
        perp_y = h * (x2 - x1) / p2p
        
        point1 = (p0_x + perp_x, p0_y + perp_y)
        point2 = (p0_x - perp_x, p0_y - perp_y) if h > 0 else None
        return (point1, point2)

    def three_point(self, x1, y1, x2, y2, r1, r2):
        p2p = math.sqrt((x2 - x1)**2 + (y2 - y1)**2)
        if p2p == 0: return (x1, y1)
        if r1 + r2 < p2p:
            temp_x = x1 + (x2 - x1) * r1 / (r1 + r2)
            temp_y = y1 + (y2 - y1) * r1 / (r1 + r2)
            return temp_x, temp_y
        if abs(r1 - r2) > p2p:
            temp_x = x1 + (x2 - x1) * r1 / (r1 + r2)
            temp_y = y1 + (y2 - y1) * r1 / (r1 + r2)
            return temp_x, temp_y
        
        a = (r1**2 - r2**2 + p2p**2) / (2 * p2p)
        h_squared = r1**2 - a**2
        if h_squared < 0: h_squared = 0
        h = math.sqrt(h_squared)
        
        p0_x = x1 + a * (x2 - x1) / p2p
        p0_y = y1 + a * (y2 - y1) / p2p
        perp_x = -h * (y2 - y1) / p2p
        perp_y = h * (x2 - x1) / p2p
        
        temp_x = p0_x + perp_x
        temp_y = p0_y + perp_y
        return temp_x, temp_y