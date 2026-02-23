r"""Parse LaTeX \input chains to build navigation structure for Zensical config.

Reads the main .tex file of each doc set, follows the \input{src/...} chain,
and extracts chapter/section titles from the leaf .tex files to build a
hierarchical nav structure.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path

from scripts.models import NavItem

logger = logging.getLogger(__name__)


def parse_input_chain(main_tex: Path, *, _root: Path | None = None) -> list[str]:
    r"""Parse \input{src/...} entries from a .tex file, recursively.

    Returns a flat list of relative paths in document order, e.g.
    ``["src/overview", "src/overview/what-is-energyplus", ...]``.

    Chapter-level files that themselves contain ``\input`` directives are
    included *before* their children so the nav builder sees the chapter
    entry first.
    """
    if not main_tex.exists():
        return []

    # On the initial call the root is the doc-set directory (parent of the
    # main .tex file).  Recursive calls reuse the same root so that
    # \input{src/...} paths always resolve relative to the doc-set root.
    root = _root if _root is not None else main_tex.parent
    text = main_tex.read_text(errors="replace")
    inputs: list[str] = []

    for m in re.finditer(r"\\input\{(src/[^}]+)\}", text):
        rel = m.group(1)
        inputs.append(rel)

        # Recurse into the referenced file if it also contains \input entries
        child_tex = root / f"{rel}.tex"
        if child_tex.exists():
            child_text = child_tex.read_text(errors="replace")
            if r"\input{src/" in child_text:
                children = parse_input_chain(child_tex, _root=root)
                inputs.extend(children)

    return inputs


def extract_heading(tex_path: Path) -> tuple[str, int]:
    r"""Extract the first heading from a .tex file.

    Returns (title, level) where level is:
    - 0 for \chapter
    - 1 for \section
    - 2 for \subsection
    - 3 for \subsubsection
    """
    if not tex_path.exists():
        return (tex_path.stem.replace("-", " ").title(), 1)

    text = tex_path.read_text(errors="replace")

    heading_patterns = [
        (r"\\chapter\*?\{([^}]+)\}", 0),
        (r"\\section\*?\{([^}]+)\}", 1),
        (r"\\subsection\*?\{([^}]+)\}", 2),
        (r"\\subsubsection\*?\{([^}]+)\}", 3),
    ]

    for pattern, level in heading_patterns:
        m = re.search(pattern, text, re.DOTALL)
        if m:
            title = m.group(1).strip()
            # Clean LaTeX from title
            title = re.sub(r"\\[a-zA-Z]+\{([^}]*)\}", r"\1", title)
            title = re.sub(r"[\\{}]", "", title)
            # Normalize whitespace (multi-line headings with \\ linebreaks)
            title = re.sub(r"\s+", " ", title).strip()
            return (title, level)

    # Fallback: use filename
    return (tex_path.stem.replace("-", " ").title(), 1)


def input_path_to_md_path(input_rel: str) -> str:
    """Convert an input relative path to a markdown file path.

    E.g., "src/energyplus-overview/what-is-energyplus" -> "energyplus-overview/what-is-energyplus.md"
    """
    # Strip "src/" prefix
    path = input_rel
    if path.startswith("src/"):
        path = path[4:]
    return f"{path}.md"


def build_nav_tree(inputs: list[str], doc_set_dir: Path, doc_set_slug: str) -> list[NavItem]:
    """Build a navigation tree from the input chain.

    Groups leaf files under their parent chapter entries.
    """
    nav_items: list[NavItem] = []
    current_chapter: NavItem | None = None

    for inp in inputs:
        # Skip title input
        if inp == "src/title" or inp.endswith("/title"):
            continue

        tex_path = doc_set_dir / f"{inp}.tex"
        md_path = input_path_to_md_path(inp)
        title, _level = extract_heading(tex_path)

        parts = inp.replace("src/", "").split("/")

        if len(parts) == 1:
            # Chapter-level entry
            item = NavItem(title=title, path=f"{doc_set_slug}/{md_path}")
            current_chapter = item
            nav_items.append(item)
        elif len(parts) >= 2:
            # Section-level entry (child of a chapter)
            item = NavItem(title=title, path=f"{doc_set_slug}/{md_path}")
            if current_chapter is not None:
                current_chapter.children.append(item)
            else:
                # Orphan section - add at top level
                nav_items.append(item)

    return nav_items


def nav_to_zensical_format(nav_items: list[NavItem]) -> list:
    """Convert NavItem tree to the nested dict/list format for zensical.toml nav."""
    result = []
    for item in nav_items:
        if item.children:
            children = [{child.title: child.path} for child in item.children]
            result.append({item.title: [{item.title: item.path}, *children]})
        else:
            result.append({item.title: item.path})
    return result


def generate_nav(
    doc_set_dir: Path,
    doc_set_slug: str,
    main_tex_name: str,
) -> list:
    """Generate the full nav structure for a doc set.

    Args:
        doc_set_dir: Path to the doc set directory in the cloned repo
        doc_set_slug: URL slug for this doc set
        main_tex_name: Name of the main .tex file (without extension)

    Returns:
        Nav structure in zensical.toml format
    """
    main_tex = doc_set_dir / f"{main_tex_name}.tex"
    inputs = parse_input_chain(main_tex)

    if not inputs:
        logger.warning("No \\input entries found in %s", main_tex)
        return []

    nav_items = build_nav_tree(inputs, doc_set_dir, doc_set_slug)
    return nav_to_zensical_format(nav_items)
