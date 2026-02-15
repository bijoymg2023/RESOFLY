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
    
    On non-Linux systems, returns mock data for testing.
    """
    
    try:
        # 1. Find the path to btmgmt
        btmgmt_path = shutil.which("btmgmt") or "/usr/bin/btmgmt"
        if not os.path.exists(btmgmt_path):
             btmgmt_path = "/usr/sbin/btmgmt"
        
        log_debug(f"Using btmgmt path: {btmgmt_path}")

        # 2. Check if we are on Linux
        log_debug(f"Starting 7s Bluetooth LE scan (via scan_helper.sh)...")
        try:
            # Delegate complexity to shell script
            script_path = os.path.join(os.path.dirname(__file__), "scan_helper.sh")
            # Make sure it's executable
            os.chmod(script_path, 0o755)
            
            # Run scan helper (handles sudo/root/path internally)
            # Use 'sudo' only if not root, handled by caller or script? 
            # Actually, script just runs commands. If we are user, we need sudo.
            is_root = (os.geteuid() == 0)
            prefix = "" if is_root else "sudo "
            
            cmd = f"{prefix}bash {script_path}"
            output = subprocess.check_output(cmd, shell=True).decode("utf-8", errors="ignore")
            
            lines = output.split('\n')
            current_dev = {}
            devices = []
            
            log_debug(f"Scan complete. Output length: {len(output)} chars.")
            # log_debug(f"DEBUG OUTPUT: {output[:500]}...") 

            for line in lines:
                line = line.strip()
                
                # Format 1: btmgmt find
                # dev_found: 64:45:B8:AE:78:CA type LE Random rssi -31 flags 0x0000
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
                # Device 64:45:B8:AE:78:CA iPhone
                elif line.startswith("Device"):
                    parts = line.split(" ", 2)
                    if len(parts) >= 2:
                        mac = parts[1]
                        name = parts[2] if len(parts) > 2 else "Unknown"
                        # bluetoothctl devices doesn't show RSSI easily without interactive scan
                        # but scan_helper runs 'scan on' first so it populates cache.
                        # RSSI might be missing, default to -99
                        devices.append({"mac": mac, "name": name, "rssi": -99})

            if current_dev and 'mac' in current_dev:
                devices.append(current_dev)

            return _deduplicate(devices)

        except subprocess.CalledProcessError as e:
            # Shell script error (should be rare as script handles errors)
            log_debug(f"Scan script failed (Code {e.returncode}): {e}")
            # Try to read output anyway if available
            if e.output:
                log_debug(f"Script output before fail: {e.output.decode('utf-8', errors='ignore')}")
            return []

    except Exception as e:
        log_debug(f"Bluetooth scan CRITICAL error: {e}")
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
