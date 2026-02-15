#!/bin/bash
# Robust Bluetooth Scanner for Raspberry Pi (Systemd compatible)
# Tries btmgmt first, falls back to bluetoothctl

export PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin

# Function to parse btmgmt output
scan_btmgmt() {
    # Ensure power is on
    btmgmt power on >/dev/null 2>&1
    
    # Start find in background with line buffering
    # We pipe to 'cat' to ensure it's treated as a stream
    stdbuf -oL btmgmt find > /tmp/bt_scan.log 2>&1 &
    SCAN_PID=$!
    
    # Wait for scan duration
    sleep 7
    
    # Kill the scan
    kill $SCAN_PID >/dev/null 2>&1
    btmgmt stop-find >/dev/null 2>&1
    
    # Output the captured log
    cat /tmp/bt_scan.log
    rm /tmp/bt_scan.log
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
