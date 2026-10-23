import os, sys, traceback
import tkinter as tk
from tkinter import messagebox, ttk
import tkinter.font as tkfont

from bench_panel import BenchPanel
from server_panel import ServerPanel

VERSION = "v9.4.0"
APP_DIR = os.path.dirname(os.path.abspath(sys.executable if getattr(sys, "frozen", False) else __file__))
LOG = os.path.join(APP_DIR, "runner.log")

T = dict(
    bg="#0d1117", side="#010409", panel="#161b22", panel2="#1c2230", border="#30363d",
    text="#e6edf3", muted="#8b949e", accent="#58a6ff", accent_bg="#1f6feb",
    ok="#3fb950", warn="#d29922", err="#f85149", term="#0d1117", hover="#21262d", sel="#1f2a3d",
)
UI = "Segoe UI"
MONO = "Cascadia Code"


def dark_titlebar(win):
    try:
        import ctypes
        win.update_idletasks()
        hwnd = ctypes.windll.user32.GetParent(win.winfo_id())
        val = ctypes.c_int(1)
        for attr in (20, 19):
            ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, attr, ctypes.byref(val), 4)
    except Exception:
        pass


def pick_font(root, wanted, fallback):
    return wanted if wanted in tkfont.families(root) else fallback


class HoverButton(tk.Label):
    def __init__(self, master, text, command, bg, hover, fg=None, padx=14, pady=6, **kw):
        super().__init__(master, text=text, bg=bg, fg=fg or T["text"], padx=padx, pady=pady, cursor="hand2", **kw)
        self._bg, self._hover, self._cmd = bg, hover, command
        self.bind("<Enter>", lambda e: self.config(bg=self._hover))
        self.bind("<Leave>", lambda e: self.config(bg=self._bg))
        self.bind("<Button-1>", lambda e: self._cmd())


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(f"llama-server runner {VERSION}")
        self.geometry("1400x800")
        self.minsize(900, 600)
        self.configure(bg=T["bg"])
        global UI, MONO
        UI = pick_font(self, "Segoe UI", "TkDefaultFont")
        MONO = pick_font(self, "Cascadia Code", pick_font(self, "Consolas", "Courier New"))
        self.f_ui, self.f_bold, self.f_small = (UI, 10), (UI, 10, "bold"), (UI, 8)
        self.f_title, self.f_mono = (UI, 15, "bold"), (MONO, 10)
        self._style()
        self._layout()
        self._bind_keys()
        self.after(100, lambda: dark_titlebar(self))
        self.protocol("WM_DELETE_WINDOW", self.on_close)

    def _style(self):
        st = ttk.Style(self)
        st.theme_use("clam")
        for o in ("Vertical", "Horizontal"):
            st.configure(f"{o}.TScrollbar", background=T["panel2"], troughcolor=T["term"], bordercolor=T["term"],
                         arrowcolor=T["muted"], lightcolor=T["panel2"], darkcolor=T["panel2"], gripcount=0, relief="flat")
        st.configure("Vertical.TScrollbar", width=10)
        st.map("Vertical.TScrollbar", background=[("active", T["border"])])
        st.configure("TCombobox", fieldbackground=T["panel"], background=T["panel2"], foreground=T["text"],
                     arrowcolor=T["muted"], bordercolor=T["border"], lightcolor=T["panel"], darkcolor=T["panel"],
                     insertcolor=T["text"], selectbackground=T["panel"], selectforeground=T["text"])
        st.map("TCombobox", fieldbackground=[("readonly", T["panel"])], foreground=[("readonly", T["text"])],
               selectbackground=[("readonly", T["panel"])], selectforeground=[("readonly", T["text"])],
               bordercolor=[("focus", T["accent"])])
        self.option_add("*TCombobox*Listbox.background", T["panel"])
        self.option_add("*TCombobox*Listbox.foreground", T["text"])
        self.option_add("*TCombobox*Listbox.selectBackground", T["accent_bg"])
        self.option_add("*TCombobox*Listbox.selectForeground", "white")

    def _layout(self):
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)
        side = tk.Frame(self, bg=T["side"], width=280)
        side.grid(row=0, column=0, sticky="nsw")
        side.grid_propagate(False)
        side.pack_propagate(False)
        head = tk.Frame(side, bg=T["side"])
        head.pack(fill="x", padx=16, pady=(18, 4))
        tk.Label(head, text="\u26A1 llama-server", bg=T["side"], fg=T["text"], font=self.f_title).pack(anchor="w")

        fonts = dict(ui=self.f_ui, bold=self.f_bold, small=self.f_small, small_b=(UI, 8, "bold"),
                     mono=self.f_mono, mono_s=(MONO, 9), h=(UI, 13, "bold"))
        self.bench = BenchPanel(self, T, HoverButton, fonts, APP_DIR)
        self.srv = ServerPanel(self, T, HoverButton, fonts, APP_DIR, on_ini_changed=self.sync_bench, on_activate=self.show_servers)
        self.srv.grid(row=0, column=1, sticky="nsew")
        self.bench.grid(row=0, column=1, sticky="nsew")
        self.bench.grid_remove()

        foot = tk.Frame(side, bg=T["side"])
        foot.pack(fill="x", padx=14, pady=12, side="bottom")
        HoverButton(foot, "\uFF0B New from GGUF\u2026", self.srv.new_from_gguf, T["accent_bg"], "#388bfd", fg="white",
                    font=self.f_bold, anchor="w").pack(fill="x", pady=(0, 6))
        HoverButton(foot, "\U0001F9EA Benchmark", self.show_bench, T["panel"], T["hover"], font=self.f_ui, anchor="w").pack(fill="x", pady=(0, 6))
        HoverButton(foot, "\u21BB Reload models.ini  Ctrl+R", self.reload, T["panel"], T["hover"], font=self.f_ui, anchor="w").pack(fill="x")
        self.srv.build_sidebar(side)

    def _bind_keys(self):
        def srv(fn):
            def h(e=None):
                if self.srv.winfo_ismapped():
                    fn()
                    return "break"
            return h
        b = self.bind
        b("<F5>", srv(self.srv.toggle_start))
        b("<Shift-F5>", srv(self.srv.stop))
        b("<F6>", srv(self.srv.open_webui))
        for k in ("<Control-s>", "<Control-S>"):
            b(k, srv(self.srv.save))
        b("<Control-r>", lambda e: self.reload())
        b("<Control-f>", lambda e: (self.show_servers(), self.srv.focus_filter(), "break")[-1])
        b("<Control-l>", srv(self.srv.clear_log))
        b("<Control-N>", srv(self.srv.new_from_gguf))
        b("<Control-D>", srv(self.srv.duplicate))
        for i, n in enumerate(("console", "config", "settings"), 1):
            b(f"<Control-Key-{i}>", srv(lambda n=n: self.srv.show_tab(n)))
        b("<FocusIn>", self._focus_in)

    def _focus_in(self, e):
        if e.widget is self and self.srv.winfo_ismapped():
            self.srv.check_external()

    def reload(self):
        self.show_servers()
        if self.srv.dirty and not messagebox.askyesno("Unsaved changes", "Discard unsaved changes and reload models.ini?"):
            return
        self.srv.reload_ini()

    def sync_bench(self, path):
        try:
            self.bench.cfg["paths"]["models_ini"] = path
            self.bench.vars[("paths", "models_ini")].set(path)
        except Exception:
            pass

    def show_bench(self):
        self.srv.grid_remove()
        self.bench.reload_models()
        self.bench.grid()
        self.srv.deselect_visual()

    def show_servers(self):
        if self.bench.winfo_ismapped():
            self.bench.grid_remove()
            self.srv.grid()
            self.srv.sync_ini_from_settings()
            self.srv.select_visual()

    def report_callback_exception(self, exc, val, tb):
        msg = "".join(traceback.format_exception(exc, val, tb))
        try:
            with open(LOG, "a", encoding="utf-8") as f:
                f.write(msg + "\n")
        except Exception:
            pass
        try:
            self.srv.flash("internal error - see runner.log", T["err"])
        except Exception:
            pass

    def on_close(self):
        n = self.srv.running_count()
        if n and self.srv.s.get("stop_on_exit", "1") == "1":
            if not messagebox.askyesno("Server running", "A llama-server process is still running.\nStop it and exit?"):
                return
            self.srv.shutdown()
        if self.srv.dirty and not messagebox.askyesno("Unsaved changes", "Exit and discard unsaved config changes?"):
            return
        self.bench.stop()
        self.destroy()


if __name__ == "__main__":
    App().mainloop()
