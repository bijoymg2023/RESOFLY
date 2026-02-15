import subprocess
import re
import os

def log_debug(msg):
    print(f"[DEBUG-WIFI] {msg}", flush=True)

def get_wifi_devices():
    """
    Scans for Wi-Fi networks using 'iwlist wlan0 scanning'.
    Returns a list of dicts: [{'mac': 'XX:XX...', 'name': 'SSID', 'rssi': -80}]
    """
    try:
        # Check if we are on Linux
        if os.name != 'posix':
            return []

        # Run iwlist scanning
        # Requires sudo usually
        is_root = (os.geteuid() == 0)
        cmd = ["iwlist", "wlan0", "scanning"]
        if not is_root:
            cmd.insert(0, "sudo")
            
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        
        if result.returncode != 0:
            log_debug(f"Wi-Fi scan failed: {result.stderr}")
            return []
            
        output = result.stdout
        cells = output.split("Cell ")
        devices = []
        
        for cell in cells:
            mac_match = re.search(r"Address: ([0-9A-F:]{17})", cell, re.I)
            ssid_match = re.search(r'ESSID:"([^"]*)"', cell)
            signal_match = re.search(r"Signal level=(-\d+) dBm", cell)
            
            if mac_match:
                mac = mac_match.group(1)
                name = ssid_match.group(1) if ssid_match else "Hidden Network"
                rssi = int(signal_match.group(1)) if signal_match else -100
                
                devices.append({
                    "mac": mac,
                    "name": name,
                    "rssi": rssi,
                    "type": "wifi"
                })
                
        return devices
        
    except Exception as e:
        log_debug(f"Wi-Fi scan error: {e}")
        return []

if __name__ == "__main__":
    devs = get_wifi_devices()
    for d in devs:
        print(f"Found: {d['name']} [{d['mac']}] RSSI: {d['rssi']}")
