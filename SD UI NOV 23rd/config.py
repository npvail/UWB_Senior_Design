"""
Configuration constants for UWB tracking system
"""

# Color definitions (used for data, not display)
RED = [255, 0, 0]
BLACK = [255, 255, 255]  # Changed to white for better contrast if needed

# UWB System Configuration
ANC_COUNT = 3
TAG_COUNT = 1

# Anchor positions (in cm)
A0X, A0Y = 0, 0
A1X, A1Y = 1357, 0
A2X, A2Y = 0, 1340

# Map dimensions (in cm)
MAP_WIDTH_CM = 2000
MAP_HEIGHT_CM = 2000

# Serial port configuration
SERIAL_BAUDRATE = 115200
SERIAL_SLEEP_TIME = 0.01  # Delay in seconds between serial reads

# Flask configuration
FLASK_HOST = '0.0.0.0'
FLASK_PORT = 2405

