#!/usr/bin/env python
"""Phase 2 slice 3: tools= injection into the litellm completion call.

Two layers tested:

1. Coder._get_mcp_tools_for_model — gate logic. Returns [] when no
   runtime, or when the model doesn't support tool calling. Otherwise
   builds the OpenAI tools array from runtime.list_tools().

2. Model.send_completion — merges `mcp_tools` into `tools=` without
   forcing a `tool_choice` (the model must be free to pick text or
   any tool, unlike the legacy `functions` path)."""

import tempfile
from pathlib import Path
from unittest import TestCase
from unittest.mock import MagicMock, patch

from aider.coders import Coder
from aider.io import InputOutput
from aider.models import Model


class TestMCPToolsInjection(TestCase):
    def setUp(self):
        self.tempdir = Path(tempfile.mkdtemp())
        self.GPT35 = Model("gpt-3.5-turbo")
        self.coder = Coder.create(
            self.GPT35, None, io=InputOutput(pretty=False, fancy_input=False, yes=True)
        )
        self.coder.mcp_runtime = None

    def test_no_runtime_returns_empty_list(self):
        """No MCP runtime configured → no tools to inject. The model sees
        the same prompt it would without MCP."""
        out = self.coder._get_mcp_tools_for_model(self.GPT35)
        self.assertEqual(out, [])

    def test_unsupported_model_returns_empty_with_warning(self):
        """Model that doesn't support function calling → don't pass tools=
        (provider would error). Surface a tool_warning so the user knows
        MCP is silently inactive."""
        runtime = MagicMock()
        runtime.list_tools.return_value = [
            {"name": "read", "server": "fs", "inputSchema": {}},
        ]
        self.coder.mcp_runtime = runtime
        with patch("aider.llm.litellm.supports_function_calling", return_value=False):
            with patch.object(self.coder.io, "tool_warning") as warn:
                out = self.coder._get_mcp_tools_for_model(self.GPT35)
        self.assertEqual(out, [])
        self.assertTrue(warn.called)

    def test_supported_model_with_runtime_returns_converted_tools(self):
        """Happy path. Tool list comes from runtime, gets namespaced
        as `mcp__<server>__<tool>`, returned in OpenAI tools format."""
        runtime = MagicMock()
        runtime.list_tools.return_value = [
            {
                "name": "read",
                "server": "fs",
                "description": "read a file",
                "inputSchema": {"type": "object"},
            },
            {
                "name": "list",
                "server": "fs",
                "description": "list dir",
                "inputSchema": {"type": "object"},
            },
        ]
        self.coder.mcp_runtime = runtime
        with patch("aider.llm.litellm.supports_function_calling", return_value=True):
            out = self.coder._get_mcp_tools_for_model(self.GPT35)
        self.assertEqual(len(out), 2)
        names = [t["function"]["name"] for t in out]
        self.assertEqual(names, ["mcp__fs__read", "mcp__fs__list"])

    def test_unsupported_warning_shown_only_once_per_session(self):
        """A noisy warning every turn would clutter the chat. Show once."""
        runtime = MagicMock()
        runtime.list_tools.return_value = [
            {"name": "x", "server": "y", "inputSchema": {}},
        ]
        self.coder.mcp_runtime = runtime
        with patch("aider.llm.litellm.supports_function_calling", return_value=False):
            with patch.object(self.coder.io, "tool_warning") as warn:
                self.coder._get_mcp_tools_for_model(self.GPT35)
                self.coder._get_mcp_tools_for_model(self.GPT35)
                self.coder._get_mcp_tools_for_model(self.GPT35)
        self.assertEqual(warn.call_count, 1)


class TestSendCompletionMergesMCPTools(TestCase):
    """Model.send_completion plumbing: mcp_tools= merges into tools= without
    forcing tool_choice."""

    def setUp(self):
        self.GPT35 = Model("gpt-3.5-turbo")

    @patch("aider.models.litellm.completion")
    def test_mcp_tools_added_to_kwargs(self, mock_completion):
        """When mcp_tools is provided, kwargs['tools'] gets it. tool_choice
        is NOT forced — the model is free to pick text or any tool."""
        mcp_tools = [
            {
                "type": "function",
                "function": {"name": "mcp__fs__read", "description": "", "parameters": {}},
            },
        ]
        mock_completion.return_value = MagicMock()
        self.GPT35.send_completion(
            messages=[{"role": "user", "content": "hi"}],
            functions=None,
            stream=False,
            mcp_tools=mcp_tools,
        )
        kwargs = mock_completion.call_args.kwargs
        self.assertIn("tools", kwargs)
        self.assertEqual(kwargs["tools"], mcp_tools)
        self.assertNotIn("tool_choice", kwargs)

    @patch("aider.models.litellm.completion")
    def test_legacy_functions_and_mcp_tools_both_present(self, mock_completion):
        """When both `functions` (legacy *_func coder path) and `mcp_tools`
        are supplied, the merged tools list contains both, but tool_choice
        is dropped because forcing the legacy function would prevent the
        model from using any MCP tool."""
        legacy_function = {"name": "write_file", "description": "", "parameters": {}}
        mcp_tools = [
            {
                "type": "function",
                "function": {"name": "mcp__fs__read", "description": "", "parameters": {}},
            },
        ]
        mock_completion.return_value = MagicMock()
        self.GPT35.send_completion(
            messages=[{"role": "user", "content": "hi"}],
            functions=[legacy_function],
            stream=False,
            mcp_tools=mcp_tools,
        )
        kwargs = mock_completion.call_args.kwargs
        names = [t["function"]["name"] for t in kwargs["tools"]]
        self.assertIn("write_file", names)
        self.assertIn("mcp__fs__read", names)
        self.assertNotIn("tool_choice", kwargs)

    @patch("aider.models.litellm.completion")
    def test_no_mcp_tools_legacy_path_unchanged(self, mock_completion):
        """When mcp_tools is None or empty, the legacy path is byte-for-byte
        the same as before. tool_choice IS set, forcing the named function.
        Existing func-coders depend on this."""
        legacy_function = {"name": "write_file", "description": "", "parameters": {}}
        mock_completion.return_value = MagicMock()
        self.GPT35.send_completion(
            messages=[{"role": "user", "content": "hi"}],
            functions=[legacy_function],
            stream=False,
        )
        kwargs = mock_completion.call_args.kwargs
        self.assertIn("tool_choice", kwargs)
        self.assertEqual(kwargs["tool_choice"]["function"]["name"], "write_file")
