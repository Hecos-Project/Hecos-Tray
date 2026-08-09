import os
import sys
import datetime as _dt
import threading
import subprocess
import shutil
import tempfile
import customtkinter as ctk

from tray.dashboard.theme import TEXT, MUTED, ACCENT, SURFACE, BORDER, RED, BG
from tray.update_sources import load_sources, set_active_source, add_source, remove_source, import_source_list, import_source_list_from_file
from tray.updater import check_for_updates, download_asset, apply_update_and_restart, get_tray_version, get_current_version
from tray.core_installer import install_core_from_scratch, run_setup_wizard
from tray.config import _ROOT, VERSION_FILE, _TRAY_DIR


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
    return os.path.exists(VERSION_FILE)


def _get_python_info():
    """Returns a dict with python info for system, core, and tray environments."""
    results = {}

    # --- System Python ---
    sys_exe = ""
    for cmd in [["py", "-3", "--version"], ["python3", "--version"], ["python", "--version"]]:
        try:
            out = subprocess.check_output(cmd, stderr=subprocess.STDOUT, timeout=5, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0x08000000)).decode().strip()
            path_cmd = cmd[:-1] + ["-c", "import sys; print(sys.executable)"]
            sys_exe = subprocess.check_output(path_cmd, stderr=subprocess.STDOUT, timeout=5, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0x08000000)).decode().strip()
            results["system"] = {"version": out, "path": sys_exe, "ok": True}
            break
        except Exception:
            continue
    if "system" not in results:
        results["system"] = {"version": "Not found", "path": "", "ok": False}

    # --- Core Python ---
    core_py = os.path.join(_ROOT, "python_env", "python.exe")
    core_venv = os.path.join(_ROOT, "venv", "Scripts", "python.exe")
    core_type = "Portable"
    if os.path.exists(core_py):
        core_exe = core_py
    elif os.path.exists(core_venv):
        core_exe = core_venv
        core_type = "Venv"
    else:
        core_exe = sys_exe if sys_exe else "python"
        core_type = "System Fallback"

    try:
        out = subprocess.check_output([core_exe, "--version"], stderr=subprocess.STDOUT, timeout=5, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0x08000000)).decode().strip()
        results["core"] = {"version": out, "path": core_exe if core_exe != "python" else "", "ok": True, "type": core_type}
    except Exception as e:
        results["core"] = {"version": f"Not found \u2014 install Python or run Core Setup Wizard", "path": "", "ok": False, "type": core_type}

    # --- Tray Python ---
    tray_root_dir = os.path.abspath(os.path.join(_TRAY_DIR, ".."))
    tray_py = os.path.join(tray_root_dir, "python_env", "python.exe")
    tray_type = "Portable"
    if os.path.exists(tray_py):
        tray_exe = tray_py
    else:
        tray_exe = sys.executable
        tray_type = "System Fallback"
        
    try:
        out = subprocess.check_output([tray_exe, "--version"], stderr=subprocess.STDOUT, timeout=5, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0x08000000)).decode().strip()
        results["tray"] = {"version": out, "path": tray_exe, "ok": True, "type": tray_type}
    except Exception as e:
        results["tray"] = {"version": f"Error: {e}", "path": tray_exe, "ok": False, "type": tray_type}

    return results


def _check_packages(python_exe, packages):
    result = {}
    for pkg in packages:
        try:
            out = subprocess.check_output(
                [python_exe, "-c", f"import importlib.metadata; print(importlib.metadata.version('{pkg}'))"],
                stderr=subprocess.DEVNULL, timeout=5, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0x08000000)
            ).decode().strip()
            result[pkg] = out
        except Exception:
            result[pkg] = None
    return result


def build_update(ctx):
    container = ctk.CTkScrollableFrame(ctx.content_frame, fg_color="transparent")
    container.pack(fill="both", expand=True, padx=20, pady=16)
    ctx.content_widgets.append(container)

    ctk.CTkLabel(
        container, text="Install",
        font=ctk.CTkFont(size=22, weight="bold"), text_color=TEXT
    ).pack(anchor="w", pady=(0, 2))
    ctk.CTkLabel(
        container,
        text="Manage update sources, install or update Hecos Core, and clean up your system.",
        font=ctk.CTkFont(size=12), text_color=MUTED
    ).pack(anchor="w", pady=(0, 18))

    core_ok = _is_core_installed()

    # ══════════════════════════════════════════════════════════════════════════
    # SECTION 1 — Update Sources
    # ══════════════════════════════════════════════════════════════════════════
    src_card = _card(container, "\U0001f517  Update Sources")

    sources_data = load_sources()
    active_src   = sources_data.get("active_source", "")
    all_sources  = sources_data.get("sources", [])
    source_names = [s["name"] for s in all_sources] or ["(No sources configured)"]
    src_var = ctk.StringVar(value=active_src if active_src in source_names else source_names[0])

    log_frame = ctk.CTkFrame(src_card, fg_color=BG, corner_radius=6)
    log_frame.pack(fill="x", padx=16, pady=(4, 10))
    src_log = ctk.CTkTextbox(
        log_frame, height=90, fg_color=BG, text_color="#a3e4a3",
        font=ctk.CTkFont(family="Consolas", size=11), wrap="word", state="normal"
    )
    src_log.pack(fill="x", padx=4, pady=4)

    def _src_log(msg):
        ts = _dt.datetime.now().strftime("%H:%M:%S")
        def _do():
            src_log.configure(state="normal")
            src_log.insert("end", f"[{ts}] {msg}\n")
            src_log.see("end")
            src_log.configure(state="disabled")
        src_log.after(0, _do)

    active_url = next((s.get("url", "") for s in all_sources if s["name"] == src_var.get()), "")
    _src_log(f"Active: {src_var.get()}")
    _src_log(f"URL:    {active_url}")
    src_log.configure(state="disabled")

    ctk.CTkLabel(src_card, text="Active source:", text_color=MUTED, font=ctk.CTkFont(size=11)).pack(anchor="w", padx=16)

    def on_source_change(val):
        set_active_source(val)
        new_url = next((s.get("url", "") for s in all_sources if s["name"] == val), "")
        _src_log(f"Switched to: {val}")
        _src_log(f"URL: {new_url}")

    src_action_row = ctk.CTkFrame(src_card, fg_color="transparent")
    src_action_row.pack(fill="x", padx=16, pady=(4, 8))
    src_action_row.columnconfigure(0, weight=1)

    ctk.CTkOptionMenu(
        src_action_row, values=source_names, variable=src_var, command=on_source_change,
        fg_color=BORDER, button_color=BORDER, button_hover_color=ACCENT,
        dropdown_fg_color=SURFACE, text_color=TEXT, height=32
    ).grid(row=0, column=0, sticky="ew", padx=(0, 6))

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
            add_btn.configure(text="\u25b2 Hide")

    ctk.CTkButton(
        src_action_row, text="\u2715  Remove",
        fg_color="transparent", border_width=1, border_color=RED,
        text_color=RED, hover_color="#3a1a1a", height=28, width=70, corner_radius=8,
        command=remove_selected
    ).grid(row=0, column=1, padx=(0, 6))

    add_btn = ctk.CTkButton(
        src_action_row, text="+ Add Source",
        fg_color=BORDER, text_color=TEXT, hover_color=ACCENT, height=28, width=80, corner_radius=8,
        command=toggle_add_panel
    )
    add_btn.grid(row=0, column=2)

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
            _src_log("\u26a0 Please fill in both name and URL.")

    ctk.CTkButton(
        add_panel, text="Save Source", fg_color=ACCENT,
        text_color="#000", hover_color=ACCENT, height=32, command=save_new_source
    ).pack(anchor="e", pady=(6, 0))

    ctk.CTkFrame(src_card, height=1, fg_color=BORDER).pack(fill="x", padx=16, pady=(4, 10))
    ctk.CTkLabel(src_card, text="\U0001f4e5  Import source list:", text_color=MUTED, font=ctk.CTkFont(size=11)).pack(anchor="w", padx=16)

    import_row = ctk.CTkFrame(src_card, fg_color="transparent")
    import_row.pack(fill="x", padx=16, pady=(4, 14))
    import_row.columnconfigure(0, weight=1)

    import_url_entry = ctk.CTkEntry(
        import_row, placeholder_text="Paste URL (Pastebin, GitHub raw, etc.)  or  load from file \u2192", height=32
    )
    import_url_entry.grid(row=0, column=0, sticky="ew", padx=(0, 6))

    def do_import():
        url = import_url_entry.get().strip()
        if not url:
            _src_log("\u26a0 Enter a URL or use the file button.")
            return
        _src_log(f"Fetching: {url}")
        def _task():
            added, err = import_source_list(url)
            if err:
                _src_log(f"\u26a0 {err}")
            else:
                _src_log(f"\u2705 {added} new source(s) added.")
                if added > 0:
                    ctx.switch_tab_fn("update")
        threading.Thread(target=_task, daemon=True).start()

    ctk.CTkButton(
        import_row, text="\u2b07 URL", fg_color=BORDER, text_color=TEXT, hover_color=ACCENT, height=32, width=70, command=do_import
    ).grid(row=0, column=1, padx=(0, 6))

    def do_import_file():
        from tkinter import filedialog
        path = filedialog.askopenfilename(title="Select Hecos Sources List (.toml)", filetypes=[("TOML files", "*.toml"), ("All files", "*.*")])
        if not path:
            return
        _src_log(f"Loading file: {os.path.basename(path)}")
        def _task():
            added, err = import_source_list_from_file(path)
            if err:
                _src_log(f"\u26a0 {err}")
            else:
                _src_log(f"\u2705 {added} new source(s) added.")
                if added > 0:
                    ctx.switch_tab_fn("update")
        threading.Thread(target=_task, daemon=True).start()

    ctk.CTkButton(
        import_row, text="\U0001f4c2 File", fg_color=BORDER, text_color=TEXT, hover_color=ACCENT, height=32, width=70, command=do_import_file
    ).grid(row=0, column=2)

    # ══════════════════════════════════════════════════════════════════════════
    # SECTION 2 — Core Installation & Updates
    # ══════════════════════════════════════════════════════════════════════════
    install_card = _card(container, "\U0001f4e5  Core Installation & Updates")

    info_frame = ctk.CTkFrame(install_card, fg_color="transparent")
    info_frame.pack(fill="x", padx=16, pady=(0, 10))

    info_frame.columnconfigure(0, weight=1)

    if core_ok:
        try:
            core_ver = open(VERSION_FILE, encoding="utf-8").read().strip()
        except Exception:
            core_ver = "?"
        curr_tray_v = get_tray_version()
        
        v_lbl = ctk.CTkLabel(info_frame, text=f"✅ Core v{core_ver}   •   ✅ Tray v{curr_tray_v}\nInstalled at: {_ROOT}", 
                             font=ctk.CTkFont(size=11), text_color="#4ade80", justify="left")
        v_lbl.grid(row=0, column=0, sticky="w")
    else:
        v_lbl = ctk.CTkLabel(info_frame, text=f"⚠ Core not found at: {_ROOT}\nDownload it to get started.", 
                             font=ctk.CTkFont(size=11), text_color=ACCENT, justify="left")
        v_lbl.grid(row=0, column=0, sticky="w")

    btn_row = ctk.CTkFrame(info_frame, fg_color="transparent")
    btn_row.grid(row=0, column=1, sticky="e")
    
    btn_cfg = dict(height=28, width=70, corner_radius=8, font=ctk.CTkFont(size=12))
    
    if core_ok:
        setup_btn = ctk.CTkButton(btn_row, text="Setup", fg_color=BORDER, text_color=TEXT, hover_color=ACCENT, **btn_cfg)
        setup_btn.pack(side="left", padx=(0, 6))
        
        dl_btn = ctk.CTkButton(btn_row, text="Download", fg_color=BORDER, text_color=TEXT, hover_color=ACCENT, **btn_cfg)
        dl_btn.pack(side="left", padx=(0, 6))
        
        upd_btn = ctk.CTkButton(btn_row, text="Update", fg_color=ACCENT, text_color="#000", hover_color=ACCENT, **btn_cfg)
        upd_btn.pack(side="left")
    else:
        dl_btn = ctk.CTkButton(btn_row, text="Download Core", fg_color=ACCENT, text_color="#000", hover_color=ACCENT, **btn_cfg)
        dl_btn.pack(side="right")
        setup_btn = None
        upd_btn = None

    status_lbl = ctk.CTkLabel(install_card, text="", text_color=MUTED, font=ctk.CTkFont(size=11))
    status_lbl.pack(anchor="w", padx=16)
    prog_bar = ctk.CTkProgressBar(install_card, fg_color=BORDER, progress_color=ACCENT)
    prog_bar.set(0)

    _dl_files = {}

    def do_download():
        dl_btn.configure(state="disabled", text="Downloading\u2026")
        if setup_btn: setup_btn.configure(state="disabled")
        if upd_btn: upd_btn.configure(state="disabled")
        prog_bar.pack(fill="x", padx=16, pady=(0, 8))
        prog_bar.set(0)
        def _task():
            def prog(p): prog_bar.set(p)
            def stat(msg): status_lbl.configure(text=msg, text_color=RED if "\u26a0" in msg else MUTED)
            success = install_core_from_scratch(prog, stat)
            prog_bar.pack_forget()
            if success:
                status_lbl.configure(text="\u2705 Core downloaded. Click 'Setup Wizard' to continue.", text_color="#4ade80")
                dl_btn.configure(state="normal", text="\U0001f4e5 Re-Download", fg_color=BORDER, text_color=TEXT)
                if setup_btn: setup_btn.configure(state="normal")
                if upd_btn: upd_btn.configure(state="normal")
            else:
                dl_btn.configure(state="normal", text="\U0001f4e5 Download Core" if not core_ok else "\U0001f4e5 Re-Download")
                if setup_btn: setup_btn.configure(state="disabled" if not core_ok else "normal")
                if upd_btn: upd_btn.configure(state="normal")
        threading.Thread(target=_task, daemon=True).start()

    def do_setup():
        setup_btn.configure(state="disabled", text="Launching\u2026")
        def stat(msg): status_lbl.configure(text=msg, text_color=RED if "\u26a0" in msg else "#4ade80")
        run_setup_wizard(status_callback=stat)
        setup_btn.configure(state="normal", text="\u2699 Setup Wizard")

    def do_check():
        src = src_var.get()
        if not src or src == "(No sources configured)":
            status_lbl.configure(text="\u26a0 No update source selected.", text_color=RED)
            return
        upd_btn.configure(state="disabled", text="Checking\u2026")
        status_lbl.configure(text="Contacting update server\u2026", text_color=MUTED)
        def _task():
            res = check_for_updates()
            err = res.get("error")
            if err:
                status_lbl.configure(text=f"\u26a0 {err}", text_color=RED)
                upd_btn.configure(state="normal", text="\U0001f504 Check Updates", command=do_check)
            elif res.get("update_available"):
                lv = res["latest_version"]
                status_lbl.configure(text=f"\u2705 Update available: v{lv}", text_color="#4ade80")
                upd_btn.configure(state="normal", text=f"\u2b07 Download v{lv}", command=lambda: do_download_update(res["assets"]))
            else:
                status_lbl.configure(text="\u2713 You are on the latest version.", text_color="#4ade80")
                upd_btn.configure(state="normal", text="\U0001f504 Check Updates", command=do_check)
        threading.Thread(target=_task, daemon=True).start()

    def do_download_update(assets):
        upd_btn.configure(state="disabled", text="Downloading\u2026")
        if setup_btn: setup_btn.configure(state="disabled")
        dl_btn.configure(state="disabled")
        prog_bar.pack(fill="x", padx=16, pady=(0, 8))
        def _task():
            try:
                temp_dir = os.path.join(_ROOT, "bin", "update_temp")
                os.makedirs(temp_dir, exist_ok=True)
                target_assets = [a for a in assets if (sys.platform == "win32" and a["name"].lower().endswith(".exe")) or (sys.platform != "win32" and not a["name"].lower().endswith(".exe") and any(k in a["name"].lower() for k in ("linux", "darwin", "mac")))]
                if not target_assets:
                    status_lbl.configure(text="\u26a0 No compatible assets found for this OS.", text_color=RED)
                    prog_bar.pack_forget()
                    upd_btn.configure(state="normal", text="\U0001f504 Check Updates", command=do_check)
                    if setup_btn: setup_btn.configure(state="normal")
                    dl_btn.configure(state="normal")
                    return
                for i, asset in enumerate(target_assets):
                    status_lbl.configure(text=f"Downloading {asset['name']} ({i+1}/{len(target_assets)})\u2026", text_color=MUTED)
                    def cb(done, total, bar=prog_bar):
                        if total > 0: bar.set(done / total)
                    dest = os.path.join(temp_dir, asset["name"])
                    download_asset(asset["url"], dest, cb)
                    nl = asset["name"].lower()
                    if "tray" in nl: _dl_files["tray"] = dest
                    elif "dashboard" in nl or "control" in nl: _dl_files["dashboard"] = dest
                status_lbl.configure(text="\u2705 Download complete \u2014 ready to apply.", text_color="#4ade80")
                prog_bar.pack_forget()
                upd_btn.configure(state="normal", text="\u26a1 Restart & Apply", command=do_apply)
            except Exception as e:
                status_lbl.configure(text=f"\u26a0 Download failed: {e}", text_color=RED)
                prog_bar.pack_forget()
                upd_btn.configure(state="normal", text="\U0001f504 Check Updates", command=do_check)
                if setup_btn: setup_btn.configure(state="normal")
                dl_btn.configure(state="normal")
        threading.Thread(target=_task, daemon=True).start()

    def do_apply():
        upd_btn.configure(state="disabled", text="Applying\u2026")
        status_lbl.configure(text="Launching updater and restarting\u2026", text_color=MUTED)
        apply_update_and_restart(_dl_files.get("tray", ""), _dl_files.get("dashboard", ""))

    dl_btn.configure(command=do_download)
    if setup_btn: setup_btn.configure(command=do_setup)
    if upd_btn: upd_btn.configure(command=do_check)

    # ══════════════════════════════════════════════════════════════════════════
    # SECTION 4 — Environment Inspector
    # ══════════════════════════════════════════════════════════════════════════
    env_card = _card(container, "\U0001f50d  Environment Inspector")

    ctk.CTkLabel(
        env_card,
        text="Verifies the Python environments and key packages for each Hecos component.",
        font=ctk.CTkFont(size=11), text_color=MUTED
    ).pack(anchor="w", padx=16, pady=(0, 8))

    env_box = ctk.CTkTextbox(
        env_card, height=200, fg_color="#1e1e1e", text_color="#a3e4a3",
        font=ctk.CTkFont(family="Consolas", size=10), wrap="word"
    )
    env_box.pack(fill="x", padx=16, pady=(0, 8))
    env_box.configure(state="disabled")

    def _env_log(msg):
        def _do():
            env_box.configure(state="normal")
            env_box.insert("end", msg + "\n")
            env_box.see("end")
            env_box.configure(state="disabled")
        env_box.after(0, _do)

    def run_env_check():
        env_scan_btn.configure(state="disabled", text="Scanning\u2026")
        env_box.configure(state="normal")
        env_box.delete("1.0", "end")
        env_box.configure(state="disabled")

        def _task():
            info = _get_python_info()
            _env_log("\u2500\u2500\u2500 PYTHON ENVIRONMENTS \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500")

            sys_i = info["system"]
            _env_log(f"{'✅' if sys_i['ok'] else '❌'} System Python: {sys_i['version']}")
            if sys_i["path"]:
                _env_log(f"   Path: {sys_i['path']}")

            core_i = info["core"]
            core_status = '✅' if core_i['ok'] else '❌'
            _env_log(f"{core_status} Core  Python:  [{core_i.get('type', 'Unknown')}] {core_i['version']}")
            if core_i["path"]:
                _env_log(f"   Path: {core_i['path']}")
                pkgs = _check_packages(core_i["path"], ["flask", "dotenv", "pydantic", "litellm", "yaml"])
                ok_p = [f"{k} ({v})" for k, v in pkgs.items() if v]
                miss = [k for k, v in pkgs.items() if not v]
                if ok_p:   _env_log(f"   Packages: {', '.join(ok_p)}")
                if miss:   _env_log(f"   \u26a0 Missing: {', '.join(miss)}")

            tray_i = info["tray"]
            tray_status = '✅' if tray_i['ok'] else '❌'
            _env_log(f"{tray_status} Tray  Python:  [{tray_i.get('type', 'Unknown')}] {tray_i['version']}")
            if tray_i["path"]:
                _env_log(f"   Path: {tray_i['path']}")
                pkgs = _check_packages(tray_i["path"], ["pystray", "PIL", "customtkinter", "psutil", "tomli_w"])
                ok_p = [f"{k} ({v})" for k, v in pkgs.items() if v]
                miss = [k for k, v in pkgs.items() if not v]
                if ok_p:   _env_log(f"   Packages: {', '.join(ok_p)}")
                if miss:   _env_log(f"   \u26a0 Missing: {', '.join(miss)}")

            _env_log("\u2500\u2500\u2500 DISK PATHS \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500")
            _env_log(f"Core root: {_ROOT}  {'✅' if os.path.isdir(_ROOT) else '❌ Not found'}")
            tray_rp = os.path.abspath(os.path.join(_TRAY_DIR, ".."))
            _env_log(f"Tray root: {tray_rp}  {'✅' if os.path.isdir(tray_rp) else '❌ Not found'}")
            _env_log("\u2500" * 50)
            _env_log("Scan complete.")
            
            def _reset_btn():
                env_scan_btn.configure(state="normal", text="\U0001f50d  Scan Environment")
            env_scan_btn.after(0, _reset_btn)

        threading.Thread(target=_task, daemon=True).start()

    env_scan_btn = ctk.CTkButton(
        env_card, text="\U0001f50d  Scan Environment",
        fg_color=BORDER, text_color=TEXT, hover_color=ACCENT,
        height=32, corner_radius=8, command=run_env_check
    )
    env_scan_btn.pack(anchor="w", padx=16, pady=(0, 14))

    # ══════════════════════════════════════════════════════════════════════════
    # SECTION 5 — Uninstall & Cleanup
    # ══════════════════════════════════════════════════════════════════════════
    uni_card = _card(container, "\U0001f5d1  Uninstall & Cleanup")

    uni_info_frame = ctk.CTkFrame(uni_card, fg_color="transparent")
    uni_info_frame.pack(fill="x", padx=16, pady=(0, 8))
    uni_info_frame.columnconfigure(0, weight=1)

    ctk.CTkLabel(
        uni_info_frame,
        text="Permanently remove Hecos from your system.\nThe selected components will be uninstalled while you watch.",
        font=ctk.CTkFont(size=11), text_color=MUTED, justify="left", wraplength=460
    ).grid(row=0, column=0, sticky="w")

    uni_buttons = ctk.CTkFrame(uni_info_frame, fg_color="transparent")
    uni_buttons.grid(row=0, column=1, sticky="e")

    log_box = ctk.CTkTextbox(
        uni_card, height=180, fg_color="#1e1e1e", text_color="#a3a3a3",
        font=ctk.CTkFont(family="Consolas", size=10), wrap="word"
    )

    _TRAY_PKG_DIR = os.path.dirname(os.path.abspath(__file__))
    _TERMINATOR_SRC = os.path.normpath(os.path.join(_TRAY_PKG_DIR, "..", "..", "uninstall_terminator.py"))

    def _append_log(text):
        log_box.insert("end", text)
        log_box.see("end")

    def _suicide_and_quit():
        _append_log("\n[!] Tray self-destruct initiated. Closing in 3 seconds...\n")
        log_box.update()

        tray_root = os.path.abspath(os.path.join(_TRAY_PKG_DIR, "..", ".."))
        tmp_dir = tempfile.gettempdir()
        bat_path = os.path.join(tmp_dir, "hecos_suicide.bat")
        with open(bat_path, "w") as f:
            f.write(
                f"@echo off\n"
                f"timeout /t 5 /nobreak >nul\n"
                f"rmdir /s /q \"{tray_root}\" >nul 2>&1\n"
                f"del \"%~f0\" >nul 2>&1\n"
            )

        try:
            subprocess.Popen(
                ["cmd.exe", "/c", bat_path],
                creationflags=subprocess.DETACHED_PROCESS,
                close_fds=True,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except Exception as e:
            _append_log(f"[!] Could not launch cleanup script: {e}\n")

        import time
        time.sleep(3)
        try:
            os._exit(0)
        except Exception:
            pass

        # Fallback: if still running, tell the user to close manually
        log_box.after(0, lambda: _append_log(
            "\n[!] Window did not close automatically.\n"
            "    You can safely close this window manually.\n"
            "    The cleanup will continue in the background.\n"
        ))

    def _run_terminator_thread(mode, dest):
        try:
            exe_cmd = sys.executable
            if exe_cmd.lower().endswith("pythonw.exe"):
                exe_cmd = exe_cmd[:-len("pythonw.exe")] + "python.exe"

            proc = subprocess.Popen(
                [exe_cmd, dest, "--mode", mode, "--wait", "1", "--skip-tray-delete"],
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1,
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
            )
            for line in proc.stdout:
                log_box.after(0, _append_log, line)
            proc.wait()

            if proc.returncode == 0:
                log_box.after(0, _append_log, "\n✅ Phase 1 Cleanup Complete.\n")
                if mode in ("full", "tray"):
                    threading.Thread(target=_suicide_and_quit, daemon=True).start()
                else:
                    log_box.after(0, _append_log, "\n[!] Core has been removed. The Tray is still installed.\n    You may safely close this window.")
            else:
                log_box.after(0, _append_log, f"\n❌ Terminator exited with error code {proc.returncode}\n")
        except Exception as e:
            log_box.after(0, _append_log, f"\n❌ Error launching terminator: {e}\n")

    def _launch_live_terminator(mode):
        try:
            uni_buttons.pack_forget()
            uni_info_frame.pack_forget()
            confirm_btn.pack_forget()
            log_box.pack(fill="x", padx=16, pady=(10, 14))
            _append_log(f"Initializing {mode.upper()} wipe...\n")
            dest = os.path.join(tempfile.gettempdir(), "hecos_uninstall_terminator.py")
            shutil.copy2(_TERMINATOR_SRC, dest)
            threading.Thread(target=_run_terminator_thread, args=(mode, dest), daemon=True).start()
        except Exception as e:
            _append_log(f"⚠ Failed to initialize: {e}\n")

    def _confirm_and_run(mode, label):
        for btn in _uninstall_buttons:
            btn.configure(state="disabled")
        confirm_btn.pack(fill="x", padx=16, pady=(4, 14))
        confirm_btn.configure(state="normal", text=f"CONFIRM: {label}", command=lambda: _launch_live_terminator(mode))

    _uninstall_buttons = []
    uni_cfg = dict(height=28, width=80, corner_radius=8, font=ctk.CTkFont(size=11))

    b1 = ctk.CTkButton(
        uni_buttons, text="Remove Core",
        fg_color=BORDER, text_color=TEXT if core_ok else MUTED,
        hover_color="#8b5cf6",
        state="normal" if core_ok else "disabled",
        command=lambda: _confirm_and_run("core", "Remove Core"), **uni_cfg
    )
    b1.pack(side="left", padx=(0, 6))

    b2 = ctk.CTkButton(
        uni_buttons, text="Remove Tray",
        fg_color=BORDER, text_color=TEXT, hover_color="#f97316",
        command=lambda: _confirm_and_run("tray", "Remove Tray"), **uni_cfg
    )
    b2.pack(side="left", padx=(0, 6))

    b3 = ctk.CTkButton(
        uni_buttons, text="Full Wipe",
        fg_color="transparent", border_width=1, border_color=RED,
        text_color=RED, hover_color="#3a1a1a",
        command=lambda: _confirm_and_run("full", "Full Wipe"), **uni_cfg
    )
    b3.pack(side="left")
    _uninstall_buttons.extend([b1, b2, b3])

    confirm_btn = ctk.CTkButton(
        uni_card, text="", state="disabled",
        fg_color=RED, hover_color="#7f1d1d", text_color="white",
        height=32, corner_radius=8, font=ctk.CTkFont(size=11, weight="bold")
    )
