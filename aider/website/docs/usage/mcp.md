---
title: MCP servers
parent: Usage
nav_order: 800
description: Connect aider to Model Context Protocol (MCP) servers so the model can call external tools (filesystem, GitHub, custom servers, etc.) during a chat.
---

# MCP servers

Aider can connect to [Model Context Protocol](https://modelcontextprotocol.io)
(MCP) servers, letting the active model call external tools during a chat —
read or write files outside the editable set, query a database, search the
web, hit a GitHub API, etc. Each tool call surfaces inline in the chat as
`→ server.tool(args)` / `← result` lines.

MCP support is shipped as an optional extra. Install it with:

```bash
pip install "aider-chat[mcp]"
```

Without the extra, aider runs exactly as before — no behavior change, no
extra dependencies.

## Quick start

Pick an MCP server. The reference filesystem server is a Node package; install
it once:

```bash
npm install -g @modelcontextprotocol/server-filesystem
```

Then create `~/.aider/mcp.yml` (global) or `./.aider/mcp.yml` (per-project):

```yaml
servers:
  filesystem:
    command: mcp-server-filesystem
    args: ["/tmp"]
    default_permission: ask
```

You can also invoke the package directly via `npx` without a global install,
but cold-spawning npx on every aider startup is slower and occasionally
fragile. Use the long-form `--yes` flag rather than `-y` to avoid an npx
parsing quirk:

```yaml
servers:
  filesystem:
    command: npx
    args: ["--yes", "@modelcontextprotocol/server-filesystem", "/tmp"]
    default_permission: ask
```

Start aider against a model that supports tool calls (most modern Claude,
GPT-4o, Gemini, etc.). The startup banner prints the server status:

```
MCP: 1/1 servers running
```

Ask the model to use a tool, e.g. `list files in /tmp`. Aider will prompt
for permission the first time, then dispatch the call.

## Configuration reference

```yaml
servers:
  <name>:
    command: <executable>            # required: how to launch the stdio server
    args: ["..."]                    # optional: argv for the command
    env:                             # optional: extra env vars; supports $VAR
      API_KEY: $GITHUB_TOKEN
    enabled: true                    # optional, default true
    default_permission: ask          # optional: auto | ask | deny
    permissions:                     # optional: per-tool overrides
      read_file: auto
      delete_repository: deny
```

Both global (`~/.aider/mcp.yml`) and project (`./.aider/mcp.yml`) files are
loaded; project entries with the same name override global ones. Env-var
expansion supports `$VAR` and `${VAR}`. Unknown keys are rejected with a
clear error message.

Only the **stdio transport** is supported today; HTTP/SSE transports may be
added later.

## Permissions

Each tool call resolves to one of three modes:

| Mode | Behavior |
|---|---|
| `auto` | Run the call without prompting. |
| `ask` | Prompt the user for each call. |
| `deny` | Refuse the call; the model is told the tool is denied. |

The mode is resolved with this priority (highest wins):

1. **Persisted decision** in `./.aider/mcp-permissions.json` — set by picking
   "Always for this tool" or "Deny permanently" in an earlier session.
2. **Per-tool override** in `mcp.yml` (`permissions:` block).
3. **Per-server default** (`default_permission`).
4. **Tool annotation** — `readOnlyHint: true` defaults to `auto`,
   `destructiveHint: true` defaults to `ask`.
5. **Fallback**: `ask`.

When a call resolves to `ask`, the prompt is:

```
MCP tool requested: filesystem.write_file({...})
  (Y)es  (N)o  (A)lways for this tool  (D)eny permanently  (S)kip session
```

`A` and `D` write to `./.aider/mcp-permissions.json` so the decision
survives across sessions. To revoke, edit or delete that file.

## Slash commands

| Command | What it does |
|---|---|
| `/mcp` or `/mcp list` | Show the state of each configured server. |
| `/mcp tools [server]` | List tools across all servers, or one server. |
| `/mcp restart <server>` | Kill and respawn a single server. |

## Costs

Each tool call round-trips through the model with the full tool catalog
attached. For Anthropic models the catalog can be large enough to push you
toward rate limits; pair MCP with `--cache-prompts` to send the catalog
once and have subsequent turns billed against the cache.

## Implementation notes

`aider/mcp/` contains the MCP integration:

- `config.py` — YAML loader with env-var expansion.
- `client.py` — stdio client wrapping the MCP SDK's `ClientSession`.
- `manager.py` — orchestrates N servers, parallel startup, isolated failures.
- `runtime.py` — sync wrapper running an asyncio loop on a daemon thread.
- `permissions.py` — pure priority-order resolver.
- `persistence.py` — atomic JSON load/save for persisted decisions.
- `tool_schemas.py` — qualifies tool names as `mcp__<server>__<tool>` and
  converts MCP tool definitions to the OpenAI/`tools=` format.

Tool dispatch lives in `Coder._execute_pending_tool_calls` and
`Coder._call_one_mcp_tool` in `aider/coders/base_coder.py`.
