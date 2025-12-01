"""
UWB class for representing anchors and tags with positioning logic
"""
import math
import numpy as np
from config import RED, BLACK


class KalmanFilter2D:
    """2D Kalman Filter for position tracking"""
    
    def __init__(self, process_noise=0.1, measurement_noise=10.0):
        """
        Initialize Kalman filter for 2D position tracking.
        
        Args:
            process_noise: Process noise covariance (how much we expect position to change)
            measurement_noise: Measurement noise covariance (how much we trust measurements)
        """
        # State: [x, y, vx, vy] (position and velocity)
        self.state = np.zeros(4)  # [x, y, vx, vy]
        self.covariance = np.eye(4) * 100.0  # Initial uncertainty
        
        # Process noise (how much position can change)
        self.Q = np.eye(4) * process_noise
        
        # Measurement noise (how much we trust measurements)
        self.R = np.eye(2) * measurement_noise
        
        # State transition matrix (constant velocity model)
        dt = 0.5  # Time step (assuming 500ms updates)
        self.F = np.array([
            [1, 0, dt, 0],
            [0, 1, 0, dt],
            [0, 0, 1, 0],
            [0, 0, 0, 1]
        ])
        
        # Measurement matrix (we only observe position, not velocity)
        self.H = np.array([
            [1, 0, 0, 0],
            [0, 1, 0, 0]
        ])
        
        self.initialized = False
    
    def predict(self):
        """Predict next state"""
        if not self.initialized:
            return
        
        # Predict state
        self.state = self.F @ self.state
        
        # Predict covariance
        self.covariance = self.F @ self.covariance @ self.F.T + self.Q
    
    def update(self, measurement):
        """
        Update filter with new measurement.
        
        Args:
            measurement: [x, y] position measurement
        """
        measurement = np.array(measurement)
        
        if not self.initialized:
            # Initialize with first measurement
            self.state[0] = measurement[0]
            self.state[1] = measurement[1]
            self.state[2] = 0  # Initial velocity
            self.state[3] = 0
            self.initialized = True
            return
        
        # Predict first
        self.predict()
        
        # Calculate innovation (difference between measurement and prediction)
        y = measurement - self.H @ self.state
        
        # Innovation covariance
        S = self.H @ self.covariance @ self.H.T + self.R
        
        # Kalman gain
        K = self.covariance @ self.H.T @ np.linalg.inv(S)
        
        # Update state
        self.state = self.state + K @ y
        
        # Update covariance
        self.covariance = (np.eye(4) - K @ self.H) @ self.covariance
    
    def get_position(self):
        """Get current filtered position"""
        if not self.initialized:
            return None
        return (self.state[0], self.state[1])


class UWB:
    """Represents a UWB anchor or tag"""
    
    def __init__(self, name, type):
        self.name = name
        self.type = type
        self.x = 0
        self.y = 0
        self.status = False
        self.list = []
        
        # Smoothing state for tags (exponential moving average)
        self.smoothed_x = None
        self.smoothed_y = None
        self.smoothing_alpha = 0.4  # Smoothing factor (0-1): lower = more smoothing, higher = less smoothing
        
        # Kalman Filter for tags
        if self.type == 1:
            # Use adaptive measurement noise based on expected accuracy
            self.kalman = KalmanFilter2D(process_noise=0.5, measurement_noise=15.0)
        else:
            self.kalman = None
        
        # Movement tracking for outlier detection
        self.position_history = []  # Store last few smoothed positions
        self.max_history_size = 5  # Keep last 5 positions
        self.static_threshold = 5.0  # Tag is considered static if movement < 5 cm
        self.outlier_threshold_multiplier = 3.0  # Reject if jump > 3x recent max movement
        
        # Convergence tracking - detect when trilateration is consistently off
        self.raw_position_history = []  # Store recent raw trilateration results
        self.convergence_threshold = 30.0  # If raw positions consistently differ, increase responsiveness
        
        # Hybrid filtering: blend Kalman and EMA
        self.use_hybrid = True  # Enable hybrid filtering
        self.hybrid_weight_kalman = 0.6  # Weight for Kalman filter (0-1)
        self.hybrid_weight_ema = 0.4  # Weight for EMA

        if self.type == 1:
            self.color = RED
        else:
            self.color = BLACK

    def set_location(self, x, y, apply_smoothing=True):
        """
        Set the location and mark as active.
        
        Args:
            x: X coordinate
            y: Y coordinate
            apply_smoothing: If True and this is a tag, apply exponential moving average smoothing
        """
        # Apply smoothing only to tags and if enabled
        if self.type == 1 and apply_smoothing:
            if self.smoothed_x is None or self.smoothed_y is None:
                # First measurement - use raw value
                self.smoothed_x = float(x)
                self.smoothed_y = float(y)
                self.x = int(self.smoothed_x)
                self.y = int(self.smoothed_y)
                # Initialize position history with first position
                self.position_history = [(self.smoothed_x, self.smoothed_y)]
            else:
                # Store raw trilateration result for convergence detection
                self.raw_position_history.append((float(x), float(y)))
                if len(self.raw_position_history) > 5:
                    self.raw_position_history.pop(0)
                
                # Calculate distance from previous smoothed position (for smoothing)
                jump_distance = math.sqrt((x - self.smoothed_x)**2 + (y - self.smoothed_y)**2)
                
                # Calculate raw distance from last smoothed position (for movement detection)
                raw_jump_distance = jump_distance
                
                # Convergence detection: check if raw trilateration is consistently different from smoothed
                needs_convergence = False
                convergence_boost = 1.0
                was_reset = False
                convergence_error = 0.0
                
                if len(self.raw_position_history) >= 3:
                    # Calculate average of recent raw positions
                    avg_raw_x = sum(p[0] for p in self.raw_position_history) / len(self.raw_position_history)
                    avg_raw_y = sum(p[1] for p in self.raw_position_history) / len(self.raw_position_history)
                    
                    # Distance between average raw position and current smoothed position
                    convergence_error = math.sqrt((avg_raw_x - self.smoothed_x)**2 + (avg_raw_y - self.smoothed_y)**2)
                    
                    # If raw positions are consistently different from smoothed, increase responsiveness
                    if convergence_error > self.convergence_threshold:
                        needs_convergence = True
                        # Boost alpha by how much we need to converge (capped at reasonable value)
                        convergence_boost = min(1.0 + (convergence_error / self.convergence_threshold) * 0.5, 2.5)
                        
                        # If error is very large (likely systematic error), reset smoothing history
                        if convergence_error > 50:  # Very large error - reset smoothing
                            # Reset to use raw position more directly
                            self.smoothed_x = avg_raw_x
                            self.smoothed_y = avg_raw_y
                            # Keep some history but use new position
                            self.position_history = [(self.smoothed_x, self.smoothed_y)]
                            was_reset = True
                            # Recalculate jump distance after reset
                            jump_distance = math.sqrt((x - self.smoothed_x)**2 + (y - self.smoothed_y)**2)
                            raw_jump_distance = jump_distance
                
                # Detect if tag is static by analyzing recent movement in smoothed positions
                is_static = False
                recent_max_movement = 0.0
                
                if len(self.position_history) >= 2:
                    # Calculate maximum movement in recent smoothed history
                    movements = []
                    for i in range(len(self.position_history) - 1):
                        px, py = self.position_history[i]
                        nx, ny = self.position_history[i + 1]
                        move = math.sqrt((nx - px)**2 + (ny - py)**2)
                        movements.append(move)
                    
                    if movements:
                        recent_max_movement = max(movements)
                        avg_movement = sum(movements) / len(movements)
                        
                        # Tag is static if average movement is below threshold
                        is_static = avg_movement < self.static_threshold
                        
                        # Movement detection: if raw jump is large AND consistent, it's likely real movement
                        # Check if this is the start of actual movement (raw jump much larger than recent smoothed movement)
                        is_likely_movement = raw_jump_distance > 25 and raw_jump_distance > recent_max_movement * 2.5
                        
                        # Only apply outlier rejection if tag is truly static AND jump seems like noise
                        # Don't reject if it looks like the start of real movement OR if we need to converge
                        if is_static and not is_likely_movement and not needs_convergence:
                            # Outlier detection: if jump is much larger than recent movement, it's likely noise
                            outlier_threshold = max(self.static_threshold * self.outlier_threshold_multiplier, 
                                                  recent_max_movement * self.outlier_threshold_multiplier,
                                                  25.0)  # Minimum 25 cm threshold
                            if jump_distance > outlier_threshold:
                                # Reject outlier - don't update position, just keep previous smoothed value
                                # Tag is still active, so set status
                                self.status = True
                                return  # Exit without updating position
                        
                        # If movement is detected or convergence needed, reset static state
                        if is_likely_movement or needs_convergence:
                            is_static = False  # Override static state - tag is moving or needs to converge
                
                # Adaptive smoothing based on jump size and movement state
                # If we just reset due to large error, use very high alpha to converge quickly
                if was_reset:
                    # After reset, use high alpha to quickly converge to correct position
                    alpha = min(0.7 + (convergence_error / 100.0), 0.9)  # Very responsive after reset
                elif is_static:
                    # Tag is static - very aggressive smoothing to prevent jumps
                    if jump_distance > 30:  # Large jump when static - almost ignore it
                        alpha = 0.05  # Very aggressive - only 5% new value
                    elif jump_distance > 15:  # Medium jump when static
                        alpha = 0.1  # Aggressive smoothing
                    else:
                        alpha = 0.15  # Normal smoothing for static tag
                else:
                    # Tag is moving - use more responsive smoothing
                    # Apply convergence boost if needed
                    if needs_convergence:
                        # When convergence is needed, use more aggressive updates
                        if jump_distance > 50:
                            alpha = min(0.6 * convergence_boost, 0.8)  # Very responsive
                        elif jump_distance > 30:
                            alpha = min(0.5 * convergence_boost, 0.7)  # More responsive
                        else:
                            alpha = min(0.45 * convergence_boost, 0.65)  # Moderately responsive
                    else:
                        # Normal movement smoothing
                        if jump_distance > 80:  # Very large jump - likely start of movement
                            alpha = 0.5  # More responsive to capture movement start
                        elif jump_distance > 50:  # Large jump threshold (cm)
                            alpha = 0.35  # Moderate smoothing for large jumps
                        elif jump_distance > 30:  # Medium jump threshold
                            alpha = 0.4  # Normal smoothing for medium jumps
                        elif jump_distance > 15:  # Small-medium jump
                            alpha = 0.45  # Slightly less smoothing for smaller movements
                        else:
                            alpha = self.smoothing_alpha  # Normal smoothing (0.4)
                
                # Apply exponential moving average
                self.smoothed_x = alpha * x + (1 - alpha) * self.smoothed_x
                self.smoothed_y = alpha * y + (1 - alpha) * self.smoothed_y
                
                # Update Kalman filter with raw measurement
                if self.kalman is not None:
                    self.kalman.update([float(x), float(y)])
                    kalman_pos = self.kalman.get_position()
                    
                    if kalman_pos and self.use_hybrid:
                        # Hybrid filtering: blend Kalman and EMA
                        # Adjust weights based on movement state
                        if is_static:
                            # When static, trust Kalman more (better noise reduction)
                            k_weight = 0.7
                            e_weight = 0.3
                        else:
                            # When moving, use configured weights
                            k_weight = self.hybrid_weight_kalman
                            e_weight = self.hybrid_weight_ema
                        
                        # Blend Kalman and EMA results
                        final_x = k_weight * kalman_pos[0] + e_weight * self.smoothed_x
                        final_y = k_weight * kalman_pos[1] + e_weight * self.smoothed_y
                        
                        # Update smoothed values with hybrid result
                        self.smoothed_x = final_x
                        self.smoothed_y = final_y
                    elif kalman_pos:
                        # Use Kalman filter only
                        self.smoothed_x = kalman_pos[0]
                        self.smoothed_y = kalman_pos[1]
                
                # Update position history for movement tracking
                self.position_history.append((self.smoothed_x, self.smoothed_y))
                if len(self.position_history) > self.max_history_size:
                    self.position_history.pop(0)  # Remove oldest
                
                # Use smoothed values
                self.x = int(self.smoothed_x)
                self.y = int(self.smoothed_y)
        else:
            # No smoothing for anchors or if disabled
            self.x = x
            self.y = y
            if not apply_smoothing and self.type == 1:
                # Reset smoothing state when smoothing is disabled for tags
                self.smoothed_x = None
                self.smoothed_y = None
                # Reset Kalman filter
                if self.kalman is not None:
                    self.kalman = KalmanFilter2D(process_noise=0.5, measurement_noise=15.0)
        
        self.status = True

    def cal(self, anchors):
        """
        Calculate position using trilateration with multiple anchor pairs.
        Requires at least 3 valid anchor ranges.
        Uses improved trilateration that considers all anchors simultaneously.
        """
        count = 0
        anc_id_list = []
        for range_val in self.list:
            if range_val != 0:
                anc_id_list.append(count)
            count += 1
        
        if len(anc_id_list) >= 3:
            # Collect valid anchor positions and ranges
            anchor_positions = []
            anchor_ranges = []
            for anc_id in anc_id_list:
                anchor_positions.append((anchors[anc_id].x, anchors[anc_id].y))
                anchor_ranges.append(self.list[anc_id])
            
            # Use linear least squares trilateration (standard and most accurate method)
            # Subtract first anchor's equation from others to get linear system
            ref_x, ref_y = anchor_positions[0]
            ref_r = anchor_ranges[0]
            
            # Build linear system: 2*(xi-x0)*x + 2*(yi-y0)*y = (xi^2+yi^2-x0^2-y0^2) - (ri^2-r0^2)
            A = []
            b = []
            
            for i in range(1, len(anchor_positions)):
                ax, ay = anchor_positions[i]
                r = anchor_ranges[i]
                
                # Linear equation: 2*(ax-ref_x)*x + 2*(ay-ref_y)*y = (ax^2+ay^2-ref_x^2-ref_y^2) - (r^2-ref_r^2)
                A.append([
                    2 * (ax - ref_x),
                    2 * (ay - ref_y)
                ])
                b.append(
                    (ax**2 + ay**2 - ref_x**2 - ref_y**2) - (r**2 - ref_r**2)
                )
            
            # Solve the linear system directly - this is the most accurate method
            x, y = 0.0, 0.0  # Default fallback
            
            if len(A) >= 2:
                a11, a12 = A[0]
                a21, a22 = A[1]
                b1, b2 = b[0], b[1]
                
                det = a11 * a22 - a12 * a21
                if abs(det) > 1e-6:  # Avoid division by zero
                    x_ls = (b1 * a22 - b2 * a12) / det
                    y_ls = (a11 * b2 - a21 * b1) / det
                    
                    # Use linear least squares solution directly (most accurate)
                    if not (math.isnan(x_ls) or math.isnan(y_ls) or 
                           math.isinf(x_ls) or math.isinf(y_ls)):
                        x, y = x_ls, y_ls
                else:
                    # If determinant is zero, use fallback method
                    x1, y1 = anchor_positions[0]
                    x2, y2 = anchor_positions[1]
                    x3, y3 = anchor_positions[2]
                    r1, r2, r3 = anchor_ranges[0], anchor_ranges[1], anchor_ranges[2]
                    
                    p1a, p1b = self.get_intersection_points(x1, y1, x2, y2, r1, r2)
                    if p1a and p1b:
                        dist1 = math.sqrt((p1a[0] - x3)**2 + (p1a[1] - y3)**2)
                        dist2 = math.sqrt((p1b[0] - x3)**2 + (p1b[1] - y3)**2)
                        if abs(dist1 - r3) < abs(dist2 - r3):
                            x, y = p1a
                        else:
                            x, y = p1b
                    elif p1a:
                        x, y = p1a
            
            # Fine-tune with a few gradient descent iterations to account for measurement errors
            # But use very small steps to avoid diverging
            for iteration in range(5):
                grad_x, grad_y = 0.0, 0.0
                
                for (ax, ay), r in zip(anchor_positions, anchor_ranges):
                    dist = math.sqrt((x - ax)**2 + (y - ay)**2)
                    if dist > 0.001:  # Avoid division by zero
                        error = dist - r
                        # Gradient components (normalized by distance)
                        grad_x += error * (x - ax) / dist
                        grad_y += error * (y - ay) / dist
                
                # Very small learning rate for fine-tuning only
                learning_rate = 0.05 / (len(anchor_positions) * (iteration + 1))
                x -= learning_rate * grad_x
                y -= learning_rate * grad_y
            
            x = int(x)
            y = int(y)
            
            self.set_location(x, y)
            self.status = True

    def three_point_uwb(self, anchors, a_id, b_id):
        """Calculate position using two anchors"""
        return self.three_point(
            anchors[a_id].x, anchors[a_id].y,
            anchors[b_id].x, anchors[b_id].y,
            self.list[a_id], self.list[b_id]
        )
    
    def get_intersection_points(self, x1, y1, x2, y2, r1, r2):
        """
        Calculate both intersection points of two circles.
        Returns (point1, point2) where each point is (x, y) or None if circles don't intersect.
        """
        # Calculate distance between circle centers
        p2p = math.sqrt((x2 - x1)**2 + (y2 - y1)**2)
        
        # Handle edge cases
        if p2p == 0:
            return (None, None)  # Circles have same center
        
        # Check if circles intersect
        if r1 + r2 < p2p or abs(r1 - r2) > p2p:
            return (None, None)  # Circles don't intersect
        
        # Calculate the intersection point using proper circle-circle intersection formula
        # Distance from circle 1 center to the line perpendicular to the line connecting centers
        # that passes through the intersection points
        a = (r1**2 - r2**2 + p2p**2) / (2 * p2p)
        
        # Distance from the line connecting centers to the intersection points
        h_squared = r1**2 - a**2
        if h_squared < 0:
            # Handle floating point errors - circles are tangent
            h_squared = 0
        h = math.sqrt(h_squared)
        
        # Point on the line connecting centers that is perpendicular to intersection points
        p0_x = x1 + a * (x2 - x1) / p2p
        p0_y = y1 + a * (y2 - y1) / p2p
        
        # Perpendicular vector to the line connecting centers
        perp_x = -h * (y2 - y1) / p2p
        perp_y = h * (x2 - x1) / p2p
        
        # Two intersection points
        point1 = (p0_x + perp_x, p0_y + perp_y)
        point2 = (p0_x - perp_x, p0_y - perp_y) if h > 0 else None
        
        return (point1, point2)

    def three_point(self, x1, y1, x2, y2, r1, r2):
        """
        Trilateration calculation using two anchor points and distances.
        Returns calculated (x, y) position using proper circle-circle intersection.
        """
        # Calculate distance between anchors
        p2p = math.sqrt((x2 - x1)**2 + (y2 - y1)**2)
        
        # Handle edge cases
        if p2p == 0:
            return (x1, y1)  # Anchors are at same location
        
        # Check if circles intersect
        if r1 + r2 < p2p:
            # Circles don't intersect - place point on line between them
            temp_x = x1 + (x2 - x1) * r1 / (r1 + r2)
            temp_y = y1 + (y2 - y1) * r1 / (r1 + r2)
            return temp_x, temp_y
        
        if abs(r1 - r2) > p2p:
            # One circle is completely inside the other
            temp_x = x1 + (x2 - x1) * r1 / (r1 + r2)
            temp_y = y1 + (y2 - y1) * r1 / (r1 + r2)
            return temp_x, temp_y
        
        # Calculate the intersection point using proper circle-circle intersection formula
        # Distance from anchor 1 to the line perpendicular to the line connecting anchors
        # that passes through the intersection points
        a = (r1**2 - r2**2 + p2p**2) / (2 * p2p)
        
        # Distance from the line connecting anchors to the intersection points
        h_squared = r1**2 - a**2
        if h_squared < 0:
            h_squared = 0  # Handle floating point errors
        h = math.sqrt(h_squared)
        
        # Point on the line connecting anchors that is perpendicular to intersection points
        p0_x = x1 + a * (x2 - x1) / p2p
        p0_y = y1 + a * (y2 - y1) / p2p
        
        # Calculate the two possible intersection points
        # We choose the one that's more reasonable (typically the one further from origin if both anchors are in positive quadrant)
        # For now, we'll return the first intersection point and let averaging handle selection
        
        # Perpendicular vector to the line connecting anchors
        perp_x = -h * (y2 - y1) / p2p
        perp_y = h * (x2 - x1) / p2p
        
        # First intersection point
        temp_x = p0_x + perp_x
        temp_y = p0_y + perp_y
        
        return temp_x, temp_y

