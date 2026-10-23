"""Header status: title, chip, perf counters (split from server_panel.py)"""
import os
import time

from server.args import join_base, unquote
from server.constants import GLOBAL


class HeaderMixin:
    """Header status: title, chip, perf counters."""
    def _refresh_header(self):
        name = self.selected
        if not name:
            self.h_title.config(text="No model selected")
            self.h_sub.config(text="")
            self._set_chip()
            return
        self.h_title.config(text="Global defaults [*]" if name == GLOBAL else name)
        if name == GLOBAL:
            self.h_sub.config(text="Shared by all models. Model sections override these values.", fg=self.T["muted"])
        else:
            m = self.merged(name)
            mp = unquote(m.get("model", ""))
            if mp:
                full = join_base(mp, self.base_dir())
                ok = os.path.isfile(full)
                self.h_sub.config(text=full + ("" if ok else "  (FILE NOT FOUND)"), fg=self.T["muted"] if ok else self.T["err"])
            else:
                self.h_sub.config(text=m.get("hf") or m.get("hf-repo") or "No 'model' set in this section", fg=self.T["muted"])
        self._set_chip()

    def _set_chip(self):
        T = self.T
        r = self.runners.get(self.selected)
        if self.selected == GLOBAL or not self.selected:
            self.chip.config(text="\u25CF Defaults", bg=T["panel2"], fg=T["muted"])
            self.perf.config(text="")
            self.btn_start.config(text="\u25B6 Start  F5")
            return
        st = r.state if r else "idle"
        if r and r.alive():
            up = int(time.time() - r.started)
            t = f"{up // 3600:d}:{up % 3600 // 60:02d}:{up % 60:02d}" if up >= 3600 else f"{up // 60:02d}:{up % 60:02d}"
            if st == "ready":
                bg, fg, txt = "#12261a", T["ok"], f"\u25CF Ready :{r.port} \u00B7 {t}"
            else:
                bg, fg, txt = "#2b2111", T["warn"], f"\u25CF Loading\u2026 {t}"
            self.btn_start.config(text="\u21BB Restart  F5")
        else:
            self.btn_start.config(text="\u25B6 Start  F5")
            bg, fg, txt = {"idle": (T["panel2"], T["muted"], "\u25CF Idle"),
                           "waiting": ("#2b2111", T["warn"], "\u25CF Waiting for previous model\u2026"),
                           "stopped": ("#2b2111", T["warn"], "\u25CF Stopped"),
                           "failed": ("#2d1517", T["err"], f"\u25CF Exited {r.code if r else ''}"),
                           "done": (T["panel2"], T["muted"], "\u25CF Exited (0)")}.get(st, (T["panel2"], T["muted"], "\u25CF Idle"))
        self.chip.config(text=txt, bg=bg, fg=fg)
        self.perf.config(text=" \u00B7 ".join(x for x in ((f"PP {r.pp} t/s" if r and r.pp else ""), (f"TG {r.tg} t/s" if r and r.tg else "")) if x))
