"""Settings view: form, save, reset (split from bench_panel.py)"""
import os
import tkinter as tk
from datetime import datetime
from tkinter import filedialog
from tkinter import messagebox
from tkinter import ttk

from bench.models_ini import resolve_path
from bench.settings_store import default_cfg, norm, save_settings, validate
from bench.views.settings_spec import GROUPS


class SettingsMixin:
    """Settings view: form, save, reset."""
    def _build_settings(self):
        T, F = self.T, self.F
        page = tk.Frame(self, bg=T["bg"])
        page.grid_rowconfigure(0, weight=1)
        page.grid_columnconfigure(0, weight=1)
        wrap = tk.Frame(page, bg=T["term"], highlightthickness=1, highlightbackground=T["border"])
        wrap.grid(row=0, column=0, sticky="nsew", padx=18)
        wrap.grid_rowconfigure(0, weight=1)
        wrap.grid_columnconfigure(0, weight=1)
        self.set_canvas = tk.Canvas(wrap, bg=T["term"], highlightthickness=0, bd=0)
        sb = ttk.Scrollbar(wrap, orient="vertical", command=self.set_canvas.yview)
        self.set_canvas.config(yscrollcommand=sb.set)
        self.set_canvas.grid(row=0, column=0, sticky="nsew")
        sb.grid(row=0, column=1, sticky="ns")
        form = tk.Frame(self.set_canvas, bg=T["term"])
        win = self.set_canvas.create_window((0, 0), window=form, anchor="nw")
        form.bind("<Configure>", lambda e: self.set_canvas.configure(scrollregion=self.set_canvas.bbox("all")))
        self.set_canvas.bind("<Configure>", lambda e: self.set_canvas.itemconfig(win, width=e.width))
        self.set_canvas.bind_all("<MouseWheel>", self._wheel, add="+")
        form.grid_columnconfigure(1, weight=1)

        r = 0
        for title, fields in GROUPS:
            tk.Label(form, text=title, bg=T["term"], fg=T["accent"], font=F["bold"], anchor="w").grid(
                row=r, column=0, columnspan=4, sticky="w", padx=14, pady=(14, 4))
            r += 1
            for sec, key, default, label, hint, kind in fields:
                var = tk.StringVar(value=self.cfg[sec].get(key, default))
                self.vars[(sec, key)] = var
                tk.Label(form, text=label, bg=T["term"], fg=T["text"], font=F["ui"], anchor="w").grid(
                    row=r, column=0, sticky="w", padx=(14, 10), pady=3)
                self._entry(form, var).grid(row=r, column=1, sticky="ew", pady=3, ipady=3)
                if kind in ("file", "dir"):
                    self.Btn(form, "\u2026", lambda v=var, k=kind: self._browse(v, k), T["panel2"], T["hover"],
                             font=F["ui"]).grid(row=r, column=2, padx=(6, 0), pady=3)
                tk.Label(form, text=hint, bg=T["term"], fg=T["muted"], font=F["small"], anchor="w").grid(
                    row=r, column=3, sticky="w", padx=10)
                r += 1
        tk.Frame(form, bg=T["term"], height=10).grid(row=r)

        bar = tk.Frame(page, bg=T["bg"])
        bar.grid(row=1, column=0, sticky="ew", padx=18, pady=12)
        self.Btn(bar, "\U0001F4BE Save to settings.ini", self.save, T["accent_bg"], "#388bfd", fg="white", font=F["bold"]).pack(side="left")
        self.Btn(bar, "Reset to defaults", self.reset, T["panel2"], T["hover"], font=F["bold"]).pack(side="left", padx=8)
        self.save_lbl = tk.Label(bar, text=self.settings_path, bg=T["bg"], fg=T["muted"], font=F["small"])
        self.save_lbl.pack(side="left", padx=10)
        return page

    def _browse(self, var, kind):
        cur = resolve_path(var.get(), self.app_dir)
        if kind == "dir":
            p = filedialog.askdirectory(initialdir=cur if os.path.isdir(cur) else self.app_dir)
        else:
            p = filedialog.askopenfilename(initialdir=os.path.dirname(cur) if cur else self.app_dir)
        if p:
            var.set(os.path.normpath(p))

    def _collect(self):
        cfg = {s: dict(kv) for s, kv in self.cfg.items()}
        for (sec, key), var in self.vars.items():
            cfg[sec][key] = var.get().strip()
        return cfg

    def save(self):
        cfg = self._collect()
        errs = validate(cfg)
        if errs:
            messagebox.showerror("Invalid settings", "\n".join(errs))
            return
        for sec in ("bench", "sweeps"):
            for k, v in cfg[sec].items():
                if k not in ("extra-args", "show-diagnostics"):
                    cfg[sec][k] = norm(v)
        old_ini = self.cfg["paths"]["models_ini"]
        self.cfg = cfg
        try:
            save_settings(self.settings_path, cfg)
            self.save_lbl.config(text=f"Saved {datetime.now():%H:%M:%S} \u00B7 {self.settings_path}", fg=self.T["ok"])
        except OSError as e:
            messagebox.showerror("Save failed", str(e))
            return
        for (sec, key), var in self.vars.items():
            var.set(cfg[sec][key])
        if cfg["paths"]["models_ini"] != old_ini:
            self.reload_models()
        self._refresh_preview()

    def reset(self):
        d = default_cfg()
        for (sec, key), var in self.vars.items():
            var.set(d[sec][key])
        self.save_lbl.config(text="Defaults loaded - press Save to keep them", fg=self.T["warn"])
