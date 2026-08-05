import customtkinter as ctk
from tray.config import load_settings, save_settings
from tray.dashboard.theme import CARD, TEXT, MUTED, ACCENT
from tray.dashboard.ui import title, subtitle
from tray.system_utils import set_os_startup

def build_settings(ctx):
    sc = ctk.CTkFrame(ctx.content_frame, fg_color="transparent", corner_radius=0)
    sc.pack(fill="both", expand=True, padx=20, pady=20)
    ctx.append_widget(sc)

    title(ctx, sc, "Settings")
    subtitle(ctx, sc, "Changes apply immediately.")
    
    cfg = load_settings()

    # Special handling for OS Startup Dependency
    os_startup_var = ctk.BooleanVar(value=cfg.get("start_tray_on_os_boot", False))
    core_startup_var = ctk.BooleanVar(value=cfg.get("start_hecos_on_launch", False))
    
    # OS Startup Row
    os_row = ctk.CTkFrame(sc, fg_color=CARD, corner_radius=10)
    os_row.pack(fill="x", pady=4)
    ctk.CTkLabel(os_row, text="Auto-start Tray on Windows Boot", fg_color="transparent", font=ctk.CTkFont(size=12, weight="bold"), text_color=TEXT, anchor="w").pack(side="left", padx=14, pady=10, expand=True, fill="x")
    
    core_sw = None # Forward declare

    def on_os_toggle():
        val = os_startup_var.get()
        cfg = load_settings()
        cfg["start_tray_on_os_boot"] = val
        save_settings(cfg)
        set_os_startup(val)
        
        # Enforce dependency
        if core_sw:
            if val:
                core_sw.configure(state="normal")
            else:
                core_startup_var.set(False)
                core_sw.configure(state="disabled")
                cfg["start_hecos_on_launch"] = False
                save_settings(cfg)

    os_sw = ctk.CTkSwitch(os_row, text="", variable=os_startup_var, onvalue=True, offvalue=False, progress_color=ACCENT, command=on_os_toggle)
    os_sw.pack(side="right", padx=14, pady=10)

    # Core Startup Row
    core_row = ctk.CTkFrame(sc, fg_color=CARD, corner_radius=10)
    core_row.pack(fill="x", pady=4)
    
    core_lbl = ctk.CTkLabel(core_row, text="↳ Start Core automatically with Tray", fg_color="transparent", font=ctk.CTkFont(size=12), text_color=TEXT, anchor="w")
    core_lbl.pack(side="left", padx=28, pady=10, expand=True, fill="x")
    
    def on_core_toggle():
        cfg = load_settings()
        cfg["start_hecos_on_launch"] = core_startup_var.get()
        save_settings(cfg)

    core_sw = ctk.CTkSwitch(core_row, text="", variable=core_startup_var, onvalue=True, offvalue=False, progress_color=ACCENT, command=on_core_toggle)
    core_sw.pack(side="right", padx=14, pady=10)
    
    # Initialize dependency state
    if not os_startup_var.get():
        core_startup_var.set(False)
        core_sw.configure(state="disabled")
        cfg["start_hecos_on_launch"] = False
        save_settings(cfg)
        
    # Spacer
    ctk.CTkFrame(sc, height=1, fg_color="transparent").pack(pady=6)

    # Standard toggles
    toggles = [
        ("autoopen_webui",            "Auto-open WebUI on Startup",        True),
        ("autoopen_ai_browser",       "Auto-open Playwright Browser",      False),
        ("auto_launch_chrome_for_ai", "Auto-launch AI-Ready Chrome (CDP)", False),
        ("show_technical_menu",       "Show Technical Menu in Tray",       True),
    ]

    for key, label, default in toggles:
        row = ctk.CTkFrame(sc, fg_color=CARD, corner_radius=10)
        row.pack(fill="x", pady=4)

        ctk.CTkLabel(row, text=label, fg_color="transparent", font=ctk.CTkFont(size=12), text_color=TEXT,
                     anchor="w").pack(side="left", padx=14, pady=10, expand=True, fill="x")

        var = ctk.BooleanVar(value=cfg.get(key, default))

        def _on_toggle(v=var, k=key):
            s = load_settings()
            s[k] = v.get()
            save_settings(s)

        sw = ctk.CTkSwitch(row, text="", variable=var, onvalue=True, offvalue=False,
                           progress_color=ACCENT, command=_on_toggle)
        sw.pack(side="right", padx=14, pady=10)
