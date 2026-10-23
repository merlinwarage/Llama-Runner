"""views.config.spec (split from server_panel.py)"""

KV_TYPES = ["f32", "f16", "bf16", "q8_0", "q5_1", "q5_0", "q4_1", "q4_0", "iq4_nl"]

LOAD_MODES = ["auto", "none", "mmap", "mlock", "mmap+mlock", "dio"]  # llama-server --load-mode

FLOAT_RX = r"^-?\d+(\.\d+)?$"

ROWS = [
    [("ctx-size", "Context (ctx-size)", ["4096", "8192", "16384", "32768", "65536", "131072", "262144"]),
     ("n-gpu-layers", "GPU layers (n-gpu-layers)", ["auto", "all", "99", "0"]),
     ("n-cpu-moe", "CPU MoE layers (n-cpu-moe)", None)],
    [("threads", "Threads", None),
     ("batch-size", "Batch (batch-size)", ["512", "1024", "2048", "4096"]),
     ("ubatch-size", "Micro-batch (ubatch-size)", ["128", "256", "512", "1024"])],
    [("flash-attn", "Flash attention", ["on", "off", "auto"]),
     ("cache-type-k", "K cache (cache-type-k)", KV_TYPES),
     ("cache-type-v", "V cache (cache-type-v)", KV_TYPES)],
    [("parallel", "Parallel slots", None),
     ("host", "Host", ["127.0.0.1", "0.0.0.0"]),
     ("port", "Port", None)],
    [("temp", "Temperature (temp)", None),
     ("top-p", "Top-p (top-p)", None),
     ("top-k", "Top-k (top-k)", None)],
    [("min-p", "Min-p (min-p)", None),
     ("presence-penalty", "Presence penalty (presence-penalty)", None),
     ("repeat-penalty", "Repeat penalty (repeat-penalty)", None)],
]

PATH_FIELDS = [("model", "Model (.gguf)"), ("mmproj", "Multimodal projector (mmproj)"),
               ("chat-template-file", "Chat template file (chat-template-file)")]

FLAG_FIELDS = [("jinja", "jinja"), ("no-webui", "no-webui"), ("metrics", "metrics"),
               ("no-mmproj-offload", "no-mmproj-offload")]

INT_KEYS = {"ctx-size": r"^\d+$", "n-cpu-moe": r"^\d+$", "threads": r"^-?\d+$", "batch-size": r"^\d+$",
            "ubatch-size": r"^\d+$", "parallel": r"^-?\d+$", "port": r"^\d+$",
            "n-gpu-layers": r"^(\d+|-1|auto|all)$",
            "top-k": r"^-?\d+$", "temp": FLOAT_RX, "top-p": FLOAT_RX, "min-p": FLOAT_RX,
            "presence-penalty": FLOAT_RX, "repeat-penalty": FLOAT_RX}

ADV_SPEC = r"""
## CPU & threading
threads-batch | t | Threads for batch/prompt processing (default: same as threads)
cpu-mask | t | CPU affinity mask, arbitrarily long hex
cpu-range | t | CPU range for affinity, lo-hi
cpu-strict | c:0,1 | Strict CPU placement (default 0)
prio | c:-1,0,1,2,3 | Process priority: low -1, normal 0, medium 1, high 2, realtime 3
poll | t | Polling level 0-100 to wait for work (default 50)
cpu-mask-batch | t | CPU affinity mask for batch/prompt threads
cpu-range-batch | t | CPU range for batch/prompt threads, lo-hi
cpu-strict-batch | c:0,1 | Strict CPU placement for batch threads
prio-batch | c:0,1,2,3 | Batch thread priority: 0 normal, 1 medium, 2 high, 3 realtime
poll-batch | c:0,1 | Use polling for batch threads
numa | c:distribute,isolate,numactl | NUMA optimizations
threads-http | t | Threads for HTTP requests (default -1)

## Context, KV cache & slots
n-predict | t | Tokens to predict (-1 = infinity)
keep | t | Tokens to keep from the initial prompt (0 default, -1 = all)
swa-full | f | Use full-size SWA cache
kv-unified | b | Single unified KV buffer shared across all sequences
kv-offload | b | KV cache offloading (default enabled)
kv-unified-per-slot | t | Context limit per parallel slot
cache-ram | t | Max prompt cache size in MiB (default 8192, -1 no limit, 0 disable)
cache-idle-slots | b | Save idle slots to the prompt cache (requires cache-ram)
cache-prompt | b | Prompt caching (default enabled)
cache-reuse | t | Min chunk size to reuse from cache via KV shifting (default 0)
ctx-checkpoints | t | Max context checkpoints per slot (default 32)
checkpoint-min-step | t | Min spacing between context checkpoints in tokens (default 8192)
context-shift | b | Context shift on infinite text generation (default disabled)
slot-prompt-similarity | t | How much a prompt must match a slot to reuse it (default 0.10)
sleep-idle-seconds | t | Idle seconds before the server sleeps (-1 = disabled)
slot-save-path | p:dir | Directory to save slot KV cache

## Memory, offload & performance
lazy-mode | c:on,auto,off | On-demand reading of large tensors such as per-layer embeddings (needs mmap)
repack | b | Weight repacking (default enabled)
no-host | f | Bypass host buffer, allowing extra buffers
op-offload | b | Offload host tensor operations to device (default true)
perf | b | libllama internal performance timings
check-tensors | f | Check model tensor data for invalid values
fit | c:on,off | Adjust unset arguments to fit in device memory (default on)
fit-target | t | Target margin per device in MiB, comma-separated (default 1024)
fit-ctx | t | Minimum ctx size --fit may set (default 4096)
moe-cache-mib | t | GPU cache MiB for MoE experts kept in CPU (default 0 = off)
n-cpu-ffn | t | Keep dense FFN weights of the first N layers in CPU
cpu-moe | f | Keep all MoE weights in CPU
warmup | b | Warmup run on start (default enabled)
cont-batching | b | Continuous batching (default enabled)
override-kv | t | Override model metadata: KEY=TYPE:VALUE,... (int, float, bool, str)
override-tensor | t | Override tensor buffer type: pattern=buffer,...

## GPU & devices
device | t | Comma-separated devices for offloading (none = no offload)
split-mode | c:none,layer,row,tensor | How to split the model across GPUs (tensor is experimental)
tensor-split | t | Fraction of the model per GPU, e.g. 3,1
main-gpu | t | GPU for the model (split-mode none) or intermediate results/KV (row)
rpc | t | Comma-separated RPC servers (host:port)

## RoPE & YaRN
rope-scaling | c:none,linear,yarn | RoPE frequency scaling method
rope-scale | t | RoPE context scaling factor
rope-freq-base | t | RoPE base frequency (NTK-aware scaling)
rope-freq-scale | t | RoPE frequency scaling factor (expands context by 1/N)
yarn-orig-ctx | t | YaRN original context size (0 = model training context)
yarn-ext-factor | t | YaRN extrapolation mix factor (default -1.00)
yarn-attn-factor | t | YaRN attention magnitude scale (default -1.00)
yarn-beta-slow | t | YaRN high correction dim or alpha (default -1.00)
yarn-beta-fast | t | YaRN low correction dim or beta (default -1.00)

## Sampling extras
samplers | t | Sampler order separated by ';' (default penalties;dry;top_n_sigma;top_k;typ_p;top_p;min_p;xtc;temperature)
sampler-seq | t | Simplified sampler sequence (default edskypmxt)
seed | t | RNG seed (-1 = random)
ignore-eos | f | Ignore end-of-stream token and keep generating
top-n-sigma | t | top-n-sigma sampling (-1 = disabled)
xtc-probability | t | XTC probability (0 = disabled)
xtc-threshold | t | XTC threshold (default 0.10, 1.0 = disabled)
typical-p | t | Locally typical sampling p (1.0 = disabled)
repeat-last-n | t | Last n tokens to penalize (default 64, 0 = disabled)
frequency-penalty | t | Alpha frequency penalty (0 = disabled)
dry-multiplier | t | DRY multiplier (0 = disabled)
dry-base | t | DRY base value (default 1.75)
dry-allowed-length | t | DRY allowed length (default 2)
dry-penalty-last-n | t | DRY penalty for the last n tokens (default 64)
dry-sequence-breaker | t | DRY sequence breaker; "none" for no breakers
adaptive-target | t | adaptive-p target probability 0.0-1.0 (negative = disabled)
adaptive-decay | t | adaptive-p decay 0.0-0.99 (default 0.90)
dynatemp-range | t | Dynamic temperature range (0 = disabled)
dynatemp-exp | t | Dynamic temperature exponent (default 1.00)
mirostat | c:0,1,2 | Mirostat sampling: 0 off, 1 Mirostat, 2 Mirostat 2.0
mirostat-lr | t | Mirostat learning rate eta (default 0.10)
mirostat-ent | t | Mirostat target entropy tau (default 5.00)
logit-bias | t | TOKEN_ID(+/-)BIAS, e.g. 15043+1
grammar | t | BNF-like grammar to constrain generations
grammar-file | p | File to read grammar from
json-schema | t | JSON schema to constrain generations
json-schema-file | p | File containing a JSON schema
backend-sampling | f | Backend sampling (experimental)

## Chat, reasoning & templates
chat-template | t | Built-in template name or inline Jinja template
chat-template-kwargs | t | Extra template params as a JSON object string
reasoning | c:on,off,auto | Use reasoning/thinking in chat
reasoning-format | c:none,deepseek,deepseek-legacy,auto | How thought tags are extracted/returned
reasoning-effort | t | default, minimal, low, medium, high, xhigh or max
reasoning-budget | t | Thinking token budget: -1 unrestricted, 0 end immediately, N tokens
reasoning-budget-message | t | Message injected before end-of-thinking when the budget is exhausted
reasoning-preserve | b | Keep reasoning trace in the full history
skip-chat-parsing | b | Force a pure content parser
prefill-assistant | b | Prefill the assistant response if the last message is an assistant message
escape | b | Process escape sequences (\n, \t, ...) (default true)
special | f | Output special tokens
spm-infill | f | Suffix/Prefix/Middle pattern for infill
reverse-prompt | t | Halt generation at PROMPT

## Multimodal
mmproj-url | t | URL to a multimodal projector file
mmproj-auto | b | Use multimodal projector if available (useful with -hf)
mmproj-device | t | Device for the projector (none = don't offload)
image-min-tokens | t | Min tokens per image (dynamic-resolution vision models)
image-max-tokens | t | Max tokens per image (dynamic-resolution vision models)
mtmd-batch-max-tokens | t | Max image tokens per batch when encoding (default 1024)
video-fps | t | Target video frame rate (default 4.0)
video-timestamp-interval | t | Milliseconds between text timestamps (default 5000)
video-ffmpeg-dir | p:dir | Directory containing ffmpeg and ffprobe

## Model source & adapters
model-url | t | Model download URL
hf-repo | t | Hugging Face repo user/model[:quant]
hf-file | t | Hugging Face model file (overrides quant in hf-repo)
hf-token | t | Hugging Face access token
docker-repo | t | Docker Hub model repository [repo/]model[:quant]
offline | f | Offline mode: use cache only, no network
lora | p | LoRA adapter path (comma-separated for several)
lora-scaled | t | LoRA adapters with scale: FNAME:SCALE,...
lora-init-without-apply | f | Load LoRA adapters without applying them
control-vector | p | Control vector (comma-separated for several)
control-vector-scaled | t | Control vectors with scale: FNAME:SCALE,...
control-vector-layer-range | t | Layer range START END (inclusive)
lookup-cache-static | p | Static lookup cache for lookup decoding
lookup-cache-dynamic | p | Dynamic lookup cache for lookup decoding

## Speculative decoding
spec-type | t | Comma list: none, draft-simple, draft-eagle3, draft-mtp, draft-dflash, draft-dspark, ngram-simple, ngram-map-k, ngram-map-k4v, ngram-mod, ngram-cache
spec-draft-model | p | Draft model for speculative decoding
spec-draft-hf | t | Hugging Face repo for the draft model
spec-draft-n-max | t | Tokens to draft (default 3)
spec-draft-n-min | t | Minimum draft tokens (default 0)
spec-draft-n-ubatch | t | Physical batch size of the draft context (0 = same as ubatch)
spec-draft-p-split | t | Split probability (default 0.10)
spec-draft-p-min | t | Minimum probability, greedy (default 0.00)
spec-draft-sampling | c:greedy,probabilistic | How the draft is sampled
spec-draft-backend-sampling | b | Offload draft sampling to the backend (default enabled)
spec-draft-ngl | t | Draft model GPU layers: number, auto or all
spec-draft-device | t | Devices for the draft model
spec-draft-type-k | c:f32,f16,bf16,q8_0,q4_0,q4_1,iq4_nl,q5_0,q5_1 | KV cache type K for the draft model
spec-draft-type-v | c:f32,f16,bf16,q8_0,q4_0,q4_1,iq4_nl,q5_0,q5_1 | KV cache type V for the draft model
spec-draft-threads | t | Draft generation threads
spec-draft-threads-batch | t | Draft batch/prompt threads
spec-draft-cpu-mask | t | Draft CPU affinity mask
spec-draft-cpu-range | t | Draft CPU range lo-hi
spec-draft-cpu-strict | c:0,1 | Strict CPU placement for draft
spec-draft-prio | c:0,1,2,3 | Draft thread priority
spec-draft-poll | c:0,1 | Polling for draft work
spec-draft-cpu-mask-batch | t | Draft batch CPU affinity mask
spec-draft-cpu-strict-batch | c:0,1 | Strict placement for draft batch threads
spec-draft-prio-batch | c:0,1,2,3 | Draft batch thread priority
spec-draft-poll-batch | c:0,1 | Polling for draft batch work
spec-draft-override-tensor | t | Tensor buffer overrides for the draft model
spec-draft-cpu-moe | f | Keep all draft MoE weights in CPU
spec-draft-n-cpu-moe | t | Keep MoE weights of the first N draft layers in CPU
spec-ngram-mod-n-min | t | ngram-mod min ngram tokens (default 48)
spec-ngram-mod-n-max | t | ngram-mod max ngram tokens (default 64)
spec-ngram-mod-n-match | t | ngram-mod lookup length (default 24)
spec-ngram-simple-size-n | t | ngram-simple lookup n-gram length (default 12)
spec-ngram-simple-size-m | t | ngram-simple draft m-gram length (default 48)
spec-ngram-simple-min-hits | t | ngram-simple minimum hits (default 1)
spec-ngram-map-k-size-n | t | ngram-map-k lookup n-gram length (default 12)
spec-ngram-map-k-size-m | t | ngram-map-k draft m-gram length (default 48)
spec-ngram-map-k-min-hits | t | ngram-map-k minimum hits (default 1)

## Server, API & security
embeddings | f | Embedding-only mode (dedicated embedding models)
reranking | f | Enable the reranking endpoint
pooling | c:none,mean,cls,last,rank | Pooling type for embeddings
embd-normalize | t | Embedding normalisation (default 2 = euclidean)
alias | t | Model name aliases for the API, comma-separated
tags | t | Informational model tags, comma-separated
reuse-port | f | Allow multiple sockets on the same port
path | p:dir | Directory to serve static files from
api-prefix | t | Path prefix the server serves from (no trailing slash)
cors-origins | t | Allowed CORS origins (default *; 'localhost' reflects localhost only)
cors-methods | t | Allowed CORS methods
cors-headers | t | Allowed CORS headers
cors-credentials | b | Allow CORS credentials (default enabled)
timeout | t | Read/write timeout in seconds (default 3600)
sse-ping-interval | t | SSE ping interval in seconds (-1 disabled, default 30)
api-key | t | API key(s), comma-separated
api-key-file | p | File with API keys, one per line
ssl-key-file | p | PEM SSL private key
ssl-cert-file | p | PEM SSL certificate
ui-config | t | JSON with default UI settings
ui-config-file | p | JSON file with default UI settings
ui-mcp-proxy | b | Experimental MCP CORS proxy (untrusted environments: keep off)
tools | t | Experimental built-in agent tools (or "all"); keep off in untrusted environments
tools-runtime | t | Experimental: run tools in docker:<image>, podman:<image> or ssh:<target>
mcp-servers-json | t | Experimental inline MCP server definitions (JSON)
agent | b | Enable CORS proxy and all built-in tools (untrusted environments: keep off)
connect | f | Experimental peer-to-peer tunnel via llama-connect
connect-code | t | 40-character code for connect
props | f | Allow changing global properties via POST /props
slots | b | Slots monitoring endpoint (default enabled)
media-path | p:dir | Directory for local media files (file:// URLs)
models-dir | p:dir | Router mode: directory containing models
models-preset | p | Router mode: INI file with model presets
models-max | t | Router mode: max models loaded at once (default 4, 0 = unlimited)
models-autoload | b | Router mode: automatically load models

## Logging
log-disable | f | Disable logging
log-file | p | Log to file
log-jsonl | b | Log as JSONL on stdout (disables colors)
log-colors | c:on,off,auto | Colored logging
verbose | f | Verbosity infinity (log everything)
verbosity | c:0,1,2,3,4,5 | Log threshold: 0 generic, 1 error, 2 warning, 3 info, 4 trace, 5 debug
log-prefix | b | Prefix in log messages
log-timestamps | b | Timestamps in log messages
log-prompts-dir | p:dir | Directory to log prompts into (debugging)
"""

def parse_adv(spec):
    # 'key | kind[:extra] | help' lines under '## Group' headers; kind: t text, c choice, f flag, b on/off, p path
    groups = []
    for ln in spec.strip().splitlines():
        ln = ln.strip()
        if not ln:
            continue
        if ln.startswith("## "):
            groups.append((ln[3:], []))
            continue
        key, kind, hlp = [p.strip() for p in ln.split("|", 2)]
        extra = None
        if ":" in kind:
            kind, extra = kind.split(":", 1)
        groups[-1][1].append((key, kind, extra, hlp))
    return groups

ADV_GROUPS = parse_adv(ADV_SPEC)

MCP_CHOICES = ["default", "on", "off"]
