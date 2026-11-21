"""
Hecos Tray - Shared Install Registry & Path Resolution
Implements the shared contract with Hecos Core so Core and Tray can live
in any valid folder on disk and always find each other.

Registry file location:
  - Windows:     %LOCALAPPDATA%\\Hecos\\install.toml
  - Linux/macOS: ${XDG_CONFIG_HOME:-$HOME/.config}/hecos/install.toml
"""

from __future__ import annotations

import datetime
import os
import platform
import tempfile
from typing import Dict, List, Optional

try:
    import tomllib  # Python 3.11+
except ImportError:  # pragma: no cover
    tomllib = None  # type: ignore[assignment]


def get_registry_path() -> str:
    if os.name == "nt":
        base = os.environ.get("LOCALAPPDATA") or os.path.join(
            os.path.expanduser("~"), "AppData", "Local"
        )
        return os.path.join(base, "Hecos", "install.toml")
    xdg = os.environ.get("XDG_CONFIG_HOME") or os.path.join(
        os.path.expanduser("~"), ".config"
    )
    return os.path.join(xdg, "hecos", "install.toml")


def _fallback_parse_flat_toml(text: str) -> Dict[str, str]:
    data: Dict[str, str] = {}
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        key = k.strip()
        val = v.strip()
        if len(val) >= 2 and val[0] == "'" and val[-1] == "'":
            val = val[1:-1]
        elif len(val) >= 2 and val[0] == '"' and val[-1] == '"':
            val = val[1:-1].replace("\\\\", "\\").replace('\\"', '"')
        if key:
            data[key] = val
    return data


def read_registry(path: Optional[str] = None) -> Dict[str, str]:
    """Read shared install.toml; returns empty dict on missing or corrupt file."""
    reg_path = path or get_registry_path()
    if not os.path.isfile(reg_path):
        return {}
    try:
        if tomllib is not None:
            with open(reg_path, "rb") as f:
                raw = tomllib.load(f)
            return {str(k): str(v) for k, v in raw.items() if v is not None}
        with open(reg_path, "r", encoding="utf-8", errors="replace") as f:
            return _fallback_parse_flat_toml(f.read())
    except Exception:
        try:
            with open(reg_path, "r", encoding="utf-8", errors="replace") as f:
                return _fallback_parse_flat_toml(f.read())
        except Exception:
            return {}


def _format_toml_value(value: str) -> str:
    cleaned = str(value).strip()
    if "'" not in cleaned and "\n" not in cleaned and "\r" not in cleaned:
        return f"'{cleaned}'"
    escaped = cleaned.replace("\\", "\\\\").replace('"', '\\"').replace("\n", " ")
    return f'"{escaped}"'


def update_registry(path: Optional[str] = None, **fields: Optional[str]) -> str:
    """Merge non-None keys into install.toml and write atomically."""
    reg_path = path or get_registry_path()
    data = read_registry(reg_path)

    for key, val in fields.items():
        if val is not None and str(val).strip() != "":
            data[key] = os.path.normpath(str(val)) if key.endswith(("_path", "_python")) else str(val)

    data["updated_at"] = datetime.datetime.now().replace(microsecond=0).isoformat()

    os.makedirs(os.path.dirname(reg_path), exist_ok=True)
    ordered_keys = ["core_path", "tray_path", "core_python", "tray_python", "updated_at"]
    extras = [k for k in sorted(data.keys()) if k not in ordered_keys]

    lines = [
        "# Hecos shared install registry (managed automatically by Core & Tray setup)",
    ]
    for key in ordered_keys + extras:
        if key in data and data[key] != "":
            lines.append(f"{key} = {_format_toml_value(data[key])}")

    content = "\n".join(lines) + "\n"
    reg_dir = os.path.dirname(reg_path)
    fd, tmp_path = tempfile.mkstemp(prefix=".install_", suffix=".tmp", dir=reg_dir)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as f:
            f.write(content)
        os.replace(tmp_path, reg_path)
    except Exception:
        try:
            os.remove(tmp_path)
        except OSError:
            pass
        with open(reg_path, "w", encoding="utf-8", newline="\n") as f:
            f.write(content)

    return reg_path


def is_valid_core_dir(path: Optional[str]) -> bool:
    if not path:
        return False
    return os.path.isfile(os.path.join(path, "hecos", "core", "version"))


def resolve_core_path(
    tray_root: str,
    settings_core_path: Optional[str] = None,
) -> str:
    """Resolve Hecos Core path using the shared contract order:
      1. tray_settings.toml `core_path` (if valid)
      2. install.toml `core_path` (if valid)
      3. Sibling `<tray_parent>/Hecos` (if valid)
      4. Default OS paths: Windows `C:\\Hecos` | POSIX `~/Hecos`, `/opt/hecos` (if valid)
      5. Fallback (when Core is not installed yet): explicit settings/registry path,
         else sibling `<tray_parent>/Hecos`, else platform default.
    """
    reg = read_registry()
    reg_core = reg.get("core_path")

    norm_tray = os.path.normpath(os.path.abspath(tray_root))
    tray_parent = os.path.dirname(norm_tray)
    sibling_core = os.path.join(tray_parent, "Hecos")

    candidates: List[Optional[str]] = [
        settings_core_path,
        reg_core,
        sibling_core,
    ]
    if platform.system() == "Windows":
        candidates.append(r"C:\Hecos")
    else:
        candidates.append(os.path.join(os.path.expanduser("~"), "Hecos"))
        candidates.append("/opt/hecos")

    for cand in candidates:
        if cand and is_valid_core_dir(cand):
            return os.path.normpath(os.path.abspath(cand))

    # Core not yet installed on disk: prefer explicit setting, registry, or sibling
    if settings_core_path and settings_core_path.strip():
        return os.path.normpath(settings_core_path.strip())
    if reg_core and reg_core.strip():
        return os.path.normpath(reg_core.strip())
    if tray_parent and tray_parent != norm_tray:
        return os.path.normpath(sibling_core)
    return r"C:\Hecos" if platform.system() == "Windows" else os.path.join(os.path.expanduser("~"), "Hecos")
