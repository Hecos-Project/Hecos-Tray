import customtkinter as ctk
import time
import threading
import datetime as _dt

from tray.dashboard.theme import BG, CARD, BORDER, MUTED, ACCENT, RED, AMBER, TEXT
from tray.dashboard.ui import make_card, title, subtitle
from tray.system_utils import (
    get_hecos_processes, kill_all_hecos_processes, kill_duplicate_hecos_processes,
    get_ollama_processes, is_ollama_api_responding, kill_ollama_processes,
    get_tts_engines_status, control_tts_engine,
    get_swarmui_processes, is_swarmui_api_responding, kill_swarmui_processes, start_swarmui,
)

# ── Colour palette for Ollama status ─────────────────────────────────────────
_GREEN  = "#22c55e"
_DIMMED = "#6b7280"
_AMBER  = "#f59e0b"


def build_processes(ctx):
    outer = ctk.CTkScrollableFrame(
        ctx.content_frame,
        fg_color="transparent",
        corner_radius=0,
        scrollbar_button_color=BORDER,
        scrollbar_button_hover_color=ACCENT,
    )
    outer.pack(fill="both", expand=True, padx=20, pady=20)
    ctx.append_widget(outer)

    title(ctx, outer, "Process Manager")
    subtitle(ctx, outer, "Monitor and manage Ollama, TTS neural engines/daemons, and Hecos subsystems.")

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
                mgr = OllamaLifecycleManager.get_instance()
                mgr.maybe_auto_start_server(_cfg2)
                if _cfg2.get("backend", {}).get("ollama", {}).get("warmup_model", False):
                    mgr.maybe_warmup_model(_cfg2, delay=4.5)
                    ctx.app.after(0, lambda: _ol_log("✅ Start + model warm-up scheduled (~5–10 s)."))
                else:
                    ctx.app.after(0, lambda: _ol_log("✅ Start signal sent. Server should be online in ~5 s."))
            except Exception as ex:
                ctx.app.after(0, lambda: _ol_log(f"Error: {ex}"))
            ctx.app.after(0, lambda: btn_ol_start.configure(state="normal", text="▶  Start Server"))
            ctx.app.after(3000, _refresh_ollama)
        threading.Thread(target=_bg, daemon=True).start()

    btn_ol_stop.configure(command=_on_ol_stop)
    btn_ol_start.configure(command=_on_ol_start)

    # ══════════════════════════════════════════════════════════════════════════
    # ── TTS ENGINES & DAEMONS SECTION ─────────────────────────────────────────
    # ══════════════════════════════════════════════════════════════════════════
    tts_card = make_card(outer)
    tts_card.pack(fill="x", pady=(12, 0))

    tts_header = ctk.CTkFrame(tts_card, fg_color="transparent")
    tts_header.pack(fill="x", padx=15, pady=(12, 6))

    ctk.CTkLabel(
        tts_header,
        text="🎙  TTS Engines",
        font=ctk.CTkFont(size=13, weight="bold"),
        fg_color="transparent",
        text_color=TEXT,
    ).pack(side="left")

    tts_badge = ctk.CTkLabel(
        tts_header,
        text="● Checking...",
        font=ctk.CTkFont(size=11, weight="bold"),
        fg_color="transparent",
        text_color=_DIMMED,
    )
    tts_badge.pack(side="left", padx=(12, 0))

    btn_tts_stop_all = ctk.CTkButton(
        tts_header,
        text="⏹  Stop All & Free RAM/VRAM",
        fg_color=RED, text_color="#fff", hover_color="#b91c1c",
        width=175, height=26,
        font=ctk.CTkFont(size=11),
    )
    btn_tts_stop_all.pack(side="right")

    tts_rows_box = ctk.CTkFrame(tts_card, fg_color=BG, corner_radius=8)
    tts_rows_box.pack(fill="x", padx=10, pady=(2, 6))

    tts_log = ctk.CTkTextbox(
        tts_card,
        height=56,
        fg_color=BG,
        text_color="#a3e4a3",
        font=ctk.CTkFont("Consolas", size=11),
        wrap="word",
        state="disabled",
    )
    tts_log.pack(fill="x", padx=10, pady=(0, 12))

    def _tts_log(msg: str):
        ts = _dt.datetime.now().strftime("%H:%M:%S")
        tts_log.configure(state="normal")
        tts_log.insert("end", f"[{ts}] {msg}\n")
        tts_log.see("end")
        tts_log.configure(state="disabled")

    _tts_row_widgets = {}
    _TTS_ORDER = [
        ("piper", "Piper TTS"),
        ("kokoro", "Kokoro-82M"),
        ("xtts2", "Coqui XTTSv2"),
        ("fish_speech", "Fish Speech S2"),
    ]

    for idx, (eng_key, eng_title) in enumerate(_TTS_ORDER):
        row = ctk.CTkFrame(tts_rows_box, fg_color="transparent")
        row.pack(fill="x", padx=10, pady=(6 if idx == 0 else 3, 6 if idx == len(_TTS_ORDER) - 1 else 3))

        dot_lbl = ctk.CTkLabel(
            row, text="●", width=14,
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=_DIMMED, fg_color="transparent",
        )
        dot_lbl.pack(side="left")

        name_lbl = ctk.CTkLabel(
            row, text=eng_title, width=120, anchor="w",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=TEXT, fg_color="transparent",
        )
        name_lbl.pack(side="left", padx=(4, 4))

        role_lbl = ctk.CTkLabel(
            row, text="", width=72, anchor="w",
            font=ctk.CTkFont("Consolas", size=10, weight="bold"),
            text_color=MUTED, fg_color="transparent",
        )
        role_lbl.pack(side="left", padx=(0, 6))

        info_lbl = ctk.CTkLabel(
            row, text="Checking...", anchor="w",
            font=ctk.CTkFont("Consolas", size=11),
            text_color=MUTED, fg_color="transparent",
        )
        info_lbl.pack(side="left", fill="x", expand=True)

        is_daemon_eng = eng_key in ("piper", "fish_speech")
        stop_btn = ctk.CTkButton(
            row,
            text="⏹ Stop" if is_daemon_eng else "⏹ Unload",
            fg_color=RED, text_color="#fff", hover_color="#b91c1c",
            width=68, height=24, font=ctk.CTkFont(size=10),
        )
        stop_btn.pack(side="right", padx=(4, 0))

        restart_btn = ctk.CTkButton(
            row,
            text="↻",
            fg_color="#374151", text_color="#fff", hover_color="#4b5563",
            width=30, height=24, font=ctk.CTkFont(size=11),
        )
        restart_btn.pack(side="right", padx=(4, 0))

        start_btn = ctk.CTkButton(
            row,
            text="▶ Start" if is_daemon_eng else "▶ Load",
            fg_color="#16a34a", text_color="#fff", hover_color="#15803d",
            width=64, height=24, font=ctk.CTkFont(size=10),
        )
        start_btn.pack(side="right")

        _tts_row_widgets[eng_key] = {
            "dot": dot_lbl,
            "name": name_lbl,
            "role": role_lbl,
            "info": info_lbl,
            "start": start_btn,
            "restart": restart_btn,
            "stop": stop_btn,
            "is_daemon": is_daemon_eng,
        }

    def _apply_tts_snapshot(snap: dict):
        if ctx.active_tab.get("key") != "processes":
            return
        core_online = bool(snap.get("core_online"))
        engines = snap.get("engines") or {}
        online_count = sum(1 for v in engines.values() if v.get("status") in ("online", "cloud"))
        starting_count = sum(1 for v in engines.values() if v.get("status") == "starting")

        if core_online:
            if starting_count:
                tts_badge.configure(text=f"● {online_count} Online · {starting_count} Loading...", text_color=_AMBER)
            elif online_count:
                tts_badge.configure(text=f"● {online_count} Active in Memory", text_color=_GREEN)
            else:
                tts_badge.configure(text="● All Idle (RAM Free)", text_color=_DIMMED)
        else:
            if online_count:
                tts_badge.configure(text=f"● Core Offline ({online_count} Orphan Daemon)", text_color=_AMBER)
            else:
                tts_badge.configure(text="● Core Offline", text_color=_DIMMED)

        for eng_key, w in _tts_row_widgets.items():
            st = engines.get(eng_key) or {}
            state = st.get("status", "offline")
            is_active = bool(st.get("active"))
            is_fb = bool(st.get("fallback"))
            autostart = bool(st.get("autostart", True))

            if is_active:
                w["role"].configure(text="[ACTIVE]", text_color=ACCENT)
            elif is_fb:
                w["role"].configure(text="[FALLBACK]", text_color=MUTED)
            else:
                w["role"].configure(text="[BOOT:ON]" if autostart else "[MANUAL]", text_color=_DIMMED)

            details = []
            if state == "online":
                w["dot"].configure(text_color=_GREEN)
                if st.get("mode") == "daemon" and st.get("pid"):
                    details.append(f"PID {st['pid']}")
                elif st.get("mode") == "in-process":
                    details.append("In-Proc")
                if st.get("port"):
                    details.append(f":{st['port']}")
                if st.get("device") and st.get("device") != "—":
                    details.append(str(st["device"]))
                ram = float(st.get("ram_mb") or 0.0)
                vram = float(st.get("vram_mb") or 0.0)
                if ram > 0:
                    details.append(f"{ram:.0f}MB RAM")
                if vram > 0:
                    details.append(f"{vram:.0f}MB VRAM")
                w["info"].configure(text=" · ".join(details) or "Online", text_color=TEXT)
                w["start"].configure(state="disabled")
                w["restart"].configure(state="normal" if core_online else "disabled")
                w["stop"].configure(state="normal")
            elif state == "cloud":
                w["dot"].configure(text_color=_GREEN)
                w["info"].configure(text="Cloud API Endpoint", text_color=TEXT)
                w["start"].configure(state="disabled")
                w["restart"].configure(state="disabled")
                w["stop"].configure(state="disabled")
            elif state == "starting":
                w["dot"].configure(text_color=_AMBER)
                w["info"].configure(text="Loading model / starting daemon...", text_color=_AMBER)
                w["start"].configure(state="disabled")
                w["restart"].configure(state="disabled")
                w["stop"].configure(state="normal")
            else:
                w["dot"].configure(text_color=_DIMMED)
                off_txt = "Stopped" if w["is_daemon"] else "Unloaded (RAM Free)"
                w["info"].configure(text=off_txt, text_color=_DIMMED)
                w["start"].configure(state="normal" if core_online else "disabled")
                w["restart"].configure(state="disabled")
                w["stop"].configure(state="disabled")

    def _refresh_tts():
        if ctx.active_tab.get("key") != "processes":
            return
        def _bg():
            snap = get_tts_engines_status()
            if ctx.active_tab.get("key") == "processes":
                ctx.app.after(0, lambda: _apply_tts_snapshot(snap))
        threading.Thread(target=_bg, daemon=True).start()

    def _make_tts_cmd(eng_key: str, action: str):
        def _handler():
            _tts_log(f"Sending '{action}' to {eng_key}...")
            def _bg():
                ok, msg = control_tts_engine(eng_key, action)
                prefix = "✅" if ok else "❌"
                ctx.app.after(0, lambda: _tts_log(f"{prefix} {msg}"))
                ctx.app.after(200, _refresh_tts)
                ctx.app.after(500, _refresh_hecos)
            threading.Thread(target=_bg, daemon=True).start()
        return _handler

    for _ek, _w in _tts_row_widgets.items():
        _w["start"].configure(command=_make_tts_cmd(_ek, "start"))
        _w["restart"].configure(command=_make_tts_cmd(_ek, "restart"))
        _w["stop"].configure(command=_make_tts_cmd(_ek, "stop"))

    def _on_tts_stop_all():
        btn_tts_stop_all.configure(state="disabled", text="Stopping...")
        _tts_log("Stopping all TTS daemons and unloading models from RAM/VRAM...")
        def _bg():
            ok, msg = control_tts_engine("all", "stop")
            prefix = "✅" if ok else "❌"
            ctx.app.after(0, lambda: _tts_log(f"{prefix} {msg}"))
            ctx.app.after(0, lambda: btn_tts_stop_all.configure(state="normal", text="⏹  Stop All & Free RAM/VRAM"))
            ctx.app.after(200, _refresh_tts)
            ctx.app.after(500, _refresh_hecos)
        threading.Thread(target=_bg, daemon=True).start()

    btn_tts_stop_all.configure(command=_on_tts_stop_all)


    # ══════════════════════════════════════════════════════════════════════════
    # ── SWARMUI SECTION ───────────────────────────────────────────────────────
    # ══════════════════════════════════════════════════════════════════════════
    swarm_card = make_card(outer)
    swarm_card.pack(fill="x", pady=(12, 0))

    swarm_header = ctk.CTkFrame(swarm_card, fg_color="transparent")
    swarm_header.pack(fill="x", padx=15, pady=(12, 4))

    ctk.CTkLabel(
        swarm_header,
        text="🖼  SwarmUI",
        font=ctk.CTkFont(size=13, weight="bold"),
        fg_color="transparent",
        text_color=TEXT,
    ).pack(side="left")

    swarm_badge = ctk.CTkLabel(
        swarm_header,
        text="● Checking...",
        font=ctk.CTkFont(size=11, weight="bold"),
        fg_color="transparent",
        text_color=_DIMMED,
    )
    swarm_badge.pack(side="left", padx=(12, 0))

    btn_swarm_stop = ctk.CTkButton(
        swarm_header,
        text="⏹  Stop & Free RAM",
        fg_color=RED, text_color="#fff", hover_color="#b91c1c",
        width=135, height=26,
        font=ctk.CTkFont(size=11),
    )
    btn_swarm_stop.pack(side="right", padx=(6, 0))

    btn_swarm_start = ctk.CTkButton(
        swarm_header,
        text="▶  Start",
        fg_color="#16a34a", text_color="#fff", hover_color="#15803d",
        width=70, height=26,
        font=ctk.CTkFont(size=11),
    )
    btn_swarm_start.pack(side="right")

    swarm_txt = ctk.CTkTextbox(
        swarm_card,
        height=72,
        fg_color=BG,
        text_color=TEXT,
        font=ctk.CTkFont("Consolas", size=12),
        wrap="none",
        state="disabled",
    )
    swarm_txt.pack(fill="x", padx=10, pady=(4, 4))

    swarm_log = ctk.CTkTextbox(
        swarm_card,
        height=52,
        fg_color=BG,
        text_color="#a3e4a3",
        font=ctk.CTkFont("Consolas", size=11),
        wrap="word",
        state="disabled",
    )
    swarm_log.pack(fill="x", padx=10, pady=(0, 12))

    def _swarm_log(msg: str):
        ts = _dt.datetime.now().strftime("%H:%M:%S")
        swarm_log.configure(state="normal")
        swarm_log.insert("end", f"[{ts}] {msg}\n")
        swarm_log.see("end")
        swarm_log.configure(state="disabled")

    def _refresh_swarmui():
        """Update the SwarmUI section. Called every 3 s from the background loop."""
        if ctx.active_tab.get("key") != "processes":
            return
        try:
            procs  = get_swarmui_processes()
            api_ok = is_swarmui_api_responding()

            if api_ok:
                badge_txt   = "● API Online"
                badge_color = _GREEN
            elif procs:
                badge_txt   = "● Running (API not ready)"
                badge_color = _AMBER
            else:
                badge_txt   = "● Offline"
                badge_color = _DIMMED

            swarm_badge.configure(text=badge_txt, text_color=badge_color)
            btn_swarm_stop.configure(state="normal" if (procs or api_ok) else "disabled")
            btn_swarm_start.configure(state="disabled" if (procs or api_ok) else "normal")

            swarm_txt.configure(state="normal")
            swarm_txt.delete("1.0", "end")
            if not procs:
                swarm_txt.insert("end", "  No SwarmUI processes found.\n")
            else:
                for p in procs:
                    mem_str = f"{p['ram_mb']} MB RAM" if p["ram_mb"] else "—"
                    line = (
                        f"  {p['type']:<22} PID: {p['pid']:<8} "
                        f"CPU: {p['cpu_percent']:>5.1f}%   Mem: {mem_str:<10}  [{p['status']}]\n"
                    )
                    swarm_txt.insert("end", line)
            swarm_txt.configure(state="disabled")
        except Exception as e:
            swarm_badge.configure(text=f"● Error: {e}", text_color=RED)

    def _on_swarm_stop():
        btn_swarm_stop.configure(state="disabled", text="Stopping...")
        _swarm_log("Sending stop signal to SwarmUI (taskkill + process scan)...")
        def _bg():
            try:
                n = kill_swarmui_processes()
                ctx.app.after(0, lambda: _swarm_log(
                    f"Done — {n} process(es) terminated. RAM freed." if n else "No SwarmUI processes were running."
                ))
            except Exception as ex:
                ctx.app.after(0, lambda: _swarm_log(f"Error: {ex}"))
            ctx.app.after(0, lambda: btn_swarm_stop.configure(state="normal", text="⏹  Stop & Free RAM"))
            ctx.app.after(0, _refresh_swarmui)
        threading.Thread(target=_bg, daemon=True).start()

    def _on_swarm_start():
        btn_swarm_start.configure(state="disabled", text="Starting...")
        _swarm_log("Launching SwarmUI via Hecos image_gen launcher...")
        def _bg():
            try:
                ok, msg = start_swarmui()
                prefix = "✅" if ok else "❌"
                ctx.app.after(0, lambda: _swarm_log(f"{prefix} {msg}"))
            except Exception as ex:
                ctx.app.after(0, lambda: _swarm_log(f"Error: {ex}"))
            ctx.app.after(0, lambda: btn_swarm_start.configure(state="normal", text="▶  Start"))
            ctx.app.after(3000, _refresh_swarmui)
        threading.Thread(target=_bg, daemon=True).start()

    btn_swarm_stop.configure(command=_on_swarm_stop)
    btn_swarm_start.configure(command=_on_swarm_start)

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
        height=130,
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
    _refresh_tts()
    _refresh_swarmui()
    _refresh_hecos()

    # ── Background refresh loop (every 3 s) ───────────────────────────────────
    def _loop():
        while ctx.active_tab.get("key") == "processes":
            time.sleep(3)
            if ctx.active_tab.get("key") == "processes":
                ctx.app.after(0, _refresh_ollama)
                ctx.app.after(0, _refresh_tts)
                ctx.app.after(0, _refresh_hecos)

    threading.Thread(target=_loop, daemon=True).start()
