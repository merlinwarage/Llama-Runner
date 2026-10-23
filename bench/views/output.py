"""Output pane: log text, state, reports folder (split from bench_panel.py)"""
import os

from bench.models_ini import resolve_path


class OutputMixin:
    """Output pane: log text, state, reports folder."""
    def write(self, s, tag=None):
        self.out.config(state="normal")
        self.out.insert("end", s, tag)
        if int(self.out.index("end-1c").split(".")[0]) > 8000:
            self.out.delete("1.0", "2000.0")
        self.out.see("end")
        self.out.config(state="disabled")

    def clear(self):
        self.out.config(state="normal")
        self.out.delete("1.0", "end")
        self.out.config(state="disabled")

    def set_state(self, state, detail=""):
        T = self.T
        bg, fg, label = {"idle": (T["panel2"], T["muted"], "Idle"), "running": ("#12261a", T["ok"], "Running"),
                         "done": ("#12261a", T["ok"], "Finished"), "failed": ("#2d1517", T["err"], "Failed"),
                         "stopped": ("#2b2111", T["warn"], "Stopped")}[state]
        self.chip.config(bg=bg, fg=fg, text="\u25CF " + label + (f"  {detail}" if detail else ""))

    def open_reports(self):
        d = resolve_path(self.cfg["paths"]["output_dir"], self.app_dir)
        os.makedirs(d, exist_ok=True)
        os.startfile(d)
