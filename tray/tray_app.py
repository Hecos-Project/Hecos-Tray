"""
MODULE: tray/tray_app.py  (Hecos-Tray repository)
PURPOSE: Hecos System Tray icon — standalone control panel for the Hecos Core engine.

USAGE:
  Run standalone: python -m tray.tray_app  (from C:\\Hecos-Tray\\)
  Auto-launched at user login via Registry HKCU\\Run
"""

import os
import sys
import json
import time
import threading
import webbrowser
import subprocess

# --- INIT TRAY LOGGER ---
# Must be initialized before any other 3rd party imports or checks!
try:
    _TRAY_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    from tray.logger import setup_logger
    setup_logger(_TRAY_ROOT)
except Exception as e:
    # If logger itself fails to load, fallback to standard stream print
    print(f"[TRAY] Fatal Error initializing logger: {e}", file=sys.stderr)

# --- Dependency pre-check with AUTO-INSTALL ---
def _check_deps():
    PACKAGES = [
        ("tomli_w",       "tomli-w"),
        ("pystray",       "pystray"),
        ("PIL",           "pillow"),
        ("customtkinter", "customtkinter"),
        ("psutil",        "psutil"),
        ("yaml",          "pyyaml"),
    ]
    missing = []
    for mod, pkg in PACKAGES:
        try:
            __import__(mod)
        except ImportError:
            missing.append(pkg)

    if not missing:
        return  # All good

    print(f"[TRAY] Auto-installing missing packages: {', '.join(missing)}")
    try:
        import subprocess as _sp
        result = _sp.run(
            [sys.executable, "-m", "pip", "install", "--quiet"] + missing,
            capture_output=True, text=True, timeout=120
        )
        if result.returncode != 0:
            print(f"[TRAY] pip error: {result.stderr.strip()}")
            sys.exit(1)
        print(f"[TRAY] Packages installed OK. Restarting tray to load them...")
        # On Windows os.execv does NOT replace the process (unlike Linux).
        # The singleton socket on port 17099 stays bound until the old process
        # actually exits, causing the restarted process to quit immediately.
        # Use Popen + sys.exit instead: exit first, then the new process starts.
        import subprocess as _sp2
        _sp2.Popen([sys.executable] + sys.argv,
                   creationflags=getattr(_sp2, 'CREATE_NEW_CONSOLE', 0) if sys.platform == 'win32' else 0)
        sys.exit(0)
    except Exception as e:
        print(f"[TRAY] Auto-install failed: {e}")
        print(f"[TRAY] Run manually: pip install {' '.join(missing)}")
        sys.exit(1)

_check_deps()

# Relaunch as hecos_tray.exe if running as a compiled executable
# In development (plain python), we skip this entirely.
_is_compiled = getattr(sys, 'frozen', False) or getattr(sys, 'compiled', False)
if sys.platform == "win32" and _is_compiled:
    if not sys.executable.lower().endswith("hecos_tray.exe"):
        from tray.system_utils import get_named_executable
        tray_exe = get_named_executable("hecos_tray")
        if tray_exe and tray_exe != sys.executable:
            subprocess.Popen([tray_exe, "-m", "tray.tray_app"])
            sys.exit(0)

from tray.config import SETTINGS_FILE, _DEFAULTS, _ROOT, load_settings, save_settings
from tray.browser_manager import launch_ai_ready_browser, is_ai_ready_browser_running, set_cdp_alive, _get_cdp_port
from tray.network_utils import get_scheme
from tray.system_utils import play_beep
from tray.orchestrator import start_hecos, stop_hecos, is_hecos_running
from tray.hotkeys import tray_hotkeys
from tray.ui import load_icon, build_menu, refresh_ui, TRAY_AVAILABLE
from tray.control_center import show_control_center

try:
    import pystray
except ImportError:
    pass

_singleton_socket = None
_STATUS_POLL_NORMAL  = 3    # seconds between checks when stable
_STATUS_POLL_STARTUP = 1    # seconds between checks while waiting for server to come up

def _monitor_status(icon: "pystray.Icon"):
    attempted_start = False
    was_online = False
    first_run = True

    while True:
        try:
            settings = load_settings()

            # ── Single source of truth for the icon: TCP port reachable ─────
            # is_hecos_online() uses a 2s socket timeout; fast, no HTTP overhead.
            # This matches exactly what refresh_ui() checks, so there is never a
            # mismatch between the icon colour and the actual server state.
            from tray.network_utils import is_hecos_online as _is_online
            online = _is_online()

            # ── Update cached CDP status so build_menu() never blocks ────────
            cdp_port = _get_cdp_port()
            set_cdp_alive(is_ai_ready_browser_running(cdp_port))
            # ─────────────────────────────────────────────────────────────────

            # TRANSITION: Offline → Online
            if online and not was_online:
                play_beep(400, 100)
                play_beep(600, 150)

                headless_lock = os.path.join(_ROOT, ".headless_boot")
                is_headless = os.path.exists(headless_lock)
                if is_headless:
                    try:
                        os.remove(headless_lock)
                        print("[TRAY] Suppressed auto-open for headless launch (lock file removed).")
                    except Exception: pass

                # Auto-launch Chrome in AI-Ready mode if setting is enabled
                # MUST be launched FIRST so that if autoopen_webui is true, it opens inside this browser
                if settings.get("auto_launch_chrome_for_ai", False) and not is_headless:
                    cdp_port = _get_cdp_port()
                    if not is_ai_ready_browser_running(cdp_port):
                        time.sleep(0.5)
                        from tray.network_utils import get_scheme
                        startup_url = settings.get("browser_startup_url", "")
                        if startup_url:
                            real_scheme = get_scheme()
                            if startup_url.startswith("http://") and real_scheme == "https":
                                startup_url = startup_url.replace("http://", "https://", 1)
                            elif startup_url.startswith("https://") and real_scheme == "http":
                                startup_url = startup_url.replace("https://", "http://", 1)
                        launch_ai_ready_browser(cdp_port=cdp_port, startup_url=startup_url)
                        time.sleep(1.5)

                # Auto-open/refresh WebUI
                if settings.get("autoopen_webui", True) and not is_headless:
                    from tray.browser_manager import intelligent_open_webui
                    time.sleep(1.0)
                    intelligent_open_webui(icon, None)

                # Auto-open/refresh AI Browser (Headless/Integrated)
                if settings.get("autoopen_ai_browser", False) and not is_headless:
                    from tray.browser_manager import intelligent_open_ai_browser
                    time.sleep(1.5)
                    intelligent_open_ai_browser(icon, None)

            # Auto-start service if the toggle says it should be running
            # (use is_hecos_running() here — process check is enough for start logic)
            if settings["start_hecos_on_launch"] and not is_hecos_running() and not attempted_start:
                attempted_start = True
                print("[TRAY] start_hecos_on_launch=True but offline — starting Hecos subprocess…")
                threading.Thread(target=start_hecos, daemon=True).start()

            # Refresh icon/menu only on state change (prevents flickering)
            if first_run or online != was_online:
                refresh_ui(icon)
                first_run = False

            was_online = online

        except Exception as e:
            pass

        # Poll fast (1s) while offline/starting so the icon turns green quickly.
        # Once stable and online, slow down to avoid unnecessary CPU/network load.
        poll_interval = _STATUS_POLL_STARTUP if not online else _STATUS_POLL_NORMAL
        time.sleep(poll_interval)



def run_tray():
    # --- SINGLE INSTANCE LOCK ---
    import socket
    # Using a global reference to ensure the socket stays open for the life of the process
    global _singleton_socket
    _singleton_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        # We bind to a specific high-range port to ensure only one Tray instance runs per machine
        _singleton_socket.bind(("127.0.0.1", 17099))
    except (socket.error, OverflowError):
        # Already running
        print("[TRAY] Hecos Tray is already running. Exiting current instance.")
        sys.exit(0)

    if not TRAY_AVAILABLE:
        print("\n[!] ERRORE: Dipendenze mancanti per la Tray Icon.")
        print("    Esegui questo comando nel terminale:")
        print("    pip install pystray pillow")
        sys.exit(1)

    if not os.path.exists(SETTINGS_FILE):
        save_settings(_DEFAULTS)
        print(f"[TRAY] Settings file created: {SETTINGS_FILE}")

    settings = load_settings()
    print(f"[TRAY] Settings loaded: {settings}")

    online = is_hecos_running()
    icon_image = load_icon(online)

    icon = pystray.Icon(
        name="hecos_core",
        icon=icon_image,
        title="HECOS — Helping Companion System",
        menu=build_menu([None])
    )

    # Left-click opens the Control Center
    def _on_activate(ic):
        show_control_center(ic, None)
    icon.default_action = _on_activate

    monitor_thread = threading.Thread(target=_monitor_status, args=(icon,), daemon=True)
    monitor_thread.start()

    tray_hotkeys.start()

    print("[TRAY] Hecos tray icon started.")
    try:
        try:
            icon.run()
        except Exception as e:
            import traceback
            print(f"[CRASH] pystray icon.run() failed: {e}")
            traceback.print_exc()
    finally:
        # Guarantee that if tray drops unexpectedly, we don't leave zombie subprocesses
        stop_hecos()


if __name__ == "__main__":
    run_tray()
