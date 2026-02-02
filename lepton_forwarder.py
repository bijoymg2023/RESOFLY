#!/usr/bin/env python3
"""
Lepton Forwarder - Runs on Raspberry Pi
Reads raw thermal frames from FLIR Lepton via SPI and forwards to laptop via UDP.
Minimal processing to reduce Pi load.
"""

import spidev
import socket
import struct
import time
import sys

# ==== CONFIGURATION ====
LAPTOP_IP = "192.168.10.1"  # Laptop static IP
LAPTOP_PORT = 5005          # UDP port to send to
SPI_SPEED = 20000000        # 20 MHz SPI clock

# Lepton 3.5 specs
PACKET_SIZE = 164
PACKETS_PER_FRAME = 60
FRAME_WIDTH = 80
FRAME_HEIGHT = 60
FRAME_SIZE_BYTES = FRAME_WIDTH * FRAME_HEIGHT * 2  # 9600 bytes (uint16)

# ==== SETUP ====
print(f"[FORWARDER] Starting Lepton Forwarder")
print(f"[FORWARDER] Target: {LAPTOP_IP}:{LAPTOP_PORT}")

# Initialize SPI
spi = spidev.SpiDev()
spi.open(0, 0)  # SPI0, CE0
spi.max_speed_hz = SPI_SPEED
spi.mode = 0b11  # CPOL=1, CPHA=1

# Initialize UDP socket
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

def read_frame():
    """
    Read a complete frame from Lepton.
    Returns raw 16-bit pixel data as bytes (9600 bytes for 80x60).
    """
    frame_data = bytearray(FRAME_SIZE_BYTES)
    row = 0
    max_retries = 1000
    retries = 0
    
    while row < FRAME_HEIGHT and retries < max_retries:
        packet = spi.readbytes(PACKET_SIZE)
        
        # Check for discard packet (ID nibble = 0x0F)
        if (packet[0] & 0x0F) == 0x0F:
            retries += 1
            continue
        
        packet_row = packet[1]
        
        # Check if we got the expected row
        if packet_row != row:
            # Out of sync, reset
            row = 0
            retries += 1
            continue
        
        # Extract pixel data (skip 4-byte header)
        for col in range(FRAME_WIDTH):
            hi = packet[4 + col * 2]
            lo = packet[5 + col * 2]
            offset = (row * FRAME_WIDTH + col) * 2
            frame_data[offset] = hi
            frame_data[offset + 1] = lo
        
        row += 1
        retries = 0
    
    if retries >= max_retries:
        print("[FORWARDER] Warning: Max retries reached, partial frame")
    
    return bytes(frame_data)

def main():
    frame_count = 0
    start_time = time.time()
    
    print("[FORWARDER] Starting frame capture and forwarding...")
    
    try:
        while True:
            # Read frame from Lepton
            frame_data = read_frame()
            
            # Add frame header (frame number + timestamp)
            timestamp = int(time.time() * 1000) & 0xFFFFFFFF
            header = struct.pack('>II', frame_count, timestamp)
            
            # Send via UDP (header + raw frame data)
            packet = header + frame_data
            sock.sendto(packet, (LAPTOP_IP, LAPTOP_PORT))
            
            frame_count += 1
            
            # Print stats every 27 frames (~3 seconds at 9fps)
            if frame_count % 27 == 0:
                elapsed = time.time() - start_time
                fps = frame_count / elapsed
                print(f"[FORWARDER] Frames: {frame_count}, FPS: {fps:.1f}")
    
    except KeyboardInterrupt:
        print("\n[FORWARDER] Shutting down...")
    finally:
        spi.close()
        sock.close()

if __name__ == "__main__":
    main()
