
import sys
import time
import os
import subprocess

print("========================================")
print("   RESOFLY SENSOR VERIFICATION TOOL     ")
print("========================================")

# 1. BLUETOOTH TEST
print("\n[1/2] Testing Bluetooth Scanner...")
try:
    import bluetooth_scanner
    print("Running: bluetooth_scanner.get_bluetooth_devices()")
    devices = bluetooth_scanner.get_bluetooth_devices()
    print(f"Result: Found {len(devices)} devices.")
    for d in devices:
        print(f"  - {d}")
    
    if not devices:
        print("-> WARNING: 0 devices found. Did you run with 'sudo'?")
        print("   Try: sudo python3 backend/verify_sensors.py")
except Exception as e:
    print(f"-> ERROR: Bluetooth scan failed: {e}")

# 2. GPS TEST
print("\n[2/2] Testing GPS Module...")
GPS_PORT = "/dev/serial0"
print(f"Target Port: {GPS_PORT}")

if not os.path.exists(GPS_PORT):
    print(f"-> ERROR: Port {GPS_PORT} does not exist!")
    print("   Available serial ports:")
    os.system("ls /dev/tty* /dev/serial* 2>/dev/null")
else:
    try:
        import gps_real
        reader = gps_real.GPSReader(port=GPS_PORT)
        reader.start()
        print("GPS Reader started. Waiting 5 seconds for data stream...")
        
        for i in range(5):
            time.sleep(1)
            data = reader.get_data()
            print(f"  T+{i}s: {data}")
            if data['latitude'] != 0.0:
                print("  -> LOCK AQUIRED!")
                break
        
        reader.stop()
        if data['latitude'] == 0.0:
             print("-> WARNING: GPS is connected but returning 0.00.")
             print("   Note: GPS needs clear view of sky.")
    except Exception as e:
        print(f"-> ERROR: GPS read failed: {e}")

print("\n========================================")
print("Verification Complete.")
