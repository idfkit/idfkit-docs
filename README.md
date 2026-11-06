<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="https://raw.githubusercontent.com/idfkit/idfkit-brand/identity-2026.5/marks/mark-on-dark.svg">
    <source media="(prefers-color-scheme: light)" srcset="https://raw.githubusercontent.com/idfkit/idfkit-brand/identity-2026.5/marks/mark-on-light.svg">
    <img alt="idfkit" width="72" src="https://raw.githubusercontent.com/idfkit/idfkit-brand/identity-2026.5/marks/tile.png">
  </picture>
</p>

# idfkit-docs

The EnergyPlus input and output reference, rendered by idfkit for every supported version.

[idfkit](https://idfkit.com) · [Developers](https://developers.idfkit.com) · [EnergyPlus docs](https://docs.idfkit.com) · [Envelop](https://app.idfkit.com) · [MCP](https://mcp.idfkit.com) · [Shoebox](https://shoebox.idfkit.com) · [GitHub](https://github.com/idfkit)

[![Build status](https://img.shields.io/github/actions/workflow/status/idfkit/idfkit-docs/main.yml?branch=main)](https://github.com/idfkit/idfkit-docs/actions/workflows/main.yml?query=branch%3Amain) [![License](https://img.shields.io/github/license/idfkit/idfkit-docs)](https://github.com/idfkit/idfkit-docs/blob/main/LICENSE)

EnergyPlus documentation built with [Zensical](https://zensical.org/). The conversion pipeline renders each EnergyPlus documentation set found in a release's `doc/` directory, among them the Input Output Reference, the Engineering Reference, Getting Started and the application guides. The thirteen configured sets are listed in `DOC_SET_INFO`, and the versions converted, v8.9.0 through v26.2.0, in `TARGET_VERSIONS`, both in `scripts/config.py`. The site carries the idfkit visual identity at the level declared under `[tool.idfkit.identity]` in `pyproject.toml`; the derivation is vendored under `identity/` and served as idfkit-brand built it.

## Development

This project uses [uv](https://docs.astral.sh/uv/) for dependency management and [Zensical](https://zensical.org/) to build the documentation site.

### Setup

```bash
# Clone the repository
git clone https://github.com/idfkit/idfkit-docs.git
cd idfkit-docs

# Install dependencies and pre-commit hooks
make install
```

### Commands

```bash
make install    # Install dependencies and pre-commit hooks
make check      # Check the lock file and run pre-commit hooks on all files
make docs-test  # Build the root site (docs/index.md only) with zensical
```

The conversion pipeline clones the `doc/` tree of an EnergyPlus release into `build/sources/`, converts it to Markdown under `build/<short version>/` (for example `build/v25.2`), and builds a site there:

```bash
make convert VERSION=v25.2.0        # Build the editor bundle, convert one version, then run make deploy for it
make build-version VERSION=v25.2.0  # Same as make convert
make deploy VERSION=v25.2.0         # Copy one built version into dist/ and regenerate the root files
make convert-all                    # Convert every version in TARGET_VERSIONS in parallel and merge them into dist/
make build-editor                   # Build the IDF Monaco editor bundle (npm) and copy it to scripts/assets/
```

`make deploy` writes to the local `dist/` directory only; it does not publish the site. To preview:

```bash
make dev                    # Serve the first version under build/ with zensical, with hot reload
make dev VERSION=v25.2.0    # Serve one converted version
make serve                  # Serve the merged multi-version site from dist/ on http://localhost:8003
```

`make docs-test` does not exercise the conversion pipeline or any converted version.

## Contributing

Contributions are welcome! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.
