"""cmdline (split from bench_panel.py)"""
import shlex

from bench.constants import FLAGS
from bench.models_ini import effective
from bench.settings_store import norm


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
