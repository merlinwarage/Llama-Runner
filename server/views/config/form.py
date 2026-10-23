"""Config tab: form <-> models.ini binding, save/revert (split from server_panel.py)"""
import os
import re
import subprocess
from bench_panel import resolve_path
from datetime import datetime
from tkinter import filedialog
from tkinter import messagebox

from server.args import build_args, join_base, unquote
from server.constants import FALSE, GLOBAL, LEGACY_LOAD, TRUE
from server.ini_doc import parse_kv
from server.settings_store import write_setting
from server.views.config.spec import INT_KEYS


class ConfigFormMixin:
    """Config tab: form <-> models.ini binding, save/revert."""
    def _load_form(self):
        self._loading = True
        name = self.selected
        has = bool(name) and self.doc.has(name)
        d = self.doc.dict(name) if has else {}
        for key, var in self.fvars.items():
            var.set(d.get(key, ""))
        if not d.get("load-mode"):  # migrate legacy mlock / no-mmap checkboxes
            ml = "mlock" in d and (d["mlock"] == "" or d["mlock"].lower() in TRUE)
            nm = "no-mmap" in d and (d["no-mmap"] == "" or d["no-mmap"].lower() in TRUE)
            if ml or nm:
                self.fvars["load-mode"].set("mlock" if (ml and nm) else ("mmap+mlock" if ml else "none"))
        for key, var in self.flagvars.items():
            var.set(1 if key in d and (d[key].lower() in TRUE or d[key] == "") else 0)
        for key, (kind, var) in self.advvars.items():
            v = d.get(key)
            if v is None:
                var.set("")
                continue
            if kind in ("b", "f"):
                on = v == "" or v.lower() in TRUE
                off = v.lower() in FALSE
                var.set(("on" if on else ("off" if off else "")) if kind == "b" else ("true" if on else ""))
            else:
                var.set(v)
        mv = unquote(d.get("mcp", "")).lower()
        self.mcp_var.set("on" if mv and mv in TRUE else ("off" if mv and mv in FALSE else "default"))
        keep = []
        for ln in (self.doc.body(name) if has else []):
            kv = parse_kv(ln)
            if kv and (kv[0] in self.fvars or kv[0] == "mcp" or kv[0] in LEGACY_LOAD):
                continue
            if kv and kv[0] in self.advvars:
                continue
            if kv and kv[0] in self.flagvars and (kv[1].lower() in TRUE or kv[1] == ""):
                continue
            keep.append(ln)
        while keep and not keep[0].strip():
            keep.pop(0)
        while keep and not keep[-1].strip():
            keep.pop()
        self.extra.delete("1.0", "end")
        self.extra.insert("1.0", "\n".join(keep))
        self.extra.edit_reset()
        self.comment.delete("1.0", "end")
        self.comment.insert("1.0", "\n".join(self.doc.comment(name)) if has else "")
        self.comment.edit_reset()
        self._comment_orig = "\n".join(self._comment_lines())
        self._loading = False
        self.dirty = False
        self._after_change()

    def _comment_lines(self):
        out = []
        for ln in self.comment.get("1.0", "end").splitlines():
            s = ln.strip()
            if s:
                out.append(s if s.startswith("#") else "# " + s)
        return out

    def _on_comment(self):
        if not self._loading and "\n".join(self._comment_lines()) != self._comment_orig:
            self._on_change()

    def _form_lines(self):
        lines = []
        for key in self.fvars:
            v = self.fvars[key].get().strip()
            if v:
                lines.append(f"{key} = {v}")
        if self.mcp_var.get() in ("on", "off"):
            lines.append(f"mcp = {self.mcp_var.get()}")
        for key, (kind, var) in self.advvars.items():
            v = var.get().strip()
            if kind == "b":
                v = {"on": "true", "off": "false"}.get(v, "")
            elif kind == "f":
                v = "true" if v else ""
            if v:
                lines.append(f"{key} = {v}")
        for key, var in self.flagvars.items():
            if var.get():
                lines.append(f"{key} = true")
        extra = [ln.rstrip() for ln in self.extra.get("1.0", "end").rstrip("\n").splitlines()]
        return lines, extra

    def _form_dict(self):
        lines, extra = self._form_lines()
        d = {}
        for ln in lines + extra:
            kv = parse_kv(ln)
            if kv:
                d[kv[0]] = kv[1]
        return d

    def _on_change(self, *_):
        if self._loading:
            return
        self.dirty = True
        self._after_change()

    def _after_change(self):
        g = self.doc.dict(GLOBAL) if self.doc.has(GLOBAL) else {}
        for key, lbl in self.hints.items():
            if key == "mcp":
                base = {} if self.selected == GLOBAL else g
                lbl.config(text=f"\u21B3 default: {'on' if self.mcp_enabled(base) else 'off'}" if self.mcp_var.get() == "default" else "")
                continue
            v = self.fvars[key].get().strip() if key in self.fvars else ""
            lbl.config(text=f"\u21B3 global: {g[key]}" if (not v and key in g and self.selected != GLOBAL) else "")
        for key, lbl in self.adv_hints.items():
            cur = self.advvars[key][1].get().strip()
            lbl.config(text=f"\u21B3 global: {g[key]}" if (not cur and key in g and self.selected != GLOBAL) else "")
        self.dirty_lbl.config(text="\u25CF unsaved changes" if self.dirty else "")
        self.btn_save._bg = self.T["accent_bg"] if self.dirty else self.T["panel2"]
        self.btn_save.config(bg=self.btn_save._bg)
        self.preview.config(state="normal")
        self.preview.delete("1.0", "end")
        if self.selected in (None, GLOBAL):
            self.preview.insert("end", "Global defaults: every model inherits these unless its own section overrides the key.")
        else:
            merged = dict(g)
            merged.update(self._form_dict())
            exe = self.s["server_exe"] or "llama-server"
            real = resolve_path(self.s["server_exe"], self.app_dir)
            self.preview.insert("end", subprocess.list2cmdline([exe] + build_args(merged, self.base_dir(), self.s["extra_args"]) + self.mcp_args(real, merged)[0]))
        self.preview.config(state="disabled")

    def _browse(self, key):
        cur = unquote(self.fvars[key].get())
        init = os.path.dirname(join_base(cur, self.base_dir())) if cur else (self.s.get("gguf_dir") or self.base_dir())
        ft = ([("Jinja template", "*.jinja *.jinja2 *.txt"), ("All files", "*.*")] if key == "chat-template-file"
              else [("GGUF", "*.gguf"), ("All files", "*.*")])
        p = filedialog.askopenfilename(title=f"Select {key}", initialdir=init if os.path.isdir(init) else self.base_dir(),
                                       filetypes=ft)
        if p:
            self.fvars[key].set(p)
            self._remember_dir(p)

    def _remember_dir(self, p):
        self.s["gguf_dir"] = os.path.dirname(p)
        try:
            write_setting(self.settings_path, "state", {"gguf_dir": self.s["gguf_dir"]})
        except OSError:
            pass

    def _collect(self):
        lines, extra = self._form_lines()
        managed = set(self.fvars) | set(self.flagvars) | set(self.advvars) | {"mcp"}
        for ln in extra:
            kv = parse_kv(ln)
            if kv and kv[0] in managed:
                return None, f"'{kv[0]}' is set in the form above - remove it from Other parameters (or clear the form field)."
        for key, rx in INT_KEYS.items():
            v = self.fvars[key].get().strip()
            if v and not re.match(rx, v, re.I):
                return None, f"{key}: unexpected value '{v}'"
        return lines + ([""] if extra else []) + extra, None

    def save(self):
        name = self.selected
        if not name:
            return False
        lines, err = self._collect()
        if err:
            messagebox.showerror("Cannot save", err)
            return False
        self.doc.set_body(name, lines)
        self.doc.set_comment(name, self._comment_lines())
        if not self._write_ini():
            return False
        self._comment_orig = "\n".join(self._comment_lines())
        self.dirty = False
        self._after_change()
        self._refresh_header()
        for n in self.items:
            self._refresh_item(n)
        self.flash(f"Saved {datetime.now():%H:%M:%S}")
        if self.on_ini_changed:
            self.on_ini_changed(self.ini_path)
        return True

    def revert(self):
        self._load_form()
        self.flash("Reverted", self.T["warn"])
