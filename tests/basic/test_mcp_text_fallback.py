"""Tests for the text-fallback MCP tool-call parser.

Each test mirrors a real failure mode observed when local Ollama models
emit tool calls as content text instead of via the structured tool_calls
field. Test inputs are based on actual emissions seen during fork
testing with mistral-nemo:12b, hermes3:8b, and qwen2.5:14b on Ollama.
"""

import json
import unittest

from aider.mcp.text_fallback import extract_tool_calls


class TestExtractToolCalls(unittest.TestCase):
    def test_empty_content_returns_empty_list(self):
        self.assertEqual(extract_tool_calls(""), [])
        self.assertEqual(extract_tool_calls(None), [])

    def test_no_mcp_call_returns_empty(self):
        self.assertEqual(extract_tool_calls("Just some prose, no tools."), [])
        self.assertEqual(
            extract_tool_calls('{"name": "regular_function", "arguments": {}}'),
            [],
        )

    def test_bare_json_single_call(self):
        # The shape mistral-nemo:12b emits — bare JSON in content.
        content = (
            '{"name": "mcp__filesystem__list_directory",'
            ' "arguments": {"path": "/tmp"}}'
        )
        result = extract_tool_calls(content)
        self.assertEqual(len(result), 1)
        tc = result[0]
        self.assertEqual(tc["name"], "mcp__filesystem__list_directory")
        self.assertEqual(json.loads(tc["arguments"]), {"path": "/tmp"})
        self.assertTrue(tc["id"].startswith("text_fb_"))

    def test_json_inside_code_fence(self):
        content = (
            "Here is the call:\n\n"
            '```json\n{"name": "mcp__filesystem__read_file",'
            ' "arguments": {"path": "/etc/hosts"}}\n```\n'
        )
        result = extract_tool_calls(content)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["name"], "mcp__filesystem__read_file")

    def test_json_inside_unlabeled_code_fence(self):
        content = (
            '```\n{"name": "mcp__server__tool",'
            ' "arguments": {}}\n```'
        )
        result = extract_tool_calls(content)
        self.assertEqual(len(result), 1)

    def test_array_of_tool_calls(self):
        content = (
            '[{"name": "mcp__filesystem__list_directory", "arguments": {"path": "/tmp"}},'
            ' {"name": "mcp__filesystem__list_directory", "arguments": {"path": "/var"}}]'
        )
        result = extract_tool_calls(content)
        self.assertEqual(len(result), 2)
        self.assertEqual(json.loads(result[0]["arguments"]), {"path": "/tmp"})
        self.assertEqual(json.loads(result[1]["arguments"]), {"path": "/var"})

    def test_inline_json_with_surrounding_prose(self):
        content = (
            "I'll list the files for you. "
            '{"name": "mcp__filesystem__list_directory", "arguments": {"path": "/tmp"}} '
            "and that should do it."
        )
        result = extract_tool_calls(content)
        self.assertEqual(len(result), 1)

    def test_arguments_as_json_string(self):
        # Some models double-encode arguments as a JSON string.
        content = (
            '{"name": "mcp__filesystem__read_file",'
            ' "arguments": "{\\"path\\": \\"/tmp/x\\"}"}'
        )
        result = extract_tool_calls(content)
        self.assertEqual(len(result), 1)
        # The arguments field stays as the JSON string the model emitted.
        self.assertEqual(json.loads(result[0]["arguments"]), {"path": "/tmp/x"})

    def test_arguments_missing_defaults_to_empty(self):
        content = '{"name": "mcp__server__no_args_tool"}'
        result = extract_tool_calls(content)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["arguments"], "{}")

    def test_invalid_arguments_string_is_rejected(self):
        # If arguments is a non-JSON string, refuse — never dispatch garbage.
        content = (
            '{"name": "mcp__server__tool",'
            ' "arguments": "this is not json"}'
        )
        self.assertEqual(extract_tool_calls(content), [])

    def test_non_mcp_name_is_rejected(self):
        # Names without the mcp__ prefix are not our tools.
        content = '{"name": "delete_everything", "arguments": {}}'
        self.assertEqual(extract_tool_calls(content), [])

    def test_nested_arguments_object(self):
        content = (
            '{"name": "mcp__filesystem__edit_file",'
            ' "arguments": {"path": "/x", "edits": [{"line": 1, "text": "hi"}]}}'
        )
        result = extract_tool_calls(content)
        self.assertEqual(len(result), 1)
        args = json.loads(result[0]["arguments"])
        self.assertEqual(args["edits"][0]["text"], "hi")

    def test_multiple_inline_calls_deduped_by_position(self):
        # Two distinct calls at different positions, not duplicates.
        content = (
            'First: {"name": "mcp__a__one", "arguments": {}}\n'
            'Second: {"name": "mcp__b__two", "arguments": {"k": 1}}'
        )
        result = extract_tool_calls(content)
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]["name"], "mcp__a__one")
        self.assertEqual(result[1]["name"], "mcp__b__two")

    def test_malformed_json_after_match_is_skipped(self):
        # Hint matches but the body is garbage — should not crash.
        content = '{"name": "mcp__server__tool", "arguments": broken'
        self.assertEqual(extract_tool_calls(content), [])


if __name__ == "__main__":
    unittest.main()
