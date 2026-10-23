"""args (split from server_panel.py)"""
import os
import shlex

from server.constants import APP_ONLY, BOOL_FLAGS, FALSE, MUST_JOIN, NEGATABLE, PATH_KEYS, SHORT_FLAGS, TRUE


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
