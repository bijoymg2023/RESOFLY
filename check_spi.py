#!/usr/bin/env python3
"""
SPI Check for FLIR Lepton 3.5
Tests basic SPI communication with the camera.
Step-by-step diagnostics to find where it hangs.
"""

import sys
import time

print("=" * 50)
print("  LEPTON SPI CHECK (Diagnostic Mode)")
print("=" * 50)

# Step 1: Check if spidev exists
print("[1/5] Checking for SPI device files...")
import os
if os.path.exists("/dev/spidev0.0"):
    print("      Found /dev/spidev0.0")
if os.path.exists("/dev/spidev0.1"):
    print("      Found /dev/spidev0.1 ✓")
else:
    print("      ERROR: /dev/spidev0.1 not found!")
    print("      Run: sudo raspi-config -> Interface Options -> SPI -> Enable")
    print("      Then reboot the Pi")
    sys.exit(1)

# Step 2: Import spidev
print("[2/5] Importing spidev module...")
try:
    import spidev
    print("      spidev imported ✓")
except ImportError:
    print("      ERROR: spidev not installed!")
    print("      Run: sudo apt install python3-spidev")
    sys.exit(1)

# Step 3: Create SpiDev object
print("[3/5] Creating SpiDev object...")
spi = spidev.SpiDev()
print("      SpiDev created ✓")

# Step 4: Open SPI port
print("[4/5] Opening SPI port 0.0 (CS0 - Pin 24)...")
sys.stdout.flush()
try:
    spi.open(0, 0)  # CS0 (CE0, Pin 24)
    print("      SPI opened ✓")
except Exception as e:
    print(f"      ERROR opening SPI: {e}")
    sys.exit(1)

# Step 5: Configure and test
print("[5/5] Configuring SPI (18 MHz, Mode 3)...")
try:
    spi.max_speed_hz = 10000000  # 10 MHz
    spi.mode = 0b11
    print("      SPI configured ✓")
except Exception as e:
    print(f"      ERROR configuring SPI: {e}")
    spi.close()
    sys.exit(1)

print("\n[TEST] Reading 5 packets from Lepton...")
sys.stdout.flush()

valid = 0
discard = 0
for i in range(5):
    try:
        packet = spi.readbytes(164)
        if (packet[0] & 0x0F) == 0x0F:
            discard += 1
            print(f"       Packet {i}: discard")
        else:
            valid += 1
            print(f"       Packet {i}: valid (num={packet[1]})")
    except Exception as e:
        print(f"       Packet {i}: ERROR - {e}")
    time.sleep(0.01)

spi.close()

print("\n" + "=" * 50)
if valid > 0:
    print("✓ SUCCESS: Lepton is responding!")
elif discard > 0:
    print("⚠ Lepton sending discard packets - needs warm-up time (2-3 min)")
else:
    print("✗ FAILED: Check wiring - MISO(21), CLK(23), CS(26)")
print("=" * 50)
