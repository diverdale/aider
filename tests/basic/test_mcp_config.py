#!/usr/bin/env python

import pytest

from aider.mcp import config as mcp_config


def test_load_minimal_server(tmp_path):
    """A YAML with one minimal server entry produces a single normalized dict
    with command/args preserved and `enabled` defaulting to True."""
    p = tmp_path / "mcp.yml"
    p.write_text(
        "servers:\n"
        "  filesystem:\n"
        "    command: npx\n"
        "    args: [\"-y\", \"@modelcontextprotocol/server-filesystem\", \"/tmp\"]\n"
    )
    servers = mcp_config.load_servers(project_path=p, global_path=None)
    assert "filesystem" in servers
    assert servers["filesystem"]["command"] == "npx"
    assert servers["filesystem"]["args"] == [
        "-y",
        "@modelcontextprotocol/server-filesystem",
        "/tmp",
    ]
    assert servers["filesystem"]["enabled"] is True


def test_missing_command_raises(tmp_path):
    """A server entry without `command` is a hard error — no silent default."""
    p = tmp_path / "mcp.yml"
    p.write_text(
        "servers:\n"
        "  broken:\n"
        "    args: [\"-y\"]\n"
    )
    with pytest.raises(mcp_config.MCPConfigError, match="command"):
        mcp_config.load_servers(project_path=p, global_path=None)


def test_env_var_expansion(tmp_path, monkeypatch):
    """`${VAR}` and `$VAR` references in env values get expanded from os.environ.
    Plain (non-templated) values pass through untouched."""
    monkeypatch.setenv("GITHUB_TOKEN_FOR_TEST", "ghp_xxx")
    p = tmp_path / "mcp.yml"
    p.write_text(
        "servers:\n"
        "  github:\n"
        "    command: docker\n"
        "    args: [\"run\", \"-i\", \"--rm\", \"ghcr.io/github/github-mcp-server\"]\n"
        "    env:\n"
        "      TOKEN_BRACED: ${GITHUB_TOKEN_FOR_TEST}\n"
        "      TOKEN_BARE: $GITHUB_TOKEN_FOR_TEST\n"
        "      LITERAL: dollar-sign-only\n"
    )
    servers = mcp_config.load_servers(project_path=p, global_path=None)
    assert servers["github"]["env"]["TOKEN_BRACED"] == "ghp_xxx"
    assert servers["github"]["env"]["TOKEN_BARE"] == "ghp_xxx"
    assert servers["github"]["env"]["LITERAL"] == "dollar-sign-only"


def test_missing_env_var_raises(tmp_path, monkeypatch):
    """An unset env var in a `${VAR}` reference is a clear error, not a
    silently-empty string. Otherwise misconfigured servers would launch
    with empty credentials and fail mysteriously."""
    monkeypatch.delenv("DEFINITELY_NOT_SET_FOR_TEST", raising=False)
    p = tmp_path / "mcp.yml"
    p.write_text(
        "servers:\n"
        "  s:\n"
        "    command: x\n"
        "    env:\n"
        "      KEY: ${DEFINITELY_NOT_SET_FOR_TEST}\n"
    )
    with pytest.raises(mcp_config.MCPConfigError, match="DEFINITELY_NOT_SET_FOR_TEST"):
        mcp_config.load_servers(project_path=p, global_path=None)


def test_project_overrides_global(tmp_path):
    """Same server name in both files: project wins. Servers only in global
    pass through."""
    g = tmp_path / "global.yml"
    g.write_text(
        "servers:\n"
        "  shared:\n"
        "    command: from-global\n"
        "  global-only:\n"
        "    command: only-global\n"
    )
    p = tmp_path / "project.yml"
    p.write_text(
        "servers:\n"
        "  shared:\n"
        "    command: from-project\n"
        "  project-only:\n"
        "    command: only-project\n"
    )
    servers = mcp_config.load_servers(project_path=p, global_path=g)
    assert servers["shared"]["command"] == "from-project"
    assert servers["global-only"]["command"] == "only-global"
    assert servers["project-only"]["command"] == "only-project"


def test_no_files_returns_empty(tmp_path):
    """Both paths missing: returns empty dict, no error. The common case for a
    user who hasn't configured MCP yet — they shouldn't see a crash."""
    servers = mcp_config.load_servers(
        project_path=tmp_path / "missing-project.yml",
        global_path=tmp_path / "missing-global.yml",
    )
    assert servers == {}
