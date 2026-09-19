import os
import time
import threading
import tkinter as tk
import customtkinter as ctk

from tray.config import load_settings, save_settings, _ROOT
from tray.dashboard.theme import CARD, TEXT, MUTED, ACCENT, ACCENT2, RED, SURFACE, BORDER
from tray.dashboard.ui import title, subtitle, create_tooltip
from tray.dashboard.tabs.logs_controller import LogController

def build_logs(ctx):
    # Outer container
    outer = ctk.CTkFrame(ctx.content_frame, fg_color="transparent", corner_radius=0)
    outer.pack(fill="both", expand=True, padx=20, pady=20)
    ctx.append_widget(outer)

    title(ctx, outer, "Live Logs")
    subtitle(ctx, outer, "Read directly from disk — works even when the WebUI is offline.")

    # State variables
    full_color = [load_settings().get("full_color_logs", True)]
    is_paused = [False]

    # Default logs directory: Hecos Core hecos/logs subfolder
    _default_logs_dir = os.path.join(_ROOT, "hecos", "logs")
    _settings = load_settings()
    logs_dir = _settings.get("custom_logs_dir", _default_logs_dir)
    if not os.path.isdir(logs_dir):
        logs_dir = _default_logs_dir
    logs_dir_var = [logs_dir]  # mutable reference

    # ── Path Bar: shows current folder + browse button ─────────────────────
    path_row = ctk.CTkFrame(outer, fg_color="transparent")
    path_row.pack(fill="x", pady=(0, 4))

    path_lbl = ctk.CTkLabel(
        path_row, text=logs_dir_var[0],
        font=ctk.CTkFont(family="Consolas", size=10),
        text_color=MUTED, anchor="w"
    )
    path_lbl.pack(side="left", fill="x", expand=True)

    # ── File selector ────────────────────────────────────────────────────────
    ctrl_row = ctk.CTkFrame(outer, fg_color="transparent")
    ctrl_row.pack(fill="x", pady=(0, 6))

    file_var = ctk.StringVar(value="")
    file_dd = ctk.CTkOptionMenu(
        ctrl_row, variable=file_var,
        values=["(no logs)"],
        fg_color=CARD, button_color=ACCENT2,
        dropdown_fg_color=CARD, text_color=TEXT,
        font=ctk.CTkFont(size=11), width=180
    )
    file_dd.pack(side="left", padx=(0, 4))
    create_tooltip(file_dd, "Select log file to monitor")

    # Lines selector
    lines_var = ctk.StringVar(value="400")
    lines_dd = ctk.CTkOptionMenu(
        ctrl_row, variable=lines_var,
        values=["100", "400", "1000", "5000", "All"],
        fg_color=CARD, button_color=ACCENT2,
        dropdown_fg_color=CARD, text_color=TEXT,
        font=ctk.CTkFont(size=11), width=80
    )
    lines_dd.pack(side="left", padx=(0, 4))
    create_tooltip(lines_dd, "Select number of lines to display")

    # Search box
    search_frame = ctk.CTkFrame(ctrl_row, fg_color=CARD, border_width=1, border_color=BORDER, corner_radius=6)
    search_frame.pack(side="left", padx=(0, 4))
    
    search_icon = ctk.CTkLabel(search_frame, text="🔍", width=24, text_color=MUTED)
    search_icon.pack(side="left", padx=(6, 2))
    
    search_var = ctk.StringVar()
    search_entry = ctk.CTkEntry(search_frame, textvariable=search_var, placeholder_text="Search...", width=120, height=26, fg_color="transparent", border_width=0, text_color=TEXT)
    search_entry.pack(side="left", padx=(0, 6))
    create_tooltip(search_entry, "Search logs (filters entire file)")
    create_tooltip(search_icon, "Search logs (filters entire file)")

    lines_lbl = ctk.CTkLabel(ctrl_row, text="", font=ctk.CTkFont(size=10), text_color=MUTED)
    lines_lbl.pack(side="right")

    font_size = [10]  # mutable

    # Log text widget (tkinter Text for performance with large files)
    log_frame = ctk.CTkFrame(outer, fg_color=CARD, corner_radius=8)
    log_frame.pack(fill="both", expand=True, pady=(4, 0))

    log_text = tk.Text(
        log_frame, wrap="none",
        bg=CARD, fg=TEXT, selectbackground=ACCENT2, selectforeground="#ffffff",
        insertbackground=ACCENT,
        font=("Consolas", font_size[0]),
        relief="flat", padx=6, pady=4,
        state="disabled"
    )
    scroll_y = ctk.CTkScrollbar(log_frame, command=log_text.yview)
    scroll_x = ctk.CTkScrollbar(log_frame, orientation="horizontal",
                                command=log_text.xview)
    log_text.configure(yscrollcommand=scroll_y.set, xscrollcommand=scroll_x.set)

    scroll_y.pack(side="right", fill="y")
    scroll_x.pack(side="bottom", fill="x")
    log_text.pack(side="left", fill="both", expand=True)

    from tray.dashboard.tabs.logs_parser import SEV_COLORS, TAG_COLORS_MAP
    # Tags for coloring — severity levels
    for kw, col in SEV_COLORS.items():
        log_text.tag_configure(kw, foreground=col)
    log_text.tag_configure("MUTED", foreground=MUTED)
    log_text.tag_configure("URL", foreground=ACCENT, underline=True)

    # Tags for Source Tagging
    for tag_key, tag_col in TAG_COLORS_MAP.items():
        log_text.tag_configure(f"TAG_{tag_key}", foreground=tag_col, font=("Consolas", font_size[0], "bold"))

    def _open_url(event):
        try:
            import webbrowser
            idx = log_text.index(f"@{event.x},{event.y}")
            tags = log_text.tag_names(idx)
            if "URL" in tags:
                rng = log_text.tag_prevrange("URL", f"{idx}+1c")
                if rng:
                    url = log_text.get(rng[0], rng[1])
                    webbrowser.open(url)
        except Exception:
            pass

    log_text.tag_bind("URL", "<Button-1>", _open_url)
    log_text.tag_bind("URL", "<Enter>", lambda e: log_text.configure(cursor="hand2"))
    log_text.tag_bind("URL", "<Leave>", lambda e: log_text.configure(cursor=""))

    # Instantiate Controller
    controller = LogController(
        ctx=ctx,
        logs_dir_var=logs_dir_var,
        file_var=file_var,
        lines_var=lines_var,
        search_var=search_var,
        is_paused=is_paused,
        full_color=full_color,
        log_text=log_text,
        lines_lbl=lines_lbl,
        file_dd=file_dd
    )

    # Bindings
    file_dd.configure(command=controller.on_file_change)
    lines_dd.configure(command=lambda choice: (
        setattr(controller, '_last_size', 0),
        setattr(controller, '_last_line_count', 0),
        controller.load()
    ))
    search_entry.bind("<KeyRelease>", controller.schedule_search)

    def _browse_folder():
        from tkinter import filedialog
        chosen = filedialog.askopenfilename(
            title="Select Log File",
            initialdir=logs_dir_var[0],
            filetypes=[("Log Files", "*.log"), ("All Files", "*.*")]
        )
        if not chosen:
            return
            
        folder = os.path.dirname(chosen)
        file_name = os.path.basename(chosen)
        
        logs_dir_var[0] = folder
        path_lbl.configure(text=folder)
        # Persist the choice
        s = load_settings()
        s["custom_logs_dir"] = folder
        save_settings(s)
        # Reload the file list
        controller.refresh_file_list()
        
        # Select the chosen file in the dropdown
        if file_name in file_dd.cget("values"):
            file_var.set(file_name)
            controller.on_file_change(file_name)

    ctk.CTkButton(
        path_row, text="📂", width=34,
        fg_color=SURFACE, text_color=ACCENT,
        hover_color=BORDER, corner_radius=6,
        command=_browse_folder
    ).pack(side="right", padx=(6, 0))

    def _zoom(delta):
        font_size[0] = max(6, min(24, font_size[0] + delta))
        log_text.configure(font=("Consolas", font_size[0]))
        for tag_key, tag_col in TAG_COLORS_MAP.items():
            log_text.tag_configure(f"TAG_{tag_key}", font=("Consolas", font_size[0], "bold"))

    btn_row = ctk.CTkFrame(ctrl_row, fg_color="transparent")
    btn_row.pack(side="left", padx=8)

    def _update_pause_btn():
        if is_paused[0]:
            btn_pause.configure(text="⏸ Pause", text_color=RED)
        else:
            btn_pause.configure(text="▶ Active", text_color=MUTED)

    def _toggle_pause():
        is_paused[0] = not is_paused[0]
        _update_pause_btn()

    btn_pause = ctk.CTkButton(btn_row, text="", width=70, fg_color=SURFACE, text_color=MUTED,
                              hover_color=BORDER, corner_radius=6,
                              command=_toggle_pause)
    _update_pause_btn()
    btn_pause.pack(side="left", padx=2)
    create_tooltip(btn_pause, "Pause or resume live auto-refresh")

    def _toggle_full_color():
        full_color[0] = not full_color[0]
        s = load_settings()
        s["full_color_logs"] = full_color[0]
        save_settings(s)
        btn_color.configure(
            text="❖ Color" if full_color[0] else "◇ Simple",
            text_color=ACCENT if full_color[0] else MUTED
        )
        controller.load()

    btn_color = ctk.CTkButton(
        btn_row, text="❖ Color" if full_color[0] else "◇ Simple",
        width=80, fg_color=SURFACE,
        text_color=ACCENT if full_color[0] else MUTED,
        hover_color=BORDER, corner_radius=6,
        command=_toggle_full_color
    )
    btn_color.pack(side="left", padx=2)
    create_tooltip(btn_color, "Toggle syntax highlighting for logs")

    btn_zoom_out = ctk.CTkButton(btn_row, text="A-", width=34, fg_color=SURFACE, text_color=TEXT,
                  hover_color=BORDER, corner_radius=6, command=lambda: _zoom(-2))
    btn_zoom_out.pack(side="left", padx=2)
    create_tooltip(btn_zoom_out, "Decrease font size")

    btn_zoom_in = ctk.CTkButton(btn_row, text="A+", width=34, fg_color=SURFACE, text_color=TEXT,
                  hover_color=BORDER, corner_radius=6, command=lambda: _zoom(2))
    btn_zoom_in.pack(side="left", padx=2)
    create_tooltip(btn_zoom_in, "Increase font size")

    btn_refresh = ctk.CTkButton(btn_row, text="↻ Refresh", width=80, fg_color=SURFACE, text_color=ACCENT,
                  hover_color=BORDER, corner_radius=6, command=controller.full_refresh_from_btn)
    btn_refresh.pack(side="left", padx=2)
    create_tooltip(btn_refresh, "Force reload the entire file")

    btn_reset = ctk.CTkButton(btn_row, text="⌂ Main", width=70, fg_color=SURFACE, text_color=MUTED,
                  hover_color=BORDER, corner_radius=6, command=controller.reset_to_main)
    btn_reset.pack(side="left", padx=2)
    create_tooltip(btn_reset, "Reset to hecos_main.log")

    # Start
    controller.refresh_file_list(preserve_selection=False)
    controller.load()
    controller.start_auto_refresh()
