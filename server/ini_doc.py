"""ini_doc (split from server_panel.py)"""
import re

from server.constants import GLOBAL, IS_WIN


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
    # comment-preserving models.ini editor. Section = [name, body_lines, comment_lines];
    # comment_lines = the contiguous '#' lines directly above the [header] (belong to that section)
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
                com = self._take_comment(cur)
                cur = []
                self.secs.append([m.group(1).strip(), cur, com])
            else:
                cur.append(ln)

    @staticmethod
    def _take_comment(lines):
        i = len(lines)
        while i > 0 and lines[i - 1].lstrip().startswith("#"):
            i -= 1
        com = lines[i:]
        del lines[i:]
        return com

    def names(self):
        return [s[0] for s in self.secs]

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

    def comment(self, name):
        s = self._sec(name)
        return list(s[2]) if s else []

    def set_comment(self, name, lines):
        s = self._sec(name)
        if s:
            s[2][:] = list(lines)

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

    def add(self, name, lines, comment=None):
        lines = list(lines)
        while lines and not lines[-1].strip():
            lines.pop()
        com = list(comment or [])
        if name == GLOBAL:
            self.secs.insert(0, [name, lines + ([""] if self.secs else []), com])
            return
        if self.secs:
            prev = self.secs[-1][1]
            if prev and prev[-1].strip():
                prev.append("")
        elif self.pre and self.pre[-1].strip():
            self.pre.append("")
        self.secs.append([name, lines, com])

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
        for name, body, com in self.secs:
            out += com
            out.append(f"[{name}]")
            out += body
        return self.nl.join(out) + self.nl
