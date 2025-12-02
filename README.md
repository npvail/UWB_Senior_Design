
# UWB Tracking System

A modular Flask-based web application for real-time tracking of UWB (Ultra-Wideband) tags. It features a live map visualization, zone-based alerting, and a persistent configuration system.

## 📋 Table of Contents
1. [Project Structure](#project-structure)
2. [Installation & Setup](#installation--setup)
3. [User Manual](#user-manual)
    - [The Interface](#1-the-interface)
    - [Map Configuration](#2-map-configuration)
    - [Anchor Setup (Calibration)](#3-anchor-setup-calibration)
    - [Zone Management](#4-zone-management)
    - [Tag Management](#5-tag-management)
4. [Technical Details](#technical-details)
5. [Troubleshooting](#troubleshooting)

---

## Project Structure

```text
.
├── app.py                 # Main Flask application entry point
├── config.py              # Configuration constants (IPs, serial settings)
├── uwb.py                 # UWB math (Trilateration & Kalman Filter)
├── serial_reader.py       # Serial communication handling
├── zone_manager.py        # Logic for zone alerts and intersections
├── state_store.py         # JSON persistence (Save/Load settings)
├── state.json             # (Generated) Stores your map/zone/anchor settings
├── templates/
│   └── index.html         # Main UI structure
└── static/
    ├── style.css          # Visual styling
    └── script.js          # Client-side logic (Canvas drawing, SocketIO)
```

---

## Installation & Setup

### 1. Prerequisites
*   **Python 3.9+**
*   **UWB Hardware** (Connected via USB)
*   **Drivers:**
    *   **macOS:** Install **CH34xVCPDriver** if using WCH-based serial chips.
    *   **Windows:** Ensure COM port drivers are installed.

### 2. Install Dependencies
This project uses `Flask-SocketIO` in **threading mode** (to avoid serial conflicts on macOS) and requires `simple-websocket`.

```bash
# Create virtual environment (optional but recommended)
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install required packages
pip install flask flask-socketio simple-websocket numpy pyserial
```

### 3. Run the Application
1.  Connect Anchor 0 to the USB port.
2.  Start the server:
    ```bash
    python app.py
    ```
3.  Open your browser to: `http://localhost:2406`

---

## 📖 User Manual

This system allows you to visualize tag locations on a custom floor plan. Access is split into **Admin** (Control) and **Viewer** (Read-only) modes based on your IP address.

### 1. The Interface
*   **The Map:** The large central area shows your floor plan.
    *   🔵 **Blue Dots:** Anchors (Fixed reference points).
    *   🔴 **Red Dots:** Tags (Moving objects).
    *   🔲 **Rectangles:** Safety Zones.
*   **Sidebar:** Click the **⚙️ Settings** button (top left) to open/close the control panel.

### 2. Map Configuration
Before tracking, set up your virtual environment to match the physical room.
1.  Open the **Map Settings** accordion in the sidebar.
2.  **Background Image:** Click "Select Background Image" to upload a `.png` or `.jpg` of your floor plan.
3.  **Tracking Area:** Enter the real-world **Width** and **Height** of your map in meters (e.g., 20.0m x 20.0m).
4.  Click **Save Area**.

### 3. Anchor Setup (Calibration)
*Critically important for accuracy.*
1.  Physically measure the location of your anchors in the room (in centimeters).
    *   *Example:* Anchor 0 is usually at `(0, 0)`. Anchor 1 might be at `(1357, 0)`.
2.  Open **Anchor Configuration** in the sidebar.
3.  Type the X and Y coordinates (in cm) for each Anchor ID.
4.  Click **Save Anchor Positions**.
    *   *Note:* The Blue dots on the map will move to the new positions.

### 4. Zone Management
You can draw virtual zones to trigger alerts when a tag enters them.
1.  Open **Zones** in the sidebar.
2.  **Drawing a Zone:**
    *   Click the **Draw Zone** button (it turns Red).
    *   Click and drag on the map to draw a rectangle.
    *   Release the mouse to finish.
3.  **Configuring the Zone:**
    *   **Name:** Give it a name (e.g., "Forklift Path").
    *   **Severity:**
        *   `WARNING` (Yellow): Minor alert.
        *   `ALERT` (Red): Critical safety violation (plays a sound).
    *   **Color:** Pick a color for the zone border.
    *   Click **Save** inside the zone form.
4.  **Editing:** Click "Edit" next to any zone in the list to resize or rename it.

### 5. Tag Management
1.  Open **Tag Management**.
2.  Select a Tag ID from the dropdown.
3.  Enter a friendly name (e.g., "Worker 1" or "Forklift A").
4.  Click **Rename Tag**.

---

## Technical Details

### Module Descriptions
*   **`app.py`**: The brain of the operation. It runs the Web Server, calculates coordinates from serial data, and pushes updates to the browser via WebSockets.
*   **`config.py`**: Edit this to change the `ADMIN_IPS` whitelist or default `ANC_COUNT` (Anchor count).
*   **`uwb.py`**: Contains the math.
    *   **Trilateration:** Uses Linear Least Squares (if 3+ anchors) or Circle Intersection (if 2 anchors) to find X/Y.
    *   **Kalman Filter:** Smooths the movement to prevent "jittery" dots.
*   **`serial_reader.py`**: Auto-detects USB ports (`/dev/cu.*` or `COM*`) and reads the raw distance data.
*   **`state_store.py`**: Automatically saves your map size, zones, and anchor positions to `state.json` so you don't lose data when restarting the server.

### Persistence
The system creates a file named `state.json` in the root folder. If you ever need to "Factory Reset" the map, simply delete this file and restart the server.

---

## Troubleshooting

### 1. "AssertionError: write() before start_response"
*   **Cause:** You are running Flask-SocketIO in threading mode without the WebSocket handler.
*   **Fix:** Install the missing package:
    ```bash
    pip install simple-websocket
    ```

### 2. "No compatible serial port found"
*   **Check 1:** Is the USB cable connected?
*   **Check 2 (Mac):** Did you click "Allow" on the "Allow accessory to connect" popup?
*   **Check 3:** Verify drivers. Run `ls /dev/cu.*` in terminal. You should see `cu.wchusbserial...` or similar.

### 3. The Map is Empty / No Data
*   **Cause:** The serial reader might be connected but the Tag is not seeing enough Anchors.
*   **Check:** Look at the terminal logs.
    *   If you see `Range to ANC 0: 150`, but no other anchors, the math cannot calculate an X/Y position.
    *   **Fix:** Move the tag closer to at least 2 anchors.

### 4. Admin controls are disabled (Read-Only)
*   **Cause:** Your device's IP address is not in the `ADMIN_IPS` list in `config.py`.
*   **Fix:**
    1.  Check the server logs for: `WARNING: Non-admin access attempt from: 192.168.x.x`.
    2.  Copy that IP.
    3.  Add it to `ADMIN_IPS` in `config.py`.
    4.  Restart the server.


Update the frist_get_com() function in position.py to be able run on MAC

Need install driver on MAC OS: 
https://www.wch-ic.com/downloads/CH341SER_MAC_ZIP.html

download -> setting -> general -> login & extention -> allow driver extention 

cmd to check the port number: 
ls /dev/cu.*

check data format, sometime it is unrecognize format

make sure use the hardware left port for power, right port uploads code

uncommend the anchor 4 in main function

create this python script into an app(.exe) using pyinstaller
1.pip install pyinstaller
2.pyinstaller --onefile --windowed app.py

note: run "pyinstaller --clean --onefile --windowed app.py" again if we modify/debug code "--clean" overwrite the privious version

if we have more than 1 file like seperated CSS, html, ...: use --add-data "<source>:<destination>", note: update function "def resource_path(relative_path)"
On MacOS/Linux: 
pyinstaller --onefile --windowed \
--add-data "templates:templates" \
--add-data "static:static" \
app.py

On Window: replace ":" to ";"

