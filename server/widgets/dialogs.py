"""widgets.dialogs (split from server_panel.py)"""
import tkinter as tk


def ask_text(parent, T, fonts, title, prompt, initial=""):
    top = parent.winfo_toplevel()
    dlg = tk.Toplevel(top)
    dlg.title(title)
    dlg.configure(bg=T["bg"])
    dlg.transient(top)
    dlg.resizable(False, False)
    res = [None]
    tk.Label(dlg, text=prompt, bg=T["bg"], fg=T["text"], font=fonts["ui"], anchor="w").pack(fill="x", padx=18, pady=(16, 6))
    var = tk.StringVar(value=initial)
    ent = tk.Entry(dlg, textvariable=var, width=52, bg=T["panel"], fg=T["text"], insertbackground=T["text"], relief="flat",
                   font=fonts["ui"], highlightthickness=1, highlightbackground=T["border"], highlightcolor=T["accent"])
    ent.pack(fill="x", padx=18, ipady=5)
    bar = tk.Frame(dlg, bg=T["bg"])
    bar.pack(fill="x", padx=18, pady=14)

    def ok(_e=None):
        res[0] = var.get().strip()
        dlg.destroy()

    for text, cmd, bg, fg in (("OK", ok, T["accent_bg"], "white"), ("Cancel", dlg.destroy, T["panel2"], T["text"])):
        tk.Button(bar, text=text, command=cmd, bg=bg, fg=fg, relief="flat", font=fonts["bold"], padx=16, pady=3,
                  activebackground=T["hover"], activeforeground=T["text"], cursor="hand2").pack(side="right", padx=(6, 0))
    dlg.bind("<Return>", ok)
    dlg.bind("<Escape>", lambda e: dlg.destroy())
    dlg.update_idletasks()
    x = top.winfo_rootx() + (top.winfo_width() - dlg.winfo_width()) // 2
    y = top.winfo_rooty() + (top.winfo_height() - dlg.winfo_height()) // 3
    dlg.geometry(f"+{max(0, x)}+{max(0, y)}")
    dlg.grab_set()
    ent.focus_set()
    ent.select_range(0, "end")
    parent.wait_window(dlg)
    return res[0]
