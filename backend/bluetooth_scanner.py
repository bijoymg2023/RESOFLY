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
    
    # Check if we are on Linux/Pi
    if sys.platform != "linux" or not shutil.which("btmgmt"):
        # Mock Data for testing on MacOS/Windows
        return [
            {"mac": "XX:XX:XX:XX:XX:01", "name": "Target Phone", "rssi": -65},
            {"mac": "AA:BB:CC:DD:EE:FF", "name": "Unknown Beacon", "rssi": -88},
            {"mac": "11:22:33:44:55:66", "name": "Headphones", "rssi": -72}
        ]

    try:
        # Run btmgmt find (needs sudo usually, make sure user has permissions or run typical scan)
        # Using timeout to stop scanning after 5 seconds
        cmd = "sudo timeout 5s btmgmt find"
        
        # On some systems 'hcitool lescan' might be used, but btmgmt is better for RSSI
        # If btmgmt fails, we might need another approach.
        
        output = subprocess.check_output(cmd, shell=True).decode("utf-8", errors="ignore")
        
        devices = []
        
        # Regex to parse btmgmt output
        # Example: hci0 dev_found: 59:90:3A:C7:60:02 type LE Random rssi -66 flags 0x0000 
        #          AD flags 0x06 
        #          name Galaxy S21
        
        # Simplify: just look for blocks
        lines = output.split('\n')
        current_dev = {}
        
        for line in lines:
            line = line.strip()
            if "dev_found" in line:
                # Save previous if exists
                if current_dev and 'mac' in current_dev:
                    devices.append(current_dev)
                
                current_dev = {}
                
                # Extract MAC and RSSI
                mac_match = re.search(r"dev_found:\s+([0-9A-F:]{17})", line, re.I)
                rssi_match = re.search(r"rssi\s+(-?\d+)", line, re.I)
                
                if mac_match:
                    current_dev['mac'] = mac_match.group(1)
                if rssi_match:
                    current_dev['rssi'] = int(rssi_match.group(1))
                    
            elif "name" in line and current_dev:
                # Extract Name
                name_match = re.search(r"name\s+(.*)", line, re.I)
                if name_match:
                    current_dev['name'] = name_match.group(1)
        
        # Append last one
        if current_dev and 'mac' in current_dev:
            devices.append(current_dev)
            
        # Deduplicate by MAC, keeping strongest signal
        unique_devs = {}
        for d in devices:
            mac = d['mac']
            if mac not in unique_devs or d.get('rssi', -100) > unique_devs[mac].get('rssi', -100):
                unique_devs[mac] = d
        
        return list(unique_devs.values())

    except Exception as e:
        print(f"Bluetooth scan error: {e}")
        return []

if __name__ == "__main__":
    print("Scanning for Bluetooth devices...")
    devs = get_bluetooth_devices()
    for d in devs:
        print(f"Found: {d.get('name', 'Unknown')} [{d.get('mac')}] | RSSI: {d.get('rssi')} dBm")
