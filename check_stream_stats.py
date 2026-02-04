import cv2
import numpy as np
import sys

def check_stream(url):
    print(f"Connecting to {url}...")
    cap = cv2.VideoCapture(url)
    if not cap.isOpened():
        print("Error: Could not open stream.")
        return

    ret, frame = cap.read()
    cap.release()

    if not ret or frame is None:
        print("Error: Could not read frame.")
        return

    # Analyze frame
    height, width = frame.shape[:2]
    min_val = np.min(frame)
    max_val = np.max(frame)
    mean_val = np.mean(frame)
    
    print(f"Frame Captured: {width}x{height}")
    print(f"Min Value: {min_val}")
    print(f"Max Value: {max_val}")
    print(f"Mean Value: {mean_val:.2f}")

    if mean_val < 5:
        print("\nDIAGNOSIS: Frame is effectively BLACK.")
        print("Possible causes: Camera shutter closed, flat scene with aggressive AGC, or C++ app mapping issue.")
    else:
        print("\nDIAGNOSIS: Frame contains visual data (not black).")
        print("If dashboard is black, the issue is likely the Proxy or Browser rendering.")

if __name__ == "__main__":
    url = "http://127.0.0.1:8080/mjpeg"
    if len(sys.argv) > 1:
        url = sys.argv[1]
    check_stream(url)
