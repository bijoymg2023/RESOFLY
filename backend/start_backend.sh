#!/bin/bash
# Startup script for ResoFly Backend
# Tries to find and use the virtual environment regardless of where it was created

# Move to the backend directory
cd "$(dirname "$0")"

# Check for virtual environments
if [ -f "../.venv/bin/activate" ]; then
    echo "Activating venv (../.venv)"
    source ../.venv/bin/activate
elif [ -f ".venv/bin/activate" ]; then
    echo "Activating venv (.venv)"
    source .venv/bin/activate
elif [ -f "/home/team13/RESOFLY/.venv/bin/activate" ]; then
     echo "Activating venv (/home/team13/RESOFLY/.venv)"
     source /home/team13/RESOFLY/.venv/bin/activate
else
    echo "No venv found, using system python"
fi

# Ensure dependencies are installed if missing (optional safety check?)
# No, don't auto-install, it might hang boot.

# Ensure clean slate on boot (User Request)
if [ -f "clear_alerts.py" ]; then
    echo "Clearing old alerts..."
    python3 clear_alerts.py
fi

# Start the server
# Use exec to ensure signals are passed to python
echo "Starting Server on port ${PORT:-5000}..."
exec python3 server.py
