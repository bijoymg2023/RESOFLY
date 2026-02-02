#!/usr/bin/env python3
"""
Thermal Processor (Round-Trip) - Runs on Laptop
1. Receives raw thermal frames from Pi via UDP
2. Processes frames (normalize, colormap, scale, encode)
3. Sends processed JPEG frames back to Pi
"""

import socket
import struct
import time
import numpy as np
import cv2

# ==== CONFIGURATION ====
LISTEN_IP = "0.0.0.0"           # Listen on all interfaces
LISTEN_PORT = 5005              # Receive raw data from Pi
PI_IP = "192.168.10.2"          # Pi's IP address
PI_RECEIVE_PORT = 5006          # Port to send processed frames to Pi

# Lepton 3.5 specs
FRAME_WIDTH = 160
FRAME_HEIGHT = 120
FRAME_SIZE_BYTES = FRAME_WIDTH * FRAME_HEIGHT * 2  # 38400 bytes

# Output settings
OUTPUT_SCALE = 4                # Scale factor (160*4 = 640, 120*4 = 480)
JPEG_QUALITY = 85               # JPEG compression quality

# ==== GLOBALS ====
frame_count = 0
start_time = None

def process_frame(raw_data):
    """
    Process raw 16-bit thermal data into colored JPEG.
    Uses GPU acceleration if available via OpenCV.
    """
    # Convert bytes to numpy array (big-endian uint16)
    frame_16bit = np.frombuffer(raw_data, dtype='>u2')
    frame_16bit = frame_16bit.reshape((FRAME_HEIGHT, FRAME_WIDTH))
    
    # Normalize to 8-bit
    frame_norm = cv2.normalize(frame_16bit, None, 0, 255, cv2.NORM_MINMAX)
    frame_8bit = frame_norm.astype(np.uint8)
    
    # Apply colormap (INFERNO for thermal)
    frame_colored = cv2.applyColorMap(frame_8bit, cv2.COLORMAP_INFERNO)
    
    # Scale up for visibility
    output_width = FRAME_WIDTH * OUTPUT_SCALE
    output_height = FRAME_HEIGHT * OUTPUT_SCALE
    frame_scaled = cv2.resize(frame_colored, (output_width, output_height),
                              interpolation=cv2.INTER_LINEAR)
    
    # Encode to JPEG
    encode_params = [cv2.IMWRITE_JPEG_QUALITY, JPEG_QUALITY]
    _, jpeg_data = cv2.imencode('.jpg', frame_scaled, encode_params)
    
    return jpeg_data.tobytes()

def main():
    global frame_count, start_time
    
    print("=" * 50)
    print("  THERMAL PROCESSOR (Round-Trip Mode)")
    print("=" * 50)
    print(f"[LAPTOP] Receiving raw frames on port {LISTEN_PORT}")
    print(f"[LAPTOP] Sending processed frames to {PI_IP}:{PI_RECEIVE_PORT}")
    print(f"[LAPTOP] Output: {FRAME_WIDTH * OUTPUT_SCALE}x{FRAME_HEIGHT * OUTPUT_SCALE}")
    print("=" * 50)
    
    # Receive socket
    recv_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    recv_sock.bind((LISTEN_IP, LISTEN_PORT))
    recv_sock.settimeout(5.0)
    
    # Send socket
    send_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    
    expected_packet_size = 8 + FRAME_SIZE_BYTES  # Header + frame data
    start_time = time.time()
    
    print("[LAPTOP] Waiting for frames from Pi...")
    
    while True:
        try:
            data, addr = recv_sock.recvfrom(expected_packet_size + 100)
            
            if len(data) >= expected_packet_size:
                # Extract header and raw frame
                pi_frame_num, timestamp = struct.unpack('>II', data[:8])
                raw_frame = data[8:8 + FRAME_SIZE_BYTES]
                
                # Process the frame
                proc_start = time.time()
                jpeg_data = process_frame(raw_frame)
                proc_time = (time.time() - proc_start) * 1000
                
                # Send processed frame back to Pi
                jpeg_size = len(jpeg_data)
                header = struct.pack('>II', frame_count, jpeg_size)
                
                # Send (may need chunking for large JPEGs, but 640x480 should fit in one packet)
                send_sock.sendto(header + jpeg_data, (PI_IP, PI_RECEIVE_PORT))
                
                frame_count += 1
                
                if frame_count % 9 == 0:
                    elapsed = time.time() - start_time
                    fps = frame_count / elapsed
                    print(f"[LAPTOP] Frame {pi_frame_num} → processed in {proc_time:.1f}ms, " +
                          f"JPEG: {jpeg_size} bytes, FPS: {fps:.1f}")
            else:
                print(f"[LAPTOP] Incomplete packet: {len(data)} bytes (expected {expected_packet_size})")
        
        except socket.timeout:
            print("[LAPTOP] Waiting for data from Pi...")
        except Exception as e:
            print(f"[LAPTOP] Error: {e}")

if __name__ == "__main__":
    main()
