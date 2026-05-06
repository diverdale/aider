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
