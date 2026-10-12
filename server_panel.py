# server_panel.py - llama-server runner view (models.ini presets -> llama-server processes)
import configparser, glob, os, queue, re, shlex, shutil, socket, subprocess, threading, time, urllib.request, webbrowser
from datetime import datetime
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from bench_panel import resolve_path

IS_WIN = os.name == "nt"
NO_WINDOW = 0x08000000 if IS_WIN else 0
NEW_GROUP = 0x00000200 if IS_WIN else 0
SETTINGS_FILE = "settings.ini"
GLOBAL = "*"
APP_ONLY = {"load-on-startup", "stop-timeout", "mcp"}  # keys never passed to llama-server
PATH_KEYS = {"model", "mmproj", "model-draft", "lora", "lora-scaled", "chat-template-file", "grammar-file",
             "json-schema-file", "slot-save-path", "media-path", "api-key-file", "ssl-key-file", "ssl-cert-file"}
MUST_JOIN = {"model", "mmproj", "model-draft"}
BOOL_FLAGS = {"jinja", "mlock", "no-mmap", "cont-batching", "no-cont-batching", "no-webui", "metrics", "slots",
              "no-slots", "kv-unified", "no-kv-offload", "swa-full", "verbose", "log-timestamps", "log-prefix",
              "no-warmup", "embedding", "embeddings", "reranking", "no-context-shift", "context-shift",
              "cpu-moe", "no-host", "no-op-offload", "check-tensors", "no-perf", "special", "mmap", "webui",
              "warmup", "kv-offload", "op-offload", "direct-io", "no-direct-io"}
NEGATABLE = {"mmap", "webui", "cont-batching", "warmup", "context-shift", "kv-offload", "slots", "op-offload",
             "perf", "direct-io"}
SHORT_FLAGS = {"ngl", "ctk", "ctv", "ncmoe", "cmoe", "ctkd", "ctvd", "ngld", "hfr", "hff", "hfd", "hfrd", "hfv", "hffv",
               "tb", "tbd", "kvu", "nkvo", "np", "dev", "devd", "lcs", "lcd", "sps", "ctxcp"}
TRUE = {"true", "yes", "enabled", "on", "1"}
FALSE = {"false", "no", "disabled", "off", "0"}
KV_TYPES = ["f32", "f16", "bf16", "q8_0", "q5_1", "q5_0", "q4_1", "q4_0", "iq4_nl"]

# (key, label, choices or None)
ROWS = [
    [("ctx-size", "Context (ctx-size)", ["4096", "8192", "16384", "32768", "65536", "131072", "262144"]),
     ("n-gpu-layers", "GPU layers (n-gpu-layers)", ["auto", "all", "99", "0"]),
     ("n-cpu-moe", "CPU MoE layers (n-cpu-moe)", None)],
    [("threads", "Threads", None),
     ("batch-size", "Batch (batch-size)", ["512", "1024", "2048", "4096"]),
     ("ubatch-size", "Micro-batch (ubatch-size)", ["128", "256", "512", "1024"])],
    [("flash-attn", "Flash attention", ["on", "off", "auto"]),
     ("cache-type-k", "K cache (cache-type-k)", KV_TYPES),
     ("cache-type-v", "V cache (cache-type-v)", KV_TYPES)],
    [("parallel", "Parallel slots", None),
     ("host", "Host", ["127.0.0.1", "0.0.0.0"]),
     ("port", "Port", None)],
]
PATH_FIELDS = [("model", "Model (.gguf)"), ("mmproj", "Multimodal projector (mmproj)")]
FLAG_FIELDS = [("jinja", "jinja"), ("mlock", "mlock"), ("no-mmap", "no-mmap"), ("no-webui", "no-webui"),
               ("metrics", "metrics")]
INT_KEYS = {"ctx-size": r"^\d+$", "n-cpu-moe": r"^\d+$", "threads": r"^-?\d+$", "batch-size": r"^\d+$",
            "ubatch-size": r"^\d+$", "parallel": r"^-?\d+$", "port": r"^\d+$",
            "n-gpu-layers": r"^(\d+|-1|auto|all)$"}
MCP_CHOICES = ["default", "on", "off"]

ERR_RE = re.compile(r"\b(error|failed|fatal|exception|out of memory|oom|cannot|unable)\b", re.I)
WARN_RE = re.compile(r"\bwarn(ing)?\b", re.I)
OK_RE = re.compile(r"server is listening|all slots are idle", re.I)
PP_RE = re.compile(r"prompt eval time\s*=.*?([\d.]+)\s+tokens per second", re.I)
TG_RE = re.compile(r"^\s*eval time\s*=.*?([\d.]+)\s+tokens per second", re.I)


# ---------------- pure logic ----------------
def unquote(v):
    v = (v or "").strip()
    if len(v) >= 2 and v[0] == v[-1] and v[0] in "\"'":
        v = v[1:-1]
    return os.path.expandvars(v)


def join_base(v, base, must=True):
    v = unquote(v)
    if not v or os.path.isabs(v):
        return v
    cand = os.path.normpath(os.path.join(base, v))
    return cand if (must or os.path.exists(cand)) else v


def build_args(merged, base, extra=""):
    args = []
    for raw_key, raw_val in merged.items():
        k = raw_key.strip().lstrip("-")
        if not k or k in APP_ONLY:
            continue
        v = unquote(raw_val)
        lv = v.lower()
        if v == "" and k not in BOOL_FLAGS:
            continue  # empty value (e.g. "mmproj =") means "not set"
        if k == "model":
            args += ["-m", join_base(v, base)]
            continue
        flag = ("-" if (len(k) <= 2 or k in SHORT_FLAGS) else "--") + k
        generic_bool = lv in ("true", "false", "yes", "no", "enabled", "disabled")
        if k in BOOL_FLAGS or generic_bool:
            if k in BOOL_FLAGS:
                on, off = (v == "" or lv in TRUE), lv in FALSE
            else:
                on, off = lv in ("true", "yes", "enabled"), lv in ("false", "no", "disabled")
            if on:
                args.append(flag)
            elif off:
                if k in NEGATABLE:
                    args.append("--no-" + k)
            else:
                args += [flag, v]
            continue
        if k in PATH_KEYS:
            v = join_base(v, base, k in MUST_JOIN)
        args += [flag, v]
    if extra.strip():
        for t in shlex.split(extra, posix=False):
            args.append(t[1:-1] if len(t) >= 2 and t[0] == t[-1] and t[0] in "\"'" else t)
    return args


def server_addr(merged):
    host = unquote(merged.get("host", "")) or "127.0.0.1"
    port = unquote(merged.get("port", "")) or "8080"
    return host, port


def browse_host(host):
    return "127.0.0.1" if host in ("0.0.0.0", "::", "") else host


def port_busy(port):
    try:
        with socket.create_connection(("127.0.0.1", int(port)), timeout=0.3):
            return True
    except Exception:
        return False


def open_url(url):
    ok = False
    try:
        ok = webbrowser.open(url)
    except Exception:
        pass
    if not ok and IS_WIN:
        try:
            os.startfile(url)
            ok = True
        except Exception:
            pass
    return ok


SEC_RE = re.compile(r"^\s*\[(.*?)\]\s*$")


def parse_kv(line):
    s = line.strip()
    if not s or s[0] in ";#":
        return None
    if "=" in s:
        k, v = s.split("=", 1)
        return k.strip(), v.strip()
    return s, ""


class IniDoc:
    # comment-preserving models.ini editor: sections keep their raw lines
    def __init__(self, text=""):
        if "\r\n" in text:
            self.nl = "\r\n"
        elif "\n" in text:
            self.nl = "\n"
        else:
            self.nl = "\r\n" if IS_WIN else "\n"
        self.pre, self.secs = [], []
        cur = self.pre
        for ln in text.splitlines():
            m = SEC_RE.match(ln)
            if m:
                cur = []
                self.secs.append([m.group(1).strip(), cur])
            else:
                cur.append(ln)

    def names(self):
        return [n for n, _ in self.secs]

    def has(self, name):
        return name in self.names()

    def _sec(self, name):
        for s in self.secs:
            if s[0] == name:
                return s
        return None

    def body(self, name):
        s = self._sec(name)
        return list(s[1]) if s else []

    def dict(self, name):
        d = {}
        for ln in self.body(name):
            kv = parse_kv(ln)
            if kv:
                d[kv[0]] = kv[1]
        return d

    def set_body(self, name, lines):
        lines = list(lines)
        while lines and not lines[-1].strip():
            lines.pop()
        s = self._sec(name)
        if s is None:
            return self.add(name, lines)
        if s is not self.secs[-1]:
            lines.append("")
        s[1][:] = lines

    def add(self, name, lines):
        lines = list(lines)
        while lines and not lines[-1].strip():
            lines.pop()
        if name == GLOBAL:
            self.secs.insert(0, [name, lines + ([""] if self.secs else [])])
            return
        if self.secs:
            prev = self.secs[-1][1]
            if prev and prev[-1].strip():
                prev.append("")
        elif self.pre and self.pre[-1].strip():
            self.pre.append("")
        self.secs.append([name, lines])

    def remove(self, name):
        s = self._sec(name)
        if s:
            self.secs.remove(s)
            if self.secs:
                last = self.secs[-1][1]
                while last and not last[-1].strip():
                    last.pop()

    def rename(self, old, new):
        s = self._sec(old)
        if s:
            s[0] = new

    def dump(self):
        out = list(self.pre)
        for name, body in self.secs:
            out.append(f"[{name}]")
            out += body
        return self.nl.join(out) + self.nl


DEFAULT_SRV = {"server_exe": "llama-server.exe", "extra_args": "", "open_browser": "0", "stop_on_exit": "1",
               "mcp_config": "mcp.json", "use_mcp": "0"}


def load_srv_settings(path):
    cp = configparser.ConfigParser(interpolation=None, strict=False)
    cp.optionxform = str
    if os.path.isfile(path):
        cp.read(path, encoding="utf-8-sig")
    s = dict(DEFAULT_SRV)
    for k in DEFAULT_SRV:
        if cp.has_option("server", k):
            s[k] = cp.get("server", k).strip()
    s["models_ini"] = cp.get("paths", "models_ini", fallback="models.ini").strip() or "models.ini"
    s["last_model"] = cp.get("state", "server_last_model", fallback="").strip()
    s["gguf_dir"] = cp.get("state", "gguf_dir", fallback="").strip()
    return s


def write_setting(path, section, kv):
    cp = configparser.ConfigParser(interpolation=None, strict=False)
    cp.optionxform = str
    if os.path.isfile(path):
        cp.read(path, encoding="utf-8-sig")
    if not cp.has_section(section):
        cp.add_section(section)
    for k, v in kv.items():
        cp.set(section, k, str(v))
    with open(path, "w", encoding="utf-8") as f:
        cp.write(f)


def ask_text(parent, T, fonts, title, prompt, initial=""):
    top = parent.winfo_toplevel()
    dlg = tk.Toplevel(top)
    dlg.title(title)
    dlg.configure(bg=T["bg"])
    dlg.transient(top)
    dlg.resizable(False, False)
    res = [None]
    tk.Label(dlg, text=prompt, bg=T["bg"], fg=T["text"], font=fonts["ui"], anchor="w").pack(fill="x", padx=18, pady=(16, 6))
    var = tk.StringVar(value=initial)
    ent = tk.Entry(dlg, textvariable=var, width=52, bg=T["panel"], fg=T["text"], insertbackground=T["text"], relief="flat",
                   font=fonts["ui"], highlightthickness=1, highlightbackground=T["border"], highlightcolor=T["accent"])
    ent.pack(fill="x", padx=18, ipady=5)
    bar = tk.Frame(dlg, bg=T["bg"])
    bar.pack(fill="x", padx=18, pady=14)

    def ok(_e=None):
        res[0] = var.get().strip()
        dlg.destroy()

    for text, cmd, bg, fg in (("OK", ok, T["accent_bg"], "white"), ("Cancel", dlg.destroy, T["panel2"], T["text"])):
        tk.Button(bar, text=text, command=cmd, bg=bg, fg=fg, relief="flat", font=fonts["bold"], padx=16, pady=3,
                  activebackground=T["hover"], activeforeground=T["text"], cursor="hand2").pack(side="right", padx=(6, 0))
    dlg.bind("<Return>", ok)
    dlg.bind("<Escape>", lambda e: dlg.destroy())
    dlg.update_idletasks()
    x = top.winfo_rootx() + (top.winfo_width() - dlg.winfo_width()) // 2
    y = top.winfo_rooty() + (top.winfo_height() - dlg.winfo_height()) // 3
    dlg.geometry(f"+{max(0, x)}+{max(0, y)}")
    dlg.grab_set()
    ent.focus_set()
    ent.select_range(0, "end")
    parent.wait_window(dlg)
    return res[0]


class Runner:
    def __init__(self, name):
        self.name = name
        self.proc = None
        self.lines = []
        self.state = "idle"
        self.started = None
        self.host, self.port = "127.0.0.1", "8080"
        self.pp = self.tg = ""
        self.stopping = False
        self.probing = False
        self.code = None

    def alive(self):
        return self.proc is not None and self.proc.poll() is None


class ModelItem(tk.Frame):
    DOT = {"idle": "border", "loading": "warn", "waiting": "warn", "ready": "ok", "failed": "err", "stopped": "warn"}

    def __init__(self, master, T, name, title, fonts, on_click, on_menu):
        super().__init__(master, bg=T["side"], cursor="hand2")
        self.T, self.name, self.selected, self.hover = T, name, False, False
        self.bar = tk.Frame(self, width=3, bg=T["side"])
        self.bar.pack(side="left", fill="y")
        self.dot = tk.Label(self, text="\u25CF", bg=T["side"], fg=T["border"], font=fonts["small"])
        self.dot.pack(side="left", padx=(8, 0))
        self.inner = tk.Frame(self, bg=T["side"])
        self.inner.pack(side="left", fill="x", expand=True, padx=(6, 8), pady=6)
        self.title = tk.Label(self.inner, text=title, bg=T["side"], fg=T["text"], font=fonts["ui"], anchor="w")
        self.title.pack(fill="x")
        self.sub = tk.Label(self.inner, text="", bg=T["side"], fg=T["muted"], font=fonts["small"], anchor="w")
        self.sub.pack(fill="x")
        self.parts = (self, self.dot, self.inner, self.title, self.sub)
        for w in self.parts + (self.bar,):
            w.bind("<Enter>", self._enter)
            w.bind("<Leave>", self._leave)
            w.bind("<Button-1>", lambda e: on_click(self.name))
            w.bind("<Button-3>", lambda e: on_menu(self.name, e))

    def _paint(self):
        T = self.T
        bg = T["sel"] if self.selected else (T["hover"] if self.hover else T["side"])
        for w in self.parts:
            w.config(bg=bg)
        self.bar.config(bg=T["accent"] if self.selected else bg)

    def _enter(self, _e):
        self.hover = True
        self._paint()

    def _leave(self, _e):
        self.hover = False
        self._paint()

    def set_selected(self, v):
        self.selected = v
        self._paint()

    def set_info(self, sub, state, warn=False):
        self.sub.config(text=sub, fg=self.T["err"] if warn else self.T["muted"])
        self.dot.config(fg=self.T[self.DOT.get(state, "border")])


class ServerPanel(tk.Frame):
    TABS = (("console", "\u25B6 Console  (Ctrl+1)"), ("config", "\u270E Config  (Ctrl+2)"), ("settings", "\u2699 Settings  (Ctrl+3)"))

    def __init__(self, master, T, Btn, fonts, app_dir, on_ini_changed=None, on_activate=None):
        super().__init__(master, bg=T["bg"])
        self.T, self.Btn, self.F, self.app_dir = T, Btn, fonts, app_dir
        self.on_ini_changed, self.on_activate = on_ini_changed, on_activate
        self.settings_path = os.path.join(app_dir, SETTINGS_FILE)
        self.s = load_srv_settings(self.settings_path)
        self.runners, self.items, self.visible = {}, {}, []
        self.selected = None
        self.dirty = False
        self._loading = False
        self.q = queue.Queue()
        self.restart = set()
        self.pending_start = None
        self.pending = []
        self.tab = "config"
        self.doc = IniDoc()
        self.ini_path, self.ini_mtime, self.ini_err = "", None, None
        self.fvars, self.hints, self.flagvars, self.svars = {}, {}, {}, {}
        self.mcp_var = tk.StringVar(value="default")
        self._flash_id = None
        self._build()
        self.after(40, self._pump)
        self.after(1000, self._tick)

    # ---------- helpers ----------
    def _entry(self, parent, var, **kw):
        T = self.T
        return tk.Entry(parent, textvariable=var, bg=T["panel"], fg=T["text"], insertbackground=T["text"], relief="flat",
                        font=self.F["ui"], highlightthickness=1, highlightbackground=T["border"],
                        highlightcolor=T["accent"], **kw)

    def _combo(self, parent, var, values, **kw):
        return ttk.Combobox(parent, textvariable=var, values=values, font=self.F["ui"], **kw)

    def mcp_enabled(self, merged):
        # per-model 'mcp = on/off' (or inherited from [*]) wins over the global Settings checkbox
        v = unquote(merged.get("mcp", "")).lower()
        if v and v in TRUE:
            return True
        if v and v in FALSE:
            return False
        return self.s.get("use_mcp") == "1"

    def mcp_args(self, exe, merged):
        # returns (args, error); path is tried against the app folder, then the llama-server folder
        if not self.mcp_enabled(merged):
            return [], None
        raw = unquote(self.s.get("mcp_config", ""))
        if not raw:
            return [], "MCP is enabled but no config path is set (Settings tab)."
        cands = [raw] if os.path.isabs(raw) else [os.path.normpath(os.path.join(self.app_dir, raw)),
                                                  os.path.normpath(os.path.join(os.path.dirname(exe), raw))]
        for c in cands:
            if os.path.isfile(c):
                return ["--mcp-servers-config", c], None
        return ["--mcp-servers-config", cands[0]], "MCP config not found: " + " | ".join(cands)

    def base_dir(self):
        return os.path.dirname(os.path.abspath(self.ini_path)) if self.ini_path else self.app_dir

    def model_names(self):
        return [n for n in self.doc.names() if n != GLOBAL]

    def merged(self, name):
        g = self.doc.dict(GLOBAL) if self.doc.has(GLOBAL) else {}
        m = dict(g)
        if name and name != GLOBAL:
            m.update(self.doc.dict(name))
        return m

    def runner(self, name):
        if name not in self.runners:
            self.runners[name] = Runner(name)
        return self.runners[name]

    def running_count(self):
        return sum(1 for r in self.runners.values() if r.alive())

    def flash(self, text, color=None):
        self.flash_lbl.config(text=text, fg=color or self.T["ok"])
        if self._flash_id:
            self.after_cancel(self._flash_id)
        self._flash_id = self.after(4500, lambda: self.flash_lbl.config(text=""))

    # ---------- build main area ----------
    def _build(self):
        T, F = self.T, self.F
        self.grid_rowconfigure(2, weight=1)
        self.grid_columnconfigure(0, weight=1)

        head = tk.Frame(self, bg=T["bg"])
        head.grid(row=0, column=0, sticky="ew", padx=18, pady=(14, 6))

        right = tk.Frame(head, bg=T["bg"])
        right.pack(side="right")
        
        left = tk.Frame(head, bg=T["bg"])
        left.pack(side="left", fill="x", expand=True)
        self.h_title = tk.Label(left, text="No model selected", bg=T["bg"], fg=T["text"], font=F["h"], anchor="w")
        self.h_title.pack(fill="x")
        self.h_sub = tk.Label(left, text="", bg=T["bg"], fg=T["muted"], font=F["small"], anchor="w")
        self.h_sub.pack(fill="x")

        self.perf = tk.Label(right, text="", bg=T["bg"], fg=T["muted"], font=F["mono_s"])
        self.perf.pack(side="left", padx=(0, 10))
        self.chip = tk.Label(right, text="\u25CF Idle", bg=T["panel2"], fg=T["muted"], font=F["bold"], padx=12, pady=4)
        self.chip.pack(side="left", padx=(0, 10))
        self.btn_start = self.Btn(right, "\u25B6 Start  F5", self.toggle_start, T["accent_bg"], "#388bfd", fg="white", font=F["bold"])
        self.btn_start.pack(side="left", padx=3)
        self.Btn(right, "\u25A0 Stop", self.stop, T["panel2"], "#3b1d1f", fg=T["err"], font=F["bold"]).pack(side="left", padx=3)
        self.Btn(right, "\U0001F310 WebUI", self.open_webui, T["panel2"], T["hover"], font=F["bold"]).pack(side="left", padx=3)

        tabs = tk.Frame(self, bg=T["bg"])
        tabs.grid(row=1, column=0, sticky="ew", padx=18, pady=(0, 8))
        self.tab_btns = {}
        for name, text in self.TABS:
            b = self.Btn(tabs, text, lambda n=name: self.show_tab(n), T["panel2"], T["hover"], font=F["ui"])
            b.pack(side="left", padx=(0, 6))
            self.tab_btns[name] = b
        self.flash_lbl = tk.Label(tabs, text="", bg=T["bg"], fg=T["ok"], font=F["small_b"])
        self.flash_lbl.pack(side="right")

        self.pages = {"console": self._build_console(), "config": self._build_config(), "settings": self._build_settings()}
        self.show_tab("config")

    def show_tab(self, name):
        if name == "console" and self.selected == GLOBAL:
            name = "config"
        self.tab = name
        for n, p in self.pages.items():
            p.grid_remove()
            active = n == name
            b = self.tab_btns[n]
            b._bg = self.T["accent_bg"] if active else self.T["panel2"]
            b.config(bg=b._bg, fg="white" if active else self.T["text"])
        self.pages[name].grid(row=2, column=0, sticky="nsew")
        if name == "console":
            self.text.focus_set()

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

    def _build_config(self):
        T, F = self.T, self.F
        page = tk.Frame(self, bg=T["bg"])
        page.grid_rowconfigure(2, weight=1)
        page.grid_columnconfigure(0, weight=1)
        card = tk.Frame(page, bg=T["panel"], highlightthickness=1, highlightbackground=T["border"])
        card.grid(row=0, column=0, sticky="ew", padx=18)
        card.grid_columnconfigure(0, weight=1)

        def cell_header(parent, key, label):
            hd = tk.Frame(parent, bg=T["panel"])
            hd.pack(fill="x")
            tk.Label(hd, text=label, bg=T["panel"], fg=T["muted"], font=F["small"], anchor="w").pack(side="left")
            hint = tk.Label(hd, text="", bg=T["panel"], fg=T["warn"], font=F["small"], anchor="e")
            hint.pack(side="right")
            self.hints[key] = hint

        for key, label in PATH_FIELDS:
            row = tk.Frame(card, bg=T["panel"])
            row.pack(fill="x", padx=12, pady=(10, 0))
            cell_header(row, key, label)
            line = tk.Frame(row, bg=T["panel"])
            line.pack(fill="x")
            var = tk.StringVar()
            self.fvars[key] = var
            var.trace_add("write", self._on_change)
            self._entry(line, var).pack(side="left", fill="x", expand=True, ipady=4)
            self.Btn(line, "\u2026", lambda k=key: self._browse(k), T["panel2"], T["hover"], font=F["ui"], padx=10, pady=3).pack(side="left", padx=(6, 0))
        grid = tk.Frame(card, bg=T["panel"])
        grid.pack(fill="x", padx=12, pady=(8, 0))
        for r, row in enumerate(ROWS):
            for c, (key, label, choices) in enumerate(row):
                grid.grid_columnconfigure(c, weight=1, uniform="f")
                cell = tk.Frame(grid, bg=T["panel"])
                cell.grid(row=r, column=c, sticky="ew", padx=(0 if c == 0 else 8, 0), pady=(0, 6))
                cell_header(cell, key, label)
                var = tk.StringVar()
                self.fvars[key] = var
                var.trace_add("write", self._on_change)
                w = self._combo(cell, var, choices) if choices else self._entry(cell, var)
                w.pack(fill="x", ipady=2 if choices else 3)
        # MCP override + flags
        fl = tk.Frame(card, bg=T["panel"])
        fl.pack(fill="x", padx=12, pady=(2, 10))
        tk.Label(fl, text="MCP", bg=T["panel"], fg=T["muted"], font=F["small"]).pack(side="left", padx=(0, 6))
        self.mcp_var.trace_add("write", self._on_change)
        self._combo(fl, self.mcp_var, MCP_CHOICES, width=9, state="readonly").pack(side="left")
        hint = tk.Label(fl, text="", bg=T["panel"], fg=T["warn"], font=F["small"])
        hint.pack(side="left", padx=(6, 22))
        self.hints["mcp"] = hint
        for key, label in FLAG_FIELDS:
            var = tk.IntVar()
            self.flagvars[key] = var
            var.trace_add("write", self._on_change)
            tk.Checkbutton(fl, text=label, variable=var, bg=T["panel"], fg=T["text"], selectcolor=T["panel2"],
                           activebackground=T["panel"], activeforeground=T["text"], font=F["ui"], bd=0,
                           highlightthickness=0, cursor="hand2").pack(side="left", padx=(0, 16))

        tk.Label(page, text="OTHER PARAMETERS  \u00B7  one 'key = value' per line, flags without dashes (e.g. temp = 0.7, cache-reuse = 256). ; or # starts a comment",
                 bg=T["bg"], fg=T["muted"], font=F["small_b"], anchor="w").grid(row=1, column=0, sticky="ew", padx=18, pady=(10, 4))
        ex = tk.Frame(page, bg=T["term"], highlightthickness=1, highlightbackground=T["border"])
        ex.grid(row=2, column=0, sticky="nsew", padx=18)
        ex.grid_rowconfigure(0, weight=1)
        ex.grid_columnconfigure(0, weight=1)
        self.extra = tk.Text(ex, bg=T["term"], fg=T["text"], insertbackground=T["text"], font=F["mono"], wrap="none",
                             relief="flat", bd=0, padx=12, pady=8, height=6, undo=True, selectbackground="#264f78")
        esy = ttk.Scrollbar(ex, orient="vertical", command=self.extra.yview)
        self.extra.config(yscrollcommand=esy.set)
        self.extra.grid(row=0, column=0, sticky="nsew")
        esy.grid(row=0, column=1, sticky="ns")
        for ev in ("<KeyRelease>", "<<Paste>>", "<<Cut>>"):
            self.extra.bind(ev, lambda e: self.after(1, self._on_change))

        tk.Label(page, text="COMMAND (with global [*] defaults applied)", bg=T["bg"], fg=T["muted"], font=F["small_b"],
                 anchor="w").grid(row=3, column=0, sticky="ew", padx=18, pady=(10, 4))
        pv = tk.Frame(page, bg=T["panel"], highlightthickness=1, highlightbackground=T["border"])
        pv.grid(row=4, column=0, sticky="ew", padx=18)
        self.preview = tk.Text(pv, bg=T["panel"], fg=T["muted"], font=F["mono_s"], wrap="word", relief="flat", bd=0,
                               padx=10, pady=6, height=4, state="disabled", selectbackground="#264f78")
        self.preview.pack(fill="x")

        bar = tk.Frame(page, bg=T["bg"])
        bar.grid(row=5, column=0, sticky="ew", padx=18, pady=10)
        self.btn_save = self.Btn(bar, "\U0001F4BE Save  Ctrl+S", self.save, T["accent_bg"], "#388bfd", fg="white", font=F["bold"])
        self.btn_save.pack(side="left")
        for text, cmd in (("\u21BA Revert", self.revert), ("\u2750 Duplicate", self.duplicate), ("\u270E Rename", self.rename),
                          ("\U0001F5D1 Delete", self.delete), ("\U0001F4DD Open models.ini", self.open_ini)):
            self.Btn(bar, text, cmd, T["panel2"], T["hover"], font=F["ui"]).pack(side="left", padx=(6, 0))
        self.dirty_lbl = tk.Label(bar, text="", bg=T["bg"], fg=T["warn"], font=F["bold"])
        self.dirty_lbl.pack(side="right")
        return page

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

    # ---------- sidebar ----------
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

    def _refresh_item(self, name):
        it = self.items.get(name)
        if not it:
            return
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

    # ---------- models.ini ----------
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

    # ---------- selection / form ----------
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

    def _load_form(self):
        self._loading = True
        name = self.selected
        has = bool(name) and self.doc.has(name)
        d = self.doc.dict(name) if has else {}
        for key, var in self.fvars.items():
            var.set(d.get(key, ""))
        for key, var in self.flagvars.items():
            var.set(1 if key in d and (d[key].lower() in TRUE or d[key] == "") else 0)
        mv = unquote(d.get("mcp", "")).lower()
        self.mcp_var.set("on" if mv and mv in TRUE else ("off" if mv and mv in FALSE else "default"))
        keep = []
        for ln in (self.doc.body(name) if has else []):
            kv = parse_kv(ln)
            if kv and (kv[0] in self.fvars or kv[0] == "mcp"):
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
        self._loading = False
        self.dirty = False
        self._after_change()

    def _form_lines(self):
        lines = []
        for key in self.fvars:
            v = self.fvars[key].get().strip()
            if v:
                lines.append(f"{key} = {v}")
        if self.mcp_var.get() in ("on", "off"):
            lines.append(f"mcp = {self.mcp_var.get()}")
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
        p = filedialog.askopenfilename(title=f"Select {key}", initialdir=init if os.path.isdir(init) else self.base_dir(),
                                       filetypes=[("GGUF", "*.gguf"), ("All files", "*.*")])
        if p:
            self.fvars[key].set(p)
            self._remember_dir(p)

    def _remember_dir(self, p):
        self.s["gguf_dir"] = os.path.dirname(p)
        try:
            write_setting(self.settings_path, "state", {"gguf_dir": self.s["gguf_dir"]})
        except OSError:
            pass

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

    def _tick(self):
        try:
            self._set_chip()
            for r in self.runners.values():
                if r.alive() and r.state == "loading" and not r.probing:
                    r.probing = True
                    threading.Thread(target=self._probe, args=(r, r.proc, r.host, r.port), daemon=True).start()
        finally:
            self.after(1000, self._tick)

    def _probe(self, r, proc, host, port):
        ok = False
        try:
            with urllib.request.urlopen(f"http://{browse_host(host)}:{port}/health", timeout=1.5) as resp:
                ok = resp.status == 200
        except Exception:
            pass
        r.probing = False
        if ok:
            self.q.put((r.name, proc, "ready", None))

    # ---------- editing actions ----------
    def _collect(self):
        lines, extra = self._form_lines()
        managed = set(self.fvars) | set(self.flagvars) | {"mcp"}
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
        if not self._write_ini():
            return False
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
        self.doc.add(new, [ln for ln in self.doc.body(name)])
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

    # ---------- settings ----------
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

    # ---------- console ----------
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

    # ---------- process control ----------
    def toggle_start(self):
        name = self.selected
        if not name or name == GLOBAL:
            messagebox.showinfo("Pick a model", "Select a model section first (the global [*] block is not startable).")
            return
        if self.runner(name).alive():
            self.restart.add(name)
            self.stop(name)
        else:
            self.start(name)

    def _fail(self, name, msg):
        self._log(name, msg + "\n", "err")
        self.runner(name).state = "failed"
        self._refresh_item(name)
        if name == self.selected:
            self.show_tab("console")
            self._flush()
            self._set_chip()

    def start(self, name):
        r = self.runner(name)
        if r.alive():
            return
        if self.dirty and name == self.selected and not self.save():
            return
        merged = self.merged(name)
        if r.lines and r.state != "waiting":
            r.lines.append(("\n", None))
        exe = resolve_path(self.s["server_exe"], self.app_dir)
        if not os.path.isfile(exe):
            self._fail(name, f"llama-server not found: {exe}\nSet its path in the Settings tab.")
            if name == self.selected:
                self.show_tab("settings")
            return
        mp = unquote(merged.get("model", ""))
        if mp:
            full = join_base(mp, self.base_dir())
            if not os.path.isfile(full):
                self._fail(name, f"Model file not found: {full}")
                return
        elif not any(k in merged for k in ("hf", "hf-repo", "model-url", "hf-file")):
            self._fail(name, f"[{name}] has no 'model' (or hf) entry.")
            return
        mcp, mcp_err = self.mcp_args(exe, merged)
        if mcp_err:
            self._fail(name, mcp_err + "\nFix the path in Settings, or set this model's MCP to 'off'.")
            return
        # one model at a time: stop whatever else is running, then start this one when it has exited
        others = [o for o, rr in self.runners.items() if o != name and rr.alive()]
        if others:
            self.pending_start = name
            r.state = "waiting"
            self._log(name, f"[stopping {', '.join('[' + o + ']' for o in others)} first...]\n", "info")
            for o in others:
                self.stop(o)
            self._refresh_item(name)
            if name == self.selected:
                self.show_tab("console")
                self._flush()
                self._set_chip()
            return
        host, port = server_addr(merged)
        if port_busy(port) and not messagebox.askyesno("Port in use", f"Something is already listening on port {port}.\nStart anyway?"):
            r.state = "idle"
            self._refresh_item(name)
            return
        cmd = [exe] + build_args(merged, self.base_dir(), self.s["extra_args"]) + mcp
        r.state, r.started, r.host, r.port = "loading", time.time(), host, port
        r.pp = r.tg = ""
        r.stopping, r.code, r.probing = False, None, False
        self._log(name, f"\u276F {subprocess.list2cmdline(cmd)}\n", "cmd")
        try:
            r.proc = subprocess.Popen(cmd, cwd=os.path.dirname(exe) or None, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                      stdin=subprocess.DEVNULL, creationflags=NO_WINDOW | NEW_GROUP, bufsize=0)
        except Exception as e:
            r.proc = None
            self._fail(name, f"Cannot start llama-server: {e}")
            return
        threading.Thread(target=self._reader, args=(name, r.proc), daemon=True).start()
        self._refresh_item(name)
        if name == self.selected:
            self.show_tab("console")
            self._flush()
            self._set_chip()

    def _reader(self, name, proc):
        try:
            for raw in iter(proc.stdout.readline, b""):
                self.q.put((name, proc, "log", raw.decode("utf-8", "replace").rstrip("\r\n")))
        except Exception:
            pass
        self.q.put((name, proc, "exit", proc.wait()))

    @staticmethod
    def _kill(proc):
        try:
            if IS_WIN:
                subprocess.run(["taskkill", "/PID", str(proc.pid), "/T", "/F"], creationflags=NO_WINDOW, capture_output=True)
            else:
                proc.terminate()
        except Exception:
            pass

    def stop(self, name=None):
        name = name or self.selected
        r = self.runners.get(name)
        if not r:
            return
        if r.state == "waiting" and not r.alive():
            self.pending_start = None
            r.state = "idle"
            self._log(name, "[start cancelled]\n", "info")
            self._refresh_item(name)
            self._set_chip()
            return
        if not r.alive():
            return
        r.stopping = True
        self._log(name, "[stopping...]\n", "info")
        threading.Thread(target=self._kill, args=(r.proc,), daemon=True).start()

    def shutdown(self):
        for r in self.runners.values():
            if r.alive():
                self._kill(r.proc)

    def open_webui(self):
        name = self.selected
        if not name or name == GLOBAL:
            return
        r = self.runners.get(name)
        host, port = (r.host, r.port) if r and r.alive() else server_addr(self.merged(name))
        open_url(f"http://{browse_host(host)}:{port}")

    def _mark_ready(self, r):
        if r.state != "loading":
            return
        r.state = "ready"
        self._refresh_item(r.name)
        if self.s.get("open_browser") == "1":
            url = f"http://{browse_host(r.host)}:{r.port}"
            ok = open_url(url)
            self._log(r.name, f"[ready - opening {url} in the browser{'' if ok else ' FAILED, open it manually'}]\n", "ok" if ok else "err")

    def _on_line(self, r, line):
        tag = self._classify(line)
        self._log(r.name, line + "\n", tag)
        if r.state == "loading" and OK_RE.search(line):
            self._mark_ready(r)
        m = PP_RE.search(line)
        if m:
            r.pp = f"{float(m.group(1)):.0f}"
        m = TG_RE.search(line)
        if m:
            r.tg = f"{float(m.group(1)):.1f}"

    def _on_exit(self, r, code):
        r.code = code
        if r.stopping:
            r.state = "stopped"
        else:
            r.state = "done" if code == 0 else "failed"
        self._log(r.name, f"\n[exit code {code}]\n", "ok" if code == 0 or r.stopping else "err")
        self._refresh_item(r.name)
        if r.name in self.restart:
            self.restart.discard(r.name)
            self.after(150, lambda n=r.name: self.start(n))
        elif self.pending_start and not any(x.alive() for x in self.runners.values()):
            n, self.pending_start = self.pending_start, None
            self.after(150, lambda n=n: self.start(n))

    def _pump(self):
        try:
            for _ in range(600):
                name, proc, kind, data = self.q.get_nowait()
                r = self.runners.get(name)
                if r is None or r.proc is not proc:
                    continue
                if kind == "log":
                    self._on_line(r, data)
                elif kind == "ready":
                    self._mark_ready(r)
                else:
                    self._on_exit(r, data)
        except queue.Empty:
            pass
        finally:
            self._flush()
            self.after(40, self._pump)
