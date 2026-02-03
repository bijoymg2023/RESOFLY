#!/usr/bin/env python3
"""
Lepton Forwarder (Values Only) - Runs on Raspberry Pi
1. Reads raw thermal frames from FLIR Lepton via SPI
2. Forwards raw data to laptop via UDP
"""

import spidev
import socket
import struct
import time
import sys

# ==== CONFIGURATION ====
LAPTOP_IP = "192.168.10.1"      # Laptop static IP (send raw user data heere)
LAPTOP_PORT = 5005              # UDP port for raw data
SPI_SPEED = 5000000             # 5 MHz SPI clock

# Set to True to test pipeline with fake data (no camera needed)
TEST_MODE = False

# Lepton 3.5 specs
PACKET_SIZE = 164
PACKETS_PER_FRAME = 60
FRAME_WIDTH = 160               # Lepton 3.5 = 160x120
FRAME_HEIGHT = 120
PACKETS_PER_SEGMENT = 60
SEGMENTS_PER_FRAME = 4          # Lepton 3.5 has 4 segments
FRAME_SIZE_BYTES = FRAME_WIDTH * FRAME_HEIGHT * 2  # 38400 bytes

# ==== READ AND FORWARD RAW FRAMES ====
def read_and_forward():
    import random
    
    if TEST_MODE:
        print("[PI] *** TEST MODE - Using fake thermal data ***")
    else:
        print("[PI] Initializing SPI...")
        # Initialize SPI
        try:
            spi = spidev.SpiDev()
            spi.open(0, 0)
            spi.max_speed_hz = SPI_SPEED
            spi.mode = 0b11
        except Exception as e:
            print(f"[PI] SPI INIT ERROR: {e}")
            sys.exit(1)
    
    # UDP socket for sending
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    
    print(f"[PI] Forwarding raw frames to {LAPTOP_IP}:{LAPTOP_PORT}")
    
    send_frame_count = 0
    
    while True:
        try:
            frame_data = bytearray(FRAME_SIZE_BYTES)
            
            if TEST_MODE:
                # Generate fake thermal gradient with moving hot spot
                t = time.time()
                hot_x = int((FRAME_WIDTH / 2) + 30 * (0.5 + 0.5 * (t % 6) / 3))
                hot_y = int((FRAME_HEIGHT / 2) + 20 * (0.5 + 0.5 * ((t * 0.7) % 6) / 3))
                
                for y in range(FRAME_HEIGHT):
                    for x in range(FRAME_WIDTH):
                        # Distance from center (creates gradient)
                        dx = x - hot_x
                        dy = y - hot_y
                        dist = (dx*dx + dy*dy) ** 0.5
                        
                        # Temperature value (16-bit) - hotter in center
                        temp = max(0, min(65535, int(40000 - dist * 300 + random.randint(-500, 500))))
                        
                        offset = (y * FRAME_WIDTH + x) * 2
                        frame_data[offset] = (temp >> 8) & 0xFF
                        frame_data[offset + 1] = temp & 0xFF
                
                time.sleep(0.111)  # ~9 fps to match Lepton
            else:
                # Read one complete frame (4 segments for Lepton 3.5)
                for segment in range(SEGMENTS_PER_FRAME):
                    segment_row = 0
                    retries = 0
                    max_retries = 500
                    
                    while segment_row < (FRAME_HEIGHT // SEGMENTS_PER_FRAME) and retries < max_retries:
                        packet = spi.readbytes(PACKET_SIZE)
                        
                        # Check for discard packet
                        if (packet[0] & 0x0F) == 0x0F:
                            retries += 1
                            continue
                        
                        packet_row = packet[1]
                        
                        # For Lepton 3.5, check segment number in packet 20
                        if packet_row == 20:
                            pkt_segment = (packet[0] >> 4) & 0x0F
                            if pkt_segment != (segment + 1):
                                segment_row = 0
                                retries += 1
                                continue
                        
                        if packet_row != segment_row:
                            segment_row = 0
                            retries += 1
                            continue
                        
                        # Extract pixel data
                        actual_row = segment * (FRAME_HEIGHT // SEGMENTS_PER_FRAME) + segment_row
                        for col in range(FRAME_WIDTH // 2):  # Each packet has 80 pixels
                            hi = packet[4 + col * 2]
                            lo = packet[5 + col * 2]
                            # Lepton 3.5: two packets per row (left and right halves)
                            offset = (actual_row * FRAME_WIDTH + col) * 2
                            frame_data[offset] = hi
                            frame_data[offset + 1] = lo
                        
                        segment_row += 1
                        retries = 0
            
            # Pack and send frame
            timestamp = int(time.time() * 1000) & 0xFFFFFFFF
            header = struct.pack('>II', send_frame_count, timestamp)
            
            # Send in chunks if needed (UDP limit ~65KB)
            packet = header + bytes(frame_data)
            sock.sendto(packet, (LAPTOP_IP, LAPTOP_PORT))
            
            send_frame_count += 1
            
            if send_frame_count % 27 == 0:
                print(f"[PI] Sent frame {send_frame_count}")
        
        except Exception as e:
            print(f"[PI] Error: {e}")
            time.sleep(0.1)

# ==== MAIN ====
def main():
    print("=" * 50)
    print("  LEPTON FORWARDER (One-Way)")
    print("=" * 50)
    print(f"[PI] Raw data → {LAPTOP_IP}:{LAPTOP_PORT}")
    print("=" * 50)
    
    try:
        read_and_forward()
    except KeyboardInterrupt:
        print("\n[PI] Shutting down...")

if __name__ == "__main__":
    main()
