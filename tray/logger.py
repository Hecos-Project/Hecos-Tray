import sys
import os
import datetime
import traceback

class TrayLogger:
    def __init__(self, log_dir: str):
        self.log_dir = log_dir
        self.log_file = os.path.join(self.log_dir, "tray_error.log")
        
        # Ensure log directory exists
        os.makedirs(self.log_dir, exist_ok=True)
        
        # Rotate logs if too big (> 1MB)
        self._rotate_log_if_needed()
        
        # Keep references to original streams
        self.original_stdout = sys.stdout
        self.original_stderr = sys.stderr

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
            
        # Also print to original stdout/stderr if we are in a console (like DEBUG_TRAY.bat)
        if level in ("ERROR", "EXCEPTION") and self.original_stderr:
            try:
                self.original_stderr.write(formatted)
                self.original_stderr.flush()
            except Exception:
                pass
        elif self.original_stdout:
            try:
                self.original_stdout.write(formatted)
                self.original_stdout.flush()
            except Exception:
                pass

    def write(self, message: str):
        if message.strip():
            self.log(message.strip(), "STDOUT")

    def flush(self):
        pass

def excepthook_handler(exc_type, exc_value, exc_traceback):
    """Global exception handler to ensure uncaught exceptions are logged."""
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return
        
    error_msg = "".join(traceback.format_exception(exc_type, exc_value, exc_traceback))
    _global_logger.log(f"UNCAUGHT EXCEPTION:\n{error_msg}", "EXCEPTION")

# Global instance initialized when setup_logger is called
_global_logger = None

def setup_logger(root_dir: str):
    """
    Initializes the Tray Logger.
    Redirects stdout and stderr to the log file.
    Hooks into sys.excepthook to catch any fatal crashes.
    """
    global _global_logger
    if _global_logger is not None:
        return
        
    log_dir = os.path.join(root_dir, "logs")
    _global_logger = TrayLogger(log_dir)
    
    # Redirect standard streams to our logger
    sys.stdout = _global_logger
    sys.stderr = _global_logger
    
    # Override global exception handler
    sys.excepthook = excepthook_handler
    
    _global_logger.log("=== TRAY APPLICATION STARTED ===", "INFO")
