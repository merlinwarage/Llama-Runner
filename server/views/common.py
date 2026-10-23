"""Shared widget factories and model/ini lookups (split from server_panel.py)"""
import os
import tkinter as tk
from tkinter import ttk

from server.constants import GLOBAL
from server.runner import Runner


class CommonMixin:
    """Shared widget factories and model/ini lookups."""
    def _entry(self, parent, var, **kw):
        T = self.T
        return tk.Entry(parent, textvariable=var, bg=T["panel"], fg=T["text"], insertbackground=T["text"], relief="flat",
                        font=self.F["ui"], highlightthickness=1, highlightbackground=T["border"],
                        highlightcolor=T["accent"], **kw)

    def _combo(self, parent, var, values, **kw):
        return ttk.Combobox(parent, textvariable=var, values=values, font=self.F["ui"], **kw)

    def base_dir(self):
        return os.path.dirname(os.path.abspath(self.ini_path)) if self.ini_path else self.app_dir

    def model_names(self):
        return [n for n in self.doc.names() if n != GLOBAL]

    def merged(self, name):
        g = self.doc.dict(GLOBAL) if self.doc.has(GLOBAL) else {}
        m = dict(g)
        if name and name != GLOBAL:
            m.update(self.doc.dict(name))
        return m

    def runner(self, name):
        if name not in self.runners:
            self.runners[name] = Runner(name)
        return self.runners[name]

    def running_count(self):
        return sum(1 for r in self.runners.values() if r.alive())

    def flash(self, text, color=None):
        self.flash_lbl.config(text=text, fg=color or self.T["ok"])
        if self._flash_id:
            self.after_cancel(self._flash_id)
        self._flash_id = self.after(4500, lambda: self.flash_lbl.config(text=""))
