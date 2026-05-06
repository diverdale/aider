#!/usr/bin/env python
"""Phase 2 slice 2: tool execution loop helper.

Tests `Coder._execute_pending_tool_calls` — the helper that consumes
`partial_tool_calls`, dispatches each through the MCP runtime, and
appends `{role: assistant, tool_calls: ...}` + `{role: tool, ...}`
messages so the next send() can let the model react.

Tested in isolation from send_message's retry loop. The retry-loop
wiring is a single `if helper(): continue` line — too thin to deserve
its own integration test."""

import tempfile
from pathlib import Path
from unittest import TestCase
from unittest.mock import MagicMock, patch

from aider.coders import Coder
from aider.io import InputOutput
from aider.models import Model


def _ok_result(text):
    return {"is_error": False, "content": [{"type": "text", "text": text}]}


def _err_result(text):
    return {"is_error": True, "content": [{"type": "text", "text": text}]}


class TestMCPToolLoop(TestCase):
    def setUp(self):
        self.tempdir = Path(tempfile.mkdtemp())
        self.GPT35 = Model("gpt-3.5-turbo")
        self.coder = Coder.create(
            self.GPT35, None, io=InputOutput(pretty=False, fancy_input=False, yes=True)
        )
        # Default: no MCP runtime, no pending calls.
        self.coder.partial_tool_calls = []
        self.coder.partial_response_content = ""
        self.coder.multi_response_content = ""
        self.coder.mcp_runtime = None
        # Default the permission prompt to "yes" so ask-mode tests don't
        # block on stdin. Tests exercising specific decisions override.
        self._ask_patcher = patch.object(Coder, "_ask_mcp_permission", return_value="yes")
        self._ask_patcher.start()

    def tearDown(self):
        self._ask_patcher.stop()

    def test_no_pending_calls_returns_false(self):
        """Empty partial_tool_calls is the common text-only path. Helper
        returns False so send_message breaks out of its loop normally."""
        messages = [{"role": "user", "content": "hi"}]
        executed = self.coder._execute_pending_tool_calls(messages)
        self.assertFalse(executed)
        self.assertEqual(messages, [{"role": "user", "content": "hi"}])

    def test_pending_calls_without_runtime_returns_false(self):
        """If MCP wasn't wired (no runtime), pending tool calls are dropped
        with a False return — model called a tool but we have no way to
        execute it. Better than crashing; the next send() will see no
        change and loop will break cleanly."""
        self.coder.partial_tool_calls = [
            {"id": "c0", "name": "mcp__fs__read", "arguments": '{"path":"/x"}'},
        ]
        executed = self.coder._execute_pending_tool_calls([{"role": "user", "content": "hi"}])
        self.assertFalse(executed)

    def test_executes_one_call_and_appends_two_messages(self):
        """One pending call → one assistant message (with tool_calls array)
        AND one tool message (with the result). Both shapes match what
        litellm expects on the next round."""
        runtime = MagicMock()
        runtime.call_tool.return_value = _ok_result("file body")
        self.coder.mcp_runtime = runtime
        self.coder.partial_response_content = "I'll read it. "
        self.coder.partial_tool_calls = [
            {"id": "c0", "name": "mcp__fs__read", "arguments": '{"path": "/etc/hosts"}'},
        ]
        messages = [{"role": "user", "content": "what's in /etc/hosts?"}]
        executed = self.coder._execute_pending_tool_calls(messages)
        self.assertTrue(executed)
        # Original user message preserved + 2 new entries.
        self.assertEqual(len(messages), 3)
        assistant = messages[1]
        self.assertEqual(assistant["role"], "assistant")
        self.assertEqual(len(assistant["tool_calls"]), 1)
        self.assertEqual(assistant["tool_calls"][0]["id"], "c0")
        self.assertEqual(assistant["tool_calls"][0]["function"]["name"], "mcp__fs__read")
        tool_msg = messages[2]
        self.assertEqual(tool_msg["role"], "tool")
        self.assertEqual(tool_msg["tool_call_id"], "c0")
        self.assertIn("file body", tool_msg["content"])
        # Runtime called with parsed (server, tool, args).
        runtime.call_tool.assert_called_once_with("fs", "read", {"path": "/etc/hosts"})

    def test_invalid_json_args_become_error_tool_message(self):
        """Malformed arguments JSON shouldn't crash — surface as an error
        message the model can read and recover from."""
        runtime = MagicMock()
        self.coder.mcp_runtime = runtime
        self.coder.partial_tool_calls = [
            {"id": "c0", "name": "mcp__fs__read", "arguments": "not-json"},
        ]
        messages = [{"role": "user", "content": "hi"}]
        executed = self.coder._execute_pending_tool_calls(messages)
        self.assertTrue(executed)
        # Runtime was NOT called — args couldn't parse.
        runtime.call_tool.assert_not_called()
        tool_msg = messages[-1]
        self.assertEqual(tool_msg["role"], "tool")
        self.assertIn("error", tool_msg["content"].lower())

    def test_runtime_exception_becomes_error_tool_message(self):
        """A failure inside runtime.call_tool (server crashed, MCPManagerError,
        etc.) surfaces to the model as a `[error]`-prefixed tool result —
        not a Python exception that aborts the turn."""
        runtime = MagicMock()
        runtime.call_tool.side_effect = RuntimeError("server died")
        self.coder.mcp_runtime = runtime
        self.coder.partial_tool_calls = [
            {"id": "c0", "name": "mcp__fs__read", "arguments": '{"x":1}'},
        ]
        messages = [{"role": "user", "content": "hi"}]
        executed = self.coder._execute_pending_tool_calls(messages)
        self.assertTrue(executed)
        tool_msg = messages[-1]
        self.assertIn("server died", tool_msg["content"])
        self.assertIn("error", tool_msg["content"].lower())

    def test_unqualified_tool_name_becomes_error(self):
        """A tool name without the mcp__<server>__ prefix has no server to
        route to. Surface as a tool-message error rather than crashing."""
        runtime = MagicMock()
        self.coder.mcp_runtime = runtime
        self.coder.partial_tool_calls = [
            {"id": "c0", "name": "plain_function", "arguments": "{}"},
        ]
        executed = self.coder._execute_pending_tool_calls([{"role": "user", "content": "hi"}])
        self.assertTrue(executed)
        runtime.call_tool.assert_not_called()

    def test_permission_auto_calls_without_prompt(self):
        """A tool resolved to `auto` (read-only annotation, or persisted
        always) runs silently — no confirm_ask, runtime.call_tool fires."""
        runtime = MagicMock()
        runtime.call_tool.return_value = _ok_result("ok")
        runtime.get_tool_meta.return_value = {"name": "read", "annotations": {"readOnlyHint": True}}
        runtime.get_server_config.return_value = {"default_permission": None, "permissions": {}}
        self.coder.mcp_runtime = runtime
        self.coder.partial_tool_calls = [
            {"id": "c0", "name": "mcp__fs__read", "arguments": "{}"},
        ]
        with patch.object(self.coder.io, "confirm_ask") as confirm:
            self.coder._execute_pending_tool_calls([{"role": "user", "content": "hi"}])
        confirm.assert_not_called()
        runtime.call_tool.assert_called_once()

    def test_permission_ask_yes_runs_the_call(self):
        """`ask` mode prompts the user; on yes, the call proceeds normally."""
        runtime = MagicMock()
        runtime.call_tool.return_value = _ok_result("done")
        runtime.get_tool_meta.return_value = {"name": "write"}
        runtime.get_server_config.return_value = {"default_permission": "ask", "permissions": {}}
        self.coder.mcp_runtime = runtime
        self.coder.partial_tool_calls = [
            {"id": "c0", "name": "mcp__fs__write", "arguments": '{"x":1}'},
        ]
        # setUp already mocks _ask_mcp_permission to "yes"; this test just
        # verifies the resulting behavior end-to-end.
        self.coder._execute_pending_tool_calls([{"role": "user", "content": "hi"}])
        runtime.call_tool.assert_called_once_with("fs", "write", {"x": 1})

    def test_permission_ask_no_blocks_with_error_tool_message(self):
        """`ask` mode with a `no` answer must NOT call runtime.call_tool. The
        model gets a clear error tool message so it can adapt — apologize,
        try a different approach, etc."""
        runtime = MagicMock()
        runtime.get_tool_meta.return_value = {"name": "delete"}
        runtime.get_server_config.return_value = {"default_permission": "ask", "permissions": {}}
        self.coder.mcp_runtime = runtime
        self.coder.partial_tool_calls = [
            {"id": "c0", "name": "mcp__fs__delete", "arguments": "{}"},
        ]
        messages = [{"role": "user", "content": "hi"}]
        with patch.object(Coder, "_ask_mcp_permission", return_value="no"):
            self.coder._execute_pending_tool_calls(messages)
        runtime.call_tool.assert_not_called()
        tool_msg = messages[-1]
        self.assertEqual(tool_msg["role"], "tool")
        self.assertIn("declined", tool_msg["content"].lower())

    def test_permission_deny_blocks_without_prompting(self):
        """`deny` mode short-circuits before any prompt or call — the user
        already configured this tool as off-limits."""
        runtime = MagicMock()
        runtime.get_tool_meta.return_value = {"name": "rm"}
        runtime.get_server_config.return_value = {
            "default_permission": "ask",
            "permissions": {"rm": "deny"},
        }
        self.coder.mcp_runtime = runtime
        self.coder.partial_tool_calls = [
            {"id": "c0", "name": "mcp__fs__rm", "arguments": "{}"},
        ]
        messages = [{"role": "user", "content": "hi"}]
        with patch.object(self.coder.io, "confirm_ask") as confirm:
            self.coder._execute_pending_tool_calls(messages)
        confirm.assert_not_called()
        runtime.call_tool.assert_not_called()
        self.assertIn("denied", messages[-1]["content"].lower())

    def test_parallel_calls_dispatched_to_correct_servers(self):
        """Two pending calls to different servers each go to the right
        runtime endpoint. The qualified name carries the routing info."""
        runtime = MagicMock()
        runtime.call_tool.side_effect = [
            _ok_result("alpha-result"),
            _ok_result("beta-result"),
        ]
        self.coder.mcp_runtime = runtime
        self.coder.partial_tool_calls = [
            {"id": "c0", "name": "mcp__alpha__read", "arguments": "{}"},
            {"id": "c1", "name": "mcp__beta__write", "arguments": '{"v":1}'},
        ]
        messages = [{"role": "user", "content": "hi"}]
        self.coder._execute_pending_tool_calls(messages)
        calls = runtime.call_tool.call_args_list
        self.assertEqual(calls[0].args, ("alpha", "read", {}))
        self.assertEqual(calls[1].args, ("beta", "write", {"v": 1}))
        # Two tool messages, in order, matching ids.
        tool_msgs = [m for m in messages if m["role"] == "tool"]
        self.assertEqual([m["tool_call_id"] for m in tool_msgs], ["c0", "c1"])
        self.assertIn("alpha-result", tool_msgs[0]["content"])
        self.assertIn("beta-result", tool_msgs[1]["content"])
