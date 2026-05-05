"""Project-local persistence of MCP permission decisions.

`.aider/mcp-permissions.json` stores `{server: {tool: mode}}` so user
choices ("Always for this tool", "Never ask here") survive across
aider sessions. This is the differentiator vs Claude Code's session-
only model.

Pure I/O. The resolver in aider/mcp/permissions.py decides what to
DO with the loaded data; this module only owns moving bytes."""

import json
import os
import tempfile
from pathlib import Path


_VALID_MODES = ("auto", "ask", "deny")


def load_permissions(path):
    """Read `{server: {tool: mode}}` from `path` (a Path or str). Returns
    {} when the file is missing, malformed, or has the wrong top-level
    shape — never raises. The user shouldn't have to create an empty
    file before MCP works, and a hand-edited corrupt file shouldn't
    block aider startup."""
    p = Path(path)
    if not p.exists():
        return {}
    try:
        data = json.loads(p.read_text())
    except (json.JSONDecodeError, OSError):
        return {}
    if not isinstance(data, dict):
        return {}
    out = {}
    for server, perms in data.items():
        if not isinstance(perms, dict):
            continue
        cleaned = {
            tool: mode
            for tool, mode in perms.items()
            if isinstance(mode, str) and mode in _VALID_MODES
        }
        if cleaned:
            out[server] = cleaned
    return out


def save_permissions(path, decisions):
    """Atomically write `decisions` (a `{server: {tool: mode}}` dict) to
    `path`. Creates parent directories as needed. Invalid modes are
    silently dropped — better than persisting garbage that the resolver
    will ignore on the next load."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)

    cleaned = {}
    for server, perms in (decisions or {}).items():
        if not isinstance(perms, dict):
            continue
        valid = {
            tool: mode
            for tool, mode in perms.items()
            if isinstance(mode, str) and mode in _VALID_MODES
        }
        if valid:
            cleaned[server] = valid

    # Atomic write: write to a sibling tmp file in the same directory
    # then rename. NamedTemporaryFile with delete=False so we control
    # the rename; clean up on any failure between write and rename.
    fd, tmp_path = tempfile.mkstemp(
        prefix=p.name + ".",
        suffix=".tmp",
        dir=str(p.parent),
    )
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(cleaned, f, indent=2, sort_keys=True)
            f.write("\n")
        os.replace(tmp_path, p)
    except Exception:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise
