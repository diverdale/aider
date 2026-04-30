#!/usr/bin/env python

import io
import os
import re
import time

from pygments.lexers import get_lexer_by_name, get_lexer_for_filename, guess_lexer
from pygments.util import ClassNotFound
from rich import box
from rich.console import Console
from rich.live import Live
from rich.markdown import CodeBlock, Heading, Markdown
from rich.panel import Panel
from rich.syntax import Syntax
from rich.text import Text

from aider.dump import dump  # noqa: F401

_text_prefix = """
# Header

Lorem Ipsum is simply dummy text of the printing and typesetting industry.
Lorem Ipsum has been the industry's standard dummy text ever since the 1500s,
when an unknown printer took a galley of type and scrambled it to make a type
specimen book. It has survived not only five centuries, but also the leap into
electronic typesetting, remaining essentially unchanged. It was popularised in
the 1960s with the release of Letraset sheets containing Lorem Ipsum passages,
and more recently with desktop publishing software like Aldus PageMaker
including versions of Lorem Ipsum.



## Sub header

- List 1
- List 2
- List me
- List you



```python
"""

_text_suffix = """
```

## Sub header too

The end.

"""  # noqa: E501

DISPLAY_FENCE_OPENERS = {
    "<source>",
    "<code>",
    "<pre>",
    "<codeblock>",
    "<sourcecode>",
}

DISPLAY_FENCE_CLOSERS = {
    "</source>",
    "</code>",
    "</pre>",
    "</codeblock>",
    "</sourcecode>",
}


class NoInsetCodeBlock(CodeBlock):
    """A code block with syntax highlighting and no padding."""

    # Class variable set by NoInsetMarkdown to pass theme to instances
    _default_code_theme = "monokai"

    @staticmethod
    def _looks_like_python(code):
        """Heuristic detection for Python snippets when fence language is missing."""
        if not code:
            return False

        markers = [
            r"^\s*def\s+\w+\s*\(",
            r"^\s*class\s+\w+\s*[:\(]",
            r"^\s*from\s+\w[\w\.]*\s+import\s+",
            r"^\s*import\s+\w",
            r"^\s*if\s+__name__\s*==\s*['\"]__main__['\"]\s*:",
            r"\bNone\b|\bTrue\b|\bFalse\b",
        ]

        for marker in markers:
            if re.search(marker, code, flags=re.MULTILINE):
                return True

        return False

    @staticmethod
    def _normalize_fence_token(lexer_name):
        """Normalize fence info token for language/filename detection."""
        if not lexer_name:
            return ""

        token = str(lexer_name).strip().split()[0]
        token = token.strip("`'\"()[]{}<>:,;")

        for prefix in ("file=", "filename=", "path="):
            if token.lower().startswith(prefix):
                token = token.split("=", 1)[1].strip("`'\"()[]{}<>:,;")
                break

        # Keep only final path segment for extension checks.
        token = os.path.basename(token)
        return token.strip()

    @staticmethod
    def _lexer_from_extension(token):
        """Direct extension map for common languages before Pygments lookups."""
        ext = os.path.splitext(token)[1].lower()
        ext_to_lexer = {
            ".py": "python",
            ".js": "javascript",
            ".ts": "typescript",
            ".tsx": "tsx",
            ".jsx": "jsx",
            ".json": "json",
            ".md": "markdown",
            ".sh": "bash",
            ".zsh": "bash",
            ".yaml": "yaml",
            ".yml": "yaml",
            ".toml": "toml",
            ".html": "html",
            ".css": "css",
            ".sql": "sql",
            ".go": "go",
            ".rs": "rust",
            ".java": "java",
            ".c": "c",
            ".h": "c",
            ".cpp": "cpp",
            ".hpp": "cpp",
            ".cs": "csharp",
            ".rb": "ruby",
            ".php": "php",
            ".xml": "xml",
            ".ini": "ini",
            ".cfg": "ini",
        }
        return ext_to_lexer.get(ext)

    @staticmethod
    def _resolve_lexer_name(lexer_name, code=None):
        """Resolve rich fence info into a concrete lexer name.

        Supports both language fences (```python) and filename fences (```add.py).
        """
        if not lexer_name:
            if code:
                if NoInsetCodeBlock._looks_like_python(code):
                    return "python"
                try:
                    lexer = guess_lexer(code)
                    return lexer.aliases[0] if lexer.aliases else "text"
                except (ClassNotFound, Exception):
                    return "text"
            return "text"

        token = NoInsetCodeBlock._normalize_fence_token(lexer_name)
        if not token:
            return "text"

        ext_lexer = NoInsetCodeBlock._lexer_from_extension(token)
        if ext_lexer:
            return ext_lexer

        try:
            lexer = get_lexer_by_name(token)
            return lexer.aliases[0] if lexer.aliases else token
        except (ClassNotFound, Exception):
            pass

        # If the fence token looks like a filename, use extension-based detection.
        if "." in token:
            try:
                lexer = get_lexer_for_filename(token)
                return lexer.aliases[0] if lexer.aliases else token
            except (ClassNotFound, Exception):
                pass

        if code:
            if NoInsetCodeBlock._looks_like_python(code):
                return "python"
            try:
                lexer = guess_lexer(code)
                return lexer.aliases[0] if lexer.aliases else "text"
            except (ClassNotFound, Exception):
                pass

        return "text"

    def __rich_console__(self, console, options):
        code = str(self.text).rstrip()
        lexer_name = self._resolve_lexer_name(self.lexer_name, code)

        # Use theme from CodeBlock or fall back to class default
        theme = self.theme or NoInsetCodeBlock._default_code_theme or "monokai"

        syntax = Syntax(
            code,
            lexer_name,
            theme=theme,
            word_wrap=False,
            line_numbers=True,
            padding=(0, 0),
        )
        yield syntax


class LeftHeading(Heading):
    """A heading class that renders left-justified."""

    def __rich_console__(self, console, options):
        text = self.text
        text.justify = "left"  # Override justification
        if self.tag == "h1":
            # Draw a border around h1s, but keep text left-aligned
            yield Panel(
                text,
                box=box.HEAVY,
                style="markdown.h1.border",
            )
        else:
            # Styled text for h2 and beyond
            if self.tag == "h2":
                yield Text("")  # Keep the blank line before h2
            yield text


class NoInsetMarkdown(Markdown):
    """Markdown with code blocks that have no padding and left-justified headings."""

    elements = {
        **Markdown.elements,
        "fence": NoInsetCodeBlock,
        "code_block": NoInsetCodeBlock,
        "heading_open": LeftHeading,
    }

    def __init__(self, text, *, code_theme=None, **kwargs):
        """Initialize with explicit code_theme support.

        Args:
            text: Markdown source text
            code_theme: Theme name for code blocks (e.g., "monokai", "vim")
            **kwargs: Other markdown parameters
        """
        # Store code_theme on the class so CodeBlock instances can access it
        if code_theme:
            NoInsetCodeBlock._default_code_theme = code_theme
        super().__init__(text, code_theme=code_theme, **kwargs)


def _strip_xml_fence_prefix(stripped, lowered, openers):
    """If `stripped` starts with one of `openers` (matched case-insensitively),
    return the trailing portion of the line — empty string for a bare opener,
    or a language token like "python" for `<source>python`. Returns None if no
    opener matched, so callers can distinguish "matched, no language" from "no
    match" (the bare and language cases both need the line rewritten)."""
    for opener in openers:
        if lowered.startswith(opener):
            return stripped[len(opener):].strip()
    return None


def normalize_markdown_for_terminal(text):
    """Normalize aider output into markdown that Rich can render consistently."""
    if not text:
        return text

    lines = text.splitlines()
    in_fence = False
    blank_count_prose = 0
    blank_count_code = 0
    out_lines = []

    for line in lines:
        stripped = line.strip()
        lowered = stripped.lower()

        # Aider may use XML-style fences for file edits when backticks would collide with file
        # contents. Convert them into markdown fences for display so pretty rendering still works.
        # Aider's prompt templates emit the opener fused with a language token, e.g.
        # `<source>python`, so we match by prefix and preserve the trailing token as the
        # fence info string for syntax highlighting.
        opener_lang = _strip_xml_fence_prefix(stripped, lowered, DISPLAY_FENCE_OPENERS)
        if opener_lang is not None:
            in_fence = True
            blank_count_prose = 0
            blank_count_code = 0
            out_lines.append("````" + opener_lang if opener_lang else "````")
            continue

        if _strip_xml_fence_prefix(stripped, lowered, DISPLAY_FENCE_CLOSERS) is not None:
            in_fence = False
            blank_count_prose = 0
            blank_count_code = 0
            out_lines.append("````")
            continue

        if stripped.startswith("```"):
            in_fence = not in_fence
            blank_count_prose = 0
            blank_count_code = 0
            out_lines.append(line)
            continue

        if in_fence:
            if stripped == "":
                blank_count_code += 1
                if blank_count_code <= 1:
                    out_lines.append("")
                continue

            blank_count_code = 0
            out_lines.append(line)
            continue

        if stripped == "":
            blank_count_prose += 1
            if blank_count_prose <= 1:
                out_lines.append("")
            continue

        blank_count_prose = 0
        out_lines.append(line)

    return "\n".join(out_lines)


class MarkdownStream:
    """Streaming markdown renderer that progressively displays content with a live updating window.

    Uses rich.console and rich.live to render markdown content with smooth scrolling
    and partial updates. Maintains a sliding window of visible content while streaming
    in new markdown text.
    """

    live = None  # Rich Live display instance
    when = 0  # Timestamp of last update
    min_delay = 1.0 / 20  # Minimum time between updates (20fps)
    live_window = 6  # Number of lines to keep visible at bottom during streaming

    def __init__(self, mdargs=None, console=None):
        """Initialize the markdown stream.

        Args:
            mdargs (dict, optional): Additional arguments to pass to rich Markdown renderer
        """
        self.printed = []  # Stores lines that have already been printed
        self.console = console

        if mdargs:
            self.mdargs = mdargs
        else:
            self.mdargs = dict()

        # Defer Live creation until the first update.
        self.live = None
        self._live_started = False

    def _render_markdown_to_lines(self, text):
        """Render markdown text to a list of lines.

        Args:
            text (str): Markdown text to render

        Returns:
            list: List of rendered lines with line endings preserved
        """
        # Render the markdown to a string buffer
        string_io = io.StringIO()
        color_system = self.console.color_system if self.console is not None else None
        console = Console(file=string_io, force_terminal=True, color_system=color_system)
        markdown = NoInsetMarkdown(text, **self.mdargs)
        console.print(markdown)
        output = string_io.getvalue()

        # Split rendered output into lines
        return output.splitlines(keepends=True)

    def __del__(self):
        """Destructor to ensure Live display is properly cleaned up."""
        if self.live:
            try:
                self.live.stop()
            except Exception:
                pass  # Ignore any errors during cleanup

    def update(self, text, final=False):
        """Update the displayed markdown content.

        Args:
            text (str): The markdown text received so far
            final (bool): If True, this is the final update and we should clean up

        Splits the output into "stable" older lines and the "last few" lines
        which aren't considered stable. They may shift around as new chunks
        are appended to the markdown text.

        The stable lines emit to the console above the Live window.
        The unstable lines emit into the Live window so they can be repainted.

        Markdown going to the console works better in terminal scrollback buffers.
        The live window doesn't play nice with terminal scrollback.
        """
        # On the first call, stop the spinner and start the Live renderer
        if not getattr(self, "_live_started", False):
            self.live = Live(
                Text(""),
                console=self.console,
                refresh_per_second=1.0 / self.min_delay,
            )
            self.live.start()
            self._live_started = True

        now = time.time()
        # Throttle updates to maintain smooth rendering
        if not final and now - self.when < self.min_delay:
            return
        self.when = now

        # Measure render time and adjust min_delay to maintain smooth rendering
        normalized_text = normalize_markdown_for_terminal(text)

        start = time.time()
        lines = self._render_markdown_to_lines(normalized_text)
        render_time = time.time() - start

        # Set min_delay to render time plus a small buffer
        self.min_delay = min(max(render_time * 10, 1.0 / 20), 2)

        num_lines = len(lines)

        # How many lines have "left" the live window and are now considered stable?
        # Or if final, consider all lines to be stable.
        if not final:
            num_lines -= self.live_window

        # If we have stable content to display...
        if final or num_lines > 0:
            # How many stable lines do we need to newly show above the live window?
            num_printed = len(self.printed)
            show = num_lines - num_printed

            # Skip if no new lines to show above live window
            if show <= 0:
                return

            # Get the new lines and display them
            show = lines[num_printed:num_lines]
            show = "".join(show)
            show = Text.from_ansi(show)
            self.live.console.print(show)  # to the console above the live area

            # Update our record of printed lines
            self.printed = lines[:num_lines]

        # Handle final update cleanup
        if final:
            self.live.update(Text(""))
            self.live.stop()
            self.live = None
            return

        # Update the live window with remaining lines
        rest = lines[num_lines:]
        rest = "".join(rest)
        rest = Text.from_ansi(rest)
        self.live.update(rest)

    def find_minimal_suffix(self, text, match_lines=50):
        """
        Splits text into chunks on blank lines "\n\n".
        """


if __name__ == "__main__":
    with open("aider/io.py", "r") as f:
        code = f.read()
    _text = _text_prefix + code + _text_suffix
    _text = _text * 10

    pm = MarkdownStream()
    print("Using NoInsetMarkdown for code blocks with padding=0")
    for i in range(6, len(_text), 5):
        pm.update(_text[:i])
        time.sleep(0.01)

    pm.update(_text, final=True)
