"""settings_store (split from bench_panel.py)"""
import configparser
import os
import re
import shlex

from bench.constants import FA_OK, NUM_LIST
from bench.views.settings_spec import GROUPS


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
