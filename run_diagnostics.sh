#!/bin/bash
# run_diagnostics.sh
# Run this on the Pi to check why the camera isn't working

echo "=========================================="
echo "       RESOFLY DIAGNOSTIC TOOL            "
echo "=========================================="

echo "[1] Checking SPI Devices..."
if ls /dev/spidev* 1> /dev/null 2>&1; then
    echo "    OK: SPI devices found."
    ls -l /dev/spidev*
else
    echo "    ERROR: No SPI devices found (/dev/spidev*)."
    echo "    ACTION: Run 'sudo raspi-config', enable SPI, and reboot."
fi

echo ""
echo "[2] Checking Binary..."
BIN_PATH="/home/team13/RESOFLY/Raspberry-Pi-FLIR-Lepton-Thermal-Imaging-Camera/LeptonModule/software/raspberrypi_video/raspberrypi_video"
if [ -f "$BIN_PATH" ]; then
    echo "    OK: Binary exists."
else
    echo "    ERROR: Binary not found!"
    echo "    ACTION: Run './build_lepton.sh' to compile it."
fi

echo ""
echo "[3] Checking Service Status..."
SERVICE_STATUS=$(systemctl is-active lepton-view.service)
echo "    Status: $SERVICE_STATUS"
if [ "$SERVICE_STATUS" != "active" ]; then
    echo "    ERROR: Service is NOT active."
else
    echo "    OK: Service is running."
fi

echo ""
echo "[4] Checking Ports (Is 8080 open?)..."
if sudo netstat -tulpn | grep 8080; then
    echo "    OK: Port 8080 is listening."
else
    echo "    ERROR: Nothing listening on port 8080."
fi

echo ""
echo "[5] Last 30 lines of service logs:"
sudo journalctl -u lepton-view.service -n 30 --no-pager

echo "=========================================="
