"""Run view: llama-bench run form (split from bench_panel.py)"""
import tkinter as tk
from tkinter import ttk

from bench.constants import MODES


class RunViewMixin:
    """Run view: llama-bench run form."""
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
