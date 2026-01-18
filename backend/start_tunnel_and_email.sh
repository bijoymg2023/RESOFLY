#!/bin/bash
# start_tunnel_and_email.sh

# 1. Kill old instances
pkill -f cloudflared

# 2. Start Cloudflare Quick Tunnel
# We DO NOT use nohup here because we want to track the PID within this script.
# We redirect output to log.
echo "Starting Cloudflare Tunnel..."
rm -f /home/team13/tunnel.log
cloudflared tunnel --url http://127.0.0.1:8000 > /home/team13/tunnel.log 2>&1 &
TUNNEL_PID=$!

echo "Tunnel started with PID $TUNNEL_PID"

# 3. Wait for tunnel to initialize and generate URL
# We loop until we see the URL in the log
echo "Waiting for URL..."
MAX_RETRIES=30
COUNT=0
URL=""

while [ $COUNT -lt $MAX_RETRIES ]; do
    sleep 2
    if grep -q "trycloudflare.com" /home/team13/tunnel.log; then
        echo "URL found!"
        break
    fi
    ((COUNT++))
done

# 4. Run the Email Monitor Script
echo "Running Email Monitor..."
python3 monitor_tunnel.py

# 5. KEEP ALIVE
# This is Critical. If this script exits, systemd will kill the tunnel process.
# We wait for the tunnel process to exit (which it shouldn't unless it crashes).
wait $TUNNEL_PID
