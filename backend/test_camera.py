import time
import sys
import os

def check_requirements():
    print("--- 1. Checking Essentials ---")
    
    # Check SPI Device
    if not os.path.exists("/dev/spidev0.0"):
        print("[FAIL] /dev/spidev0.0 does not exist.")
        print("Enable SPI in raspi-config: Interface Options -> SPI")
        return False
    print("[PASS] /dev/spidev0.0 exists.")
    
    # Check Buffer Size
    try:
        with open("/sys/module/spidev/parameters/bufsiz", "r") as f:
            bufsiz = int(f.read().strip())
        print(f"[INFO] Current SPI buffer size: {bufsiz}")
        if bufsiz < 65536:
            print("[FAIL] Buffer size too small for Lepton 3.5!")
            print("Run this command and REBOOT:")
            print("sudo sed -i '$s/$/ spidev.bufsiz=65536/' /boot/cmdline.txt")
            return False
    except FileNotFoundError:
        print("[WARN] Could not read bufsiz parameter. Assuming it might be okay, but proceed with caution.")
    print("[PASS] Buffer size check passed or skipped.")
    
    # Check Library
    try:
        import spidev
        import numpy as np
        import cv2
    except ImportError as e:
        print(f"[FAIL] Missing Python Library: {e}")
        print("Run: pip install spidev numpy opencv-python-headless")
        return False
    print("[PASS] Python libraries found.")
    return True

def test_stream():
    print("\n--- 2. Testing Camera Stream ---")
    import spidev
    import numpy as np
    import cv2
    
    spi = spidev.SpiDev()
    spi.open(0, 0)
    spi.max_speed_hz = 16000000
    spi.mode = 0b11
    
    print("Capturing frames (Ctrl+C to stop)...")
    success_count = 0
    
    try:
        for i in range(10): # Try 10 frames
            print(f"Attempt {i+1}...", end=" ")
            
            # Reset sync limit
            time.sleep(0.2)
            
            # Read
            data = spi.readbytes(39360)
            
            # Simple VoSPI Validation
            # Packet 20 of Segment X should have a specific ID
            raw = np.frombuffer(bytearray(data), dtype=np.uint8)
            packets = raw.reshape(240, 164)
            
            # Check packet numbers (second byte of each packet should increment)
            # Just check the first few packets
            p0 = packets[0, 1]
            p1 = packets[1, 1]
            
            if p0 != 0 or p1 != 1:
                print(f"[FAIL] VoSPI Sync Error (Expected Pkts 0,1 got {p0},{p1})")
                
                # Check for all zeroes (Wiring issue)
                if np.all(raw == 0):
                    print("       -> ALL ZEROS RECEIVED. Check MISO/CLK wiring!")
                # Check for all ones (Wiring issue)
                elif np.all(raw == 255):
                    print("       -> ALL ONES RECEIVED. Check Wiring!")
                
                continue
                
            print(f"[SUCCESS] Packet Sync Good. Frame Data Size: {len(data)}")
            success_count += 1
            
            # Parse & Save one valid frame
            payload = packets[:, 4:].flatten().view(np.uint16).byteswap().reshape(120, 160)
            norm = cv2.normalize(payload, None, 0, 255, cv2.NORM_MINMAX, dtype=cv2.CV_8U)
            color = cv2.applyColorMap(norm, cv2.COLORMAP_INFERNO)
            cv2.imwrite("test_thermal_success.jpg", color)
            print("       -> Saved 'test_thermal_success.jpg'")
            break
            
    except KeyboardInterrupt:
        pass
    finally:
        spi.close()
        
    if success_count > 0:
        print("\n[RESULT] PASSED: Camera is communicating!")
    else:
        print("\n[RESULT] FAILED: Could not sync with camera.")

if __name__ == "__main__":
    if check_requirements():
        test_stream()
