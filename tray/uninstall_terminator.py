"""
hecos_uninstall_terminator.py
─────────────────────────────────────────────────────────────────────────────
Standalone terminator script for Hecos.

This script is copied to the system temp directory and launched as a
detached process. That way it can safely delete the C:/Hecos and/or
C:/Hecos-Tray folders without hitting Windows "file in use" locks.

Modes:
    full  — Remove Core deps, Tray deps, autostart, then delete BOTH folders.
    core  — Remove Core deps only, then delete C:/Hecos.
    tray  — Remove Tray deps only, remove autostart, then delete C:/Hecos-Tray.
"""
import os
import sys
import re
import time
import shutil
import subprocess
import argparse
import platform

try:
    import tomllib  # Python 3.11+
except ImportError:
    tomllib = None

if platform.system() == "Windows":
    DEFAULT_CORE_DIR = "C:\\Hecos"
    DEFAULT_TRAY_DIR = "C:\\Hecos-Tray"
else:
    DEFAULT_CORE_DIR = os.path.join(os.path.expanduser("~"), "Hecos")
    DEFAULT_TRAY_DIR = os.path.join(os.path.expanduser("~"), "Hecos-Tray")


def _read_install_registry():
    if os.name == "nt":
        base = os.environ.get("LOCALAPPDATA") or os.path.join(os.path.expanduser("~"), "AppData", "Local")
        reg_path = os.path.join(base, "Hecos", "install.toml")
    else:
        xdg = os.environ.get("XDG_CONFIG_HOME") or os.path.join(os.path.expanduser("~"), ".config")
        reg_path = os.path.join(xdg, "hecos", "install.toml")
    if not os.path.isfile(reg_path):
        return {}
    try:
        if tomllib is not None:
            with open(reg_path, "rb") as f:
                return {str(k): str(v) for k, v in tomllib.load(f).items() if v is not None}
    except Exception:
        pass
    data = {}
    try:
        with open(reg_path, "r", encoding="utf-8", errors="replace") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                data[k.strip()] = v.strip().strip("'\"")
    except Exception:
        pass
    return data


def _parse_toml_deps(toml_path):
    packages = []
    if not os.path.exists(toml_path):
        print(f"  [WARN] pyproject.toml not found at: {toml_path}")
        return packages
    raw = []
    try:
        if tomllib is not None:
            with open(toml_path, "rb") as f:
                data = tomllib.load(f)
            proj = data.get("project", {})
            raw.extend(proj.get("dependencies", []) or [])
            opt = proj.get("optional-dependencies", {}) or {}
            raw.extend(opt.get("service", []) or [])
    except Exception as e:
        print(f"  [WARN] tomllib parse failed for {toml_path}: {e}")

    if not raw:
        try:
            with open(toml_path, "r", encoding="utf-8") as f:
                in_array = False
                for line in f:
                    s = line.strip()
                    if not in_array:
                        if re.match(r"^(dependencies|service)\s*=\s*\[", s):
                            in_array = True
                            if s.endswith("]"):
                                raw.extend(re.findall(r'"([^"]+)"', s))
                                in_array = False
                    else:
                        if s.startswith("]"):
                            in_array = False
                            continue
                        if not s.startswith("#"):
                            raw.extend(re.findall(r'"([^"]+)"', s))
        except Exception as e:
            print(f"  [WARN] Failed to parse {toml_path}: {e}")

    for pkg in raw:
        name = re.split(r"[\[\];>=<~!@]", pkg)[0].strip()
        if name:
            packages.append(name)
    return packages


def _uninstall_packages(packages, label):
    if not packages:
        print(f"  [*] No {label} packages found to uninstall.")
        return
    print(f"  [*] Uninstalling {len(packages)} {label} packages...")
    batch_size = 10
    for i in range(0, len(packages), batch_size):
        batch = packages[i:i + batch_size]
        cmd = [sys.executable, "-m", "pip", "uninstall", "-y"] + batch
        try:
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode == 0:
                print(f"    OK: {', '.join(batch)}")
            else:
                print(f"    ~ (skipped or already removed): {', '.join(batch)}")
        except Exception as e:
            print(f"    [!] Error: {e}")


def _remove_autostart():
    print("  [*] Removing autostart entries...")
    if platform.system() == "Windows":
        # Remove startup shortcut
        startup_dir = os.path.expandvars(r"%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup")
        lnk_path = os.path.join(startup_dir, "HecosTray.lnk")
        if os.path.exists(lnk_path):
            try:
                os.remove(lnk_path)
                print("    OK: Windows Startup folder shortcut removed.")
            except Exception as e:
                print(f"    [!] Error removing shortcut: {e}")
        try:
            import winreg
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Run",
                0, winreg.KEY_SET_VALUE
            )
            for k in ("HecosTray", "ZentraTray", "ZentraCore"):
                try:
                    winreg.DeleteValue(key, k)
                except OSError:
                    pass
            winreg.CloseKey(key)
            print("    OK: Windows autostart registry keys removed.")
        except FileNotFoundError:
            print("    ~ No autostart registry key found.")
        except Exception as e:
            print(f"    [!] Registry error: {e}")
    else:
        desktop = os.path.expanduser("~/.config/autostart/hecos-tray.desktop")
        if os.path.exists(desktop):
            try:
                os.remove(desktop)
                print("    OK: Linux autostart .desktop file removed.")
            except Exception as e:
                print(f"    [!] {e}")
        else:
            print("    ~ No Linux autostart file found.")


def _delete_folder(path):
    if not os.path.exists(path):
        print(f"  ~ Folder not found, skipping: {path}")
        return
    print(f"  [*] Deleting: {path}")
    for attempt in range(5):
        try:
            shutil.rmtree(path, ignore_errors=False)
            print(f"    OK: Deleted {path}")
            return
        except Exception as e:
            if attempt < 4:
                print(f"    [!] Error (locked?), retrying in 1s: {e}")
                time.sleep(1)
            else:
                print(f"    [!] Error deleting {path}: {e}")
                # Fallback: force delete ignoring errors
                shutil.rmtree(path, ignore_errors=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["full", "core", "tray"], required=True)
    parser.add_argument("--wait", type=int, default=4)
    parser.add_argument("--skip-tray-delete", action="store_true")
    parser.add_argument("--core-dir", default=None)
    parser.add_argument("--tray-dir", default=None)
    args = parser.parse_args()

    reg = _read_install_registry()
    core_dir = args.core_dir or reg.get("core_path") or DEFAULT_CORE_DIR
    tray_dir = args.tray_dir or reg.get("tray_path") or DEFAULT_TRAY_DIR

    print("=" * 64)
    print("  HECOS UNINSTALL TERMINATOR  |  Mode:", args.mode.upper())
    print("  Core:", core_dir)
    print("  Tray:", tray_dir)
    print("=" * 64)
    print(f"\n  Waiting {args.wait}s for all Hecos processes to exit...\n")
    time.sleep(args.wait)

    mode = args.mode

    if mode in ("full", "core"):
        print("[1] Removing Hecos Core dependencies...")
        pkgs = _parse_toml_deps(os.path.join(core_dir, "pyproject.toml"))
        pkgs.extend(["hecos-core", "hecos"])
        _uninstall_packages(list(set(pkgs)), "Core")
        print()

    if mode in ("full", "tray"):
        print("[2] Removing Hecos Tray dependencies...")
        pkgs = _parse_toml_deps(os.path.join(tray_dir, "pyproject.toml"))
        pkgs.extend(["hecos-tray"])
        _uninstall_packages(list(set(pkgs)), "Tray")
        print()

    if mode in ("full", "tray"):
        print("[3] Removing autostart...")
        _remove_autostart()
        print()

    print("[4] Deleting folders...")
    if mode in ("full", "core"):
        _delete_folder(core_dir)
    if mode in ("full", "tray"):
        if args.skip_tray_delete:
            print(f"  ~ Skipping deletion of {tray_dir} (--skip-tray-delete enabled)")
        else:
            _delete_folder(tray_dir)

    print()
    print("=" * 64)
    print("  DONE! Hecos has been removed from your system.")
    print("=" * 64)

    try:
        os.remove(__file__)
    except Exception:
        pass


if __name__ == "__main__":
    main()
