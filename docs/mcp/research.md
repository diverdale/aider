# MCP Phase 0 — Research & Decisions

**Status:** Decisions locked for v1 implementation.
**Date:** 2026-04-30
**Authors:** dalwrigh (with Claude assistance)

This document is the output of Phase 0 of the MCP support roadmap (`docs/mcp-support-roadmap.md`). For each open question, it records what v1 will do and the one-sentence rationale.

## Sources consulted

- MCP spec: <https://modelcontextprotocol.io/docs/concepts/transports> (current protocol version `2025-06-18`).
- MCP Python SDK: <https://github.com/modelcontextprotocol/python-sdk>.
- Claude Code MCP behavior, surveyed via the official `/docs/en/mcp` reference.
- Aider's existing skills subsystem (`aider/skills.py`) for config-layout precedent.

## Decision log

### D1. Transport for v1: **stdio only**

**Why.** The current spec defines exactly two standard transports: stdio and Streamable HTTP. The spec is explicit that "clients SHOULD support stdio whenever possible," and stdio is what every community server we'd ship demos for already supports (filesystem, git, github CLI, etc.). Streamable HTTP is necessary for hosted services (Linear, Slack as a service), but the Python SDK ships a streamable-HTTP client we can plug in later — same `ClientSession`, different transport context manager.

**Implication.** v1 won't talk to Linear's hosted MCP, Slack's hosted MCP, or other cloud-only servers. That's a real gap, but each requires OAuth flows we don't want in v1. v1.1 adds streamable HTTP with **bearer-token auth only**; full OAuth waits for v1.2.

**SSE is dead.** SSE was deprecated as of protocol version `2024-11-05` and replaced by Streamable HTTP. We never implement plain SSE — when we do HTTP, we go straight to streamable.

### D2. Config file location: mirror skills layout

- Global: `~/.aider/mcp.yml`
- Project: `./.aider/mcp.yml`

**Precedence.** Project entries override global entries by `name` (case-sensitive match). Project-only or global-only entries appear as-is. No "managed" or org-level scope in v1.

**Why.** Claude Code uses four scopes (local/project/user/managed); that's overkill for v1. Two scopes covers the actual user need (personal + per-project), keeps precedence trivial to reason about, and matches the skills directory layout users already learned.

### D3. Config file format

YAML, matching the existing `.aider.conf.yml` style. Initial schema:

```yaml
servers:
  filesystem:
    command: npx
    args: ["-y", "@modelcontextprotocol/server-filesystem", "/path/to/dir"]
    # Optional fields:
    env:
      EXAMPLE_TOKEN: $EXAMPLE_TOKEN_VAR     # $VAR expanded from os.environ
    permissions:                             # see D6
      write_file: ask
      delete_file: deny
    enabled: true                            # default true; set false to keep config but disable
```

**Env var expansion.** `$VAR` and `${VAR}` syntax expanded from `os.environ`. Missing var → server load fails with a clear error message, not silent empty string. Quoted as `${VAR:-default}` for explicit defaults.

**No `name` field inside the entry** — the YAML key is the canonical name.

### D4. Server lifecycle: **eager startup**

Servers spawn at aider session start. A "Starting MCP servers..." line shows progress; per-server failures log a warning but don't block session start. Servers that fail to start are marked `failed` and excluded from the tool registry; the user can `/mcp restart <name>` after fixing the issue.

**Why.** Aider sessions are long-running (hours, not seconds). Pay startup cost once, fail loudly up front. Lazy startup defers latency to the first tool call, which is a worse UX than a 1–2s session-start delay.

**Caveat.** If `enabled: false`, server is not started. If a server is configured globally but the project-local config disables it, project wins — server doesn't start.

### D5. Process management: **use the SDK, don't roll your own**

The Python SDK's `mcp.client.stdio.stdio_client(...)` is an async context manager that handles spawn, stdin/stdout wiring, and termination on exit. We use it directly. No custom subprocess code.

**stderr handling.** Servers MAY write logs to stderr. Capture per-server, expose via `/mcp logs <name>`. Don't let stderr leak to aider's main stdout (would corrupt the TUI).

**Crash handling.** If `stdio_client` raises (server died, bad initialization), catch, mark server `failed`, log the error, surface via `/mcp list`. No automatic restart in v1 — Claude Code's experience shows automatic restart on stdio creates more confusion than it solves. User explicitly runs `/mcp restart`.

### D6. Permission model

Three modes per (server, tool): `auto`, `ask`, `deny`.

**Default resolution order:**
1. Project-local persisted decision (see below) — highest precedence.
2. Per-tool override in `mcp.yml` (`servers.<name>.permissions.<tool>`).
3. Per-server default (`servers.<name>.default_permission` — `ask` if unset).
4. Tool annotation: if the SDK exposes `readOnlyHint: true` on the tool, default is `auto`.

**Confirmation UI.** Reuses `io.confirm_ask` (the one we just polished). Prompt format:

```
github.create_issue
  title: "Bug: SSL verify"
  body: "..."
Allow this tool call? (Y)es / (N)o / (A)lways for this tool / (S)kip session
```

**Persistence.** "Always for this tool" persists to `./.aider/mcp-permissions.json`:

```json
{
  "github": {
    "get_issue": "auto",
    "create_issue": "ask"
  }
}
```

**Differentiator vs Claude Code.** Claude Code does NOT persist tool approvals across sessions for MCP tools — users re-approve common operations every session. We do. This is a real ergonomic win for the multi-LLM users we're targeting.

### D7. Streaming UX during tool calls: **buffer, don't pause-resume in v1**

When the model emits a tool call mid-stream:
1. Allow the streaming text to complete (most providers emit tool calls at the end of a response chunk anyway).
2. Show a single tool-call summary line: `→ filesystem.read_file("README.md")`.
3. Run the tool, capture result.
4. Re-enter the completion loop with the tool result appended.

**No mid-stream pause-and-resume of the markdown renderer in v1.** The `MarkdownStream` we just spent a day debugging is fragile under interruption. Pretty interleaving of tool calls and assistant text waits for v1.1, gated on a clean refactor of `MarkdownStream` to handle interruption explicitly.

### D8. Tool result handling

- Results are appended to `cur_messages` as `role: "tool"` messages, per litellm's tool-use convention.
- Output >10,000 tokens (configurable via `AIDER_MCP_MAX_OUTPUT_TOKENS`): truncate, append a `[truncated, full output saved to <path>]` marker, write full output to `~/.aider/mcp-cache/<server>-<timestamp>.txt`.
- Tool-result tokens count against the same budget as chat messages — repomap budgeting in `aider/repomap.py` should subtract a reserve (e.g. 5k tokens) when MCP is active.
- Iteration cap: 10 tool calls per user turn, configurable via `--mcp-max-iterations`. Hard error on overflow ("MCP iteration limit reached; tell me what you want me to do") rather than silent stop.

### D9. Hero servers for the demo / integration test

| Server | Install via | What it tests |
|--------|-------------|---------------|
| `@modelcontextprotocol/server-filesystem` | `npx -y …` | Universal read/write; npm-based servers |
| `mcp-server-git` (Anthropic) | `uvx mcp-server-git --repository .` | Python-based servers via uvx; git read ops |
| `github-mcp-server` | `docker run -i …` | Containerized servers; env-var auth; many tools |

**Why these three.** Different install mechanisms (npx, uvx, docker) stress the config schema in v1. All three are first-party / well-maintained. None require OAuth, so they fit v1's bearer-token-only auth posture.

### D10. Provider compatibility

Use `litellm.supports_function_calling(model_name)` to detect tool-use capability. If MCP is configured but the active model doesn't support tools:

- Print a `tool_warning` at session start: "MCP is configured but `<model>` doesn't support tool calling. MCP will be inactive for this session. Switch to a tool-capable model with `/model <name>`."
- Don't crash. Don't silently disable.

**Verified tool-capable model families** (from litellm's tool-support matrix):
- Anthropic Claude 3+ (all)
- OpenAI GPT-4 family
- OpenAI o1, o3-mini (with structured outputs)
- Google Gemini 1.5+
- DeepSeek Chat (recent versions)
- Mistral Large

**Known not-supported in v1:**
- Most Ollama-hosted local models (some have tool support, support is uneven; revisit per-model)
- Older OpenRouter models
- Anthropic Claude 2.x

### D11. Slash commands

- `/mcp list` — table of configured servers, state (`running`, `failed`, `disabled`), tool count.
- `/mcp tools [server]` — list tools (name, one-line description). With `server` arg, scoped to one server; without, all.
- `/mcp restart <server>` — kill and restart one server. Clears the `failed` state.
- `/mcp logs <server> [-n 50]` — last N lines of stderr from that server, plus last N JSON-RPC exchanges.
- `/mcp info <server> <tool>` — full tool schema, permission setting, last call timestamp.

**Out of scope for v1.** `/mcp install <server>`, `/mcp search` (would need a registry, see roadmap Phase 5).

### D12. SDK pinning

Pin to the latest stable `mcp` package on PyPI at implementation time. Add to `requirements/requirements-mcp.in` (new file) so MCP support stays an opt-in install group rather than a hard dependency on every aider install. Wire as an extra: `pip install aider-chat[mcp]`.

**Why an extras group.** The `mcp` package pulls in async dependencies (`anyio`, etc.) that not every aider user needs. Keeping it optional keeps the base install lean. CI runs both with and without `[mcp]` to make sure non-MCP code paths don't accidentally import the SDK.

### D13. Implementation testability

Hardest-to-test surface: tool-use loop in `base_coder`. Plan:

- Build a fake MCP server (subclass of the SDK's server primitives) that exposes a deterministic `echo` tool. Use it in unit tests of the manager and tool-execution loop. No subprocesses needed for unit tests.
- For integration tests, use the real filesystem server against a tmp dir.
- Mock litellm's `completion()` to emit canned tool-use chunks; test the chunk-loop integration in isolation.

## Open questions deferred to implementation

These don't need answers now but are flagged so they don't get lost:

- **Q.** When a tool call's arguments include large blobs (e.g. file contents), should we still pretty-print them in the confirmation prompt? Need a sensible truncation strategy.
- **Q.** How do we surface tool-call cost? MCP calls are free locally, but they cause the model to make additional completions per turn. Should `/cost` break out "MCP-induced tokens"?
- **Q.** Skill ↔ MCP integration: the marketplace spec already mentions skills declaring MCP server deps. Concrete frontmatter shape — `mcp_servers: [github, filesystem]`? Or richer with version constraints? Decide when wiring Phase 5.

## Glossary

- **MCP server**: a process that exposes tools/resources/prompts via JSON-RPC over a transport.
- **MCP client**: aider, in this design.
- **Streamable HTTP**: the current spec's HTTP transport (replaces SSE; uses POST + optional SSE response stream + session IDs).
- **stdio**: subprocess transport using newline-delimited JSON-RPC over stdin/stdout.
- **Tool-call iteration**: one round of (model emits tool call → we execute → result fed back → model continues). Cap of 10 per user turn.
