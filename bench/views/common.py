"""Shared widget factory and mouse wheel (split from bench_panel.py)"""
import tkinter as tk


class CommonMixin:
    """Shared widget factory and mouse wheel."""
    def _entry(self, parent, var, **kw):
        T = self.T
        return tk.Entry(parent, textvariable=var, bg=T["panel"], fg=T["text"], insertbackground=T["text"],
                        relief="flat", font=self.F["ui"], highlightthickness=1,
                        highlightbackground=T["border"], highlightcolor=T["accent"], **kw)

    def _wheel(self, e):
        w = self.winfo_containing(e.x_root, e.y_root)
        if w is not None and str(w).startswith(str(self.set_canvas)) and self.pages["settings"].winfo_ismapped():
            self.set_canvas.yview_scroll(int(-e.delta / 120), "units")
            return "break"
