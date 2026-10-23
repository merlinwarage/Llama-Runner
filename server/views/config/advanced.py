"""Config tab: Advanced page (accordion, sections built on first open)"""
import os
import tkinter as tk
from tkinter import filedialog, ttk

from server.args import join_base, unquote
from server.views.config.spec import ADV_GROUPS
from server.widgets.tooltip import Tooltip


class ConfigAdvancedMixin:
    """Advanced page: all StringVars exist up front, widgets exist only for opened sections."""

    def _adv_wheel(self, e):  # stops ttk comboboxes from changing value on wheel; scrolls the page instead
        self._config_wheel(e)
        return "break"

    def _adv_browse(self, key, kind):
        cur = unquote(self.advvars[key][1].get())
        init = os.path.dirname(join_base(cur, self.base_dir())) if cur else self.base_dir()
        init = init if os.path.isdir(init) else self.base_dir()
        p = (filedialog.askdirectory(title=f"Select {key}", initialdir=init) if kind == "dir"
             else filedialog.askopenfilename(title=f"Select {key}", initialdir=init))
        if p:
            self.advvars[key][1].set(os.path.normpath(p))

    def _adv_cell(self, parent, key, kind, extra, hlp):
        T, F = self.T, self.F
        var = self.advvars[key][1]
        cell = tk.Frame(parent, bg=T["panel"])
        hd = tk.Frame(cell, bg=T["panel"])
        hd.pack(fill="x")
        lbl = tk.Label(hd, text=key, bg=T["panel"], fg=T["muted"], font=F["small"], anchor="w")
        lbl.pack(side="left")
        hint = tk.Label(hd, text="", bg=T["panel"], fg=T["warn"], font=F["small"], anchor="e")
        hint.pack(side="right")
        if kind == "f":
            w = tk.Checkbutton(cell, text="enable", variable=var, onvalue="true", offvalue="", bg=T["panel"],
                               fg=T["text"], selectcolor=T["panel2"], activebackground=T["panel"],
                               activeforeground=T["text"], font=F["ui"], bd=0, highlightthickness=0,
                               cursor="hand2", anchor="w")
            w.pack(fill="x")
        elif kind in ("b", "c"):
            vals = ["", "on", "off"] if kind == "b" else [""] + [x.strip() for x in (extra or "").split(",")]
            w = self._combo(cell, var, vals, state="readonly" if kind == "b" else "normal")
            w.pack(fill="x", ipady=2)
            w.bind("<MouseWheel>", self._adv_wheel)
        elif kind == "p":
            line = tk.Frame(cell, bg=T["panel"])
            line.pack(fill="x")
            self._entry(line, var).pack(side="left", fill="x", expand=True, ipady=3)
            self.Btn(line, "\u2026", lambda k=key, x=extra: self._adv_browse(k, x), T["panel2"], T["hover"],
                     font=F["ui"], padx=8, pady=2).pack(side="left", padx=(4, 0))
        else:
            self._entry(cell, var).pack(fill="x", ipady=3)
        self.adv_hints[key] = hint
        Tooltip([lbl], T, F["small"]).text = f"--{key}\n{hlp}"
        return cell

    def _build_advanced(self, parent):
        T, F = self.T, self.F
        page = tk.Frame(parent, bg=T["bg"])
        page.grid_rowconfigure(1, weight=1)
        page.grid_columnconfigure(0, weight=1)
        top = tk.Frame(page, bg=T["bg"])
        top.grid(row=0, column=0, columnspan=2, sticky="ew", padx=18, pady=(0, 6))
        tk.Label(top, text="Filter", bg=T["bg"], fg=T["muted"], font=F["small_b"]).pack(side="left", padx=(0, 8))
        self.adv_filter = tk.StringVar()
        self._entry(top, self.adv_filter).pack(side="left", fill="x", expand=True, ipady=3)
        self.adv_count = tk.Label(top, text="", bg=T["bg"], fg=T["muted"], font=F["small"])
        self.adv_count.pack(side="left", padx=10)
        self.Btn(top, "Collapse all", lambda: self._adv_set_all(False), T["panel2"], T["hover"],
                 font=F["ui"], padx=8, pady=2).pack(side="left")
        cv = tk.Canvas(page, bg=T["bg"], highlightthickness=0, bd=0)
        vs = ttk.Scrollbar(page, orient="vertical", command=cv.yview)
        cv.configure(yscrollcommand=vs.set)
        cv.grid(row=1, column=0, sticky="nsew")
        vs.grid(row=1, column=1, sticky="ns")
        inner = tk.Frame(cv, bg=T["bg"])
        win = cv.create_window((0, 0), window=inner, anchor="nw")
        self._adv_busy = False

        def fit(_e=None):
            if self._adv_busy:
                return
            cv.itemconfig(win, width=cv.winfo_width())
            cv.configure(scrollregion=cv.bbox("all"))

        self._adv_fit = fit
        cv.bind("<Configure>", fit)
        inner.bind("<Configure>", fit)
        self.adv_canvas, self.adv_inner = cv, inner

        self._adv_job = None
        for title, items in ADV_GROUPS:
            for key, kind, _extra, _hlp in items:
                var = tk.StringVar()
                var.trace_add("write", self._on_change)
                self.advvars[key] = (kind, var)
            gf = tk.Frame(inner, bg=T["panel"], highlightthickness=1, highlightbackground=T["border"])
            hdr = tk.Label(gf, text="", bg=T["panel"], fg=T["accent"], font=F["small_b"], anchor="w",
                           cursor="hand2")
            hdr.pack(fill="x", padx=12, pady=8)
            body = tk.Frame(gf, bg=T["panel"])
            for c in range(3):
                body.grid_columnconfigure(c, weight=1, uniform="a")
            g = {"title": title, "items": items, "frame": gf, "hdr": hdr, "body": body, "open": False,
                 "cells": None, "vis": None,
                 "index": [(k, (k + " " + h).lower()) for k, _kd, _ex, h in items]}
            hdr.bind("<Button-1>", lambda e, g=g: self._adv_toggle(g))
            self.adv_groups.append(g)
        self.adv_filter.trace_add("write", lambda *a: self._adv_schedule_layout())
        self._adv_layout(reset=True)
        return page

    def _adv_toggle(self, g):
        g["open"] = not g["open"]
        self._adv_layout()

    def _adv_set_all(self, state):
        for g in self.adv_groups:
            g["open"] = state
        self._adv_layout(reset=True)

    def _adv_build_cells(self, g):
        g["cells"] = {key: self._adv_cell(g["body"], key, kind, extra, hlp) for key, kind, extra, hlp in g["items"]}
        self._after_change()          # refresh "global: ..." hints on the new widgets

    def _adv_schedule_layout(self):
        if self._adv_job:
            self.after_cancel(self._adv_job)
        self._adv_job = self.after(150, lambda: self._adv_layout(reset=True))

    def _adv_layout(self, reset=False):
        self._adv_job = None
        q = self.adv_filter.get().strip().lower()
        shown = 0
        self._adv_busy = True
        for g in self.adv_groups:
            g["frame"].pack_forget()
        for g in self.adv_groups:
            match = [k for k, t in g["index"] if not q or q in t]
            if not match:
                continue
            expanded = bool(q) or g["open"]
            nset = sum(1 for k, _kd, _ex, _h in g["items"] if self.advvars[k][1].get().strip())
            arrow = "\u25BE" if expanded else "\u25B8"
            sep = "   \u00B7   "
            txt = f"{arrow} {g['title'].upper()}{sep}{len(match)} options"
            if nset:
                txt += f"{sep}{nset} set"
            g["hdr"].config(text=txt)
            g["frame"].pack(fill="x", padx=18, pady=(0, 8))
            shown += len(match)
            if not expanded:
                g["body"].pack_forget()
                continue
            if g["cells"] is None:
                self._adv_build_cells(g)
            g["body"].pack(fill="x", padx=12, pady=(0, 6))
            keys = tuple(match)
            if g["vis"] != keys:
                for cell in g["cells"].values():
                    cell.grid_forget()
                for i, k in enumerate(keys):
                    g["cells"][k].grid(row=i // 3, column=i % 3, sticky="ew",
                                       padx=(0 if i % 3 == 0 else 8, 0), pady=(0, 6))
                g["vis"] = keys
        self._adv_busy = False
        self.adv_count.config(text=f"{shown} options")
        self._adv_fit()
        if reset:
            self.adv_canvas.yview_moveto(0)