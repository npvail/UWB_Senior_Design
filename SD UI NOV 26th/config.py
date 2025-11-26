"""
Configuration constants for UWB tracking system
"""
import socket

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
FLASK_PORT = 2406


def _resolve_default_admin_ips():
    ips = {'127.0.0.1', '::1', 'localhost'}
    
    try:
        # Get the local hostname
        hostname = socket.gethostname()
        ips.add(hostname)
        
        # Try to resolve hostname to IP
        host_ip = socket.gethostbyname(hostname)
        if host_ip and host_ip != '127.0.1.1':  # Skip loopback variants
            ips.add(host_ip)
    except socket.error:
        pass
    
    # Also try to get all addresses for the hostname
    try:
        hostname = socket.gethostname()
        addr_info = socket.getaddrinfo(hostname, None)
        for family, socktype, proto, canonname, sockaddr in addr_info:
            ip = sockaddr[0]
            # Add non-loopback IPs and avoid duplicates
            if ip and not ip.startswith('127.'):
                ips.add(ip)
    except socket.error:
        pass
    
    return ips


# Only these IP addresses can modify settings (others are read-only)
# By default this includes:
#   - 127.0.0.1, ::1, localhost
#   - The machine hostname
#   - All IPs resolved for this hostname on the current machine
ADMIN_IPS = _resolve_default_admin_ips()
