"""llama-server process lifecycle, log reader, health probe (split from server_panel.py)"""
import os
import queue
import subprocess
import threading
import time
import urllib.request
from bench_panel import resolve_path
from tkinter import messagebox

from server.args import browse_host, build_args, join_base, server_addr, unquote
from server.constants import GLOBAL, IS_WIN, NEW_GROUP, NO_WINDOW, OK_RE, PP_RE, TG_RE
from server.netutil import open_url, port_busy


class ProcessMixin:
    """llama-server process lifecycle, log reader, health probe."""
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
