import os
import sys
import json
import urllib.request
import urllib.error
import zipfile
import shutil
import tempfile
import subprocess
from tray.config import _ROOT
from tray.update_sources import load_sources


def _get_zipball_url_from_active_source() -> tuple:
    """
    Returns (zipball_url, source_name, error_msg).
    Reads the active source from update_sources and fetches the latest release zipball URL.
    """
    data = load_sources()
    active_name = data.get("active_source", "")
    active_src = next((s for s in data.get("sources", []) if s.get("name") == active_name), None)

    if not active_src:
        return None, None, "No active update source configured. Please select a source in the Updates section."

    api_url = active_src.get("url", "")
    source_name = active_src.get("name", "")
    source_type = active_src.get("type", "github_release")

    if not api_url:
        return None, source_name, "Active source has no URL configured."

    try:
        req = urllib.request.Request(api_url, headers={'User-Agent': 'HecosTrayCoreInstaller/1.0'})
        with urllib.request.urlopen(req, timeout=15) as response:
            resp_data = json.loads(response.read().decode('utf-8'))

        if source_type == "github_release":
            zipball_url = resp_data.get("zipball_url")
            if not zipball_url:
                return None, source_name, "No zipball_url found in the GitHub release response."
            return zipball_url, source_name, None
        else:
            # custom_json: expect {"zipball_url": "..."}
            zipball_url = resp_data.get("zipball_url")
            if not zipball_url:
                return None, source_name, "Custom source response does not contain 'zipball_url'."
            return zipball_url, source_name, None

    except Exception as e:
        return None, source_name, f"Network error: {str(e)}"


def install_core_from_scratch(progress_callback=None, status_callback=None) -> bool:
    """
    Downloads and installs Hecos Core from the active update source.

    Steps:
      1. Read active source -> fetch zipball URL via GitHub API (or custom JSON)
      2. Download ZIP to temp file, streaming with progress
      3. Extract to temp dir, move contents to _ROOT
      4. Launch HECOS_SETUP_CONSOLE_WIN.bat (or Linux equivalent)

    progress_callback(float 0.0-1.0)
    status_callback(str message)

    Returns True on success, False on failure.
    """
    def _status(msg):
        if status_callback:
            status_callback(msg)

    def _progress(p):
        if progress_callback:
            progress_callback(p)

    try:
        # --- Step 1: Resolve zipball URL from active source ---
        _status("Reading active source configuration…")
        zipball_url, source_name, err = _get_zipball_url_from_active_source()
        if err:
            _status(f"⚠ Error: {err}")
            return False

        _status(f"Source: {source_name} — Fetching release…")

        # --- Step 2: Download ---
        _status("Downloading Core… this may take a moment.")
        fd, temp_zip_path = tempfile.mkstemp(suffix=".zip", prefix="hecos_core_")
        os.close(fd)

        try:
            req_dl = urllib.request.Request(zipball_url, headers={'User-Agent': 'HecosTrayCoreInstaller/1.0'})
            with urllib.request.urlopen(req_dl, timeout=60) as response:
                total_size = int(response.info().get('Content-Length', -1))
                bytes_so_far = 0
                chunk_size = 128 * 1024  # 128 KB

                with open(temp_zip_path, "wb") as f:
                    while True:
                        chunk = response.read(chunk_size)
                        if not chunk:
                            break
                        f.write(chunk)
                        bytes_so_far += len(chunk)

                        if total_size > 0:
                            _progress(min(bytes_so_far / total_size * 0.85, 0.85))
                        else:
                            # No Content-Length — estimate based on 80MB expected
                            _progress(min(bytes_so_far / (80 * 1024 * 1024) * 0.85, 0.85))

            # --- Step 3: Extract ---
            _status("Extracting files…")
            _progress(0.88)

            temp_extract_dir = tempfile.mkdtemp(prefix="hecos_extract_")
            try:
                with zipfile.ZipFile(temp_zip_path, 'r') as zip_ref:
                    zip_ref.extractall(temp_extract_dir)

                # GitHub zipballs have a single root folder like "Hecos-Project-Hecos-abc123"
                extracted_items = os.listdir(temp_extract_dir)
                if len(extracted_items) == 1 and os.path.isdir(os.path.join(temp_extract_dir, extracted_items[0])):
                    source_dir = os.path.join(temp_extract_dir, extracted_items[0])
                else:
                    source_dir = temp_extract_dir

                _status(f"Installing to {_ROOT}…")
                _progress(0.93)
                os.makedirs(_ROOT, exist_ok=True)

                for item in os.listdir(source_dir):
                    s = os.path.join(source_dir, item)
                    d = os.path.join(_ROOT, item)
                    if os.path.exists(d):
                        if os.path.isdir(d):
                            shutil.rmtree(d, ignore_errors=True)
                        else:
                            os.remove(d)
                    shutil.move(s, d)

            finally:
                shutil.rmtree(temp_extract_dir, ignore_errors=True)

        finally:
            if os.path.exists(temp_zip_path):
                os.remove(temp_zip_path)

        _progress(1.0)

        # --- Step 4: Verify and run setup ---
        version_file = os.path.join(_ROOT, "hecos", "core", "version")
        if not os.path.exists(version_file):
            _status("⚠ Warning: Core installed but version file not found. Try running Setup.")

        _status("Core downloaded! Launch Setup to continue.")
        return True

    except Exception as e:
        _status(f"⚠ Error: {str(e)}")
        return False


def run_setup_wizard(status_callback=None):
    """
    Launches the Hecos Setup Wizard (web-based, via the console bat/sh).
    """
    def _status(msg):
        if status_callback:
            status_callback(msg)

    try:
        if sys.platform == "win32":
            wizard = os.path.join(_ROOT, "scripts", "windows", "setup", "HECOS_SETUP_CONSOLE_WIN.bat")
            if not os.path.exists(wizard):
                _status(f"⚠ Setup script not found at:\n{wizard}")
                return False
            subprocess.Popen(["cmd.exe", "/c", wizard], creationflags=0x00000010, cwd=_ROOT)
        else:
            wizard = os.path.join(_ROOT, "scripts", "linux", "setup", "HECOS_SETUP_CONSOLE_LINUX.sh")
            if not os.path.exists(wizard):
                _status(f"⚠ Setup script not found at:\n{wizard}")
                return False
            subprocess.Popen(["bash", wizard], start_new_session=True, cwd=_ROOT)

        _status("Setup Wizard launched — check your browser.")
        return True

    except Exception as e:
        _status(f"⚠ Could not launch Setup: {str(e)}")
        return False
