#!/bin/bash
# ─────────────────────────────────────────────────────────────────────────────
#  START_HECOS_TRAY_LINUX.sh — launches the Hecos Tray Icon (detached, no console)
# ─────────────────────────────────────────────────────────────────────────────

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" &> /dev/null && pwd)"
cd "$SCRIPT_DIR" || exit 1

echo ""
echo " [*] Starting Hecos Tray Icon..."
echo ""

# ── Detect ROOT_DIR (Hecos Core location) ────────────────────────────────────
ROOT_DIR=""
if [ -f "$SCRIPT_DIR/../Hecos/hecos/core/version" ]; then
    ROOT_DIR="$(cd "$SCRIPT_DIR/../Hecos" && pwd)"
elif [ -d "/opt/hecos" ]; then
    ROOT_DIR="/opt/hecos"
elif [ -d "$HOME/Hecos" ]; then
    ROOT_DIR="$HOME/Hecos"
fi

# ── Python Detection — find ANY python, never re-install ─────────────────────
PY_CMD=""

# Priority 1: Core venv
if [ -f "$ROOT_DIR/venv/bin/python3" ]; then
    PY_CMD="$ROOT_DIR/venv/bin/python3"

# Priority 2: python3 on PATH
elif command -v python3 &> /dev/null; then
    PY_CMD="python3"

# Priority 3: python on PATH
elif command -v python &> /dev/null; then
    PY_CMD="python"
fi

if [ -z "$PY_CMD" ]; then
    echo " [!] ERROR: Python is not installed or not found."
    echo ""
    echo " Hecos Tray requires Python 3. Please install it:"
    echo "   Ubuntu/Debian:  sudo apt install python3"
    echo "   Fedora:         sudo dnf install python3"
    echo "   Arch:           sudo pacman -S python"
    echo ""
    echo " Or run HECOS_TRAY_SETUP.sh to configure the environment."
    echo ""
    read -p "Press Enter to exit..."
    exit 1
fi

# ── Launch Tray detached (nohup + background, no console window) ─────────────
nohup $PY_CMD -m tray.tray_app > /dev/null 2>&1 &

echo " [+] Tray launched with: $PY_CMD"
echo " [+] The icon will appear in your system tray shortly."
echo ""
sleep 1
exit 0
