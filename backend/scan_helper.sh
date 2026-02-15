#!/bin/bash
# Robust Bluetooth Scanner for Raspberry Pi (Systemd compatible)
# Tries btmgmt first, falls back to bluetoothctl

export PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin

# Function to parse btmgmt output
scan_btmgmt() {
    # Ensure power is on
    btmgmt power on >/dev/null 2>&1
    
    # Run find with timeout
    # expected output format:
    # dev_found: 64:45:B8:AE:78:CA type LE Random rssi -31 flags 0x0000 
    # name 0x09 'iPhone'
    timeout 7s btmgmt find
}

# Function to parse bluetoothctl output (Fallback)
scan_bluetoothctl() {
    # Start scanning in background
    bluetoothctl scan on >/dev/null 2>&1 &
    SCAN_PID=$!
    
    sleep 7
    
    # Get devices
    bluetoothctl devices
    
    # Kill background scan
    kill $SCAN_PID >/dev/null 2>&1
    # stop scan explicitly
    bluetoothctl scan off >/dev/null 2>&1
}

# Try btmgmt first (detected devices are output to stdout)
OUTPUT=$(scan_btmgmt)

if [ -z "$OUTPUT" ] || [ $(echo "$OUTPUT" | wc -l) -lt 2 ]; then
    # If empty or just 1 line (header/error), try fallback
    echo "DEBUG: btmgmt failed/empty, trying bluetoothctl..." >&2
    scan_bluetoothctl
else
    echo "$OUTPUT"
fi
