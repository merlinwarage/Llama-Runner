"""Benchmark worker thread: start / stop / output pump (split from bench_panel.py)"""
import os
import queue
import re
import subprocess
import threading
from datetime import datetime
from tkinter import messagebox

from bench.cmdline import build_plan
from bench.constants import MODES, NO_WINDOW
from bench.models_ini import resolve_path
from bench.results import best_summary
from bench.settings_store import validate


class RunnerMixin:
    """Benchmark worker thread: start / stop / output pump."""
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
