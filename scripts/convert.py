"""Single-version EnergyPlus documentation converter.

Converts all LaTeX doc sets for one EnergyPlus version to Markdown,
generates the Zensical config, and optionally builds the site.

Usage:
    python -m scripts.convert --source /path/to/EnergyPlus --output build/v25.2 --version v25.2.0
"""

from __future__ import annotations

import argparse
import copy
import logging
import os
import re
import shutil
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import tomli_w

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib

from scripts.config import (
    DOC_SET_INFO,
    EXCLUDED_DIRS,
    IMAGE_EXTENSIONS,
    version_to_title,
)
from scripts.latex_preprocessor import preprocess
from scripts.markdown_postprocessor import postprocess
from scripts.models import ConversionResult, DocSet, DocSetResult, LabelRef, VersionResult
from scripts.nav_generator import extract_heading, generate_nav, parse_input_chain
from scripts.rst_doc_sets import (
    RstPage,
    append_child_toc,
    build_rst_pages,
    collect_rst_labels,
    discover_rst_doc_sets,
    format_rst_figures,
    normalize_heading_levels,
    parse_rst_sections,
    resolve_rst_roles,
    rst_to_markdown,
)
from scripts.schema_utils import DocObjectInfo, build_object_index, serialize_for_monaco

logger = logging.getLogger(__name__)

ROOT_CONFIG_PATH = Path(__file__).resolve().parent.parent / "zensical.toml"
FILTER_PATH = Path(__file__).parent / "pandoc_filters" / "energyplus.lua"
ASSETS_DIR = Path(__file__).parent / "assets"


def discover_doc_sets(source_dir: Path) -> list[DocSet]:
    """Scan the doc/ directory to find which doc sets exist for this version."""
    doc_dir = source_dir / "doc"
    if not doc_dir.exists():
        logger.error("No doc/ directory found at %s", source_dir)
        return []

    doc_sets = []
    for entry in sorted(doc_dir.iterdir()):
        if not entry.is_dir():
            continue
        if entry.name in EXCLUDED_DIRS:
            continue
        if entry.name.startswith("."):
            continue

        # Check for a main .tex file
        main_tex = entry / f"{entry.name}.tex"
        if not main_tex.exists():
            continue

        # Look up display info or generate defaults
        if entry.name in DOC_SET_INFO:
            title, slug = DOC_SET_INFO[entry.name]
        else:
            title = entry.name.replace("-", " ").title()
            slug = entry.name
            logger.info("Unknown doc set '%s', using default title '%s'", entry.name, title)

        doc_sets.append(
            DocSet(
                dir_name=entry.name,
                title=title,
                slug=slug,
                source_dir=entry,
                main_source=main_tex,
            )
        )

    # Documents upstream has moved out of the LaTeX tree still live in the
    # Sphinx tree as reStructuredText.  Add any that the LaTeX scan missed.
    found = {ds.dir_name for ds in doc_sets}
    for rst_set in discover_rst_doc_sets(source_dir, DOC_SET_INFO):
        if rst_set.dir_name not in found:
            doc_sets.append(rst_set)

    report_missing_doc_sets(doc_sets)

    # Order by source directory name, which is the order the LaTeX-only scan
    # produced, so restored doc sets slot into the existing nav rather than
    # reshuffling the tabs of versions that already build.
    return sorted(doc_sets, key=lambda ds: ds.dir_name)


def report_missing_doc_sets(doc_sets: list[DocSet]) -> list[str]:
    """Warn about doc sets that are configured but were not found in the source.

    Losing a configured document is what let Auxiliary Programs, the EMS
    Application Guide, Tips and Tricks and EnergyPlus Essentials disappear from
    the v25.1.0+ builds unnoticed: upstream moved them and the build simply
    produced fewer documents without saying so.  Surfacing the gap makes the
    next upstream reshuffle visible instead of silent.
    """
    found = {ds.dir_name for ds in doc_sets}
    missing = [name for name in DOC_SET_INFO if name not in found]
    for name in missing:
        title, _slug = DOC_SET_INFO[name]
        logger.warning(
            "Configured doc set '%s' (%s) was not found in the source tree - it will be missing from this build",
            name,
            title,
        )
    return missing


def _clean_equation_latex(latex: str) -> str:
    r"""Strip TeX spacing preamble that MathJax doesn't understand.

    Some EnergyPlus equations contain spacing overrides like
    ``\medmuskip=0mu \thinmuskip=0mu`` that render as red error text
    in MathJax tooltips.
    """
    # Remove \command=<value><unit> assignments (e.g. \medmuskip=0mu, \scriptspace=0pt)
    latex = re.sub(r"\\[a-zA-Z]+=\d+[a-z]+\s*", "", latex)
    return latex.strip()


def _collect_numbered_math(text: str) -> list[tuple[int, str, str]]:
    r"""Collect all display math environments from LaTeX source in document order.

    After the Lua filter, ALL display equations (including ``equation*`` and
    ``\[...\]``) are wrapped in ``\begin{equation}...\end{equation}``, so
    MathJax numbers them all.  Non-starred ``\begin{align}`` rows are also
    numbered.  Starred ``align*`` is preserved unnumbered.

    Returns a list of ``(position, kind, body)`` tuples sorted by position.
    """
    items: list[tuple[int, str, str]] = []

    for m in re.finditer(r"\\begin\{equation\*?\}(.*?)\\end\{equation\*?\}", text, re.DOTALL):
        items.append((m.start(), "equation", m.group(1)))

    for m in re.finditer(r"\\begin\{align\}(.*?)\\end\{align\}", text, re.DOTALL):
        items.append((m.start(), "align", m.group(1)))

    for m in re.finditer(r"\\\[(.*?)\\\]", text, re.DOTALL):
        items.append((m.start(), "equation", m.group(1)))

    items.sort(key=lambda x: x[0])
    return items


def _compute_equation_numbers(text: str) -> dict[str, tuple[str, int]]:
    r"""Compute per-page MathJax AMS equation numbers for labeled equations.

    Returns a dict mapping label → (equation_body, equation_number).
    """
    result: dict[str, tuple[str, int]] = {}
    counter = 0

    for _pos, kind, body in _collect_numbered_math(text):
        clean_body = _clean_equation_latex(re.sub(r"\s*\\label\{[^}]+\}", "", body).strip())

        if kind == "equation":
            counter += 1
            label_m = re.search(r"\\label\{([^}]+)\}", body)
            if label_m:
                result[label_m.group(1)] = (clean_body, counter)

        elif kind == "align":
            for row in re.split(r"\\\\", body):
                has_nonumber = r"\nonumber" in row or r"\notag" in row
                if not has_nonumber:
                    counter += 1
                label_m = re.search(r"\\label\{([^}]+)\}", row)
                if label_m and not has_nonumber:
                    result[label_m.group(1)] = (clean_body, counter)

    return result


def _count_page_figures(
    text: str,
    fig_counter: int,
) -> tuple[list[int], dict[str, int], int]:
    r"""Count ``\begin{figure}`` environments in a single .tex file.

    Returns ``(page_fignums, label_to_num, updated_counter)`` where
    *page_fignums* is the ordered list of doc-set-wide figure numbers for
    every figure in this file (labeled or not), *label_to_num* maps
    labeled figures to their number, and *updated_counter* is the running
    counter after processing this file.
    """
    page_fignums: list[int] = []
    label_to_num: dict[str, int] = {}

    for fig_m in re.finditer(r"\\begin\{figure\*?\}(.*?)\\end\{figure\*?\}", text, re.DOTALL):
        fig_counter += 1
        page_fignums.append(fig_counter)
        body = fig_m.group(1)
        label_m = re.search(r"\\label\{([^}]+)\}", body)
        if label_m:
            label_to_num[label_m.group(1)] = fig_counter

    return page_fignums, label_to_num, fig_counter


def _register_labels(
    text: str,
    md_path: str,
    eq_info: dict[str, tuple[str, int]],
    fig_label_to_num: dict[str, int],
    label_index: dict[str, LabelRef],
) -> None:
    r"""Register all ``\label{}`` directives found in *text* into *label_index*."""
    for m in re.finditer(r"\\label\{([^}]+)\}", text):
        label = m.group(1)
        if label in eq_info:
            eq_body, eq_num = eq_info[label]
            label_index[label] = LabelRef(
                label=label,
                output_path=md_path,
                heading_anchor=label,
                label_type="equation",
                equation_latex=eq_body,
                equation_number=eq_num,
            )
        elif label in fig_label_to_num:
            label_index[label] = LabelRef(
                label=label,
                output_path=md_path,
                heading_anchor=label,
                label_type="figure",
                figure_number=fig_label_to_num[label],
            )
        else:
            # Only set heading_anchor for labels whose anchors survive
            # in the final output.  Figure labels get explicit <a id="...">
            # anchors from the Lua filter's Figure handler.  Section labels
            # (sec:*) are absorbed into Pandoc heading attributes ({#sec:...})
            # which clean_pandoc_artifacts strips, so anchoring to them
            # would create dead fragment links.
            anchor = label if label.startswith("fig:") else ""
            label_index[label] = LabelRef(label=label, output_path=md_path, heading_anchor=anchor)


def build_label_index(source_dir: Path, doc_sets: list[DocSet]) -> tuple[dict[str, LabelRef], dict[str, list[int]]]:
    r"""Scan all .tex files for \label{} and map to output markdown paths.

    For labels inside equation/align environments, stores the equation body,
    sets ``label_type="equation"``, and pre-computes the MathJax AMS equation
    number so cross-page references can display the correct number.

    For labels inside figure environments, sets ``label_type="figure"`` and
    computes the doc-set-wide figure number.

    Returns:
        A tuple of ``(label_index, file_figure_numbers)`` where
        *file_figure_numbers* maps each markdown file path to an ordered
        list of doc-set-wide figure numbers for all figures in that file
        (both labeled and unlabeled).
    """
    label_index: dict[str, LabelRef] = {}
    file_figure_numbers: dict[str, list[int]] = {}
    total_figures = 0

    for ds in doc_sets:
        if ds.source_format != "latex":
            # reST doc sets carry their own cross-reference targets, resolved
            # during conversion; there are no \label{} directives to index.
            continue
        inputs = parse_input_chain(ds.main_source)
        fig_counter = 0
        fig_label_to_num: dict[str, int] = {}

        for inp in inputs:
            if inp == "src/title" or inp.endswith("/title"):
                continue

            tex_path = ds.source_dir / f"{inp}.tex"
            if not tex_path.exists():
                continue

            text = tex_path.read_text(errors="replace")
            md_rel = inp[4:] if inp.startswith("src/") else inp
            md_path = f"{ds.slug}/{md_rel}.md"

            # Count figures in this file and assign doc-set-wide numbers
            page_fignums, page_fig_labels, fig_counter = _count_page_figures(text, fig_counter)
            fig_label_to_num.update(page_fig_labels)
            if page_fignums:
                file_figure_numbers[md_path] = page_fignums

            # Compute equation numbers and register all labels
            eq_info = _compute_equation_numbers(text)
            _register_labels(text, md_path, eq_info, fig_label_to_num, label_index)

        total_figures += fig_counter

    logger.info("Built label index with %d entries (%d figures)", len(label_index), total_figures)
    return label_index, file_figure_numbers


def copy_media(doc_set: DocSet, output_dir: Path) -> None:
    """Copy media files from the doc set to the output directory."""
    media_src = doc_set.media_dir
    if not media_src.exists():
        return

    media_dst = output_dir / doc_set.slug / "media"
    media_dst.mkdir(parents=True, exist_ok=True)

    for f in media_src.iterdir():
        if f.suffix.lower() in IMAGE_EXTENSIONS:
            shutil.copy2(f, media_dst / f.name)


def convert_tex_file(
    tex_path: Path,
    output_path: Path,
    doc_set_slug: str,
    label_index: dict[str, LabelRef],
    rel_depth: int = 0,
    doc_set_title: str = "",
    current_md_path: str = "",
    figure_numbers: list[int] | None = None,
    object_index: dict[str, DocObjectInfo] | None = None,
) -> ConversionResult:
    """Convert a single .tex file to Markdown via preprocessing -> Pandoc -> postprocessing."""
    warnings: list[str] = []

    try:
        # Read source
        text = tex_path.read_text(errors="replace")

        # Preprocess
        text = preprocess(text, source_hint=str(tex_path))

        # Write to a temp file for Pandoc
        temp_tex = output_path.with_suffix(".tex.tmp")
        temp_tex.parent.mkdir(parents=True, exist_ok=True)
        temp_tex.write_text(text)

        # Run Pandoc
        pandoc_args = [
            "pandoc",
            str(temp_tex),
            "-f",
            "latex",
            "-t",
            "markdown",
            "--wrap=none",
            "--markdown-headings=atx",
        ]

        # Add Lua filter if it exists
        if FILTER_PATH.exists():
            pandoc_args.extend(["--lua-filter", str(FILTER_PATH)])

        result = subprocess.run(
            pandoc_args,
            capture_output=True,
            text=True,
            timeout=60,
        )

        # Clean up temp file
        temp_tex.unlink(missing_ok=True)

        if result.returncode != 0:
            stderr = result.stderr.strip()
            if stderr:
                warnings.append(f"Pandoc warnings: {stderr}")
            if result.returncode != 0 and not result.stdout:
                return ConversionResult(
                    source=tex_path,
                    output=output_path,
                    success=False,
                    error=f"Pandoc failed: {stderr}",
                    warnings=warnings,
                )

        md_text = result.stdout
        if result.stderr:
            warnings.append(result.stderr.strip())

        # Postprocess
        md_text = postprocess(
            md_text,
            doc_set_slug=doc_set_slug,
            doc_set_title=doc_set_title,
            label_index=label_index,
            rel_depth=rel_depth,
            current_md_path=current_md_path,
            figure_numbers=figure_numbers,
            object_index=object_index,
        )

        # Write output
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(md_text)

        return ConversionResult(
            source=tex_path,
            output=output_path,
            success=True,
            warnings=warnings,
        )

    except subprocess.TimeoutExpired:
        return ConversionResult(
            source=tex_path,
            output=output_path,
            success=False,
            error="Pandoc timed out after 60s",
            warnings=warnings,
        )
    except Exception as e:
        return ConversionResult(
            source=tex_path,
            output=output_path,
            success=False,
            error=str(e),
            warnings=warnings,
        )


def generate_doc_set_index(doc_set: DocSet, output_dir: Path, first_page: str) -> None:
    """Generate an index.md for a doc set section so browsing the section URL works."""
    index_path = output_dir / "docs" / doc_set.slug / "index.md"
    index_path.parent.mkdir(parents=True, exist_ok=True)
    index_path.write_text(
        f"---\ntitle: {doc_set.title}\ntags:\n  - {doc_set.title}\nhide:\n  - tags\n---\n\n# {doc_set.title}\n"
    )


def _append_child_toc(
    parent_md: Path,
    children: list[str],
    doc_set: DocSet,
) -> None:
    """Append a table-of-contents list to a parent page linking to its children.

    Parent pages that originally used ``\\input{}`` to include child files get
    their ``\\input`` directives stripped during preprocessing, leaving only the
    chapter heading.  This function adds a markdown list of links to those child
    pages so the parent page is not empty.
    """
    toc_lines = ["\n## Contents\n"]
    for child_inp in children:
        if child_inp.endswith("/title"):
            continue
        tex_path = doc_set.source_dir / f"{child_inp}.tex"
        title, _level = extract_heading(tex_path)
        # Parent is at  <slug>/<chapter>/index.md
        # Child  is at  <slug>/<chapter>/<section>.md
        # So relative link is just <section>.md (same directory)
        child_rel = child_inp[4:] if child_inp.startswith("src/") else child_inp
        child_filename = child_rel.split("/", 1)[1] if "/" in child_rel else child_rel
        toc_lines.append(f"- [{title}]({child_filename}.md)")

    if len(toc_lines) > 1:  # More than just the heading
        existing = parent_md.read_text()
        parent_md.write_text(existing.rstrip() + "\n" + "\n".join(toc_lines) + "\n")


def _build_parent_children_map(inputs: list[str]) -> dict[str, list[str]]:
    """Build a map of parent input paths to their child input paths."""
    parent_children: dict[str, list[str]] = {}
    for inp in inputs:
        parts = inp.replace("src/", "").split("/")
        if len(parts) >= 2:
            parent = f"src/{parts[0]}"
            parent_children.setdefault(parent, []).append(inp)
    return parent_children


def _output_path_for_input(inp: str, doc_set_slug: str, output_dir: Path, is_parent: bool) -> tuple[Path, int, str]:
    """Compute the output .md path, rel_depth, and md_path relative to docs root."""
    md_rel = inp[4:] if inp.startswith("src/") else inp
    if is_parent:
        # Parent pages become index.md inside their chapter folder
        # so navigation.indexes makes the section header clickable.
        md_path = f"{doc_set_slug}/{md_rel}/index.md"
        return output_dir / "docs" / doc_set_slug / md_rel / "index.md", md_rel.count("/") + 1, md_path
    md_path = f"{doc_set_slug}/{md_rel}.md"
    return output_dir / "docs" / doc_set_slug / f"{md_rel}.md", md_rel.count("/"), md_path


def _convert_files(
    tasks: list[tuple[str, Path, Path, int, str]],
    doc_set_slug: str,
    doc_set_title: str,
    label_index: dict[str, LabelRef],
    max_workers: int,
    file_figure_numbers: dict[str, list[int]] | None = None,
    object_index: dict[str, DocObjectInfo] | None = None,
) -> list[tuple[str, ConversionResult]]:
    """Run file conversions, using a thread pool when *max_workers* > 1."""
    if file_figure_numbers is None:
        file_figure_numbers = {}
    converted: list[tuple[str, ConversionResult]] = []
    if max_workers > 1 and len(tasks) > 1:
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_inp = {
                executor.submit(
                    convert_tex_file,
                    tex_path,
                    output_path,
                    doc_set_slug,
                    label_index,
                    rel_depth,
                    doc_set_title,
                    current_md_path,
                    file_figure_numbers.get(current_md_path),
                    object_index,
                ): inp
                for inp, tex_path, output_path, rel_depth, current_md_path in tasks
            }
            for future in as_completed(future_to_inp):
                inp = future_to_inp[future]
                converted.append((inp, future.result()))
    else:
        for inp, tex_path, output_path, rel_depth, current_md_path in tasks:
            converted.append((
                inp,
                convert_tex_file(
                    tex_path,
                    output_path,
                    doc_set_slug,
                    label_index,
                    rel_depth=rel_depth,
                    doc_set_title=doc_set_title,
                    current_md_path=current_md_path,
                    figure_numbers=file_figure_numbers.get(current_md_path),
                    object_index=object_index,
                ),
            ))
    return converted


def _collect_tasks(
    inputs: list[str],
    doc_set: DocSet,
    output_dir: Path,
    parent_children: dict[str, list[str]],
    result: DocSetResult,
) -> list[tuple[str, Path, Path, int, str]]:
    """Build the list of conversion tasks from the input chain, recording missing-file errors."""
    tasks: list[tuple[str, Path, Path, int, str]] = []
    for inp in inputs:
        if inp == "src/title" or inp.endswith("/title"):
            continue
        tex_path = doc_set.source_dir / f"{inp}.tex"
        if not tex_path.exists():
            result.file_results.append(
                ConversionResult(
                    source=tex_path, output=Path(), success=False, error=f"Source file not found: {tex_path}"
                )
            )
            continue
        output_path, rel_depth, current_md_path = _output_path_for_input(
            inp, doc_set.slug, output_dir, is_parent=inp in parent_children
        )
        tasks.append((inp, tex_path, output_path, rel_depth, current_md_path))
    return tasks


def convert_doc_set(
    doc_set: DocSet,
    output_dir: Path,
    label_index: dict[str, LabelRef],
    *,
    max_workers: int = 1,
    file_figure_numbers: dict[str, list[int]] | None = None,
    object_index: dict[str, DocObjectInfo] | None = None,
) -> DocSetResult:
    """Convert all files in a doc set.

    When *max_workers* > 1, file conversions are executed in parallel
    using a :class:`~concurrent.futures.ThreadPoolExecutor`.  The Pandoc
    subprocess calls are I/O-bound, so threads work well here.
    """
    if doc_set.source_format == "rst":
        return convert_rst_doc_set(doc_set, output_dir, max_workers=max_workers)

    result = DocSetResult(doc_set=doc_set)
    copy_media(doc_set, output_dir / "docs")

    inputs = parse_input_chain(doc_set.main_source)
    parent_children = _build_parent_children_map(inputs)
    tasks = _collect_tasks(inputs, doc_set, output_dir, parent_children, result)

    # Phase 1: Convert files (parallel when max_workers > 1)
    converted = _convert_files(
        tasks, doc_set.slug, doc_set.title, label_index, max_workers, file_figure_numbers, object_index
    )

    # Phase 2: Log results and append TOCs (must happen after files are written)
    for inp, file_result in converted:
        result.file_results.append(file_result)
        if not file_result.success:
            logger.warning("Failed to convert %s: %s", file_result.source, file_result.error)
        elif file_result.warnings:
            for w in file_result.warnings:
                logger.debug("Warning for %s: %s", file_result.source, w)
        if file_result.success and inp in parent_children:
            _append_child_toc(file_result.output, parent_children[inp], doc_set)

    # Generate section index page
    first_page = ""
    for inp in inputs:
        if inp == "src/title" or inp.endswith("/title"):
            continue
        md_rel = inp[4:] if inp.startswith("src/") else inp
        first_page = f"{md_rel}.md"
        break
    generate_doc_set_index(doc_set, output_dir, first_page)

    return result


def _rst_pages_for(doc_set: DocSet) -> tuple[list[RstPage], dict[str, str]]:
    """Split a reST doc set into pages and collect its cross-reference targets."""
    lines = doc_set.main_source.read_text(errors="replace").split("\n")
    sections = parse_rst_sections(lines)
    if not sections:
        logger.warning("No sections found in %s", doc_set.main_source)
        return [], {}
    return build_rst_pages(lines, sections), collect_rst_labels(lines)


def _convert_rst_page(
    page: RstPage,
    doc_set: DocSet,
    output_dir: Path,
    labels: dict[str, str],
) -> ConversionResult:
    """Convert one reST page to Markdown and write it into the build tree."""
    output_path = output_dir / "docs" / doc_set.slug / page.md_rel

    md_text, error = rst_to_markdown(page.rst_text)
    if error:
        return ConversionResult(source=doc_set.main_source, output=output_path, success=False, error=error)

    md_text = normalize_heading_levels(md_text)
    md_text = format_rst_figures(md_text)
    md_text = resolve_rst_roles(md_text, labels)
    md_text = append_child_toc(md_text, page)
    md_text = postprocess(
        md_text,
        title=page.title,
        doc_set_slug=doc_set.slug,
        doc_set_title=doc_set.title,
        rel_depth=page.rel_depth,
        current_md_path=f"{doc_set.slug}/{page.md_rel}",
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(md_text)
    return ConversionResult(source=doc_set.main_source, output=output_path, success=True)


def convert_rst_doc_set(
    doc_set: DocSet,
    output_dir: Path,
    *,
    max_workers: int = 1,
) -> DocSetResult:
    """Convert a monolithic reStructuredText doc set into per-chapter pages."""
    result = DocSetResult(doc_set=doc_set)
    copy_media(doc_set, output_dir / "docs")

    pages, labels = _rst_pages_for(doc_set)
    if not pages:
        return result

    if max_workers > 1 and len(pages) > 1:
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = [executor.submit(_convert_rst_page, page, doc_set, output_dir, labels) for page in pages]
            for future in as_completed(futures):
                result.file_results.append(future.result())
    else:
        for page in pages:
            result.file_results.append(_convert_rst_page(page, doc_set, output_dir, labels))

    for file_result in result.file_results:
        if not file_result.success:
            logger.warning("Failed to convert %s: %s", file_result.output, file_result.error)

    generate_doc_set_index(doc_set, output_dir, first_page=pages[0].md_rel)
    return result


def generate_rst_nav(doc_set: DocSet) -> list:
    """Build the Zensical nav structure for a reST doc set."""
    pages, _labels = _rst_pages_for(doc_set)

    nav: list = []
    by_chapter: dict[str, dict] = {}

    for page in pages:
        path = f"{doc_set.slug}/{page.md_rel}"
        if "/" not in page.md_rel:
            nav.append({page.title: path})
            continue
        chapter_slug = page.md_rel.split("/", 1)[0]
        if page.md_rel.endswith("/index.md"):
            entry = {page.title: [path]}
            by_chapter[chapter_slug] = entry
            nav.append(entry)
        else:
            entry = by_chapter.get(chapter_slug)
            if entry is None:
                nav.append({page.title: path})
            else:
                next(iter(entry.values())).append({page.title: path})

    return nav


def generate_index_page(version: str, doc_sets: list[DocSet], output_dir: Path) -> None:
    """Generate the index.md landing page for this version."""
    version_title = version_to_title(version)
    content = f"""---
title: EnergyPlus {version_title} Documentation
---

# EnergyPlus {version_title} Documentation

Welcome to the EnergyPlus {version_title} documentation.

## Documentation Sets

"""
    for ds in doc_sets:
        content += f"- [{ds.title}]({ds.slug}/)\n"

    index_path = output_dir / "docs" / "index.md"
    index_path.parent.mkdir(parents=True, exist_ok=True)
    index_path.write_text(content)


def generate_zensical_config(
    version: str,
    doc_sets: list[DocSet],
    output_dir: Path,
) -> None:
    """Generate the zensical.toml config for this version.

    Reads the root zensical.toml as a base, applies version-specific
    overrides (site_name, site_url, nav, versioning, MathJax), and
    writes the merged config with tomli_w.
    """
    version_title = version_to_title(version)

    # Load root config as base
    with ROOT_CONFIG_PATH.open("rb") as f:
        config = tomllib.load(f)
    config = copy.deepcopy(config)

    project = config.setdefault("project", {})

    # Version-specific overrides
    project["site_name"] = f"{project.get('site_name', 'EnergyPlus Documentation')} - {version_title}"
    project["site_url"] = "/"

    # Build navigation
    nav_tabs = []
    for ds in doc_sets:
        if ds.source_format == "rst":
            ds_nav = generate_rst_nav(ds)
        else:
            ds_nav = generate_nav(ds.source_dir, ds.slug, ds.dir_name)
        if ds_nav:
            nav_tabs.append((ds.title, ds.slug, ds_nav))

    nav_data = []
    for title, slug, items in nav_tabs:
        nav_data.append({title: [{title: f"{slug}/index.md"}, *items]})
    project["nav"] = nav_data

    # Version provider for mike
    extra = project.setdefault("extra", {})
    extra["version"] = {"provider": "mike", "default": "stable"}

    # Tags for cmd-k search filtering
    extra["tags"] = {ds.title: ds.slug for ds in doc_sets}

    # Markdown extensions — specify explicitly so we don't lose Zensical's
    # defaults (superfences, highlight, etc.) when adding our overrides.
    # Omitting this from zensical.toml would work for `make docs-test`, but
    # since we need toc_depth=4 and arithmatex, we must list everything.
    project["markdown_extensions"] = {
        "abbr": {},
        "admonition": {},
        "attr_list": {},
        "def_list": {},
        "footnotes": {},
        "md_in_html": {},
        "toc": {"permalink": True, "toc_depth": 4},
        "pymdownx.arithmatex": {"generic": True},
        "pymdownx.betterem": {},
        "pymdownx.caret": {},
        "pymdownx.details": {},
        "pymdownx.highlight": {
            "anchor_linenums": True,
            "line_spans": "__span",
            "pygments_lang_class": True,
        },
        "pymdownx.inlinehilite": {},
        "pymdownx.keys": {},
        "pymdownx.magiclink": {},
        "pymdownx.mark": {},
        "pymdownx.smartsymbols": {},
        "pymdownx.superfences": {
            "custom_fences": [{"name": "mermaid", "class": "mermaid"}],
        },
        "pymdownx.tabbed": {
            "alternate_style": True,
            "combine_header_slug": True,
        },
        "pymdownx.tasklist": {"custom_checkbox": True},
        "pymdownx.tilde": {},
    }

    # MathJax with equation numbering + equation tooltips + IDF editor
    project["extra_javascript"] = [
        {"path": "assets/mathjax-config.js"},
        {"path": "https://cdnjs.cloudflare.com/ajax/libs/mathjax/3.2.2/es5/tex-mml-chtml.js", "async": True},
        {"path": "assets/eq-tooltips.js"},
        {"path": "assets/idf-editor.js", "defer": True},
    ]
    project["extra_css"] = [
        "assets/eq-tooltips.css",
        "assets/figures.css",
        "assets/idf-fields.css",
        "assets/idf-editor.css",
        "assets/theme-overrides.css",
    ]

    config_path = output_dir / "zensical.toml"
    config_path.write_text(tomli_w.dumps(config))


def copy_assets(output_dir: Path) -> None:
    """Copy static JS/CSS assets into the build output's docs/assets/ directory."""
    if not ASSETS_DIR.exists():
        return
    dst = output_dir / "docs" / "assets"
    dst.mkdir(parents=True, exist_ok=True)
    for f in ASSETS_DIR.iterdir():
        if f.is_file():
            shutil.copy2(f, dst / f.name)


def build_site(output_dir: Path) -> tuple[bool, str]:
    """Build the Zensical site for this version."""
    try:
        result = subprocess.run(
            ["zensical", "build"],
            cwd=str(output_dir),
            capture_output=True,
            text=True,
            timeout=300,
        )
    except FileNotFoundError:
        return False, "zensical not found. Install with: uv add zensical"
    except subprocess.TimeoutExpired:
        return False, "Build timed out after 300s"
    else:
        if result.returncode != 0:
            return False, result.stderr.strip()
        return True, ""


def convert_version(
    source_dir: Path,
    output_dir: Path,
    version: str,
    *,
    skip_build: bool = False,
    max_workers: int = 1,
) -> VersionResult:
    """Convert all doc sets for a single EnergyPlus version.

    Args:
        source_dir: Path to the cloned EnergyPlus repo
        output_dir: Path to write the build output
        version: Version tag (e.g., "v25.2.0")
        skip_build: If True, skip the zensical build step
        max_workers: Maximum parallel file conversions (1 = sequential)

    Returns:
        VersionResult with conversion and build status
    """
    result = VersionResult(version=version)

    # Discover doc sets
    doc_sets = discover_doc_sets(source_dir)
    if not doc_sets:
        result.build_error = "No doc sets found"
        return result

    logger.info("Found %d doc sets for %s: %s", len(doc_sets), version, [ds.dir_name for ds in doc_sets])

    # Build label index across all doc sets
    label_index, file_figure_numbers = build_label_index(source_dir, doc_sets)

    # Load epJSON schema from idfkit for structured field metadata and hover docs
    object_index: dict[str, DocObjectInfo] | None = None
    try:
        object_index = build_object_index(version)
    except Exception:
        logger.warning(
            "Failed to load epJSON schema for %s, field metadata will not be available", version, exc_info=True
        )

    # Convert each doc set
    for ds in doc_sets:
        logger.info("Converting doc set: %s", ds.title)
        # Only pass object index for IO Reference doc set (contains IDF object field docs)
        ds_object_index = object_index if ds.slug == "io-reference" else None
        ds_result = convert_doc_set(
            ds,
            output_dir,
            label_index,
            max_workers=max_workers,
            file_figure_numbers=file_figure_numbers,
            object_index=ds_object_index,
        )
        result.doc_set_results.append(ds_result)
        logger.info(
            "  %s: %d/%d files converted",
            ds.title,
            ds_result.success_count,
            len(ds_result.file_results),
        )

    # Generate index page
    generate_index_page(version, doc_sets, output_dir)

    # Generate zensical config
    generate_zensical_config(version, doc_sets, output_dir)

    # Copy static assets (MathJax config, equation tooltips, editor bundle)
    copy_assets(output_dir)

    # Generate compact JSON schema for Monaco hover documentation
    if object_index:
        schema_output = output_dir / "docs" / "assets" / "idd-schema.json"
        serialize_for_monaco(object_index, version, schema_output)

    # Build site
    if not skip_build:
        logger.info("Building Zensical site for %s...", version)
        success, error = build_site(output_dir)
        result.build_success = success
        result.build_error = error
        if not success:
            logger.error("Build failed for %s: %s", version, error)
    else:
        result.build_success = True

    # Summary
    logger.info(
        "Version %s: %d/%d files converted, build %s",
        version,
        result.total_successes,
        result.total_files,
        "succeeded" if result.build_success else "FAILED",
    )

    return result


def main() -> None:
    """CLI entry point for single-version conversion."""
    parser = argparse.ArgumentParser(description="Convert EnergyPlus docs for a single version")
    parser.add_argument("--source", required=True, type=Path, help="Path to EnergyPlus source tree")
    parser.add_argument("--output", required=True, type=Path, help="Output build directory")
    parser.add_argument("--version", required=True, help="Version tag (e.g., v25.2.0)")
    parser.add_argument("--skip-build", action="store_true", help="Skip the zensical build step")
    parser.add_argument(
        "--max-workers",
        type=int,
        default=os.cpu_count() or 4,
        help="Maximum parallel file conversions (default: CPU count)",
    )
    parser.add_argument("--verbose", "-v", action="store_true", help="Enable verbose logging")

    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s: %(message)s",
    )

    result = convert_version(
        args.source, args.output, args.version, skip_build=args.skip_build, max_workers=args.max_workers
    )

    # Print summary
    print(f"\n{'=' * 60}")
    print(f"Conversion Summary: {args.version}")
    print(f"{'=' * 60}")
    for ds_result in result.doc_set_results:
        status = "OK" if ds_result.failure_count == 0 else "WARN"
        print(f"  [{status}] {ds_result.doc_set.title}: {ds_result.success_count}/{len(ds_result.file_results)} files")
        for fr in ds_result.file_results:
            if not fr.success:
                print(f"        FAIL: {fr.source.name}: {fr.error}")
    print(f"\nTotal: {result.total_successes}/{result.total_files} files converted")
    print(f"Build: {'SUCCESS' if result.build_success else 'FAILED'}")
    if result.build_error:
        print(f"Build error: {result.build_error}")

    sys.exit(0 if result.build_success else 1)


if __name__ == "__main__":
    main()
