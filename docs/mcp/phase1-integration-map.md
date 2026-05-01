# MCP Phase 1 Integration Map

This memory captures the *exact* code surfaces Phase 1 of MCP support touches, derived from a symbolic survey of `aider/coders/base_coder.py`. Read alongside `docs/mcp-support-roadmap.md` and `docs/mcp/research.md`.

## The key insight: integration point is `send_message`, not `show_send_output_stream`

The streaming chunk loop in `Coder.show_send_output_stream` (1972–2047) is where tool-call deltas are *accumulated*. The actual orchestration — "model called tools → run them → ask the model to continue" — happens one level up, in `Coder.send_message` (1445–1695). The retry loop there at line ~1494 already implements the exact pattern we need:

```python
while True:
    try:
        yield from self.send(messages, functions=self.functions)
        break                                          # <-- model finished cleanly
    except FinishReasonLength:
        # save partial content into messages, retry
        self.multi_response_content = self.get_multi_response_content_in_progress()
        messages.append({"role": "assistant", "content": self.multi_response_content, "prefix": True})
        # falls through to retry
    except <retry-able>: ...
    except <fatal>: ...
```

For MCP, add another break-clause after a successful `send()` return:

```python
if self.partial_tool_calls:
    # execute tool calls, append results to messages, re-enter loop
    self.multi_response_content = self.get_multi_response_content_in_progress()
    messages.append({"role": "assistant", "content": self.multi_response_content, "tool_calls": [...]})
    for call in self.partial_tool_calls:
        result = mcp_manager.execute(call)
        messages.append({"role": "tool", "tool_call_id": call.id, "content": result})
    if mcp_iterations >= MCP_MAX_ITERATIONS:
        break
    continue                                           # <-- re-enter loop
```

This mirrors the `FinishReasonLength` pattern almost exactly: save partial state, append messages, re-enter. **Architecturally, aider is much more MCP-ready than the surface read suggested.**

## State variables to add / preserve

### Add (new)

- `Coder.partial_tool_calls: list[dict]` — list of accumulated tool-call deltas from streaming. Reset in `Coder.send` (1862) alongside `partial_response_function_call`. Distinct from `partial_response_function_call` (which is the deprecated single-call API; can't be reused).

### Preserve (existing — touch carefully)

- `partial_response_content` — accumulating text content. Stays as-is. **Critical:** `Coder.send` (1862) resets this to `""` per call. Across MCP iterations within one turn, text must accumulate via `multi_response_content`, exactly like `FinishReasonLength` already does (see line 2210 `get_multi_response_content_in_progress` = cur + new).
- `partial_response_function_call` — the OLD, deprecated single-function-call API. Used only by `EditBlockFunctionCoder`, `WholeFileFunctionCoder`, `SingleWholeFileFunctionCoder`. **Don't merge MCP into this** — it's a different shape (single dict vs list of structured calls).
- `multi_response_content` — turn-level accumulator. MCP iteration would write to this between `send()` calls.
- `cur_messages` — chat history. Tool calls and results must be added here for the model to see context across turns. The shape `{role: "tool", tool_call_id: ..., content: ...}` is litellm-standard.

## Code surfaces to modify

### `aider/coders/base_coder.py`

1. **`Coder.__init__`** (298–558): initialize `self.partial_tool_calls = []` if MCP enabled.

2. **`Coder.send`** (1855–1906):
   - Line 1862: add `self.partial_tool_calls = []` reset.
   - Around the litellm.completion call (delegated to `aider/sendchat.py`): pass `tools=[...]` from MCP manager when MCP is configured.

3. **`Coder.show_send_output`** (non-streaming, 1908–1970):
   - Around line 1922 where `tool_calls` are already extracted (currently for the function-call API): also handle tool_calls list for MCP. Existing line:
     ```python
     if completion.choices[0].message.tool_calls:
         self.partial_response_function_call = (
             completion.choices[0].message.tool_calls[0].function
         )
     ```
     → split: legacy `partial_response_function_call` for func-coders, new `partial_tool_calls` (list) for MCP-enabled flow.

4. **`Coder.show_send_output_stream`** (streaming, 1972–2047):
   - Around lines 1985–1992 where function_call deltas are merged: parallel handler for `chunk.choices[0].delta.tool_calls` (a list of `ChatCompletionDeltaToolCall` with `index`, `id`, `function.name`, `function.arguments`). Merge by `index`.
   - The text path (`partial_response_content += text`, `live_incremental_response`) stays unchanged — text and tool calls coexist.

5. **`Coder.send_message`** (1445–1695):
   - After the inner `yield from self.send(...)` succeeds and the `try` exits cleanly: check `partial_tool_calls`. If non-empty, save state, append tool messages, re-enter loop. (Don't `break`.)
   - Add iteration counter; cap at `MCP_MAX_ITERATIONS` (env-configurable; **revise from 10 to ~25 per Serena onboarding observation**).
   - On overflow: surface a clear `tool_warning`, append a synthetic assistant message ("MCP iteration cap reached"), break.

6. **`Coder.add_assistant_reply_to_cur_messages`** (1774–1784):
   - Currently: appends `partial_response_content` and/or `partial_response_function_call` to `cur_messages`.
   - Add: when `partial_tool_calls` is set, the assistant message needs `tool_calls=[...]` per litellm/OpenAI shape, plus the tool-result messages (already in `cur_messages` from the iteration loop) need to be the next entries.

### `aider/sendchat.py`

- `litellm.completion(...)` call: thread `tools=` parameter through. litellm handles provider-specific conversion.
- `litellm.supports_function_calling(model_name)` gate: if MCP configured but model doesn't support tools, surface warning, suppress `tools=` param.

### Subclass impact (good news: minimal)

- **Function-call coders** (`editblock_func_coder.py`, `wholefile_func_coder.py`, `single_wholefile_func_coder.py`): use `partial_response_function_call` exclusively, never touch `partial_tool_calls`. **Unchanged.**
- **Text-based coders** (`editblock_coder.py`, `wholefile_coder.py`, `udiff_coder.py`, `patch_coder.py`, `architect_coder.py`, `context_coder.py`): parse `partial_response_content` in `get_edits()` / `reply_completed()`. Since `partial_response_content` ends up containing the full accumulated text across MCP iterations (via `multi_response_content` round-trip in the `finally` block at 1561), **unchanged.**

## Risks identified

1. **Text content accumulation across iterations.** The whole flow depends on `multi_response_content` correctly accumulating between `send()` calls. The existing `FinishReasonLength` path proves this works, but MCP's pattern (append tool calls + results) is subtly different. Test with a multi-iteration scenario before declaring it done.

2. **Streaming UX during long tool calls.** Per research D7 (buffer-then-call in v1), this is fine. But the `MarkdownStream` lifecycle (started at line 1483, finalized in `finally` at 1556) needs to reset between iterations. Either: tear down + re-init mdstream per send() call (probably the right move), or: keep one alive across the turn (more complex). **Defer decision to actual implementation.**

3. **Tool-call assistant message shape.** litellm/OpenAI expects `{role: "assistant", content: "...", tool_calls: [...]}`. Today aider sometimes sends `content` as `None` and uses `function_call` (line 1781). The MCP path needs the modern `tool_calls` array shape. Don't break the legacy path.

4. **`functions=self.functions` parameter** still passed to `send()` at line 1495. Coexists with MCP's `tools=` param. In litellm, `functions` is the deprecated API. For MCP-enabled flow, stop sending `functions=`. For function-call-coder flow (when not MCP-enabled), keep sending `functions=`. Decision lives in `send()`.

5. **`render_incremental_response` overrides** (`EditBlockFunctionCoder`, `WholeFileFunctionCoder`, `SingleWholeFileFunctionCoder`): these construct rendering content from the function call args. MCP doesn't change them, but worth eyeballing each subclass's logic to confirm.

## What this map does NOT cover (Phase 0/2 work)

- The `aider/mcp/` module itself (client/manager/config) — that's separate infrastructure, decided in research.md.
- Permission UX wiring — Phase 3.
- `format_messages()` changes for tool-result messages in chat history persistence — investigate when implementing.
- Test harness for the tool-use loop — Phase 1 deliverable, separate planning.

## Next steps when implementing Phase 1

1. Build `aider/mcp/` (client, manager, config) — independent module, no `base_coder.py` changes yet.
2. Add `aider/mcp/tool_schemas.py` to convert MCP tool defs → litellm `tools=` shape.
3. Modify `Coder.send` to inject `tools=` and track `partial_tool_calls`.
4. Modify `Coder.show_send_output_stream` to merge `tool_calls` deltas.
5. Modify `Coder.send_message` to add the "if partial_tool_calls, re-enter" branch.
6. Add `Coder.add_assistant_reply_to_cur_messages` shape handling for `tool_calls` array.
7. Tests: drive end-to-end with a fake MCP server and a mocked litellm streaming chunks emitter.
