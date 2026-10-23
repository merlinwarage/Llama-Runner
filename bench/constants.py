"""constants (split from bench_panel.py)"""
import re


NO_WINDOW = 0x08000000

SETTINGS_FILE = "settings.ini"

FLAGS = [("threads", "-t"), ("n-gpu-layers", "-ngl"), ("n-cpu-moe", "-ncmoe"), ("fa", "-fa"),
         ("cache-type-k", "-ctk"), ("cache-type-v", "-ctv"), ("batch-size", "-b"),
         ("ubatch-size", "-ub"), ("n-prompt", "-p"), ("n-gen", "-n"), ("repeats", "-r")]

INHERIT = {k for k, _ in FLAGS[:8]}

NUM_LIST = re.compile(r"^\d+(,\d+)*$")

FA_OK = {"on", "off", "0", "1", "auto"}

MODES = [
    ("baseline", "Quick baseline", "One run with the base settings"),
    ("batch", "Batch / ubatch sweep", "Sweep lists: batch x ubatch"),
    ("kv", "KV-cache sweep", "Sweep list: K:V cache pairs"),
    ("threads", "CPU thread sweep", "Sweep list: threads"),
    ("moe", "CPU-MoE sweep", "Sweep list: -ncmoe x base threads"),
    ("all", "Run all tests", "Baseline + all four sweeps"),
]
