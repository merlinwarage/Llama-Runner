"""Create / duplicate / rename / delete model sections (split from server_panel.py)"""
import os
import re
from tkinter import filedialog
from tkinter import messagebox

from server.constants import GLOBAL
from server.widgets.dialogs import ask_text


class ModelActionsMixin:
    """Create / duplicate / rename / delete model sections."""
    def _unique(self, base):
        n, name = 2, base
        while self.doc.has(name):
            name = f"{base}-{n}"
            n += 1
        return name

    def _valid_name(self, name, old=None):
        if not name or any(c in name for c in "[]\r\n") or name == GLOBAL:
            messagebox.showerror("Invalid name", "Use a non-empty name without [ ] characters.")
            return False
        if name != old and self.doc.has(name):
            messagebox.showerror("Name taken", f"[{name}] already exists.")
            return False
        return True

    def _after_structure(self, select):
        self.dirty = False
        self.selected = select
        if self.flt.get():
            self.flt.set("")
        self.render_list()
        self._load_form()
        self._refresh_header()
        self._render_console()
        self._see(select)
        if self.on_ini_changed:
            self.on_ini_changed(self.ini_path)

    def new_from_gguf(self):
        if self.dirty and not self._confirm_leave():
            return
        init = self.s.get("gguf_dir") or self.base_dir()
        p = filedialog.askopenfilename(title="Select a GGUF model", initialdir=init if os.path.isdir(init) else self.base_dir(),
                                       filetypes=[("GGUF", "*.gguf"), ("All files", "*.*")])
        if not p:
            return
        self._remember_dir(p)
        stem = re.sub(r"-0*1-of-\d+$", "", re.sub(r"\.gguf$", "", os.path.basename(p), flags=re.I), flags=re.I)
        name = ask_text(self, self.T, self.F, "New model", "Name of the new [section]:", self._unique(stem))
        if name is None or not self._valid_name(name):
            return
        self.doc.add(name, [f"model = {p}"])
        if self._write_ini():
            self._after_structure(name)
            self.show_tab("config")
            self.flash(f"Created [{name}]")

    def duplicate(self):
        name = self.selected
        if not name or name == GLOBAL:
            return
        if self.dirty and not self.save():
            return
        new = self._unique(name + "-copy")
        self.doc.add(new, [ln for ln in self.doc.body(name)], self.doc.comment(name))
        if self._write_ini():
            self._after_structure(new)
            self.flash(f"Duplicated to [{new}]")

    def rename(self):
        name = self.selected
        if not name or name == GLOBAL:
            return
        if self.runner(name).alive():
            messagebox.showwarning("Running", "Stop the server before renaming it.")
            return
        if self.dirty and not self.save():
            return
        new = ask_text(self, self.T, self.F, "Rename model", f"New name for [{name}]:", name)
        if new is None or new == name or not self._valid_name(new, name):
            return
        self.doc.rename(name, new)
        self.runners.pop(name, None)
        if self._write_ini():
            self._after_structure(new)
            self.flash(f"Renamed to [{new}]")

    def delete(self):
        name = self.selected
        if not name or name == GLOBAL:
            return
        if not messagebox.askyesno("Delete model", f"Remove [{name}] from models.ini?\n(a models.ini.bak backup is kept)"):
            return
        if self.runner(name).alive():
            self.stop(name)
        self.doc.remove(name)
        self.runners.pop(name, None)
        if self._write_ini():
            names = self.model_names()
            self._after_structure(names[0] if names else GLOBAL)
            self.flash(f"Deleted [{name}]", self.T["warn"])
