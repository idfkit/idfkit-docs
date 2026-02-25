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
import re
import shutil
import subprocess
import sys
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

logger = logging.getLogger(__name__)

ROOT_CONFIG_PATH = Path(__file__).resolve().parent.parent / "zensical.toml"
FILTER_PATH = Path(__file__).parent / "pandoc_filters" / "energyplus.lua"


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
                main_tex=main_tex,
            )
        )

    return doc_sets


def build_label_index(source_dir: Path, doc_sets: list[DocSet]) -> dict[str, LabelRef]:
    r"""Scan all .tex files for \label{} and map to output markdown paths."""
    label_index: dict[str, LabelRef] = {}

    for ds in doc_sets:
        inputs = parse_input_chain(ds.main_tex)
        for inp in inputs:
            if inp == "src/title" or inp.endswith("/title"):
                continue

            tex_path = ds.source_dir / f"{inp}.tex"
            if not tex_path.exists():
                continue

            text = tex_path.read_text(errors="replace")
            # Strip "src/" prefix for the md path
            md_rel = inp[4:] if inp.startswith("src/") else inp
            md_path = f"{ds.slug}/{md_rel}.md"

            for m in re.finditer(r"\\label\{([^}]+)\}", text):
                label = m.group(1)
                label_index[label] = LabelRef(label=label, output_path=md_path)

    logger.info("Built label index with %d entries", len(label_index))
    return label_index


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
    index_path.write_text(f"---\ntitle: {doc_set.title}\ntags:\n  - {doc_set.title}\n---\n\n# {doc_set.title}\n")


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


def _output_path_for_input(inp: str, doc_set_slug: str, output_dir: Path, is_parent: bool) -> tuple[Path, int]:
    """Compute the output .md path and rel_depth for an input entry."""
    md_rel = inp[4:] if inp.startswith("src/") else inp
    if is_parent:
        # Parent pages become index.md inside their chapter folder
        # so navigation.indexes makes the section header clickable.
        return output_dir / "docs" / doc_set_slug / md_rel / "index.md", md_rel.count("/") + 1
    return output_dir / "docs" / doc_set_slug / f"{md_rel}.md", md_rel.count("/")


def convert_doc_set(
    doc_set: DocSet,
    output_dir: Path,
    label_index: dict[str, LabelRef],
) -> DocSetResult:
    """Convert all files in a doc set."""
    result = DocSetResult(doc_set=doc_set)

    # Copy media files
    copy_media(doc_set, output_dir / "docs")

    # Parse input chain recursively to discover all files
    inputs = parse_input_chain(doc_set.main_tex)

    # Build map of parent -> children for TOC generation
    parent_children = _build_parent_children_map(inputs)

    for inp in inputs:
        # Skip title
        if inp == "src/title" or inp.endswith("/title"):
            continue

        tex_path = doc_set.source_dir / f"{inp}.tex"
        if not tex_path.exists():
            result.file_results.append(
                ConversionResult(
                    source=tex_path,
                    output=Path(),
                    success=False,
                    error=f"Source file not found: {tex_path}",
                )
            )
            continue

        # Compute output path and depth within doc set
        output_path, rel_depth = _output_path_for_input(inp, doc_set.slug, output_dir, is_parent=inp in parent_children)

        file_result = convert_tex_file(
            tex_path, output_path, doc_set.slug, label_index, rel_depth=rel_depth, doc_set_title=doc_set.title
        )
        result.file_results.append(file_result)

        if not file_result.success:
            logger.warning("Failed to convert %s: %s", tex_path, file_result.error)
        elif file_result.warnings:
            for w in file_result.warnings:
                logger.debug("Warning for %s: %s", tex_path, w)

        # For parent pages, append a table of contents linking to children
        if file_result.success and inp in parent_children:
            _append_child_toc(output_path, parent_children[inp], doc_set)

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

    # MathJax
    project["extra_javascript"] = [
        {"path": "https://cdnjs.cloudflare.com/ajax/libs/mathjax/3.2.2/es5/tex-mml-chtml.js", "async": True},
    ]

    config_path = output_dir / "zensical.toml"
    config_path.write_text(tomli_w.dumps(config))


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
) -> VersionResult:
    """Convert all doc sets for a single EnergyPlus version.

    Args:
        source_dir: Path to the cloned EnergyPlus repo
        output_dir: Path to write the build output
        version: Version tag (e.g., "v25.2.0")
        skip_build: If True, skip the zensical build step

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
    label_index = build_label_index(source_dir, doc_sets)

    # Convert each doc set
    for ds in doc_sets:
        logger.info("Converting doc set: %s", ds.title)
        ds_result = convert_doc_set(ds, output_dir, label_index)
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
    parser.add_argument("--verbose", "-v", action="store_true", help="Enable verbose logging")

    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s: %(message)s",
    )

    result = convert_version(args.source, args.output, args.version, skip_build=args.skip_build)

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
