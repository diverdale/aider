# Configurable Status Bar

The fork adds a live, configurable status bar above the input prompt. It surfaces:

- **Mode hint** — what Enter / Alt-Enter do given your current multiline state.
- **Model + context usage** — `model=claude-opus-4-5 ctx=42%` so you can watch the budget shrink without typing `/tokens`.
- **Layout indicator** — when you've switched away from the default single-pane layout.
- **Progress strip** — `Now:apply edits Next:finalize Waiting:edit application`, updated as the coder moves through phases of a turn.

Two knobs control the look:

- `ui-density`: how much information to pack in (`compact`, `comfortable`, `focus`).
- `ui-layout`: which workflow style to optimize for (`single`, `split`, `review-first`).

Plus an escape hatch for full customization: `ui-key-hints-template` lets you override the line entirely with a format string.

---

## Quick start

```bash
aider --ui-density compact --ui-layout single
```

Or in `.aider.conf.yml`:

```yaml
ui-density: compact
ui-layout: review-first
```

You can change density mid-session by re-running aider — there isn't (yet) a slash command to toggle it without a restart.

---

## Density modes

### `comfortable` (default)

The richest view. Includes the mode hint, base keybinding hints, model, context %, layout (when non-default), and the progress strip:

```
Now:idle Next:waiting for input Waiting:- | Enter submit | Alt-Enter newline | Ctrl-X Ctrl-E edit in editor | Ctrl-Up/Down history | model=claude-opus-4-5 | ctx=42%
```

Best for long sessions on a wide terminal where you have screen real estate to spare.

### `compact`

Drops the keybinding hints and re-flows. Keeps model + ctx + layout:

```
Now:idle Next:waiting for input Waiting:- | Enter submit | Alt-Enter newline | model=claude-opus-4-5 | ctx=42%
```

Right tradeoff for narrow terminals or split-screen setups.

### `focus`

Strips everything except the mode hint and the progress strip. Best for screencasts and pair programming when you want minimum visual chrome:

```
Now:apply edits Next:finalize response Waiting:edit application | Enter submit | Alt-Enter newline
```

---

## Layout modes

### `single` (default)

Standard aider behavior. No layout segment in the status bar.

### `review-first`

Optimized for "let the model propose, I review every diff before merging" workflows. Adds review/undo hints to the bar:

```
... | /diff review | /undo revert
```

The progress strip's wording also shifts toward review-oriented phrasing — `now: review context`, `now: read model response`, `now: review response` — so you can see where in the lifecycle you are.

### `split`

For terminals where you've split read-only context and editable changes into separate panes. Adds:

```
... | split: RO + editable panes
```

The progress strip shows `Layout:split` instead of the standard format.

---

## Progress strip

The progress strip is the pre-status portion that reads `Now:... Next:... Waiting:...`. It's updated by `Coder` at each lifecycle transition: preparing context, requesting the model, reading the response, applying edits, running lint/test, idle.

You can disable the progress strip independently of density:

```bash
aider --no-ui-progress-strip
```

(Or `ui-progress-strip: false` in config.)

---

## Custom templates

For full control, set `ui-key-hints-template` to a format string. The fork's defaults are good but if you want a particular layout, it's available:

```yaml
ui-key-hints-template: "[{model}] {context_pct} | {mode}"
```

Available placeholders:

| Placeholder | Value |
|---|---|
| `{mode}` | `normal` or `multiline` |
| `{density}` | `compact`, `comfortable`, or `focus` |
| `{layout}` | `single`, `split`, or `review-first` |
| `{model}` | Active model name (e.g. `claude-opus-4-5`) |
| `{context_used}` | Tokens used in the current message budget |
| `{context_max}` | Model's max context |
| `{context_pct}` | Percentage used (e.g. `42%`) |

If you reference a placeholder aider doesn't provide, it's left as `{name}` rather than crashing — typo-tolerant.

The progress strip has its own template, `ui-progress-template`:

```yaml
ui-progress-template: "▶ {now} → {next}"
```

Placeholders: `{now}`, `{next}`, `{waiting_on}`.

---

## All settings

| Setting | Default | Notes |
|---|---|---|
| `ui-density` | `comfortable` | One of `compact`, `comfortable`, `focus`. |
| `ui-layout` | `single` | One of `single`, `split`, `review-first`. |
| `ui-progress-strip` | true | Set false to hide the `Now:... Next:...` line. |
| `ui-key-hints-template` | (built-in by density) | Custom format string with placeholders above. |
| `ui-progress-template` | (built-in by layout) | Custom format for the progress strip. |

Validation runs at startup; an invalid `ui-density` or `ui-layout` raises with a list of valid values.

---

## Implementation notes

The status bar is rendered as the bottom toolbar of `prompt_toolkit`'s `PromptSession`:

- `aider/io.py::InputOutput.__init__` — validates settings, stores them on the IO object, registers `_build_key_hints` as `bottom_toolbar` on the session.
- `aider/io.py::InputOutput._build_key_hints` — returns the toolbar string each render cycle. Honors `ui_key_hints_template` if set; otherwise dispatches by `ui_density`.
- `aider/io.py::InputOutput._build_progress_segment` — returns the leading `Now:... Next:...` part. Honors `ui_progress_template` if set; otherwise dispatches by `ui_layout`.
- `aider/io.py::InputOutput.set_progress_state(now=..., next=..., waiting_on=...)` — called by `Coder.send_message` at lifecycle transitions to update the strip.
- `aider/io.py::InputOutput.set_hint_model(name)` and `set_hint_context_usage(...)` — called by `Coder` to update the model/budget portion.

The strip is best-effort: missing values render as `-`, validation errors fall back to defaults, and the toolbar is rebuilt on every prompt render so changes are immediate.
