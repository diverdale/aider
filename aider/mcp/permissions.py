"""MCP permission resolution.

Pure logic: given metadata about a tool call (server name, tool name,
the tool's MCP annotations, the server's mcp.yml config, and any
persisted decisions from .aider/mcp-permissions.json), return one of
{auto, ask, deny}.

No I/O. The persisted-decisions store is loaded by callers and passed
in here as a plain dict so this module stays trivially testable.

Priority order (highest wins):

  1. Persisted decision (user clicked "Always" or "Never" earlier)
  2. Per-tool override in mcp.yml — `servers.<name>.permissions.<tool>`
  3. Per-server default in mcp.yml — `servers.<name>.default_permission`
  4. Tool annotation: `readOnlyHint: True` → auto; otherwise → ask
  5. Hard fallback: ask

Anything `destructiveHint` and similar still falls into "ask" rather
than "deny" — destructiveHint is informative, not prescriptive.
Explicit deny is for the user's mcp.yml or a persisted "Never"."""

VALID_MODES = ("auto", "ask", "deny")


def resolve_permission(server_name, tool_name, tool_meta, server_config, persisted):
    """Return the effective permission mode for one tool call.

    Args:
        server_name: e.g. "filesystem"
        tool_name: bare tool name without the mcp__<server>__ prefix
        tool_meta: dict from runtime.list_tools(); may contain "annotations"
        server_config: dict from mcp_config.load_servers()[server_name];
            must have "default_permission" and "permissions" keys
        persisted: dict shaped {server_name: {tool_name: mode}}; may be
            empty or missing entries
    """
    # 1. Persisted decision.
    persisted_for_server = persisted.get(server_name) or {}
    persisted_mode = persisted_for_server.get(tool_name)
    if persisted_mode in VALID_MODES:
        return persisted_mode

    # 2. Per-tool config override.
    config_perms = server_config.get("permissions") or {}
    config_mode = config_perms.get(tool_name)
    if config_mode in VALID_MODES:
        return config_mode

    # 3. Per-server default.
    default = server_config.get("default_permission")
    if default in VALID_MODES:
        return default

    # 4. Annotation-derived default.
    annotations = (tool_meta or {}).get("annotations") or {}
    if annotations.get("readOnlyHint") is True:
        return "auto"

    # 5. Conservative fallback.
    return "ask"
