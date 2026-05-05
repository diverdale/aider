#!/usr/bin/env python
"""Phase 3 slice 5: interactive permission prompt with auto-save.

When the resolver returns `ask`, the user gets a multi-option prompt:

  (Y)es                — run this call only
  (N)o                 — skip this call only
  (A)lways for this tool — persist as auto, save to JSON
  (D)eny permanently   — persist as deny, save to JSON
  (S)kip session       — block same (server, tool) for the rest of
                         this session, no persistence

The first two are one-shot; A and D update mcp-permissions.json so
subsequent sessions skip the prompt; S updates an in-memory session
set.

Tests drive `Coder._execute_pending_tool_calls` end-to-end with the
prompt mocked, so the full integration (resolver + prompt + save +
session-skip + tool execution) is exercised."""

import json
import tempfile
from pathlib import Path
from unittest import TestCase
from unittest.mock import MagicMock, patch

from aider.coders import Coder
from aider.io import InputOutput
from aider.models import Model


def _ok_result(text):
    return {"is_error": False, "content": [{"type": "text", "text": text}]}


class TestMCPPermissionPrompt(TestCase):
    def setUp(self):
        self.tempdir = Path(tempfile.mkdtemp())
        self.GPT35 = Model("gpt-3.5-turbo")
        self.coder = Coder.create(
            self.GPT35, None, io=InputOutput(pretty=False, fancy_input=False, yes=False)
        )
        self.coder.partial_tool_calls = []
        self.coder.partial_response_content = ""
        self.coder.multi_response_content = ""

        self.runtime = MagicMock()
        self.runtime.call_tool.return_value = _ok_result("ok")
        # No annotations / no per-tool config → resolver lands on `ask`.
        self.runtime.get_tool_meta.return_value = {"name": "write"}
        self.runtime.get_server_config.return_value = {
            "default_permission": "ask", "permissions": {}}
        self.coder.mcp_runtime = self.runtime

        self.perm_path = self.tempdir / ".aider" / "mcp-permissions.json"
        self.coder.mcp_persisted_permissions = {}
        self.coder.mcp_persisted_permissions_path = self.perm_path

    def _set_pending(self, server="fs", tool="write", call_id="c0"):
        self.coder.partial_tool_calls = [
            {"id": call_id, "name": f"mcp__{server}__{tool}", "arguments": '{}'},
        ]

    # ---- decision paths ------------------------------------------------

    def test_yes_runs_once_no_persistence(self):
        self._set_pending()
        with patch.object(self.coder, "_ask_mcp_permission", return_value="yes"):
            self.coder._execute_pending_tool_calls(
                [{"role": "user", "content": "x"}]
            )
        self.runtime.call_tool.assert_called_once()
        self.assertFalse(self.perm_path.exists(),
                         "yes should not write to mcp-permissions.json")

    def test_no_blocks_once_no_persistence(self):
        self._set_pending()
        messages = [{"role": "user", "content": "x"}]
        with patch.object(self.coder, "_ask_mcp_permission", return_value="no"):
            self.coder._execute_pending_tool_calls(messages)
        self.runtime.call_tool.assert_not_called()
        self.assertIn("declined", messages[-1]["content"].lower())
        self.assertFalse(self.perm_path.exists())

    def test_always_persists_auto_and_runs(self):
        self._set_pending()
        with patch.object(self.coder, "_ask_mcp_permission", return_value="always"):
            self.coder._execute_pending_tool_calls(
                [{"role": "user", "content": "x"}]
            )
        self.runtime.call_tool.assert_called_once()
        # File written with auto for this (server, tool).
        self.assertTrue(self.perm_path.exists())
        data = json.loads(self.perm_path.read_text())
        self.assertEqual(data, {"fs": {"write": "auto"}})
        # In-memory state updated too — next call hits resolver's
        # persisted-decision branch instead of prompting again.
        self.assertEqual(
            self.coder.mcp_persisted_permissions["fs"]["write"], "auto"
        )

    def test_never_persists_deny_and_blocks(self):
        self._set_pending()
        messages = [{"role": "user", "content": "x"}]
        with patch.object(self.coder, "_ask_mcp_permission", return_value="never"):
            self.coder._execute_pending_tool_calls(messages)
        self.runtime.call_tool.assert_not_called()
        self.assertIn("denied", messages[-1]["content"].lower())
        data = json.loads(self.perm_path.read_text())
        self.assertEqual(data, {"fs": {"write": "deny"}})

    def test_skip_session_blocks_same_tool_without_re_prompting(self):
        """Skip blocks THIS call AND any subsequent call to (server, tool)
        in the same session — no second prompt. No file write."""
        self._set_pending()
        with patch.object(self.coder, "_ask_mcp_permission",
                          return_value="skip") as ask:
            self.coder._execute_pending_tool_calls(
                [{"role": "user", "content": "x"}]
            )
            # Same tool again → no prompt, no call.
            self._set_pending(call_id="c1")
            self.coder._execute_pending_tool_calls(
                [{"role": "user", "content": "y"}]
            )
        self.assertEqual(ask.call_count, 1, "skip should suppress re-prompt")
        self.runtime.call_tool.assert_not_called()
        self.assertFalse(self.perm_path.exists())

    def test_skip_does_not_affect_other_tools(self):
        """Skip on (fs, write) must NOT block (fs, read) — scope is
        per-(server, tool), not per-server."""
        self._set_pending(server="fs", tool="write")
        with patch.object(self.coder, "_ask_mcp_permission",
                          side_effect=["skip", "yes"]) as ask:
            self.coder._execute_pending_tool_calls(
                [{"role": "user", "content": "a"}]
            )
            self._set_pending(server="fs", tool="read", call_id="c1")
            self.coder._execute_pending_tool_calls(
                [{"role": "user", "content": "b"}]
            )
        self.assertEqual(ask.call_count, 2, "different tool should re-prompt")
        # The second call (read with yes) ran.
        self.runtime.call_tool.assert_called_once_with("fs", "read", {})

    def test_save_failure_logs_warning_does_not_block_call(self):
        """If saving the JSON fails (disk full, permission error), the call
        still proceeds — the user said `always` and we honor that for
        this turn even if persistence broke."""
        self._set_pending()
        with patch.object(self.coder, "_ask_mcp_permission",
                          return_value="always"):
            with patch("aider.mcp.persistence.save_permissions",
                       side_effect=OSError("disk full")):
                with patch.object(self.coder.io, "tool_warning") as warn:
                    self.coder._execute_pending_tool_calls(
                        [{"role": "user", "content": "x"}]
                    )
        # Warning surfaced, call still ran.
        self.assertTrue(warn.called)
        self.runtime.call_tool.assert_called_once()
