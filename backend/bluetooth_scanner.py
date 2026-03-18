import subprocess
import time
import re
import sys
import shutil
import os
import pty
import select

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

        cmd = ["sudo", btmgmt_cmd, "find"]
        log_debug(f"Executing natively IN PTY: {' '.join(cmd)}")
        
        # 2. Hostile CLI tools drop output if they aren't attached to a real Terminal (TTY).
        # systemd has no TTY. We use `pty.openpty()` to construct a perfectly authentic mock terminal!
        master_fd, slave_fd = pty.openpty()
        
        proc = subprocess.Popen(cmd, stdout=slave_fd, stderr=slave_fd, close_fds=True)
        os.close(slave_fd)  # Close child's end in the parent
        
        output = ""
        start_time = time.time()
        
        # 3. Read continuously from the fake terminal for 6 seconds
        while time.time() - start_time < 6:
            # select.select waits up to 1 second for data to become readable
            r, _, _ = select.select([master_fd], [], [], 1.0)
            if master_fd in r:
                try:
                    data = os.read(master_fd, 1024)
                    if not data:
                        break # EOF
                    output += data.decode('utf-8', errors='replace')
                except OSError:
                    break # Usually EIO when child closes PTY
            
            # If the process miraculously exits early, stop reading
            if proc.poll() is not None:
                break

        # 4. Gracefully stop find (causes btmgmt to flush and exit)
        subprocess.run(["sudo", btmgmt_cmd, "stop-find"], capture_output=True)
        proc.terminate()
        proc.wait(timeout=2)
        os.close(master_fd) # Cleanup

        if not output:
             log_debug(f"Warning: Empty native stdout. The PTY returned zero bytes.")
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
