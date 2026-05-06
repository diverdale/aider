# Local LLMs with Aider

This fork is positioned around **local LLM use** — running aider against models served by Ollama, LM Studio, llama.cpp, or any OpenAI-compatible local server. Local models are a different beast from frontier models (Claude, GPT-4, Gemini); they have weaker instruction following, lossier tool calling, and quirkier output formatting. This document captures what actually works and how to get there.

---

## Quick recommendations by hardware

| VRAM available | Best general model | Best tool-capable model | Best coder model |
|---|---|---|---|
| 4-8 GB | `llama3.2:3b` | `llama3.2:3b` | `qwen2.5-coder:7b` |
| 8-12 GB | `llama3.1:8b` | `llama3.1:8b` or `hermes3:8b` | `qwen2.5-coder:7b` |
| 12-24 GB | `mistral-nemo:12b` | `mistral-nemo:12b` or `qwen2.5:14b` | `qwen2.5-coder:14b` |
| 24-48 GB | `qwen2.5:32b` | `command-r:35b` | `qwen2.5-coder:32b` or `qwen3-coder:30b` |
| 48+ GB | `llama3.1:70b` | `llama3.1:70b` or `firefunction-v2:70b` | `deepseek-coder-v2:33b` |

The "best coder" column doesn't always overlap with "best tool-capable" — see the [naming trap](#the-coder-naming-trap) below.

---

## The coder naming trap

The most surprising thing about choosing a local model for aider: **`-coder` fine-tunes drop tool-calling support.** This trips up everyone who expects "of course the coder model is the best for aider."

| Model | Tool calling | Code quality |
|---|---|---|
| `qwen2.5:14b` (base) | ✓ | Good |
| `qwen2.5-coder:14b` | ✗ | Better for code, but no MCP |
| `qwen3:14b` (base) | ✓ | Good |
| `qwen3-coder:30b` | ✗ | Best code locally, no MCP |
| `deepseek-v3` | ✓ | Strong |
| `deepseek-coder-v2:33b` | ✗ | Excellent code, no MCP |

**The tradeoff:** if you want MCP servers / tool calling in aider, use the **base** model (no `-coder` suffix). If you want pure code quality and don't care about tools, the `-coder` variants are usually 1-2 tiers stronger.

You can run both side by side — point one terminal at a base model for MCP-heavy work, another at a coder variant for pure code editing.

---

## Tool-capable Ollama models

A non-exhaustive list of models that work with the MCP integration today (verified via `litellm.supports_function_calling`):

| Model | Size | Notes |
|---|---|---|
| `llama3.1:8b` | ~5 GB | The reference small tool-capable model. |
| `llama3.2:3b` | ~2 GB | Tiniest tool-capable option. Tool calls work, tool *selection* is rougher. |
| `llama3.1:70b` | ~40 GB | Frontier-quality tool calls, frontier hardware needs. |
| `mistral-nemo:12b` | ~7 GB | Best 12B for MCP. Better instruction following than `llama3.1:8b`. |
| `qwen2.5:7b` / `:14b` / `:32b` / `:72b` | 4-45 GB | **Base** qwen2.5 (NOT `-coder`) supports tools. |
| `firefunction-v2:70b` | ~40 GB | Purpose-built for tool calling. Highest tool-call accuracy locally. |
| `command-r:35b` | ~20 GB | Cohere's tool-tuned model. Strong grounded responses + tool calls. |
| `hermes3:8b` | ~5 GB | NousResearch fine-tune of llama3.1, specifically tuned for function calling. Often beats vanilla `llama3.1:8b` on tool tasks. |

### Verifying before you `ollama pull`

```bash
python -c "from litellm import supports_function_calling; print(supports_function_calling('ollama/<model>'))"
```

Bulk check:

```bash
for m in llama3.1:8b mistral-nemo:12b qwen2.5:14b hermes3:8b; do
  echo -n "$m: "
  python -c "from litellm import supports_function_calling; print(supports_function_calling('ollama/$m'))"
done
```

`True` means aider's MCP path will use the model. `False` means you'll get the *"Model does not support tool calling"* warning when MCP is configured.

---

## Hardware sizing for popular models

Quantization makes the difference between "fits on a laptop GPU" and "needs a workstation." Ollama defaults to Q4_0 quantization on most tags, which is the right balance of quality vs size for daily use.

| Model (Q4_0) | VRAM needed | Realistic hardware |
|---|---|---|
| `llama3.2:3b` | ~2 GB | Any modern GPU; even integrated graphics with shared RAM |
| `llama3.1:8b`, `hermes3:8b`, `qwen2.5-coder:7b` | ~5 GB | RTX 3060 12 GB, M2/M3 with 16 GB unified |
| `mistral-nemo:12b`, `qwen2.5:14b` | ~7-9 GB | RTX 3070+, 4070+, M2 Pro+ |
| `qwen2.5:32b`, `qwen3-coder:30b`, `command-r:35b` | ~20 GB | RTX 3090/4090 24 GB, M3 Max 32 GB+ |
| `llama3.1:70b`, `firefunction-v2:70b` | ~40 GB | 2×4090, RTX A6000, Mac Studio 64 GB+, A100 cloud |

**Rule of thumb:** model size in GB ≈ minimum VRAM for Q4. Add 2-4 GB headroom for context window.

### When VRAM is tight

Ollama can split between GPU and CPU automatically. The GPU runs as many layers as fit; the rest stay on CPU. The downside is **enormous** speed loss — typical drop is from 30-40 tokens/sec (full GPU) to 1-3 tokens/sec (CPU-heavy split). Useful for one-off testing, painful for daily use.

Apple Silicon's unified memory architecture mostly avoids this tradeoff: a 64 GB Mac Studio runs 70B models smoothly even though there's no discrete GPU, because the same memory pool serves CPU and GPU. The catch is that token throughput is 2-3× slower than a comparable Nvidia setup.

---

## Edit-format defaults per model

Local models reliably follow the `diff` edit format but produce double-spaced output (and other artifacts) when emitting whole files. The fork ships `edit_format: diff` defaults in `aider/resources/model-settings.yml` for known-tricky models — currently `qwen3-coder:30b`, with more to come as they're verified.

To check a model's effective edit format, look at the aider startup banner. If you don't see the model in the model-settings file, aider falls back to its generic default (usually `whole`), which is what produces the double-spacing artifact for weak local models.

If you find a model that works better with a specific edit format, the fix is a 5-line addition to `model-settings.yml`:

```yaml
- name: ollama/<model-tag>
  edit_format: diff
```

---

## Choosing a local server

Aider doesn't care which local server hosts your model — it just needs an OpenAI-compatible endpoint (or Ollama's native API). The four common options have very different characteristics for aider's usage pattern (long sustained sessions, growing context, frequent tool calls):

| Server | Ease of setup | Speed in aider | Best for |
|---|---|---|---|
| **Ollama** | Easiest — one-liner install, `ollama pull` per model | Good if configured (see footguns below); poor at defaults | Casual / first-time users; one-command workflow |
| **llama.cpp** (`llama-server`) | Manual GGUF download + flags | Fastest sustained throughput; lowest overhead | Daily-driver setups where startup time isn't a concern |
| **LM Studio** | Easy — GUI for download + serve | Comparable to Ollama | Users who prefer a GUI over CLI for model management |
| **vLLM** | Hardest — Python install, CUDA setup | Best for batched/multi-user; overkill for solo | Teams sharing a GPU server |

### Ollama footguns

Three default settings hurt aider performance specifically. Fix all three with environment variables:

```bash
export OLLAMA_CONTEXT_LENGTH=8192   # default is 2048 — silently truncates aider repomap
export OLLAMA_KEEP_ALIVE=24h        # default is 5min — model evicts mid-session, slow reload
export OLLAMA_NUM_PARALLEL=2        # allows aider + a scratch session simultaneously
```

Persist these in `~/.bashrc` or your Ollama systemd service. Restart Ollama after setting.

For per-model context overrides, create a Modelfile:

```
FROM qwen3-coder:30b
PARAMETER num_ctx 16384
```

```bash
ollama create qwen3-coder-16k -f Modelfile
aider --model ollama/qwen3-coder-16k
```

### llama.cpp setup for aider

Download a GGUF from HuggingFace, then start `llama-server`:

```bash
llama-server \
  --model ~/models/qwen3-coder-30b-q4.gguf \
  --n-gpu-layers 99 \
  --ctx-size 16384 \
  --threads 12 \
  --port 8080 \
  --host 0.0.0.0
```

`--n-gpu-layers 99` means "fit as many layers on GPU as possible" — llama.cpp will auto-determine. Adjust `--threads` to match your physical core count.

In aider:

```yaml
# ~/.aider.conf.yml
model: openai/qwen3-coder-30b
openai-api-base: http://localhost:8080/v1
openai-api-key: dummy
```

The API key satisfies aider's "is auth set?" check — llama.cpp ignores it.

### LM Studio setup for aider

LM Studio includes a built-in OpenAI-compatible server (toggle from the GUI, default port 1234):

```yaml
model: openai/<model-name-from-lm-studio>
openai-api-base: http://localhost:1234/v1
openai-api-key: dummy
```

The model name in aider must match what LM Studio shows in its server panel.

### vLLM (mostly skip unless you need it)

vLLM shines at batched inference for multi-user serving. For solo aider use it offers no meaningful speed advantage over llama.cpp and is significantly harder to set up. Worth considering if you're hosting a model for a team to share.

### Practical recommendation

For most fork users:

1. **Start with Ollama** — one-line install, easiest path. Set the three env vars above on day 1.
2. **Switch to llama-server** if you find Ollama overhead bothering you in long sessions, or if you want max throughput on whatever GGUF quant you choose.
3. **Use LM Studio** if you prefer a GUI for model management.

Aider's `model-settings.yml` entries (e.g., `edit_format: diff` for qwen3-coder) apply across all backends, since they're keyed by model name regardless of which server hosts it.

---

## Context window limits — three different settings

A common confusion: aider has multiple settings that each look like "the context limit," but they control different things and the *real* ceiling is whichever is smallest. Hitting a "context limit reached" error around 27K-32K despite setting `max_chat_history_tokens: 180000` is the classic symptom.

### The three limits

| Setting | What it actually controls | Default |
|---|---|---|
| `max_chat_history_tokens` (aider config) | Threshold at which aider summarizes old chat turns via the weak model. **Not** the model's context window. | 16384 |
| `OLLAMA_CONTEXT_LENGTH` (Ollama) / `--ctx-size` (llama.cpp) | The actual KV cache size the inference server allocates per session. **This is the real hardware-side ceiling.** | 2048 (Ollama!) / unset on llama.cpp (must specify) |
| litellm's known context for the model | What aider thinks the model can accept. Used for token-budget calculations and the pre-flight "context limit reached" check. | Unknown for non-canonical names like `openai/qwen3-coder-30b` → falls back to a sane default (~32K) |

The error happens whichever fires first. If your inference server is at 8K, you hit 8K. If litellm thinks the model is 32K, you hit ~27K (32K minus output reservation and prompt buffer). Setting `max_chat_history_tokens` to 180000 doesn't help if neither of the other two limits matches.

### The "Unknown context window size" warning is the giveaway

If aider prints this on startup:

```
Warning for openai/qwen3-coder-30b: Unknown context window size and costs, using sane defaults.
```

…that means **litellm has no entry for your model**. It's using a fallback context size (typically 32K), which is why you hit 27K-ish in practice. Fix it by telling litellm what the model actually supports.

### Telling litellm the real context size

Create `~/.aider.model.metadata.json`:

```json
{
  "openai/qwen3-coder-30b": {
    "max_tokens": 32768,
    "max_input_tokens": 32768,
    "max_output_tokens": 4096,
    "input_cost_per_token": 0,
    "output_cost_per_token": 0
  },
  "ollama/qwen3-coder:30b": {
    "max_tokens": 32768,
    "max_input_tokens": 32768,
    "max_output_tokens": 4096,
    "input_cost_per_token": 0,
    "output_cost_per_token": 0
  }
}
```

Pick `max_input_tokens` to match what your inference server is configured for, not the model's training maximum. qwen3-coder's training context is 256K but most users can't allocate that much KV cache.

### Telling the inference server to actually allocate that much

**Ollama:**

```bash
export OLLAMA_CONTEXT_LENGTH=32768
```

Restart Ollama. Or per-model via Modelfile:

```
FROM qwen3-coder:30b
PARAMETER num_ctx 32768
```

**llama-server:**

```bash
llama-server --model qwen3-coder-30b.gguf \
  --n-gpu-layers 99 \
  --ctx-size 32768 \
  ...
```

### KV cache VRAM cost

Context window costs VRAM separately from the model weights themselves. Rough cost for the KV cache of a 30B-class model at Q4:

| Context | KV cache size |
|---|---|
| 8K | ~1 GB |
| 16K | ~2 GB |
| 32K | ~4 GB |
| 64K | ~8 GB |
| 128K | ~16 GB |
| 256K | ~32 GB |

These numbers double for 70B models, halve for 14B models. If your hardware has the model occupying 20 GB out of 24 GB available, your KV cache budget is ~4 GB → **32K is your realistic ceiling**, regardless of what the model can technically do.

To get *bigger* effective context on hardware-limited setups, drop to a smaller model with more headroom (e.g., `mistral-nemo:12b` can comfortably hold 64K-128K context on a single 24 GB GPU).

### Quick checklist when you hit a context wall

1. Did you see the "Unknown context window size" warning at startup? → Add the metadata JSON entry.
2. Is `OLLAMA_CONTEXT_LENGTH` set, or is `llama-server --ctx-size` flag specified? → Default Ollama is 2048; default llama-server is 4096. Both are too small.
3. Did you restart the inference server after changing context settings? Required.
4. Is the requested context realistic for your VRAM? Use the table above.
5. Is `max_chat_history_tokens` reasonable (e.g., 50-75% of your real model context)? Aider summarizes when chat exceeds this, so setting it too low causes premature summarization; too high lets the chat fill the model context with no summarization headroom.

---

## Realistic limitations

These aren't bugs in aider — they're properties of the models themselves, and worth knowing before you commit to a local-only workflow:

- **Tool calls fail more often than on Claude/GPT.** Even "tool-capable" local models will sometimes emit malformed JSON, pick the wrong tool, or loop on the same call. The smaller the model, the worse it gets.
- **Edit-format compliance is shakier.** Models that should emit `SEARCH/REPLACE` blocks sometimes emit prose descriptions of changes instead. The fix is usually swapping edit format, not switching models.
- **Context windows are smaller.** Most local models cap at 32K-128K context vs 200K-1M for frontier models. Large repomaps may not fit.
- **Architect mode is risky.** Two model passes amplify hallucinations. If you've configured aider with `chat-mode: architect` and a small local model is the architect, expect the editor to obediently apply hallucinated changes.
- **Conventions files don't always work.** Weak instruction-following models ignore prose-level rules (e.g., "always use 4-space indent"). Format-level constraints (e.g., `--edit-format diff`) are more reliable.

The general posture: **local models are real and usable, but they need the surrounding tooling to be more opinionated than frontier models do.** That's the niche this fork fills.

---

## Reporting model results

If you find a model that works particularly well or particularly badly, consider opening an issue on this fork's repo. The matrix above will only stay accurate if real users contribute their findings. Useful information to include:

1. Model name (Ollama tag, exact spelling).
2. Hardware (GPU model + VRAM, or Apple Silicon variant).
3. Edit format that worked best (`diff`, `whole`, etc.).
4. Whether tool calling worked (yes / no / yes-but-flaky).
5. Approximate tokens/sec on your hardware.
