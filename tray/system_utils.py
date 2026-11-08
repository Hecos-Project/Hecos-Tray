import sys
import subprocess
import os
import shutil
from tray.config import VERSION_FILE, _ROOT

# Global list of Popen objects for tracked console windows
_managed_consoles = []

def play_beep(freq: int, duration_ms: int):
    """Universal cross-platform audio helper for system beeps/cues."""
    if sys.platform == "win32":
        try:
            import winsound
            winsound.Beep(int(freq), int(duration_ms))
        except Exception:
            pass
    else:
        try:
            subprocess.run(["beep", "-f", str(freq), "-l", str(duration_ms)],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception:
            print('\a', end='', flush=True)

def get_version():
    # Try tray-specific version first (hecos/tray/version)
    _this_dir = os.path.dirname(os.path.abspath(__file__))
    _tray_ver_file = os.path.join(_this_dir, "version")
    try:
        with open(_tray_ver_file, "r", encoding="utf-8-sig") as f:
            v = f.read().strip()
            if v:
                return v
    except Exception:
        pass
    # Fallback: read from hecos/core/version
    try:
        with open(VERSION_FILE, "r", encoding="utf-8-sig") as f:
            return f.read().strip()
    except Exception:
        return "1.0.1"

def launch_console(script_path: str):
    """Launches a script in a new tracked console window."""
    global _managed_consoles
    _managed_consoles = [p for p in _managed_consoles if p.poll() is None]
    try:
        if sys.platform == "win32":
            p = subprocess.Popen(
                ["cmd.exe", "/c", script_path],
                creationflags=0x00000010,  # CREATE_NEW_CONSOLE
                cwd=_ROOT
            )
            _managed_consoles.append(p)
        else:
            p = subprocess.Popen(["x-terminal-emulator", "-e", script_path], cwd=_ROOT)
            _managed_consoles.append(p)
    except Exception as e:
        print(f"[TRAY] Failed to launch console: {e}")

def terminate_consoles():
    """Closes all console windows tracked by the Tray App."""
    global _managed_consoles
    for p in _managed_consoles:
        if p.poll() is None:
            try:
                p.terminate()
            except Exception:
                pass
    _managed_consoles = []

# ── Ollama Process Utilities ──────────────────────────────────────────────────

_OLLAMA_PROCESS_NAMES = {"ollama.exe", "ollama_llama_server.exe", "ollama app.exe"}

def get_ollama_processes():
    """Returns a list of dicts describing running Ollama-related processes.
    Each dict: {pid, name, type, vram_mb, cpu_percent, status}
    type is one of: 'Ollama Server' | 'Ollama GPU Runner' | 'Ollama App'
    """
    try:
        import psutil
    except ImportError:
        return []

    results = []
    for proc in psutil.process_iter(['pid', 'name', 'status', 'cpu_percent']):
        try:
            name_lower = (proc.info.get('name') or '').lower()
            if name_lower not in {n.lower() for n in _OLLAMA_PROCESS_NAMES}:
                continue

            if 'llama_server' in name_lower or 'llama-server' in name_lower:
                p_type = 'Ollama GPU Runner'
            elif 'ollama app' in name_lower:
                p_type = 'Ollama App (GUI)'
            else:
                p_type = 'Ollama Server'

            # Try to read memory info
            vram_mb = 0
            try:
                mem = proc.memory_info()
                vram_mb = round(mem.rss / (1024 * 1024))
            except Exception:
                pass

            results.append({
                'pid':         proc.info['pid'],
                'name':        proc.info.get('name', ''),
                'type':        p_type,
                'vram_mb':     vram_mb,
                'cpu_percent': round(proc.info.get('cpu_percent') or 0.0, 1),
                'status':      proc.info.get('status', 'unknown'),
            })
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return results


def is_ollama_api_responding(url: str = "http://127.0.0.1:11434", timeout: int = 2) -> bool:
    """Returns True if Ollama's HTTP API is actually responding (model can accept requests)."""
    try:
        import urllib.request
        req = urllib.request.Request(f"{url}/api/tags", method="GET")
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status == 200
    except Exception:
        return False


def kill_ollama_processes():
    """Kills all Ollama-related processes cleanly.
    Uses psutil first for silent, instantaneous in-memory termination (no console windows).
    Falls back to taskkill /F /T with CREATE_NO_WINDOW on Windows.
    Returns number of processes killed.
    """
    import subprocess, sys
    killed = 0

    # 1. Pure Python termination via psutil (completely silent on all platforms)
    try:
        import psutil
        target_names = {'ollama.exe', 'ollama_llama_server.exe', 'ollama app.exe', 'ollama'}
        for proc in psutil.process_iter(['pid', 'name']):
            if (proc.info.get('name') or '').lower() in target_names:
                try:
                    proc.kill()
                    killed += 1
                except Exception:
                    pass
    except Exception:
        pass

    # 2. Windows fallback if psutil was not available
    if sys.platform == 'win32' and killed == 0:
        for exe in ('ollama.exe', 'ollama_llama_server.exe', 'ollama app.exe'):
            try:
                result = subprocess.run(
                    ['taskkill', '/F', '/T', '/IM', exe],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=5,
                    creationflags=subprocess.CREATE_NO_WINDOW
                )
                if result.returncode == 0:
                    killed += 1
            except Exception:
                pass

    return killed


# ── TTS Engines Loopback & Process Utilities ─────────────────────────────────

def _read_tts_control_endpoint():
    """Reads loopback control URL and token from hecos/data/run/tts_control.json."""
    import json
    from tray.config import get_webui_config
    ctrl_file = os.path.join(_ROOT, "hecos", "data", "run", "tts_control.json")
    port = 7070
    scheme = "http"
    token = ""
    try:
        wcfg = get_webui_config()
        port = int(wcfg.get("port", 7070))
        if wcfg.get("https_enabled"):
            scheme = "https"
    except Exception:
        pass
    try:
        if os.path.isfile(ctrl_file):
            with open(ctrl_file, "r", encoding="utf-8") as f:
                data = json.load(f) or {}
            token = str(data.get("token") or "")
            if data.get("port"):
                port = int(data["port"])
            if data.get("scheme") in ("http", "https"):
                scheme = data["scheme"]
    except Exception:
        pass
    return f"{scheme}://127.0.0.1:{port}", token


def _tts_loopback_request(path: str, method: str = "GET", payload: dict = None, timeout: float = 2.5):
    import json
    import ssl
    import urllib.request
    base_url, token = _read_tts_control_endpoint()
    url = f"{base_url}{path}"
    headers = {"Accept": "application/json"}
    if token:
        headers["X-Hecos-Local-Token"] = token
    body = None
    if payload is not None:
        body = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    ctx = ssl._create_unverified_context() if url.startswith("https://") else None
    with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
        return json.loads(resp.read().decode("utf-8"))


def get_tts_engines_status() -> dict:
    """
    Queries Hecos Core for live TTS engine runtime status (Piper, Kokoro, XTTSv2, Fish Speech).
    Falls back to local psutil process inspection + audio.yaml when Core is offline.
    """
    try:
        data = _tts_loopback_request("/api/audio/engines/status", method="GET", timeout=2.0)
        if isinstance(data, dict) and data.get("ok") and "engines" in data:
            data["core_online"] = True
            return data
    except Exception:
        pass

    # Offline fallback: inspect audio.yaml + lingering daemon processes via psutil
    active = "piper"
    cfg = {}
    try:
        import yaml
        audio_yaml = os.path.join(_ROOT, "hecos", "config", "data", "audio.yaml")
        if os.path.isfile(audio_yaml):
            with open(audio_yaml, "r", encoding="utf-8") as f:
                cfg = yaml.safe_load(f) or {}
            active = str(cfg.get("active_engine") or "piper").lower()
            if active == "fish":
                active = "fish_speech"
    except Exception:
        pass

    piper_pid, piper_ram = None, 0.0
    fish_pid, fish_ram = None, 0.0
    try:
        import psutil
        for proc in psutil.process_iter(["pid", "name", "cmdline"]):
            try:
                nm = (proc.info.get("name") or "").lower()
                cmd = " ".join(proc.info.get("cmdline") or []).lower()
                if "piper" in nm and "--json-input" in cmd:
                    piper_pid = proc.info["pid"]
                    piper_ram = round(proc.memory_info().rss / (1024 * 1024), 1)
                elif "fish_speech_server.py" in cmd:
                    fish_pid = proc.info["pid"]
                    fish_ram = round(proc.memory_info().rss / (1024 * 1024), 1)
            except Exception:
                continue
    except Exception:
        pass

    return {
        "ok": True,
        "core_online": False,
        "active_engine": active,
        "engines": {
            "piper": {
                "engine": "piper", "label": "Piper TTS",
                "status": "online" if piper_pid else "offline",
                "loaded": bool(piper_pid), "mode": "daemon",
                "pid": piper_pid, "ram_mb": piper_ram, "vram_mb": 0.0,
                "device": "CPU (ONNX)", "active": active == "piper", "fallback": True,
                "autostart": bool(cfg.get("piper_autostart", True)),
            },
            "kokoro": {
                "engine": "kokoro", "label": "Kokoro-82M",
                "status": "offline", "loaded": False, "mode": "in-process",
                "pid": None, "ram_mb": 0.0, "vram_mb": 0.0,
                "device": "—", "active": active == "kokoro", "fallback": False,
                "autostart": bool((cfg.get("kokoro") or {}).get("autostart", True)),
            },
            "xtts2": {
                "engine": "xtts2", "label": "Coqui XTTSv2",
                "status": "offline", "loaded": False, "mode": "in-process",
                "pid": None, "ram_mb": 0.0, "vram_mb": 0.0,
                "device": "—", "active": active == "xtts2", "fallback": False,
                "autostart": bool((cfg.get("xtts") or {}).get("autostart", True)),
            },
            "fish_speech": {
                "engine": "fish_speech", "label": "Fish Speech S2",
                "status": "online" if fish_pid else "offline",
                "loaded": bool(fish_pid), "mode": "daemon",
                "pid": fish_pid, "ram_mb": fish_ram, "vram_mb": 0.0,
                "device": "CUDA" if fish_pid else "—", "active": active == "fish_speech", "fallback": False,
                "autostart": bool((cfg.get("fish_speech") or {}).get("autostart", True)),
            },
        },
    }


def control_tts_engine(engine: str, action: str):
    """
    Sends a runtime lifecycle action ('start', 'stop', 'restart') to Hecos Core.
    When Core is offline, supports 'stop' to kill lingering Piper / Fish Speech daemons.
    """
    try:
        data = _tts_loopback_request(
            f"/api/audio/engines/{engine}/action",
            method="POST",
            payload={"action": action},
            timeout=15.0,
        )
        if isinstance(data, dict):
            ok = bool(data.get("ok"))
            msg = data.get("message") or data.get("error") or ("Completed." if ok else "Action failed.")
            return ok, str(msg)
    except Exception:
        pass

    # Core is offline — allow killing orphan subprocess daemons directly
    if action in ("stop", "unload"):
        killed = 0
        try:
            import psutil
            for proc in psutil.process_iter(["pid", "name", "cmdline"]):
                try:
                    nm = (proc.info.get("name") or "").lower()
                    cmd = " ".join(proc.info.get("cmdline") or []).lower()
                    match_piper = engine in ("piper", "all") and "piper" in nm and "--json-input" in cmd
                    match_fish = engine in ("fish_speech", "all") and "fish_speech_server.py" in cmd
                    if match_piper or match_fish:
                        for ch in proc.children(recursive=True):
                            try:
                                ch.kill()
                            except Exception:
                                pass
                        proc.kill()
                        killed += 1
                except Exception:
                    continue
        except Exception as ex:
            return False, f"Core offline; process cleanup error: {ex}"
        if killed:
            return True, f"Core offline — terminated {killed} lingering TTS daemon process(es)."
        return True, "Core is offline — no lingering TTS processes were running."

    return False, "Hecos Core is offline. Start Hecos Core first to load TTS engines."


def get_hecos_processes():
    import os
    try:
        import psutil
    except ImportError:
        return []
        
    hecos_procs = []
    my_pid = os.getpid()
    
    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            pid = proc.info['pid']
            if pid == my_pid:
                continue
                
            name = proc.info.get('name', '').lower()
            cmdline = proc.info.get('cmdline') or []
            cmd_str = " ".join(cmdline).lower()
            
            p_type = None
            
            if "pyrefly" in name or "antigravity" in cmd_str:
                continue

            if not ("python" in name or "piper" in name or "hecos" in name):
                continue
                
            if "piper" in name:
                p_type = "Piper TTS"
            elif "fish_speech_server" in cmd_str:
                p_type = "Fish Speech TTS"
            elif "hecos.core.daemon" in cmd_str:
                p_type = "Hecos Daemon"
            elif "monitor.py" in cmd_str:
                p_type = "Monitor"
            elif "hecos.app.main" in cmd_str or "hecos_core" in name or ("main.py" in cmd_str and "hecos" in cmd_str):
                p_type = "Hecos Core"
            elif "web_ui.server" in cmd_str or "hecos_web" in name:
                p_type = "Web Server"
            elif "tray" in cmd_str or "hecos_tray" in name:
                p_type = "Hecos Tray"
            elif "hecos_sdk.runner" in cmd_str or "hecos_module_" in name:
                p_type = "HPM Subprocess"
            elif "python" in name or "hecos" in name:
                if "hecos" in name or "hecos" in cmd_str:
                    p_type = "Hecos (Generic)"
                else:
                    continue

            if p_type:
                hecos_procs.append({
                    "pid": pid,
                    "type": p_type,
                    "cmd": " ".join(cmdline) or name
                })
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    # Also surface in-process TTS neural engines (Kokoro-82M / XTTSv2) loaded inside Web Server RAM/VRAM
    try:
        tts_data = _tts_loopback_request("/api/audio/engines/status", method="GET", timeout=2.2)
        if isinstance(tts_data, dict) and tts_data.get("ok"):
            for ek, label in (("kokoro", "Kokoro TTS (RAM)"), ("xtts2", "XTTSv2 TTS (RAM)")):
                st = (tts_data.get("engines") or {}).get(ek) or {}
                if st.get("mode") == "in-process" and st.get("status") == "online":
                    parts = ["In-Memory in Web Server"]
                    if st.get("device") and st.get("device") != "—":
                        parts.append(str(st["device"]))
                    ram = float(st.get("ram_mb") or 0.0)
                    vram = float(st.get("vram_mb") or 0.0)
                    if ram > 0:
                        parts.append(f"{ram:.0f}MB RAM")
                    if vram > 0:
                        parts.append(f"{vram:.0f}MB VRAM")
                    hecos_procs.append({
                        "pid": st.get("pid") or "in-mem",
                        "type": label,
                        "cmd": f"[{' · '.join(parts)}] {st.get('model') or st.get('label') or ek}",
                        "virtual": True,
                    })
    except Exception:
        pass

    return hecos_procs

def kill_all_hecos_processes():
    try:
        import psutil
    except ImportError:
        return 0
        
    procs = get_hecos_processes()
    killed = 0
    for p in procs:
        if p['type'] == "Hecos Tray" or p.get("virtual"):
            continue
        try:
            psutil.Process(p['pid']).kill()
            killed += 1
        except: pass
    return killed

def kill_duplicate_hecos_processes():
    try:
        import psutil
    except ImportError:
        return 0
        
    procs = [p for p in get_hecos_processes() if not p.get("virtual")]
    counts = {}
    for p in procs:
        counts[p['cmd']] = counts.get(p['cmd'], 0) + 1
        
    killed = 0
    for p in procs:
        if p['type'] == "Hecos Tray":
            continue
        if counts[p['cmd']] > 1:
            try:
                psutil.Process(p['pid']).kill()
                counts[p['cmd']] -= 1
                killed += 1
            except: pass
    return killed

def get_named_executable(name: str, base_exe: str = None) -> str:
    if base_exe is None:
        base_exe = sys.executable
    if not name.lower().endswith(".exe"):
        name += ".exe"
    base_dir = os.path.dirname(base_exe)
    target_path = os.path.join(base_dir, name)
    if os.path.exists(target_path):
        return target_path
    try:
        shutil.copy2(base_exe, target_path)
        return target_path
    except Exception:
        return base_exe

def set_os_startup(enable: bool):
    import sys
    import os
    import subprocess

    if sys.platform == "win32":
        startup_dir = os.path.expandvars(r"%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup")
        lnk_path = os.path.join(startup_dir, "HecosTray.lnk")

        # Always clean up legacy or broken registry keys from Run
        try:
            import winreg
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run", 0, winreg.KEY_SET_VALUE)
            for vname in ("HecosTray", "ZentraTray", "ZentraCore"):
                try:
                    winreg.DeleteValue(key, vname)
                except OSError:
                    pass
            winreg.CloseKey(key)
        except Exception:
            pass

        if enable:
            _this_dir = os.path.dirname(os.path.abspath(__file__))
            tray_root = os.path.dirname(_this_dir)
            bat_path = os.path.join(tray_root, "START_HECOS_TRAY_WIN.bat")
            icon_path = os.path.join(tray_root, "assets", "Hecos_Logo_SQR_NBG_LogoOnly.ico")

            # Create shortcut in Startup folder
            created = False
            try:
                import win32com.client
                shell = win32com.client.Dispatch("WScript.Shell")
                sc = shell.CreateShortcut(lnk_path)
                sc.TargetPath = bat_path
                sc.Arguments = "--silent"
                sc.WorkingDirectory = tray_root
                sc.WindowStyle = 7  # Minimized
                sc.Description = "Hecos System Tray"
                if os.path.exists(icon_path):
                    sc.IconLocation = f"{icon_path},0"
                sc.Save()
                created = True
            except Exception:
                pass

            if not created:
                try:
                    ico_clause = f'$s.IconLocation = "{icon_path},0"; ' if os.path.exists(icon_path) else ''
                    ps_cmd = (
                        f'$ws = New-Object -ComObject WScript.Shell; '
                        f'$s = $ws.CreateShortcut("{lnk_path}"); '
                        f'$s.TargetPath = "{bat_path}"; '
                        f'$s.Arguments = "--silent"; '
                        f'$s.WorkingDirectory = "{tray_root}"; '
                        f'{ico_clause}'
                        f'$s.WindowStyle = 7; '
                        f'$s.Description = "Hecos System Tray"; '
                        f'$s.Save()'
                    )
                    subprocess.run(
                        ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps_cmd],
                        capture_output=True, timeout=10
                    )
                except Exception as e:
                    print(f"[TRAY] Error creating startup shortcut via PowerShell: {e}")
        else:
            if os.path.exists(lnk_path):
                try:
                    os.remove(lnk_path)
                except Exception as e:
                    print(f"[TRAY] Error removing startup shortcut: {e}")

    elif sys.platform.startswith("linux"):
        desktop_dir = os.path.expanduser("~/.config/autostart")
        desktop_file = os.path.join(desktop_dir, "hecos-tray.desktop")
        if enable:
            _this_dir = os.path.dirname(os.path.abspath(__file__))
            tray_root = os.path.dirname(_this_dir)
            sh_path = os.path.join(tray_root, "START_HECOS_TRAY_LINUX.sh")
            icon_path = os.path.join(tray_root, "assets", "Hecos_Logo_SQR_NBG_LogoOnly.png")
            os.makedirs(desktop_dir, exist_ok=True)
            content = (
                "[Desktop Entry]\n"
                "Type=Application\n"
                "Name=Hecos Tray\n"
                "Comment=Hecos Tray Orchestrator\n"
                f"Exec={sh_path} --silent\n"
                f"Icon={icon_path if os.path.exists(icon_path) else 'application-default-icon'}\n"
                "Terminal=false\n"
                "Categories=Utility;\n"
                "X-GNOME-Autostart-enabled=true\n"
            )
            try:
                with open(desktop_file, "w", encoding="utf-8") as f:
                    f.write(content)
                os.chmod(desktop_file, 0o755)
            except Exception as e:
                print(f"[TRAY] Error writing Linux autostart: {e}")
        else:
            if os.path.exists(desktop_file):
                try:
                    os.remove(desktop_file)
                except Exception as e:
                    print(f"[TRAY] Error removing Linux autostart: {e}")
