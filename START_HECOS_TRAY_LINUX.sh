#!/bin/bash
# Hecos - Restart Tray Icon

# Navigate to the script's directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" &> /dev/null && pwd)"
cd "$SCRIPT_DIR" || exit 1

echo ""
echo " [*] Restoring system tray icon..."
echo ""

# Detect ROOT_DIR (where Hecos Core is installed)
if [ -d "$SCRIPT_DIR/../Hecos" ]; then
    ROOT_DIR="$(cd "$SCRIPT_DIR/../Hecos" && pwd)"
elif [ -d "/opt/hecos" ]; then
    ROOT_DIR="/opt/hecos"
else
    # Fallback to assuming they are in the same dir
    ROOT_DIR="$(cd "$SCRIPT_DIR/../Hecos" 2>/dev/null && pwd)"
fi

# Detect Python
PY_CMD=""
if [ -f "$ROOT_DIR/venv/bin/python3" ]; then
    PY_CMD="$ROOT_DIR/venv/bin/python3"
elif command -v python3 &>/dev/null; then
    PY_CMD="python3"
elif command -v python &>/dev/null; then
    PY_CMD="python"
fi

if [ -z "$PY_CMD" ]; then
    echo -e "\e[31m[!] ERROR: Python is not installed or not found.\e[0m"
    echo ""
    echo "Hecos Tray requires Python to run."
    echo "Please run HECOS_SETUP_WIZARD.sh to configure the Python environment."
    echo ""
    read -p "Press Enter to exit..."
    exit 1
fi

# Run the tray app in background (quietly)
nohup $PY_CMD -m tray.tray_app >/dev/null 2>&1 &

echo " [+] Command sent. The icon will appear shortly."
echo ""
sleep 1
exit 0
