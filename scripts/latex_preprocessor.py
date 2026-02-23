"""Pre-Pandoc LaTeX transformations for EnergyPlus documentation.

Handles custom macros and environments that Pandoc cannot process directly:
- siunitx \\SI{}, \\si{}, \\IP{}, \\ip{} macros and custom unit declarations
- Bracket macros: \\PB{}, \\RB{}, \\CB{}
- callout environment -> quote (Pandoc-friendly)
- \\warning{} -> bold warning markers
- Strip \\input{} directives (leaf files are converted independently)
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


def expand_bracket_macros(text: str) -> str:
    r"""Expand \PB{}, \RB{}, \CB{} bracket macros to standard LaTeX."""
    text = re.sub(r"\\PB" + _BRACE_RE, r"\\left( \1 \\right)", text)
    text = re.sub(r"\\RB" + _BRACE_RE, r"\\left[ \1 \\right]", text)
    text = re.sub(r"\\CB" + _BRACE_RE, r"\\left\\{ \1 \\right\\}", text)
    return text


def convert_callout_env(text: str) -> str:
    r"""Convert \begin{callout}...\end{callout} to \begin{quote}...\end{quote}."""
    text = text.replace(r"\begin{callout}", r"\begin{quote}")
    text = text.replace(r"\end{callout}", r"\end{quote}")
    return text


def convert_warning_macro(text: str) -> str:
    r"""Convert \warning{text} to a quote environment with bold warning prefix.

    The Lua filter detects the \textbf{Warning:} prefix inside the resulting
    blockquote and emits a ``!!! warning`` admonition instead of ``!!! note``.
    """
    return re.sub(
        r"\\warning" + _BRACE_RE,
        r"\\begin{quote}\n\\textbf{Warning:} \1\n\\end{quote}",
        text,
    )


def strip_input_directives(text: str) -> str:
    r"""Strip \input{} directives since leaf files are converted independently."""
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


def preprocess(text: str, *, source_hint: str = "") -> str:
    """Apply all preprocessing transformations in the correct order."""
    text = strip_document_wrapper(text)
    text = strip_input_directives(text)
    text = strip_longtable_continuations(text)
    text = expand_si_macros(text)
    text = expand_bracket_macros(text)
    text = convert_callout_env(text)
    text = convert_warning_macro(text)
    text = convert_wherelist_env(text)
    text = strip_tex_spacing_primitives(text)
    text = clean_label_commands(text)
    text = fix_unbalanced_braces(text, source_hint=source_hint)
    return text
