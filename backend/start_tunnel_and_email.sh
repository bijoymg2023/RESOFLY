#!/bin/bash
# start_tunnel_and_email.sh

# 1. Kill old instances to be safe
pkill -f cloudflared

# 2. Start Cloudflare Quick Tunnel pointing to our Backend (Port 5000)
# We log to /home/team13/tunnel.log so the python script can find the URL
echo "Starting Cloudflare Tunnel..."
nohup cloudflared tunnel --url http://localhost:8000 > /home/team13/tunnel.log 2>&1 &

# 3. Wait for tunnel to initialize (it takes a few seconds to generate the URL)
sleep 10

# 4. Run the Email Monitor Script
# This script reads ~/tunnel.log, finds the trycloudflare.com URL, and emails it.
echo "Running Email Monitor..."
python3 monitor_tunnel.py
