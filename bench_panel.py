# bench_panel.py - backwards-compatible shim (server/ still imports resolve_path from here)
from bench import *  # noqa: F401,F403
from bench import BenchPanel, resolve_path, load_settings, save_settings, build_args, build_plan  # noqa: F401
