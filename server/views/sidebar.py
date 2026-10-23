"""Sidebar: model list, filter, selection (split from server_panel.py)"""
import os
import re
import tkinter as tk
from tkinter import messagebox

from server.args import join_base, unquote
from server.constants import GLOBAL
from server.settings_store import write_setting
from server.widgets.model_item import ModelItem


class SidebarMixin:
    """Sidebar: model list, filter, selection."""
    def build_sidebar(self, side):
        T, F = self.T, self.F
        sbox = tk.Frame(side, bg=T["panel"], highlightthickness=1, highlightbackground=T["border"], highlightcolor=T["accent"])
        sbox.pack(fill="x", padx=14, pady=(12, 8))
        tk.Label(sbox, text="\u2315", bg=T["panel"], fg=T["muted"], font=F["ui"]).pack(side="left", padx=(8, 0))
        self.flt = tk.StringVar()
        self.flt.trace_add("write", lambda *a: self.render_list())
        self.flt_entry = tk.Entry(sbox, textvariable=self.flt, bg=T["panel"], fg=T["text"], insertbackground=T["text"],
                                  relief="flat", font=F["ui"])
        self.flt_entry.pack(side="left", fill="x", expand=True, padx=6, pady=6)
        self.flt_entry.bind("<Up>", lambda e: self._move(-1))
        self.flt_entry.bind("<Down>", lambda e: self._move(1))
        self.flt_entry.bind("<Return>", lambda e: self._move(0))
        self.flt_entry.bind("<Escape>", lambda e: self.flt.set(""))
        tk.Label(side, text="MODELS", bg=T["side"], fg=T["muted"], font=F["small_b"]).pack(anchor="w", padx=18, pady=(4, 2))
        self.src_lbl = tk.Label(side, text="", bg=T["side"], fg=T["muted"], font=F["small"], anchor="w", justify="left", wraplength=250)
        self.src_lbl.pack(fill="x", padx=16, pady=(4, 0), side="bottom")
        wrap = tk.Frame(side, bg=T["side"])
        wrap.pack(fill="both", expand=True)
        self.list_canvas = tk.Canvas(wrap, bg=T["side"], highlightthickness=0, bd=0)
        self.list_canvas.pack(fill="both", expand=True)
        self.list_frame = tk.Frame(self.list_canvas, bg=T["side"])
        self.list_win = self.list_canvas.create_window((0, 0), window=self.list_frame, anchor="nw")
        self.list_frame.bind("<Configure>", lambda e: self.list_canvas.configure(scrollregion=self.list_canvas.bbox("all")))
        self.list_canvas.bind("<Configure>", lambda e: self.list_canvas.itemconfig(self.list_win, width=e.width))
        self.list_canvas.bind_all("<MouseWheel>", self._wheel, add="+")
        self.menu = tk.Menu(self, tearoff=0, bg=T["panel"], fg=T["text"], activebackground=T["accent_bg"], activeforeground="white", bd=0)
        self.reload_ini()

    def _wheel(self, e):
        w = self.winfo_containing(e.x_root, e.y_root)
        if w is not None and (str(w).startswith(str(self.list_canvas)) or str(w).startswith(str(self.list_frame))):
            self.list_canvas.yview_scroll(int(-e.delta / 120), "units")

    def focus_filter(self):
        self.flt_entry.focus_set()
        self.flt_entry.select_range(0, "end")

    def _move(self, d):
        if not self.visible:
            return "break"
        i = self.visible.index(self.selected) if self.selected in self.visible else -1
        i = max(0, min(len(self.visible) - 1, i + d)) if (d or i >= 0) else 0
        self.select(self.visible[i])
        self._see(self.visible[i])
        return "break"

    def _see(self, name):
        it = self.items.get(name)
        if not it:
            return
        self.update_idletasks()
        total = max(1, self.list_frame.winfo_height())
        top, bot = self.list_canvas.yview()
        y0, y1 = it.winfo_y() / total, (it.winfo_y() + it.winfo_height()) / total
        if y0 < top:
            self.list_canvas.yview_moveto(y0)
        elif y1 > bot:
            self.list_canvas.yview_moveto(y1 - (bot - top))

    def render_list(self):
        for w in self.list_frame.winfo_children():
            w.destroy()
        self.items = {}
        flt = self.flt.get().strip().lower()
        names = ([GLOBAL] if not flt else []) + [n for n in self.model_names() if flt in n.lower()]
        self.visible = names
        for n in names:
            it = ModelItem(self.list_frame, self.T, n, "\u2605 Global defaults [*]" if n == GLOBAL else n, self.F, self.select, self._popup)
            it.pack(fill="x")
            it.set_selected(n == self.selected)
            self.items[n] = it
            self._refresh_item(n)
        if not self.model_names() and not flt:
            tk.Label(self.list_frame, text="No models yet.\nClick '+ New from GGUF' below.", bg=self.T["side"], fg=self.T["muted"],
                     font=self.F["small"], justify="left").pack(pady=14, padx=16, anchor="w")
        n = len(self.model_names())
        self.src_lbl.config(text=f"{n} models \u00B7 {self.ini_path}" + (" (not created yet)" if self.ini_mtime is None and not self.ini_err else ""),
                            fg=self.T["err"] if self.ini_err else self.T["muted"])

    def _model_state(self, name):
        r = self.runners.get(name)
        if r and (r.alive() or r.state in ("failed", "stopped", "waiting")):
            return r.state
        return "idle"

    def comment_tip(self, name):
        return "\n".join(re.sub(r"^\s*#\s?", "", l) for l in self.doc.comment(name)).strip()

    def _refresh_item(self, name):
        it = self.items.get(name)
        if not it:
            return
        it.set_tip(self.comment_tip(name))
        if name == GLOBAL:
            it.set_info("applies to every model", "idle")
            return
        m = self.merged(name)
        r = self.runners.get(name)
        mp = unquote(m.get("model", ""))
        warn = False
        if mp:
            full = join_base(mp, self.base_dir())
            base = os.path.basename(mp.replace("\\", "/"))
            warn = not os.path.isfile(full)
        else:
            base = m.get("hf") or m.get("hf-repo") or "no model set"
            warn = base == "no model set"
        if r and r.alive():
            sub = f"{'ready' if r.state == 'ready' else 'loading'} \u00B7 :{r.port}"
            warn = False
        elif r and r.state == "waiting":
            sub, warn = "waiting for previous model to stop\u2026", False
        else:
            sub = ("\u26A0 missing: " if warn and mp else "") + base
        it.set_info(sub, self._model_state(name), warn)

    def _popup(self, name, event):
        self.select(name)
        m = self.menu
        m.delete(0, "end")
        if name != GLOBAL:
            m.add_command(label="Start / Restart (F5)", command=self.toggle_start)
            m.add_command(label="Stop (Shift+F5)", command=self.stop)
            m.add_command(label="Open WebUI (F6)", command=self.open_webui)
            m.add_separator()
            m.add_command(label="Duplicate", command=self.duplicate)
            m.add_command(label="Rename\u2026", command=self.rename)
            m.add_command(label="Show model folder", command=self.show_folder)
            m.add_command(label="Delete", command=self.delete)
        else:
            m.add_command(label="Open models.ini", command=self.open_ini)
        m.tk_popup(event.x_root, event.y_root)

    def select(self, name):
        if name == self.selected:
            if self.on_activate:
                self.on_activate()
            return
        if self.dirty and not self._confirm_leave():
            return
        self.selected = name
        if name != GLOBAL:
            self.s["last_model"] = name
            try:
                write_setting(self.settings_path, "state", {"server_last_model": name})
            except OSError:
                pass
        for n, it in self.items.items():
            it.set_selected(n == name)
        self._load_form()
        self._refresh_header()
        self._render_console()
        if self.tab == "settings" or (name == GLOBAL and self.tab == "console"):
            self.show_tab("config")
        if self.on_activate:
            self.on_activate()

    def select_visual(self):
        for n, it in self.items.items():
            it.set_selected(n == self.selected)

    def deselect_visual(self):
        for it in self.items.values():
            it.set_selected(False)

    def _confirm_leave(self):
        r = messagebox.askyesnocancel("Unsaved changes", f"Save changes to [{self.selected}] first?")
        if r is None:
            return False
        if r:
            return self.save()
        self.dirty = False
        return True
