#!/usr/bin/env python3
"""
Lepton Forwarder (Round-Trip) - Runs on Raspberry Pi
1. Reads raw thermal frames from FLIR Lepton via SPI
2. Forwards raw data to laptop via UDP
3. Receives processed JPEG frames back from laptop
4. Serves MJPEG stream for dashboard
"""

import spidev
import socket
import struct
import threading
import time
import traceback
from http.server import HTTPServer, BaseHTTPRequestHandler
import sys

# ==== CONFIGURATION ====
LAPTOP_IP = "192.168.10.1"      # Laptop static IP (send raw data here)
LAPTOP_PORT = 5005              # UDP port for raw data
PI_RECEIVE_PORT = 5006          # UDP port to receive processed frames
HTTP_PORT = 8080                # MJPEG stream port
SPI_SPEED = 5000000             # 5 MHz SPI clock (lowered for stability)

# Set to True to test pipeline with fake data (no camera needed)
TEST_MODE = True

# Lepton 3.5 specs
PACKET_SIZE = 164
PACKETS_PER_FRAME = 60
FRAME_WIDTH = 160               # Lepton 3.5 = 160x120
FRAME_HEIGHT = 120
PACKETS_PER_SEGMENT = 60
SEGMENTS_PER_FRAME = 4          # Lepton 3.5 has 4 segments
FRAME_SIZE_BYTES = FRAME_WIDTH * FRAME_HEIGHT * 2  # 38400 bytes

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
                        if current_jpeg:
                            frame = current_jpeg
                        else:
                            # Placeholder if no frame yet
                            frame = None
                    
                    if frame:
                        self.wfile.write(b'--frame\r\n')
                        self.wfile.write(b'Content-Type: image/jpeg\r\n\r\n')
                        self.wfile.write(frame)
                        self.wfile.write(b'\r\n')
                    
                    time.sleep(0.033)  # ~30 fps max
            except (BrokenPipeError, ConnectionResetError):
                pass
        elif self.path == '/':
            self.send_response(200)
            self.send_header('Content-Type', 'text/html')
            self.end_headers()
            html = b'''<!DOCTYPE html>
<html><head><title>Thermal Stream</title>
<style>body{background:#000;display:flex;justify-content:center;align-items:center;height:100vh;margin:0;}
img{max-width:100%;border:2px solid #0f0;}</style></head>
<body><img src="/stream" /></body></html>'''
            self.wfile.write(html)
        else:
            self.send_response(404)
            self.end_headers()

def start_http_server():
    try:
        server = HTTPServer(('0.0.0.0', HTTP_PORT), MJPEGHandler)
        print(f"[PI] MJPEG server on port {HTTP_PORT}")
        server.serve_forever()
    except OSError as e:
        print(f"[PI] HTTP SERVER ERROR: {e}")
        print(f"[PI] Port {HTTP_PORT} may be in use. Run: sudo fuser -k {HTTP_PORT}/tcp")
    except Exception as e:
        print(f"[PI] HTTP SERVER ERROR: {e}")
        traceback.print_exc()

# ==== RECEIVE PROCESSED FRAMES FROM LAPTOP ====
def receive_processed_frames():
    global current_jpeg, frame_count
    
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind(('0.0.0.0', PI_RECEIVE_PORT))
        sock.settimeout(5.0)
        
        print(f"[PI] Listening for processed frames on port {PI_RECEIVE_PORT}")
        
        # Buffer for large JPEG (may come in chunks)
        max_packet_size = 65535
        
        while True:
            try:
                data, addr = sock.recvfrom(max_packet_size)
                
                if len(data) > 8:
                    # Extract header
                    frame_num, jpeg_size = struct.unpack('>II', data[:8])
                    jpeg_data = data[8:]
                    
                    with jpeg_lock:
                        current_jpeg = jpeg_data
                        frame_count += 1
                    
                    if frame_count % 27 == 0:
                        print(f"[PI] Received frame {frame_num}, size {len(jpeg_data)} bytes")
            
            except socket.timeout:
                print("[PI] Waiting for frames from laptop...")
            except Exception as e:
                print(f"[PI] Receive error: {e}")
    except OSError as e:
        print(f"[PI] SOCKET ERROR: {e}")
        print(f"[PI] Port {PI_RECEIVE_PORT} may be in use. Run: sudo fuser -k {PI_RECEIVE_PORT}/tcp")
        traceback.print_exc()
    except Exception as e:
        print(f"[PI] RECEIVER ERROR: {e}")
        traceback.print_exc()


# ==== READ AND FORWARD RAW FRAMES ====
def read_and_forward():
    import random
    
    if TEST_MODE:
        print("[PI] *** TEST MODE - Using fake thermal data ***")
    else:
        print("[PI] Initializing SPI...")
        # Initialize SPI
        spi = spidev.SpiDev()
        spi.open(0, 0)
        spi.max_speed_hz = SPI_SPEED
        spi.mode = 0b11
    
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
    print("  LEPTON FORWARDER (Round-Trip Mode)")
    print("=" * 50)
    print(f"[PI] Raw data → {LAPTOP_IP}:{LAPTOP_PORT}")
    print(f"[PI] Processed frames ← port {PI_RECEIVE_PORT}")
    print(f"[PI] Dashboard → http://localhost:{HTTP_PORT}")
    print("=" * 50)
    
    # Start HTTP server thread
    http_thread = threading.Thread(target=start_http_server, daemon=True)
    http_thread.start()
    
    # Start frame receiver thread
    receiver_thread = threading.Thread(target=receive_processed_frames, daemon=True)
    receiver_thread.start()
    
    # Main thread: read SPI and forward
    try:
        read_and_forward()
    except KeyboardInterrupt:
        print("\n[PI] Shutting down...")

if __name__ == "__main__":
    main()
