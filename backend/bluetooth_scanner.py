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
    Avoids bash scripts and temporary files to ensure systemd robustness.
    """
    try:
        # Determine paths natively since systemd may strip /usr/sbin from PATH
        hciconfig_cmd = subprocess.run(["which", "hciconfig"], capture_output=True, text=True).stdout.strip() or "hciconfig"
        btmgmt_cmd = subprocess.run(["which", "btmgmt"], capture_output=True, text=True).stdout.strip() or "btmgmt"

        # 1. Force hardware reset purely with crucial delays
        subprocess.run(["sudo", hciconfig_cmd, "hci0", "down"], capture_output=True)
        time.sleep(1)
        subprocess.run(["sudo", hciconfig_cmd, "hci0", "up"], capture_output=True)
        time.sleep(0.5)
        subprocess.run(["sudo", btmgmt_cmd, "power", "on"], capture_output=True)

        # Add stdbuf -oL to force libc line buffering under systemd pipes.
        # Otherwise <4096 bytes are trapped and memory-wiped when the process dies.
        stdbuf_cmd = subprocess.run(["which", "stdbuf"], capture_output=True, text=True).stdout.strip() or "stdbuf"
        cmd = ["sudo", stdbuf_cmd, "-oL", btmgmt_cmd, "find"]
        log_debug(f"Executing natively: {' '.join(cmd)}")
        
        # 2. Start find process natively
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        
        # Wait for 6 seconds of scanning
        time.sleep(6)
        
        # 3. Gracefully stop find (causes btmgmt to flush and exit)
        subprocess.run(["sudo", btmgmt_cmd, "stop-find"], capture_output=True)
        
        # 4. Read output
        try:
            output, stderr = proc.communicate(timeout=2)
        except subprocess.TimeoutExpired:
            log_debug("Stop-find failed, forcing termination.")
            # Send SIGTERM first instead of SIGKILL to allow C flush
            proc.terminate()
            try:
                output, stderr = proc.communicate(timeout=1)
            except:
                proc.kill()
                output, stderr = proc.communicate()

        if not output:
             log_debug(f"Warning: Empty native stdout. Stderr: {stderr}")
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
