#!/bin/bash
# ─────────────────────────────────────────────────────────────────────────────
#  HECOS TRAY SETUP (LINUX) — launched from C:/Hecos-Tray
#  Handles:
#    1. Detecting Tray and Core directories (versioned folder support)
#    2. Detecting ANY available Python (no re-install if already present)
#    3. Checking/installing Tray-only dependencies from pyproject.toml
#    4. Offering user choice: Setup Wizard OR launch Tray directly
#    5. Downloading Core from GitHub if not found
# ─────────────────────────────────────────────────────────────────────────────

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" &> /dev/null && pwd)"
TRAY_DIR="$SCRIPT_DIR"
TRAY_WARN=""

# ── Determine ROOT_DIR (Hecos Core) ──────────────────────────────────────────
ROOT_DIR=""
TRAY_CANONICAL="$(dirname "$TRAY_DIR")/Hecos"

if [ -f "$SCRIPT_DIR/../../../hecos/core/version" ]; then
    ROOT_DIR="$(cd "$SCRIPT_DIR/../../.." && pwd)"
elif [ -f "$SCRIPT_DIR/../Hecos/hecos/core/version" ]; then
    ROOT_DIR="$(cd "$SCRIPT_DIR/../Hecos" && pwd)"
elif [ -f "/opt/hecos/hecos/core/version" ]; then
    ROOT_DIR="/opt/hecos"
else
    # Derive from tray path: strip -Tray* suffix to get the Core sibling
    ROOT_DIR="${SCRIPT_DIR%%-Tray*}"
    [ "$ROOT_DIR" = "$SCRIPT_DIR" ] && ROOT_DIR="$(dirname "$SCRIPT_DIR")/Hecos"
fi

CORE_FOUND=0
[ -f "$ROOT_DIR/hecos/core/version" ] && CORE_FOUND=1

echo "=============================================================================="
echo "                     HECOS TRAY SETUP (LINUX)"
echo "=============================================================================="
echo ""

# ── 1. SYSTEM CHECK ──────────────────────────────────────────────────────────
echo "[SYSTEM CHECK]"
echo "[OK] Tray found at: $TRAY_DIR"
if [ "$TRAY_WARN" = "1" ]; then
    echo "  [!] WARNING: Tray folder has a version suffix. Rename it to: $TRAY_CANONICAL"
fi

if [ "$CORE_FOUND" = "1" ]; then
    echo "[OK] Core found at: $ROOT_DIR"
else
    echo "[-] Core NOT found — will offer download below."
fi
echo ""

# ── 2. PYTHON DETECTION — find ANY python, never re-install if already present ─
echo "[PYTHON DETECTION]"
PYTHON_CMD=""
PYTHON_LOC=""

if [ -f "$ROOT_DIR/venv/bin/python3" ]; then
    PYTHON_CMD="$ROOT_DIR/venv/bin/python3"
    PYTHON_LOC="Virtual Environment ($ROOT_DIR/venv)"
elif command -v python3 &> /dev/null; then
    PYTHON_CMD="python3"
    PYTHON_LOC="System (python3)"
elif command -v python &> /dev/null; then
    PYTHON_CMD="python"
    PYTHON_LOC="System (python)"
fi

if [ -n "$PYTHON_CMD" ]; then
    echo "[OK] Python found: $PYTHON_LOC"
    $PYTHON_CMD --version
    echo ""
else
    echo "[!] Python 3 is NOT installed or not found."
    echo ""
    echo "  Please install it using your system package manager:"
    echo "  Ubuntu/Debian:  sudo apt install python3 python3-pip"
    echo "  Fedora:         sudo dnf install python3 python3-pip"
    echo "  Arch:           sudo pacman -S python python-pip"
    echo ""
    read -p "Press Enter to exit..."
    exit 1
fi

# ── 3. TRAY DEPENDENCY CHECK ──────────────────────────────────────────────────
echo "[DEPENDENCY CHECK]"

# Quick check: if key tray modules are importable, skip install
if $PYTHON_CMD -c "import tomli_w, pystray, PIL" &> /dev/null; then
    echo "[OK] All Tray dependencies are already installed."
    echo ""
else
    echo "[!] Some Tray dependencies are missing. Installing..."
    echo ""

    PYPROJECT="$TRAY_DIR/pyproject.toml"
    if [ -f "$PYPROJECT" ]; then
        $PYTHON_CMD -m pip install --quiet --upgrade pip &> /dev/null
        $PYTHON_CMD -m pip install --quiet "$TRAY_DIR[.]" 2>/dev/null || \
            $PYTHON_CMD -m pip install --quiet pystray pillow tomli-w packaging psutil pyyaml customtkinter
    else
        $PYTHON_CMD -m pip install --quiet pystray pillow tomli-w packaging psutil pyyaml customtkinter
    fi

    # Verify
    if ! $PYTHON_CMD -c "import tomli_w, pystray, PIL" &> /dev/null; then
        echo ""
        echo "  [!] ERROR: Failed to install Tray dependencies."
        echo "  [!] Try running manually: pip3 install pystray pillow tomli-w packaging psutil pyyaml customtkinter"
        read -p "Press Enter to exit..."
        exit 1
    fi
    echo "[+] Tray dependencies installed successfully."
    echo ""
fi

# ── 4. READY — let the user choose ──────────────────────────────────────────
echo "=============================================================================="
echo "                      HECOS TRAY IS READY"
echo "=============================================================================="
echo ""
echo "  The Tray is fully configured and ready to launch."
echo "  What would you like to do?"
echo ""

if [ "$CORE_FOUND" = "1" ]; then
    echo "   1. Open the Hecos Setup Wizard (configure AI, voices, install deps)"
    echo "   2. Launch the Tray Icon directly"
    echo "   3. Exit"
    echo ""
    read -p "Select an option (1-3): " READY_CHOICE

    if [ "$READY_CHOICE" = "1" ]; then
        goto_setup_wizard=1
    elif [ "$READY_CHOICE" = "2" ]; then
        goto_tray_only=1
    else
        exit 0
    fi
else
    echo "   1. Download Hecos Core from GitHub (then open Setup Wizard)"
    echo "   2. Launch the Tray Icon only (download Core later from the Dashboard)"
    echo "   3. Exit"
    echo ""
    read -p "Select an option (1-3): " READY_CHOICE

    if [ "$READY_CHOICE" = "1" ]; then
        goto_download_core=1
    elif [ "$READY_CHOICE" = "2" ]; then
        goto_tray_only=1
    else
        exit 0
    fi
fi

# ── LAUNCH SETUP WIZARD ───────────────────────────────────────────────────────
if [ "$goto_setup_wizard" = "1" ]; then
    echo ""
    echo "[*] Launching Hecos Setup Wizard..."
    cd "$ROOT_DIR" || exit 1
    $PYTHON_CMD "hecos/setup_wizard.py" --web
    exit 0
fi

# ── LAUNCH TRAY ONLY ──────────────────────────────────────────────────────────
if [ "$goto_tray_only" = "1" ]; then
    echo ""
    echo "[*] Launching Hecos Tray..."
    echo "[*] The tray icon will appear shortly."
    sleep 1
    cd "$TRAY_DIR" || exit 1
    nohup $PYTHON_CMD -m tray.tray_app > /dev/null 2>&1 &
    echo "[+] Done."
    exit 0
fi

# ── DOWNLOAD CORE ─────────────────────────────────────────────────────────────
if [ "$goto_download_core" = "1" ]; then
    echo ""
    echo "=============================================================================="
    echo "                  DOWNLOADING HECOS CORE FROM GITHUB"
    echo "=============================================================================="
    echo ""

    GH_API_URL="https://api.github.com/repos/Hecos-Project/Hecos/releases/latest"
    TEMP_ZIP="/tmp/hecos_core_$$.zip"
    TEMP_EXTRACT="/tmp/hecos_extract_$$"

    if command -v curl &> /dev/null; then
        DOWNLOADER="curl"
    elif command -v wget &> /dev/null; then
        DOWNLOADER="wget"
    else
        echo "[!] Neither curl nor wget found. Install one and retry."
        echo "[!] Or download manually from: https://github.com/Hecos-Project/Hecos/releases/latest"
        read -p "Press Enter to exit..."
        exit 1
    fi

    echo "[*] Fetching latest release info from GitHub..."
    if [ "$DOWNLOADER" = "curl" ]; then
        ZIPBALL_URL=$(curl -sS -H "User-Agent: HecosSetup/1.0" "$GH_API_URL" | \
            $PYTHON_CMD -c "import sys,json; print(json.load(sys.stdin).get('zipball_url',''))" 2>/dev/null)
    else
        ZIPBALL_URL=$(wget -q -O- --header="User-Agent: HecosSetup/1.0" "$GH_API_URL" | \
            $PYTHON_CMD -c "import sys,json; print(json.load(sys.stdin).get('zipball_url',''))" 2>/dev/null)
    fi

    if [ -z "$ZIPBALL_URL" ]; then
        echo "[!] Failed to fetch release info. Check your internet connection."
        echo "[!] Manual download: https://github.com/Hecos-Project/Hecos/releases/latest"
        read -p "Press Enter to exit..."
        exit 1
    fi

    echo "[*] Downloading Core (~50-100 MB)... please wait."
    if [ "$DOWNLOADER" = "curl" ]; then
        curl -L --progress-bar -H "User-Agent: HecosSetup/1.0" -o "$TEMP_ZIP" "$ZIPBALL_URL"
    else
        wget -q --show-progress --user-agent="HecosSetup/1.0" -O "$TEMP_ZIP" "$ZIPBALL_URL"
    fi

    if [ $? -ne 0 ] || [ ! -f "$TEMP_ZIP" ]; then
        echo "[!] Download failed."
        read -p "Press Enter to exit..."
        exit 1
    fi

    echo ""
    echo "[*] Extracting files..."
    mkdir -p "$TEMP_EXTRACT"
    unzip -q "$TEMP_ZIP" -d "$TEMP_EXTRACT"

    echo "[*] Installing to $ROOT_DIR..."
    mkdir -p "$ROOT_DIR"
    INNER_DIR=$(find "$TEMP_EXTRACT" -mindepth 1 -maxdepth 1 -type d | head -n 1)
    if [ -n "$INNER_DIR" ]; then
        cp -a "$INNER_DIR/." "$ROOT_DIR/"
    else
        cp -a "$TEMP_EXTRACT/." "$ROOT_DIR/"
    fi

    rm -f "$TEMP_ZIP"
    rm -rf "$TEMP_EXTRACT"

    if [ -f "$ROOT_DIR/hecos/core/version" ]; then
        echo ""
        echo "  [+] Hecos Core installed successfully!"
        echo ""
        sleep 2
        echo "[*] Launching Core Setup Wizard..."
        cd "$ROOT_DIR" || exit 1
        $PYTHON_CMD "hecos/setup_wizard.py"
    else
        echo ""
        echo "  [!] Extraction done but Core files not found. Extract the ZIP manually."
        read -p "Press Enter to exit..."
    fi
fi
