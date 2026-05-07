# Fork Features — `diverdale/aider`

This fork adds capabilities targeted at **multi-LLM consumers** — users who use three or more model providers and care about a unified, polished terminal experience. The base aider already has the best multi-provider story in the AI-coding-CLI space (via `litellm`); this fork builds on that with extensibility, ergonomics, and trustworthy tool integration.

Most of this code was AI-paired (Claude). The fork itself is an experiment in what AI-built tooling can look like end-to-end.

## What's new

| Feature | One-line summary | Doc |
|---|---|---|
| **MCP support** | Connect any Model Context Protocol server (filesystem, git, github, linear, …) and use its tools across every model. Permission gate with persistent decisions. | [mcp.md](./mcp.md) |
| **Skills system** | Claude Code-compatible `SKILL.md` loader. Install from a URL or local path, enable/disable, auto-apply by triggers. `/skills` command family. | [skills.md](./skills.md) |
| **Color theming** | Built-in presets (dracula, solarized-dark/light, monokai, …) + custom YAML theme files. Override individual colors without breaking the theme. | [theming.md](./theming.md) |
| **Configurable status bar** | Density modes (compact / comfortable / focus), layout modes (single / split / review-first), live context-usage and progress indicators above the prompt. | [status-bar.md](./status-bar.md) |
| **Streaming markdown improvements** | XML-fence handling (`<source>python` → highlighted code block), filename-based language inference, themed code blocks, no-padding rendering. | [mdstream.md](./mdstream.md) |
| **Local-LLM defaults & guidance** | Model-by-model defaults in `model-settings.yml` for known-tricky local models (qwen3-coder defaults to `diff`). Practical hardware sizing + tool-capability matrix. | [local-models.md](./local-models.md) |
| **Shift+Enter newline** | Modern keybinding (alongside Alt+Enter). Matches muscle memory from Slack/Discord/ChatGPT/Claude Desktop. Requires terminal config; recipes included. | [keybindings.md](./keybindings.md) |

## Smaller fixes worth knowing about

**`--no-verify-ssl` actually works on modern litellm.** Upstream aider sets `os.environ["SSL_VERIFY"] = ""` which modern litellm interprets as a (nonexistent) CA-bundle path rather than "off" — so the flag silently fails for Anthropic / Gemini / OpenRouter and other providers using per-request httpx clients. This fork sets `"False"` (parseable by `str_to_bool`) and also sets `litellm.ssl_verify = False` as a fallback. See `aider/main.py:719–730` and the upstream issue [Aider-AI/aider#3702](https://github.com/Aider-AI/aider/issues/3702).

## Quick install on top of upstream aider

This fork is a soft fork — most upstream behavior is unchanged. The additions are opt-in: features only activate when you configure them (MCP requires an `mcp.yml`, theming requires `--color-theme`, etc.).

```bash
git clone https://github.com/diverdale/aider.git
cd aider
pip install -e .
pip install 'mcp>=1.27,<2'   # optional, only needed if you'll use MCP
```

## Reading order

If you only read one thing, read [mcp.md](./mcp.md) — it's the most strategically interesting feature and the most user-visible. If you're styling your terminal, [theming.md](./theming.md) and [status-bar.md](./status-bar.md). If you write your own prompts, [skills.md](./skills.md).

The roadmap and design decisions for MCP support live in `docs/mcp-support-roadmap.md`, `docs/mcp/research.md`, and `docs/mcp/phase1-integration-map.md` — those are developer-facing.
