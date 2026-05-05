#!/usr/bin/env python
"""Phase 2 slice 1: chunk-loop accumulation of MCP tool_calls deltas.

Drives `Coder.partial_tool_calls` via fake litellm streaming chunks. The
coder's existing `partial_response_function_call` plumbing handles the
deprecated single-call API; MCP's tool_calls list lives in a parallel
state var so legacy func-coders (editblock_func, wholefile_func) keep
working unchanged."""

import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest import TestCase

from aider.coders import Coder
from aider.io import InputOutput
from aider.models import Model


def _delta_chunk(content=None, tool_calls=None):
    """Build a fake litellm streaming chunk with optional content and/or
    tool_calls deltas. finish_reason=None mirrors mid-stream chunks."""
    delta = SimpleNamespace(
        content=content,
        tool_calls=tool_calls,
        function_call=None,
    )
    return SimpleNamespace(
        choices=[SimpleNamespace(delta=delta, finish_reason=None)],
    )


def _tool_call_delta(index, id=None, name=None, arguments=""):
    """Build a fake delta entry shaped like litellm's
    ChoiceDeltaToolCall. id/name only appear on the first chunk for a
    given index; arguments stream in pieces."""
    fn = None
    if name is not None or arguments:
        fn = SimpleNamespace(name=name, arguments=arguments)
    return SimpleNamespace(index=index, id=id, type="function", function=fn)


class TestMCPChunkLoop(TestCase):
    def setUp(self):
        self.tempdir = Path(tempfile.mkdtemp())
        self.GPT35 = Model("gpt-3.5-turbo")
        self.coder = Coder.create(
            self.GPT35, None, io=InputOutput(pretty=False, fancy_input=False, yes=True)
        )
        # Bypass the spinner / mdstream lifecycle that send_message normally
        # sets up — these tests drive show_send_output_stream directly.
        self.coder.mdstream = None
        self.coder.partial_response_content = ""
        self.coder.partial_response_function_call = {}
        self.coder.partial_tool_calls = []
        self.coder.got_reasoning_content = False
        self.coder.ended_reasoning_content = False

    def _consume_stream(self, chunks):
        list(self.coder.show_send_output_stream(iter(chunks)))

    def test_single_tool_call_accumulates_id_name_and_args(self):
        """First chunk supplies id/name; subsequent chunks append to args.
        Final state has the merged arguments string and the id/name set
        once."""
        self._consume_stream([
            _delta_chunk(tool_calls=[
                _tool_call_delta(0, id="call_1", name="mcp__fs__read",
                                 arguments='{"path"'),
            ]),
            _delta_chunk(tool_calls=[
                _tool_call_delta(0, arguments=': "/etc/hosts"}'),
            ]),
        ])
        self.assertEqual(len(self.coder.partial_tool_calls), 1)
        tc = self.coder.partial_tool_calls[0]
        self.assertEqual(tc["id"], "call_1")
        self.assertEqual(tc["name"], "mcp__fs__read")
        self.assertEqual(tc["arguments"], '{"path": "/etc/hosts"}')

    def test_multiple_tool_calls_merge_independently_by_index(self):
        """Two parallel tool calls with interleaved deltas — each accumulates
        its own arguments without crossing wires."""
        self._consume_stream([
            _delta_chunk(tool_calls=[
                _tool_call_delta(0, id="c0", name="t_a", arguments='{"a"'),
            ]),
            _delta_chunk(tool_calls=[
                _tool_call_delta(1, id="c1", name="t_b", arguments='{"b"'),
            ]),
            _delta_chunk(tool_calls=[
                _tool_call_delta(0, arguments=":1}"),
                _tool_call_delta(1, arguments=":2}"),
            ]),
        ])
        self.assertEqual(len(self.coder.partial_tool_calls), 2)
        by_id = {tc["id"]: tc for tc in self.coder.partial_tool_calls}
        self.assertEqual(by_id["c0"]["name"], "t_a")
        self.assertEqual(by_id["c0"]["arguments"], '{"a":1}')
        self.assertEqual(by_id["c1"]["name"], "t_b")
        self.assertEqual(by_id["c1"]["arguments"], '{"b":2}')

    def test_text_and_tool_calls_coexist(self):
        """Text content streams normally into partial_response_content while
        tool_calls accumulate separately. The two channels don't interfere."""
        self._consume_stream([
            _delta_chunk(content="I'll read the file. "),
            _delta_chunk(tool_calls=[
                _tool_call_delta(0, id="c0", name="mcp__fs__read",
                                 arguments='{"path": "/x"}'),
            ]),
            _delta_chunk(content="Done."),
        ])
        self.assertEqual(self.coder.partial_response_content,
                         "I'll read the file. Done.")
        self.assertEqual(len(self.coder.partial_tool_calls), 1)
        self.assertEqual(self.coder.partial_tool_calls[0]["name"],
                         "mcp__fs__read")

    def test_no_tool_calls_leaves_state_empty(self):
        """A pure-text response keeps partial_tool_calls empty — the existing
        text-only path is unchanged."""
        self._consume_stream([
            _delta_chunk(content="Just text, no tools."),
        ])
        self.assertEqual(self.coder.partial_tool_calls, [])
        self.assertEqual(self.coder.partial_response_content,
                         "Just text, no tools.")

    def test_non_streaming_show_send_output_captures_tool_calls(self):
        """The non-streaming path (show_send_output) must populate
        partial_tool_calls with the full list — not just the first call.
        litellm hands us the entire list at once when stream=False; we'd
        lose parallel calls if we only kept the first."""
        msg_tool_calls = [
            SimpleNamespace(
                id="c0",
                type="function",
                function=SimpleNamespace(name="t_a", arguments='{"x":1}'),
            ),
            SimpleNamespace(
                id="c1",
                type="function",
                function=SimpleNamespace(name="t_b", arguments='{"y":2}'),
            ),
        ]
        completion = SimpleNamespace(
            choices=[SimpleNamespace(
                message=SimpleNamespace(
                    tool_calls=msg_tool_calls,
                    content="Calling tools.",
                    reasoning_content=None,
                ),
                finish_reason="tool_calls",
            )],
        )
        self.coder.show_send_output(completion)
        self.assertEqual(len(self.coder.partial_tool_calls), 2)
        names = [tc["name"] for tc in self.coder.partial_tool_calls]
        self.assertEqual(names, ["t_a", "t_b"])
        ids = [tc["id"] for tc in self.coder.partial_tool_calls]
        self.assertEqual(ids, ["c0", "c1"])
