"""constants (split from server_panel.py)"""
import os
import re


IS_WIN = os.name == "nt"

NO_WINDOW = 0x08000000 if IS_WIN else 0

NEW_GROUP = 0x00000200 if IS_WIN else 0

SETTINGS_FILE = "settings.ini"

GLOBAL = "*"

APP_ONLY = {"load-on-startup", "stop-timeout", "mcp"}  # keys never passed to llama-server

PATH_KEYS = {"model", "mmproj", "model-draft", "lora", "lora-scaled", "chat-template-file", "grammar-file",
             "json-schema-file", "slot-save-path", "media-path", "api-key-file", "ssl-key-file", "ssl-cert-file",
             "lookup-cache-static", "lookup-cache-dynamic", "spec-draft-model", "control-vector", "log-file",
             "ui-config-file", "log-prompts-dir", "path", "models-dir", "models-preset", "video-ffmpeg-dir"}

MUST_JOIN = {"model", "mmproj", "model-draft"}

BOOL_FLAGS = {"jinja", "mlock", "no-mmap", "cont-batching", "no-cont-batching", "no-webui", "metrics", "slots",
              "no-slots", "kv-unified", "no-kv-offload", "swa-full", "verbose", "log-timestamps", "log-prefix",
              "no-warmup", "embedding", "embeddings", "reranking", "no-context-shift", "context-shift",
              "cpu-moe", "no-host", "no-op-offload", "check-tensors", "no-perf", "special", "mmap", "webui",
              "warmup", "kv-offload", "op-offload", "direct-io", "no-direct-io", "no-mmproj-offload"}

NEGATABLE = {"mmap", "webui", "cont-batching", "warmup", "context-shift", "kv-offload", "slots", "op-offload",
             "perf", "direct-io", "repack", "escape", "log-jsonl", "log-prefix", "log-timestamps", "cors-credentials",
             "cache-idle-slots", "cache-prompt", "prefill-assistant", "skip-chat-parsing", "reasoning-preserve",
             "spec-draft-backend-sampling", "models-autoload", "mmproj-auto", "ui-mcp-proxy", "kv-unified", "agent"}

SHORT_FLAGS = {"ngl", "ctk", "ctv", "ncmoe", "cmoe", "ctkd", "ctvd", "ngld", "hfr", "hff", "hfd", "hfrd", "hfv", "hffv",
               "tb", "tbd", "kvu", "nkvo", "np", "dev", "devd", "lcs", "lcd", "sps", "ctxcp"}

TRUE = {"true", "yes", "enabled", "on", "1"}

FALSE = {"false", "no", "disabled", "off", "0"}

LEGACY_LOAD = {"mlock", "no-mmap"}  # old checkboxes, migrated into load-mode

ERR_RE = re.compile(r"\b(error|failed|fatal|exception|out of memory|oom|cannot|unable)\b", re.I)

WARN_RE = re.compile(r"\bwarn(ing)?\b", re.I)

OK_RE = re.compile(r"server is listening|all slots are idle", re.I)

PP_RE = re.compile(r"prompt eval time\s*=.*?([\d.]+)\s+tokens per second", re.I)

TG_RE = re.compile(r"^\s*eval time\s*=.*?([\d.]+)\s+tokens per second", re.I)

DEFAULT_SRV = {"server_exe": "llama-server.exe", "extra_args": "", "open_browser": "0", "stop_on_exit": "1",
               "mcp_config": "mcp.json", "use_mcp": "0"}
