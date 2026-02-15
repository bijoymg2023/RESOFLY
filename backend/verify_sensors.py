
import sys
import time
import os
import subprocess

# --- VENV AUTO-SWITCH ---
# Check if running in a venv (sys.prefix != sys.base_prefix)
# And if not, check common venv locations and restart.
if sys.prefix == sys.base_prefix:
    possible_venvs = [
        os.path.join(os.path.dirname(__file__), "../.venv"),      # relative from backend/
        os.path.join(os.path.dirname(__file__), ".venv"),         # inside backend/
        "/home/team13/RESOFLY/.venv"                              # absolute
    ]
    for venv_path in possible_venvs:
        python_bin = os.path.join(venv_path, "bin", "python3")
        if os.path.exists(python_bin):
            print(f"-> Switching to virtual environment: {python_bin}")
            # Re-execute with venv python
            os.execv(python_bin, [python_bin] + sys.argv)

print("========================================")
print("   RESOFLY SENSOR VERIFICATION TOOL     ")
print("========================================")

# 1. BLUETOOTH TEST
print("\n[1/2] Testing Bluetooth Scanner...")
try:
    import bluetooth_scanner
    print(f"Running as UID: {os.geteuid()}")
    print(f"Current PATH: {os.environ.get('PATH')}")

    print("\n--- Testing Bluetooth Scanner (via scan_helper.sh) ---")
    try:
        script_path = os.path.join(os.path.dirname(__file__), "scan_helper.sh")
        if not os.path.exists(script_path):
             print(f"ERROR: scan_helper.sh NOT FOUND at {script_path}")
        else:
             print(f"Script found at: {script_path}")
             # Run it
             cmd = ["bash", script_path]
             if os.geteuid() != 0:
                 cmd.insert(0, "sudo")
             
             print(f"Executing: {' '.join(cmd)}")
             result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
             
             print(f"Exit Code: {result.returncode}")
             print(f"STDOUT:\n{result.stdout}")
             print(f"STDERR:\n{result.stderr}")
             
             if not result.stdout.strip():
                 print("WARNING: Output was empty! This explains 'IDLE' dashboard.")
    except Exception as e:
        print(f"Error running scan helper: {e}")

    # Also test via Python module
    print("\n--- Testing Python Wrapper (bluetooth_scanner.py) ---")
    try:
        devices = bluetooth_scanner.get_bluetooth_devices()
        print(f"Found {len(devices)} devices via Python wrapper.")
        for d in devices:
            print(f"  - {d}")
        
        if not devices:
            print("-> WARNING: 0 devices found. Did you run with 'sudo'?")
            print("   Try: sudo python3 backend/verify_sensors.py")
    except Exception as e:
        print(f"Python Wrapper Error: {e}")

    print("\n[2/3] Testing Wi-Fi Scanner (New Feature)...")
    try:
        # Check if iwlist exists
        if not shutil.which("iwlist"):
             print("WARNING: 'iwlist' not found. Is it installed? (sudo apt install wireless-tools)")
        else:
             print("Running: sudo iwlist wlan0 scanning")
             res = subprocess.run(["sudo", "iwlist", "wlan0", "scanning"], capture_output=True, text=True)
             if res.returncode != 0:
                 print(f"Wi-Fi Scan Error (Code {res.returncode}):\n{res.stderr}")
             else:
                 output = res.stdout
                 cells = output.split("Cell ")
                 wifi_devs = []
                 for cell in cells:
                     ssid_match = re.search(r'ESSID:"([^"]+)"', cell)
                     signal_match = re.search(r'Signal level=(-\d+) dBm', cell)
                     if ssid_match and signal_match:
                         wifi_devs.append({
                             "ssid": ssid_match.group(1),
                             "rssi": int(signal_match.group(1))
                         })
                 
                 print(f"Found {len(wifi_devs)} Wi-Fi Networks:")
                 for w in wifi_devs[:5]: # Show top 5
                     print(f"  - {w['ssid']} ({w['rssi']} dBm)")
    except Exception as e:
        print(f"Wi-Fi Test Failed: {e}")

except Exception as e:
    print(f"-> ERROR: Bluetooth scan failed: {e}")

# 2. GPS TEST
print("\n[3/3] Testing GPS Module...") # Changed from [2/2] to [3/3]
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
