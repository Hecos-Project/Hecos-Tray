import os
import time
import threading
import tkinter as tk
from tray.dashboard.tabs.logs_parser import parse_log_lines

class LogController:
    def __init__(self, ctx, logs_dir_var, file_var, lines_var, search_var, is_paused, full_color, log_text, lines_lbl, file_dd):
        self.ctx = ctx
        self.logs_dir_var = logs_dir_var
        self.file_var = file_var
        self.lines_var = lines_var
        self.search_var = search_var
        self.is_paused = is_paused
        self.full_color = full_color
        self.log_text = log_text
        self.lines_lbl = lines_lbl
        self.file_dd = file_dd
        
        self._last_size = 0
        self._last_line_count = 0
        self._search_job = None

    def refresh_file_list(self, preserve_selection=False):
        """Refresh the list of available log files.
        
        If preserve_selection=True, keeps the currently selected file if it
        still exists in the folder after the refresh.
        """
        d = self.logs_dir_var[0]
        log_files = []
        try:
            log_files = sorted(
                [f for f in os.listdir(d) if f.endswith(".log")],
                key=lambda x: os.path.getmtime(os.path.join(d, x)),
                reverse=True
            )
        except Exception:
            pass
            
        if log_files:
            self.file_dd.configure(values=log_files)
            current = self.file_var.get()
            if preserve_selection and current in log_files:
                # Keep user's current file selection — do not reset
                pass
            else:
                default = "hecos_main.log" if "hecos_main.log" in log_files else log_files[0]
                self.file_var.set(default)
            self._last_size = 0
            self._last_line_count = 0
        else:
            self.file_dd.configure(values=["(no logs)"])
            self.file_var.set("(no logs)")
            self.log_text.configure(state="normal")
            self.log_text.delete("1.0", "end")
            self.log_text.insert("end", f"No .log files found in:\n{d}")
            self.log_text.configure(state="disabled")

    def reset_to_main(self):
        """Reset file selection to hecos_main.log and reload."""
        files = self.file_dd.cget("values")
        if "hecos_main.log" in files:
            self.file_var.set("hecos_main.log")
        elif files:
            self.file_var.set(files[0])
        self._last_size = 0
        self._last_line_count = 0
        self.load()

    def schedule_search(self, event=None):
        if self._search_job:
            self.ctx.app.after_cancel(self._search_job)
        self._search_job = self.ctx.app.after(500, self.load)

    def load(self, auto=False):
        fname = self.file_var.get()
        if not fname or fname == "(no logs)": return
        path = os.path.join(self.logs_dir_var[0], fname)
        if not os.path.exists(path): return
        threading.Thread(target=self._do_full_reload, args=(path,), daemon=True).start()

    def on_file_change(self, choice):
        self._last_size = 0
        self._last_line_count = 0
        self.load()

    def full_refresh_from_btn(self):
        self._last_size = 0
        self._last_line_count = 0
        self.refresh_file_list(preserve_selection=True)
        self.load()

    def _full_reload_on_main(self, segments, total, tail_len):
        self.log_text.configure(state="normal")
        self.log_text.delete("1.0", "end")
        for text, tag in segments:
            self.log_text.insert("end", text, tag)
        self.log_text.configure(state="disabled")
        self.log_text.see("end")
        self.lines_lbl.configure(text=f"{total} lines — showing last {tail_len}")

    def _do_full_reload(self, path):
        try:
            sz = os.path.getsize(path)
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                all_lines = f.readlines()
            self._last_size = sz
            self._last_line_count = len(all_lines)
            
            q = self.search_var.get().lower()
            if q:
                filtered_lines = [line for line in all_lines if q in line.lower()]
            else:
                filtered_lines = all_lines
                
            nl = self.lines_var.get()
            if nl == "All":
                tail = filtered_lines
            else:
                try:
                    limit = int(nl)
                except ValueError:
                    limit = 400
                tail = filtered_lines[-limit:] if len(filtered_lines) > limit else filtered_lines
            
            segments = parse_log_lines(tail, full_color=self.full_color[0])
            self.ctx.app.after(0, self._full_reload_on_main, segments, len(filtered_lines), len(tail))
        except Exception as ex:
            def _show_error():
                self.log_text.configure(state="normal")
                self.log_text.delete("1.0", "end")
                self.log_text.insert("end", f"Error reading log: {ex}")
                self.log_text.configure(state="disabled")
            self.ctx.app.after(0, _show_error)

    def start_auto_refresh(self):
        threading.Thread(target=self._auto_refresh_loop, daemon=True).start()

    def _auto_refresh_loop(self):
        while self.ctx.active_tab["key"] == "logs":
            time.sleep(0.5)
            if self.ctx.active_tab["key"] != "logs" or self.is_paused[0]:
                continue
            fname = self.file_var.get()
            if not fname or fname == "(no logs)":
                continue
            path = os.path.join(self.logs_dir_var[0], fname)
            try:
                sz = os.path.getsize(path)
                if sz == self._last_size:
                    continue
                with open(path, "r", encoding="utf-8", errors="replace") as f:
                    all_lines = f.readlines()
                total = len(all_lines)
                already = self._last_line_count
                if total < already:
                    self._last_size = 0
                    self._last_line_count = 0
                    self.ctx.app.after(0, self.load)
                    continue
                
                new_lines = all_lines[already:]
                self._last_size = sz
                self._last_line_count = total
                
                if not new_lines:
                    continue
                    
                q = self.search_var.get().lower()
                if q:
                    new_lines = [line for line in new_lines if q in line.lower()]
                
                if not new_lines:
                    continue
                    
                segments = parse_log_lines(new_lines, full_color=self.full_color[0])
                
                def _push(segs=segments, tot=total, nl=len(new_lines)):
                    at_bottom = self.log_text.yview()[1] >= 0.97
                    self.log_text.configure(state="normal")
                    for text, tag in segs:
                        self.log_text.insert("end", text, tag)
                    self.log_text.configure(state="disabled")
                    if at_bottom:
                        self.log_text.see("end")
                    self.lines_lbl.configure(text=f"{tot} file lines (+{nl} matched)")
                self.ctx.app.after(0, _push)
            except Exception:
                pass
