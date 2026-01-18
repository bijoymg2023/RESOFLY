#!/bin/bash
# Rebuild the Lepton C++ Module
# MUST be run on the Raspberry Pi

set -e

echo "Starting Lepton C++ Build Process..."

# 1. Navigate to the directory
cd "$(dirname "$0")/Raspberry-Pi-FLIR-Lepton-Thermal-Imaging-Camera/LeptonModule/software/raspberrypi_video"

echo "Current Directory: $PWD"

# 2. Clean previous build
echo "Cleaning..."
if [ -f Makefile ]; then
    make clean || true
fi
rm -f raspberrypi_video
rm -f .qmake.stash

# 3. Compile
echo "Compiling (this may take a few minutes)..."
qmake
make -j4

# 4. Success Check
if [ -f raspberrypi_video ]; then
    echo "SUCCESS: Binary 'raspberrypi_video' created."
    echo "You can now restart the service."
    echo "sudo systemctl restart lepton-view.service"
else
    echo "ERROR: Compilation failed. Binary not found."
    exit 1
fi
