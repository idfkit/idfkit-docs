"""Pre-Pandoc LaTeX transformations for EnergyPlus documentation.

Handles custom macros and environments that Pandoc cannot process directly:
- siunitx \\SI{}, \\si{}, \\IP{}, \\ip{} macros and custom unit declarations
- Bracket macros: \\PB{}, \\RB{}, \\CB{}
- callout environment -> quote (Pandoc-friendly)
- Admonition macros: \\warning{}, \\caution{}, \\important{}, \\tip{},
  \\note{}, \\example{}, \\seealso{}, \\limitation{} -> bold-prefixed quotes
- Standalone bold-prefixed paragraphs (\\textbf{Note:} etc.) -> quote environments
- Plain-text Note:/Caution: prefixes inside callouts -> bold form
- Strip \\input{} directives (child files are separate pages)
"""

from __future__ import annotations

import logging
import re

logger = logging.getLogger(__name__)

# --- siunitx unit macros ---
# Custom units declared in header.tex via \DeclareSIUnit

SI_UNITS: dict[str, str] = {
    # SI custom units
    r"\area": "m²",
    r"\volume": "m³",
    r"\volumeFlowRate": "m³/s",
    r"\massFlowRate": "kg/s",
    r"\density": "kg/m³",
    r"\humidityRatio": "kg_W/kg_DA",
    r"\specificHeatCapacity": "J/(kg·K)",
    r"\specificEnthalpy": "J/kg",
    r"\coefficientOfPerformance": "W/W",
    r"\wattperVolumeFlowRate": "W·s/m³",
    r"\volumeFlowRateperArea": "(m³/s)/m²",
    r"\volumeFlowRateperWatt": "m³/(s·W)",
    r"\umolperAreaperSecond": "μmol/(m²·s)",
    r"\evapotranspirationRate": "kg/(m²·s)",
    # IP custom units
    r"\fahrenheit": "°F",
    r"\ft": "ft",
    r"\sqft": "ft²",
    r"\cfm": "ft³/min",
    r"\CFM": "CFM",
    r"\gal": "gal",
    r"\gpm": "gpm",
    r"\MBH": "MBH",
    # Standard siunitx units (common ones used in EnergyPlus docs)
    r"\watt": "W",
    r"\kilowatt": "kW",
    r"\megawatt": "MW",
    r"\joule": "J",
    r"\kilojoule": "kJ",
    r"\megajoule": "MJ",
    r"\kelvin": "K",
    r"\celsius": "°C",
    r"\meter": "m",
    r"\kilogram": "kg",
    r"\gram": "g",
    r"\second": "s",
    r"\minute": "min",
    r"\hour": "h",
    r"\ampere": "A",
    r"\volt": "V",
    r"\pascal": "Pa",
    r"\kilopascal": "kPa",
    r"\percent": "%",
    r"\liter": "L",
    r"\milli": "m",
    r"\kilo": "k",
    r"\mega": "M",
    r"\micro": "μ",
    r"\per": "/",
    r"\square": "²",
    r"\cubic": "³",
    r"\of": "·",
}

# siunitx prefix pattern for \SI{value}{unit} and \si{unit}
_BRACE_RE = r"\{([^{}]*(?:\{[^{}]*\}[^{}]*)*)\}"


def _expand_unit(unit_str: str) -> str:
    """Expand a siunitx unit specification to plain text."""
    result = unit_str
    # Sort by length (longest first) to avoid partial matches
    for macro, text in sorted(SI_UNITS.items(), key=lambda x: -len(x[0])):
        result = result.replace(macro, text)
    # Clean up remaining LaTeX artifacts
    result = result.replace("\\", "")
    result = result.replace("{", "")
    result = result.replace("}", "")
    return result.strip()


def expand_si_macros(text: str) -> str:
    r"""Expand \SI{value}{unit}, \si{unit}, \IP{value}{unit}, \ip{unit} macros."""

    # \SI{value}{unit} and \IP{value}{unit} -> "value unit"
    def replace_si_val_unit(m: re.Match) -> str:
        value = m.group(1)
        unit = _expand_unit(m.group(2))
        return f"{value} {unit}"

    text = re.sub(r"\\SI" + _BRACE_RE + _BRACE_RE, replace_si_val_unit, text)
    text = re.sub(r"\\IP" + _BRACE_RE + _BRACE_RE, replace_si_val_unit, text)

    # \si{unit} and \ip{unit} -> "unit"
    def replace_si_unit(m: re.Match) -> str:
        return _expand_unit(m.group(1))

    text = re.sub(r"\\si" + _BRACE_RE, replace_si_unit, text)
    text = re.sub(r"\\ip" + _BRACE_RE, replace_si_unit, text)

    return text


def _find_brace_content(text: str, start: int) -> tuple[str, int] | None:
    """Find the content of a brace group starting at *start*, handling arbitrary nesting.

    *start* must point to the opening ``{``.  Returns ``(content, end)``
    where *end* is the index just past the closing ``}``, or ``None`` if
    the braces are unbalanced.
    """
    if start >= len(text) or text[start] != "{":
        return None
    depth = 1
    i = start + 1
    while i < len(text) and depth > 0:
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
        i += 1
    if depth != 0:
        return None
    # content excludes the outer braces
    return text[start + 1 : i - 1], i


_BRACKET_MACROS = {
    "\\PB": ("\\left(", "\\right)"),
    "\\RB": ("\\left[", "\\right]"),
    "\\CB": ("\\left\\{", "\\right\\}"),
}


_BRACKET_MACRO_RE = re.compile(r"\\(?:PB|RB|CB)\{")


def _expand_all_bracket_macros(text: str) -> str:
    r"""Expand all ``\PB``, ``\RB``, ``\CB`` macros in *text*, inside-out.

    When an outer macro wraps inner macros (e.g. ``\PB{a \PB{b}}``) the
    inner content is recursively expanded first, so the final result
    contains no bracket macros regardless of nesting depth.

    Uses regex to jump to the next macro occurrence instead of scanning
    every character, which is critical for large files.
    """
    result: list[str] = []
    pos = 0
    while True:
        m = _BRACKET_MACRO_RE.search(text, pos)
        if m is None:
            result.append(text[pos:])
            break
        # Append everything before this macro
        result.append(text[pos : m.start()])
        macro = text[m.start() : m.end() - 1]  # e.g. "\\PB"
        brace_start = m.end() - 1  # position of the '{'
        found = _find_brace_content(text, brace_start)
        if found:
            content, end = found
            # Recursively expand any bracket macros inside the content
            content = _expand_all_bracket_macros(content)
            left, right = _BRACKET_MACROS[macro]
            result.append(f"{left} {content} {right}")
            pos = end
        else:
            # Unbalanced brace — emit macro text literally and continue
            result.append(text[m.start() : m.end()])
            pos = m.end()
    return "".join(result)


def expand_bracket_macros(text: str) -> str:
    r"""Expand \PB{}, \RB{}, \CB{} bracket macros to standard LaTeX.

    Uses stack-based brace matching with recursion to handle arbitrary
    nesting depth (e.g. ``\PB{\frac{\dot{m}_{a}}{\dot{m}_{b}}}``).
    """
    return _expand_all_bracket_macros(text)


def normalize_bold_prefix_colons(text: str) -> str:
    r"""Normalize ``\textbf{Note}:`` to ``\textbf{Note:}`` (move colon inside braces).

    Some EnergyPlus files place the colon *after* the closing brace.  The Lua
    filter expects the colon inside the bold group (``**Note:**`` not
    ``**Note**:``), so we normalise the variant.
    """
    # Match \textbf{<Label>}: where <Label> is a known admonition keyword
    return re.sub(
        r"\\textbf\{(Note|Caution|Warning|Important|Tip|Example|See Also|Limitation)\}:",
        r"\\textbf{\1:}",
        text,
    )


def promote_callout_prefixes(text: str) -> str:
    r"""Convert plain-text admonition prefixes inside callout bodies to bold form.

    Many callout environments start with plain ``Note:``, ``NOTE:``, or
    ``Caution:`` without ``\textbf{}``.  The Lua filter only detects bold
    prefixes (``**Note:**``), so these plain-text prefixes are promoted to
    ``\textbf{Note:}`` etc.  Must run *before* ``convert_callout_env()`` so
    that the callout delimiters are still present for matching.
    """

    def _promote(m: re.Match) -> str:
        body = m.group(1)
        # Match a leading admonition keyword followed by a colon (required to
        # avoid false positives like "Note that..." or "Note also that...")
        prefix_match = re.match(r"\s*(NOTE|Note|Caution|CAUTION):\s*", body)
        if prefix_match:
            keyword = prefix_match.group(1).capitalize()
            # Replace the plain prefix with \textbf{Keyword:}
            body = re.sub(
                r"^\s*(?:NOTE|Note|Caution|CAUTION):\s*",
                rf"\\textbf{{{keyword}:}} ",
                body,
                count=1,
            )
        return r"\begin{callout}" + body + r"\end{callout}"

    return re.sub(
        r"\\begin\{callout\}(.*?)\\end\{callout\}",
        _promote,
        text,
        flags=re.DOTALL,
    )


def wrap_standalone_bold_admonitions(text: str) -> str:
    r"""Wrap standalone ``\textbf{Note:}`` / ``\textbf{Example:}`` paragraphs in quote environments.

    EnergyPlus uses ``\textbf{Note:} text...`` as free-standing paragraphs
    (not inside callout environments).  Pandoc renders these as normal bold
    text in a paragraph — the Lua filter never sees them as BlockQuotes.
    This function wraps them in ``\begin{quote}...\end{quote}`` so the full
    admonition pipeline applies.

    Only matches paragraphs that begin with the bold prefix at the start of
    a line (preceded by a blank line or start of string) and continue until
    the next blank line.
    """
    return re.sub(
        r"(?:^|\n\n)"  # paragraph boundary
        r"(\\textbf\{(?:Note|Caution|Warning|Important|Tip|Example|See Also|Limitation):}[ ~]*"  # bold prefix
        r"(?:[^\n]|\n(?!\n))+)",  # rest of paragraph (lines until blank line)
        lambda m: "\n\n\\begin{quote}\n" + m.group(1) + "\n\\end{quote}",
        text,
    )


def convert_callout_env(text: str) -> str:
    r"""Convert \begin{callout}...\end{callout} to \begin{quote}...\end{quote}."""
    text = text.replace(r"\begin{callout}", r"\begin{quote}")
    text = text.replace(r"\end{callout}", r"\end{quote}")
    return text


# Admonition macros: LaTeX command name -> bold prefix label.
# Each macro \<name>{text} is converted to \begin{quote}\n\textbf{<Label>} text\n\end{quote}.
# The Lua filter then detects the bold prefix and emits the corresponding Zensical admonition type.
_ADMONITION_MACROS: dict[str, str] = {
    "warning": "Warning:",
    "caution": "Caution:",
    "important": "Important:",
    "tip": "Tip:",
    "note": "Note:",
    "example": "Example:",
    "seealso": "See Also:",
    "limitation": "Limitation:",
}


def convert_admonition_macros(text: str) -> str:
    r"""Convert admonition macros to quote environments with bold prefixes.

    Handles \warning{}, \caution{}, \important{}, \tip{}, \note{}, \example{},
    \seealso{}, and \limitation{} macros.  Each is converted to a
    ``\begin{quote}`` block with a ``\textbf{<Type>:}`` prefix that the Lua
    filter uses to select the appropriate Zensical admonition type.
    """
    for macro_name, label in _ADMONITION_MACROS.items():
        text = re.sub(
            rf"\\{macro_name}" + _BRACE_RE,
            rf"\\begin{{quote}}\n\\textbf{{{label}}} \1\n\\end{{quote}}",
            text,
        )
    return text


def strip_input_directives(text: str) -> str:
    r"""Strip \input{} directives.

    Content from child files is converted as separate pages; the parent page
    gets a generated table of contents linking to them (see ``convert.py``).
    """
    return re.sub(r"\\input\{[^}]*\}", "", text)


def convert_wherelist_env(text: str) -> str:
    r"""Convert \begin{wherelist}...\end{wherelist} to a definition-list-friendly format.

    The wherelist environment renders as "where:" followed by "symbol = description" items.
    We convert it to a Pandoc-friendly itemize with bold symbols.
    """

    def replace_wherelist(m: re.Match) -> str:
        body = m.group(1)
        # Each item is typically: \item[symbol] description
        items = re.findall(r"\\item\[([^\]]*)\]\s*(.*?)(?=\\item|\Z)", body, re.DOTALL)
        if not items:
            return body
        lines = ["*where:*\n"]
        for symbol, desc in items:
            desc = desc.strip()
            lines.append(f"- **{symbol}** = {desc}")
        return "\n".join(lines) + "\n"

    return re.sub(
        r"\\begin\{wherelist\}(.*?)\\end\{wherelist\}",
        replace_wherelist,
        text,
        flags=re.DOTALL,
    )


def strip_longtable_continuations(text: str) -> str:
    r"""Strip longtable continuation headers/footers used only for PDF pagination.

    Longtables define \endfirsthead (first-page header), \endhead (continuation
    header), \endfoot, and \endlastfoot blocks. Only the first-page header is
    needed for Markdown output; the rest cause duplicate rows in Pandoc's AST.
    """
    # Remove from \endfirsthead through \endhead (continuation header block)
    text = re.sub(r"\\endfirsthead.*?\\endhead", "", text, flags=re.DOTALL)
    # Remove from \endfoot through \endlastfoot (footer blocks)
    text = re.sub(r"\\endfoot.*?\\endlastfoot", "", text, flags=re.DOTALL)
    # Clean up any remaining standalone markers
    text = re.sub(r"\\endfirsthead\b", "", text)
    text = re.sub(r"\\endhead\b", "", text)
    text = re.sub(r"\\endfoot\b", "", text)
    text = re.sub(r"\\endlastfoot\b", "", text)
    return text


def strip_document_wrapper(text: str) -> str:
    r"""Strip \begin{document}...\end{document} and preamble for leaf files."""
    marker = r"\begin{document}"
    idx = text.find(marker)
    if idx != -1:
        text = text[idx + len(marker) :]
    text = text.replace(r"\end{document}", "")
    return text


def strip_tex_spacing_primitives(text: str) -> str:
    r"""Strip TeX math spacing primitives unsupported by MathJax.

    Commands like \medmuskip=0mu, \thinmuskip=0mu, \nulldelimiterspace=0pt
    are used in the LaTeX source to compress wide equations for PDF output.
    MathJax ignores or chokes on these, so we remove them.
    """
    text = re.sub(r"\\(?:med|thin|thick)muskip\s*=\s*\S+", "", text)
    text = re.sub(r"\\nulldelimiterspace\s*=\s*\S+", "", text)
    text = re.sub(r"\\scriptspace\s*=\s*\S+", "", text)
    return text


def clean_label_commands(text: str) -> str:
    r"""Preserve \label{} commands but mark them for the Lua filter to handle."""
    # Labels inside equations are handled later by the postprocessor
    # For section-level labels, keep them as-is for Pandoc
    return text


_MAX_ORPHAN_BRACES = 3


def _find_orphan_braces(text: str) -> tuple[list[int], list[int]]:
    """Scan *text* and return (unmatched_open_positions, unmatched_close_positions).

    Escaped braces (``\\{``, ``\\}``) and LaTeX comment lines are skipped.
    """
    open_stack: list[int] = []
    orphan_close: list[int] = []

    i = 0
    n = len(text)
    while i < n:
        ch = text[i]

        # Skip LaTeX comments (% to end of line)
        if ch == "%" and (i == 0 or text[i - 1] != "\\"):
            while i < n and text[i] != "\n":
                i += 1
            continue

        # Skip double-backslash (LaTeX linebreak \\) so that \\{ is not
        # misread as \{ (escaped brace).  The { after \\ is a real brace.
        if ch == "\\" and i + 1 < n and text[i + 1] == "\\":
            i += 2
            continue

        # Skip escaped braces: \{ and \}
        if ch == "\\" and i + 1 < n and text[i + 1] in "{}":
            i += 2
            continue

        if ch == "{":
            open_stack.append(i)
        elif ch == "}":
            if open_stack:
                open_stack.pop()
            else:
                orphan_close.append(i)

        i += 1

    return open_stack, orphan_close


def fix_unbalanced_braces(text: str, *, source_hint: str = "") -> str:
    r"""Remove orphan braces that would cause Pandoc parse errors.

    Some upstream EnergyPlus .tex files have brace typos (e.g. an extra ``{``
    before a parenthesised unit, or a stray ``}`` at line end).  Pandoc aborts
    on these with "unexpected end of input" or "unexpected Symbol }".

    As a safeguard the function only acts when the total number of orphan braces
    is at most ``_MAX_ORPHAN_BRACES``; larger imbalances likely indicate a bug
    in an earlier preprocessing step, and are left untouched (with a warning).
    """
    open_stack, orphan_close = _find_orphan_braces(text)

    if not open_stack and not orphan_close:
        return text

    total_orphans = len(open_stack) + len(orphan_close)
    hint = source_hint or "<unknown>"

    if total_orphans > _MAX_ORPHAN_BRACES:
        logger.warning(
            "Brace imbalance too large to auto-fix (%d orphans) in %s — skipping",
            total_orphans,
            hint,
        )
        return text

    for pos in open_stack:
        line_num = text[:pos].count("\n") + 1
        logger.debug("Removing orphan '{' at line %d in %s", line_num, hint)
    for pos in orphan_close:
        line_num = text[:pos].count("\n") + 1
        logger.debug("Removing orphan '}' at line %d in %s", line_num, hint)

    to_remove = set(open_stack) | set(orphan_close)
    return "".join(ch for i, ch in enumerate(text) if i not in to_remove)


def isolate_display_math_envs(text: str) -> str:
    r"""Insert blank lines around display math environments.

    Pandoc needs blank lines around ``\begin{equation}``, ``\begin{align}``,
    etc. to parse them as standalone blocks rather than inline content within
    a paragraph.  Without this, Pandoc may merge the equation into the
    preceding paragraph and emit inline ``$...$`` instead of display ``$$...$$``.
    """
    envs = r"equation|equation\*|align|align\*|gather|gather\*|multline|multline\*|eqnarray|eqnarray\*"
    # Ensure a blank line before \begin{env}
    text = re.sub(rf"(?<!\n\n)(\\begin{{({envs})}})", r"\n\n\1", text)
    # Ensure a blank line after \end{env}
    text = re.sub(rf"(\\end{{({envs})}})(?!\n\n)", r"\1\n\n", text)
    return text


def preprocess(text: str, *, source_hint: str = "") -> str:
    """Apply all preprocessing transformations in the correct order."""
    text = strip_document_wrapper(text)
    text = isolate_display_math_envs(text)
    text = strip_input_directives(text)
    text = strip_longtable_continuations(text)
    text = expand_si_macros(text)
    text = expand_bracket_macros(text)
    text = normalize_bold_prefix_colons(text)
    text = promote_callout_prefixes(text)
    text = wrap_standalone_bold_admonitions(text)
    text = convert_callout_env(text)
    text = convert_admonition_macros(text)
    text = convert_wherelist_env(text)
    text = strip_tex_spacing_primitives(text)
    text = clean_label_commands(text)
    text = fix_unbalanced_braces(text, source_hint=source_hint)
    return text
