"""Model list, selection, info and command preview (split from bench_panel.py)"""
import glob
import os
import subprocess
from tkinter import filedialog
from tkinter import messagebox

from bench.cmdline import build_plan
from bench.models_ini import load_models, resolve_path
from bench.settings_store import save_settings


class ModelsMixin:
    """Model list, selection, info and command preview."""
    def choose_models_ini(self):
        cur = resolve_path(self.cfg["paths"]["models_ini"], self.app_dir)
        p = filedialog.askopenfilename(title="Select models.ini", initialdir=os.path.dirname(cur) if cur else self.app_dir,
                                       filetypes=[("INI files", "*.ini"), ("All files", "*.*")])
        if not p:
            return
        p = os.path.normpath(p)
        self.cfg["paths"]["models_ini"] = p
        self.vars[("paths", "models_ini")].set(p)
        try:
            save_settings(self.settings_path, {"paths": self.cfg["paths"]})
        except OSError as e:
            messagebox.showerror("Save failed", str(e))
        self.reload_models()

    def reload_models(self):
        path = resolve_path(self.cfg["paths"]["models_ini"], self.app_dir)
        if not os.path.isfile(path):
            found = sorted(glob.glob(os.path.join(self.app_dir, "models*.ini")))
            if found:
                path = found[0]
        try:
            _, self.models = load_models(path)
            self.models_lbl.config(text=f"{len(self.models)} models \u00B7 {path}", fg=self.T["muted"])
        except Exception as e:
            self.models = {}
            self.models_lbl.config(text=f"Cannot read {path}: {e}", fg=self.T["err"])
        self.model_names = list(self.models)
        self._fill_list()
        last = self.cfg["state"].get("last_model")
        if last in self.models:
            self._select_name(last)

    def _fill_list(self):
        f = self.flt.get().strip().lower()
        self.lb.delete(0, "end")
        self.visible = [n for n in self.model_names if f in n.lower()]
        for n in self.visible:
            moe = self.models[n].get("n-cpu-moe")
            self.lb.insert("end", n + (f"   [MoE {moe}]" if moe else ""))
        if self.selected in self.visible:
            i = self.visible.index(self.selected)
            self.lb.selection_set(i)
            self.lb.see(i)

    def _select_name(self, name):
        self.selected = name
        self._fill_list()
        self._update_model_info()

    def _on_select(self, _e=None):
        sel = self.lb.curselection()
        if sel:
            self.selected = self.visible[sel[0]]
            self.cfg["state"]["last_model"] = self.selected
            try:
                save_settings(self.settings_path, {"state": {"last_model": self.selected}})
            except OSError:
                pass
            self._update_model_info()

    def _update_model_info(self):
        m = self.models.get(self.selected)
        if not m:
            return
        self.model_title.config(text=self.selected)
        ok = os.path.isfile(m["model"])
        self.model_info.config(text=m["model"] + ("" if ok else "   (FILE NOT FOUND)"), fg=self.T["muted"] if ok else self.T["err"])
        self._refresh_preview()

    def _refresh_preview(self):
        m = self.models.get(self.selected)
        if not m:
            self.preview.config(text="")
            return
        try:
            args = build_plan("baseline", self.cfg, m)[0][1]
            self.preview.config(text="baseline: llama-bench " + subprocess.list2cmdline(args[2:]))
        except Exception as e:
            self.preview.config(text=f"preview error: {e}")
