"""Minimal Pygments lexer for EnergyPlus IDF files.

Registers the ``idf`` language name with Pygments so that fenced code blocks
tagged as ``idf`` in Markdown are rendered with the correct ``language-idf``
CSS class instead of falling back to ``language-text``.

The actual syntax highlighting in the browser is handled by the Monaco-based
IDF editor bundle (``idf-editor/``), so this lexer only needs to provide basic
token classification — enough for Pygments to produce reasonable colour output
as a static fallback.
"""

from __future__ import annotations

from typing import ClassVar

from pygments.lexer import RegexLexer, bygroups
from pygments.token import Comment, Keyword, Name, Number, Punctuation, String, Text


class IDFLexer(RegexLexer):
    """Pygments lexer for EnergyPlus Input Data Files (.idf)."""

    name = "IDF"
    aliases: ClassVar[list[str]] = ["idf"]
    filenames: ClassVar[list[str]] = ["*.idf"]
    mimetypes: ClassVar[list[str]] = ["text/x-idf"]

    tokens: ClassVar[dict] = {
        "root": [
            # Comments: everything after '!'
            (r"!.*$", Comment.Single),
            # Object terminator
            (r";", Punctuation),
            # Field separator
            (r",", Punctuation),
            # Numeric values (integer and float, with optional sign)
            (r"-?\d+\.\d*([eE][+-]?\d+)?", Number.Float),
            (r"-?\d+([eE][+-]?\d+)?", Number.Integer),
            # Special keywords
            (
                r"\b(autosize|autocalculate|yes|no)\b",
                Keyword,
            ),
            # Object name (first non-whitespace token on a line before comma/semicolon)
            # This matches EnergyPlus class names like "Zone," or "Building,"
            (r"^([A-Za-z][A-Za-z0-9:_ -]*)(,)", bygroups(Name.Class, Punctuation)),
            # Field values (general text)
            (r"[^\s,;!]+", String),
            # Whitespace
            (r"\s+", Text),
        ],
    }
