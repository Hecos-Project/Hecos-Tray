import customtkinter as ctk
import time
import threading
import datetime as _dt

from tray.dashboard.theme import BG, CARD, MUTED, ACCENT, RED, AMBER, TEXT
from tray.dashboard.ui import make_card, title, subtitle
from tray.system_utils import (
    get_hecos_processes, kill_all_hecos_processes, kill_duplicate_hecos_processes,
    get_ollama_processes, is_ollama_api_responding, kill_ollama_processes,
)

# ── Colour palette for Ollama status ─────────────────────────────────────────
_GREEN  = "#22c55e"
_DIMMED = "#6b7280"
_AMBER  = "#f59e0b"


def build_processes(ctx):
    outer = ctk.CTkFrame(ctx.content_frame, fg_color="transparent", corner_radius=0)
    outer.pack(fill="both", expand=True, padx=20, pady=20)
    ctx.append_widget(outer)

    title(ctx, outer, "Process Manager")
    subtitle(ctx, outer, "Monitor and manage Hecos subsystems and Ollama server.")

    # ══════════════════════════════════════════════════════════════════════════
    # ── OLLAMA SECTION ────────────────────────────────────────────────────────
    # ══════════════════════════════════════════════════════════════════════════
    ollama_card = make_card(outer)
    ollama_card.pack(fill="x", pady=(10, 0))

    # Header row
    ol_header = ctk.CTkFrame(ollama_card, fg_color="transparent")
    ol_header.pack(fill="x", padx=15, pady=(12, 4))

    ctk.CTkLabel(
        ol_header,
        text="⚡  Ollama",
        font=ctk.CTkFont(size=13, weight="bold"),
        fg_color="transparent",
        text_color=TEXT,
    ).pack(side="left")

    # Status badge
    ol_badge = ctk.CTkLabel(
        ol_header,
        text="● Checking...",
        font=ctk.CTkFont(size=11, weight="bold"),
        fg_color="transparent",
        text_color=_DIMMED,
    )
    ol_badge.pack(side="left", padx=(12, 0))

    # Buttons
    btn_ol_stop = ctk.CTkButton(
        ol_header,
        text="⏹  Stop & Free VRAM",
        fg_color=RED, text_color="#fff", hover_color="#b91c1c",
        width=140, height=26,
        font=ctk.CTkFont(size=11),
    )
    btn_ol_stop.pack(side="right", padx=(6, 0))

    btn_ol_start = ctk.CTkButton(
        ol_header,
        text="▶  Start Server",
        fg_color="#16a34a", text_color="#fff", hover_color="#15803d",
        width=110, height=26,
        font=ctk.CTkFont(size=11),
    )
    btn_ol_start.pack(side="right")

    # Process list textbox
    ol_txt = ctk.CTkTextbox(
        ollama_card,
        height=80,
        fg_color=BG,
        text_color=TEXT,
        font=ctk.CTkFont("Consolas", size=12),
        wrap="none",
        state="disabled",
    )
    ol_txt.pack(fill="x", padx=10, pady=(4, 4))

    # Log box for Ollama actions
    ol_log = ctk.CTkTextbox(
        ollama_card,
        height=60,
        fg_color=BG,
        text_color="#a3e4a3",
        font=ctk.CTkFont("Consolas", size=11),
        wrap="word",
        state="disabled",
    )
    ol_log.pack(fill="x", padx=10, pady=(0, 12))

    def _ol_log(msg: str):
        ts = _dt.datetime.now().strftime("%H:%M:%S")
        ol_log.configure(state="normal")
        ol_log.insert("end", f"[{ts}] {msg}\n")
        ol_log.see("end")
        ol_log.configure(state="disabled")

    def _refresh_ollama():
        """Update the Ollama section. Called every 3 s from the background loop."""
        if ctx.active_tab.get("key") != "processes":
            return
        try:
            procs   = get_ollama_processes()
            api_ok  = is_ollama_api_responding()

            # Badge
            if api_ok:
                badge_txt   = "● API Online"
                badge_color = _GREEN
            elif procs:
                badge_txt   = "● Running (API not ready)"
                badge_color = _AMBER
            else:
                badge_txt   = "● Offline"
                badge_color = _DIMMED

            ol_badge.configure(text=badge_txt, text_color=badge_color)

            # Process list
            ol_txt.configure(state="normal")
            ol_txt.delete("1.0", "end")
            if not procs:
                ol_txt.insert("end", "  No Ollama processes found.\n")
            else:
                for p in procs:
                    mem_str = f"{p['vram_mb']} MB RAM" if p['vram_mb'] else "—"
                    line = (
                        f"  {p['type']:<22} PID: {p['pid']:<8} "
                        f"CPU: {p['cpu_percent']:>5.1f}%   Mem: {mem_str:<10}  [{p['status']}]\n"
                    )
                    ol_txt.insert("end", line)
            ol_txt.configure(state="disabled")
        except Exception as e:
            ol_badge.configure(text=f"● Error: {e}", text_color=RED)

    def _on_ol_stop():
        btn_ol_stop.configure(state="disabled", text="Stopping...")
        _ol_log("Sending stop signal to Ollama (unload + taskkill)...")
        def _bg():
            try:
                n = kill_ollama_processes()
                ctx.app.after(0, lambda: _ol_log(
                    f"Done — {n} process group(s) terminated. VRAM freed." if n else "No Ollama processes were running."
                ))
            except Exception as ex:
                ctx.app.after(0, lambda: _ol_log(f"Error: {ex}"))
            ctx.app.after(0, lambda: btn_ol_stop.configure(state="normal", text="⏹  Stop & Free VRAM"))
            ctx.app.after(0, _refresh_ollama)
        threading.Thread(target=_bg, daemon=True).start()

    def _on_ol_start():
        """Start Ollama via Hecos config (reads binary_path from system.yaml)."""
        btn_ol_start.configure(state="disabled", text="Starting...")
        _ol_log("Looking up Ollama executable from Hecos config...")
        def _bg():
            try:
                import sys as _sys, os as _os
                hecos_root = r"C:\Hecos"
                if hecos_root not in _sys.path:
                    _sys.path.insert(0, hecos_root)
                import yaml as _yaml
                cfg_path = _os.path.join(hecos_root, "hecos", "config", "data", "system.yaml")
                with open(cfg_path, encoding="utf-8") as _f:
                    _cfg = _yaml.safe_load(_f)
                bin_path = _cfg.get("backend", {}).get("ollama", {}).get("binary_path", "")
                ollama_url = _cfg.get("backend", {}).get("ollama", {}).get("url", "http://127.0.0.1:11434")
                from hecos.core.llm.ollama_lifecycle import find_ollama_executable, OllamaLifecycleManager
                exe = find_ollama_executable(bin_path)
                if not exe:
                    ctx.app.after(0, lambda: _ol_log("❌ Ollama executable not found. Set path in Hecos backend config."))
                    return
                ctx.app.after(0, lambda: _ol_log(f"Launching: {exe}"))
                _cfg2 = dict(_cfg)
                _cfg2.setdefault("backend", {}).setdefault("ollama", {})["auto_start_server"] = True
                OllamaLifecycleManager.get_instance().maybe_auto_start_server(_cfg2)
                ctx.app.after(0, lambda: _ol_log("✅ Start signal sent. Server should be online in ~5 s."))
            except Exception as ex:
                ctx.app.after(0, lambda: _ol_log(f"Error: {ex}"))
            ctx.app.after(0, lambda: btn_ol_start.configure(state="normal", text="▶  Start Server"))
            ctx.app.after(3000, _refresh_ollama)
        threading.Thread(target=_bg, daemon=True).start()

    btn_ol_stop.configure(command=_on_ol_stop)
    btn_ol_start.configure(command=_on_ol_start)

    # ══════════════════════════════════════════════════════════════════════════
    # ── HECOS PROCESSES SECTION ───────────────────────────────────────────────
    # ══════════════════════════════════════════════════════════════════════════
    hecos_card = make_card(outer)
    hecos_card.pack(fill="both", expand=True, pady=(12, 0))

    top_bar = ctk.CTkFrame(hecos_card, fg_color="transparent")
    top_bar.pack(fill="x", padx=15, pady=(15, 0))

    status_lbl = ctk.CTkLabel(
        top_bar,
        text="Scanning Hecos processes...",
        fg_color="transparent",
        font=ctk.CTkFont(size=12, weight="bold"),
    )
    status_lbl.pack(side="left")

    btn_dupes = ctk.CTkButton(
        top_bar, text="Kill Duplicates",
        fg_color=AMBER, text_color="#000", hover_color="#d97706", width=110,
    )
    btn_dupes.pack(side="right", padx=(10, 0))
    btn_all = ctk.CTkButton(
        top_bar, text="Kill All",
        fg_color=RED, text_color="#fff", hover_color="#b91c1c", width=100,
    )
    btn_all.pack(side="right")

    txt_frame = ctk.CTkFrame(hecos_card, fg_color="transparent", corner_radius=0)
    txt_frame.pack(fill="both", expand=True, padx=10, pady=(15, 5))

    textbox = ctk.CTkTextbox(
        txt_frame,
        fg_color=BG, text_color=TEXT,
        font=ctk.CTkFont("Consolas", size=13),
        wrap="none",
    )
    textbox.pack(fill="both", expand=True)

    # Hecos log box
    log_frame = ctk.CTkFrame(hecos_card, fg_color=BG, corner_radius=6)
    log_frame.pack(fill="x", padx=10, pady=(5, 15))

    log_box = ctk.CTkTextbox(
        log_frame,
        height=80,
        fg_color=BG, text_color="#a3e4a3",
        font=ctk.CTkFont(family="Consolas", size=11),
        wrap="word", state="normal",
    )
    log_box.pack(fill="x", padx=4, pady=4)

    def _log(msg: str):
        ts = _dt.datetime.now().strftime("%H:%M:%S")
        log_box.configure(state="normal")
        log_box.insert("end", f"[{ts}] {msg}\n")
        log_box.see("end")
        log_box.configure(state="disabled")

    _log("Process Manager initialized.")
    log_box.configure(state="disabled")

    def on_kill_all():
        _log("Executing Kill All command...")
        killed = kill_all_hecos_processes()
        _log(f"Result: Killed {killed} process(es).")
        ctx.rebuild_tab("processes")

    def on_kill_dupes():
        _log("Scanning for duplicate processes...")
        killed = kill_duplicate_hecos_processes()
        _log(f"Result: Killed {killed} duplicate process(es).")
        ctx.rebuild_tab("processes")

    btn_dupes.configure(command=on_kill_dupes)
    btn_all.configure(command=on_kill_all)

    def _refresh_hecos():
        if ctx.active_tab.get("key") != "processes":
            return
        try:
            procs = get_hecos_processes()
            status_lbl.configure(
                text=f"Hecos Processes: {len(procs)}",
                text_color=ACCENT,
            )
            textbox.configure(state="normal")
            textbox.delete("1.0", "end")
            if not procs:
                textbox.insert("end", "  No Hecos processes found.\n")
            else:
                for p in procs:
                    cmd_short = p['cmd'].replace('\n', ' ')
                    if len(cmd_short) > 130:
                        cmd_short = cmd_short[:127] + "..."
                    line = f"  {p['type']:<20} PID: {p['pid']:<8} {cmd_short}\n"
                    textbox.insert("end", line)
            textbox.configure(state="disabled")
        except Exception as e:
            status_lbl.configure(text=f"Error scanning: {e}", text_color=RED)

    # ── Initial paint ─────────────────────────────────────────────────────────
    _refresh_ollama()
    _refresh_hecos()

    # ── Background refresh loop (every 3 s) ───────────────────────────────────
    def _loop():
        while ctx.active_tab.get("key") == "processes":
            time.sleep(3)
            if ctx.active_tab.get("key") == "processes":
                ctx.app.after(0, _refresh_ollama)
                ctx.app.after(0, _refresh_hecos)

    threading.Thread(target=_loop, daemon=True).start()
