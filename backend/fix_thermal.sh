#!/bin/bash

# fix_thermal.sh
# ---------------------------------------------------------
# This script robustly sets up the Thermal Camera for ResoFly
# 1. Loads the virtual video cable driver (v4l2loopback)
# 2. Compiles the Lepton driver (v4l2lepton)
# 3. Starts the driver
# 4. Restarts the website
# ---------------------------------------------------------

GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${GREEN}=== ResoFly Thermal Camera Fix ===${NC}"

# 1. SETUP VIDEO DEVICE
echo "--> Checking Video Driver..."
if ! ls /dev/video1 >/dev/null 2>&1; then
    echo "    /dev/video1 missing. Loading loopback driver..."
    if ! sudo modprobe v4l2loopback video_nr=1 card_label="ThermalCam" exclusive_caps=1; then
        echo -e "${RED}    Failed to load driver! Installing package...${NC}"
        sudo apt-get update
        sudo apt-get install -y v4l2loopback-dkms v4l2loopback-utils
        sudo modprobe v4l2loopback video_nr=1 card_label="ThermalCam" exclusive_caps=1
    fi
    
    # Check again
    if ls /dev/video1 >/dev/null 2>&1; then
        echo -e "${GREEN}    [OK] /dev/video1 created.${NC}"
    else
        echo -e "${RED}    [FAIL] Could not create /dev/video1. Reboot and try again.${NC}"
        exit 1
    fi
else
    echo -e "${GREEN}    [OK] /dev/video1 exists.${NC}"
fi

# 2. BUILD DRIVER
echo "--> Building Camera Driver..."
cd ../lepton_module/software/v4l2lepton || exit
make clean >/dev/null 2>&1
if make; then
    echo -e "${GREEN}    [OK] Driver compiled.${NC}"
else
    echo -e "${RED}    [FAIL] Compilation failed.${NC}"
    exit 1
fi

# 3. START DRIVER
echo "--> Starting Camera Driver..."
killall v4l2lepton >/dev/null 2>&1
./v4l2lepton -v /dev/video1 > /dev/null 2>&1 &

sleep 2
if pgrep v4l2lepton >/dev/null; then
    echo -e "${GREEN}    [OK] Driver is running (PID $(pgrep v4l2lepton)).${NC}"
else
    echo -e "${RED}    [FAIL] Driver crashed immediately. Check wiring!${NC}"
    # Try creating a log
    ./v4l2lepton -v /dev/video1 &
    exit 1
fi

# 4. CONFIGURE & RESTART SERVER
echo "--> Config & Restart Server..."
# Force Config
sudo sed -i 's/CAMERA_SOURCE=.*/CAMERA_SOURCE=1/' /etc/systemd/system/resofly.service
if ! grep -q "CAMERA_SOURCE=1" /etc/systemd/system/resofly.service; then
    # If not found to replace, append it
    sudo sed -i '/Environment=PYTHONUNBUFFERED=1/a Environment=CAMERA_SOURCE=1' /etc/systemd/system/resofly.service
fi

sudo systemctl daemon-reload
sudo systemctl restart resofly

echo -e "${GREEN}=== DONE! ===${NC}"
echo "Please check the Dashboard now."
