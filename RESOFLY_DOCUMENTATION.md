# RESOFLY System Documentation

## 1. Project Overview
**RESOFLY** is an autonomous thermal vision hub designed for the Raspberry Pi. Is allows users to view live thermal video feeds, track GPS coordinates, and monitor system diagnostics remotely through a secure web dashboard.

**Key capabilities:**
*   **Live Thermal Streaming**: Real-time visualization of heat signatures via FLIR Lepton 3.5.
*   **GPS Tracking**: Real-time location data overlay.
*   **Plug & Play Automation**: Automatically boots, creates a secure internet tunnel, and emails the access link to the user without any manual intervention.
*   **Secure Dashboard**: Login-protected interface built with modern web technologies.

---

## 2. System Architecture

The system follows a classic **Client-Server** architecture, hosted entirely on the Raspberry Pi:

*   **Hardware Layer**: Raspberry Pi 4 + FLIR Lepton 3.5 + GPS Module.
*   **Backend (Python/FastAPI)**: Handles hardware drivers, image processing, and API requests.
*   **Frontend (React/Vite)**: Provides the visual user interface in the browser.
*   **Connectivity (Cloudflare)**: Exposes the local server to the open internet securely.

---

## 3. Backend (The Core)
Located in `/backend`, this is the brain of the operation.

### A. Main Server (`server.py`)
*   **Framework**: FastAPI (Python).
*   **Role**:
    *   Serves the React frontend static files.
    *   Provides API endpoints for `system-status`, `gps`, and `alerts`.
    *   Stream video via `/api/stream/thermal`.
    *   Handles JWT Authentication (Login/Security).
*   **Database**: Uses `thermo_vision.db` (SQLite) to store User accounts and Alerts.

### B. Camera Logic (`camera_real.py`)
*   **Role**: Interfaces with the hardware.
*   **Functionality**:
    *   Connects to the Lepton sensor logic.
    *   Captures raw 16-bit radiometric data.
    *   Converts raw data into an 8-bit visual heatmap (using OpenCV `applyColorMap`).
    *   Encodes images to JPEG for web streaming.

### C. GPS Logic (`gps_real.py`)
*   **Role**: Reads NMEA data from the USB GPS module.
*   **Library**: Uses `pyserial` and `pynmea2`.
*   **Functionality**: Runs in a background thread to constantly update Latitude, Longitude, and Speed without blocking the main server.

---

## 4. Frontend (The Interface)
Located in `/src`, this is a generic **Single Page Application (SPA)** built with React.

### A. Technology Stack
*   **React + TypeScript**: For Type-safe interface building.
*   **Vite**: Build tool for fast performance.
*   **Tailwind CSS**: For "Cyberpunk/Glassmorphism" styling.

### B. Key Components
*   **`ThermalDashboard.tsx`**: The main control center. Organizes the video, map, and charts into a grid.
*   **`VideoStreamBox.tsx`**: Displays the MJPEG stream from the backend. Handles "Connection Lost" states.
*   **`GPSCoordinateBox.tsx`**: Visualizes location data (Satellite count, Altitude, Speed).
*   **`AlertBox.tsx`**: Shows system warnings (e.g., "High Temp Detected").

---

## 5. Automation & Hosting ("Plug & Play")
This is the custom logic that makes the device autonomous.

### A. The Tunnel (`cloudflared`)
We use **Cloudflare Tunnel** to create a secure outbound connection. This bypasses firewalls and router configurations, giving the Pi a public URL (e.g., `https://random-name.trycloudflare.com`).

### B. Notification Bot (`monitor_tunnel.py`)
*   **Runs on**: Boot (Service).
*   **Logic**:
    1.  Watches the `tunnel.log` file file where Cloudflare writes its output.
    2.  Waits for a URL to appear.
    3.  Once found, it uses **SMTP (Gmail)** to send an email to everyone listed in `email_list.txt`.
    4.  It authenticates using a Google App Password for security.

### C. System Services (`setup_boot.sh`)
These are Linux `systemd` services that control the lifecycle:
1.  **`resofly.service`**: Starts the Python Web Server.
2.  **`resofly-tunnel.service`**: Starts the Cloudflare connection.
3.  **`resofly-notify.service`**: Starts the email bot.

---

## 6. Directory Structure
```text
thermo-vision-hub/
├── backend/                  # Python Logic
│   ├── .venv/               # Virtual Environment (Libraries)
│   ├── server.py            # Main API
│   ├── camera_real.py       # Camera Driver
│   ├── monitor_tunnel.py    # Email Notification Bot
│   ├── email_list.txt       # List of notification recipients
│   └── setup_boot.sh        # Installer for auto-start services
├── src/                      # React Frontend Code
│   ├── App.tsx              # Main Router
│   └── components/          # UI Widgets (Video, GPS, Alerts)
├── dist/                     # Compiled Frontend (what is actually served)
├── resofly.service           # Template service file
└── package.json              # Javascript dependencies
```
