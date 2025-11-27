"""
Serial port communication for UWB tracking system
"""
import serial
import serial.tools.list_ports
import time
import threading
import math
from config import SERIAL_BAUDRATE, SERIAL_SLEEP_TIME


def get_first_com():
    """
    Find the first compatible serial port.
    Returns the port device name or None if not found.
    """
    port_list = serial.tools.list_ports.comports()
    for port in port_list:
        if ("usbserial" in port.device or 
            "usbmodem" in port.device or 
            "CH340" in port.description or 
            "wchusbserial" in port.device or 
            "1A86:7523" in port.hwid):
            print(f"Found compatible port: {port.device}")
            return port.device
    print("WARNING: No compatible serial port found.")
    return None


class SerialReader:
    """Handles serial communication and data parsing"""
    
    def __init__(self, anchors, tags, height_getter=None):
        """
        Initialize serial reader with references to anchors and tags.
        
        Args:
            anchors: List of UWB anchor objects
            tags: List of UWB tag objects
            height_getter: Function that returns (anchor_z_heights, tag_height) tuple
        """
        self.anchors = anchors
        self.tags = tags
        self.height_getter = height_getter
        self.ser = None
        self.running = False
        self.thread = None
    
    def convert_slant_to_horizontal(self, slant_range, anchor_z, tag_z):
        """
        Convert 3D slant range to 2D horizontal range using Pythagorean theorem.
        
        Args:
            slant_range: The 3D distance measurement from sensor (cm)
            anchor_z: Z-height of the anchor (cm)
            tag_z: Z-height of the tag (cm)
        
        Returns:
            Horizontal distance (cm), or 0 if slant_range < height_difference
        """
        height_difference = abs(anchor_z - tag_z)
        
        # Edge case: if sensor range is smaller than height difference (due to noise), force to 0
        if slant_range <= height_difference:
            return 0.0
        
        # Apply Pythagorean theorem: horizontal_distance = sqrt(slant_range^2 - height_difference^2)
        horizontal_distance = math.sqrt(slant_range**2 - height_difference**2)
        
        return horizontal_distance
        
    def connect(self):
        """Connect to the serial port"""
        port = get_first_com()
        if port:
            self.ser = serial.Serial(port, SERIAL_BAUDRATE)
            self.ser.write("begin".encode('UTF-8'))
            self.ser.reset_input_buffer()
            return True
        return False
    
    def read_data(self):
        """Read and parse a line of data from the serial port"""
        if not self.ser or not self.ser.is_open:
            return
            
        line = self.ser.readline().decode('UTF-8', errors='ignore').strip()
        if not line:
            return
            
        try:
            # Get current heights for 3D to 2D conversion
            anchor_z_heights = None
            tag_height = None
            if self.height_getter:
                try:
                    anchor_z_heights, tag_height = self.height_getter()
                except:
                    pass  # If height_getter fails, use raw ranges
            
            range_values = None
            
            if line.startswith("AT+RANGE="):
                start_index = line.find("range:(")
                if start_index == -1:
                    return
                end_index = line.find(")", start_index)
                if end_index == -1:
                    return
                ranges_str = line[start_index + len("range:("):end_index]
                range_values = [int(r) for r in ranges_str.split(',')]
            elif "nge:" in line:
                ranges = line.split("nge:(")[1].split(")")[0]
                range_values = [int(r) if r != "0" else 0 for r in ranges.split(",")]
            
            if range_values is not None:
                tid = 0
                if tid < len(self.tags):
                    # Update anchor and tag Z-heights from the height_getter
                    # The cal() function will do the conversion from slant to horizontal
                    if anchor_z_heights and tag_height is not None:
                        # Update anchor Z-heights
                        for i, height in enumerate(anchor_z_heights):
                            if i < len(self.anchors):
                                self.anchors[i].z = height
                        # Update tag Z-height
                        self.tags[tid].z = tag_height
                    
                    # Store raw ranges - cal() function will convert them using anchor.z and tag.z
                    self.tags[tid].list = range_values
                    
                    valid_ranges = [r for r in self.tags[tid].list if r > 0]
                    if len(valid_ranges) >= 3:
                        self.tags[tid].cal(self.anchors)
        except Exception as e:
            print(f"[ERROR] Failed to process line: '{line}', Error: {e}")
    
    def serial_loop(self):
        """Background thread function to continuously read serial data"""
        while self.running:
            self.read_data()
            time.sleep(SERIAL_SLEEP_TIME)
    
    def start(self):
        """Start the serial reading thread"""
        if self.connect():
            self.running = True
            self.thread = threading.Thread(target=self.serial_loop, daemon=True)
            self.thread.start()
            return True
        return False
    
    def stop(self):
        """Stop the serial reading thread"""
        self.running = False
        if self.ser and self.ser.is_open:
            self.ser.close()

