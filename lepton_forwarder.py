#!/usr/bin/env python3
"""
Lepton Forwarder with Improved VoSPI Sync - Runs on Raspberry Pi
Uses proper VoSPI protocol: waits for out-of-sync, then captures frame.
"""

import spidev
import socket
import struct
import time
import sys
import argparse

# ==== CONFIGURATION ====
LAPTOP_IP = "192.168.10.1"
LAPTOP_PORT = 5005
SPI_SPEED = 10000000  # 10 MHz

# Lepton 3.5 specs
PACKET_SIZE = 164
PACKETS_PER_SEGMENT = 60
FRAME_WIDTH = 160
FRAME_HEIGHT = 120
SEGMENTS_PER_FRAME = 4
FRAME_SIZE_BYTES = FRAME_WIDTH * FRAME_HEIGHT * 2

def read_and_forward(test_mode=False):
    import random
    
    if test_mode:
        print("[PI] *** TEST MODE ***")
        spi = None
    else:
        print("[PI] Initializing SPI...")
        spi = spidev.SpiDev()
        spi.open(0, 0)  # CS0, Pin 24
        spi.max_speed_hz = SPI_SPEED
        spi.mode = 0b11
        print(f"[PI] SPI ready at {SPI_SPEED // 1000000} MHz")
        
        # VoSPI sync: wait for desync then resync
        print("[PI] Performing VoSPI initial sync...")
        sync_vospi(spi)
    
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    print(f"[PI] Sending to {LAPTOP_IP}:{LAPTOP_PORT}")
    
    frame_count = 0
    
    while True:
        try:
            if test_mode:
                frame_data = generate_test_frame(frame_count)
                time.sleep(0.111)
            else:
                frame_data = capture_frame(spi)
                if frame_data is None:
                    continue
            
            # Send frame
            timestamp = int(time.time() * 1000) & 0xFFFFFFFF
            header = struct.pack('>II', frame_count, timestamp)
            sock.sendto(header + frame_data, (LAPTOP_IP, LAPTOP_PORT))
            
            frame_count += 1
            if frame_count % 9 == 0:
                print(f"[PI] Sent frame {frame_count}")
                
        except Exception as e:
            print(f"[PI] Error: {e}")
            time.sleep(0.1)

def sync_vospi(spi):
    """VoSPI sync: find sync point by reading until we get consecutive valid packets."""
    print("[PI] Waiting for VoSPI sync...")
    
    # Read packets until we find packet 0
    max_attempts = 1000
    for attempt in range(max_attempts):
        packet = spi.readbytes(PACKET_SIZE)
        
        # Check for discard
        if (packet[0] & 0x0F) == 0x0F:
            time.sleep(0.0001)  # 100us between discards
            continue
        
        packet_num = packet[1]
        if packet_num == 0:
            print(f"[PI] VoSPI sync achieved at attempt {attempt}")
            return True
        
        time.sleep(0.0001)
    
    print("[PI] Warning: VoSPI sync timeout, continuing anyway")
    return False

def capture_frame(spi):
    """Capture one complete Lepton 3.5 frame (4 segments x 60 packets)."""
    frame_data = bytearray(FRAME_SIZE_BYTES)
    
    for seg_idx in range(SEGMENTS_PER_FRAME):
        segment_data = capture_segment(spi, seg_idx)
        if segment_data is None:
            return None
        
        # Copy segment to frame
        rows_per_seg = FRAME_HEIGHT // SEGMENTS_PER_FRAME  # 30 rows
        for pkt_idx in range(PACKETS_PER_SEGMENT):
            # 2 packets per row for 160-pixel width
            row = seg_idx * rows_per_seg + (pkt_idx // 2)
            col_offset = (pkt_idx % 2) * 80
            
            for px in range(80):
                src_offset = pkt_idx * PACKET_SIZE + 4 + px * 2
                dst_offset = (row * FRAME_WIDTH + col_offset + px) * 2
                
                if dst_offset + 1 < len(frame_data) and src_offset + 1 < len(segment_data):
                    frame_data[dst_offset] = segment_data[src_offset]
                    frame_data[dst_offset + 1] = segment_data[src_offset + 1]
    
    return bytes(frame_data)

def capture_segment(spi, expected_segment):
    """Capture one segment (60 packets). Returns raw packet data."""
    segment_data = bytearray(PACKETS_PER_SEGMENT * PACKET_SIZE)
    
    retries = 0
    max_retries = 500
    pkt_idx = 0
    
    while pkt_idx < PACKETS_PER_SEGMENT and retries < max_retries:
        packet = spi.readbytes(PACKET_SIZE)
        
        # Check discard
        if (packet[0] & 0x0F) == 0x0F:
            retries += 1
            continue
        
        packet_num = packet[1]
        
        # Check sequence
        if packet_num != pkt_idx:
            # Out of sequence, reset
            pkt_idx = 0
            retries += 1
            # Small delay for resync
            time.sleep(0.001)
            continue
        
        # Packet 20 has segment number for Lepton 3.5
        if packet_num == 20:
            seg_num = (packet[0] >> 4) & 0x0F
            if seg_num != expected_segment + 1:  # Segments are 1-indexed in packet
                pkt_idx = 0
                retries += 1
                continue
        
        # Valid packet, store it
        start = pkt_idx * PACKET_SIZE
        segment_data[start:start + PACKET_SIZE] = packet
        pkt_idx += 1
        retries = 0
    
    if pkt_idx < PACKETS_PER_SEGMENT:
        return None
    
    return bytes(segment_data)

def generate_test_frame(frame_num):
    """Generate fake thermal data for testing."""
    import random
    frame_data = bytearray(FRAME_SIZE_BYTES)
    t = time.time()
    hot_x = int(80 + 30 * ((t % 6) / 3))
    hot_y = int(60 + 20 * (((t * 0.7) % 6) / 3))
    
    for y in range(FRAME_HEIGHT):
        for x in range(FRAME_WIDTH):
            dist = ((x - hot_x)**2 + (y - hot_y)**2) ** 0.5
            temp = max(0, min(65535, int(40000 - dist * 300 + random.randint(-500, 500))))
            offset = (y * FRAME_WIDTH + x) * 2
            frame_data[offset] = (temp >> 8) & 0xFF
            frame_data[offset + 1] = temp & 0xFF
    
    return bytes(frame_data)

def main():
    global LAPTOP_IP
    
    parser = argparse.ArgumentParser()
    parser.add_argument('--test', action='store_true', help='Test mode (no camera)')
    parser.add_argument('--ip', type=str, default=None, help='Laptop IP')
    args = parser.parse_args()
    
    if args.ip:
        LAPTOP_IP = args.ip
    
    print("=" * 50)
    print("  LEPTON FORWARDER (VoSPI Sync)")
    print("=" * 50)
    print(f"[PI] Target: {LAPTOP_IP}:{LAPTOP_PORT}")
    print(f"[PI] Mode: {'TEST' if args.test else 'LIVE'}")
    print("=" * 50)
    
    try:
        read_and_forward(test_mode=args.test)
    except KeyboardInterrupt:
        print("\n[PI] Stopped")

if __name__ == "__main__":
    main()
