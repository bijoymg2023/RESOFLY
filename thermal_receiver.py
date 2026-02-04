#!/usr/bin/env python3
"""
Thermal Receiver - Runs on Raspberry Pi
1. Receives processed JPEG frames from laptop via UDP (port 5006)
2. Serves MJPEG stream on port 8081 for the dashboard
"""

import socket
import struct
import time
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler

# ==== CONFIGURATION ====
LISTEN_PORT = 5006              # Receive processed frames from laptop
HTTP_PORT = 8081                # MJPEG stream port for dashboard

# ==== GLOBALS ====
current_jpeg = None
jpeg_lock = threading.Lock()
frame_count = 0

# ==== HTTP SERVER FOR MJPEG ====
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
                        frame = current_jpeg
                    
                    if frame:
                        self.wfile.write(b'--frame\r\n')
                        self.wfile.write(b'Content-Type: image/jpeg\r\n\r\n')
                        self.wfile.write(frame)
                        self.wfile.write(b'\r\n')
                    
                    time.sleep(0.033)  # ~30 fps max
            except (BrokenPipeError, ConnectionResetError):
                pass
        elif self.path == '/status':
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(f'{{"frames_received": {frame_count}}}'.encode())
        else:
            self.send_response(404)
            self.end_headers()

def start_http_server():
    try:
        server = HTTPServer(('0.0.0.0', HTTP_PORT), MJPEGHandler)
        print(f"[PI-RX] MJPEG server on http://0.0.0.0:{HTTP_PORT}/stream")
        server.serve_forever()
    except OSError as e:
        print(f"[PI-RX] HTTP SERVER ERROR: {e}")
        print(f"[PI-RX] Port {HTTP_PORT} may be in use. Kill other processes or change port.")
    except Exception as e:
        print(f"[PI-RX] HTTP SERVER ERROR: {e}")

def main():
    global current_jpeg, frame_count
    
    print("=" * 50)
    print("  THERMAL RECEIVER (Pi Side)")
    print("=" * 50)
    print(f"[PI-RX] Listening for processed frames on port {LISTEN_PORT}")
    print(f"[PI-RX] Serving MJPEG stream on port {HTTP_PORT}")
    print("=" * 50)
    
    # Start HTTP server in background
    http_thread = threading.Thread(target=start_http_server, daemon=True)
    http_thread.start()
    
    # UDP socket for receiving processed frames
    recv_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    recv_sock.bind(('0.0.0.0', LISTEN_PORT))
    recv_sock.settimeout(5.0)
    
    # Max UDP packet size (65KB typical max)
    MAX_PACKET_SIZE = 65535
    
    print("[PI-RX] Waiting for frames from laptop...")
    
    start_time = time.time()
    
    while True:
        try:
            data, addr = recv_sock.recvfrom(MAX_PACKET_SIZE)
            
            if len(data) > 8:
                # Extract header
                frame_num, jpeg_size = struct.unpack('>II', data[:8])
                jpeg_data = data[8:8 + jpeg_size]
                
                # Update MJPEG buffer
                with jpeg_lock:
                    current_jpeg = jpeg_data
                
                frame_count += 1
                
                if frame_count % 27 == 0:
                    elapsed = time.time() - start_time
                    fps = frame_count / elapsed if elapsed > 0 else 0
                    print(f"[PI-RX] Received frame {frame_num}, size={len(jpeg_data)} bytes, FPS: {fps:.1f}")
            
        except socket.timeout:
            print("[PI-RX] Waiting for frames from laptop...")
        except Exception as e:
            print(f"[PI-RX] Error: {e}")

if __name__ == "__main__":
    main()
