# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a documentation-only project for EnergyPlus, built with [Zensical](https://zensical.org/).

## Common Commands

```bash
# Install dependencies
uv sync

# Run all quality checks (pre-commit hooks)
make check

# Convert a single version (builds AND deploys to dist/)
make convert VERSION=v25.2.0

# Serve the full multi-version site from dist/
make serve

# Hot-reload dev server (single version, for development)
make dev VERSION=v25.2.0

# Test documentation build
make docs-test
```

## Before Committing

Always run the quality gate before proposing changes:

```bash
make check
```

This runs: lock file validation and pre-commit hooks (file format checks).
