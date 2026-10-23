"""Config tab: General page layout (split from server_panel.py)"""
import tkinter as tk
from tkinter import ttk

from server.views.config.spec import FLAG_FIELDS, LOAD_MODES, MCP_CHOICES, PATH_FIELDS, ROWS


class ConfigGeneralMixin:
    """Config tab: General page layout."""
    def _config_wheel(self, e):
        w = self.winfo_containing(e.x_root, e.y_root)
        if w is None or isinstance(w, tk.Text):
            return
        for cv, inner in ((self.cfg_canvas, self.cfg_inner), (self.adv_canvas, self.adv_inner)):
            if cv.winfo_ismapped() and str(w).startswith(str(cv)) and inner.winfo_reqheight() > cv.winfo_height():
                cv.yview_scroll(int(-e.delta / 120), "units")
                return

    def _cfg_sub(self, name):
        self.cfg_sub = name
        for n, b in self.cfg_sub_btns.items():
            act = n == name
            b._bg = self.T["accent_bg"] if act else self.T["panel2"]
            b.config(bg=b._bg, fg="white" if act else self.T["text"])
        if name == "main":
            self.adv_page.grid_remove()
            self.cfg_canvas.grid()
            self.cfg_vs.grid()
        else:
            self.cfg_canvas.grid_remove()
            self.cfg_vs.grid_remove()
            self.adv_page.grid(row=1, column=0, columnspan=2, sticky="nsew")

    def _build_config(self):
        T, F = self.T, self.F
        outer = tk.Frame(self, bg=T["bg"])
        outer.grid_rowconfigure(1, weight=1)
        outer.grid_columnconfigure(0, weight=1)
        cv = tk.Canvas(outer, bg=T["bg"], highlightthickness=0, bd=0)
        vs = ttk.Scrollbar(outer, orient="vertical", command=cv.yview)
        cv.configure(yscrollcommand=vs.set)
        cv.grid(row=1, column=0, sticky="nsew")
        vs.grid(row=1, column=1, sticky="ns")
        page = tk.Frame(cv, bg=T["bg"])
        win = cv.create_window((0, 0), window=page, anchor="nw")

        def fit(_e=None):
            # inner page fills the canvas width; grows to canvas height so OTHER PARAMETERS still stretches
            cv.itemconfig(win, width=cv.winfo_width(), height=max(cv.winfo_height(), page.winfo_reqheight()))
            cv.configure(scrollregion=cv.bbox("all"))
            if page.winfo_reqheight() <= cv.winfo_height():
                cv.yview_moveto(0)

        cv.bind("<Configure>", fit)
        page.bind("<Configure>", fit)
        self.cfg_outer, self.cfg_canvas, self.cfg_inner, self.cfg_vs = outer, cv, page, vs
        strip = tk.Frame(outer, bg=T["bg"])
        strip.grid(row=0, column=0, columnspan=2, sticky="ew", padx=18, pady=(0, 6))
        self.cfg_sub_btns = {}
        for n, text in (("main", "General"), ("advanced", "Advanced")):
            b = self.Btn(strip, text, lambda n=n: self._cfg_sub(n), T["panel2"], T["hover"], font=F["ui"])
            b.pack(side="left", padx=(0, 6))
            self.cfg_sub_btns[n] = b
        self.adv_page = self._build_advanced(outer)
        self._cfg_sub("main")
        cv.bind_all("<MouseWheel>", self._config_wheel, add="+")
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

        crow = tk.Frame(card, bg=T["panel"])
        crow.pack(fill="x", padx=12, pady=(10, 0))
        tk.Label(crow, text="Comment  \u00B7  '#' lines above the [section] in models.ini  \u00B7  shown as tooltip in the model list",
                 bg=T["panel"], fg=T["muted"], font=F["small"], anchor="w").pack(fill="x")
        cbox = tk.Frame(crow, bg=T["term"], highlightthickness=1, highlightbackground=T["border"])
        cbox.pack(fill="x")
        self.comment = tk.Text(cbox, bg=T["term"], fg=T["text"], insertbackground=T["text"], font=F["mono_s"],
                               wrap="word", relief="flat", bd=0, padx=8, pady=4, height=4, undo=True,
                               selectbackground="#264f78")
        csy = ttk.Scrollbar(cbox, orient="vertical", command=self.comment.yview)
        self.comment.config(yscrollcommand=csy.set)
        csy.pack(side="right", fill="y")
        self.comment.pack(side="left", fill="x", expand=True)
        for ev in ("<KeyRelease>", "<<Paste>>", "<<Cut>>", "<<Undo>>", "<<Redo>>"):
            self.comment.bind(ev, lambda e: self.after(1, self._on_comment))

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
        tk.Label(fl, text="Load mode", bg=T["panel"], fg=T["muted"], font=F["small"]).pack(side="left", padx=(0, 6))
        lm = tk.StringVar()
        self.fvars["load-mode"] = lm
        lm.trace_add("write", self._on_change)
        self._combo(fl, lm, [""] + LOAD_MODES, width=12, state="readonly").pack(side="left")
        lh = tk.Label(fl, text="", bg=T["panel"], fg=T["warn"], font=F["small"])
        lh.pack(side="left", padx=(6, 22))
        self.hints["load-mode"] = lh
        for key, label in FLAG_FIELDS:
            var = tk.IntVar()
            self.flagvars[key] = var
            var.trace_add("write", self._on_change)
            tk.Checkbutton(fl, text=label, variable=var, bg=T["panel"], fg=T["text"], selectcolor=T["panel2"],
                           activebackground=T["panel"], activeforeground=T["text"], font=F["ui"], bd=0,
                           highlightthickness=0, cursor="hand2").pack(side="left", padx=(0, 16))

        tk.Label(page, text="OTHER PARAMETERS  \u00B7  one 'key = value' per line, flags without dashes (e.g. cache-reuse = 256, ctx-checkpoints = 32). ; or # starts a comment",
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

        bar = tk.Frame(outer, bg=T["bg"])
        bar.grid(row=2, column=0, columnspan=2, sticky="ew", padx=18, pady=10)
        self.btn_save = self.Btn(bar, "\U0001F4BE Save  Ctrl+S", self.save, T["accent_bg"], "#388bfd", fg="white", font=F["bold"])
        self.btn_save.pack(side="left")
        for text, cmd in (("\u21BA Revert", self.revert), ("\u2750 Duplicate", self.duplicate), ("\u270E Rename", self.rename),
                          ("\U0001F5D1 Delete", self.delete), ("\U0001F4DD Open models.ini", self.open_ini)):
            self.Btn(bar, text, cmd, T["panel2"], T["hover"], font=F["ui"]).pack(side="left", padx=(6, 0))
        self.dirty_lbl = tk.Label(bar, text="", bg=T["bg"], fg=T["warn"], font=F["bold"])
        self.dirty_lbl.pack(side="right")
        return outer
