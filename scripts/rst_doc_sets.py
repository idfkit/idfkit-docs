r"""Discovery and conversion for reStructuredText documentation sets.

Historically every EnergyPlus document lived in the LaTeX tree as
``doc/<name>/<name>.tex`` plus a chain of ``\input{src/...}`` chapter files.
Upstream has been migrating documents out of that tree and into the Sphinx
tree at ``doc/readthedocs/sphinx/<name>/<name>.rst``, where each document is a
single monolithic ``.rst`` file instead of a directory of chapters.

``Tips and Tricks`` moved in v23.2.0; ``Auxiliary Programs``,
``EMS Application Guide`` and ``EnergyPlus Essentials`` moved in v25.1.0.  The
LaTeX-only discovery in :mod:`scripts.convert` silently skipped them, so those
documents vanished from the newer builds — and therefore from the search index
— even though they were still listed in ``DOC_SET_INFO``.

This module restores them by splitting each monolithic ``.rst`` into the same
page shape the LaTeX pipeline produces (a page per chapter, child pages per
section) and converting each page with Pandoc's reStructuredText reader.
"""

from __future__ import annotations

import logging
import re
import subprocess
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path

from scripts.config import DOC_SET_ALIASES
from scripts.models import DocSet

logger = logging.getLogger(__name__)

# Location of the Sphinx tree relative to the cloned repo's doc/ directory.
SPHINX_SUBDIR = "readthedocs/sphinx"

# Directories under the Sphinx tree that are not prose documentation sets.
SPHINX_EXCLUDED_DIRS: frozenset[str] = frozenset({
    "_static",
    ".templates",
    "media",
})

# Punctuation characters reStructuredText allows as section adornments.
_ADORNMENT_CHARS = frozenset("""!"#$%&'()*+,-./:;<=>?@[\\]^_`{|}~""")

# Pandoc writer format.  Two deliberate choices here:
#   * pipe tables only, which is what Zensical renders (the LaTeX pipeline
#     achieves the same thing through the Lua filter);
#   * no raw HTML, so that a reST ``.. figure::`` carrying a ``:width:`` option
#     comes out as a Markdown image with link attributes rather than an
#     ``<img>`` tag.  Raw tags would slip past the image-path rewriting in
#     :mod:`scripts.markdown_postprocessor` and break on every nested page.
PANDOC_MARKDOWN_FORMAT = "markdown-simple_tables-multiline_tables-grid_tables-raw_html+pipe_tables+link_attributes"


@dataclass
class RstSection:
    """A section parsed out of a reStructuredText document."""

    title: str
    level: int
    start: int  # index of the title line
    body_start: int  # index of the first line after the adornment
    end: int = 0  # exclusive index of the last line belonging to this section
    children: list[RstSection] = field(default_factory=list)


@dataclass
class RstPage:
    """One output Markdown page carved out of a monolithic ``.rst`` document."""

    title: str
    md_rel: str  # path within the doc set, e.g. "weather-converter-program/index.md"
    rst_text: str
    rel_depth: int
    child_titles: list[str] = field(default_factory=list)
    child_slugs: list[str] = field(default_factory=list)


def slugify(title: str) -> str:
    """Convert a section title into a URL-safe slug.

    Mirrors the shape of the upstream LaTeX file names (lowercase words joined
    by hyphens) so reST-sourced URLs look like the LaTeX-sourced ones.
    """
    normalized = unicodedata.normalize("NFKD", title)
    ascii_only = normalized.encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", ascii_only).strip("-").lower()
    return slug or "section"


def _is_adornment(line: str) -> bool:
    """True if *line* is a reStructuredText section adornment rule."""
    stripped = line.strip()
    if len(stripped) < 2:
        return False
    return len(set(stripped)) == 1 and stripped[0] in _ADORNMENT_CHARS


def _find_section_markers(lines: list[str]) -> list[tuple[int, int, str, tuple[bool, str]]]:
    """Locate every section title in *lines*.

    Returns ``(title_index, body_start_index, title, style)`` tuples, where
    *style* is ``(has_overline, adornment_char)``.  reStructuredText treats an
    overlined adornment as a distinct level from the same character used as a
    plain underline, which is how these documents separate the document title
    from its chapters.
    """
    markers: list[tuple[int, int, str, tuple[bool, str]]] = []
    i = 0
    n = len(lines)

    while i < n:
        line = lines[i]

        # Overline form: rule / title / rule, all starting at column 0.
        if _is_adornment(line) and not line.startswith(" ") and i + 2 < n:
            title = lines[i + 1]
            under = lines[i + 2]
            char = line.strip()[0]
            if (
                title.strip()
                and not title.startswith(" ")
                and _is_adornment(under)
                and under.strip()[0] == char
                and len(line.strip()) >= len(title.rstrip())
            ):
                markers.append((i + 1, i + 3, title.strip(), (True, char)))
                i += 3
                continue

        # Underline form: title / rule.  Require the title to be preceded by a
        # blank line so that a transition rule (``----`` on its own) is not
        # mistaken for the underline of whatever text came before it.
        if (
            line.strip()
            and not line.startswith(" ")
            and not line.lstrip().startswith("..")
            and i + 1 < n
            and _is_adornment(lines[i + 1])
            and not lines[i + 1].startswith(" ")
            and len(lines[i + 1].strip()) >= len(line.rstrip())
            and (i == 0 or not lines[i - 1].strip())
        ):
            markers.append((i, i + 2, line.strip(), (False, lines[i + 1].strip()[0])))
            i += 2
            continue

        i += 1

    return markers


def parse_rst_sections(lines: list[str]) -> list[RstSection]:
    """Parse *lines* into a tree of :class:`RstSection` objects.

    Section levels follow the reStructuredText rule that adornment styles are
    ranked by first appearance rather than by any fixed character order.
    """
    markers = _find_section_markers(lines)
    if not markers:
        return []

    style_order: list[tuple[bool, str]] = []
    for _, _, _, style in markers:
        if style not in style_order:
            style_order.append(style)
    level_of = {style: idx + 1 for idx, style in enumerate(style_order)}

    roots: list[RstSection] = []
    stack: list[RstSection] = []

    for title_idx, body_idx, title, style in markers:
        section = RstSection(title=title, level=level_of[style], start=title_idx, body_start=body_idx)

        while stack and stack[-1].level >= section.level:
            stack.pop().end = title_idx
        if stack:
            stack[-1].children.append(section)
        else:
            roots.append(section)
        stack.append(section)

    while stack:
        stack.pop().end = len(lines)

    return roots


def _strip_sphinx_directives(text: str) -> str:
    """Remove Sphinx-only directives that Pandoc cannot render usefully.

    ``.. contents::`` duplicates the theme's table of contents, and
    ``.. raw:: html`` carries Sphinx-theme scaffolding (a floating "back to
    top" button) that has no place in the generated site.
    """
    lines = text.split("\n")
    result: list[str] = []
    skipping = False

    for line in lines:
        if skipping:
            # A directive block ends at the first non-blank, non-indented line.
            if not line.strip() or line.startswith((" ", "\t")):
                continue
            skipping = False
        if re.match(r"^\.\.\s+(contents|raw|toctree|highlight|sectionauthor)::", line):
            skipping = True
            continue
        result.append(line)

    return "\n".join(result)


def collect_rst_labels(lines: list[str]) -> dict[str, str]:
    r"""Map ``.. _label:`` targets to the text of whatever they introduce.

    Cross-references in these documents are written as ``:numref:`` and
    ``:ref:`` roles pointing at explicit targets.  Pandoc leaves the raw target
    name behind, so we keep the human-readable text (a table caption or a
    section title) to substitute in its place.
    """
    labels: dict[str, str] = {}

    for idx, line in enumerate(lines):
        m = re.match(r"^\.\.\s+_([^:]+):\s*$", line.strip())
        if not m:
            continue
        target = m.group(1).strip()

        # Look ahead for the caption or title the target introduces.
        for look in range(idx + 1, min(idx + 6, len(lines))):
            candidate = lines[look].strip()
            if not candidate:
                continue
            table_m = re.match(r"^\.\.\s+(table|figure|_?list-table)::\s*(.*)$", candidate)
            if table_m:
                caption = table_m.group(2).strip()
                if caption:
                    labels[target] = caption
                break
            if candidate.startswith(".."):
                break
            if look + 1 < len(lines) and _is_adornment(lines[look + 1]):
                labels[target] = candidate
            break

    return labels


def resolve_rst_roles(text: str, labels: dict[str, str]) -> str:
    """Replace Pandoc's leftover interpreted-text roles with readable text.

    Pandoc renders an unknown role as ``` `target`{.interpreted-text
    role="numref"} ```.  Substitute the caption or title the target names, so
    the prose reads as a reference instead of an internal identifier.
    """

    def replace(m: re.Match) -> str:
        target = m.group(1).strip()
        role = m.group(2)

        # ``:ref:`text <target>``` keeps its display text in the target slot.
        explicit = re.match(r"^(.*?)\s*<([^>]+)>$", target)
        if explicit:
            display = explicit.group(1).strip()
            if display:
                return display
            target = explicit.group(2).strip()

        if target in labels:
            return labels[target]
        if role in {"numref", "ref", "doc"}:
            # Fall back to a de-slugified form of the target name.
            cleaned = re.sub(r"^(table|figure|fig|sec)[_-]", "", target)
            return cleaned.replace("_", " ").replace("-", " ").strip()
        return target

    return re.sub(
        r"`([^`]+)`\{\.interpreted-text\s+role=\"([a-z]+)\"\}",
        replace,
        text,
    )


def _dedupe_slug(slug: str, used: set[str]) -> str:
    """Return *slug*, suffixed with a counter if it is already taken."""
    if slug not in used:
        used.add(slug)
        return slug
    counter = 2
    while f"{slug}-{counter}" in used:
        counter += 1
    unique = f"{slug}-{counter}"
    used.add(unique)
    return unique


def build_rst_pages(lines: list[str], sections: list[RstSection]) -> list[RstPage]:
    """Split a parsed reST document into the pages the site should publish.

    A document whose sections all hang off a single root (the document title)
    is unwrapped first, so that chapters — not the title — become top-level
    pages.  Chapters with subsections become ``<chapter>/index.md`` with their
    subsections alongside, matching the LaTeX pipeline's layout and letting
    Zensical's ``navigation.indexes`` make the chapter clickable.
    """
    while len(sections) == 1 and sections[0].children:
        sections = sections[0].children

    pages: list[RstPage] = []
    used_chapter_slugs: set[str] = set()

    for chapter in sections:
        chapter_slug = _dedupe_slug(slugify(chapter.title), used_chapter_slugs)

        if not chapter.children:
            pages.append(
                RstPage(
                    title=chapter.title,
                    md_rel=f"{chapter_slug}.md",
                    rst_text="\n".join(lines[chapter.start : chapter.end]),
                    rel_depth=0,
                )
            )
            continue

        # Chapter lead-in: everything between the chapter title and its first
        # subsection.  Keep the title so the page has a heading of its own.
        lead_end = chapter.children[0].start
        lead_lines = lines[chapter.start : lead_end]

        used_child_slugs: set[str] = set()
        child_titles: list[str] = []
        child_slugs: list[str] = []
        child_pages: list[RstPage] = []

        for child in chapter.children:
            child_slug = _dedupe_slug(slugify(child.title), used_child_slugs)
            child_titles.append(child.title)
            child_slugs.append(child_slug)
            child_pages.append(
                RstPage(
                    title=child.title,
                    md_rel=f"{chapter_slug}/{child_slug}.md",
                    rst_text="\n".join(lines[child.start : child.end]),
                    rel_depth=1,
                )
            )

        pages.append(
            RstPage(
                title=chapter.title,
                md_rel=f"{chapter_slug}/index.md",
                rst_text="\n".join(lead_lines),
                rel_depth=1,
                child_titles=child_titles,
                child_slugs=child_slugs,
            )
        )
        pages.extend(child_pages)

    return pages


def rst_to_markdown(rst_text: str, timeout: int = 120) -> tuple[str, str]:
    """Convert a reStructuredText fragment to Markdown via Pandoc.

    Returns ``(markdown, error)``; *error* is empty on success.
    """
    try:
        result = subprocess.run(
            [
                "pandoc",
                "-f",
                "rst",
                "-t",
                PANDOC_MARKDOWN_FORMAT,
                "--wrap=none",
                "--markdown-headings=atx",
            ],
            input=_strip_sphinx_directives(rst_text),
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return "", f"Pandoc timed out after {timeout}s"
    except FileNotFoundError:
        return "", "pandoc not found on PATH"

    if result.returncode != 0 and not result.stdout:
        return "", f"Pandoc failed: {result.stderr.strip()}"

    return result.stdout, ""


def format_rst_figures(text: str) -> str:
    """Turn Pandoc's figure/caption divs into captioned Markdown images.

    Pandoc renders a reST ``.. figure::`` as an image followed by a
    ``::: caption`` div.  Fold the caption into the image's alt text and leave
    an italic caption line beneath it, matching what the LaTeX pipeline's Lua
    filter produces for ``\begin{figure}``.
    """

    def replace(m: re.Match) -> str:
        image = m.group(1)
        caption = " ".join(m.group(2).split())
        if not caption:
            return image
        # Fill in empty alt text so the image is described without the caption.
        alt = caption.replace("[", "").replace("]", "")
        captioned = re.sub(r"^!\[\]\(", f"![{alt}](", image)
        return f"{captioned}\n\n*{caption}*"

    return re.sub(
        r"(!\[[^\]]*\]\([^)]+\)(?:\{[^}]*\})?)\n\n:{3,} caption\n"
        r"([^\n]*(?:\n(?!:{3,})[^\n]*)*)\n"
        r":{3,}",
        replace,
        text,
    )


def normalize_heading_levels(text: str) -> str:
    """Shift Markdown headings so the page's own top heading is ``#``.

    Pandoc ranks reST adornment styles by first appearance within whatever it
    is given, so a fragment usually already starts at ``#``.  This guards the
    case where a chapter's lead-in contains only deeper styles.
    """
    levels = [len(m.group(1)) for m in re.finditer(r"^(#{1,6})\s+\S", text, re.MULTILINE)]
    if not levels:
        return text

    shift = min(levels) - 1
    if shift <= 0:
        return text

    def restage(m: re.Match) -> str:
        return "#" * max(1, len(m.group(1)) - shift) + m.group(2)

    return re.sub(r"^(#{1,6})(\s+\S)", restage, text, flags=re.MULTILINE)


def append_child_toc(text: str, page: RstPage) -> str:
    """Append links to a chapter page's subsection pages.

    Chapter index pages hold only the lead-in prose, so without this they give
    the reader no way onward to the sections beneath them.
    """
    if not page.child_titles:
        return text

    lines = ["", "## Contents", ""]
    lines.extend(f"- [{title}]({slug}.md)" for title, slug in zip(page.child_titles, page.child_slugs, strict=True))
    return text.rstrip() + "\n" + "\n".join(lines) + "\n"


def discover_rst_doc_sets(source_dir: Path, doc_set_info: dict[str, tuple[str, str]]) -> list[DocSet]:
    """Find documentation sets that live in the Sphinx tree as ``.rst``.

    Only directories named in *doc_set_info* are returned; the Sphinx tree also
    holds API reference pages that this site does not publish.  Upstream renamed
    some directories on the way over, so ``DOC_SET_ALIASES`` and
    punctuation-insensitive matching both feed the lookup.
    """
    sphinx_dir = source_dir / "doc" / SPHINX_SUBDIR
    if not sphinx_dir.is_dir():
        return []

    # Index the configured names by a punctuation-insensitive key so a rename
    # between hyphens and underscores does not lose the document.
    by_key: dict[str, str] = {}
    for dir_name in doc_set_info:
        by_key.setdefault(re.sub(r"[^a-z0-9]+", "", dir_name.lower()), dir_name)
    for alias, dir_name in DOC_SET_ALIASES.items():
        if dir_name in doc_set_info:
            by_key[re.sub(r"[^a-z0-9]+", "", alias.lower())] = dir_name

    doc_sets: list[DocSet] = []
    for entry in sorted(sphinx_dir.iterdir()):
        if not entry.is_dir() or entry.name in SPHINX_EXCLUDED_DIRS or entry.name.startswith("."):
            continue

        main_rst = entry / f"{entry.name}.rst"
        if not main_rst.exists():
            continue

        configured = by_key.get(re.sub(r"[^a-z0-9]+", "", entry.name.lower()))
        if configured is None:
            logger.debug("Sphinx directory '%s' is not a configured doc set, skipping", entry.name)
            continue

        title, slug = doc_set_info[configured]
        doc_sets.append(
            DocSet(
                dir_name=configured,
                title=title,
                slug=slug,
                source_dir=entry,
                main_source=main_rst,
                source_format="rst",
            )
        )

    return doc_sets
