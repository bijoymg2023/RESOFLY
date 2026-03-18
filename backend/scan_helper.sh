#!/bin/bash
# Robust Bluetooth Scanner for Raspberry Pi (Systemd compatible)
# Tries btmgmt first, falls back to bluetoothctl

export PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin

scan_btmgmt() {
    # Force a quick software reset of the HCI device to clear 'Busy' states
    hciconfig hci0 down >/dev/null 2>&1
    hciconfig hci0 up >/dev/null 2>&1
    
    # We run btmgmt find with a strict timeout so it doesn't need stdbuf or tmp files
    # Instead of piping, we let it run natively and timeout kills it after 6 seconds
    timeout 6s btmgmt find 2>&1
}

scan_bluetoothctl() {
    # Fallback to bluetoothctl list of discovered devices
    timeout 6s bluetoothctl scan on >/dev/null 2>&1
    bluetoothctl devices
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
