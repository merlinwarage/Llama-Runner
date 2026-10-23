"""models_ini (split from bench_panel.py)"""
import configparser
import os
import shutil

from bench.constants import FLAGS, INHERIT
from bench.settings_store import norm


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
