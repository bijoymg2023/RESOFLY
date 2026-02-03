#!/usr/bin/env python3
"""
Lepton Forwarder (Values Only) - Runs on Raspberry Pi
1. Reads raw thermal frames from FLIR Lepton via SPI
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
SPI_SPEED = 5000000             # 5 MHz SPI clock

# Lepton 3.5 specs
PACKET_SIZE = 164
PACKETS_PER_FRAME = 60
FRAME_WIDTH = 160               # Lepton 3.5 = 160x120
FRAME_HEIGHT = 120
PACKETS_PER_SEGMENT = 60
SEGMENTS_PER_FRAME = 4          # Lepton 3.5 has 4 segments
FRAME_SIZE_BYTES = FRAME_WIDTH * FRAME_HEIGHT * 2  # 38400 bytes

# Timeout settings
MAX_FRAME_RETRIES = 3000        # Max retries before giving up on a frame
FRAME_TIMEOUT_SECONDS = 5       # Timeout for a single frame

# ==== READ AND FORWARD RAW FRAMES ====
def read_and_forward(test_mode=False):
    import random
    
    if test_mode:
        print("[PI] *** TEST MODE - Using fake thermal data ***")
        print("[PI] No camera needed - sending simulated frames")
        spi = None
    else:
        print("[PI] Initializing SPI...")
        # Initialize SPI
        try:
            spi = spidev.SpiDev()
            spi.open(0, 0)
            spi.max_speed_hz = SPI_SPEED
            spi.mode = 0b11
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
        
        print("[PI] Waiting for Lepton to stabilize (2 seconds)...")
        time.sleep(2)
        print("[PI] Starting frame capture...")
    
    # UDP socket for sending
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    
    print(f"[PI] Forwarding raw frames to {LAPTOP_IP}:{LAPTOP_PORT}")
    
    send_frame_count = 0
    
    failed_frames = 0
    last_status_time = time.time()
    
    while True:
        try:
            frame_data = bytearray(FRAME_SIZE_BYTES)
            frame_start_time = time.time()
            
            if test_mode:
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
                frame_complete = True
                total_retries = 0
                
                for segment in range(SEGMENTS_PER_FRAME):
                    segment_row = 0
                    retries = 0
                    max_retries = 750  # Increased for reliability
                    
                    # Show progress for first frame
                    if send_frame_count == 0 and segment == 0:
                        print(f"[PI] Reading segment {segment + 1}/{SEGMENTS_PER_FRAME}...")
                    
                    while segment_row < (FRAME_HEIGHT // SEGMENTS_PER_FRAME) and retries < max_retries:
                        # Check for timeout
                        if time.time() - frame_start_time > FRAME_TIMEOUT_SECONDS:
                            print(f"[PI] Frame timeout after {FRAME_TIMEOUT_SECONDS}s (segment {segment}, row {segment_row})")
                            frame_complete = False
                            break
                        
                        packet = spi.readbytes(PACKET_SIZE)
                        
                        # Check for discard packet
                        if (packet[0] & 0x0F) == 0x0F:
                            retries += 1
                            total_retries += 1
                            continue
                        
                        packet_row = packet[1]
                        
                        # For Lepton 3.5, check segment number in packet 20
                        if packet_row == 20:
                            pkt_segment = (packet[0] >> 4) & 0x0F
                            if pkt_segment != (segment + 1):
                                segment_row = 0
                                retries += 1
                                total_retries += 1
                                continue
                        
                        if packet_row != segment_row:
                            segment_row = 0
                            retries += 1
                            total_retries += 1
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
                    
                    if retries >= max_retries:
                        print(f"[PI] Max retries reached on segment {segment}, row {segment_row}")
                        frame_complete = False
                        break
                    
                    if not frame_complete:
                        break
                
                if not frame_complete:
                    failed_frames += 1
                    if failed_frames >= 5:
                        print(f"[PI] WARNING: {failed_frames} consecutive failed frames")
                        print("[PI] Check: Is Lepton connected? Is SPI wiring correct?")
                        failed_frames = 0
                        time.sleep(1)  # Brief pause before retrying
                    continue
                
                # Reset failed frame counter on success
                failed_frames = 0
            
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
    parser = argparse.ArgumentParser(description='Lepton Forwarder - Send thermal frames to laptop')
    parser.add_argument('--test', action='store_true', 
                        help='Use fake thermal data (no camera needed)')
    parser.add_argument('--ip', type=str, default=LAPTOP_IP,
                        help=f'Laptop IP address (default: {LAPTOP_IP})')
    args = parser.parse_args()
    
    # Update laptop IP if specified
    global LAPTOP_IP
    if args.ip != LAPTOP_IP:
        LAPTOP_IP = args.ip
    
    print("=" * 50)
    print("  LEPTON FORWARDER (One-Way)")
    print("=" * 50)
    print(f"[PI] Raw data → {LAPTOP_IP}:{LAPTOP_PORT}")
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

