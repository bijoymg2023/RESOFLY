#!/usr/bin/env python3
"""
Thermal Server - Runs on Laptop
Receives raw thermal frames from Pi via UDP, processes them, and serves MJPEG stream.
"""

import socket
import struct
import threading
import time
import numpy as np
import cv2
from flask import Flask, Response, render_template_string

# ==== CONFIGURATION ====
UDP_IP = "0.0.0.0"          # Listen on all interfaces
UDP_PORT = 5005             # Must match Pi forwarder
HTTP_PORT = 8080            # Web server port

# Lepton 3.5 specs
FRAME_WIDTH = 80
FRAME_HEIGHT = 60
FRAME_SIZE_BYTES = FRAME_WIDTH * FRAME_HEIGHT * 2  # 9600 bytes

# ==== GLOBALS ====
current_frame = None
frame_lock = threading.Lock()
frame_count = 0
last_frame_time = 0

# ==== FLASK APP ====
app = Flask(__name__)

HTML_TEMPLATE = '''
<!DOCTYPE html>
<html>
<head>
    <title>Thermal Stream</title>
    <style>
        body {
            background: #0a0a0a;
            color: #00ff88;
            font-family: monospace;
            display: flex;
            flex-direction: column;
            align-items: center;
            padding: 20px;
        }
        h1 { color: #00ff88; }
        img {
            border: 2px solid #00ff88;
            max-width: 100%;
            image-rendering: pixelated;
        }
        .stats {
            margin-top: 10px;
            padding: 10px;
            background: #1a1a1a;
            border: 1px solid #333;
        }
    </style>
</head>
<body>
    <h1>🔥 THERMAL STREAM</h1>
    <img src="/stream" width="640" height="480" />
    <div class="stats">
        <p>Stream: /stream (MJPEG)</p>
        <p>Resolution: 80x60 (scaled 8x)</p>
    </div>
</body>
</html>
'''

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route('/stream')
def video_stream():
    return Response(generate_mjpeg(),
                    mimetype='multipart/x-mixed-replace; boundary=frame')

def generate_mjpeg():
    """Generate MJPEG frames for streaming."""
    global current_frame
    
    while True:
        with frame_lock:
            if current_frame is not None:
                frame = current_frame.copy()
            else:
                # No frame yet, send placeholder
                frame = np.zeros((FRAME_HEIGHT * 8, FRAME_WIDTH * 8, 3), dtype=np.uint8)
                cv2.putText(frame, "WAITING FOR DATA...", (50, 240),
                           cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 136), 2)
        
        # Encode as JPEG
        _, jpeg = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 90])
        
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + jpeg.tobytes() + b'\r\n')
        
        time.sleep(0.03)  # ~30 fps output

def process_frame(raw_data):
    """
    Process raw 16-bit thermal data into colored image.
    """
    global current_frame, frame_count, last_frame_time
    
    # Convert bytes to numpy array
    frame_16bit = np.frombuffer(raw_data, dtype='>u2')  # Big-endian uint16
    frame_16bit = frame_16bit.reshape((FRAME_HEIGHT, FRAME_WIDTH))
    
    # Normalize to 8-bit
    frame_norm = cv2.normalize(frame_16bit, None, 0, 255, cv2.NORM_MINMAX)
    frame_8bit = frame_norm.astype(np.uint8)
    
    # Apply colormap (INFERNO is good for thermal)
    frame_colored = cv2.applyColorMap(frame_8bit, cv2.COLORMAP_INFERNO)
    
    # Scale up 8x for visibility
    frame_scaled = cv2.resize(frame_colored, (FRAME_WIDTH * 8, FRAME_HEIGHT * 8),
                              interpolation=cv2.INTER_NEAREST)
    
    # Update global frame
    with frame_lock:
        current_frame = frame_scaled
        frame_count += 1
        last_frame_time = time.time()

def udp_receiver():
    """
    Receive raw frames from Pi via UDP.
    """
    global frame_count
    
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((UDP_IP, UDP_PORT))
    sock.settimeout(5.0)
    
    print(f"[SERVER] Listening for thermal data on UDP port {UDP_PORT}...")
    
    expected_packet_size = 8 + FRAME_SIZE_BYTES  # 8-byte header + frame data
    
    while True:
        try:
            data, addr = sock.recvfrom(expected_packet_size + 100)
            
            if len(data) >= expected_packet_size:
                # Extract header
                pi_frame_num, timestamp = struct.unpack('>II', data[:8])
                raw_frame = data[8:8 + FRAME_SIZE_BYTES]
                
                # Process the frame
                process_frame(raw_frame)
                
                if frame_count % 27 == 0:
                    print(f"[SERVER] Received frame {pi_frame_num} from {addr[0]}")
            else:
                print(f"[SERVER] Incomplete packet: {len(data)} bytes")
        
        except socket.timeout:
            print("[SERVER] Waiting for data from Pi...")
        except Exception as e:
            print(f"[SERVER] Error: {e}")

def main():
    print("=" * 50)
    print("  THERMAL SERVER - Laptop Side")
    print("=" * 50)
    print(f"[SERVER] HTTP server on port {HTTP_PORT}")
    print(f"[SERVER] UDP listener on port {UDP_PORT}")
    print(f"[SERVER] Open http://localhost:{HTTP_PORT} in browser")
    print("=" * 50)
    
    # Start UDP receiver in background thread
    receiver_thread = threading.Thread(target=udp_receiver, daemon=True)
    receiver_thread.start()
    
    # Start Flask server
    app.run(host='0.0.0.0', port=HTTP_PORT, threaded=True)

if __name__ == "__main__":
    main()
