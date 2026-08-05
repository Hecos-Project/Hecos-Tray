import webbrowser
import customtkinter as ctk

from tray.dashboard.theme import SURFACE, CARD, ACCENT, ACCENT2, TEXT, MUTED, BORDER, GREEN


WIKI_URL = "https://github.com/Hecos-Project/Hecos/wiki"

QUICK_STEPS = [
    ("1", "Go to the  Updates  tab", "Click on it in the left sidebar."),
    ("2", "Download / Install the Core", "The Tray will handle the full download and setup."),
    ("3", "Switch to the  Status  tab", "Once installed, click  Start Hecos  to launch the engine."),
    ("4", "Open the Web UI", "Click  Web UI  in the sidebar and start chatting with Hecos!"),
]

LINKS = [
    ("📖  User Guide", "Step-by-step guides for every feature.", WIKI_URL),
]


def build_guide(ctx):
    sc = ctk.CTkScrollableFrame(ctx.content_frame, fg_color="transparent", corner_radius=0)
    sc.pack(fill="both", expand=True, padx=20, pady=16)
    ctx.append_widget(sc)

    # ── Page Header ────────────────────────────────────────────────────────────
    ctk.CTkLabel(sc, text="Guide & Help",
                 font=ctk.CTkFont(size=22, weight="bold"), text_color=TEXT
                 ).pack(anchor="w", pady=(0, 2))
    ctk.CTkLabel(sc, text="New here? Follow the Quick Start below — it takes less than 2 minutes.",
                 font=ctk.CTkFont(size=12), text_color=MUTED
                 ).pack(anchor="w", pady=(0, 18))

    # ── Quick Start Card ───────────────────────────────────────────────────────
    qs_card = ctk.CTkFrame(sc, fg_color=SURFACE, corner_radius=10)
    qs_card.pack(fill="x", pady=(0, 14))

    ctk.CTkLabel(qs_card, text="🚀  Quick Start (First Time Users)",
                 font=ctk.CTkFont(size=13, weight="bold"), text_color=TEXT
                 ).pack(anchor="w", padx=16, pady=(14, 8))

    for num, step_title, step_desc in QUICK_STEPS:
        row = ctk.CTkFrame(qs_card, fg_color=CARD, corner_radius=8)
        row.pack(fill="x", padx=16, pady=(0, 6))

        # Number badge
        badge = ctk.CTkFrame(row, fg_color=ACCENT2, corner_radius=6, width=28, height=28)
        badge.pack(side="left", padx=(12, 10), pady=10)
        badge.pack_propagate(False)
        ctk.CTkLabel(badge, text=num, font=ctk.CTkFont(size=11, weight="bold"),
                     text_color="#ffffff").place(relx=0.5, rely=0.5, anchor="center")

        # Text
        txt_block = ctk.CTkFrame(row, fg_color="transparent")
        txt_block.pack(side="left", fill="x", expand=True, pady=10)
        ctk.CTkLabel(txt_block, text=step_title,
                     font=ctk.CTkFont(size=12, weight="bold"), text_color=TEXT,
                     anchor="w").pack(anchor="w")
        ctk.CTkLabel(txt_block, text=step_desc,
                     font=ctk.CTkFont(size=11), text_color=MUTED,
                     anchor="w").pack(anchor="w")

    ctk.CTkFrame(qs_card, height=10, fg_color="transparent").pack()

    # ── Online Documentation Card ──────────────────────────────────────────────
    doc_card = ctk.CTkFrame(sc, fg_color=SURFACE, corner_radius=10)
    doc_card.pack(fill="x", pady=(0, 14))

    ctk.CTkLabel(doc_card, text="📚  Online Documentation",
                 font=ctk.CTkFont(size=13, weight="bold"), text_color=TEXT
                 ).pack(anchor="w", padx=16, pady=(14, 4))
    ctk.CTkLabel(doc_card,
                 text="The official Hecos Wiki on GitHub — always up to date, available even if Hecos is not installed.",
                 font=ctk.CTkFont(size=11), text_color=MUTED, wraplength=460, justify="left"
                 ).pack(anchor="w", padx=16, pady=(0, 12))

    for link_label, link_desc, link_url in LINKS:
        link_row = ctk.CTkFrame(doc_card, fg_color=CARD, corner_radius=8)
        link_row.pack(fill="x", padx=16, pady=(0, 6))

        inner = ctk.CTkFrame(link_row, fg_color="transparent")
        inner.pack(side="left", fill="both", expand=True, padx=12, pady=8)
        ctk.CTkLabel(inner, text=link_label,
                     font=ctk.CTkFont(size=12, weight="bold"), text_color=TEXT,
                     anchor="w").pack(anchor="w")
        ctk.CTkLabel(inner, text=link_desc,
                     font=ctk.CTkFont(size=10), text_color=MUTED,
                     anchor="w").pack(anchor="w")

        go_btn = ctk.CTkButton(
            link_row, text="Open ↗", width=72,
            fg_color="transparent", text_color=ACCENT,
            hover_color=BORDER, corner_radius=6,
            font=ctk.CTkFont(size=11),
            command=lambda u=link_url: webbrowser.open(u)
        )
        go_btn.pack(side="right", padx=10)

    ctk.CTkFrame(doc_card, height=10, fg_color="transparent").pack()
