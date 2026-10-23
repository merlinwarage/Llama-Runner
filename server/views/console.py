"""Console tab: log view and log actions (split from server_panel.py)"""
import tkinter as tk
from datetime import datetime
from tkinter import filedialog
from tkinter import ttk

from server.constants import ERR_RE, OK_RE, WARN_RE


class ConsoleMixin:
    """Console tab: log view and log actions."""
    def _build_console(self):
        T, F = self.T, self.F
        page = tk.Frame(self, bg=T["bg"])
        page.grid_rowconfigure(0, weight=1)
        page.grid_columnconfigure(0, weight=1)
        card = tk.Frame(page, bg=T["term"], highlightthickness=1, highlightbackground=T["border"])
        card.grid(row=0, column=0, sticky="nsew", padx=18)
        card.grid_rowconfigure(0, weight=1)
        card.grid_columnconfigure(0, weight=1)
        self.text = tk.Text(card, bg=T["term"], fg=T["text"], insertbackground=T["text"], font=F["mono"], wrap="none",
                            state="disabled", relief="flat", bd=0, padx=14, pady=10, selectbackground="#264f78",
                            spacing1=1, spacing3=1)
        sy = ttk.Scrollbar(card, orient="vertical", command=self.text.yview)
        sx = ttk.Scrollbar(card, orient="horizontal", command=self.text.xview)
        self.text.config(yscrollcommand=sy.set, xscrollcommand=sx.set)
        self.text.grid(row=0, column=0, sticky="nsew")
        sy.grid(row=0, column=1, sticky="ns")
        sx.grid(row=1, column=0, sticky="ew")
        for tag, col in (("info", T["warn"]), ("err", T["err"]), ("ok", T["ok"]), ("cmd", T["accent"]), ("warn", T["warn"])):
            self.text.tag_config(tag, foreground=col)
        bar = tk.Frame(page, bg=T["bg"])
        bar.grid(row=1, column=0, sticky="ew", padx=18, pady=10)
        self.Btn(bar, "\u2715 Clear  Ctrl+L", self.clear_log, T["panel2"], T["hover"], font=F["ui"]).pack(side="left", padx=(0, 6))
        self.Btn(bar, "\u2398 Copy log", self.copy_log, T["panel2"], T["hover"], font=F["ui"]).pack(side="left", padx=6)
        self.Btn(bar, "\U0001F4BE Save log\u2026", self.save_log, T["panel2"], T["hover"], font=F["ui"]).pack(side="left", padx=6)
        self.Btn(bar, "\u2398 Copy command", self.copy_command, T["panel2"], T["hover"], font=F["ui"]).pack(side="left", padx=6)
        return page

    def _classify(self, line):
        if ERR_RE.search(line):
            return "err"
        if WARN_RE.search(line):
            return "warn"
        if OK_RE.search(line):
            return "ok"
        return None

    def _log(self, name, text, tag=None):
        r = self.runner(name)
        r.lines.append((text, tag))
        if len(r.lines) > 6000:
            del r.lines[:1000]
        if name == self.selected:
            self.pending.append((text, tag))

    def _flush(self):
        if not self.pending:
            return
        t = self.text
        at_bottom = t.yview()[1] >= 0.97
        t.config(state="normal")
        buf, cur = [], None
        for text, tag in self.pending:
            if tag != cur and buf:
                t.insert("end", "".join(buf), cur)
                buf = []
            cur = tag
            buf.append(text)
        if buf:
            t.insert("end", "".join(buf), cur)
        self.pending = []
        if int(t.index("end-1c").split(".")[0]) > 6000:
            t.delete("1.0", "1001.0")
        if at_bottom:
            t.see("end")
        t.config(state="disabled")

    def _render_console(self):
        self.pending = []
        t = self.text
        t.config(state="normal")
        t.delete("1.0", "end")
        r = self.runners.get(self.selected)
        if r:
            buf, cur = [], None
            for text, tag in r.lines:
                if tag != cur and buf:
                    t.insert("end", "".join(buf), cur)
                    buf = []
                cur = tag
                buf.append(text)
            if buf:
                t.insert("end", "".join(buf), cur)
        t.see("end")
        t.config(state="disabled")

    def clear_log(self):
        r = self.runners.get(self.selected)
        if r:
            r.lines = []
        self._render_console()

    def copy_log(self):
        r = self.runners.get(self.selected)
        self.clipboard_clear()
        self.clipboard_append("".join(t for t, _ in r.lines) if r else "")
        self.flash("Log copied")

    def save_log(self):
        r = self.runners.get(self.selected)
        if not r or not r.lines:
            return
        p = filedialog.asksaveasfilename(defaultextension=".log", initialfile=f"{self.selected}_{datetime.now():%Y%m%d_%H%M%S}.log",
                                         filetypes=[("Log", "*.log"), ("Text", "*.txt")])
        if p:
            with open(p, "w", encoding="utf-8") as f:
                f.write("".join(t for t, _ in r.lines))
            self.flash("Log saved")

    def copy_command(self):
        self.clipboard_clear()
        self.clipboard_append(self.preview.get("1.0", "end").strip())
        self.flash("Command copied")
