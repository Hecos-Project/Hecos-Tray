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
    """Kills all Ollama-related processes using taskkill /F /T on Windows,
    ensuring child GPU runners are also terminated and VRAM is freed.
    Returns number of processes killed.
    """
    import subprocess, sys
    killed = 0
    if sys.platform == 'win32':
        for exe in ('ollama.exe', 'ollama_llama_server.exe', 'ollama app.exe'):
            try:
                result = subprocess.run(
                    ['taskkill', '/F', '/T', '/IM', exe],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=5
                )
                if result.returncode == 0:
                    killed += 1
            except Exception:
                pass
    else:
        try:
            import psutil
            for proc in psutil.process_iter(['pid', 'name']):
                if (proc.info.get('name') or '').lower() in {'ollama', 'ollama_llama_server'}:
                    try:
                        proc.kill()
                        killed += 1
                    except Exception:
                        pass
        except Exception:
            pass
    return killed


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
            elif "hecos.core.daemon" in cmd_str:
                p_type = "Hecos Daemon"
            elif "monitor.py" in cmd_str:
                p_type = "Monitor"
            elif "hecos.app.main" in cmd_str or "hecos_core" in name or "main.py" in cmd_str:
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
    return hecos_procs

def kill_all_hecos_processes():
    try:
        import psutil
    except ImportError:
        return 0
        
    procs = get_hecos_processes()
    killed = 0
    for p in procs:
        if p['type'] == "Hecos Tray":
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
        
    procs = get_hecos_processes()
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
