# Aider MCP Support — Roadmap

## Goal

Add Model Context Protocol (MCP) support to aider so users can plug in any MCP-compliant tool server (filesystem, github, postgres, linear, slack, ...) and have those tools available regardless of which model they're talking to. The strategic angle: aider already has the best multi-provider story via litellm; MCP makes that story matter for tool use too. One config, every model, every tool.

## Why MCP

- **Industry standard.** Claude Code, opencode, Cursor, Zed, etc. all speak MCP. Without it, aider feels increasingly behind on integrations.
- **Decouples tools from models.** A linear MCP server works whether you're on Claude, GPT-4, Gemini, or DeepSeek — same config, same UX.
- **Plays to existing strengths.** litellm already abstracts tool-calling across providers; MCP fills in the integration side.
- **Skills synergy.** Skills + MCP = a skill can declare "I need MCP server X" as a dependency; the marketplace handles distribution.

## Architectural fit

Tools are **orthogonal to edit format**. Today's coders parse model text into file edits — that stays. MCP adds a parallel channel: when the model emits a tool call, aider executes it via the right server and feeds the result back into the conversation. The model can interleave file edits and tool calls freely.

The natural seam is in `aider/coders/base_coder.py::show_send_output_stream` — that's where tool calls would be detected and dispatched. litellm already handles the wire format across providers.

## Phased plan

### Phase 0 — Research & decisions

**Output:** a `docs/mcp/research.md` capturing concrete decisions, not a wall of background.

- Pin the MCP Python SDK version (`mcp` on PyPI). Read its README and the linked spec.
- Confirm v1 transport choice. **Default: stdio-only.** HTTP/SSE in a follow-up; some community servers don't yet support the new streamable HTTP transport.
- Pick 3 "hero" servers to demo with. Candidates: `@modelcontextprotocol/server-filesystem`, `mcp-server-git`, `github-mcp-server`. The chosen three drive the integration-test design.
- Read how Claude Code and opencode wire MCP into their loops. Don't copy — extract patterns and rejection criteria.
- Decide: where does MCP server config live? Default: `~/.aider/mcp.yml`, with project-local override `./.aider/mcp.yml` (mirrors the skills directory layout).

**Verification:** the document answers, for each open question, "v1 chooses X because Y."

### Phase 1 — MCP client subsystem (3–4 days)

**Output:** aider can connect to a configured MCP server, list its tools, and report status. No model integration yet.

- New module `aider/mcp/`:
  - `client.py` — per-server `ClientSession` (use the official SDK; do not roll your own JSON-RPC).
  - `manager.py` — orchestrates N servers, lifecycle (start/stop/restart), exposes the union of tools.
  - `config.py` — load + validate `mcp.yml`.
- Server config format (initial draft):
  ```yaml
  servers:
    filesystem:
      command: npx
      args: ["-y", "@modelcontextprotocol/server-filesystem", "/path/to/dir"]
    github:
      command: docker
      args: ["run", "-i", "--rm", "ghcr.io/github/github-mcp-server"]
      env:
        GITHUB_PERSONAL_ACCESS_TOKEN: $GITHUB_TOKEN
  ```
- Slash commands:
  - `/mcp list` — show configured servers and their state (running, crashed, idle).
  - `/mcp tools [server]` — list discovered tools (name, description, input schema).
  - `/mcp restart <name>` — restart a server.
- Servers start lazily on first use, not at aider boot, to keep startup fast.
- Tests: at least one fake MCP server (or use the SDK's test harness) that exercises connect → list-tools → disconnect.

**Verification:** with a real filesystem MCP server in `mcp.yml`, `/mcp tools` lists `read_file`, `list_directory`, etc. with correct schemas.

### Phase 2 — Tool execution path (3–5 days)

**Output:** the model can call MCP tools mid-conversation, see results, and continue.

- Convert MCP tool definitions to litellm tool schemas (mostly 1:1; well documented in litellm).
- Pass tools to `litellm.completion(tools=[...])` in `aider/sendchat.py`.
- In the streaming chunk loop in `base_coder.show_send_output_stream`, detect tool-call deltas. Buffer until complete, then:
  - Resolve which server owns the tool.
  - Execute via the SDK's `session.call_tool(name, args)`.
  - Append the tool result as an assistant message with `role: tool`.
  - Re-enter the completion loop so the model can react to the result.
- Cap tool-call iterations per user turn (default: 10) to prevent runaway loops.
- Render tool calls inline in the chat: `→ filesystem.read_file("README.md")` style, with the result shown collapsed.

**Verification:** prompt "read README.md and summarize" triggers `read_file`, model receives content, summary appears. Same prompt against three different providers (Claude, GPT, an open model) all work.

### Phase 3 — Permission model (2–3 days)

**Output:** users can trust running MCP servers without fear of silent destructive operations.

- Three modes per tool: `auto` / `ask` / `deny`.
- Defaults derived from the tool's MCP annotations:
  - `readOnlyHint: true` → `auto`.
  - Anything else, or unannotated → `ask`.
- Prompt UI reuses `io.confirm_ask` with the (server, tool, args) summary. Options: yes / no / always-this-tool / always-this-server / never.
- Per-server defaults overridable in `mcp.yml`:
  ```yaml
  servers:
    github:
      command: ...
      permissions:
        get_issue: auto
        create_issue: ask
        delete_repository: deny
  ```
- Persistent "always" / "never" decisions stored per-project (`.aider/mcp-permissions.json`).

**Verification:** `read_file` runs silently. `create_issue` prompts. `delete_repository` declines without prompting.

### Phase 4 — Polish & integration (2–3 days)

**Output:** MCP feels like a first-class part of aider, not a bolt-on.

- `/mcp logs <server>` shows recent JSON-RPC traffic. Debug-critical when servers misbehave.
- Tool-call output counts against context budget; surface in repomap budgeting (`aider/repomap.py`).
- Graceful degradation: model without tool support → MCP disabled with a clear `tool_warning`, not a crash. Use litellm's `supports_function_calling()` per model.
- Documentation page (`docs/mcp.md`) + 2–3 worked examples (filesystem, git, github).
- Add `--mcp-config <path>` CLI flag for one-off config files.

**Verification:** new user can read the docs and have a working filesystem-server-backed session in under 5 minutes.

### Phase 5 — Distribution & ecosystem (post-v1)

**Output:** users discover MCP servers as easily as they discover skills.

- Curated list of recommended servers in docs.
- Skills can declare MCP server dependencies in their frontmatter; the install flow surfaces "this skill requires server X — install instructions: Y" without auto-installing arbitrary processes.
- Long-term: HTTP/SSE transport, OAuth flows for hosted servers (linear, slack), prompt resources (the third pillar of MCP, ignored in v1).

## Key risks

1. **Provider tool-use parity is uneven.** Some openrouter/local models don't support tool calls. v1 must fail with a clear error when MCP is configured but the active model can't use it. Lean on `litellm.supports_function_calling()`.
2. **MCP spec evolution.** The spec is still maturing (transport changes, auth flows, new annotations). Pin the SDK version, document the compatibility window, plan for one breaking-change upgrade per year.
3. **Process lifecycle is the unsexy hard part.** Servers crash, hang, leak file descriptors, write garbage to stderr. Use the official SDK's `ClientSession` rather than rolling JSON-RPC handling — it covers handshake, heartbeats, shutdown.
4. **Security.** MCP servers are arbitrary code. The Phase 3 permission model is non-negotiable, not nice-to-have. Default-deny for destructive ops.
5. **Streaming UX.** Tool calls mid-stream are messy. The ANSWER stream pauses, tool runs, stream resumes. The renderer (`MarkdownStream`, recently debugged) needs to handle the pause-resume cleanly.

## Success criteria for v1

- A user with no MCP background can read `docs/mcp.md`, drop a `mcp.yml` in `~/.aider/`, and have a working filesystem-backed conversation against any tool-supporting model in under 5 minutes.
- The 3 hero servers (filesystem, git, github) all work reliably across at least 3 model providers.
- A community member can write a SKILL.md that says "this skill depends on the linear MCP server" and have it work end-to-end.
- No silent destructive operations possible from a default config.

## What's explicitly NOT in v1

- HTTP/SSE / streamable HTTP transport (stdio only).
- MCP `prompts` (the third capability) — tools are enough to ship.
- Auto-discovery / registry of MCP servers (community-curated YAML stays canonical).
- Sandboxing of MCP server processes beyond OS-level isolation.
- `resources` beyond what the SDK gives us for free in tool results.
