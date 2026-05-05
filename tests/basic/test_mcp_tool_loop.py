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
from unittest.mock import MagicMock

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
        executed = self.coder._execute_pending_tool_calls(
            [{"role": "user", "content": "hi"}]
        )
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
            {"id": "c0", "name": "mcp__fs__read",
             "arguments": '{"path": "/etc/hosts"}'},
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
        self.assertEqual(
            assistant["tool_calls"][0]["function"]["name"], "mcp__fs__read"
        )
        tool_msg = messages[2]
        self.assertEqual(tool_msg["role"], "tool")
        self.assertEqual(tool_msg["tool_call_id"], "c0")
        self.assertIn("file body", tool_msg["content"])
        # Runtime called with parsed (server, tool, args).
        runtime.call_tool.assert_called_once_with(
            "fs", "read", {"path": "/etc/hosts"}
        )

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
            {"id": "c0", "name": "plain_function", "arguments": '{}'},
        ]
        executed = self.coder._execute_pending_tool_calls(
            [{"role": "user", "content": "hi"}]
        )
        self.assertTrue(executed)
        runtime.call_tool.assert_not_called()

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
            {"id": "c0", "name": "mcp__alpha__read", "arguments": '{}'},
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
