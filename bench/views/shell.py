"""Top-level layout and show() (split from bench_panel.py)"""
import tkinter as tk


class ShellMixin:
    """Top-level layout and show()."""
    def _build(self):
        T, F = self.T, self.F
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)
        tabs = tk.Frame(self, bg=T["bg"])
        tabs.grid(row=0, column=0, sticky="ew", padx=18, pady=(14, 8))
        tk.Label(tabs, text="\U0001F9EA Benchmark", bg=T["bg"], fg=T["text"], font=F["h"]).pack(side="left")
        self.chip = tk.Label(tabs, text="\u25CF Idle", bg=T["panel2"], fg=T["muted"], font=F["bold"], padx=12, pady=4)
        self.chip.pack(side="right")
        self.tab_btns = {}
        for name, text in (("settings", "\u2699 Settings"), ("run", "\u25B6 Run")):
            b = self.Btn(tabs, text, lambda n=name: self.show(n), T["panel2"], T["hover"], font=F["bold"])
            b.pack(side="right", padx=4)
            self.tab_btns[name] = b
        self.pages = {"run": self._build_run(), "settings": self._build_settings()}
        self.show("run")

    def show(self, name):
        for n, p in self.pages.items():
            p.grid_remove()
            active = n == name
            self.tab_btns[n]._bg = self.T["accent_bg"] if active else self.T["panel2"]
            self.tab_btns[n].config(bg=self.tab_btns[n]._bg, fg="white" if active else self.T["text"])
        self.pages[name].grid(row=1, column=0, sticky="nsew")
        if name == "run":
            self._refresh_preview()
