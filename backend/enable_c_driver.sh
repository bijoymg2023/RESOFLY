#!/bin/bash
# enable_c_driver.sh
# Switches from Python Soft-Sync to Robust C Hardware Driver

echo "=== Switching to C Driver ==="

# 1. Stop Services
echo "--> Stopping current service..."
sudo systemctl stop resofly
sudo killall v4l2lepton 2>/dev/null

# 2. Setup Video Device
echo "--> Loading Kernel Module..."
# Unload first to reset
sudo rmmod v4l2loopback 2>/dev/null
# Load with correct caps
sudo modprobe v4l2loopback video_nr=1 card_label="ThermalCam" exclusive_caps=1

if ! ls /dev/video1 >/dev/null 2>&1; then
    echo "ERROR: /dev/video1 failed to appear."
    exit 1
fi
echo "    [OK] /dev/video1 ready."

# 3. Start C Driver
echo "--> Starting Lepton C Driver..."
cd ../lepton_module/software/v4l2lepton || exit
# Run in background, logging to temp file
nohup ./v4l2lepton -v /dev/video1 > /tmp/lepton.log 2>&1 &
LEPTON_PID=$!

sleep 3
if ! ps -p $LEPTON_PID > /dev/null; then
    echo "ERROR: C Driver crashed."
    cat /tmp/lepton.log
    exit 1
fi
echo "    [OK] Driver running (PID $LEPTON_PID)."

# 4. Configure Backend
echo "--> Configuring Backend to use C Driver..."
SERVICE_FILE="/etc/systemd/system/resofly.service"

# Ensure CAMERA_SOURCE=1
if grep -q "CAMERA_SOURCE=" "$SERVICE_FILE"; then
    sudo sed -i 's/CAMERA_SOURCE=.*/CAMERA_SOURCE=1/' "$SERVICE_FILE"
else
    # Insert after Environment=PYTHONUNBUFFERED=1
    sudo sed -i '/Environment=PYTHONUNBUFFERED=1/a Environment=CAMERA_SOURCE=1' "$SERVICE_FILE"
fi

sudo systemctl daemon-reload

# 5. Restart
echo "--> Starting Server..."
sudo systemctl start resofly

echo "=== SUCCESS ==="
echo "The robust C driver is now feeding the dashboard."
echo "Check your dashboard link now."
