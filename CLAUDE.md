# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**idfkit-docs** converts EnergyPlus LaTeX documentation into a multi-version Markdown website built with [Zensical](https://zensical.org/). It automates the full pipeline: clone EnergyPlus source, preprocess LaTeX, convert via Pandoc, postprocess Markdown, and deploy as a static site.

- **Site:** <https://docs.idfkit.com/>
- **Repo:** <https://github.com/samuelduchesne/idfkit-docs>
- **Upstream source:** <https://github.com/NatLabRockies/EnergyPlus>
- **Versions covered:** v8.9.0 through v25.2.0 (16 versions)
- **Doc sets:** 13 per version (IO Reference, Engineering Reference, Getting Started, etc.)

## Common Commands

```bash
# Install dependencies (requires uv)
uv sync

# Install pre-commit hooks
make install

# Run all quality checks (lock validation + pre-commit hooks)
make check

# Convert a single version (clones source, converts, builds, and deploys to dist/)
make convert VERSION=v25.2.0

# Deploy an already-built version to dist/
make deploy VERSION=v25.2.0

# Convert all target versions in parallel
make convert-all

# Serve the full multi-version site from dist/
make serve

# Hot-reload dev server for a single version (for development)
make dev VERSION=v25.2.0

# Test documentation build (validates Zensical can build docs/)
make docs-test
```

## Before Committing

Always run the quality gate before proposing changes:

```bash
make check
```

This runs:
1. `uv lock --locked` — validates the lock file matches pyproject.toml
2. `uv run pre-commit run -a` — runs all pre-commit hooks on all files

## Architecture

### Conversion Pipeline

The core pipeline for a single version:

```
EnergyPlus .tex source
  → scripts/latex_preprocessor.py   (expand macros, siunitx units, strip \input{})
  → Pandoc with scripts/pandoc_filters/energyplus.lua   (LaTeX → Markdown)
  → scripts/markdown_postprocessor.py   (fix links, images, cross-refs, front matter)
  → Zensical build   (Markdown → HTML site)
```

### Directory Layout

```
scripts/
├── config.py                 # Constants: TARGET_VERSIONS, DOC_SET_INFO, LATEST_VERSION
├── models.py                 # Dataclasses: DocSet, NavItem, LabelRef, ConversionResult, etc.
├── convert.py                # Single-version converter (main entry point)
├── convert_all.py            # Parallel multi-version orchestrator (ProcessPoolExecutor)
├── version_manager.py        # versions.json manifest, root landing page, deployment
├── latex_preprocessor.py     # LaTeX macro expansion (siunitx, custom macros)
├── markdown_postprocessor.py # Post-Pandoc cleanup (links, images, cross-refs, front matter)
├── nav_generator.py          # Navigation structure from LaTeX \input chains
└── pandoc_filters/
    └── energyplus.lua        # Pandoc Lua filter (tables, admonitions, cross-refs)
docs/
└── index.md                  # Root docs page (for Zensical)
build/                        # (gitignored) Build artifacts and cloned sources
dist/                         # (gitignored) Final deployed multi-version site
```

### Key Modules

- **`scripts/config.py`** — All configuration constants. `TARGET_VERSIONS` lists every supported version. `DOC_SET_INFO` maps EnergyPlus directory names to display titles and URL slugs. Helper functions `version_to_short()` and `version_to_title()` handle version string formatting.

- **`scripts/convert.py`** — Main entry point for single-version conversion. Discovers doc sets, builds a label index for cross-references, copies media files, converts each `.tex` file through the full pipeline, generates navigation, and writes `zensical.toml` per version.

- **`scripts/convert_all.py`** — Orchestrates parallel conversion of all target versions using `ProcessPoolExecutor`. Sparse-clones EnergyPlus repos, supports caching and force-rebuild.

- **`scripts/latex_preprocessor.py`** — Handles siunitx macros (`\SI{}`, `\si{}`, `\IP{}`), custom bracket macros (`\PB{}`, `\RB{}`, `\CB{}`), callout environments, and strips `\input{}` directives before Pandoc processing.

- **`scripts/markdown_postprocessor.py`** — Rewrites internal PDF links to cross-doc-set Markdown links, fixes image paths, resolves cross-references via the label index, generates YAML front matter, and normalizes formatting.

- **`scripts/nav_generator.py`** — Recursively parses LaTeX `\input{src/...}` directives to build the hierarchical navigation tree for the Zensical config.

- **`scripts/pandoc_filters/energyplus.lua`** — Pandoc Lua filter that converts tables to pipe-table markdown (Zensical compatibility), handles admonitions from blockquotes, normalizes non-breaking spaces, and processes code blocks.

- **`scripts/version_manager.py`** — Generates `versions.json` manifest for the version selector, creates the root landing page with version cards, and handles deployment of built versions to `dist/`.

## Tooling & Dependencies

- **Python:** >=3.10, <4.0
- **Package manager:** [uv](https://docs.astral.sh/uv/) (Astral)
- **Doc framework:** [Zensical](https://zensical.org/) >=0.0.23
- **LaTeX converter:** Pandoc (via pypandoc)
- **Linter/formatter:** Ruff (line length 120, preview formatting enabled)
- **Pre-commit hooks:** trailing whitespace, EOF fixer, YAML/JSON/TOML validation, Ruff lint + format

### Ruff Configuration

- Target: Python 3.10
- Line length: 120
- Auto-fix enabled
- Rules: flake8-bandit, flake8-bugbear, flake8-comprehensions, isort, pyupgrade, and more
- Ignored: E501 (line too long), E731 (lambda assignment), S603/S607 (subprocess — intentional)

## CI/CD

All workflows are in `.github/workflows/`:

- **`main.yml`** — Runs on push to main and PRs. Checks quality (`make check`) and docs build (`zensical build`).
- **`check-new-release.yml`** — Weekly cron (Monday 08:00 UTC) checks for new EnergyPlus releases on NatLabRockies/EnergyPlus and triggers a conversion if found.
- **`convert-docs.yml`** — Main build pipeline. Matrix job that converts each version in parallel, then merges all outputs and deploys to GitHub Pages.
- **`on-release-main.yml`** — Triggers full rebuild of all versions when a release is published on this repo.

A reusable action at `.github/actions/setup-python-env/action.yml` handles Python + uv setup.

## Conventions

- All Python code is formatted and linted by Ruff. Run `make check` to validate.
- Version tags follow the format `vMAJOR.MINOR.PATCH` (e.g., `v25.2.0`). Short form is `vMAJOR.MINOR` (e.g., `v25.2`).
- New EnergyPlus versions require adding entries to `TARGET_VERSIONS` and updating `LATEST_VERSION` in `scripts/config.py`. If the new version has a new doc set, add it to `DOC_SET_INFO`.
- The `build/` and `dist/` directories are gitignored. `build/sources/` holds cloned EnergyPlus repos; `build/vXX.X/` holds per-version Zensical projects; `dist/` holds the final deployed site.
- The Zensical site configuration template is in `zensical.toml` (root). Per-version configs are generated dynamically by `scripts/convert.py`.
