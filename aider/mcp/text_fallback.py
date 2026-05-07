"""Text-fallback parser for MCP tool calls.

Many local models served via Ollama 'know' to call a tool but don't
emit it via the OpenAI `tool_calls` field — they put the JSON in the
text content instead. Without this fallback, MCP appears completely
broken on those models even though the model is producing the right
data, just in the wrong place.

This module extracts MCP tool calls from response content, returning
dicts in the same shape as `Coder.partial_tool_calls` entries so the
existing dispatch path can handle them unchanged.

Opt-in via `--mcp-text-fallback` (default off, since frontier models
should always use the structured field — enabling fallback for them
adds a small risk of mis-parsing prose that happens to look JSON-ish).
"""

import json
import re
import uuid

# Match any JSON-looking object that has "name": "mcp__<something>".
# We use the regex only to find candidate start positions; actual
# JSON parsing uses a brace-matching scan to handle nested objects.
_TOOL_CALL_HINT = re.compile(r'\{[^{]*?"name"\s*:\s*"(mcp__[^"]+)"', re.DOTALL)


def extract_tool_calls(content):
    """Return a list of tool-call dicts extracted from the model's text content.

    Each dict has the same shape as entries in `Coder.partial_tool_calls`:
    {id, name, arguments} where arguments is a JSON string.

    Returns [] when content is empty, has no MCP tool calls, or none
    of the candidates parse cleanly.
    """
    if not content:
        return []

    cleaned = _strip_code_fences(content)

    # First: try parsing the whole thing as JSON (single tool call or array).
    body = cleaned.strip()
    parsed = _try_json(body)
    if isinstance(parsed, dict):
        tc = _to_tool_call(parsed)
        if tc:
            return [tc]
    elif isinstance(parsed, list):
        results = [_to_tool_call(item) for item in parsed]
        results = [r for r in results if r]
        if results:
            return results

    # Otherwise scan for inline JSON objects matching the tool-call shape.
    results = []
    seen_starts = set()
    for match in _TOOL_CALL_HINT.finditer(cleaned):
        start = match.start()
        if start in seen_starts:
            continue
        seen_starts.add(start)
        end = _find_matching_brace(cleaned, start)
        if end is None:
            continue
        candidate = cleaned[start : end + 1]
        parsed = _try_json(candidate)
        if not isinstance(parsed, dict):
            continue
        tc = _to_tool_call(parsed)
        if tc:
            results.append(tc)
    return results


def _strip_code_fences(text):
    # Drop ```json / ``` opener and ``` closer. Keeps the body intact.
    text = re.sub(r"```(?:json|javascript|js|python|py)?\s*\n", "", text)
    return text.replace("```", "")


def _try_json(s):
    try:
        return json.loads(s)
    except (ValueError, TypeError):
        return None


def _find_matching_brace(text, start):
    # Scan forward from an opening `{` to find its matching `}`, accounting
    # for nested objects and double-quoted strings (with escape handling).
    depth = 0
    in_string = False
    escape = False
    for i in range(start, len(text)):
        ch = text[i]
        if escape:
            escape = False
            continue
        if ch == "\\":
            escape = True
            continue
        if ch == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return i
    return None


def _to_tool_call(obj):
    # Convert a parsed dict into the shape Coder.partial_tool_calls uses.
    if not isinstance(obj, dict):
        return None
    name = obj.get("name")
    if not isinstance(name, str) or not name.startswith("mcp__"):
        return None

    args = obj.get("arguments")
    if isinstance(args, dict):
        args_str = json.dumps(args)
    elif isinstance(args, str):
        # Some models double-encode arguments as a JSON string. Validate
        # it parses; if not, reject the call rather than dispatch garbage.
        if _try_json(args) is None:
            return None
        args_str = args
    elif args is None:
        args_str = "{}"
    else:
        return None

    return {
        "id": f"text_fb_{uuid.uuid4().hex[:8]}",
        "name": name,
        "arguments": args_str,
    }
