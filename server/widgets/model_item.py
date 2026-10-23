"""widgets.model_item (split from server_panel.py)"""
import tkinter as tk

from server.widgets.tooltip import Tooltip


class ModelItem(tk.Frame):
    DOT = {"idle": "border", "loading": "warn", "waiting": "warn", "ready": "ok", "failed": "err", "stopped": "warn"}

    def __init__(self, master, T, name, title, fonts, on_click, on_menu):
        super().__init__(master, bg=T["side"], cursor="hand2")
        self.T, self.name, self.selected, self.hover = T, name, False, False
        self.bar = tk.Frame(self, width=3, bg=T["side"])
        self.bar.pack(side="left", fill="y")
        self.dot = tk.Label(self, text="\u25CF", bg=T["side"], fg=T["border"], font=fonts["small"])
        self.dot.pack(side="left", padx=(8, 0))
        self.inner = tk.Frame(self, bg=T["side"])
        self.inner.pack(side="left", fill="x", expand=True, padx=(6, 8), pady=6)
        self.title = tk.Label(self.inner, text=title, bg=T["side"], fg=T["text"], font=fonts["ui"], anchor="w")
        self.title.pack(fill="x")
        self.sub = tk.Label(self.inner, text="", bg=T["side"], fg=T["muted"], font=fonts["small"], anchor="w")
        self.sub.pack(fill="x")
        self.parts = (self, self.dot, self.inner, self.title, self.sub)
        for w in self.parts + (self.bar,):
            w.bind("<Enter>", self._enter)
            w.bind("<Leave>", self._leave)
            w.bind("<Button-1>", lambda e: on_click(self.name))
            w.bind("<Button-3>", lambda e: on_menu(self.name, e))
        self.tooltip = Tooltip(self.parts + (self.bar,), T, fonts["small"])

    def set_tip(self, text):
        self.tooltip.text = text

    def destroy(self):
        self.tooltip.hide()
        super().destroy()

    def _paint(self):
        T = self.T
        bg = T["sel"] if self.selected else (T["hover"] if self.hover else T["side"])
        for w in self.parts:
            w.config(bg=bg)
        self.bar.config(bg=T["accent"] if self.selected else bg)

    def _enter(self, _e):
        self.hover = True
        self._paint()

    def _leave(self, _e):
        self.hover = False
        self._paint()

    def set_selected(self, v):
        self.selected = v
        self._paint()

    def set_info(self, sub, state, warn=False):
        self.sub.config(text=sub, fg=self.T["err"] if warn else self.T["muted"])
        self.dot.config(fg=self.T[self.DOT.get(state, "border")])
