#!/bin/bash
# Robust Bluetooth Scanner for Raspberry Pi (Systemd compatible)
# Tries btmgmt first, falls back to bluetoothctl

export PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin

scan_btmgmt() {
    # Force a quick software reset of the HCI device to clear 'Busy' states
    hciconfig hci0 down >/dev/null 2>&1
    sleep 0.5
    hciconfig hci0 up >/dev/null 2>&1
    sleep 0.5
    btmgmt power on >/dev/null 2>&1
    
    rm -f /tmp/bt_scan.log
    
    # Start find in background with line buffering
    stdbuf -oL btmgmt find > /tmp/bt_scan.log 2>&1 &
    SCAN_PID=$!
    
    # Wait for scan duration
    sleep 7
    
    # Kill the scan
    kill -INT $SCAN_PID >/dev/null 2>&1
    sleep 0.5
    kill -9 $SCAN_PID >/dev/null 2>&1
    
    btmgmt stop-find >/dev/null 2>&1
    
    # Output the captured log
    cat /tmp/bt_scan.log 2>/dev/null
}

scan_bluetoothctl() {
    # Fallback
    bluetoothctl scan on >/dev/null 2>&1 &
    SCAN_PID=$!
    sleep 7
    bluetoothctl devices
    kill $SCAN_PID >/dev/null 2>&1
    bluetoothctl scan off >/dev/null 2>&1
}

OUTPUT=$(scan_btmgmt)

if [ -z "$OUTPUT" ] || [ $(echo "$OUTPUT" | wc -l) -lt 2 ]; then
    echo "DEBUG: btmgmt failed/empty, trying bluetoothctl..." >&2
    scan_bluetoothctl
else
    echo "$OUTPUT"
fi
