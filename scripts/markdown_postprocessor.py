"""Post-Pandoc Markdown cleanup for EnergyPlus documentation.

Handles:
- Internal PDF link rewriting (inter-doc-set references)
- Ordered list detection (non-breaking space after number markers)
- Admonition formatting for Zensical (4-space indent)
- Image path rewriting relative to output file location
- Cross-reference resolution via label index
- Equation reference resolution (same-page eqref / cross-page tooltip links)
- YAML front matter generation
- Pandoc artifact cleanup
- Typographic dash conversion in headings
"""

from __future__ import annotations

import html
import posixpath
import re

from scripts.models import LabelRef

# Map PDF filenames used in \href{...} to their doc-set URL slugs.
# These are inter-doc-set cross-references left over from the original
# EnergyPlus LaTeX build where each doc set produced a separate PDF.
_PDF_TO_SLUG: dict[str, str] = {
    "InputOutputReference.pdf": "io-reference",
    "EngineeringReference.pdf": "engineering-reference",
    "EngineeringDoc.pdf": "engineering-reference",
    "GettingStarted.pdf": "getting-started",
    "OutputDetailsAndExamples.pdf": "output-details",
    "AuxiliaryPrograms.pdf": "auxiliary-programs",
    "InterfaceDeveloper.pdf": "interface-developer",
}


def rewrite_internal_pdf_links(text: str, rel_depth: int = 0) -> str:
    """Rewrite links to internal PDF doc sets as relative site paths.

    After Pandoc, ``\\href{InputOutputReference.pdf}{text}`` becomes
    ``[text](InputOutputReference.pdf)``.  We replace the PDF target with a
    relative path to the corresponding doc-set index page on the site.

    A page at depth *rel_depth* inside its doc set needs ``rel_depth + 1``
    parent traversals (``../``) to reach the site root before descending into
    the target doc set.
    """
    prefix = "../" * (rel_depth + 1)

    def rewrite(m: re.Match) -> str:
        link_text = m.group(1)
        path = m.group(2)
        # Extract the bare filename from potentially deep relative paths
        filename = path.rsplit("/", 1)[-1]
        slug = _PDF_TO_SLUG.get(filename)
        if slug:
            return f"[{link_text}]({prefix}{slug}/)"
        return m.group(0)

    return re.sub(r"\[([^\]]+)\]\(([^)]*\.pdf)\)", rewrite, text)


def fix_ordered_list_markers(text: str) -> str:
    r"""Replace non-breaking spaces after ordered-list markers with regular spaces.

    LaTeX ``~`` (non-breaking space) becomes U+00A0 in Pandoc's output.  When a
    manually numbered line like ``1.~Variable`` passes through Pandoc, the
    markdown output is ``1.\xa0Variable``.  Markdown parsers require a regular
    ASCII space after the ``1.`` marker to recognise an ordered list, so the
    non-breaking space must be replaced.
    """
    return re.sub(r"^(\d+\.)\xa0", r"\1 ", text, flags=re.MULTILINE)


def add_front_matter(text: str, title: str, doc_set_title: str = "") -> str:
    """Add YAML front matter with title and tags."""
    lines = ["---", f"title: {title}"]
    if doc_set_title:
        lines.append("tags:")
        lines.append(f"  - {doc_set_title}")
    lines.append("hide:")
    lines.append("  - tags")
    lines.append("---")
    return "\n".join(lines) + "\n\n" + text


def extract_title(text: str) -> str:
    """Extract the title from the first heading in the markdown."""
    m = re.search(r"^#\s+(.+)$", text, re.MULTILINE)
    if m:
        title = m.group(1).strip()
        # Strip Pandoc attributes like {#overview-022} and {.unnumbered}
        title = re.sub(r"\s*\{[#.][^}]*\}", "", title).strip()
        return title
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


def resolve_cross_references(text: str, label_index: dict[str, LabelRef], current_md_path: str = "") -> str:
    """Resolve #crossref:label links using the label index.

    For equation-type labels, same-page references become ``$\\eqref{label}$``
    so MathJax renders a clickable numbered reference.  Cross-page equation
    references become ``<a class="eq-ref" ...>`` with the equation LaTeX in a
    data attribute for tooltip rendering.

    Args:
        text: Markdown content with ``#crossref:label`` links.
        label_index: Map of label names to their output paths.
        current_md_path: The current page's markdown path relative to the docs
            root (e.g. ``engineering-reference/overview/basics.md``).  Used to
            compute correct relative links.
    """
    # Directory of the current page (relative to docs root)
    current_dir = posixpath.dirname(current_md_path) if current_md_path else ""

    def resolve(m: re.Match) -> str:
        link_text = m.group(1)
        label = m.group(2)
        if label in label_index:
            ref = label_index[label]

            # Equation-type labels get special handling
            if ref.label_type == "equation":
                if ref.output_path == current_md_path:
                    # Same-page: MathJax renders the clickable number
                    return f"$\\eqref{{{label}}}$"
                # Cross-page: tooltip link with pre-computed equation number
                target_url = _relative_url(ref.output_path, current_md_path)
                anchor = _label_to_mjx_anchor(label)
                escaped_latex = html.escape(ref.equation_latex) if ref.equation_latex else ""
                eq_text = str(ref.equation_number) if ref.equation_number else "#"
                return f'<a href="{target_url}#{anchor}" class="eq-ref" data-equation="{escaped_latex}">{eq_text}</a>'

            anchor = f"#{ref.heading_anchor}" if ref.heading_anchor else ""
            target_path = ref.output_path
            if current_dir:
                target_path = posixpath.relpath(target_path, current_dir)
            return f"[{link_text}]({target_path}{anchor})"
        # Unresolved reference - keep as-is with a note
        return f"[{link_text}](#{label})"

    return re.sub(r"\[([^\]]*)\]\(#crossref:([^)]+)\)", resolve, text)


def _label_to_mjx_anchor(label: str) -> str:
    """Convert a LaTeX label to MathJax's element ID format for use in hrefs.

    MathJax 3 creates element IDs as ``mjx-eqn-<label>`` (dash prefix) with
    literal special characters (e.g. colons).  For ``href`` attributes, colons
    in the label portion must be percent-encoded so the browser decodes them
    back to match the element ID.
    """
    encoded = label.replace(":", "%3A")
    return f"mjx-eqn-{encoded}"


def _relative_url(target_md_path: str, current_md_path: str) -> str:
    """Compute a relative URL between two ``.md`` paths for raw HTML ``<a>`` hrefs.

    Zensical uses directory-style URLs: ``foo/bar.md`` is served as
    ``foo/bar/``.  This means the browser resolves relative links from
    ``foo/bar/``, one level deeper than the file's directory.  Markdown
    links are rewritten by Zensical automatically, but raw ``<a>`` tags
    must account for the extra directory level.
    """

    def _to_url_dir(md_path: str) -> str:
        """Convert a ``.md`` path to its URL-level directory."""
        if md_path.endswith("/index.md"):
            return md_path[: -len("/index.md")]
        if md_path.endswith(".md"):
            return md_path[: -len(".md")]
        return md_path

    current_dir = _to_url_dir(current_md_path)
    target_dir = _to_url_dir(target_md_path)
    return posixpath.relpath(target_dir, current_dir) + "/"


def resolve_equation_references(
    text: str,
    label_index: dict[str, LabelRef],
    current_md_path: str = "",
) -> str:
    r"""Resolve ``<span class="eqref-placeholder">`` markers emitted by the Lua filter.

    Same-page references become ``$\eqref{label}$`` so MathJax renders a
    clickable numbered link.  Cross-page references become
    ``<a class="eq-ref" ...>Eq.</a>`` with the equation LaTeX in a data
    attribute for tooltip rendering.
    """
    current_dir = posixpath.dirname(current_md_path) if current_md_path else ""

    def resolve(m: re.Match) -> str:
        label = m.group(1)
        ref = label_index.get(label)

        if ref and ref.label_type == "equation":
            if ref.output_path == current_md_path:
                return f"$\\eqref{{{label}}}$"
            # Cross-page equation reference with tooltip
            target_url = _relative_url(ref.output_path, current_md_path)
            anchor = _label_to_mjx_anchor(label)
            escaped_latex = html.escape(ref.equation_latex) if ref.equation_latex else ""
            eq_num = str(ref.equation_number) if ref.equation_number else "?"
            return f'<a href="{target_url}#{anchor}" class="eq-ref" data-equation="{escaped_latex}">({eq_num})</a>'

        # Not in index or not an equation — fall back to a crossref link
        if ref:
            target_path = ref.output_path
            if current_dir:
                target_path = posixpath.relpath(target_path, current_dir)
            return f"[Eq.]({target_path})"

        # Unresolved — emit inline eqref and hope MathJax can resolve it
        return f"$\\eqref{{{label}}}$"

    return re.sub(r'<span class="eqref-placeholder" data-label="([^"]+)"></span>', resolve, text)


def fix_heading_dashes(text: str) -> str:
    """Convert double-dashes to en-dashes in headings.

    LaTeX renders ``--`` as an en-dash, but Pandoc outputs literal ``--``
    in Markdown headings.  This restores the intended typographic dash.
    """
    en_dash = "\u2013"

    def replace_dashes(m: re.Match) -> str:
        hashes = m.group(1)
        title = m.group(2)
        title = title.replace(" -- ", f" {en_dash} ")
        return f"{hashes} {title}"

    return re.sub(r"^(#{1,6})\s+(.+)$", replace_dashes, text, flags=re.MULTILINE)


def clean_pandoc_ref_attributes(text: str) -> str:
    r"""Clean Pandoc's ``\ref{}`` output artifacts.

    Pandoc converts ``\ref{label}`` to
    ``[\[label\]](#label){reference-type="ref" reference="label"}``.
    This function:
    1. Strips the ``{reference-type=... reference=...}`` attribute span.
    2. Unescapes the bracket notation in link text: ``\[label\]`` → ``label``.
    """
    # Strip {reference-type="..." reference="..."} attribute spans
    text = re.sub(r'\{reference-type="[^"]*"\s+reference="[^"]*"\}', "", text)
    # Clean escaped brackets in link text: [\[label\]] → [label]
    # Only inside markdown links to avoid false positives
    text = re.sub(r"\[\\\[([^\]]*?)\\\]\]", r"[\1]", text)
    return text


def clean_pandoc_artifacts(text: str) -> str:
    """Remove Pandoc artifacts from the converted markdown."""
    # Remove {.unnumbered} from headings
    text = re.sub(r"\s*\{\.unnumbered\}", "", text)
    # Remove {#sec:...} attributes that Pandoc adds
    text = re.sub(r"\s*\{#[^}]+\}", "", text)
    # Clean Pandoc \ref{} output (attribute spans and escaped brackets)
    text = clean_pandoc_ref_attributes(text)
    # Fix escaped underscores in non-math contexts
    # (be careful not to break underscores in math mode)
    # Only fix double-escaped underscores
    text = text.replace(r"\\_", "_")
    # Separate consecutive display-math blocks.  Pandoc writes consecutive
    # RawBlocks without blank lines, so "$$\n$$" (closing then opening)
    # causes arithmatex to merge them into one block.
    text = re.sub(r"^\$\$\n\$\$$", "$$\n\n$$", text, flags=re.MULTILINE)
    # Collapse more than 2 consecutive blank lines to 2
    text = re.sub(r"\n{4,}", "\n\n\n", text)
    # Remove trailing whitespace from lines
    text = re.sub(r"[ \t]+$", "", text, flags=re.MULTILINE)
    return text


def clean_empty_links(text: str) -> str:
    """Remove empty links and fix malformed link syntax."""
    # Remove [](empty) links but NOT ![](src) images (negative lookbehind for !)
    text = re.sub(r"(?<!!)\[\]\([^)]*\)", "", text)
    # Clean empty bracket artifacts in image alt text: ![caption []]( → ![caption](
    # Uses .*? to handle alt text that itself contains brackets (e.g. equation refs)
    text = re.sub(r"(!\[.*?)\s*\[\](\]\()", r"\1\2", text)
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
    doc_set_title: str = "",
    label_index: dict[str, LabelRef] | None = None,
    rel_depth: int = 0,
    current_md_path: str = "",
) -> str:
    """Apply all postprocessing transformations in the correct order."""
    if label_index is None:
        label_index = {}

    # Extract title from first heading if not provided
    if title is None:
        title = extract_title(text)

    text = rewrite_internal_pdf_links(text, rel_depth=rel_depth)
    text = fix_ordered_list_markers(text)
    text = fix_admonition_indent(text)
    text = rewrite_image_paths(text, doc_set_slug, rel_depth=rel_depth)
    text = resolve_equation_references(text, label_index, current_md_path=current_md_path)
    text = resolve_cross_references(text, label_index, current_md_path=current_md_path)
    text = clean_pandoc_artifacts(text)
    text = fix_heading_dashes(text)
    text = clean_empty_links(text)
    text = clean_div_wrappers(text)
    text = add_front_matter(text, title, doc_set_title=doc_set_title)

    return text
