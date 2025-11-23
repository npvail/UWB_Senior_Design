# UWB Tracking System

A modular Flask-based web application for tracking UWB (Ultra-Wideband) tags and anchors with zone management capabilities.

## Project Structure

```
.
├── app.py                 # Main Flask application entry point
├── config.py              # Configuration constants
├── uwb.py                 # UWB class for anchors and tags
├── serial_reader.py       # Serial communication handling
├── zone_manager.py        # Zone management logic
├── templates/
│   └── index.html         # Main HTML template
└── static/
    ├── style.css          # CSS styles
    └── script.js          # JavaScript client-side logic
```

## Module Descriptions

### `app.py`
Main Flask application that:
- Initializes UWB objects (anchors and tags)
- Sets up Flask routes for the web interface
- Manages zone operations (create, update, delete)
- Handles anchor and tag configuration
- Starts the serial reader thread

### `config.py`
Centralized configuration file containing:
- Color definitions
- UWB system configuration (anchor/tag counts)
- Anchor positions
- Map dimensions
- Serial port settings
- Flask server settings

### `uwb.py`
UWB class that represents anchors and tags:
- Position tracking with trilateration
- Position smoothing using history
- Distance calculations

### `serial_reader.py`
Handles serial port communication:
- Port detection and connection
- Data parsing from serial stream
- Background thread for continuous reading
- Integration with UWB objects

### `zone_manager.py`
Zone management system:
- Create, update, and delete zones
- Tag-zone intersection detection
- Alert generation for zone entries
- Thread-safe zone operations

### `templates/index.html`
Main web interface template with:
- Map canvas for visualization
- Sidebar with settings
- Zone management UI
- Anchor and tag controls

### `static/style.css`
All CSS styling for the web interface

### `static/script.js`
Client-side JavaScript for:
- Canvas drawing and rendering
- Real-time data updates
- Zone drawing and editing
- UI interactions

## Running the Application

1. Install required dependencies:
   ```bash
   pip install flask pyserial
   ```

2. Run the application:
   ```bash
   python app.py
   ```

3. Open your browser to:
   ```
   http://localhost:2405
   ```

## Features

- **Real-time Tracking**: Track UWB tags and anchors in real-time
- **Zone Management**: Create and manage zones with warnings and alerts
- **Map Visualization**: Visual representation of anchors, tags, and zones
- **Anchor Configuration**: Adjust anchor positions dynamically
- **Tag Management**: Rename tags for better identification
- **Zone Alerts**: Get alerts when tags enter defined zones

## Configuration

Edit `config.py` to modify:
- Number of anchors and tags
- Initial anchor positions
- Map dimensions
- Serial port settings
- Flask server host and port

## Dependencies

- Flask: Web framework
- pyserial: Serial port communication
- Standard Python libraries: threading, math, time

