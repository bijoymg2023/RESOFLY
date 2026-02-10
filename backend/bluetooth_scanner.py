import subprocess
import time
import re
import sys
import shutil

def get_bluetooth_devices():
    """
    Scans for Bluetooth LE devices using 'btmgmt find' on Linux (Pi).
    Returns a list of dicts: [{'mac': 'XX:XX...', 'name': 'Device', 'rssi': -80}]
    
    On non-Linux systems, returns mock data for testing.
    """
    
    try:
        # 1. Find the path to btmgmt (it might be in /usr/bin or /usr/sbin)
        btmgmt_path = shutil.which("btmgmt") or "/usr/bin/btmgmt"
        if not os.path.exists(btmgmt_path):
             btmgmt_path = "/usr/sbin/btmgmt"

        # 2. Check if we are on Linux
        if sys.platform != "linux" or not os.path.exists(btmgmt_path):
            return [
                {"mac": "XX:XX:XX:XX:XX:01", "name": "Target Phone", "rssi": -65},
                {"mac": "AA:BB:CC:DD:EE:FF", "name": "Unknown Beacon", "rssi": -88},
                {"mac": "11:22:33:44:55:66", "name": "Headphones", "rssi": -72}
            ]

        # 3. Ensure Bluetooth is powered on
        try:
            subprocess.run(f"{btmgmt_path} power on", shell=True, timeout=2, capture_output=True)
        except:
            pass # Non-critical if it fails

        # 4. Run the scan
        try:
            cmd = f"timeout 7s {btmgmt_path} find"
            output = subprocess.check_output(cmd, shell=True).decode("utf-8", errors="ignore")
            
            lines = output.split('\n')
            current_dev = {}
            devices = []

            for line in lines:
                line = line.strip()
                if "dev_found" in line:
                    if current_dev and 'mac' in current_dev:
                        devices.append(current_dev)
                    current_dev = {}
                    
                    mac_match = re.search(r"dev_found:\s+([0-9A-F:]{17})", line, re.I)
                    rssi_match = re.search(r"rssi\s+(-?\d+)", line, re.I)
                    
                    if mac_match: current_dev['mac'] = mac_match.group(1)
                    if rssi_match: current_dev['rssi'] = int(rssi_match.group(1))
                        
                elif "name" in line and current_dev:
                    name_match = re.search(r"name\s+(.*)", line, re.I)
                    if name_match: current_dev['name'] = name_match.group(1)
            
            if current_dev and 'mac' in current_dev:
                devices.append(current_dev)

            return _deduplicate(devices)
        except subprocess.CalledProcessError as e:
            print(f"Scan process error: {e}")
            return []

    except Exception as e:
        print(f"Bluetooth scan error: {e}")
        return []

def _deduplicate(devices):
    unique_devs = {}
    for d in devices:
        mac = d['mac']
        # Keep strongest signal
        if mac not in unique_devs or d.get('rssi', -100) > unique_devs[mac].get('rssi', -100):
            unique_devs[mac] = d
    # Sort by strength
    return sorted(list(unique_devs.values()), key=lambda x: x['rssi'], reverse=True)

if __name__ == "__main__":
    print("Scanning for Bluetooth devices...")
    devs = get_bluetooth_devices()
    for d in devs:
        print(f"Found: {d.get('name', 'Unknown')} [{d.get('mac')}] | RSSI: {d.get('rssi')} dBm")
