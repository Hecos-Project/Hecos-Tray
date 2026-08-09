import os
import sys
import subprocess
import time
import threading

from tray.config import _ROOT
from tray.utils import is_hecos_online

# Hold a reference to the subprocess so we can terminate it later
_hecos_process = None

# Global lock — prevents two concurrent start_hecos() / restart_hecos() calls
_start_lock = threading.Lock()


def get_platform_python():
    """
    Returns the correct Python command (as a list) to run the Hecos Core.
    Priority order (ensures Core is always independent from Tray):
      1. Core's own portable Python  (C:/Hecos/python_env/python.exe)
      2. Core's own venv             (C:/Hecos/venv/Scripts/python.exe)
      3. System 'py -3' launcher     (Windows only, matches .bat behaviour)
      4. System python3 / python     (Linux / fallback)
      5. Tray's own sys.executable   (last resort)
    Returns a list, e.g. ["C:\\...\\python.exe"] or ["py", "-3"].
    """
    import shutil

    # Priority 1: Core's portable Python (installed by the Core's own setup wizard)
    for name in ("python.exe", "python3", "python"):
        candidate = os.path.join(_ROOT, "python_env", name)
        if os.path.exists(candidate):
            print(f"[ORCHESTRATOR] Using Core portable Python: {candidate}")
            return [candidate]

    # Priority 2: Core's venv
    for rel in (
        os.path.join("venv", "Scripts", "python.exe"),  # Windows venv
        os.path.join("venv", "bin", "python3"),          # Linux venv
        os.path.join("venv", "bin", "python"),
    ):
        candidate = os.path.join(_ROOT, rel)
        if os.path.exists(candidate):
            print(f"[ORCHESTRATOR] Using Core venv Python: {candidate}")
            return [candidate]

    # Priority 3: py launcher with explicit -3 (Windows — matches the .bat files)
    if sys.platform == "win32":
        found = shutil.which("py")
        if found:
            print(f"[ORCHESTRATOR] Using system Python: py -3")
            return ["py", "-3"]

    # Priority 4: system python3 / python (Linux)
    for cmd in ("python3", "python"):
        found = shutil.which(cmd)
        if found:
            print(f"[ORCHESTRATOR] Using system Python: {found}")
            return [found]

    # Priority 5: Fall back to whatever is running the Tray itself
    base_exe = sys.executable
    print(f"[ORCHESTRATOR] Fallback: using Tray Python: {base_exe}")
    return [base_exe]



def _read_boot_trace_tail(n_lines=30) -> str:
    """Reads the last N lines of hecos_boot_trace.log for crash diagnosis."""
    boot_log_path = os.path.join(_ROOT, "hecos", "logs", "hecos_boot_trace.log")
    try:
        with open(boot_log_path, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
        tail = lines[-n_lines:] if len(lines) > n_lines else lines
        return "".join(tail).strip()
    except Exception as e:
        return f"(could not read boot trace: {e})"


def _wait_and_respawn(proc):
    """Waits for the subprocess to finish. If exit code is 42, respawns it."""
    start_time = time.time()
    proc.wait()
    elapsed = time.time() - start_time
    code = getattr(proc, 'returncode', '?')

    if code == 42:
        print("[ORCHESTRATOR] Hecos requested reboot (Exit 42). Respawning...")

        # Wait up to 5 seconds for the port to release
        for _ in range(10):
            if not is_hecos_online():
                break
            time.sleep(0.5)

        # If it's still online (ghost process or TIME_WAIT), forcefully kill by port
        if is_hecos_online():
            print("[ORCHESTRATOR] Port still held after Exit 42, forcing kill...")
            _kill_by_port()
            time.sleep(1)

        start_hecos()
    elif code != 0:
        # Non-zero, non-42 exit: log the crash trace to help diagnose
        print(f"[ORCHESTRATOR] Hecos process ended with error (exit code {code}) after {elapsed:.1f}s.")
        trace = _read_boot_trace_tail()
        if trace:
            print(f"[ORCHESTRATOR] Last boot trace output:\n--- BOOT TRACE ---\n{trace}\n--- END TRACE ---")
    elif elapsed < 10:
        # Exit code 0 but suspiciously fast — something crashed silently
        print(f"[ORCHESTRATOR] WARNING: Hecos exited with code 0 after only {elapsed:.1f}s (expected >10s).")
        trace = _read_boot_trace_tail()
        if trace:
            print(f"[ORCHESTRATOR] Last boot trace output:\n--- BOOT TRACE ---\n{trace}\n--- END TRACE ---")
    else:
        print(f"[ORCHESTRATOR] Hecos process ended normally (exit code 0, ran {elapsed:.1f}s).")




def start_hecos():
    """
    Spawns the Hecos WebUI system as a background subprocess of the Tray App.
    Thread-safe: if already running or another start is in progress, returns immediately.
    The 'use_daemon' setting controls whether a watchdog monitor wraps the server:
      - use_daemon=True  → hecos/monitor.py (watchdog) wraps hecos.modules.web_ui.server
      - use_daemon=False → hecos/modules/web_ui/server.py is started directly
    """
    global _hecos_process

    # Prevent concurrent starts — if another thread is already in start_hecos, bail
    if not _start_lock.acquire(blocking=False):
        print("[ORCHESTRATOR] Start already in progress, skipping.")
        return

    try:
        if is_hecos_running():
            return  # Already running

        server_script = os.path.join(_ROOT, "hecos", "modules", "web_ui", "server.py")
        if not os.path.exists(server_script):
            print(f"[ORCHESTRATOR] Error: Could not find {server_script}")
            return

        from tray.config import load_settings
        settings = load_settings()
        use_daemon = settings.get("use_daemon", False)

        python_cmd = get_platform_python()
        # python_cmd is a list, e.g. ["py", "-3"] or ["C:\...\python.exe"]

        boot_log_path = os.path.join(_ROOT, "hecos", "logs", "hecos_boot_trace.log")
        os.makedirs(os.path.dirname(boot_log_path), exist_ok=True)
        boot_log = open(boot_log_path, "a", encoding="utf-8")
        boot_log.write(
            f"\n{'='*50}\n"
            f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] ORCHESTRATOR: Spawning Hecos backend...\n"
            f"  Python: {' '.join(python_cmd)}\n"
            f"  Mode  : {'watchdog (hecos/monitor.py)' if use_daemon else 'standalone'}\n"
            f"{'='*50}\n"
        )
        boot_log.flush()

        # Build the command — run scripts DIRECTLY (like the .bat does), NOT as modules (-m)
        if use_daemon:
            monitor_script = os.path.join(_ROOT, "hecos", "monitor.py")
            if not os.path.exists(monitor_script):
                print(f"[ORCHESTRATOR] Error: Could not find {monitor_script}")
                return
            cmd = python_cmd + [monitor_script, "--script", "hecos.modules.web_ui.server"]
            print(f"[ORCHESTRATOR] Spawning with Watchdog... ({' '.join(python_cmd)})")
        else:
            cmd = python_cmd + [server_script, "--no-gui"]
            print(f"[ORCHESTRATOR] Spawning standalone... ({' '.join(python_cmd)})")

        # Set environment — match what the .bat does
        env = os.environ.copy()
        env["HECOS_BOOT_MODE"] = "webui"
        env["PYTHONIOENCODING"] = "utf-8"
        # Ensure _ROOT is in PYTHONPATH so hecos package is always resolvable
        env["PYTHONPATH"] = _ROOT + os.pathsep + env.get("PYTHONPATH", "")

        kwargs = dict(cwd=_ROOT, stdout=boot_log, stderr=subprocess.STDOUT, env=env)
        if sys.platform == "win32":
            kwargs["creationflags"] = 0x08000000  # CREATE_NO_WINDOW

        _hecos_process = subprocess.Popen(cmd, **kwargs)

        # Background thread handles exit code 42 (self-requested reboot)
        threading.Thread(target=_wait_and_respawn, args=(_hecos_process,), daemon=True).start()

        print("[ORCHESTRATOR] Hecos background process spawned successfully.")
    except Exception as e:
        print(f"[ORCHESTRATOR] Failed to spawn Hecos: {e}")
    finally:
        _start_lock.release()



def stop_hecos():
    """Terminates the background Hecos subprocess."""
    global _hecos_process
    if _hecos_process is not None:
        try:
            _hecos_process.terminate()
            _hecos_process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            _hecos_process.kill()
        except Exception:
            pass
        _hecos_process = None
        print("[ORCHESTRATOR] Hecos process stopped.")
    else:
        # Tray was restarted while Hecos was already running — kill by port
        _kill_by_port()


def _kill_by_port():
    """Find and kill whichever process is holding HECOS_PORT."""
    from tray.config import HECOS_PORT
    try:
        import psutil
        killed = False
        for conn in psutil.net_connections(kind="tcp"):
            if conn.laddr.port == HECOS_PORT and conn.status == "LISTEN":
                try:
                    proc = psutil.Process(conn.pid)
                    proc.terminate()
                    proc.wait(timeout=3)
                    killed = True
                    print(f"[ORCHESTRATOR] Killed process {conn.pid} on port {HECOS_PORT}.")
                except Exception as e:
                    print(f"[ORCHESTRATOR] Could not terminate PID {conn.pid}: {e}")
        if not killed:
            print(f"[ORCHESTRATOR] No process found on port {HECOS_PORT}.")
    except ImportError:
        print("[ORCHESTRATOR] psutil not available — cannot kill by port.")
    except Exception as e:
        print(f"[ORCHESTRATOR] _kill_by_port error: {e}")


def is_hecos_running() -> bool:
    """
    Returns True if we see the process handle is alive, OR if the port is responding.
    (If the Tray app crashed and was restarted, _hecos_process might be None but
    is_hecos_online() will return True.)
    """
    global _hecos_process

    if _hecos_process is not None:
        if _hecos_process.poll() is None:
            return True
        else:
            _hecos_process = None

    # Fallback: check if the port is bound
    return is_hecos_online()


def restart_hecos():
    """Stops the existing process and spawns a new one."""
    try:
        boot_log_path = os.path.join(_ROOT, "hecos", "logs", "hecos_boot_trace.log")
        os.makedirs(os.path.dirname(boot_log_path), exist_ok=True)
        with open(boot_log_path, "a", encoding="utf-8") as f:
            f.write(
                f"\n{'='*50}\n"
                f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] RESTART TRIGGERED FROM TRAY\n"
                f"{'='*50}\n"
            )
    except Exception:
        pass

    stop_hecos()

    # Wait up to 5 seconds for the port to release
    for _ in range(10):
        if not is_hecos_online():
            break
        time.sleep(0.5)

    if is_hecos_online():
        print("[ORCHESTRATOR] Port still held after stop_hecos, forcing kill...")
        _kill_by_port()
        time.sleep(1)

    start_hecos()


# ── Compatibility shim ─────────────────────────────────────────────────────────
# start_hecos_with_daemon() was removed: hecos.core.daemon module doesn't exist.
# All "daemon/watchdog" functionality is now handled by start_hecos() via
# the 'use_daemon' setting which uses hecos.monitor as the watchdog wrapper.
def start_hecos_with_daemon():
    """Deprecated: redirects to start_hecos() which handles watchdog mode internally."""
    print("[ORCHESTRATOR] start_hecos_with_daemon() → redirected to start_hecos()")
    start_hecos()


def stop_daemon():
    """Deprecated: redirects to stop_hecos()."""
    stop_hecos()


def is_daemon_running() -> bool:
    """Deprecated: always returns False (daemon supervisor was removed)."""
    return False
