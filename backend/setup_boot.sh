#!/bin/bash

# setup_boot.sh
# CONFIGURATION - CHANGE THIS TO YOUR USERNAME IF DIFFERENT
PI_USER="pi"
APP_DIR="/home/$PI_USER/thermo-vision-hub/backend"
PYTHON_EXEC="$APP_DIR/.venv/bin/python"

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}=== RESOFLY Auto-Start Setup ===${NC}"

# 1. Create the Backend Service
echo "Creating ResoFly Backend Service..."
cat <<EOF | sudo tee /etc/systemd/system/resofly.service
[Unit]
Description=RESOFLY Backend Service
After=network.target network-online.target
Wants=network-online.target

[Service]
User=$PI_USER
WorkingDirectory=$APP_DIR
# Use the Virtual Environment Python
ExecStart=$PYTHON_EXEC server.py
Restart=always
RestartSec=10
Environment=PORT=8000
# Ensure Python output is flushed immediately so logs are visible
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
EOF

# 2. Create the Tunnel Service
echo "Creating Cloudflare Tunnel Service..."
# Note: For permanent recurring tunnel without auth, we use 'tunnel --url'. 
# Ideally, user should use 'cloudflared service install', but this manual service is easier for "Zero Config".

if ! command -v cloudflared &> /dev/null; then
    if [ -f "./cloudflared" ]; then
        CLOUDFLARED_EXEC="$APP_DIR/cloudflared"
    else
        echo "Error: cloudflared not found. Please run setup_tunnel.sh first to download it."
        exit 1
    fi
else
    CLOUDFLARED_EXEC=$(which cloudflared)
fi

cat <<EOF | sudo tee /etc/systemd/system/resofly-tunnel.service
[Unit]
Description=RESOFLY Cloudflare Tunnel
After=network.target resofly.service
# Wait for the app to actually be up
StartLimitIntervalSec=0

[Service]
User=$PI_USER
Restart=always
RestartSec=10
# This creates a Quick Tunnel every time. 
# It's better for the user to check the logs to get the URL, or setup a real tunnel.
# But for "Just Works", we execute it. The challenge is GETTING the URL.
# We will write the URL to a file in the user's home dir.
ExecStart=/bin/bash -c '$CLOUDFLARED_EXEC tunnel --url http://localhost:8000 2>&1 | tee /home/$PI_USER/tunnel.log'

[Install]
WantedBy=multi-user.target
EOF


# 2. Monitor Service (Starts AFTER the tunnel)
echo "Creating Notifier Service..."
cat <<EOF | sudo tee /etc/systemd/system/resofly-notify.service
[Unit]
Description=RESOFLY Notification Service
After=resofly-tunnel.service

[Service]
User=$PI_USER
WorkingDirectory=$APP_DIR
ExecStart=$PYTHON_EXEC monitor_tunnel.py
Restart=on-failure
RestartSec=30

[Install]
WantedBy=multi-user.target
EOF

# 3. Reload and Enable
echo -e "${BLUE}Reloading SystemD...${NC}"
sudo systemctl daemon-reload

echo -e "${BLUE}Enabling Services to start on BOOT...${NC}"
sudo systemctl enable resofly.service
sudo systemctl enable resofly-tunnel.service
sudo systemctl enable resofly-notify.service

# 4. Start them now
echo -e "${BLUE}Starting Services now...${NC}"
sudo systemctl start resofly-notify.service # The others are already running or will be started

echo -e "${GREEN}DONE!${NC}"
echo "------------------------------------------------"
echo "1. The App will now start automatically when you plug in power."
echo "2. The Tunnel logs are being saved to: /home/$PI_USER/tunnel.log"
echo "3. The Notification service will read that log and EMAIL/SMS you the link."
