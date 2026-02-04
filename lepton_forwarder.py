#!/usr/bin/env python3
"""
Lepton Forwarder - Runs on Raspberry Pi
1. Reads raw thermal frames from FLIR Lepton 3.5 via SPI
2. Forwards raw data to laptop via UDP

Usage:
  python3 lepton_forwarder.py          # Normal mode (requires Lepton camera)
  python3 lepton_forwarder.py --test   # Test mode (fake thermal data)
"""

import spidev
import socket
import struct
import time
import sys
import argparse

# ==== CONFIGURATION ====
LAPTOP_IP = "192.168.10.1"      # Laptop static IP (send raw user data here)
LAPTOP_PORT = 5005              # UDP port for raw data
SPI_SPEED = 18000000            # 18 MHz SPI clock (matches working C++ reference)

# Lepton 3.5 specs
PACKET_SIZE = 164
PACKETS_PER_SEGMENT = 60
FRAME_WIDTH = 160               # Lepton 3.5 = 160x120
FRAME_HEIGHT = 120
SEGMENTS_PER_FRAME = 4          # Lepton 3.5 has 4 segments
FRAME_SIZE_BYTES = FRAME_WIDTH * FRAME_HEIGHT * 2  # 38400 bytes

# ==== READ AND FORWARD RAW FRAMES ====
def read_and_forward(test_mode=False):
    import random
    
    spi = None
    
    if test_mode:
        print("[PI] *** TEST MODE - Using fake thermal data ***")
        print("[PI] No camera needed - sending simulated frames")
    else:
        print("[PI] Initializing SPI (18 MHz, Mode 3)...")
        try:
            spi = spidev.SpiDev()
            spi.open(0, 1)  # CS1 (CE1, Pin 26)
            spi.max_speed_hz = SPI_SPEED
            spi.mode = 0b11  # SPI_MODE_3 (CPOL=1, CPHA=1)
            print("[PI] SPI initialized successfully")
        except FileNotFoundError:
            print("[PI] SPI INIT ERROR: SPI device not found!")
            print("[PI] Make sure SPI is enabled: sudo raspi-config -> Interface Options -> SPI")
            sys.exit(1)
        except PermissionError:
            print("[PI] SPI INIT ERROR: Permission denied!")
            print("[PI] Try running with sudo: sudo python3 lepton_forwarder.py")
            sys.exit(1)
        except Exception as e:
            print(f"[PI] SPI INIT ERROR: {e}")
            sys.exit(1)
        
        print("[PI] Waiting for Lepton to stabilize (3 seconds)...")
        time.sleep(3)
        print("[PI] Starting frame capture...")
    
    # UDP socket for sending
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    
    print(f"[PI] Forwarding raw frames to {LAPTOP_IP}:{LAPTOP_PORT}")
    
    send_frame_count = 0
    spi_resets = 0
    
    # Storage for all 4 segments
    shelf = [bytearray(PACKET_SIZE * PACKETS_PER_SEGMENT) for _ in range(4)]
    
    while True:
        try:
            if test_mode:
                # Generate fake thermal gradient with moving hot spot
                frame_data = bytearray(FRAME_SIZE_BYTES)
                t = time.time()
                hot_x = int((FRAME_WIDTH / 2) + 30 * (0.5 + 0.5 * (t % 6) / 3))
                hot_y = int((FRAME_HEIGHT / 2) + 20 * (0.5 + 0.5 * ((t * 0.7) % 6) / 3))
                
                for y in range(FRAME_HEIGHT):
                    for x in range(FRAME_WIDTH):
                        dx = x - hot_x
                        dy = y - hot_y
                        dist = (dx*dx + dy*dy) ** 0.5
                        temp = max(0, min(65535, int(40000 - dist * 300 + random.randint(-500, 500))))
                        offset = (y * FRAME_WIDTH + x) * 2
                        frame_data[offset] = (temp >> 8) & 0xFF
                        frame_data[offset + 1] = temp & 0xFF
                
                time.sleep(0.111)  # ~9 fps to match Lepton
            else:
                # Read one complete frame (4 segments) - matching C++ reference logic
                frame_data = bytearray(FRAME_SIZE_BYTES)
                segment_number = -1
                resets = 0
                
                # Read all 4 segments
                for seg_idx in range(SEGMENTS_PER_FRAME):
                    # Read 60 packets per segment
                    packet_idx = 0
                    while packet_idx < PACKETS_PER_SEGMENT:
                        packet = spi.readbytes(PACKET_SIZE)
                        
                        packet_number = packet[1]
                        
                        # Check if packet number matches expected
                        if packet_number != packet_idx:
                            packet_idx = 0  # Reset to start of segment
                            resets += 1
                            time.sleep(0.001)  # 1ms delay between retries
                            
                            # SPI reset after 100 failed packets (from C++ reference)
                            if resets >= 100:
                                spi.close()
                                time.sleep(0.2)  # 200ms wait
                                spi.open(0, 1)
                                spi.max_speed_hz = SPI_SPEED
                                spi.mode = 0b11
                                resets = 0
                                spi_resets += 1
                                print(f"[PI] SPI reset #{spi_resets}")
                                
                                # Camera reboot after 5 SPI resets
                                if spi_resets >= 5:
                                    print("[PI] Too many SPI resets, waiting 5s for camera...")
                                    time.sleep(5)
                                    spi_resets = 0
                            continue
                        
                        # Check segment number on packet 20
                        if packet_number == 20:
                            segment_number = (packet[0] >> 4) & 0x0F
                            if segment_number < 1 or segment_number > 4:
                                # Invalid segment, restart
                                packet_idx = 0
                                resets += 1
                                continue
                        
                        # Store packet in shelf
                        start = packet_idx * PACKET_SIZE
                        shelf[seg_idx][start:start + PACKET_SIZE] = packet
                        packet_idx += 1
                    
                    # If we read all packets but segment is not the expected one (seg_idx + 1)
                    if segment_number != -1 and segment_number != seg_idx + 1:
                        # Out of sync, retry
                        resets += 1
                        continue
                
                # Check if we have a valid frame (segment 4 was received)
                if segment_number != 4:
                    continue
                
                # Convert shelf data to frame
                for seg_idx in range(SEGMENTS_PER_FRAME):
                    ofs_row = 30 * seg_idx  # Each segment = 30 rows
                    for pkt in range(PACKETS_PER_SEGMENT):
                        pkt_start = pkt * PACKET_SIZE
                        # Skip 4 header bytes (2 uint16), read 80 pixels per packet
                        for col in range(80):
                            hi = shelf[seg_idx][pkt_start + 4 + col * 2]
                            lo = shelf[seg_idx][pkt_start + 5 + col * 2]
                            
                            # Calculate row and column (2 packets per row for 160 width)
                            row = pkt // 2 + ofs_row
                            actual_col = col + (pkt % 2) * 80
                            
                            if row < FRAME_HEIGHT and actual_col < FRAME_WIDTH:
                                offset = (row * FRAME_WIDTH + actual_col) * 2
                                frame_data[offset] = hi
                                frame_data[offset + 1] = lo
            
            # Pack and send frame
            timestamp = int(time.time() * 1000) & 0xFFFFFFFF
            header = struct.pack('>II', send_frame_count, timestamp)
            
            packet = header + bytes(frame_data)
            sock.sendto(packet, (LAPTOP_IP, LAPTOP_PORT))
            
            send_frame_count += 1
            
            if send_frame_count % 9 == 0:
                print(f"[PI] Sent frame {send_frame_count}")
        
        except Exception as e:
            print(f"[PI] Error: {e}")
            time.sleep(0.1)

# ==== MAIN ====
def main():
    global LAPTOP_IP
    
    parser = argparse.ArgumentParser(description='Lepton Forwarder - Send thermal frames to laptop')
    parser.add_argument('--test', action='store_true', 
                        help='Use fake thermal data (no camera needed)')
    parser.add_argument('--ip', type=str, default=None,
                        help=f'Laptop IP address (default: {LAPTOP_IP})')
    args = parser.parse_args()
    
    if args.ip:
        LAPTOP_IP = args.ip

    print("=" * 50)
    print("  LEPTON FORWARDER (Lepton 3.5)")
    print("=" * 50)
    print(f"[PI] Raw data → {LAPTOP_IP}:{LAPTOP_PORT}")
    print(f"[PI] SPI Speed: {SPI_SPEED // 1000000} MHz")
    if args.test:
        print("[PI] MODE: TEST (fake thermal data)")
    else:
        print("[PI] MODE: LIVE (Lepton camera)")
    print("=" * 50)
    
    try:
        read_and_forward(test_mode=args.test)
    except KeyboardInterrupt:
        print("\n[PI] Shutting down...")

if __name__ == "__main__":
    main()
