#!/bin/bash
# Hecos - Restart Tray Icon

# Navigate to the script's directory
cd "$(dirname "$0")"

echo ""
echo " [*] Restoring system tray icon..."
echo ""

# Detect Python from Hecos Core for now
if [ -d "../Hecos/venv" ] && [ -f "../Hecos/venv/bin/python" ]; then
    PY_CMD="../Hecos/venv/bin/python"
elif [ -d "/opt/hecos/venv" ] && [ -f "/opt/hecos/venv/bin/python" ]; then
    PY_CMD="/opt/hecos/venv/bin/python"
elif command -v python3 &>/dev/null; then
    PY_CMD="python3"
else
    PY_CMD="python"
fi

# Run the tray app in background (quietly)
nohup $PY_CMD -m tray.tray_app >/dev/null 2>&1 &

echo " [+] Command sent. The icon will appear shortly."
echo ""
sleep 1
exit 0
