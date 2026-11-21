#!/bin/bash
# =============================================================================
# START_HECOS_TRAY_LINUX.sh — launches Hecos Tray Icon (detached)
# Prefers Tray's own python_env -> Tray venv -> Core venv -> system python3
# =============================================================================

set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" &> /dev/null && pwd)"
cd "$SCRIPT_DIR" || exit 1

if [ -t 1 ]; then
    C_CYAN=$'\033[96m'; C_GREEN=$'\033[92m'; C_RED=$'\033[91m'; C_RST=$'\033[0m'
else
    C_CYAN=""; C_GREEN=""; C_RED=""; C_RST=""
fi

echo ""
echo "${C_CYAN}[ .. ]${C_RST} Starting Hecos Tray Icon..."

PY_CMD=""
if [ -x "$SCRIPT_DIR/python_env/bin/python3" ]; then
    PY_CMD="$SCRIPT_DIR/python_env/bin/python3"
elif [ -x "$SCRIPT_DIR/venv/bin/python3" ]; then
    PY_CMD="$SCRIPT_DIR/venv/bin/python3"
elif command -v python3 &> /dev/null; then
    PY_CMD="$(command -v python3)"
elif command -v python &> /dev/null; then
    PY_CMD="$(command -v python)"
fi

if [ -z "$PY_CMD" ]; then
    echo "${C_RED}[FAIL]${C_RST} Python 3 is not installed or not found."
    echo "       Run HECOS_TRAY_SETUP.sh to provision Standalone Python automatically."
    read -r -p "Press Enter to exit..."
    exit 1
fi

mkdir -p "$SCRIPT_DIR/logs"
nohup "$PY_CMD" -m tray.tray_app >> "$SCRIPT_DIR/logs/tray_crash.log" 2>&1 &

echo "${C_GREEN}[ OK ]${C_RST} Tray launched with: $PY_CMD"
echo "${C_GREEN}[ OK ]${C_RST} The icon will appear in your system tray shortly."
echo ""
sleep 1
exit 0
