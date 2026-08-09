"""
MODULE: tray/logger.py
PURPOSE: Automatic logging system for Hecos Tray.
         Runs on every startup (Windows + Linux) — no debug mode needed.
         - Redirects all stdout/stderr to logs/tray_error.log
         - Captures uncaught exceptions via sys.excepthook
         - Rotates log at 1MB
         - Logs rich system info at every session start
"""

import sys
import os
import datetime
import traceback
import platform


class TrayLogger:
    def __init__(self, log_dir: str):
        self.log_dir = log_dir
        self.log_file = os.path.join(self.log_dir, "tray_error.log")

        # Ensure log directory exists
        os.makedirs(self.log_dir, exist_ok=True)

        # Rotate logs if too big (> 1MB)
        self._rotate_log_if_needed()

        # Keep references to original streams (for console passthrough if attached)
        self.original_stdout = sys.stdout
        self.original_stderr = sys.stderr

        # Detect if we are running with an attached console (e.g. DEBUG_TRAY.bat)
        self._has_console = self._check_console()

    def _check_console(self) -> bool:
        """Returns True if the process has an interactive terminal attached."""
        try:
            return os.isatty(self.original_stdout.fileno()) if self.original_stdout else False
        except Exception:
            return False

    def _rotate_log_if_needed(self):
        try:
            if os.path.exists(self.log_file) and os.path.getsize(self.log_file) > 1024 * 1024:
                backup = self.log_file + ".bak"
                if os.path.exists(backup):
                    os.remove(backup)
                os.rename(self.log_file, backup)
        except Exception:
            pass

    def log(self, message: str, level: str = "INFO"):
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        formatted = f"[{timestamp}] [{level}] {message}\n"

        try:
            with open(self.log_file, "a", encoding="utf-8") as f:
                f.write(formatted)
        except Exception:
            pass

        # Mirror to the real console if one is attached (DEBUG_TRAY / terminal)
        if self._has_console:
            try:
                stream = self.original_stderr if level in ("ERROR", "EXCEPTION") else self.original_stdout
                if stream:
                    stream.write(formatted)
                    stream.flush()
            except Exception:
                pass

    # ── stream-compatible interface so sys.stdout = logger works ───────────────
    def write(self, message: str):
        if message.strip():
            self.log(message.strip(), "STDOUT")

    def flush(self):
        pass

    def fileno(self):
        """Return a valid file descriptor so isatty() / fileno() calls don't crash."""
        return self.original_stdout.fileno() if self.original_stdout else -1


def excepthook_handler(exc_type, exc_value, exc_traceback):
    """Global exception handler — ensures fatal crashes are always logged."""
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return
    error_msg = "".join(traceback.format_exception(exc_type, exc_value, exc_traceback))
    if _global_logger:
        _global_logger.log(f"UNCAUGHT EXCEPTION:\n{error_msg}", "EXCEPTION")


# Global instance initialized when setup_logger is called
_global_logger: TrayLogger | None = None


def get_logger() -> TrayLogger | None:
    """Returns the global logger instance (or None if not yet initialized)."""
    return _global_logger


def setup_logger(root_dir: str):
    """
    Initializes the Tray Logger.
    - Redirects stdout and stderr to logs/tray_error.log
    - Hooks sys.excepthook to capture fatal crashes
    - Writes a rich session header with system info
    Should be called ONCE at startup, before any other import.
    """
    global _global_logger
    if _global_logger is not None:
        return

    log_dir = os.path.join(root_dir, "logs")
    _global_logger = TrayLogger(log_dir)

    # Redirect standard streams
    sys.stdout = _global_logger
    sys.stderr = _global_logger

    # Capture uncaught exceptions
    sys.excepthook = excepthook_handler

    # ── Write rich session header ──────────────────────────────────────────────
    sep = "=" * 60
    _global_logger.log(sep, "INFO")
    _global_logger.log("=== TRAY SESSION STARTED ===", "INFO")
    _global_logger.log(sep, "INFO")

    try:
        _global_logger.log(f"  Timestamp : {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", "INFO")
        _global_logger.log(f"  OS        : {platform.system()} {platform.release()} ({platform.version()})", "INFO")
        _global_logger.log(f"  Machine   : {platform.machine()} / {platform.processor()}", "INFO")
        _global_logger.log(f"  Python    : {sys.version.splitlines()[0]}", "INFO")
        _global_logger.log(f"  Executable: {sys.executable}", "INFO")
        _global_logger.log(f"  Tray root : {root_dir}", "INFO")
        _global_logger.log(f"  Log file  : {_global_logger.log_file}", "INFO")
    except Exception as e:
        _global_logger.log(f"  [warn] Could not collect full system info: {e}", "INFO")

    _global_logger.log(sep, "INFO")
