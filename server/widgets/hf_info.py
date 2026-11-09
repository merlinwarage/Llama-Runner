"""Hugging Face model info: reachability probe + search-results dialog (accordion rows)."""
import json
import re
import threading
import time
import tkinter as tk
from concurrent.futures import ThreadPoolExecutor
import urllib.error
import urllib.parse
import urllib.request

from server.netutil import open_url

HF_BASE = "https://huggingface.co"
_UA = {"User-Agent": "LlamaRunner"}


def hf_reachable(timeout=3.0):
    """True if huggingface.co answers an HTTP request (any status < 500)."""
    try:
        req = urllib.request.Request(HF_BASE, headers=_UA, method="HEAD")
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status < 500
    except urllib.error.HTTPError as e:
        return e.code < 500
    except Exception:
        return False


# Trailing quant / format tokens, only matched at the end of the name after a separator.
_SEP = r"[-_.\s]"
_QUANT_RE = re.compile(
    rf"{_SEP}(?:"
    rf"i?q\d{{1,2}}(?:{_SEP}?(?:k|0|1))?(?:{_SEP}?(?:xxs|xs|s|m|l|xl|nl))?"  # q4_k_m, q8_0, iq3_xxs, iq4_nl
    rf"|(?:ud{_SEP})?q\d{{1,2}}{_SEP}?k{_SEP}?xl"                            # ud-q4_k_xl
    rf"|bf16|fp16|f16|fp32|f32|fp8|mxfp4|nvfp4"
    rf"|gguf"
    rf")$",
    re.IGNORECASE,
)


def search_term(name):
    """Model id without trailing quant/format suffixes (glm-4-7-flash-q4-k-m -> glm-4-7-flash)."""
    term = name.strip()
    while True:
        cut = _QUANT_RE.sub("", term)
        if cut == term or len(cut) < 2:
            return term
        term = cut


def hf_search(name, limit=10, timeout=10.0):
    """Search the HF model API, most downloaded first."""
    url = f"{HF_BASE}/api/models?search={urllib.parse.quote(name)}&limit={limit}&sort=downloads&direction=-1"
    req = urllib.request.Request(url, headers=_UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        data = json.loads(r.read().decode("utf-8"))
    return [m for m in data if isinstance(m, dict)] if isinstance(data, list) else []


def search_variants(name):
    """Search terms to try: quant-stripped name, plus a dotted version variant (glm-4-7 -> glm-4.7)."""
    term = search_term(name)
    # only when the second number is a version part (followed by a separator or end), not a size like 8B
    out = [term, re.sub(r"(?<=\d)-(?=\d+(?:[-_\s]|$))", ".", term)]
    return list(dict.fromkeys(out))


def hf_lookup(name, limit=10):
    """Merge results of all search variants (full name as last resort), sorted by downloads."""
    terms = search_variants(name)
    merged = {}
    with ThreadPoolExecutor(max_workers=len(terms)) as pool:  # variants in parallel
        for results in pool.map(lambda t: hf_search(t, limit), terms):
            for m in results:
                merged.setdefault(m.get("id") or m.get("modelId"), m)
    if not merged and name not in terms:
        terms.append(name)
        for m in hf_search(name, limit):
            merged.setdefault(m.get("id") or m.get("modelId"), m)
    data = sorted(merged.values(), key=lambda m: m.get("downloads") or 0, reverse=True)[:limit]
    return terms, data


def _fmt(v):
    if isinstance(v, list):
        return ", ".join(str(x) for x in v) or "—"
    if isinstance(v, dict):
        return json.dumps(v, ensure_ascii=False)
    if isinstance(v, int) and not isinstance(v, bool):
        return f"{v:,}"
    return str(v)


def show_model_info(parent, T, F, name="", searchable=False):
    """HF results dialog. searchable=True adds a search bar on top (sidebar header button)."""
    top = parent.winfo_toplevel()
    dlg = tk.Toplevel(top)
    dlg.title("Model info" + (f" — {name}" if name and not searchable else ""))
    dlg.configure(bg=T["bg"])
    dlg.transient(top)
    w, h = 720, 520
    x = (dlg.winfo_screenwidth() - w) // 2
    y = (dlg.winfo_screenheight() - h) // 2
    dlg.geometry(f"{w}x{h}+{max(0, x)}+{max(0, y)}")
    dlg.minsize(480, 300)

    qvar = tk.StringVar(value=name)
    if searchable:
        tk.Label(dlg, text="Search Hugging Face models", bg=T["bg"], fg=T["text"], font=F["h"],
                 anchor="w").pack(fill="x", padx=16, pady=(14, 6))
        sbar = tk.Frame(dlg, bg=T["panel"], highlightthickness=1, highlightbackground=T["border"], highlightcolor=T["accent"])
        sbar.pack(fill="x", padx=16, pady=(0, 4))
        tk.Label(sbar, text="⌕", bg=T["panel"], fg=T["muted"], font=F["ui"]).pack(side="left", padx=(8, 0))
        qent = tk.Entry(sbar, textvariable=qvar, bg=T["panel"], fg=T["text"], insertbackground=T["text"],
                        relief="flat", font=F["ui"])
        qent.pack(side="left", fill="x", expand=True, padx=6, pady=6)
        go = tk.Label(sbar, text="Search", bg=T["accent_bg"], fg="white", font=F["bold"], padx=14, cursor="hand2")
        go.pack(side="right", fill="y")
    else:
        tk.Label(dlg, text=f"Hugging Face results for “{name}”", bg=T["bg"], fg=T["text"], font=F["h"],
                 anchor="w").pack(fill="x", padx=16, pady=(14, 2))
    status = tk.Label(dlg, text="", bg=T["bg"], fg=T["muted"], font=F["small"], anchor="w")
    status.pack(fill="x", padx=16, pady=(0, 8))

    bar = tk.Frame(dlg, bg=T["bg"])
    bar.pack(fill="x", side="bottom", padx=16, pady=12)
    tk.Button(bar, text="Close", command=dlg.destroy, bg=T["panel2"], fg=T["text"], relief="flat", font=F["bold"],
              padx=16, pady=3, activebackground=T["hover"], activeforeground=T["text"], cursor="hand2").pack(side="right")

    wrap = tk.Frame(dlg, bg=T["side"], highlightthickness=1, highlightbackground=T["border"])
    wrap.pack(fill="both", expand=True, padx=16)
    canvas = tk.Canvas(wrap, bg=T["side"], highlightthickness=0, bd=0)
    sb = tk.Scrollbar(wrap, orient="vertical", command=canvas.yview)
    canvas.configure(yscrollcommand=sb.set)
    sb.pack(side="right", fill="y")
    canvas.pack(side="left", fill="both", expand=True)
    body = tk.Frame(canvas, bg=T["side"])
    win = canvas.create_window((0, 0), window=body, anchor="nw")
    body.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
    canvas.bind("<Configure>", lambda e: canvas.itemconfig(win, width=e.width))
    dlg.bind("<MouseWheel>", lambda e: canvas.yview_scroll(int(-e.delta / 120), "units"))
    dlg.bind("<Escape>", lambda e: dlg.destroy())

    def add_row(m):
        mid = m.get("id") or m.get("modelId") or "?"
        row = tk.Frame(body, bg=T["side"])
        row.pack(fill="x")
        summary = f"↓ {_fmt(m.get('downloads', 0))}   ♥ {_fmt(m.get('likes', 0))}"
        if m.get("pipeline_tag"):
            summary += f"   · {m['pipeline_tag']}"
        head = tk.Frame(row, bg=T["panel"], cursor="hand2")
        head.pack(fill="x", pady=(0, 1))
        arrow = tk.Label(head, text="▸", bg=T["panel"], fg=T["muted"], font=F["ui"], width=2)
        arrow.pack(side="left", padx=(6, 0), pady=6)
        title = tk.Label(head, text=mid, bg=T["panel"], fg=T["text"], font=F["bold"], anchor="w")
        title.pack(side="left", fill="x", expand=True)
        info = tk.Label(head, text=summary, bg=T["panel"], fg=T["muted"], font=F["small"])
        info.pack(side="right", padx=10)

        detail = tk.Frame(row, bg=T["bg"])
        grid = tk.Frame(detail, bg=T["bg"])
        grid.pack(fill="x", padx=(30, 12), pady=(8, 4))
        grid.columnconfigure(1, weight=1)
        for i, (k, v) in enumerate((k, v) for k, v in m.items() if k not in ("_id",)):
            tk.Label(grid, text=k, bg=T["bg"], fg=T["muted"], font=F["small_b"], anchor="nw").grid(
                row=i, column=0, sticky="nw", padx=(0, 12), pady=1)
            tk.Label(grid, text=_fmt(v), bg=T["bg"], fg=T["text"], font=F["mono_s"], anchor="w", justify="left",
                     wraplength=500).grid(row=i, column=1, sticky="w", pady=1)
        url = f"{HF_BASE}/{mid}"
        link = tk.Label(detail, text=f"Open {url} ↗", bg=T["bg"], fg=T["accent"], font=F["small"], cursor="hand2", anchor="w")
        link.pack(fill="x", padx=30, pady=(2, 10))
        link.bind("<Button-1>", lambda e: open_url(url))

        def toggle(_e=None):
            if detail.winfo_ismapped():
                detail.pack_forget()
                arrow.config(text="▸")
            else:
                detail.pack(fill="x")
                arrow.config(text="▾")

        for w in (head, arrow, title, info):
            w.bind("<Button-1>", toggle)
            w.bind("<Enter>", lambda e: [x.config(bg=T["hover"]) for x in (head, arrow, title, info)])
            w.bind("<Leave>", lambda e: [x.config(bg=T["panel"]) for x in (head, arrow, title, info)])

    state = {"gen": 0}

    def run_search(_e=None):
        q = qvar.get().strip()
        if not q:
            status.config(text="Type a model name and press Enter.", fg=T["muted"])
            return
        state["gen"] += 1
        gen, res = state["gen"], {}
        for w in body.winfo_children():
            w.destroy()
        canvas.yview_moveto(0)
        status.config(text="Searching…", fg=T["muted"])
        t0 = time.monotonic()

        def worker():
            # single assignment so poll() never sees a half-written result
            try:
                terms, data = hf_lookup(q)
                res["out"] = ("ok", " / ".join(terms), data)
            except Exception as e:  # network / HTTP / JSON errors
                res["out"] = ("err", str(e), None)

        def poll():
            if not dlg.winfo_exists() or gen != state["gen"]:
                return  # dialog closed or superseded by a newer search
            out = res.get("out")
            if out is None:
                status.config(text=f"Searching… {int(time.monotonic() - t0)}s")
                dlg.after(200, poll)
                return
            kind, term, data = out
            if kind == "err":
                status.config(text=f"Request failed: {term}", fg=T["err"])
                return
            qs = f"search: “{term}”"
            status.config(text=f"{len(data)} result(s) · {qs} · click a row to expand" if data
                          else f"No matching models found ({qs}).", fg=T["muted"])
            for m in data:
                try:
                    add_row(m)
                except Exception:  # one odd record must not break the rest of the list
                    continue

        threading.Thread(target=worker, daemon=True).start()
        dlg.after(100, poll)

    if searchable:
        qent.bind("<Return>", run_search)
        go.bind("<Button-1>", run_search)
        qent.focus_set()
    else:
        dlg.focus_set()
    run_search()
