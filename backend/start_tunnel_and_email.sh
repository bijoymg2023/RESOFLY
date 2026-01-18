#!/bin/bash
# start_tunnel_and_email.sh

# 1. Kill old instances
pkill -f cloudflared

# 2. Start Cloudflare Quick Tunnel (Port 5000)
# We navigate to the directory first to ensure python finds files
cd /home/team13/RESOFLY/backend

echo "Starting Cloudflare Tunnel..."
rm -f /home/team13/tunnel.log

# --url http://127.0.0.1:5000 matches the backend default
cloudflared tunnel --url http://127.0.0.1:5000 > /home/team13/tunnel.log 2>&1 &
TUNNEL_PID=$!

echo "Tunnel started with PID $TUNNEL_PID"

# 3. Wait for tunnel to initialize and generate URL
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
wait $TUNNEL_PID
