import customtkinter as ctk
from tray.dashboard.theme import CARD, TEXT, MUTED

def make_card(parent, **kw):
    f = ctk.CTkFrame(parent, fg_color=CARD, corner_radius=10, **kw)
    return f

def title(ctx, parent, text):
    lbl = ctk.CTkLabel(parent, text=text, fg_color="transparent",
                       font=ctk.CTkFont(size=18, weight="bold"), text_color=TEXT)
    lbl.pack(anchor="w", pady=(0, 2))
    ctx.append_widget(lbl)
    return lbl

def subtitle(ctx, parent, text):
    lbl = ctk.CTkLabel(parent, text=text, fg_color="transparent", font=ctk.CTkFont(size=11), text_color=MUTED)
    lbl.pack(anchor="w", pady=(0, 8))
    ctx.append_widget(lbl)
    return lbl

def section_label(ctx, parent, text):
    lbl = ctk.CTkLabel(parent, text=text, fg_color="transparent",
                       font=ctk.CTkFont(size=10, weight="bold"), text_color=MUTED)
    lbl.pack(anchor="w", pady=(8, 2))
    ctx.append_widget(lbl)
    return lbl

def info_row(card, label, value, value_color=TEXT):
    row = ctk.CTkFrame(card, fg_color="transparent")
    row.pack(fill="x", padx=14, pady=5)
    ctk.CTkLabel(row, text=label, fg_color="transparent", font=ctk.CTkFont(size=11), text_color=MUTED,
                 anchor="w").pack(side="left", expand=True, fill="x")
    ctk.CTkLabel(row, text=value, fg_color="transparent", font=ctk.CTkFont(size=11, weight="bold"),
                 text_color=value_color, anchor="e").pack(side="right")
    return row

def create_tooltip(widget, text):
    import tkinter as tk
    from tray.dashboard.theme import SURFACE, TEXT
    tipwindow = None
    id_after = None
    def showtip(event=None):
        nonlocal tipwindow
        if tipwindow or not text: return
        x = widget.winfo_rootx() + 20
        y = widget.winfo_rooty() + widget.winfo_height() + 5
        tipwindow = tw = tk.Toplevel(widget)
        tw.wm_overrideredirect(True)
        tw.wm_geometry("+%d+%d" % (x, y))
        label = tk.Label(tw, text=text, justify=tk.LEFT,
                         background=SURFACE, foreground=TEXT, relief=tk.SOLID, borderwidth=1,
                         font=("Consolas", "9", "normal"))
        label.pack(ipadx=4, ipady=2)
    def schedule(event=None):
        nonlocal id_after
        unschedule()
        id_after = widget.after(500, showtip)
    def unschedule(event=None):
        nonlocal id_after
        if id_after:
            widget.after_cancel(id_after)
            id_after = None
    def hidetip(event=None):
        nonlocal tipwindow
        unschedule()
        if tipwindow:
            tipwindow.destroy()
            tipwindow = None
    widget.bind("<Enter>", schedule, add="+")
    widget.bind("<Leave>", hidetip, add="+")
    widget.bind("<ButtonPress>", hidetip, add="+")
