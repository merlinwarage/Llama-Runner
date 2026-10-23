"""Header, tab bar and tab switching (split from server_panel.py)"""
import tkinter as tk

from server.constants import GLOBAL


class ShellMixin:
    """Header, tab bar and tab switching."""
    TABS = (("console", "\u25B6 Console  (Ctrl+1)"), ("config", "\u270E Config  (Ctrl+2)"), ("settings", "\u2699 Settings  (Ctrl+3)"))

    def _build(self):
        T, F = self.T, self.F
        self.grid_rowconfigure(2, weight=1)
        self.grid_columnconfigure(0, weight=1)

        head = tk.Frame(self, bg=T["bg"])
        head.grid(row=0, column=0, sticky="ew", padx=18, pady=(14, 6))

        right = tk.Frame(head, bg=T["bg"])
        right.pack(side="right")
        
        left = tk.Frame(head, bg=T["bg"])
        left.pack(side="left", fill="x", expand=True)
        self.h_title = tk.Label(left, text="No model selected", bg=T["bg"], fg=T["text"], font=F["h"], anchor="w")
        self.h_title.pack(fill="x")
        self.h_sub = tk.Label(left, text="", bg=T["bg"], fg=T["muted"], font=F["small"], anchor="w")
        self.h_sub.pack(fill="x")

        self.perf = tk.Label(right, text="", bg=T["bg"], fg=T["muted"], font=F["mono_s"])
        self.perf.pack(side="left", padx=(0, 10))
        self.chip = tk.Label(right, text="\u25CF Idle", bg=T["panel2"], fg=T["muted"], font=F["bold"], padx=12, pady=4)
        self.chip.pack(side="left", padx=(0, 10))
        self.btn_start = self.Btn(right, "\u25B6 Start  F5", self.toggle_start, T["accent_bg"], "#388bfd", fg="white", font=F["bold"])
        self.btn_start.pack(side="left", padx=3)
        self.Btn(right, "\u25A0 Stop", self.stop, T["panel2"], "#3b1d1f", fg=T["err"], font=F["bold"]).pack(side="left", padx=3)
        self.Btn(right, "\U0001F310 WebUI", self.open_webui, T["panel2"], T["hover"], font=F["bold"]).pack(side="left", padx=3)

        tabs = tk.Frame(self, bg=T["bg"])
        tabs.grid(row=1, column=0, sticky="ew", padx=18, pady=(0, 8))
        self.tab_btns = {}
        for name, text in self.TABS:
            b = self.Btn(tabs, text, lambda n=name: self.show_tab(n), T["panel2"], T["hover"], font=F["ui"])
            b.pack(side="left", padx=(0, 6))
            self.tab_btns[name] = b
        self.flash_lbl = tk.Label(tabs, text="", bg=T["bg"], fg=T["ok"], font=F["small_b"])
        self.flash_lbl.pack(side="right")

        self.pages = {"console": self._build_console(), "config": self._build_config(), "settings": self._build_settings()}
        self.show_tab("config")

    def show_tab(self, name):
        if name == "console" and self.selected == GLOBAL:
            name = "config"
        self.tab = name
        for n, p in self.pages.items():
            p.grid_remove()
            active = n == name
            b = self.tab_btns[n]
            b._bg = self.T["accent_bg"] if active else self.T["panel2"]
            b.config(bg=b._bg, fg="white" if active else self.T["text"])
        self.pages[name].grid(row=2, column=0, sticky="nsew")
        if name == "console":
            self.text.focus_set()
