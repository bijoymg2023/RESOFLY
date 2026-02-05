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
# PI_IP = "192.168.10.2"          # Pi's IP address (default, can be overridden)
# PI_RETURN_PORT = 5006           # Port on Pi to receive processed frames (DEPRECATED)

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
        print(f"[THERMAL] MJPEG server on port {HTTP_PORT}")
        server.serve_forever()
    except OSError as e:
        print(f"[THERMAL] HTTP SERVER ERROR: {e}")
        print(f"[THERMAL] Port {HTTP_PORT} may be in use.")
    except Exception as e:
        print(f"[THERMAL] HTTP SERVER ERROR: {e}")
        traceback.print_exc()



def main():
    global frame_count, start_time, current_jpeg
    
    print("=" * 60)
    print("  THERMAL SERVER (Pi Receiver)")
    print("=" * 60)
    print(f"[THERMAL] Receiving JPEG frames on port {LISTEN_PORT}")
    print(f"[THERMAL] Serving MJPEG stream at http://0.0.0.0:{HTTP_PORT}/stream")
    print("=" * 60)
    
    # Start HTTP server for local debugging
    http_thread = threading.Thread(target=start_http_server, daemon=True)
    http_thread.start()
    
    # Receive socket (from Pi)
    recv_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    recv_sock.bind((LISTEN_IP, LISTEN_PORT))
    recv_sock.settimeout(5.0)
    
    # Processed JPEG stream doesn't have fixed packet size, but use safe buffer
    max_packet_size = 65535  # UDP Max
    start_time = time.time()
    
    print("[THERMAL] Waiting for frames...")
    
    while True:
        try:
            data, addr = recv_sock.recvfrom(max_packet_size)
            
            if len(data) >= 8:
                # Extract header and JPEG frame
                pi_frame_num, timestamp = struct.unpack('>II', data[:8])
                jpeg_data = data[8:] # The rest is the JPEG
                
                # No processing needed - Pi did it!
                proc_time = 0 
                
                # Update local buffer (for debug stream)
                with jpeg_lock:
                    current_jpeg = jpeg_data
                
                # No return stream needed
                
                frame_count += 1
                
                if frame_count % 27 == 0:
                    elapsed = time.time() - start_time
                    fps = frame_count / elapsed
                    print(f"[THERMAL] Frame {pi_frame_num} received, FPS: {fps:.1f}")
            else:
                 # print(f"[THERMAL] Ignored small packet: {len(data)} bytes")
                 pass
        
        except socket.timeout:
            print("[THERMAL] Waiting for data...")
        except Exception as e:
            print(f"[THERMAL] Error: {e}")

if __name__ == "__main__":
    main()
