"""models.ini load / reload / write / change detection (split from server_panel.py)"""
import glob
import os
import shutil
import subprocess
from bench_panel import resolve_path
from tkinter import messagebox

from server.args import join_base
from server.constants import GLOBAL
from server.ini_doc import IniDoc
from server.settings_store import load_srv_settings


class IniStoreMixin:
    """models.ini load / reload / write / change detection."""
    def ini_file(self):
        p = resolve_path(self.s["models_ini"], self.app_dir)
        if not os.path.isfile(p):
            found = sorted(glob.glob(os.path.join(self.app_dir, "models*.ini")))
            if found:
                p = found[0]
        return p

    def reload_ini(self):
        path = self.ini_file()
        self.ini_path, self.ini_err = path, None
        try:
            if os.path.isfile(path):
                with open(path, encoding="utf-8-sig", newline="") as f:
                    text = f.read()
                self.ini_mtime = os.path.getmtime(path)
            else:
                text = "; llama-server presets: one [section] per model, keys = llama-server flags without dashes\n[*]\n"
                self.ini_mtime = None
            self.doc = IniDoc(text)
        except Exception as e:
            self.doc, self.ini_err = IniDoc(), str(e)
        self.dirty = False
        names = self.model_names()
        keep = self.selected if (self.selected in names or self.selected == GLOBAL) else None
        if not keep:
            last = self.s.get("last_model")
            keep = last if last in names else (names[0] if names else GLOBAL)
        self.selected = keep
        self.render_list()
        self._load_form()
        self._refresh_header()
        self._render_console()
        if self.tab == "console" and self.selected == GLOBAL:
            self.show_tab("config")

    def check_external(self):
        if self.dirty or not self.ini_path or self.ini_mtime is None:
            return
        try:
            m = os.path.getmtime(self.ini_path)
        except OSError:
            return
        if m != self.ini_mtime:
            self.reload_ini()
            self.flash("models.ini changed on disk - reloaded")

    def sync_ini_from_settings(self):
        s = load_srv_settings(self.settings_path)
        if s["models_ini"] != self.s["models_ini"] and not self.dirty:
            self.s["models_ini"] = s["models_ini"]
            self.svars["models_ini"].set(s["models_ini"])
            self.reload_ini()

    def _write_ini(self):
        path = self.ini_path or os.path.join(self.app_dir, "models.ini")
        try:
            if os.path.isfile(path):
                shutil.copy2(path, path + ".bak")
            tmp = path + ".tmp"
            with open(tmp, "w", encoding="utf-8", newline="") as f:
                f.write(self.doc.dump())
            os.replace(tmp, path)
            self.ini_path, self.ini_mtime = path, os.path.getmtime(path)
            return True
        except OSError as e:
            messagebox.showerror("Save failed", f"{path}\n\n{e}")
            return False

    def open_ini(self):
        try:
            if not os.path.isfile(self.ini_path):
                self._write_ini()
            os.startfile(self.ini_path)
        except Exception as e:
            messagebox.showerror("Open failed", str(e))

    def show_folder(self):
        m = self.merged(self.selected).get("model", "")
        p = join_base(m, self.base_dir()) if m else ""
        try:
            if p and os.path.isfile(p):
                subprocess.Popen(["explorer", "/select,", os.path.normpath(p)])
            elif p and os.path.isdir(os.path.dirname(p)):
                os.startfile(os.path.dirname(p))
        except Exception as e:
            messagebox.showerror("Open failed", str(e))
