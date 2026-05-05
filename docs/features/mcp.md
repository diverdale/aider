# MCP — Model Context Protocol Support

Aider can connect to any [MCP](https://modelcontextprotocol.io) server and expose its tools to whichever model you're chatting with. The killer property: **the same MCP server (filesystem, git, github, linear, slack, …) works regardless of provider** — Claude, GPT-4, Gemini, DeepSeek, local models with tool support, all the same. That makes aider's existing multi-provider story (via `litellm`) actually pay off for tool integrations, not just text completion.

This page is the user-facing reference. For design decisions and architecture, see `docs/mcp/research.md` and `docs/mcp/phase1-integration-map.md` in the repo.

---

## Quick start (5 minutes)

### 1. Install the MCP SDK

Not in aider's base requirements — it's an opt-in extra:

```bash
pip install 'mcp>=1.27,<2'
```

### 2. Pick a server to demo with

The official [MCP servers repo](https://github.com/modelcontextprotocol/servers) has filesystem, git, github, fetch, sqlite, etc. Filesystem is the easiest to start with (npm package, no auth, instant gratification).

### 3. Create `~/.aider/mcp.yml`

```yaml
servers:
  filesystem:
    command: npx
    args: ["-y", "@modelcontextprotocol/server-filesystem", "/path/to/your/project"]
```

Replace `/path/to/your/project` with a directory you want the model to be able to read.

### 4. Run aider with a tool-capable model

```bash
aider --model anthropic/claude-opus-4-5
```

You should see `MCP: 1/1 servers running` in the startup banner. Then ask the model something that requires reading a file:

```
> what's in README.md?
```

The model calls `mcp__filesystem__read_file`, you see a `→ filesystem.read_file` line, then a `← filesystem.read_file: <preview>` line, then the model summarizes. **First successful call: MCP is working.**

---

## Configuration

### File locations

Two files, both YAML, both optional:

| Path | Scope |
|---|---|
| `~/.aider/mcp.yml` | Global — applies to every aider session. |
| `./.aider/mcp.yml` | Project-local — overrides the global file by server name. |

If neither exists, MCP is silently inactive (no error, no warning). If both exist and define the same server name, the project file wins for that server; the global file's other servers still apply.

### Schema

```yaml
servers:
  <server-name>:
    command: <executable>            # required
    args: [<arg>, <arg>, ...]        # optional, default []
    env:                             # optional
      VAR_NAME: <value or "${ENV_VAR}">
    enabled: true                    # optional, default true
    default_permission: ask          # optional: auto | ask | deny
    permissions:                     # optional, per-tool overrides
      <tool-name>: auto              # auto | ask | deny
      <other-tool>: deny
```

**Field reference:**

- **`command`** (required): the executable to spawn. Resolved via `PATH`.
- **`args`** (optional, default `[]`): command-line arguments passed to the server.
- **`env`** (optional): environment variables for the server process. Values can reference your shell environment with `$VAR` or `${VAR}` syntax. **A reference to an unset variable is a hard config error** — better to fail loudly than to launch a server with empty credentials.
- **`enabled`** (optional, default `true`): set to `false` to keep a server in your config but skip it at startup.
- **`default_permission`** (optional, default unset): fallback permission mode for tools that have neither a per-tool override nor a `readOnlyHint` annotation.
- **`permissions`** (optional, default `{}`): per-tool overrides keyed by tool name.

### Env var expansion

Designed for projects that share `.aider/mcp.yml` in version control while keeping secrets in `.env` or shell:

```yaml
servers:
  github:
    command: docker
    args: ["run", "-i", "--rm", "ghcr.io/github/github-mcp-server"]
    env:
      GITHUB_PERSONAL_ACCESS_TOKEN: ${GITHUB_TOKEN}   # from your shell env
```

Both `$VAR` and `${VAR}` work. `${VAR:-default}` is **not** supported in v1.

### Example: three different install mechanisms

```yaml
servers:
  filesystem:
    command: npx
    args: ["-y", "@modelcontextprotocol/server-filesystem", "/Users/me/projects"]

  git:
    command: uvx
    args: ["mcp-server-git", "--repository", "."]

  github:
    command: docker
    args: ["run", "-i", "--rm", "ghcr.io/github/github-mcp-server"]
    env:
      GITHUB_PERSONAL_ACCESS_TOKEN: ${GITHUB_TOKEN}
    default_permission: ask
    permissions:
      get_issue: auto
      create_issue: ask
      delete_repository: deny
```

---

## Slash commands

All available inside aider. They're sync wrappers around the async MCP runtime; no asyncio in your face.

### `/mcp` or `/mcp list`

Show configured servers and their state:

```
MCP servers (3):
  filesystem            running
  git                   running
  github                failed   (Authentication failed: bad token)
```

States: `running`, `failed`, `disabled`, `stopped`.

### `/mcp tools [<server>]`

List the tools each server exposes. Without an argument, shows all tools from all running servers, tagged with their origin:

```
MCP tools: 14
  filesystem.read_file               Read a file from disk.
  filesystem.list_directory          List the contents of a directory.
  git.git_status                     Show working tree status.
  git.git_diff                       Show diff between commits.
  github.get_issue                   Get a GitHub issue by number.
  ...
```

With a server argument, scopes to one server:

```
/mcp tools git
```

### `/mcp restart <server>`

Kill and respawn a server. Useful after fixing a config problem (bad token, server crashed) without restarting all of aider:

```
/mcp restart github
Restarted MCP server 'github'.
```

---

## Permissions

The permission gate runs **before every tool call**. It decides one of three modes:

- **`auto`** — run silently. The default for tools the server marks as read-only.
- **`ask`** — prompt the user. Yes/No/Always/Never/Skip options (see below).
- **`deny`** — block the call entirely. Returns an error tool message to the model so it can adapt.

### Resolution order

The mode is resolved by checking these sources in priority order (highest wins):

1. **Persisted decision** in `./.aider/mcp-permissions.json` (set by you clicking "Always for this tool" or "Deny permanently" in an earlier session).
2. **Per-tool override** in `mcp.yml` — `servers.<name>.permissions.<tool>`.
3. **Per-server default** in `mcp.yml` — `servers.<name>.default_permission`.
4. **Tool's MCP annotation** — `readOnlyHint: true` → `auto`; otherwise fall through.
5. **Hard fallback** — `ask`.

This means a careful default is always `ask`. Tools the server explicitly marks safe (read-only) auto-run; everything else prompts unless you've configured otherwise.

### The interactive prompt

When a call hits `ask` mode, you see something like:

```
MCP tool requested: filesystem.write_file({"path": "/tmp/x.txt", "content": "hello"})
  (Y)es  (N)o  (A)lways for this tool  (D)eny permanently  (S)kip session
> 
```

Decision semantics:

| Key | Effect |
|---|---|
| `Y` (or just Enter) | Run this call. No persistence. |
| `N` | Skip this call. No persistence. The model gets an error tool message. |
| `A` | Persist as `auto`. Saved to `mcp-permissions.json`; future sessions skip the prompt. |
| `D` | Persist as `deny`. Saved permanently; the model is told it's denied. |
| `S` | Skip session. Block the same `(server, tool)` for the rest of this session. No persistence. |

EOF / Ctrl-C is treated as `N` — fail closed if you can't respond.

### Persistent decisions file

`./.aider/mcp-permissions.json` lives at your project root. JSON shape:

```json
{
  "filesystem": {
    "read_file": "auto",
    "list_directory": "auto",
    "write_file": "ask"
  },
  "github": {
    "delete_repository": "deny"
  }
}
```

You can hand-edit this file. Invalid mode values (anything not in `{auto, ask, deny}`) are silently dropped on load — a corrupt file won't block aider startup. The file is rewritten with `os.replace` (atomic) every time you pick `Always` or `Deny permanently` in a prompt.

**This is the differentiator vs Claude Code**, which only remembers session-scoped approvals. Aider's persistent decisions survive restarts.

### Configuring without prompts

If you want everything pre-configured, use `mcp.yml`:

```yaml
servers:
  filesystem:
    command: npx
    args: [...]
    default_permission: auto       # everything auto-runs (read-only server)

  github:
    command: docker
    args: [...]
    default_permission: ask        # default: prompt
    permissions:
      get_issue: auto              # cheap reads run silently
      list_pull_requests: auto
      create_issue: ask            # confirm before creating things
      delete_repository: deny      # never let the model touch this
```

---

## Tool naming convention

Aider namespaces tools when sending them to the model:

```
mcp__<server>__<tool>
```

For example, the filesystem server's `read_file` tool is presented to the model as `mcp__filesystem__read_file`. When the model calls it, aider parses the prefix back to route the call to the right server.

This convention matches what Claude Code and opencode use, so models that have seen MCP-flavored tools elsewhere recognize the pattern. Server names cannot contain `__`; tool names can (the split is on the **first** `__` after the `mcp__` prefix).

---

## Provider compatibility

MCP only works for models that support OpenAI-style tool calling. Aider gates on `litellm.supports_function_calling(model_name)`:

**Verified working:**

- Anthropic Claude 3+ (all variants, including Opus / Sonnet / Haiku)
- OpenAI GPT-4 family, GPT-4o, GPT-5
- OpenAI o1 / o3-mini (with structured outputs enabled)
- Google Gemini 1.5+
- DeepSeek Chat (recent versions)
- Mistral Large

**Not supported in v1:**

- Most Ollama-hosted local models (tool support is uneven; some work, most don't)
- Older OpenRouter free-tier models
- Anthropic Claude 2.x

If you start aider with an MCP config but the active model can't use tools, you'll see a one-time warning at session start:

```
Model 'openrouter/some/free-model' does not support tool calling. MCP tools are configured but inactive for this session. Switch to a tool-capable model with /model.
```

The warning fires once per session, then suppresses — no per-turn nag.

---

## Troubleshooting

### `MCP: 0/1 servers running (1 failed — see /mcp list)`

A server failed to start. `/mcp list` will show the error. Common causes:

- **`command not found`** — the executable isn't on `PATH` (e.g., `npx`, `uvx`, `docker` not installed).
- **Auth error from the server itself** — bad token, missing env var.
- **Server crashed during init** — try `/mcp restart <name>` after fixing the cause.

There's no auto-restart in v1; servers that fail start stay failed until you `/mcp restart`.

### `MCP config error: server 'foo': missing required field 'command'`

Your `mcp.yml` schema is invalid. The error names the field. Other variants:

- `env references unset variable ${FOO}` — your YAML uses `${FOO}` but `FOO` isn't in your shell env.
- `invalid default_permission 'yolo'` — typo in a permission mode. Must be `auto`, `ask`, or `deny`.

### Tool calls happen but produce errors

The error reason now appears in the chat:

```
  ← filesystem.read_file (error): Path /tmp is not within allowed directories...
```

Read the error, fix the request (or the server config), retry. Many MCP servers have access controls (filesystem allows only specific dirs; github requires scopes).

### The model doesn't know about my MCP tools

Two things to check:

1. **Is the server running?** `/mcp list`. If `failed`, fix and restart.
2. **Does the model support tool calling?** If you saw a "Model X does not support tool calling" warning at startup, switch models. `/model claude-opus-4-5` is a safe choice.

If both look right but the model still doesn't call tools, the model may simply have decided text was sufficient. Be more explicit: "Use the filesystem tool to read README.md" tends to nudge it.

### Iteration cap reached

```
MCP iteration cap (25) reached; stopping tool-call loop.
```

The model called more than 25 tools in one turn. Default cap is 25 (high enough that even Serena's onboarding flow doesn't hit it). Override with:

```bash
export AIDER_MCP_MAX_ITERATIONS=50
```

If you're hitting this often, the model is stuck in a loop — usually a sign that one of the tools is returning nonsense and the model is retrying forever. Check `/mcp tools` and the server's logs.

### Persistent decisions aren't being applied

Check `./.aider/mcp-permissions.json` exists at your project root and contains the decision:

```bash
cat .aider/mcp-permissions.json
```

If the file is missing, the `Always` / `Deny permanently` save failed silently (warning printed at the time). Manually create the file with the JSON shape shown in the [persistent decisions](#persistent-decisions-file) section.

---

## Architecture (for contributors)

The MCP support lives in `aider/mcp/`:

```
aider/mcp/
├── __init__.py
├── config.py            # mcp.yml load + validate + env-var expansion
├── client.py            # one stdio MCP server connection (uses the SDK's ClientSession)
├── manager.py           # async orchestrator over N clients, eager startup
├── runtime.py           # sync wrapper — runs the asyncio loop on a daemon thread
├── tool_schemas.py      # MCP tool dict ↔ litellm/OpenAI tools= shape converter
├── permissions.py       # pure permission resolver (priority order)
└── persistence.py       # mcp-permissions.json load/save (atomic)
```

### Layered responsibility

| Layer | Owns | Async/sync |
|---|---|---|
| `config` | YAML parse + validation + env expansion | sync |
| `client.Client` | one stdio server lifecycle (connect, list_tools, call_tool, disconnect) | async |
| `manager.Manager` | N clients, parallel startup, partial-failure isolation, restart | async |
| `runtime.MCPRuntime` | event-loop thread, sync API for the rest of aider | sync surface, async impl |
| `tool_schemas` | name namespacing (`mcp__server__tool`) and OpenAI-format conversion | sync, pure |
| `permissions` | priority-ordered mode resolution | sync, pure |
| `persistence` | atomic JSON read/write of `.aider/mcp-permissions.json` | sync, pure |

### Lifecycle

`aider/main.py:_setup_mcp` runs once during startup, after `Coder.create()` succeeds:

1. Load `mcp.yml` (global + project, project overrides).
2. If no servers configured → return silently (MCP inactive).
3. Build `Manager(servers_config)` and `MCPRuntime(manager)`.
4. `runtime.start()` — spawns daemon thread with asyncio loop, calls `manager.start_all()` (parallel server startup).
5. Set `coder.mcp_runtime` and `coder.commands.mcp_runtime` (mirror pattern matching skills_manager).
6. Load persisted permissions from `./.aider/mcp-permissions.json` into `coder.mcp_persisted_permissions`.
7. Register `atexit.register(runtime.stop)`.

`runtime.stop()` calls `manager.stop_all()` (disconnect each client), stops the asyncio loop, joins the thread.

### Tool execution loop

In `aider/coders/base_coder.py::send_message`:

```python
while True:
    try:
        yield from self.send(messages, functions=self.functions)
        if self._execute_pending_tool_calls(messages):
            mcp_iterations += 1
            if mcp_iterations >= mcp_max_iterations:
                # surface warning, break
                break
            continue
        break
```

`Coder.send()` injects `tools=` (built by `_get_mcp_tools_for_model`) into `litellm.completion`. The streaming chunk loop in `show_send_output_stream` accumulates `tool_calls` deltas into `Coder.partial_tool_calls`. After `send()` returns:

- If `partial_tool_calls` is non-empty: `_execute_pending_tool_calls` appends `{role: assistant, tool_calls: [...]}` and one `{role: tool, ...}` per call to `messages`, returns `True` so the loop re-enters.
- Else: `False`, loop breaks (text-only response).

Each tool call goes through `_call_one_mcp_tool`:

1. Parse `mcp__<server>__<tool>` to route to the right runtime endpoint.
2. Resolve permission (slice 3) — returns auto / ask / deny.
3. If `ask`: prompt the user via `_ask_mcp_permission` (slice 5), apply decision (persist if Always/Never, add to session-skip set if Skip).
4. If `auto` (or `ask` resolved to yes/always): call `runtime.call_tool(server, name, args)`.
5. Format result, surface `→`/`←` lines via `io.tool_output`, return text the model sees.

### Tests

35+ test cases across nine files in `tests/basic/test_mcp_*.py`:

| File | Layer covered |
|---|---|
| `test_mcp_config.py` | YAML schema validation, env expansion, project-over-global merge |
| `test_mcp_client.py` | stdio connect, list_tools, call_tool, annotations, lifecycle |
| `test_mcp_manager.py` | parallel startup, failure isolation, multi-server tool aggregation, restart |
| `test_mcp_runtime.py` | sync wrapper end-to-end |
| `test_mcp_commands.py` | `/mcp` slash command behaviors |
| `test_mcp_chunk_loop.py` | streaming `tool_calls` delta accumulation |
| `test_mcp_tool_schemas.py` | name namespacing, OpenAI-format conversion |
| `test_mcp_tool_loop.py` | end-to-end `_execute_pending_tool_calls` with mocked runtime |
| `test_mcp_tools_injection.py` | gate (`supports_function_calling`), `tools=` merge into litellm |
| `test_mcp_permissions.py` | resolver priority order |
| `test_mcp_persistence.py` | mcp-permissions.json load/save |
| `test_mcp_permission_prompt.py` | interactive Always/Never decision flow |

Test fixture for the stdio path is `tests/basic/_mcp_test_server.py` — a minimal echo server spawned via `python -m tests.basic._mcp_test_server` that takes `MCP_TEST_TOOL_NAME` and read-only/destructive flags from env so multi-server and permission tests can simulate different scenarios without separate fixture files.

---

## Roadmap

Implemented:

- **Phase 1**: client subsystem, `/mcp` slash commands, lifecycle wiring.
- **Phase 2**: tool execution loop, `tools=` injection, UX visibility.
- **Phase 3**: permission gate with persistent decisions.

Not yet implemented (loose ends):

- **Tool result truncation** — large outputs are currently sent to the model in full. Research D8 specifies a 10k-token cap with disk spillover.
- **`runtime.list_tools()` caching** — every send currently re-queries each server's tool list. Fine for a few servers; slow if you have a dozen.
- **Streamable HTTP transport** — v1 is stdio-only. HTTP (with bearer auth, then OAuth) is v1.1 / v1.2.
- **`pyproject.toml` extras wiring** — installing via `pip install aider-chat[mcp]` requires running `./scripts/pip-compile.sh` to generate the lockfile and adding the `mcp` extras entry.
