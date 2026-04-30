#!/usr/bin/env python

from aider.mdstream import NoInsetCodeBlock


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
