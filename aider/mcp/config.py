"""MCP server config loader.

Reads `mcp.yml` files from the global (`~/.aider/mcp.yml`) and project
(`./.aider/mcp.yml`) locations, validates them, expands `$VAR` / `${VAR}`
references in env values, and produces a normalized `{name: server_dict}`
mapping. Project entries override global entries by name.

See `docs/mcp/research.md` D2/D3 for the schema decision."""

import os
import re

import yaml


class MCPConfigError(ValueError):
    pass


_ENV_REF = re.compile(r"\$\{([^}]+)\}|\$([A-Za-z_][A-Za-z0-9_]*)")


def _expand_env(value, server_name):
    """Replace `$VAR` and `${VAR}` references with values from os.environ.
    Raises MCPConfigError if any referenced variable is unset."""

    def replace(match):
        name = match.group(1) or match.group(2)
        if name not in os.environ:
            raise MCPConfigError(
                f"server '{server_name}': env references unset variable ${{{name}}}"
            )
        return os.environ[name]

    return _ENV_REF.sub(replace, value)


def load_servers(project_path=None, global_path=None):
    """Return a normalized dict of {server_name: server_config}.

    Either path may be None (skipped) or point to a non-existent file
    (also skipped). Project entries override global by name."""
    servers = {}
    for path in (global_path, project_path):
        if path is None or not path.exists():
            continue
        with open(path) as f:
            data = yaml.safe_load(f) or {}
        for name, entry in (data.get("servers") or {}).items():
            if not isinstance(entry, dict):
                raise MCPConfigError(
                    f"server '{name}': entry must be a mapping, got {type(entry).__name__}"
                )
            if "command" not in entry:
                raise MCPConfigError(f"server '{name}': missing required field 'command'")
            normalized = dict(entry)
            normalized.setdefault("args", [])
            normalized.setdefault("enabled", True)
            env = normalized.get("env") or {}
            normalized["env"] = {
                k: _expand_env(str(v), name) for k, v in env.items()
            }
            servers[name] = normalized
    return servers
