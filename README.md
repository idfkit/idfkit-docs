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

EnergyPlus documentation built with [Zensical](https://zensical.org/). The site carries the idfkit visual identity at the level declared under `[tool.idfkit.identity]` in `pyproject.toml`; the derivation is vendored under `identity/` and served as idfkit-brand built it.

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
make check      # Run pre-commit hooks
make docs       # Serve documentation locally
make docs-test  # Test documentation build
```

## Contributing

Contributions are welcome! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.
