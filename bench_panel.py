# bench_panel.py - in-app llama-bench menu for launcher.py
import configparser, glob, os, queue, re, shlex, shutil, subprocess, threading
from datetime import datetime
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

NO_WINDOW = 0x08000000
SETTINGS_FILE = "settings.ini"

# (section, key, default, label, hint, kind)
GROUPS = [
    ("Paths", [
        ("paths", "models_ini", "models.ini", "Models config (models.ini)", "full path, or relative to the launcher folder; if missing, models*.ini next to the launcher is used", "file"),
        ("paths", "bench_exe", "llama-bench.exe", "llama-bench executable", "relative paths are resolved against the launcher folder", "file"),
        ("paths", "output_dir", "bench-results", "Report folder", "Markdown reports are saved here", "dir"),
    ]),
    ("Base parameters  (comma list = llama-bench tests every combination; blank = take from models.ini)", [
        ("bench", "threads", "8", "Threads  (-t)", "e.g. 8,9,10", "text"),
        ("bench", "n-gpu-layers", "99", "GPU layers  (-ngl)", "", "text"),
        ("bench", "n-cpu-moe", "", "CPU MoE layers  (-ncmoe)", "e.g. 20,30,40 - blank = model's n-cpu-moe", "text"),
        ("bench", "fa", "on", "Flash attention  (-fa)", "on / off / 0 / 1 / auto, lists allowed", "text"),
        ("bench", "cache-type-k", "q8_0", "K cache type  (-ctk)", "e.g. q8_0,q4_0,f16", "text"),
        ("bench", "cache-type-v", "q8_0", "V cache type  (-ctv)", "e.g. q8_0,q4_0,f16", "text"),
        ("bench", "batch-size", "512", "Batch  (-b)", "", "text"),
        ("bench", "ubatch-size", "128", "Micro-batch  (-ub)", "", "text"),
        ("bench", "n-prompt", "512", "Prompt tokens  (-p)", "", "text"),
        ("bench", "n-gen", "128", "Generated tokens  (-n)", "", "text"),
        ("bench", "repeats", "3", "Repeats  (-r)", "", "text"),
        ("bench", "extra-args", "", "Extra llama-bench args", "raw, appended as-is (e.g. --no-warmup)", "text"),
        ("bench", "show-diagnostics", "0", "Show stderr while running", "1 = show, 0 = only on failure / in report", "text"),
    ]),
    ("Sweep lists  (used by the sweep tests)", [
        ("sweeps", "batch", "512,1024,2048", "Batch sweep: -b values", "", "text"),
        ("sweeps", "ubatch", "128,256,512", "Batch sweep: -ub values", "values above the batch size are skipped", "text"),
        ("sweeps", "kv", "q8_0:q8_0,q8_0:q4_0,q4_0:q8_0,q4_0:q4_0", "KV sweep: K:V pairs", "comma-separated pairs, K:V", "text"),
        ("sweeps", "threads", "4,6,8,12,16", "Thread sweep: -t values", "", "text"),
        ("sweeps", "moe", "20,28,30", "MoE sweep: -ncmoe values", "combined with the base Threads list", "text"),
    ]),
]

FLAGS = [("threads", "-t"), ("n-gpu-layers", "-ngl"), ("n-cpu-moe", "-ncmoe"), ("fa", "-fa"),
         ("cache-type-k", "-ctk"), ("cache-type-v", "-ctv"), ("batch-size", "-b"),
         ("ubatch-size", "-ub"), ("n-prompt", "-p"), ("n-gen", "-n"), ("repeats", "-r")]
INHERIT = {k for k, _ in FLAGS[:8]}
NUM_LIST = re.compile(r"^\d+(,\d+)*$")
FA_OK = {"on", "off", "0", "1", "auto"}

MODES = [
    ("baseline", "Quick baseline", "One run with the base settings"),
    ("batch", "Batch / ubatch sweep", "Sweep lists: batch x ubatch"),
    ("kv", "KV-cache sweep", "Sweep list: K:V cache pairs"),
    ("threads", "CPU thread sweep", "Sweep list: threads"),
    ("moe", "CPU-MoE sweep", "Sweep list: -ncmoe x base threads"),
    ("all", "Run all tests", "Baseline + all four sweeps"),
]


# ---------------- pure logic ----------------
def default_cfg():
    cfg = {}
    for _, fields in GROUPS:
        for sec, key, default, *_ in fields:
            cfg.setdefault(sec, {})[key] = default
    return cfg


def load_settings(path):
    cfg = default_cfg()
    cp = configparser.ConfigParser(interpolation=None, strict=False)
    cp.optionxform = str
    if os.path.isfile(path):
        cp.read(path, encoding="utf-8-sig")
        for sec in cfg:
            if cp.has_section(sec):
                for key in cfg[sec]:
                    if cp.has_option(sec, key):
                        cfg[sec][key] = cp.get(sec, key).strip()
        if cp.has_section("state"):
            cfg["state"] = dict(cp.items("state"))
    cfg.setdefault("state", {})
    return cfg


def save_settings(path, cfg):
    cp = configparser.ConfigParser(interpolation=None, strict=False)
    cp.optionxform = str
    if os.path.isfile(path):
        cp.read(path, encoding="utf-8-sig")
    for sec, kv in cfg.items():
        if not cp.has_section(sec):
            cp.add_section(sec)
        for k, v in kv.items():
            cp.set(sec, k, str(v))
    with open(path, "w", encoding="utf-8") as f:
        cp.write(f)


def norm(v):
    return re.sub(r"\s+", "", v or "")


def validate(cfg):
    errs, b, s = [], cfg["bench"], cfg["sweeps"]
    for key in ("threads", "n-gpu-layers", "n-cpu-moe", "batch-size", "ubatch-size", "n-prompt", "n-gen", "repeats"):
        v = norm(b.get(key))
        if v and not NUM_LIST.match(v):
            errs.append(f"{key}: use whole numbers, comma separated (got '{b.get(key)}')")
    v = norm(b.get("fa"))
    if v and any(t.lower() not in FA_OK for t in v.split(",")):
        errs.append("fa: allowed values are on, off, 0, 1, auto")
    for key in ("batch", "ubatch", "threads", "moe"):
        v = norm(s.get(key))
        if v and not NUM_LIST.match(v):
            errs.append(f"sweep {key}: whole numbers, comma separated")
    kv = norm(s.get("kv"))
    if kv and any(p.count(":") != 1 or not all(p.split(":")) for p in kv.split(",")):
        errs.append("sweep kv: use K:V pairs like q8_0:q4_0,q4_0:q4_0")
    try:
        shlex.split(b.get("extra-args", ""))
    except ValueError as e:
        errs.append(f"extra-args: {e}")
    return errs


def resolve_path(p, base):
    p = os.path.expandvars((p or "").strip().strip('"'))
    if not p:
        return ""
    if os.path.isabs(p):
        return os.path.normpath(p)
    cand = os.path.normpath(os.path.join(base, p))
    if os.path.exists(cand):
        return cand
    return shutil.which(p) or cand


def load_models(path):
    cp = configparser.ConfigParser(interpolation=None, strict=False, delimiters=("=",), allow_no_value=True)
    cp.optionxform = str
    with open(path, encoding="utf-8-sig") as f:
        cp.read_string(f.read())
    base = os.path.dirname(os.path.abspath(path))
    glob_opts = dict(cp.items("*")) if cp.has_section("*") else {}
    models = {}
    for sec in cp.sections():
        if sec == "*":
            continue
        opts = {k: (v or "").strip() for k, v in cp.items(sec)}
        mp = opts.get("model", "")
        if not mp:
            continue
        mp = os.path.expandvars(mp.strip('"'))
        opts["model"] = os.path.normpath(mp if os.path.isabs(mp) else os.path.join(base, mp))
        merged = {k: (v or "").strip() for k, v in glob_opts.items()}
        merged.update(opts)
        models[sec] = merged
    return glob_opts, models


def effective(cfg, model_opts):
    vals = {}
    for key, _ in FLAGS:
        v = (cfg["bench"].get(key) or "").strip()
        if not v and key in INHERIT:
            v = (model_opts.get(key) or "").strip()
        vals[key] = norm(v)
    return vals


def build_args(model_path, vals, extra, over=None):
    over = over or {}
    args = ["-m", model_path]
    for key, flag in FLAGS:
        v = norm(over[key]) if key in over else vals.get(key, "")
        if v:
            args += [flag, v]
    return args + (shlex.split(extra) if extra.strip() else [])


def build_plan(mode, cfg, model_opts):
    vals = effective(cfg, model_opts)
    extra = cfg["bench"].get("extra-args", "")
    sw, mp = cfg["sweeps"], model_opts["model"]
    plan = []
    if mode in ("baseline", "all"):
        plan.append(("baseline", build_args(mp, vals, extra)))
    if mode in ("batch", "all"):
        ubs = [u for u in norm(sw["ubatch"]).split(",") if u]
        for b in [x for x in norm(sw["batch"]).split(",") if x]:
            ok = [u for u in ubs if int(u) <= int(b)]
            if ok:
                plan.append((f"batch_b{b}", build_args(mp, vals, extra, {"batch-size": b, "ubatch-size": ",".join(ok)})))
    if mode in ("kv", "all"):
        for pair in [x for x in norm(sw["kv"]).split(",") if x]:
            k, v = pair.split(":")
            plan.append((f"kv_k{k}_v{v}", build_args(mp, vals, extra, {"cache-type-k": k, "cache-type-v": v})))
    if mode in ("threads", "all") and norm(sw["threads"]):
        plan.append(("threads_sweep", build_args(mp, vals, extra, {"threads": sw["threads"]})))
    if mode in ("moe", "all") and norm(sw["moe"]):
        plan.append(("moe_sweep", build_args(mp, vals, extra, {"n-cpu-moe": sw["moe"]})))
    return plan


def parse_rows(lines):
    header, rows = None, []
    for ln in lines:
        s = ln.strip()
        if not s.startswith("|"):
            continue
        cells = [c.strip() for c in s.strip("|").split("|")]
        if "test" in cells and "t/s" in cells:
            header = cells
            continue
        if header and len(cells) == len(header) and not set(s) <= set("|-: "):
            try:
                rows.append((cells[header.index("test")], float(cells[-1].split()[0]), cells))
            except (ValueError, IndexError):
                pass
    return header, rows


def best_summary(lines):
    header, rows = parse_rows(lines)
    if not rows:
        return ""
    skip = {"model", "size", "params", "backend", "test", "t/s"}
    cols = [i for i, h in enumerate(header) if h not in skip and len({r[2][i] for r in rows}) > 1]
    best = {}
    for test, ts, cells in rows:
        if test not in best or ts > best[test][0]:
            best[test] = (ts, cells)
    out = ["Best result per test:"]
    for test, (ts, cells) in best.items():
        cfg = ", ".join(f"{header[i]}={cells[i]}" for i in cols) or "-"
        out.append(f"  {test:<8} {ts:>9.2f} t/s   {cfg}")
    return "\n".join(out) + "\n"


# ---------------- UI ----------------
class BenchPanel(tk.Frame):
    def __init__(self, master, T, Btn, fonts, app_dir):
        super().__init__(master, bg=T["bg"])
        self.T, self.Btn, self.F, self.app_dir = T, Btn, fonts, app_dir
        self.settings_path = os.path.join(app_dir, SETTINGS_FILE)
        self.cfg = load_settings(self.settings_path)
        self.models, self.model_names, self.visible = {}, [], []
        self.selected = None
        self.q = queue.Queue()
        self.proc = None
        self.running = False
        self.stop_flag = False
        self.vars = {}
        self._build()
        self.reload_models()
        self.after(50, self._pump)

    def _build(self):
        T, F = self.T, self.F
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)
        tabs = tk.Frame(self, bg=T["bg"])
        tabs.grid(row=0, column=0, sticky="ew", padx=18, pady=(14, 8))
        tk.Label(tabs, text="\U0001F9EA Benchmark", bg=T["bg"], fg=T["text"], font=F["h"]).pack(side="left")
        self.chip = tk.Label(tabs, text="\u25CF Idle", bg=T["panel2"], fg=T["muted"], font=F["bold"], padx=12, pady=4)
        self.chip.pack(side="right")
        self.tab_btns = {}
        for name, text in (("settings", "\u2699 Settings"), ("run", "\u25B6 Run")):
            b = self.Btn(tabs, text, lambda n=name: self.show(n), T["panel2"], T["hover"], font=F["bold"])
            b.pack(side="right", padx=4)
            self.tab_btns[name] = b
        self.pages = {"run": self._build_run(), "settings": self._build_settings()}
        self.show("run")

    def show(self, name):
        for n, p in self.pages.items():
            p.grid_remove()
            active = n == name
            self.tab_btns[n]._bg = self.T["accent_bg"] if active else self.T["panel2"]
            self.tab_btns[n].config(bg=self.tab_btns[n]._bg, fg="white" if active else self.T["text"])
        self.pages[name].grid(row=1, column=0, sticky="nsew")
        if name == "run":
            self._refresh_preview()

    def _entry(self, parent, var, **kw):
        T = self.T
        return tk.Entry(parent, textvariable=var, bg=T["panel"], fg=T["text"], insertbackground=T["text"],
                        relief="flat", font=self.F["ui"], highlightthickness=1,
                        highlightbackground=T["border"], highlightcolor=T["accent"], **kw)

    def _build_run(self):
        T, F = self.T, self.F
        page = tk.Frame(self, bg=T["bg"])
        page.grid_rowconfigure(0, weight=1)
        page.grid_columnconfigure(1, weight=1)

        left = tk.Frame(page, bg=T["bg"], width=300)
        left.grid(row=0, column=0, sticky="ns", padx=(18, 10), pady=(0, 14))
        left.grid_propagate(False)
        tk.Label(left, text="MODELS", bg=T["bg"], fg=T["muted"], font=F["small_b"]).pack(anchor="w")
        self.flt = tk.StringVar()
        self._entry(left, self.flt).pack(fill="x", pady=(4, 6), ipady=4)
        lf = tk.Frame(left, bg=T["term"], highlightthickness=1, highlightbackground=T["border"])
        lf.pack(fill="both", expand=True)
        self.lb = tk.Listbox(lf, bg=T["term"], fg=T["text"], selectbackground=T["accent_bg"], selectforeground="white",
                             relief="flat", bd=0, highlightthickness=0, activestyle="none", font=F["ui"], exportselection=False)
        sb = ttk.Scrollbar(lf, orient="vertical", command=self.lb.yview)
        self.lb.config(yscrollcommand=sb.set)
        self.lb.pack(side="left", fill="both", expand=True, padx=4, pady=4)
        sb.pack(side="right", fill="y")
        self.lb.bind("<<ListboxSelect>>", self._on_select)
        self.flt.trace_add("write", lambda *a: self._fill_list())
        self.models_lbl = tk.Label(left, text="", bg=T["bg"], fg=T["muted"], font=F["small"], anchor="w",
                                   justify="left", wraplength=280)
        self.models_lbl.pack(fill="x", pady=(6, 0))
        self.Btn(left, "\U0001F4C4 Choose models.ini\u2026", self.choose_models_ini, T["panel"], T["hover"], font=F["ui"]).pack(fill="x", pady=(6, 0))
        self.Btn(left, "\u21BB Reload models", self.reload_models, T["panel"], T["hover"], font=F["ui"]).pack(fill="x", pady=(6, 0))

        right = tk.Frame(page, bg=T["bg"])
        right.grid(row=0, column=1, sticky="nsew", padx=(0, 18), pady=(0, 14))
        right.grid_rowconfigure(4, weight=1)
        right.grid_columnconfigure(0, weight=1)
        self.model_title = tk.Label(right, text="Select a model", bg=T["bg"], fg=T["text"], font=(F["ui"][0], 13, "bold"), anchor="w")
        self.model_title.grid(row=0, column=0, sticky="ew")
        self.model_info = tk.Label(right, text="", bg=T["bg"], fg=T["muted"], font=F["small"], anchor="w", justify="left", wraplength=800)
        self.model_info.grid(row=1, column=0, sticky="ew", pady=(0, 8))

        grid = tk.Frame(right, bg=T["bg"])
        grid.grid(row=2, column=0, sticky="ew")
        for i, (mode, title, desc) in enumerate(MODES):
            card = tk.Frame(grid, bg=T["panel"], highlightthickness=1, highlightbackground=T["border"], cursor="hand2")
            card.grid(row=i // 3, column=i % 3, sticky="nsew", padx=3, pady=3)
            grid.grid_columnconfigure(i % 3, weight=1, uniform="m")
            t = tk.Label(card, text=title, bg=T["panel"], fg=T["text"], font=F["bold"], anchor="w", cursor="hand2")
            d = tk.Label(card, text=desc, bg=T["panel"], fg=T["muted"], font=F["small"], anchor="w", cursor="hand2")
            t.pack(fill="x", padx=10, pady=(8, 0))
            d.pack(fill="x", padx=10, pady=(0, 8))
            for w in (card, t, d):
                w.bind("<Button-1>", lambda e, m=mode: self.start(m))
                w.bind("<Enter>", lambda e, c=card, a=t, b=d: [x.config(bg=T["hover"]) for x in (c, a, b)])
                w.bind("<Leave>", lambda e, c=card, a=t, b=d: [x.config(bg=T["panel"]) for x in (c, a, b)])

        bar = tk.Frame(right, bg=T["bg"])
        bar.grid(row=3, column=0, sticky="ew", pady=(8, 6))
        self.preview = tk.Label(bar, text="", bg=T["bg"], fg=T["muted"], font=F["mono_s"], anchor="w", justify="left", wraplength=560)
        self.preview.pack(side="left", fill="x", expand=True)
        self.Btn(bar, "\u25A0 Stop", self.stop, T["panel2"], "#3b1d1f", fg=T["err"], font=F["bold"]).pack(side="right", padx=3)
        self.Btn(bar, "\U0001F4C2 Reports", self.open_reports, T["panel2"], T["hover"], font=F["bold"]).pack(side="right", padx=3)
        self.Btn(bar, "\u2715 Clear", self.clear, T["panel2"], T["hover"], font=F["bold"]).pack(side="right", padx=3)

        card = tk.Frame(right, bg=T["term"], highlightthickness=1, highlightbackground=T["border"])
        card.grid(row=4, column=0, sticky="nsew")
        card.grid_rowconfigure(0, weight=1)
        card.grid_columnconfigure(0, weight=1)
        self.out = tk.Text(card, bg=T["term"], fg=T["text"], font=F["mono"], wrap="none", state="disabled",
                           relief="flat", bd=0, padx=12, pady=8, selectbackground="#264f78")
        sy = ttk.Scrollbar(card, orient="vertical", command=self.out.yview)
        sx = ttk.Scrollbar(card, orient="horizontal", command=self.out.xview)
        self.out.config(yscrollcommand=sy.set, xscrollcommand=sx.set)
        self.out.grid(row=0, column=0, sticky="nsew")
        sy.grid(row=0, column=1, sticky="ns")
        sx.grid(row=1, column=0, sticky="ew")
        for tag, col in (("info", T["warn"]), ("err", T["err"]), ("ok", T["ok"]), ("cmd", T["accent"]), ("dim", T["muted"])):
            self.out.tag_config(tag, foreground=col)
        return page

    def _build_settings(self):
        T, F = self.T, self.F
        page = tk.Frame(self, bg=T["bg"])
        page.grid_rowconfigure(0, weight=1)
        page.grid_columnconfigure(0, weight=1)
        wrap = tk.Frame(page, bg=T["term"], highlightthickness=1, highlightbackground=T["border"])
        wrap.grid(row=0, column=0, sticky="nsew", padx=18)
        wrap.grid_rowconfigure(0, weight=1)
        wrap.grid_columnconfigure(0, weight=1)
        self.set_canvas = tk.Canvas(wrap, bg=T["term"], highlightthickness=0, bd=0)
        sb = ttk.Scrollbar(wrap, orient="vertical", command=self.set_canvas.yview)
        self.set_canvas.config(yscrollcommand=sb.set)
        self.set_canvas.grid(row=0, column=0, sticky="nsew")
        sb.grid(row=0, column=1, sticky="ns")
        form = tk.Frame(self.set_canvas, bg=T["term"])
        win = self.set_canvas.create_window((0, 0), window=form, anchor="nw")
        form.bind("<Configure>", lambda e: self.set_canvas.configure(scrollregion=self.set_canvas.bbox("all")))
        self.set_canvas.bind("<Configure>", lambda e: self.set_canvas.itemconfig(win, width=e.width))
        self.set_canvas.bind_all("<MouseWheel>", self._wheel, add="+")
        form.grid_columnconfigure(1, weight=1)

        r = 0
        for title, fields in GROUPS:
            tk.Label(form, text=title, bg=T["term"], fg=T["accent"], font=F["bold"], anchor="w").grid(
                row=r, column=0, columnspan=4, sticky="w", padx=14, pady=(14, 4))
            r += 1
            for sec, key, default, label, hint, kind in fields:
                var = tk.StringVar(value=self.cfg[sec].get(key, default))
                self.vars[(sec, key)] = var
                tk.Label(form, text=label, bg=T["term"], fg=T["text"], font=F["ui"], anchor="w").grid(
                    row=r, column=0, sticky="w", padx=(14, 10), pady=3)
                self._entry(form, var).grid(row=r, column=1, sticky="ew", pady=3, ipady=3)
                if kind in ("file", "dir"):
                    self.Btn(form, "\u2026", lambda v=var, k=kind: self._browse(v, k), T["panel2"], T["hover"],
                             font=F["ui"]).grid(row=r, column=2, padx=(6, 0), pady=3)
                tk.Label(form, text=hint, bg=T["term"], fg=T["muted"], font=F["small"], anchor="w").grid(
                    row=r, column=3, sticky="w", padx=10)
                r += 1
        tk.Frame(form, bg=T["term"], height=10).grid(row=r)

        bar = tk.Frame(page, bg=T["bg"])
        bar.grid(row=1, column=0, sticky="ew", padx=18, pady=12)
        self.Btn(bar, "\U0001F4BE Save to settings.ini", self.save, T["accent_bg"], "#388bfd", fg="white", font=F["bold"]).pack(side="left")
        self.Btn(bar, "Reset to defaults", self.reset, T["panel2"], T["hover"], font=F["bold"]).pack(side="left", padx=8)
        self.save_lbl = tk.Label(bar, text=self.settings_path, bg=T["bg"], fg=T["muted"], font=F["small"])
        self.save_lbl.pack(side="left", padx=10)
        return page

    def _wheel(self, e):
        w = self.winfo_containing(e.x_root, e.y_root)
        if w is not None and str(w).startswith(str(self.set_canvas)) and self.pages["settings"].winfo_ismapped():
            self.set_canvas.yview_scroll(int(-e.delta / 120), "units")
            return "break"

    def _browse(self, var, kind):
        cur = resolve_path(var.get(), self.app_dir)
        if kind == "dir":
            p = filedialog.askdirectory(initialdir=cur if os.path.isdir(cur) else self.app_dir)
        else:
            p = filedialog.askopenfilename(initialdir=os.path.dirname(cur) if cur else self.app_dir)
        if p:
            var.set(os.path.normpath(p))

    # ----- settings -----
    def _collect(self):
        cfg = {s: dict(kv) for s, kv in self.cfg.items()}
        for (sec, key), var in self.vars.items():
            cfg[sec][key] = var.get().strip()
        return cfg

    def save(self):
        cfg = self._collect()
        errs = validate(cfg)
        if errs:
            messagebox.showerror("Invalid settings", "\n".join(errs))
            return
        for sec in ("bench", "sweeps"):
            for k, v in cfg[sec].items():
                if k not in ("extra-args", "show-diagnostics"):
                    cfg[sec][k] = norm(v)
        old_ini = self.cfg["paths"]["models_ini"]
        self.cfg = cfg
        try:
            save_settings(self.settings_path, cfg)
            self.save_lbl.config(text=f"Saved {datetime.now():%H:%M:%S} \u00B7 {self.settings_path}", fg=self.T["ok"])
        except OSError as e:
            messagebox.showerror("Save failed", str(e))
            return
        for (sec, key), var in self.vars.items():
            var.set(cfg[sec][key])
        if cfg["paths"]["models_ini"] != old_ini:
            self.reload_models()
        self._refresh_preview()

    def reset(self):
        d = default_cfg()
        for (sec, key), var in self.vars.items():
            var.set(d[sec][key])
        self.save_lbl.config(text="Defaults loaded - press Save to keep them", fg=self.T["warn"])

    # ----- models -----
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

    # ----- output -----
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

    # ----- running -----
    def start(self, mode):
        if self.running:
            messagebox.showwarning("Busy", "A benchmark is still running. Stop it first.")
            return
        m = self.models.get(self.selected)
        if not m:
            messagebox.showinfo("Benchmark", "Select a model first.")
            return
        if not os.path.isfile(m["model"]):
            self.write(f"Model file not found: {m['model']}\n", "err")
            return
        exe = resolve_path(self.cfg["paths"]["bench_exe"], self.app_dir)
        if not os.path.isfile(exe):
            self.write(f"llama-bench not found: {exe}\nSet it in Settings.\n", "err")
            return
        errs = validate(self.cfg)
        if errs:
            self.write("Invalid settings:\n  " + "\n  ".join(errs) + "\n", "err")
            return
        plan = build_plan(mode, self.cfg, m)
        if not plan:
            self.write("Nothing to run - check the sweep lists in Settings.\n", "err")
            return
        out_dir = resolve_path(self.cfg["paths"]["output_dir"], self.app_dir)
        os.makedirs(out_dir, exist_ok=True)
        self.running, self.stop_flag = True, False
        diag = self.cfg["bench"].get("show-diagnostics", "0") == "1"
        title = {k: t for k, t, _ in MODES}[mode]
        self.write(f"\n=== {self.selected} \u00B7 {title} \u00B7 {len(plan)} run(s) ===\n", "info")
        self.set_state("running")
        threading.Thread(target=self._worker, args=(self.selected, m["model"], exe, plan, out_dir, diag), daemon=True).start()

    def _drain(self, stream, sink, show):
        for line in stream:
            sink.append(line)
            if show:
                self.q.put(("log", line, "dim"))

    def _worker(self, name, model_path, exe, plan, out_dir, diag):
        total, all_out, failed = len(plan), [], False
        try:
            for i, (label, args) in enumerate(plan, 1):
                if self.stop_flag:
                    break
                cmd = [exe] + args
                self.q.put(("state", "running", f"{i}/{total} {label}"))
                self.q.put(("log", f"\n[{i}/{total}] {label}\n> {subprocess.list2cmdline(cmd)}\n", "cmd"))
                started = datetime.now()
                out_lines, err_lines = [], []
                try:
                    self.proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                                                 encoding="utf-8", errors="replace", cwd=os.path.dirname(exe) or None,
                                                 creationflags=NO_WINDOW)
                except Exception as e:
                    self.q.put(("log", f"Cannot start llama-bench: {e}\n", "err"))
                    failed = True
                    break
                t = threading.Thread(target=self._drain, args=(self.proc.stderr, err_lines, diag), daemon=True)
                t.start()
                for line in self.proc.stdout:
                    out_lines.append(line)
                    self.q.put(("log", line, None))
                code = self.proc.wait()
                t.join(3)
                all_out += out_lines
                if self.stop_flag:
                    break
                if code != 0:
                    failed = True
                    self.q.put(("log", f"exit code {code}\n" + "".join(err_lines[-15:]), "err"))
                secs = (datetime.now() - started).total_seconds()
                try:
                    safe = re.sub(r"[^a-zA-Z0-9_.-]", "_", name)
                    path = os.path.join(out_dir, f"{safe}_{label}_{started:%Y%m%d_%H%M%S}.md")
                    rep = [f"# llama-bench results: {name} / {label}", "", f"- **Model:** `{model_path}`",
                           f"- **Date:** {started:%Y-%m-%d %H:%M:%S}", f"- **Duration:** {secs:.1f} seconds",
                           f"- **Exit code:** {code}", f"- **Command:** `{subprocess.list2cmdline(cmd)}`", "", "## Results", "",
                           "".join(out_lines).rstrip() or "_No standard output was produced._"]
                    if err_lines:
                        rep += ["", "<details>", "<summary>Diagnostics / standard error</summary>", "", "```text",
                                "".join(err_lines).rstrip(), "```", "</details>"]
                    with open(path, "w", encoding="utf-8") as f:
                        f.write("\n".join(rep) + "\n")
                    self.q.put(("log", f"saved {path}  ({secs:.0f}s)\n", "ok" if code == 0 else "err"))
                except OSError as e:
                    self.q.put(("log", f"report write failed: {e}\n", "err"))
            summary = best_summary(all_out)
            if summary:
                self.q.put(("log", "\n" + summary, "ok"))
        except Exception as e:
            failed = True
            self.q.put(("log", f"internal error: {e}\n", "err"))
        self.q.put(("end", "stopped" if self.stop_flag else ("failed" if failed else "done")))

    def stop(self):
        if self.running:
            self.stop_flag = True
            p = self.proc
            if p and p.poll() is None:
                subprocess.run(["taskkill", "/PID", str(p.pid), "/T", "/F"], creationflags=NO_WINDOW, capture_output=True)
            self.write("[stopped]\n", "err")

    def _pump(self):
        try:
            for _ in range(300):
                item = self.q.get_nowait()
                if item[0] == "log":
                    self.write(item[1], item[2])
                elif item[0] == "state":
                    self.set_state(item[1], item[2])
                elif item[0] == "end":
                    self.running = False
                    self.set_state(item[1])
        except queue.Empty:
            pass
        finally:
            self.after(50, self._pump)
