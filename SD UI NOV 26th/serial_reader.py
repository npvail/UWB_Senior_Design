"""
Serial port communication for UWB tracking system
"""
import logging
import re
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


_LOGGER = logging.getLogger(__name__)
TAG_ID_PATTERN = re.compile(r'[Tt](\d+)')


class SerialReader:
    """Handles serial communication and data parsing"""
    
    def __init__(self, anchors, tags, on_update=None):
        """
        Initialize serial reader with references to anchors and tags.
        
        Args:
            anchors: List of UWB anchor objects
            tags: List of UWB tag objects
            on_update: Optional callback invoked after fresh data is processed
        """
        self.anchors = anchors
        self.tags = tags
        self.ser = None
        self.running = False
        self.thread = None
        self.on_update = on_update
        self._reconnect_delay = 2.0
        self._port_name = None

    def set_update_callback(self, callback):
        """Set or replace the callback used to notify listeners of new data."""
        self.on_update = callback
        
    def connect(self):
        """Connect to the serial port"""
        port = get_first_com()
        if not port:
            _LOGGER.warning("No serial port available for UWB reader.")
            return False

        try:
            self.ser = serial.Serial(port, SERIAL_BAUDRATE, timeout=1)
            self.ser.write("begin".encode('UTF-8'))
            self.ser.reset_input_buffer()
            self._port_name = port
            _LOGGER.info("Connected to serial port %s", port)
            return True
        except serial.SerialException as exc:
            _LOGGER.error("Failed to open serial port %s: %s", port, exc)
            self.ser = None
            return False

    def _close_serial(self):
        if self.ser:
            try:
                self.ser.close()
            except serial.SerialException:
                pass
        self.ser = None
        self._port_name = None
    
    def _extract_tag_id(self, line: str) -> int:
        match = TAG_ID_PATTERN.search(line)
        if match:
            try:
                tag_id = int(match.group(1))
                if 0 <= tag_id < len(self.tags):
                    return tag_id
            except ValueError:
                pass
        return 0

    def _handle_ranges(self, tid: int, range_values):
        if tid >= len(self.tags):
            return
        tag = self.tags[tid]
        tag.list = range_values
        valid_ranges = [r for r in range_values if r > 0]
        if len(valid_ranges) >= 3:
            tag.cal(self.anchors)
            if self.on_update:
                self.on_update()

    def read_data(self):
        """Read and parse a line of data from the serial port"""
        if not self.ser or not self.ser.is_open:
            return

        try:
            line = self.ser.readline().decode('UTF-8', errors='ignore').strip()
        except serial.SerialException as exc:
            _LOGGER.error("Serial read error: %s", exc)
            self._close_serial()
            return

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
                tid = self._extract_tag_id(line)
                self._handle_ranges(tid, range_values)
            elif "nge:" in line:
                ranges = line.split("nge:(")[1].split(")")[0]
                range_values = [int(r) if r != "0" else 0 for r in ranges.split(",")]
                tid = self._extract_tag_id(line)
                self._handle_ranges(tid, range_values)
        except Exception as e:
            _LOGGER.error("Failed to process line '%s': %s", line, e)
    
    def serial_loop(self):
        """Background thread function to continuously read serial data"""
        while self.running:
            if not self.ser or not self.ser.is_open:
                if not self.connect():
                    time.sleep(self._reconnect_delay)
                    continue
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
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=2)
        self._close_serial()

