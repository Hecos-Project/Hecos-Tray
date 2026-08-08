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

if platform.system() == "Windows":
    CORE_DIR = "C:\\Hecos"
    TRAY_DIR = "C:\\Hecos-Tray"
else:
    CORE_DIR = "/opt/hecos"
    TRAY_DIR = "/opt/hecos-tray"


def _parse_toml_deps(toml_path):
    packages = []
    if not os.path.exists(toml_path):
        print(f"  [!] pyproject.toml not found at: {toml_path}")
        return packages
    try:
        with open(toml_path, "r", encoding="utf-8") as f:
            content = f.read()
        match = re.search(r"dependencies\s*=\s*\[(.*?)\]", content, re.DOTALL)
        if match:
            raw = re.findall(r'"([^"]+)"', match.group(1))
            for pkg in raw:
                name = re.split(r"[;>=<~]", pkg)[0].strip()
                if name:
                    packages.append(name)
    except Exception as e:
        print(f"  [!] Failed to parse {toml_path}: {e}")
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
        try:
            import winreg
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Run",
                0, winreg.KEY_SET_VALUE
            )
            winreg.DeleteValue(key, "HecosTray")
            winreg.CloseKey(key)
            print("    OK: Windows autostart registry key removed.")
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
    try:
        shutil.rmtree(path, ignore_errors=False)
        print(f"    OK: Deleted {path}")
    except Exception as e:
        print(f"    [!] Error deleting {path}: {e}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["full", "core", "tray"], required=True)
    parser.add_argument("--wait", type=int, default=4)
    args = parser.parse_args()

    print("=" * 64)
    print("  HECOS UNINSTALL TERMINATOR  |  Mode:", args.mode.upper())
    print("=" * 64)
    print(f"\n  Waiting {args.wait}s for all Hecos processes to exit...\n")
    time.sleep(args.wait)

    mode = args.mode

    if mode in ("full", "core"):
        print("[1] Removing Hecos Core dependencies...")
        pkgs = _parse_toml_deps(os.path.join(CORE_DIR, "pyproject.toml"))
        pkgs.extend(["hecos-core", "hecos"])
        _uninstall_packages(list(set(pkgs)), "Core")
        print()

    if mode in ("full", "tray"):
        print("[2] Removing Hecos Tray dependencies...")
        pkgs = _parse_toml_deps(os.path.join(TRAY_DIR, "pyproject.toml"))
        pkgs.extend(["hecos-tray"])
        _uninstall_packages(list(set(pkgs)), "Tray")
        print()

    if mode in ("full", "tray"):
        print("[3] Removing autostart...")
        _remove_autostart()
        print()

    print("[4] Deleting folders...")
    if mode in ("full", "core"):
        _delete_folder(CORE_DIR)
    if mode in ("full", "tray"):
        _delete_folder(TRAY_DIR)

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
