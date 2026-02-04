#!/usr/bin/env python3
"""
Deep SPI Diagnostic for FLIR Lepton 3.5
Checks for hardware issues when camera only outputs discard packets.
"""

import sys
import time
import os

print("=" * 60)
print("  LEPTON DEEP DIAGNOSTIC")
print("=" * 60)

# Check SPI device
print("\n[1] SPI Device Check...")
if not os.path.exists("/dev/spidev0.0"):
    print("   ✗ /dev/spidev0.0 NOT FOUND - Enable SPI in raspi-config!")
    sys.exit(1)
print("   ✓ /dev/spidev0.0 exists")

# Import and open SPI
import spidev
spi = spidev.SpiDev()
spi.open(0, 0)  # CS0, Pin 24
spi.max_speed_hz = 10000000
spi.mode = 0b11
print("   ✓ SPI opened at 10 MHz, Mode 3")

# Read lots of packets and analyze
print("\n[2] Reading 200 packets (takes ~2 seconds)...")
sys.stdout.flush()

discard_count = 0
valid_count = 0
all_ff_count = 0
all_00_count = 0
unique_bytes = set()

for i in range(200):
    packet = spi.readbytes(164)
    
    # Check packet type
    id_nibble = packet[0] & 0x0F
    if id_nibble == 0x0F:
        discard_count += 1
    else:
        valid_count += 1
    
    # Check if all 0xFF (no connection on MISO)
    if all(b == 0xFF for b in packet):
        all_ff_count += 1
    
    # Check if all 0x00 (stuck low)
    if all(b == 0x00 for b in packet):
        all_00_count += 1
    
    # Track unique bytes seen
    unique_bytes.update(packet)
    
    time.sleep(0.01)

spi.close()

print(f"\n[3] Results:")
print(f"   Valid packets:    {valid_count}")
print(f"   Discard packets:  {discard_count}")
print(f"   All-0xFF packets: {all_ff_count}")
print(f"   All-0x00 packets: {all_00_count}")
print(f"   Unique byte values seen: {len(unique_bytes)}")

print("\n[4] Diagnosis:")

if all_ff_count > 150:
    print("   ✗ PROBLEM: MISO line not connected or broken!")
    print("   → Check: MISO wire from breakout to Pi Pin 21 (GPIO 9)")
    
elif all_00_count > 150:
    print("   ✗ PROBLEM: MISO stuck LOW - possible short or no power!")
    print("   → Check: VIN power to breakout (3.3V or 5V)")
    print("   → Check: GND connection")

elif valid_count == 0 and discard_count == 200:
    if len(unique_bytes) < 5:
        print("   ✗ PROBLEM: Camera not responding properly")
        print("   → Possible causes:")
        print("      - Power issue (check VIN/GND)")
        print("      - CLK not connected (Pin 23)")
        print("      - Camera module damaged")
    else:
        print("   ⚠ Camera responding but never syncing")
        print("   → Possible causes:")
        print("      - I2C not initialized (some cameras need I2C setup)")
        print("      - Camera stuck in reset")
        print("   → Try: Power cycle the Pi completely")

elif valid_count > 0:
    print("   ✓ Camera is outputting valid packets!")
    print("   → You can run the forwarder now")

else:
    print("   ? Unexpected state - check wiring")

print("\n" + "=" * 60)
print("Wiring Reference (v2.0 Breakout → Pi):")
print("  VIN  → Pin 1 (3.3V) or Pin 2 (5V)")
print("  GND  → Pin 6")  
print("  CLK  → Pin 23 (SCLK)")
print("  MISO → Pin 21 (MISO)")
print("  CS   → Pin 24 (CE0)")
print("  SDA  → Pin 3 (optional, for I2C)")
print("  SCL  → Pin 5 (optional, for I2C)")
print("=" * 60)
