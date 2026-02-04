#!/usr/bin/env python3
"""
SPI Check for FLIR Lepton 3.5
Tests basic SPI communication with the camera.
"""

import spidev
import time
import sys

SPI_SPEED = 18000000  # 18 MHz (matches working C++ reference)

print("=" * 50)
print("  LEPTON SPI CHECK")
print("=" * 50)

print(f"[CHECK] Opening SPI at {SPI_SPEED // 1000000} MHz...")
try:
    spi = spidev.SpiDev()
    spi.open(0, 1)  # CS1 (CE1, Pin 26)
    spi.max_speed_hz = SPI_SPEED
    spi.mode = 0b11  # SPI_MODE_3
    print("[CHECK] SPI interface opened successfully")
except Exception as e:
    print(f"[CHECK] FAILED to open SPI: {e}")
    print("[CHECK] Make sure SPI is enabled: sudo raspi-config -> Interface Options -> SPI")
    sys.exit(1)

print("[CHECK] Reading 10 test packets...")
valid_packets = 0
discard_packets = 0

for i in range(10):
    try:
        packet = spi.readbytes(164)  # Lepton packet size
        
        # Check if discard packet (ID nibble = 0x0F)
        if (packet[0] & 0x0F) == 0x0F:
            discard_packets += 1
        else:
            valid_packets += 1
            packet_num = packet[1]
            print(f"  Packet {i}: ID nibble={packet[0] & 0x0F:X}, Packet#={packet_num}")
        
        time.sleep(0.01)  # Small delay between reads
    except Exception as e:
        print(f"[CHECK] FAILED to read packet {i}: {e}")
        spi.close()
        sys.exit(1)

spi.close()

print("=" * 50)
print(f"[CHECK] Results: {valid_packets} valid, {discard_packets} discard packets")

if valid_packets > 0:
    print("[CHECK] ✓ SUCCESS: Camera is responding over SPI!")
    print("[CHECK] You can now run: sudo python3 lepton_forwarder.py")
elif discard_packets == 10:
    print("[CHECK] ⚠ Camera sending discard packets - may need more warm-up time")
    print("[CHECK] Wait 2-3 minutes after power-on, then try again")
else:
    print("[CHECK] ✗ FAILED: No valid data received")
    print("[CHECK] Check wiring: MISO→Pin21, CLK→Pin23, CS→Pin26")

print("=" * 50)
