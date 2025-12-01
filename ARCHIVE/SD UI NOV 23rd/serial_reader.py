"""
Serial port communication for UWB tracking system
"""
import serial
import serial.tools.list_ports
import time
import threading
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
    
    def __init__(self, anchors, tags):
        """
        Initialize serial reader with references to anchors and tags.
        
        Args:
            anchors: List of UWB anchor objects
            tags: List of UWB tag objects
        """
        self.anchors = anchors
        self.tags = tags
        self.ser = None
        self.running = False
        self.thread = None
        
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
            if line.startswith("AT+RANGE="):
                start_index = line.find("range:(")
                if start_index == -1:
                    return
                end_index = line.find(")", start_index)
                if end_index == -1:
                    return
                ranges_str = line[start_index + len("range:("):end_index]
                range_values = [int(r) for r in ranges_str.split(',')]
                tid = 0
                if tid < len(self.tags):
                    self.tags[tid].list = range_values
                    valid_ranges = [r for r in range_values if r > 0]
                    if len(valid_ranges) >= 3:
                        self.tags[tid].cal(self.anchors)
            elif "nge:" in line:
                ranges = line.split("nge:(")[1].split(")")[0]
                range_values = [int(r) if r != "0" else 0 for r in ranges.split(",")]
                tid = 0
                if tid < len(self.tags):
                    self.tags[tid].list = range_values
                    valid_ranges = [r for r in range_values if r > 0]
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

