"""Post-Pandoc Markdown cleanup for EnergyPlus documentation.

Handles:
- Admonition formatting for Zensical (4-space indent)
- Image path rewriting relative to output file location
- Cross-reference resolution via label index
- Equation label conversion to MathJax-compatible format
- YAML front matter generation
- Pandoc artifact cleanup
"""

from __future__ import annotations

import re

from scripts.models import LabelRef


def add_front_matter(text: str, title: str) -> str:
    """Add YAML front matter with title."""
    return f"---\ntitle: {title}\n---\n\n{text}"


def extract_title(text: str) -> str:
    """Extract the title from the first heading in the markdown."""
    m = re.search(r"^#\s+(.+)$", text, re.MULTILINE)
    if m:
        return m.group(1).strip()
    return "Untitled"


def fix_admonition_indent(text: str) -> str:
    """Ensure admonition body lines are indented with exactly 4 spaces."""
    lines = text.split("\n")
    result = []
    in_admonition = False

    for line in lines:
        if re.match(r"^!!!\s+\w+", line):
            in_admonition = True
            result.append(line)
            continue

        if in_admonition:
            if line.strip() == "":
                # Blank line could end the admonition or be inside it
                # Look ahead logic not needed - just preserve blank line
                result.append("")
                continue
            if line.startswith("    "):
                result.append(line)
                continue
            # Non-indented, non-blank line ends the admonition
            in_admonition = False

        result.append(line)

    return "\n".join(result)


def rewrite_image_paths(text: str, doc_set_slug: str, rel_depth: int = 0) -> str:
    """Rewrite image paths to be relative from the output file's location.

    Args:
        text: Markdown content
        doc_set_slug: URL slug for this doc set
        rel_depth: How many directory levels deep the file is within the doc set
                   (e.g., 0 for top-level, 1 for files in a subdirectory)
    """
    prefix = "../" * rel_depth if rel_depth > 0 else ""

    # Match markdown image syntax: ![alt text](path)
    # Use a pattern that handles nested brackets in alt text
    def rewrite(m: re.Match) -> str:
        alt = m.group(1)
        path = m.group(2)
        # Already absolute or URL - skip
        if path.startswith("http") or path.startswith("/"):
            return m.group(0)
        # Prepend relative path back to doc set root
        if prefix and not path.startswith(".."):
            path = prefix + path
        return f"![{alt}]({path})"

    return re.sub(r"!\[((?:[^\[\]]|\[(?:[^\[\]]|\[[^\]]*\])*\])*)\]\(([^)]+)\)", rewrite, text)


def resolve_cross_references(text: str, label_index: dict[str, LabelRef]) -> str:
    """Resolve #crossref:label links using the label index."""

    def resolve(m: re.Match) -> str:
        link_text = m.group(1)
        label = m.group(2)
        if label in label_index:
            ref = label_index[label]
            anchor = f"#{ref.heading_anchor}" if ref.heading_anchor else ""
            return f"[{link_text}]({ref.output_path}{anchor})"
        # Unresolved reference - keep as-is with a note
        return f"[{link_text}](#{label})"

    return re.sub(r"\[([^\]]*)\]\(#crossref:([^)]+)\)", resolve, text)


def clean_equation_labels(text: str) -> str:
    r"""Convert equation labels to MathJax \tag{} format."""

    # Pattern: equation with \label inside $$ blocks
    def add_tag(m: re.Match) -> str:
        eq_body = m.group(1)
        label_match = re.search(r'<a id="([^"]+)"></a>', eq_body)
        if label_match:
            label = label_match.group(1)
            # Remove the anchor from inside the equation
            eq_body = re.sub(r'<a id="[^"]+"></a>\s*', "", eq_body)
            # Add \tag at the end of the equation
            eq_body = eq_body.rstrip()
            if not eq_body.endswith(r"\tag"):
                eq_body += f" \\tag{{{label}}}"
        return f"$$\n{eq_body}\n$$"

    return re.sub(r"\$\$\n(.*?)\n\$\$", add_tag, text, flags=re.DOTALL)


def clean_pandoc_artifacts(text: str) -> str:
    """Remove Pandoc artifacts from the converted markdown."""
    # Remove {.unnumbered} from headings
    text = re.sub(r"\s*\{\.unnumbered\}", "", text)
    # Remove {#sec:...} attributes that Pandoc adds
    text = re.sub(r"\s*\{#[^}]+\}", "", text)
    # Fix escaped underscores in non-math contexts
    # (be careful not to break underscores in math mode)
    # Only fix double-escaped underscores
    text = text.replace(r"\\_", "_")
    # Collapse more than 2 consecutive blank lines to 2
    text = re.sub(r"\n{4,}", "\n\n\n", text)
    # Remove trailing whitespace from lines
    text = re.sub(r"[ \t]+$", "", text, flags=re.MULTILINE)
    return text


def clean_empty_links(text: str) -> str:
    """Remove empty links and fix malformed link syntax."""
    # Remove [](empty) links
    text = re.sub(r"\[\]\([^)]*\)", "", text)
    return text


def clean_div_wrappers(text: str) -> str:
    """Remove Pandoc ::: div wrappers that Zensical doesn't support."""
    lines = text.split("\n")
    result = []
    for line in lines:
        stripped = line.strip()
        # Match ::: fences (any number of colons >=3), optionally with
        # class names or attributes: :::, :::: center, ::: {#id .class}
        if re.match(r"^:{3,}(\s.*)?$", stripped):
            continue
        result.append(line)
    return "\n".join(result)


def postprocess(
    text: str,
    title: str | None = None,
    doc_set_slug: str = "",
    label_index: dict[str, LabelRef] | None = None,
    rel_depth: int = 0,
) -> str:
    """Apply all postprocessing transformations in the correct order."""
    if label_index is None:
        label_index = {}

    # Extract title from first heading if not provided
    if title is None:
        title = extract_title(text)

    text = fix_admonition_indent(text)
    text = rewrite_image_paths(text, doc_set_slug, rel_depth=rel_depth)
    text = resolve_cross_references(text, label_index)
    text = clean_equation_labels(text)
    text = clean_pandoc_artifacts(text)
    text = clean_empty_links(text)
    text = clean_div_wrappers(text)
    text = add_front_matter(text, title)

    return text
