"""widgets.tooltip (split from server_panel.py)"""
import tkinter as tk


class Tooltip:
    def __init__(self, widgets, T, font, delay=450, wrap=560):
        self.T, self.font, self.delay, self.wrap = T, font, delay, wrap
        self.text, self.tip, self.job, self.w = "", None, None, widgets[0]
        for w in widgets:
            w.bind("<Enter>", self._enter, add="+")
            w.bind("<Leave>", self.hide, add="+")
            w.bind("<ButtonPress>", self.hide, add="+")

    def _enter(self, e):
        self.hide()
        if self.text:
            self.job = self.w.after(self.delay, lambda x=e.x_root, y=e.y_root: self._show(x, y))

    def _show(self, x, y):
        self.job = None
        try:
            tip = tk.Toplevel(self.w)
            tip.wm_overrideredirect(True)
            tip.attributes("-topmost", True)
            tk.Label(tip, text=self.text, justify="left", wraplength=self.wrap, bg=self.T["panel2"],
                     fg=self.T["text"], font=self.font, padx=10, pady=6, highlightthickness=1,
                     highlightbackground=self.T["border"]).pack()
            tip.geometry(f"+{x + 16}+{y + 18}")
            self.tip = tip
        except tk.TclError:
            self.tip = None

    def hide(self, _e=None):
        if self.job:
            try:
                self.w.after_cancel(self.job)
            except Exception:
                pass
            self.job = None
        if self.tip:
            try:
                self.tip.destroy()
            except Exception:
                pass
            self.tip = None
