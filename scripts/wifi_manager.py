import subprocess
import json
import time
import os
import sys

# Configuration
CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'wifi_config.json')
LOG_TAG = "WiFi-Switcher"

def log(message):
    print(f"[{LOG_TAG}] {message}")
    sys.stdout.flush()

def load_config():
    try:
        with open(CONFIG_FILE, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        log(f"Error: Config file not found at {CONFIG_FILE}")
        return []
    except json.JSONDecodeError:
        log(f"Error: Invalid JSON in {CONFIG_FILE}")
        return []

def get_available_networks():
    """Scans for available networks and returns a list of dictionaries."""
    try:
        # Run nmcli to list wifi networks
        # Fields: SSID, SIGNAL, BARS
        # We use -t for tabular output (colon separated) and -f to specify fields
        cmd = ['nmcli', '-t', '-f', 'SSID,SIGNAL,BARS', 'device', 'wifi', 'list']
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        
        networks = {}
        for line in result.stdout.splitlines():
            # nmcli -t uses ':' as separator. Escaped colons are '\:'
            # We can use a regex or a simple split if we assume no colons in SSID for simplicity, 
            # or better, use the --fields specific sizing or just csv?
            # actually nmcli -t escapes field separators. 
            parts = line.split(':')
            if len(parts) >= 2:
                # Naive splitting. Robust parsing would handle escaped colons.
                # For now, let's assume standard SSIDs.
                ssid = parts[0].strip()
                try:
                    signal = int(parts[1].strip())
                except ValueError:
                    signal = 0
                
                if ssid: 
                    # If we already saw this SSID, only update if signal is better
                    if ssid not in networks or signal > networks[ssid]:
                        networks[ssid] = signal
        
        # Convert back to list of dicts
        return [{'ssid': s, 'signal': v} for s, v in networks.items()]
    except subprocess.CalledProcessError as e:
        log(f"Error scanning for networks: {e}")
        return []

def connect_to_network(ssid, password):
    log(f"Attempting to connect to '{ssid}'...")
    try:
        # Check if the connection already exists
        cmd_check = ['nmcli', 'connection', 'show', ssid]
        subprocess.run(cmd_check, capture_output=True, check=False) # Don't check return code, it fails if not exists
        
        # If connection exists, just bring it up. If not, add and connect.
        # Actually, 'device wifi connect' handles both (creates if missing, connects if exists)
        # But we need to pass password if it's new.
        
        cmd_connect = ['nmcli', 'device', 'wifi', 'connect', ssid, 'password', password]
        subprocess.run(cmd_connect, check=True, capture_output=True, text=True)
        log(f"Successfully connected to '{ssid}'")
        return True
    except subprocess.CalledProcessError as e:
        log(f"Failed to connect to '{ssid}'. Error: {e.stderr}")
        return False

def main():
    log("Starting Wi-Fi Auto-Switcher...")
    
    known_networks = load_config()
    if not known_networks:
        log("No known networks configured. Exiting.")
        return

    log(f"Loaded {len(known_networks)} known networks.")

    available_networks = get_available_networks()
    if not available_networks:
        log("No Wi-Fi networks found during scan.")
        return

    log(f"Found {len(available_networks)} available networks.")

    # Filter available networks to only those in our config
    candidates = []
    for net in available_networks:
        for known in known_networks:
            if net['ssid'] == known['ssid']:
                candidates.append({
                    'ssid': net['ssid'],
                    'signal': net['signal'],
                    'password': known['password']
                })
                break
    
    if not candidates:
        log("No known networks are currently available.")
        return

    # Sort by signal strength (descending)
    candidates.sort(key=lambda x: x['signal'], reverse=True)
    
    # Sort by signal strength (descending)
    candidates.sort(key=lambda x: x['signal'], reverse=True)
    
    for candidate in candidates:
        ssid = candidate['ssid']
        signal = candidate['signal']
        password = candidate['password']
        
        log(f"Attempting to connect to '{ssid}' (Signal: {signal}%)...")
        
        success = connect_to_network(ssid, password)
        if success:
            # Check for actual internet connectivity
            log(f"Connected to '{ssid}'. Checking internet connectivity...")
            # Give it a moment for DHCP
            time.sleep(5) 
            if check_internet():
                log(f"Internet connection verified on '{ssid}'. Setup complete.")
                return
            else:
                log(f"Connected to '{ssid}' but no internet. Disconnecting and trying next candidate.")
                # Optional: Disconnect explicitly if needed, or just let next connect handle it.
                # nmcli connection down id <ssid>
                subprocess.run(['nmcli', 'connection', 'down', ssid], capture_output=True)
        else:
            log(f"Failed to connect to '{ssid}'. Trying next candidate.")
    
    log("Exhausted all known networks. No internet connection established.")

def check_internet():
    """Pings a reliable server (Google DNS) to check for internet connectivity."""
    try:
        # Ping 8.8.8.8 once with a 2 second timeout
        subprocess.run(['ping', '-c', '1', '-W', '2', '8.8.8.8'], check=True, capture_output=True)
        return True
    except subprocess.CalledProcessError:
        return False

if __name__ == "__main__":
    # Wait a bit for network service to be fully up if running immediately at boot
    time.sleep(10) 
    main()
