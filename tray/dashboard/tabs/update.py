import os
import sys
import datetime as _dt
import threading
import subprocess
import customtkinter as ctk

from tray.dashboard.theme import TEXT, MUTED, ACCENT, SURFACE, BORDER, RED, BG
from tray.update_sources import load_sources, set_active_source, add_source, remove_source, import_source_list, import_source_list_from_file
from tray.updater import check_for_updates, download_asset, apply_update_and_restart, get_tray_version, get_current_version
from tray.core_installer import install_core_from_scratch, run_setup_wizard
from tray.config import _ROOT, VERSION_FILE


def _card(parent, title):
    """Helper: creates a titled section card."""
    frame = ctk.CTkFrame(parent, fg_color=SURFACE, corner_radius=10)
    frame.pack(fill="x", pady=(0, 14), ipadx=2, ipady=2)
    ctk.CTkLabel(
        frame, text=title,
        font=ctk.CTkFont(size=13, weight="bold"),
        text_color=TEXT
    ).pack(anchor="w", padx=16, pady=(14, 6))
    return frame


def _is_core_installed() -> bool:
    """Detects whether Hecos Core is installed by checking the version file."""
    return os.path.exists(VERSION_FILE)


def build_update(ctx):
    container = ctk.CTkScrollableFrame(ctx.content_frame, fg_color="transparent")
    container.pack(fill="both", expand=True, padx=20, pady=16)
    ctx.content_widgets.append(container)

    # ── Page Header ────────────────────────────────────────────────────────────
    ctk.CTkLabel(
        container, text="Manage Core",
        font=ctk.CTkFont(size=22, weight="bold"), text_color=TEXT
    ).pack(anchor="w", pady=(0, 2))
    ctk.CTkLabel(
        container,
        text="Install, set up, and keep your Hecos Core up to date.",
        font=ctk.CTkFont(size=12), text_color=MUTED
    ).pack(anchor="w", pady=(0, 18))

    # ── Detect Core ───────────────────────────────────────────────────────────
    core_ok = _is_core_installed()

    # ══════════════════════════════════════════════════════════════════════════
    # SECTION 1 — Install & Setup
    # ══════════════════════════════════════════════════════════════════════════
    install_card = _card(container, "📥  Install & Setup")

    # Status badge
    if core_ok:
        try:
            core_ver = open(VERSION_FILE, encoding="utf-8").read().strip()
        except Exception:
            core_ver = "?"
        badge_text  = f"✅  Hecos Core installed  —  v{core_ver}  at  {_ROOT}"
        badge_color = "#4ade80"
    else:
        badge_text  = f"⚠  Core not found at: {_ROOT}  —  Download it to get started."
        badge_color = ACCENT

    ctk.CTkLabel(
        install_card, text=badge_text,
        font=ctk.CTkFont(size=11), text_color=badge_color,
        justify="left", wraplength=640
    ).pack(anchor="w", padx=16, pady=(0, 10))

    install_status = ctk.CTkLabel(install_card, text="", text_color=MUTED, font=ctk.CTkFont(size=11))
    install_status.pack(anchor="w", padx=16)

    install_progress = ctk.CTkProgressBar(install_card, fg_color=BORDER, progress_color=ACCENT)
    install_progress.set(0)

    # Buttons row
    btn_row = ctk.CTkFrame(install_card, fg_color="transparent")
    btn_row.pack(fill="x", padx=16, pady=(10, 14))
    btn_row.columnconfigure((0, 1), weight=1, uniform="ibtn")

    btn_cfg = dict(height=34, corner_radius=8, font=ctk.CTkFont(size=12))

    dl_btn_text = "📥  Re-Download Core" if core_ok else "📥  Download Core"
    dl_btn = ctk.CTkButton(
        btn_row, text=dl_btn_text,
        fg_color=BORDER if core_ok else ACCENT,
        text_color=TEXT if core_ok else "#000",
        hover_color=ACCENT, **btn_cfg
    )
    dl_btn.grid(row=0, column=0, padx=(0, 6), sticky="ew")

    setup_btn = ctk.CTkButton(
        btn_row, text="⚙  Run Setup Wizard",
        fg_color=BORDER, text_color=TEXT, hover_color=ACCENT,
        state="normal" if core_ok else "disabled",
        **btn_cfg
    )
    setup_btn.grid(row=0, column=1, padx=(6, 0), sticky="ew")

    def do_download():
        dl_btn.configure(state="disabled", text="Downloading…")
        setup_btn.configure(state="disabled")
        install_progress.pack(fill="x", padx=16, pady=(0, 8))
        install_progress.set(0)

        def _task():
            def prog(p): install_progress.set(p)
            def stat(msg):
                color = RED if "⚠" in msg else MUTED
                install_status.configure(text=msg, text_color=color)

            success = install_core_from_scratch(prog, stat)
            install_progress.pack_forget()
            if success:
                install_status.configure(text="✅ Core downloaded. Click 'Run Setup Wizard' to continue.", text_color="#4ade80")
                dl_btn.configure(state="normal", text="📥  Re-Download Core", fg_color=BORDER, text_color=TEXT)
                setup_btn.configure(state="normal")
            else:
                dl_btn.configure(state="normal", text=dl_btn_text)
                setup_btn.configure(state="disabled" if not core_ok else "normal")

        threading.Thread(target=_task, daemon=True).start()

    def do_setup():
        setup_btn.configure(state="disabled", text="Launching…")
        def stat(msg):
            color = RED if "⚠" in msg else "#4ade80"
            install_status.configure(text=msg, text_color=color)
        run_setup_wizard(status_callback=stat)
        setup_btn.configure(state="normal", text="⚙  Run Setup Wizard")

    dl_btn.configure(command=do_download)
    setup_btn.configure(command=do_setup)

    # ══════════════════════════════════════════════════════════════════════════
    # SECTION 2 — Update Sources
    # ══════════════════════════════════════════════════════════════════════════
    src_card = _card(container, "🔗  Update Sources")

    sources_data = load_sources()
    active_src   = sources_data.get("active_source", "")
    all_sources  = sources_data.get("sources", [])
    source_names = [s["name"] for s in all_sources] or ["(No sources configured)"]

    src_var = ctk.StringVar(value=active_src if active_src in source_names else source_names[0])

    # Log box
    log_frame = ctk.CTkFrame(src_card, fg_color=BG, corner_radius=6)
    log_frame.pack(fill="x", padx=16, pady=(4, 10))
    src_log = ctk.CTkTextbox(
        log_frame, height=90, fg_color=BG, text_color="#a3e4a3",
        font=ctk.CTkFont(family="Consolas", size=11), wrap="word", state="normal"
    )
    src_log.pack(fill="x", padx=4, pady=4)

    def _src_log(msg: str):
        ts = _dt.datetime.now().strftime("%H:%M:%S")
        src_log.configure(state="normal")
        src_log.insert("end", f"[{ts}] {msg}\n")
        src_log.see("end")
        src_log.configure(state="disabled")

    active_url = next((s.get("url", "") for s in all_sources if s["name"] == src_var.get()), "")
    _src_log(f"Active: {src_var.get()}")
    _src_log(f"URL:    {active_url}")
    src_log.configure(state="disabled")

    # Active source dropdown
    ctk.CTkLabel(src_card, text="Active source:", text_color=MUTED,
                 font=ctk.CTkFont(size=11)).pack(anchor="w", padx=16)

    def on_source_change(val):
        set_active_source(val)
        new_url = next((s.get("url", "") for s in all_sources if s["name"] == val), "")
        _src_log(f"Switched to: {val}")
        _src_log(f"URL: {new_url}")

    ctk.CTkOptionMenu(
        src_card, values=source_names, variable=src_var, command=on_source_change,
        fg_color=BORDER, button_color=BORDER, button_hover_color=ACCENT,
        dropdown_fg_color=SURFACE, text_color=TEXT, height=32
    ).pack(fill="x", padx=16, pady=(4, 8))

    # Add / Remove buttons
    src_btn_row = ctk.CTkFrame(src_card, fg_color="transparent")
    src_btn_row.pack(fill="x", padx=16, pady=(0, 8))
    src_btn_row.columnconfigure((0, 1), weight=1, uniform="sbtn")

    def remove_selected():
        remove_source(src_var.get())
        _src_log(f"Removed: {src_var.get()}")
        ctx.switch_tab_fn("update")

    add_panel = ctk.CTkFrame(src_card, fg_color="transparent")

    def toggle_add_panel():
        if add_panel.winfo_ismapped():
            add_panel.pack_forget()
            add_btn.configure(text="+ Add Source")
        else:
            add_panel.pack(fill="x", padx=16, pady=(4, 4))
            add_btn.configure(text="▲ Hide")

    ctk.CTkButton(
        src_btn_row, text="✕  Remove Selected",
        fg_color="transparent", border_width=1, border_color=RED,
        text_color=RED, hover_color="#3a1a1a", height=32,
        command=remove_selected
    ).grid(row=0, column=0, padx=(0, 6), sticky="ew")

    add_btn = ctk.CTkButton(
        src_btn_row, text="+ Add Source",
        fg_color=BORDER, text_color=TEXT, hover_color=ACCENT, height=32,
        command=toggle_add_panel
    )
    add_btn.grid(row=0, column=1, sticky="ew")

    # Add source panel (hidden by default)
    name_entry = ctk.CTkEntry(add_panel, placeholder_text="Source name  (e.g. My Mirror)")
    name_entry.pack(fill="x", pady=3)
    url_entry_add = ctk.CTkEntry(add_panel, placeholder_text="URL  (GitHub API releases/latest or custom JSON)")
    url_entry_add.pack(fill="x", pady=3)
    type_var = ctk.StringVar(value="github_release")
    ctk.CTkOptionMenu(
        add_panel, values=["github_release", "custom_json"], variable=type_var,
        fg_color=BORDER, button_color=BORDER, button_hover_color=ACCENT,
        dropdown_fg_color=SURFACE, text_color=TEXT
    ).pack(fill="x", pady=3)

    def save_new_source():
        n, u, t = name_entry.get().strip(), url_entry_add.get().strip(), type_var.get()
        if n and u:
            add_source(n, u, t)
            _src_log(f"Added: {n}  [{t}]  {u}")
            ctx.switch_tab_fn("update")
        else:
            _src_log("⚠ Please fill in both name and URL.")

    ctk.CTkButton(
        add_panel, text="Save Source", fg_color=ACCENT,
        text_color="#000", hover_color=ACCENT, height=32,
        command=save_new_source
    ).pack(anchor="e", pady=(6, 0))

    # Import row
    ctk.CTkFrame(src_card, height=1, fg_color=BORDER).pack(fill="x", padx=16, pady=(4, 10))
    ctk.CTkLabel(src_card, text="📥  Import source list:", text_color=MUTED,
                 font=ctk.CTkFont(size=11)).pack(anchor="w", padx=16)

    import_row = ctk.CTkFrame(src_card, fg_color="transparent")
    import_row.pack(fill="x", padx=16, pady=(4, 14))
    import_row.columnconfigure(0, weight=1)

    import_url_entry = ctk.CTkEntry(
        import_row,
        placeholder_text="Paste URL (Pastebin, GitHub raw, etc.)  or  load from file →",
        height=32
    )
    import_url_entry.grid(row=0, column=0, sticky="ew", padx=(0, 6))

    def do_import():
        url = import_url_entry.get().strip()
        if not url:
            _src_log("⚠ Enter a URL or use the file button.")
            return
        _src_log(f"Fetching: {url}")
        def _task():
            added, err = import_source_list(url)
            if err:
                _src_log(f"⚠ {err}")
            else:
                _src_log(f"✅ {added} new source(s) added.")
                if added > 0:
                    ctx.switch_tab_fn("update")
        threading.Thread(target=_task, daemon=True).start()

    ctk.CTkButton(
        import_row, text="⬇ URL",
        fg_color=BORDER, text_color=TEXT, hover_color=ACCENT, height=32, width=70,
        command=do_import
    ).grid(row=0, column=1, padx=(0, 6))

    def do_import_file():
        from tkinter import filedialog
        path = filedialog.askopenfilename(
            title="Select Hecos Sources List (.toml)",
            filetypes=[("TOML files", "*.toml"), ("All files", "*.*")]
        )
        if not path:
            return
        _src_log(f"Loading file: {os.path.basename(path)}")
        def _task():
            added, err = import_source_list_from_file(path)
            if err:
                _src_log(f"⚠ {err}")
            else:
                _src_log(f"✅ {added} new source(s) added.")
                if added > 0:
                    ctx.switch_tab_fn("update")
        threading.Thread(target=_task, daemon=True).start()

    ctk.CTkButton(
        import_row, text="📂 File",
        fg_color=BORDER, text_color=TEXT, hover_color=ACCENT, height=32, width=70,
        command=do_import_file
    ).grid(row=0, column=2)

    # ══════════════════════════════════════════════════════════════════════════
    # SECTION 3 — Check & Install Updates
    # (disabled if Core is not installed)
    # ══════════════════════════════════════════════════════════════════════════
    upd_card = _card(container, "🔄  Check & Install Updates")

    if not core_ok:
        ctk.CTkLabel(
            upd_card,
            text="⚠  Install Hecos Core first to enable updates.",
            font=ctk.CTkFont(size=11), text_color=MUTED
        ).pack(anchor="w", padx=16, pady=(0, 14))
    else:
        curr_core_v = get_current_version()
        curr_tray_v = get_tray_version()

        ver_frame = ctk.CTkFrame(upd_card, fg_color="transparent")
        ver_frame.pack(fill="x", padx=16, pady=(0, 8))
        ctk.CTkLabel(ver_frame, text="• Core:", text_color=MUTED, font=ctk.CTkFont(size=12, weight="bold")).grid(row=0, column=0, sticky="w", padx=(0, 10))
        ctk.CTkLabel(ver_frame, text=f"v{curr_core_v}", text_color=TEXT, font=ctk.CTkFont(size=12)).grid(row=0, column=1, sticky="w")
        ctk.CTkLabel(ver_frame, text="• Tray:", text_color=MUTED, font=ctk.CTkFont(size=12, weight="bold")).grid(row=1, column=0, sticky="w", padx=(0, 10))
        ctk.CTkLabel(ver_frame, text=f"v{curr_tray_v}", text_color=TEXT, font=ctk.CTkFont(size=12)).grid(row=1, column=1, sticky="w")

        upd_status = ctk.CTkLabel(upd_card, text="", text_color=TEXT, font=ctk.CTkFont(size=11))
        upd_status.pack(anchor="w", padx=16)

        upd_progress = ctk.CTkProgressBar(upd_card, fg_color=BORDER, progress_color=ACCENT)
        upd_progress.set(0)

        upd_btn = ctk.CTkButton(
            upd_card, text="🔄  Check for Updates",
            fg_color=ACCENT, text_color="#000", hover_color=ACCENT, height=34
        )
        upd_btn.pack(anchor="w", padx=16, pady=(10, 14))

        _dl_files = {}

        def do_check():
            src = src_var.get()
            if not src or src == "(No sources configured)":
                upd_status.configure(text="⚠ No update source selected.", text_color=RED)
                return
            upd_btn.configure(state="disabled", text="Checking…")
            upd_status.configure(text="Contacting update server…", text_color=MUTED)

            def _task():
                res = check_for_updates()
                err = res.get("error")
                if err:
                    upd_status.configure(text=f"⚠ {err}", text_color=RED)
                    upd_btn.configure(state="normal", text="🔄  Check for Updates", command=do_check)
                elif res.get("update_available"):
                    lv = res["latest_version"]
                    upd_status.configure(text=f"✅ Update available: v{lv}", text_color="#4ade80")
                    upd_btn.configure(
                        state="normal", text=f"⬇  Download v{lv}",
                        command=lambda: do_download(res["assets"])
                    )
                else:
                    upd_status.configure(text="✓ You are on the latest version.", text_color="#4ade80")
                    upd_btn.configure(state="normal", text="🔄  Check for Updates", command=do_check)

            threading.Thread(target=_task, daemon=True).start()

        def do_download(assets):
            upd_btn.configure(state="disabled", text="Downloading…")
            upd_progress.pack(fill="x", padx=16, pady=(0, 8))

            def _task():
                try:
                    temp_dir = os.path.join(_ROOT, "bin", "update_temp")
                    os.makedirs(temp_dir, exist_ok=True)

                    target_assets = []
                    for a in assets:
                        nl = a["name"].lower()
                        if sys.platform == "win32" and nl.endswith(".exe"):
                            target_assets.append(a)
                        elif sys.platform != "win32" and not nl.endswith(".exe"):
                            if any(k in nl for k in ("linux", "darwin", "mac")):
                                target_assets.append(a)

                    if not target_assets:
                        upd_status.configure(text="⚠ No compatible assets found for this OS.", text_color=RED)
                        upd_progress.pack_forget()
                        upd_btn.configure(state="normal", text="🔄  Check for Updates", command=do_check)
                        return

                    for i, asset in enumerate(target_assets):
                        upd_status.configure(
                            text=f"Downloading {asset['name']} ({i+1}/{len(target_assets)})…",
                            text_color=MUTED
                        )
                        def cb(done, total, bar=upd_progress):
                            if total > 0:
                                bar.set(done / total)

                        dest = os.path.join(temp_dir, asset["name"])
                        download_asset(asset["url"], dest, cb)
                        nl = asset["name"].lower()
                        if "tray" in nl:
                            _dl_files["tray"] = dest
                        elif "dashboard" in nl or "control" in nl:
                            _dl_files["dashboard"] = dest

                    upd_status.configure(text="✅ Download complete — ready to apply.", text_color="#4ade80")
                    upd_progress.pack_forget()
                    upd_btn.configure(state="normal", text="⚡  Restart & Apply", command=do_apply)

                except Exception as e:
                    upd_status.configure(text=f"⚠ {e}", text_color=RED)
                    upd_progress.pack_forget()
                    upd_btn.configure(state="normal", text="Retry", command=lambda: do_download(assets))

            threading.Thread(target=_task, daemon=True).start()

        def do_apply():
            upd_btn.configure(state="disabled", text="Applying…")
            upd_status.configure(text="Launching updater and restarting…", text_color=MUTED)
            apply_update_and_restart(
                _dl_files.get("tray", ""),
                _dl_files.get("dashboard", "")
            )

        upd_btn.configure(command=do_check)

    # ══════════════════════════════════════════════════════════════════════════
    # SECTION 4 — Uninstall & Cleanup
    # ══════════════════════════════════════════════════════════════════════════
    import shutil
    import tempfile

    uni_card = _card(container, "🗑  Uninstall & Cleanup")

    ctk.CTkLabel(
        uni_card,
        text=(
            "Permanently remove Hecos from your system.\n"
            "The selected components will be uninstalled in the background "
            "after this window closes."
        ),
        font=ctk.CTkFont(size=11), text_color=MUTED, justify="left", wraplength=460
    ).pack(anchor="w", padx=16, pady=(0, 8))

    uni_status = ctk.CTkLabel(uni_card, text="", text_color=MUTED, font=ctk.CTkFont(size=11))
    uni_status.pack(anchor="w", padx=16)

    # ── Source script path (shipped alongside the Tray) ──
    _TRAY_PKG_DIR = os.path.dirname(os.path.abspath(__file__))
    _TERMINATOR_SRC = os.path.join(_TRAY_PKG_DIR, "..", "..", "uninstall_terminator.py")
    _TERMINATOR_SRC = os.path.normpath(_TERMINATOR_SRC)

    def _launch_terminator(mode: str):
        """Copy the terminator to temp and launch it detached, then quit the Tray."""
        try:
            # Copy to system temp so it can delete our own folders
            tmp_dir = tempfile.gettempdir()
            dest = os.path.join(tmp_dir, "hecos_uninstall_terminator.py")
            shutil.copy2(_TERMINATOR_SRC, dest)

            # Build launch command - new console window so user can see progress
            if sys.platform == "win32":
                # Force python.exe (console) instead of pythonw.exe (windowless)
                exe_cmd = sys.executable.replace("pythonw.exe", "python.exe")
                subprocess.Popen(
                    [exe_cmd, dest, "--mode", mode, "--wait", "4"],
                    creationflags=subprocess.CREATE_NEW_CONSOLE,
                )
            else:
                subprocess.Popen(
                    [sys.executable, dest, "--mode", mode, "--wait", "4"],
                    start_new_session=True,
                    close_fds=True,
                )

            uni_status.configure(
                text=(
                    f"Uninstallation started ({mode.upper()} mode).\n"
                    "A terminal window will show the progress.\n"
                    "Hecos Tray will now close."
                ),
                text_color="#f97316"
            )
            # Give the user 3 seconds to read the message, then quit Tray
            uni_status.after(3000, lambda: os.kill(os.getpid(), 9) if sys.platform != "win32"
                             else subprocess.call(["taskkill", "/F", "/PID", str(os.getpid())]))

        except FileNotFoundError:
            uni_status.configure(
                text="⚠ uninstall_terminator.py not found in Tray folder.",
                text_color=RED
            )
        except Exception as e:
            uni_status.configure(text=f"⚠ {e}", text_color=RED)

    def _confirm_and_run(mode: str, label: str):
        """Show a confirmation label and then run after a short delay."""
        descriptions = {
            "full": "ALL Hecos data (Core + Tray + all dependencies + both folders).",
            "core": "Hecos Core and its dependencies. The Tray will remain.",
            "tray": "Hecos Tray and its dependencies. The Core will remain.",
        }
        uni_status.configure(
            text=f"⚠ {label}: This will permanently remove {descriptions[mode]}\nClick again to confirm.",
            text_color=RED
        )
        # Second click confirms
        for btn in _uninstall_buttons:
            btn.configure(state="disabled")
        confirm_btn.configure(
            state="normal", text=f"CONFIRM: {label}",
            command=lambda: _launch_terminator(mode)
        )

    _uninstall_buttons = []
    uni_cfg = dict(height=32, corner_radius=8, font=ctk.CTkFont(size=11))
    uni_buttons = ctk.CTkFrame(uni_card, fg_color="transparent")
    uni_buttons.pack(fill="x", padx=16, pady=(6, 4))
    uni_buttons.columnconfigure((0, 1, 2), weight=1, uniform="ubtn")

    b1 = ctk.CTkButton(
        uni_buttons, text="Remove Core",
        fg_color=BORDER, text_color=TEXT, hover_color="#8b5cf6",
        command=lambda: _confirm_and_run("core", "Remove Core"), **uni_cfg
    )
    b1.grid(row=0, column=0, padx=(0, 6), sticky="ew")

    b2 = ctk.CTkButton(
        uni_buttons, text="Remove Tray",
        fg_color=BORDER, text_color=TEXT, hover_color="#f97316",
        command=lambda: _confirm_and_run("tray", "Remove Tray"), **uni_cfg
    )
    b2.grid(row=0, column=1, padx=6, sticky="ew")

    b3 = ctk.CTkButton(
        uni_buttons, text="🔴  Full Nuke (Both)",
        fg_color="transparent", border_width=1, border_color=RED,
        text_color=RED, hover_color="#3a1a1a",
        command=lambda: _confirm_and_run("full", "Full Nuke"), **uni_cfg
    )
    b3.grid(row=0, column=2, padx=(6, 0), sticky="ew")
    _uninstall_buttons.extend([b1, b2, b3])

    # Hidden confirm button — appears only after first click
    confirm_btn = ctk.CTkButton(
        uni_card, text="", state="disabled",
        fg_color=RED, hover_color="#7f1d1d", text_color="white",
        height=32, corner_radius=8, font=ctk.CTkFont(size=11, weight="bold")
    )
    confirm_btn.pack(fill="x", padx=16, pady=(4, 14))
