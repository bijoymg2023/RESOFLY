# Deployment Guide: Raspberry Pi

The current application is configured for **Development Mode** (running on a Mac/PC with simulated hardware).
To run this on a Raspberry Pi with real sensors (FLIR Lepton, GPS), follow these steps.

## 1. System Requirements
- Raspberry Pi 4 (Recommended)
- enabled I2C and SPI (Run `sudo raspi-config` -> Interface Options)

## 2. Dependencies
On the Raspberry Pi, you need to install hardware-specific libraries:

```bash
# System dependencies
sudo apt-get update
sudo apt-get install -y python3-opencv libatlas-base-dev

# Python dependencies
pip install pylepton flirpy  # For Thermal Camera
pip install picamera         # For RGB Camera (Legacy)
# OR for newer BullsEye/Bookworm OS:
pip install opencv-python-headless
```

## 3. Switching to Real Hardware

### A. Thermal Camera (FLIR Lepton)
1. Install dependencies: `pip install pylepton`
2. Edit `backend/server.py`.
3. Change the import at the top:

```python
# In server.py
# import camera  <-- Change this
import camera_real as camera 
```
That's it! The `camera_real.py` file is already prepared with `LeptonCamera` logic.

### B. System Temperature
1. In `backend/server.py`, find `get_system_status()`.
2. Uncomment the Pi-specific temperature reading lines.

### C. GPS Module
1. Install dependencies: `pip install pyserial pynmea2`
2. Connect your GPS via USB/UART.
3. Edit `backend/server.py`.
4. Import and use the `gps_real` module:

```python
# In server.py
import gps_real

# Initialize globally
gps_scanner = gps_real.GPSReader(port='/dev/ttyUSB0') # Check your port!
gps_scanner.start()

# In get_gps():
@api_router.get("/gps", response_model=GPSData)
async def get_gps():
    data = gps_scanner.get_data()
    return GPSData(**data)
```

## 4. Initial Setup & Build (One Time)
Since we want the Pi to run offline, we will build the frontend and serve it via Python.

```bash
# 1. Build the Frontend
cd thermo-vision-hub
npm install
npm run build

# 2. Check Backend
cd backend
pip install -r requirements.txt
# (Optional) Verify manually
python3 server.py 
# Visit http://<PI_IP>:8000 to see the app
```

## 5. Running on Boot (Systemd)

We have created a service file `resofly.service`.

1. Copy the service file:
   ```bash
   sudo cp resofly.service /etc/systemd/system/
   ```

2. Reload daemon:
   ```bash
   sudo systemctl daemon-reload
   ```

3. Enable and Start:
   ```bash
   sudo systemctl enable resofly.service
   sudo systemctl start resofly.service
   ```

4. Check Status:
   ```bash
   sudo systemctl status resofly.service
   ```

**The app is now running and will auto-start on boot.**
Access it at `http://<PI_IP>:8000`.
