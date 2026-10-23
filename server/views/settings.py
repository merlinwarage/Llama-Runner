"""Settings tab (split from server_panel.py)"""
import os
import shlex
import tkinter as tk
from bench_panel import resolve_path
from tkinter import filedialog
from tkinter import messagebox

from server.settings_store import write_setting


class SettingsMixin:
    """Settings tab."""
    def _build_settings(self):
        T, F = self.T, self.F
        page = tk.Frame(self, bg=T["bg"])
        page.grid_columnconfigure(0, weight=1)
        form = tk.Frame(page, bg=T["term"], highlightthickness=1, highlightbackground=T["border"])
        form.grid(row=0, column=0, sticky="ew", padx=18)
        form.grid_columnconfigure(1, weight=1)
        rows = [("server_exe", "llama-server executable", "file", "relative paths are resolved against the app folder, then PATH"),
                ("models_ini", "Models config (models.ini)", "file", "shared with the Benchmark menu"),
                ("extra_args", "Extra args for every server", "text", "raw, appended to every command (e.g. --no-webui --metrics)"),
                ("mcp_config", "MCP config path", "file", "passed as --mcp-servers-config; relative = app folder, then llama-server folder")]
        for i, (key, label, kind, hint) in enumerate(rows):
            var = tk.StringVar(value=self.s[key])
            self.svars[key] = var
            tk.Label(form, text=label, bg=T["term"], fg=T["text"], font=F["ui"], anchor="w").grid(row=i, column=0, sticky="w", padx=(14, 10), pady=6)
            self._entry(form, var).grid(row=i, column=1, sticky="ew", pady=6, ipady=3)
            if kind == "file":
                self.Btn(form, "\u2026", lambda k=key: self._browse_setting(k), T["panel2"], T["hover"], font=F["ui"], padx=10, pady=3).grid(row=i, column=2, padx=(6, 0))
            tk.Label(form, text=hint, bg=T["term"], fg=T["muted"], font=F["small"], anchor="w").grid(row=i, column=3, sticky="w", padx=10)
        checks = (("use_mcp", "Use MCP by default (each model can override this in its Config tab)"),
                  ("open_browser", "Open the WebUI in the browser when a server is ready"),
                  ("stop_on_exit", "Stop the running server when this app closes"))
        for j, (key, label) in enumerate(checks):
            var = tk.IntVar(value=1 if self.s[key] == "1" else 0)
            self.svars[key] = var
            var.trace_add("write", self._save_checks)
            tk.Checkbutton(form, text=label, variable=var, bg=T["term"], fg=T["text"], selectcolor=T["panel2"],
                           activebackground=T["term"], activeforeground=T["text"], font=F["ui"], bd=0, highlightthickness=0,
                           cursor="hand2").grid(row=len(rows) + j, column=1, sticky="w", pady=4)
        tk.Frame(form, height=8, bg=T["term"]).grid(row=len(rows) + len(checks))
        bar = tk.Frame(page, bg=T["bg"])
        bar.grid(row=1, column=0, sticky="ew", padx=18, pady=12)
        self.Btn(bar, "\U0001F4BE Apply & save", self.apply_settings, T["accent_bg"], "#388bfd", fg="white", font=F["bold"]).pack(side="left")
        tk.Label(bar, text="checkboxes save instantly; paths need Apply \u00B7 " + self.settings_path, bg=T["bg"], fg=T["muted"], font=F["small"]).pack(side="left", padx=10)
        tk.Label(page, justify="left", anchor="w", bg=T["bg"], fg=T["muted"], font=F["small"], text=(
            "Only one model runs at a time: starting another stops the running one first.\n"
            "Shortcuts:  F5 start / restart   Shift+F5 stop   F6 open WebUI   Ctrl+S save   Ctrl+F filter models   Up/Down in filter = switch model\n"
            "            Ctrl+Shift+N new from GGUF   Ctrl+Shift+D duplicate   Ctrl+R reload models.ini   Ctrl+L clear log   Ctrl+1/2/3 tabs")
                 ).grid(row=2, column=0, sticky="w", padx=18, pady=(4, 0))
        return page

    def _browse_setting(self, key):
        cur = resolve_path(self.svars[key].get(), self.app_dir)
        p = filedialog.askopenfilename(initialdir=os.path.dirname(cur) if cur and os.path.isdir(os.path.dirname(cur)) else self.app_dir)
        if p:
            self.svars[key].set(os.path.normpath(p))

    def _save_checks(self, *_):
        # checkboxes take effect immediately (no Apply needed)
        if not self.svars or any(k not in self.svars for k in ("use_mcp", "open_browser", "stop_on_exit")):
            return
        vals = {k: str(int(self.svars[k].get())) for k in ("use_mcp", "open_browser", "stop_on_exit")}
        try:
            write_setting(self.settings_path, "server", vals)
        except OSError as e:
            messagebox.showerror("Save failed", str(e))
            return
        self.s.update(vals)
        self._after_change()
        self.flash("Setting saved")

    def apply_settings(self):
        v = {k: (var.get() if isinstance(var, tk.IntVar) else var.get().strip()) for k, var in self.svars.items()}
        if v["extra_args"]:
            try:
                shlex.split(v["extra_args"], posix=False)
            except ValueError as e:
                messagebox.showerror("Invalid extra args", str(e))
                return
        old_ini = self.s["models_ini"]
        try:
            write_setting(self.settings_path, "server", {"server_exe": v["server_exe"] or "llama-server.exe", "extra_args": v["extra_args"],
                                                         "open_browser": int(v["open_browser"]), "stop_on_exit": int(v["stop_on_exit"]),
                                                         "mcp_config": v["mcp_config"] or "mcp.json", "use_mcp": int(v["use_mcp"])})
            write_setting(self.settings_path, "paths", {"models_ini": v["models_ini"] or "models.ini"})
        except OSError as e:
            messagebox.showerror("Save failed", str(e))
            return
        self.s.update(server_exe=v["server_exe"] or "llama-server.exe", extra_args=v["extra_args"], models_ini=v["models_ini"] or "models.ini",
                      open_browser=str(int(v["open_browser"])), stop_on_exit=str(int(v["stop_on_exit"])),
                      mcp_config=v["mcp_config"] or "mcp.json", use_mcp=str(int(v["use_mcp"])))
        if self.s["models_ini"] != old_ini:
            if self.dirty and not self._confirm_leave():
                return
            self.reload_ini()
            if self.on_ini_changed:
                self.on_ini_changed(self.ini_path)
        self._after_change()
        self.flash("Settings saved")
