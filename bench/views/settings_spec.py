"""views.settings_spec (split from bench_panel.py)"""

# (section, key, default, label, hint, kind)
GROUPS = [
    ("Paths", [
        ("paths", "models_ini", "models.ini", "Models config (models.ini)", "full path, or relative to the launcher folder; if missing, models*.ini next to the launcher is used", "file"),
        ("paths", "bench_exe", "llama-bench.exe", "llama-bench executable", "relative paths are resolved against the launcher folder", "file"),
        ("paths", "output_dir", "bench-results", "Report folder", "Markdown reports are saved here", "dir"),
    ]),
    ("Base parameters  (comma list = llama-bench tests every combination; blank = take from models.ini)", [
        ("bench", "threads", "8", "Threads  (-t)", "e.g. 8,9,10", "text"),
        ("bench", "n-gpu-layers", "99", "GPU layers  (-ngl)", "", "text"),
        ("bench", "n-cpu-moe", "", "CPU MoE layers  (-ncmoe)", "e.g. 20,30,40 - blank = model's n-cpu-moe", "text"),
        ("bench", "fa", "on", "Flash attention  (-fa)", "on / off / 0 / 1 / auto, lists allowed", "text"),
        ("bench", "cache-type-k", "q8_0", "K cache type  (-ctk)", "e.g. q8_0,q4_0,f16", "text"),
        ("bench", "cache-type-v", "q8_0", "V cache type  (-ctv)", "e.g. q8_0,q4_0,f16", "text"),
        ("bench", "batch-size", "512", "Batch  (-b)", "", "text"),
        ("bench", "ubatch-size", "128", "Micro-batch  (-ub)", "", "text"),
        ("bench", "n-prompt", "512", "Prompt tokens  (-p)", "", "text"),
        ("bench", "n-gen", "128", "Generated tokens  (-n)", "", "text"),
        ("bench", "repeats", "3", "Repeats  (-r)", "", "text"),
        ("bench", "extra-args", "", "Extra llama-bench args", "raw, appended as-is (e.g. --no-warmup)", "text"),
        ("bench", "show-diagnostics", "0", "Show stderr while running", "1 = show, 0 = only on failure / in report", "text"),
    ]),
    ("Sweep lists  (used by the sweep tests)", [
        ("sweeps", "batch", "512,1024,2048", "Batch sweep: -b values", "", "text"),
        ("sweeps", "ubatch", "128,256,512", "Batch sweep: -ub values", "values above the batch size are skipped", "text"),
        ("sweeps", "kv", "q8_0:q8_0,q8_0:q4_0,q4_0:q8_0,q4_0:q4_0", "KV sweep: K:V pairs", "comma-separated pairs, K:V", "text"),
        ("sweeps", "threads", "4,6,8,12,16", "Thread sweep: -t values", "", "text"),
        ("sweeps", "moe", "20,28,30", "MoE sweep: -ncmoe values", "combined with the base Threads list", "text"),
    ]),
]
