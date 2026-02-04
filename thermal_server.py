#!/usr/bin/env python3
"""
Thermal Processor with Return Stream - Runs on Laptop
1. Receives raw thermal frames from Pi via UDP (port 5005)
2. Processes frames (normalize, colormap, scale, encode)
3. Sends processed JPEG back to Pi via UDP (port 5006)
4. Also serves local MJPEG stream for debugging
"""

import socket
import struct
import time
import threading
import traceback
import sys
import argparse
import numpy as np
import cv2
from http.server import HTTPServer, BaseHTTPRequestHandler

# ==== CONFIGURATION ====
LISTEN_IP = "0.0.0.0"           # Listen on all interfaces
LISTEN_PORT = 5005              # Receive raw data from Pi
HTTP_PORT = 8081                # Local MJPEG stream port (for debugging)

# Return stream to Pi
PI_IP = "192.168.10.2"          # Pi's IP address (default, can be overridden)
PI_RETURN_PORT = 5006           # Port on Pi to receive processed frames

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
current_jpeg = None
jpeg_lock = threading.Lock()

# ==== HTTP SERVER FOR LOCAL MJPEG (DEBUG) ====
class MJPEGHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass  # Suppress logging
    
    def do_GET(self):
        if self.path == '/stream' or self.path == '/api/stream/thermal':
            self.send_response(200)
            self.send_header('Content-Type', 'multipart/x-mixed-replace; boundary=frame')
            self.send_header('Cache-Control', 'no-cache')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            
            try:
                while True:
                    with jpeg_lock:
                        if current_jpeg:
                            frame = current_jpeg
                        else:
                            frame = None
                    
                    if frame:
                        self.wfile.write(b'--frame\r\n')
                        self.wfile.write(b'Content-Type: image/jpeg\r\n\r\n')
                        self.wfile.write(frame)
                        self.wfile.write(b'\r\n')
                    
                    time.sleep(0.033)  # ~30 fps max
            except (BrokenPipeError, ConnectionResetError):
                pass
        else:
            self.send_response(404)
            self.end_headers()

def start_http_server():
    try:
        server = HTTPServer(('0.0.0.0', HTTP_PORT), MJPEGHandler)
        print(f"[LAPTOP] Local MJPEG server on port {HTTP_PORT} (for debug)")
        server.serve_forever()
    except OSError as e:
        print(f"[LAPTOP] HTTP SERVER ERROR: {e}")
        print(f"[LAPTOP] Port {HTTP_PORT} may be in use.")
    except Exception as e:
        print(f"[LAPTOP] HTTP SERVER ERROR: {e}")
        traceback.print_exc()

def process_frame(raw_data):
    """
    Process raw 16-bit thermal data into colored JPEG.
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
    global frame_count, start_time, current_jpeg, PI_IP
    
    parser = argparse.ArgumentParser(description='Thermal Processor with Return Stream')
    parser.add_argument('--pi-ip', type=str, default=PI_IP,
                        help=f'Pi IP address for return stream (default: {PI_IP})')
    args = parser.parse_args()
    
    PI_IP = args.pi_ip
    
    print("=" * 60)
    print("  THERMAL PROCESSOR (Two-Way Mode)")
    print("=" * 60)
    print(f"[LAPTOP] Receiving raw frames on port {LISTEN_PORT}")
    print(f"[LAPTOP] Sending processed frames to {PI_IP}:{PI_RETURN_PORT}")
    print(f"[LAPTOP] Local debug stream: http://localhost:{HTTP_PORT}/stream")
    print(f"[LAPTOP] Output: {FRAME_WIDTH * OUTPUT_SCALE}x{FRAME_HEIGHT * OUTPUT_SCALE}")
    print("=" * 60)
    
    # Start HTTP server for local debugging
    http_thread = threading.Thread(target=start_http_server, daemon=True)
    http_thread.start()
    
    # Receive socket (from Pi)
    recv_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    recv_sock.bind((LISTEN_IP, LISTEN_PORT))
    recv_sock.settimeout(5.0)
    
    # Send socket (back to Pi)
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
                
                # Update local buffer (for debug stream)
                with jpeg_lock:
                    current_jpeg = jpeg_data
                
                # Send processed frame back to Pi
                # Header: frame_num (4 bytes) + jpeg_size (4 bytes) + jpeg_data
                return_header = struct.pack('>II', pi_frame_num, len(jpeg_data))
                return_packet = return_header + jpeg_data
                
                try:
                    send_sock.sendto(return_packet, (PI_IP, PI_RETURN_PORT))
                except Exception as e:
                    print(f"[LAPTOP] Failed to send to Pi: {e}")
                
                frame_count += 1
                
                if frame_count % 27 == 0:
                    elapsed = time.time() - start_time
                    fps = frame_count / elapsed
                    print(f"[LAPTOP] Frame {pi_frame_num} → processed in {proc_time:.1f}ms, " +
                          f"sent to Pi, FPS: {fps:.1f}")
            else:
                print(f"[LAPTOP] Incomplete packet: {len(data)} bytes (expected {expected_packet_size})")
        
        except socket.timeout:
            print("[LAPTOP] Waiting for data from Pi...")
        except Exception as e:
            print(f"[LAPTOP] Error: {e}")

if __name__ == "__main__":
    main()
