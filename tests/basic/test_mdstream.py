#!/usr/bin/env python

from aider.mdstream import NoInsetCodeBlock, normalize_markdown_for_terminal


def test_resolve_lexer_from_python_filename_token():
    code = "def add(a, b):\n    return a + b\n"
    assert NoInsetCodeBlock._resolve_lexer_name("safe_add.py", code) == "python"


def test_resolve_lexer_from_filename_key_value_token():
    code = "def add(a, b):\n    return a + b\n"
    assert NoInsetCodeBlock._resolve_lexer_name("filename=safe_add.py", code) == "python"


def test_resolve_lexer_from_path_like_token_with_punctuation():
    code = "def add(a, b):\n    return a + b\n"
    token = "path=src/utils/safe_add.py:"
    assert NoInsetCodeBlock._resolve_lexer_name(token, code) == "python"


def test_resolve_lexer_unlabeled_python_code():
    code = "def add(a, b):\n    return a + b\n"
    assert NoInsetCodeBlock._resolve_lexer_name(None, code) == "python"


def test_normalize_converts_xml_opener_with_language():
    """Aider's prompts instruct the model to emit `{fence[0]}python` — when the
    chosen fence is `<source>`, that becomes `<source>python` on a single line.
    Normalization must convert this to a markdown fence so Rich renders it as
    a code block instead of inline HTML."""
    src = (
        "Here are the *SEARCH/REPLACE* blocks:\n"
        "\n"
        "<source>python\n"
        "hello.py\n"
        "<<<<<<< SEARCH\n"
        "print('a')\n"
        "=======\n"
        "print('b')\n"
        ">>>>>>> REPLACE\n"
        "</source>\n"
    )
    out = normalize_markdown_for_terminal(src)

    assert "<source>python" not in out, (
        "opener with language must be rewritten, not passed through"
    )
    assert "</source>" not in out, "closer must be rewritten"
    # Some markdown fence must appear in place of the XML opener.
    assert "```" in out
    # Language token is preserved so the code block keeps syntax highlighting.
    assert "python" in out


def test_normalize_converts_bare_xml_fence():
    """Regression check: bare `<source>` / `</source>` (no language) still
    converts — this is the case the original code already handled."""
    src = "<source>\nfoo\n</source>\n"
    out = normalize_markdown_for_terminal(src)
    assert "<source>" not in out
    assert "</source>" not in out
    assert "```" in out
