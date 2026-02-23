# idfkit-docs

[![Release](https://img.shields.io/github/v/release/samuelduchesne/idfkit-docs)](https://github.com/samuelduchesne/idfkit-docs/releases)
[![Build status](https://img.shields.io/github/actions/workflow/status/samuelduchesne/idfkit-docs/main.yml?branch=main)](https://github.com/samuelduchesne/idfkit-docs/actions/workflows/main.yml?query=branch%3Amain)
[![License](https://img.shields.io/github/license/samuelduchesne/idfkit-docs)](https://github.com/samuelduchesne/idfkit-docs/blob/main/LICENSE)

EnergyPlus documentation built with [Zensical](https://zensical.org/).

**[Documentation](https://docs.idfkit.com/)** | **[GitHub](https://github.com/samuelduchesne/idfkit-docs/)**

## Development

This project uses [uv](https://docs.astral.sh/uv/) for dependency management and [Zensical](https://zensical.org/) to build the documentation site.

### Setup

```bash
# Clone the repository
git clone https://github.com/samuelduchesne/idfkit-docs.git
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
