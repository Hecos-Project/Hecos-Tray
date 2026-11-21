#!/bin/bash
# =============================================================================
# HECOS TRAY SETUP WIZARD (Linux / macOS)
# Zero-prerequisite bootstrap: provisions standalone Python 3.11.18 (with
# tkinter & pip) or creates an isolated venv, installs Tray deps, updates
# shared install.toml, downloads Hecos Core into any chosen safe path, and
# delegates Core setup to Core's HECOS_SETUP_WIZARD.sh.
# =============================================================================

set -u

# --- Cyber ANSI Palette (TTY-aware) ---
if [ -t 1 ]; then
    C_CYAN=$'\033[96m'
    C_MAG=$'\033[95m'
    C_GREEN=$'\033[92m'
    C_YELLOW=$'\033[93m'
    C_RED=$'\033[91m'
    C_DIM=$'\033[90m'
    C_WHITE=$'\033[97m'
    C_RST=$'\033[0m'
else
    C_CYAN=""; C_MAG=""; C_GREEN=""; C_YELLOW=""; C_RED=""; C_DIM=""; C_WHITE=""; C_RST=""
fi

TRAY_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" &> /dev/null && pwd)"
TRAY_PARENT="$(dirname "$TRAY_DIR")"
mkdir -p "$TRAY_DIR/logs" 2>/dev/null || true
WIZARD_LOG="$TRAY_DIR/logs/wizard.log"
echo "[$(date '+%Y-%m-%d %H:%M:%S')] HECOS TRAY SETUP STARTED (tray_dir=$TRAY_DIR)" >> "$WIZARD_LOG"

TRAY_VER="unknown"
[ -f "$TRAY_DIR/tray/version" ] && TRAY_VER="$(tr -d '\r\n' < "$TRAY_DIR/tray/version")"

# --- Path validation helper ---
validate_path() {
    local p="$1"
    PATH_STATUS="OK"
    PATH_MSG="Safe path"
    local errs=()
    local warns=()

    case "$p" in
        *" "*|*"	"*) errs+=("contains spaces") ;;
    esac
    if printf '%s' "$p" | LC_ALL=C grep -q '[^ -~]'; then
        errs+=("contains non-ASCII characters")
    fi
    if printf '%s' "$p" | grep -qE "[!%^&()=;,\"'\`]"; then
        errs+=("contains unsafe shell characters")
    fi
    case "$p" in
        /tmp/*|/var/tmp/*) warns+=("inside temporary directory") ;;
    esac

    if [ ${#errs[@]} -gt 0 ]; then
        PATH_STATUS="ERR"
        PATH_MSG="$(IFS='; '; echo "${errs[*]}")"
    elif [ ${#warns[@]} -gt 0 ]; then
        PATH_STATUS="WARN"
        PATH_MSG="$(IFS='; '; echo "${warns[*]}")"
    fi
}

read_toml_key() {
    local file="$1"
    local key="$2"
    [ -f "$file" ] || return 0
    awk -F'=' -v k="$key" '
        $1 ~ "^[[:space:]]*" k "[[:space:]]*$" {
            v = substr($0, index($0, "=") + 1)
            gsub(/^[[:space:]]+|[[:space:]]+$/, "", v)
            gsub(/^[\x27"]|[\x27"]$/, "", v)
            print v
            exit
        }
    ' "$file"
}

detect_core() {
    ROOT_DIR=""
    CORE_FOUND=0
    local cfg_core reg_core
    cfg_core="$(read_toml_key "$TRAY_DIR/tray/tray_settings.toml" "core_path")"
    reg_core="$(read_toml_key "${XDG_CONFIG_HOME:-$HOME/.config}/hecos/install.toml" "core_path")"

    for cand in "$cfg_core" "$reg_core" "$TRAY_PARENT/Hecos" "$HOME/Hecos" "/opt/hecos"; do
        if [ -n "$cand" ] && [ -f "$cand/hecos/core/version" ]; then
            ROOT_DIR="$cand"
            CORE_FOUND=1
            return 0
        fi
    done
}

provision_standalone_python() {
    local target_dir="$1"
    local os_name arch triple
    os_name="$(uname -s)"
    arch="$(uname -m)"

    case "${os_name}:${arch}" in
        Linux:x86_64)   triple="x86_64-unknown-linux-gnu" ;;
        Linux:aarch64|Linux:arm64) triple="aarch64-unknown-linux-gnu" ;;
        Darwin:x86_64)  triple="x86_64-apple-darwin" ;;
        Darwin:arm64)   triple="aarch64-apple-darwin" ;;
        *)
            echo "${C_YELLOW}[WARN]${C_RST} Unsupported arch (${os_name}/${arch}) for standalone Python."
            return 1
            ;;
    esac

    local asset="cpython-3.11.18+20261110-${triple}-install_only.tar.gz"
    local url="https://github.com/astral-sh/python-build-standalone/releases/download/20261110/cpython-3.11.18%2B20261110-${triple}-install_only.tar.gz"
    local sums_url="https://github.com/astral-sh/python-build-standalone/releases/download/20261110/SHA256SUMS"
    local tmp_dir
    tmp_dir="$(mktemp -d "${TMPDIR:-/tmp}/hecos_tray_py_XXXXXX")"
    local tgz="$tmp_dir/python.tar.gz"
    local sums="$tmp_dir/SHA256SUMS"

    echo "${C_CYAN}[ .. ]${C_RST} Downloading standalone Python 3.11.18 (${triple}, ~47 MB, includes tkinter)..."
    if command -v curl &> /dev/null; then
        curl --fail -L --retry 3 --retry-delay 2 --progress-bar -o "$tgz" "$url" || { rm -rf "$tmp_dir"; return 1; }
    elif command -v wget &> /dev/null; then
        wget --tries=3 --show-progress -q -O "$tgz" "$url" || { rm -rf "$tmp_dir"; return 1; }
    else
        echo "${C_RED}[FAIL]${C_RST} Neither curl nor wget is available."
        rm -rf "$tmp_dir"
        return 1
    fi

    local hash_cmd=""
    if command -v sha256sum &> /dev/null; then
        hash_cmd="sha256sum"
    elif command -v shasum &> /dev/null; then
        hash_cmd="shasum -a 256"
    fi

    if [ -n "$hash_cmd" ]; then
        local fetched=0
        if command -v curl &> /dev/null; then
            curl --fail -sSL --retry 2 -o "$sums" "$sums_url" 2>/dev/null && fetched=1
        elif command -v wget &> /dev/null; then
            wget -q -O "$sums" "$sums_url" 2>/dev/null && fetched=1
        fi
        if [ "$fetched" -eq 1 ]; then
            local expected actual
            expected="$(grep -F "$asset" "$sums" | head -n 1 | awk '{print tolower($1)}')"
            actual="$($hash_cmd "$tgz" | awk '{print tolower($1)}')"
            if [ -n "$expected" ] && [ "$expected" != "$actual" ]; then
                echo "${C_RED}[FAIL]${C_RST} SHA256 checksum MISMATCH! Aborting."
                rm -rf "$tmp_dir"
                return 1
            fi
            [ -n "$expected" ] && echo "${C_GREEN}[ OK ]${C_RST} SHA256 checksum verified."
        fi
    fi

    echo "${C_CYAN}[ .. ]${C_RST} Extracting Python into $target_dir ..."
    tar -xzf "$tgz" -C "$tmp_dir" || { rm -rf "$tmp_dir"; return 1; }
    [ -x "$tmp_dir/python/bin/python3" ] || { rm -rf "$tmp_dir"; return 1; }

    rm -rf "$target_dir"
    mv "$tmp_dir/python" "$target_dir"
    rm -rf "$tmp_dir"
    echo "${C_GREEN}[ OK ]${C_RST} Standalone Python 3.11.18 installed."
    return 0
}

update_registry_from_tray() {
    "$PYTHON_CMD" -c "
import os, sys
td = sys.argv[1]
core = sys.argv[2] if sys.argv[3] == '1' else None
sys.path.insert(0, td)
from tray.install_registry import update_registry
p = update_registry(tray_path=td, tray_python=sys.executable, core_path=core)
print('[ OK ] Registry updated:', p)
if core:
    from tray.config import set_core_path
    set_core_path(core)
" "$TRAY_DIR" "${ROOT_DIR:-}" "$CORE_FOUND"
}

echo ""
echo "${C_CYAN}==============================================================================${C_RST}"
echo "  ${C_MAG}HECOS TRAY SETUP WIZARD${C_RST}   ${C_CYAN}v${TRAY_VER}${C_RST}   ${C_DIM}(LINUX)${C_RST}"
echo "${C_CYAN}==============================================================================${C_RST}"
echo ""

# =============================================================================
# [1/4] PATH & SYSTEM CHECK
# =============================================================================
echo "${C_CYAN}[1/4] Path & System Check${C_RST}"
validate_path "$TRAY_DIR"
if [ "$PATH_STATUS" = "ERR" ]; then
    echo "${C_RED}[FAIL]${C_RST} Unsafe Tray folder path: $TRAY_DIR ($PATH_MSG)"
    echo "       Move Hecos-Tray to a clean path (e.g. $HOME/Hecos-Tray) and retry."
    read -r -p "Press Enter to exit..."
    exit 1
elif [ "$PATH_STATUS" = "WARN" ]; then
    echo "${C_YELLOW}[WARN]${C_RST} Path advisory: $PATH_MSG"
else
    echo "${C_GREEN}[ OK ]${C_RST} Tray path verified: $TRAY_DIR"
fi

detect_core
if [ "$CORE_FOUND" -eq 1 ]; then
    echo "${C_GREEN}[ OK ]${C_RST} Hecos Core detected: $ROOT_DIR"
else
    echo "${C_DIM}[ -- ]${C_RST} Hecos Core not installed yet (can download in menu below)"
fi
echo ""

# =============================================================================
# [2/4] PYTHON DETECTION (3.10+ WITH TKINTER, PEP 668 SAFE)
# =============================================================================
echo "${C_CYAN}[2/4] Python Runtime (3.10+ with tkinter)${C_RST}"
PYTHON_CMD=""
PYTHON_LOC=""

if [ -x "$TRAY_DIR/python_env/bin/python3" ] && "$TRAY_DIR/python_env/bin/python3" -c "import sys, tkinter; sys.exit(0 if sys.version_info >= (3,10) else 1)" &> /dev/null; then
    PYTHON_CMD="$TRAY_DIR/python_env/bin/python3"
    PYTHON_LOC="Tray Standalone Python ($TRAY_DIR/python_env)"
elif [ -x "$TRAY_DIR/venv/bin/python3" ] && "$TRAY_DIR/venv/bin/python3" -c "import sys, tkinter; sys.exit(0 if sys.version_info >= (3,10) else 1)" &> /dev/null; then
    PYTHON_CMD="$TRAY_DIR/venv/bin/python3"
    PYTHON_LOC="Tray Virtual Environment ($TRAY_DIR/venv)"
fi

if [ -z "$PYTHON_CMD" ]; then
    SYS_PY=""
    if command -v python3 &> /dev/null && python3 -c "import sys, tkinter; sys.exit(0 if sys.version_info >= (3,10) else 1)" &> /dev/null; then
        SYS_PY="$(command -v python3)"
    fi

    echo "${C_YELLOW}[WARN]${C_RST} No isolated Tray Python environment found."
    echo ""
    echo "  ${C_CYAN}1.${C_RST} Download Standalone Portable Python 3.11.18 ${C_GREEN}(Recommended - includes tkinter & avoids PEP 668)${C_RST}"
    if [ -n "$SYS_PY" ]; then
        echo "  ${C_CYAN}2.${C_RST} Create local venv using system Python ($("$SYS_PY" --version 2>&1))"
        echo "  ${C_DIM}3. Exit${C_RST}"
        echo ""
        read -r -p "  >> Select option (1-3) [1]: " PY_CH
    else
        echo "  ${C_DIM}2. Exit${C_RST}"
        echo ""
        read -r -p "  >> Select option (1-2) [1]: " PY_CH
        [ "${PY_CH:-1}" = "2" ] && exit 0
    fi
    PY_CH="${PY_CH:-1}"

    if [ "$PY_CH" = "1" ]; then
        if provision_standalone_python "$TRAY_DIR/python_env"; then
            PYTHON_CMD="$TRAY_DIR/python_env/bin/python3"
            PYTHON_LOC="Tray Standalone Python ($TRAY_DIR/python_env)"
        elif [ -n "$SYS_PY" ]; then
            echo "${C_YELLOW}[WARN]${C_RST} Falling back to local venv..."
            "$SYS_PY" -m venv "$TRAY_DIR/venv" && PYTHON_CMD="$TRAY_DIR/venv/bin/python3" && PYTHON_LOC="Tray Virtual Environment ($TRAY_DIR/venv)"
        fi
    elif [ "$PY_CH" = "2" ] && [ -n "$SYS_PY" ]; then
        echo "${C_CYAN}[ .. ]${C_RST} Creating venv at $TRAY_DIR/venv..."
        if "$SYS_PY" -m venv "$TRAY_DIR/venv"; then
            PYTHON_CMD="$TRAY_DIR/venv/bin/python3"
            PYTHON_LOC="Tray Virtual Environment ($TRAY_DIR/venv)"
        fi
    else
        exit 0
    fi
fi

if [ -z "$PYTHON_CMD" ]; then
    echo "${C_RED}[FAIL]${C_RST} Could not set up Python 3.10+ with tkinter."
    echo "       Debian/Ubuntu: sudo apt install python3 python3-tk python3-venv libportaudio2"
    echo "       Fedora:        sudo dnf install python3 python3-tkinter portaudio"
    echo "       Arch:          sudo pacman -S python tk portaudio"
    read -r -p "Press Enter to exit..."
    exit 1
fi

echo "${C_GREEN}[ OK ]${C_RST} Python ready: $PYTHON_LOC ($("$PYTHON_CMD" --version 2>&1))"
echo ""

# =============================================================================
# [3/4] TRAY DEPENDENCIES
# =============================================================================
echo "${C_CYAN}[3/4] Tray Dependencies${C_RST}"
if "$PYTHON_CMD" -c "import tomli_w, pystray, PIL, customtkinter, qrcode, yaml, psutil, packaging" &> /dev/null; then
    echo "${C_GREEN}[ OK ]${C_RST} All Tray dependencies are already installed."
else
    echo "${C_CYAN}[ .. ]${C_RST} Installing missing Tray dependencies..."
    "$PYTHON_CMD" -m pip install --quiet "pystray>=0.19,<1.0" "pillow>=10.0,<14.0" "tomli-w>=1.0,<2.0" "packaging>=23.0,<28.0" "psutil>=5.9,<8.0" "pyyaml>=6.0,<7.0" "customtkinter>=5.2,<7.0" "qrcode>=7.4,<9.0"
    if ! "$PYTHON_CMD" -c "import tomli_w, pystray, PIL, customtkinter, qrcode" &> /dev/null; then
        echo "${C_RED}[FAIL]${C_RST} Failed to install Tray dependencies."
        read -r -p "Press Enter to exit..."
        exit 1
    fi
    echo "${C_GREEN}[ OK ]${C_RST} Tray dependencies installed successfully."
fi
echo ""

# =============================================================================
# [4/4] INSTALL REGISTRY
# =============================================================================
echo "${C_CYAN}[4/4] Install Registry${C_RST}"
update_registry_from_tray
echo ""

# =============================================================================
# READY MENU
# =============================================================================
while true; do
    detect_core
    echo "${C_CYAN}==============================================================================${C_RST}"
    echo "  ${C_MAG}HECOS TRAY IS READY${C_RST}"
    echo "${C_CYAN}==============================================================================${C_RST}"
    echo "  ${C_DIM}Tray Path:${C_RST} ${C_WHITE}${TRAY_DIR}${C_RST}"
    if [ "$CORE_FOUND" -eq 1 ]; then
        echo "  ${C_DIM}Core Path:${C_RST} ${C_GREEN}${ROOT_DIR}${C_RST}"
        echo "${C_CYAN}------------------------------------------------------------------------------${C_RST}"
        echo ""
        echo "  ${C_CYAN}1.${C_RST} ${C_WHITE}Open Hecos Core Setup Wizard${C_RST}   ${C_DIM}(Python, deps, Piper TTS, doctor)${C_RST}"
        echo "  ${C_CYAN}2.${C_RST} ${C_WHITE}Launch Hecos Tray Icon${C_RST}         ${C_DIM}(Start system tray & dashboard)${C_RST}"
        echo "  ${C_CYAN}3.${C_RST} ${C_WHITE}Download / Reinstall Core${C_RST}      ${C_DIM}(Choose custom folder)${C_RST}"
        echo "  ${C_DIM}4. Exit${C_RST}"
        echo ""
        read -r -p "  >> Select an option (1-4): " READY_CHOICE
        case "${READY_CHOICE:-}" in
            1)
                bash "$ROOT_DIR/scripts/linux/setup/HECOS_SETUP_WIZARD.sh" --tray-dir "$TRAY_DIR"
                ;;
            2)
                bash "$TRAY_DIR/START_HECOS_TRAY_LINUX.sh"
                exit 0
                ;;
            3)
                DO_DOWNLOAD=1
                ;;
            4)
                exit 0
                ;;
            *)
                continue
                ;;
        esac
    else
        echo "  ${C_DIM}Core Path:${C_RST} ${C_YELLOW}Not installed yet${C_RST}"
        echo "${C_CYAN}------------------------------------------------------------------------------${C_RST}"
        echo ""
        echo "  ${C_CYAN}1.${C_RST} ${C_WHITE}Download & Install Hecos Core${C_RST}  ${C_DIM}(Choose folder, download, run setup)${C_RST}"
        echo "  ${C_CYAN}2.${C_RST} ${C_WHITE}Launch Tray Icon Only${C_RST}          ${C_DIM}(Download Core later from Dashboard)${C_RST}"
        echo "  ${C_DIM}3. Exit${C_RST}"
        echo ""
        read -r -p "  >> Select an option (1-3): " READY_CHOICE
        case "${READY_CHOICE:-}" in
            1)
                DO_DOWNLOAD=1
                ;;
            2)
                bash "$TRAY_DIR/START_HECOS_TRAY_LINUX.sh"
                exit 0
                ;;
            3)
                exit 0
                ;;
            *)
                continue
                ;;
        esac
    fi

    if [ "${DO_DOWNLOAD:-0}" -eq 1 ]; then
        DO_DOWNLOAD=0
        DEFAULT_CORE="$TRAY_PARENT/Hecos"
        while true; do
            echo ""
            read -r -p "  >> Core install folder [$DEFAULT_CORE]: " CHOSEN_CORE
            CHOSEN_CORE="${CHOSEN_CORE:-$DEFAULT_CORE}"
            validate_path "$CHOSEN_CORE"
            if [ "$PATH_STATUS" = "ERR" ]; then
                echo "${C_RED}[FAIL]${C_RST} Unsafe path ($PATH_MSG). Choose a clean path."
                continue
            fi
            [ "$PATH_STATUS" = "WARN" ] && echo "${C_YELLOW}[WARN]${C_RST} Path advisory: $PATH_MSG"
            ROOT_DIR="$CHOSEN_CORE"
            break
        done

        GH_API_URL="https://api.github.com/repos/Hecos-Project/Hecos/releases/latest"
        DL_TMP="$(mktemp -d "${TMPDIR:-/tmp}/hecos_core_dl_XXXXXX")"
        TEMP_ZIP="$DL_TMP/hecos_core.zip"
        TEMP_EXTRACT="$DL_TMP/extract"

        echo "${C_CYAN}[ .. ]${C_RST} Fetching latest release info from GitHub..."
        ZIPBALL_URL=""
        if command -v curl &> /dev/null; then
            ZIPBALL_URL="$(curl -sS -H "User-Agent: HecosTraySetup/2.0" "$GH_API_URL" | "$PYTHON_CMD" -c "import sys,json; print(json.load(sys.stdin).get('zipball_url',''))" 2>/dev/null)"
        elif command -v wget &> /dev/null; then
            ZIPBALL_URL="$(wget -q -O- --header="User-Agent: HecosTraySetup/2.0" "$GH_API_URL" | "$PYTHON_CMD" -c "import sys,json; print(json.load(sys.stdin).get('zipball_url',''))" 2>/dev/null)"
        fi

        if [ -z "$ZIPBALL_URL" ]; then
            echo "${C_RED}[FAIL]${C_RST} Could not fetch release info from GitHub."
            rm -rf "$DL_TMP"
            continue
        fi

        echo "${C_CYAN}[ .. ]${C_RST} Downloading Core (~50-100 MB)..."
        if command -v curl &> /dev/null; then
            curl --fail -L --retry 3 --progress-bar -H "User-Agent: HecosTraySetup/2.0" -o "$TEMP_ZIP" "$ZIPBALL_URL" || { rm -rf "$DL_TMP"; continue; }
        else
            wget --tries=3 --show-progress -q --user-agent="HecosTraySetup/2.0" -O "$TEMP_ZIP" "$ZIPBALL_URL" || { rm -rf "$DL_TMP"; continue; }
        fi

        echo "${C_CYAN}[ .. ]${C_RST} Extracting to $ROOT_DIR ..."
        mkdir -p "$TEMP_EXTRACT" "$ROOT_DIR"
        "$PYTHON_CMD" -c "import zipfile, sys; zipfile.ZipFile(sys.argv[1]).extractall(sys.argv[2])" "$TEMP_ZIP" "$TEMP_EXTRACT"
        INNER_DIR="$(find "$TEMP_EXTRACT" -mindepth 1 -maxdepth 1 -type d | head -n 1)"
        if [ -n "$INNER_DIR" ]; then
            cp -a "$INNER_DIR/." "$ROOT_DIR/"
        else
            cp -a "$TEMP_EXTRACT/." "$ROOT_DIR/"
        fi
        rm -rf "$DL_TMP"

        if [ -f "$ROOT_DIR/hecos/core/version" ]; then
            CORE_FOUND=1
            echo "${C_GREEN}[ OK ]${C_RST} Hecos Core downloaded to $ROOT_DIR"
            update_registry_from_tray
            echo "${C_CYAN}[ >> ]${C_RST} Running Core Setup Wizard..."
            bash "$ROOT_DIR/scripts/linux/setup/HECOS_SETUP_WIZARD.sh" --unattended --tray-dir "$TRAY_DIR"
        else
            echo "${C_RED}[FAIL]${C_RST} Extraction completed but Core files were not found."
        fi
    fi
done
