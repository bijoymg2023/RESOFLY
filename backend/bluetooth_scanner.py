import subprocess
import time
import re
import sys
import shutil
import os

def log_debug(msg):
    print(f"[DEBUG-BT] {msg}", flush=True)


def get_bluetooth_devices():
    """
    Scans for Bluetooth LE devices using 'btmgmt find' on Linux (Pi).
    Returns a list of dicts: [{'mac': 'XX:XX...', 'name': 'Device', 'rssi': -80}]
    """
    try:
        # 1. Determine Script Path
        script_path = os.path.join(os.path.dirname(__file__), "scan_helper.sh")
        if not os.path.exists(script_path):
             log_debug(f"Scan helper missing at: {script_path}")
             return []

        # 2. Make executable (just in case)
        try:
            os.chmod(script_path, 0o755)
        except:
            pass

        # 3. Construct Command (Identical to verification script)
        cmd = ["bash", script_path]
        if os.geteuid() != 0:
            cmd.insert(0, "sudo")
        
        log_debug(f"Executing: {' '.join(cmd)}")
        
        # 4. Run Scan (No shell=True, capturing output)
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=20)
        
        output = result.stdout
        if not output:
             log_debug(f"Warning: Empty stdout. Stderr: {result.stderr}")
             return []
        
        lines = output.split('\n')
        current_dev = {}
        devices = []
        
        log_debug(f"Scan complete. Output length: {len(output)} chars.")

        for line in lines:
            line = line.strip()
            
            # Format 1: btmgmt find
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
            
            # Format 2: bluetoothctl devices (Fallback)
            elif line.startswith("Device"):
                parts = line.split(" ", 2)
                if len(parts) >= 2:
                    mac = parts[1]
                    name = parts[2] if len(parts) > 2 else "Unknown"
                    devices.append({"mac": mac, "name": name, "rssi": -99})

        if current_dev and 'mac' in current_dev:
            devices.append(current_dev)

        return _deduplicate(devices)

    except Exception as e:
        log_debug(f"Bluetooth scan CRITICAL error: {e}")
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
