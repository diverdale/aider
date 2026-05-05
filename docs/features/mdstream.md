# Streaming Markdown Improvements

The streaming markdown renderer in `aider/mdstream.py` got a substantial overhaul in this fork. Three concrete user-visible improvements:

1. **XML-style fences render as code blocks**, not raw HTML. When aider's `choose_fence` picks `<source>...</source>` (because your chat files contain triple-backticks), the model emits `<source>python ... </source>` blocks. The fork rewrites these to backtick fences before Rich's Markdown parser sees them, so they syntax-highlight properly.
2. **Filename-based language inference.** A code block opened with ```` ```add.py ```` (or ```` ```src/utils/add.py ````) gets Python syntax highlighting via the file extension — even though "add.py" isn't a Pygments lexer alias.
3. **Code blocks are themed via `--code-theme`** without padding or panels, with line numbers. Cleaner than upstream's panel-bordered code rendering for terminal use.

Plus an SSL-fix-adjacent bug fix in normalization (see [The XML fence bug](#the-xml-fence-bug)) caught and shipped during the work.

---

## XML fence rewriting

### The problem

Aider's `Coder.choose_fence` picks a fence style for the conversation based on what's safe given the files in chat. If any chat file contains triple-backticks (common in markdown docs, shell heredocs, etc.), the picked fence falls back to one of:

```
<source>...</source>
<code>...</code>
<pre>...</pre>
<codeblock>...</codeblock>
<sourcecode>...</sourcecode>
```

The model then emits its responses using these XML fences. Rich's Markdown parser doesn't recognize them as code fences — it treats them as inline HTML and renders the whole block as raw text in the terminal.

### The fix

`mdstream.normalize_markdown_for_terminal(text)` runs as a preprocessing step before every render call (in both `MarkdownStream.update` for streaming and `io.assistant_output` for non-streaming). It rewrites XML fence openers and closers into quadruple-backtick fences:

```
<source>python   →   ````python
some code        →   some code
</source>        →   ````
```

The opener match is **prefix-based**, so `<source>` (bare) and `<source>python` (with language token attached, the actual emission shape from aider's prompt templates) both convert. The trailing language token is preserved as the fence info string for syntax highlighting.

Quadruple backticks (instead of triple) are used because the model's content might itself contain triple-backticks (CommonMark allows `` ``` `` inside a `` ```` `` fence) — a defensive choice carried over from upstream.

### The XML fence bug

Worth calling out as a regression that was caught and fixed during this work:

Upstream aider had a guard in `Coder.show_pretty()`:

```python
if self.fence[0][0] != "`":
    return False
```

…which disabled pretty rendering whenever an XML fence was active. With this guard removed (in favor of normalization), an exact-match-only normalizer left `<source>python` (the actual emission from the prompt templates) **untouched**, so Rich still rendered it as raw HTML.

The fix: the normalizer's match is now prefix-based (matches `<source>` plus any trailing token), so the prompt-template-emitted `<source>python` correctly converts to ```` ````python `` instead of passing through. See `tests/basic/test_mdstream.py::test_normalize_converts_xml_opener_with_language` for the regression test.

---

## Language inference

### From a fence info string

`mdstream.NoInsetCodeBlock._resolve_lexer_name` resolves the fence info string (the part after the opening backticks) to a Pygments lexer name. It tries:

1. **Direct extension map** — handles `.py`, `.js`, `.ts`, `.tsx`, `.jsx`, `.json`, `.md`, `.sh`, `.zsh`, `.yaml`, `.yml`, `.toml`, `.html`, `.css`, `.sql`, `.go`, `.rs`, `.java`, `.c`, `.h`, `.cpp`, `.hpp`, `.cs`, `.rb`, `.php`, `.xml`, `.ini`, `.cfg`. So a code block opened with ```` ```math/safeAdd.py ```` highlights as Python.
2. **Filename-with-prefix tokens** — `file=add.py`, `filename=src/utils/add.py`, `path=foo/bar.py:` all parse correctly. The prefix is stripped and the basename is checked against the extension map.
3. **Direct `get_lexer_by_name`** — falls back to whatever Pygments accepts (e.g. ```` ```python ```` works as before).
4. **`get_lexer_for_filename`** — for filenames with extensions Pygments knows but isn't in the extension map.
5. **Body-content guessing** — if the fence info is missing, runs a few quick regexes to detect Python (`def`, `import`, etc.) before falling back to Pygments' `guess_lexer`.

The fork's prompt templates and the model's natural output both like emitting code blocks tagged with the filename rather than the language. This resolver makes that habit work without forcing the user (or model) to know Pygments alias names.

### Fallbacks

If everything fails, the lexer falls back to `text` — Pygments still renders the block, just without colorization.

---

## Code block rendering

`NoInsetCodeBlock` overrides Rich's default `CodeBlock` for terminal-friendly output:

| Setting | Value | Why |
|---|---|---|
| `padding` | `(0, 0)` | Eliminates the 1-line vertical and 4-column horizontal padding Rich adds by default. Saves real estate. |
| `line_numbers` | `True` | Always on. Useful for referring to code positions in conversation. |
| `word_wrap` | `False` | Long lines truncate rather than wrap. Wrapping in a stream-rendered code block produces visually ugly results when the buffer is repaintainted; truncation is cleaner. |
| `theme` | `code_theme` setting | Honors the user's `--code-theme` (Pygments style name). |

The `code_theme` flows in via `NoInsetMarkdown(text, code_theme=...)` which the fork makes plumbable end-to-end (it stores it on a class-level fallback so per-instance code blocks pick it up). Default is `default` (Pygments' light theme); set `--code-theme monokai` for a dark code style on dark backgrounds.

---

## Headings

`mdstream.LeftHeading` overrides Rich's default centered headings:

- **H1** is rendered as a Rich `Panel` with a heavy box border; the title text inside the panel is left-aligned (Rich's default centers it).
- **H2** has a blank line before it (preserves visual breathing room) and is left-aligned styled text.
- **H3+** are left-aligned styled text without the blank line.

Net effect: when the model writes a multi-section reply with H1 / H2 / H3 headings, the layout reads like prose instead of like a centered title page.

---

## What you might still see go wrong

Two known quirks not yet fixed:

- **Spinner / Live overlap.** The `WaitingSpinner` is a daemon thread writing to stdout; `MarkdownStream` starts a Rich `Live` on the same console. There's a short window during the transition where ANSI sequences from both can interleave, producing a flicker on the first line of streamed output. Rare, hard to reproduce, low priority.
- **Throttle-skip path.** `MarkdownStream.update` returns early when fewer than `live_window` new lines are available, without refreshing the live tail. In practice the next chunk's update catches up; you might see a brief pause if the stream stalls right at a window boundary. Worth fixing in a polish pass.

---

## Settings reference

| Setting | Default | Notes |
|---|---|---|
| `code-theme` | `default` | Pygments style applied to code blocks. See <https://pygments.org/styles/> for available values. |

Only one setting; everything else is automatic. Themes set `code-theme` as part of the preset (most use `monokai`; light themes use `default`).

---

## Implementation notes

`aider/mdstream.py` is the file. Key entry points:

- `normalize_markdown_for_terminal(text)` — preprocesses model output. Called from `MarkdownStream.update` and `io.assistant_output`. Rewrites XML fences and limits consecutive blank lines.
- `NoInsetMarkdown` — Rich `Markdown` subclass that swaps in `NoInsetCodeBlock` for fences and `LeftHeading` for headings. Stores `code_theme` for child code blocks.
- `NoInsetCodeBlock._resolve_lexer_name(lexer_name, code)` — the language inference logic.
- `MarkdownStream` — the streaming renderer. Holds the `rich.live.Live` instance and the line-by-line update logic.

Tests in `tests/basic/test_mdstream.py` cover:

- Normalization of bare and language-laden XML fences.
- Lexer resolution from filename tokens with various decoration (`file=foo.py`, `path=src/foo.py:`, etc.).
- Lexer resolution for unlabeled Python code via body content.
