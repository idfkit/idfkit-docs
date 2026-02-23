# idfkit-docs

[![Release](https://img.shields.io/github/v/release/samuelduchesne/idfkit-docs)](https://github.com/samuelduchesne/idfkit-docs/releases)
[![Build status](https://img.shields.io/github/actions/workflow/status/samuelduchesne/idfkit-docs/main.yml?branch=main)](https://github.com/samuelduchesne/idfkit-docs/actions/workflows/main.yml?query=branch%3Amain)
[![codecov](https://codecov.io/gh/samuelduchesne/idfkit-docs/branch/main/graph/badge.svg)](https://codecov.io/gh/samuelduchesne/idfkit-docs)
[![License](https://img.shields.io/github/license/samuelduchesne/idfkit-docs)](https://github.com/samuelduchesne/idfkit-docs/blob/main/LICENSE)

EnergyPlus documenation builtt with Zensical

**[Documentation](https://samuelduchesne.github.io/idfkit-docs/)** | **[GitHub](https://github.com/samuelduchesne/idfkit-docs/)**

## Installation

```bash
pip install idfkit-docs
```

Or with [uv](https://docs.astral.sh/uv/):

```bash
uv add idfkit-docs
```

## Usage

```python
import idfkit_docs

# TODO: Add usage examples
```

## Development

This project uses [uv](https://docs.astral.sh/uv/) for dependency management.

### Setup

```bash
# Clone the repository
git clone https://github.com/samuelduchesne/idfkit-docs.git
cd idfkit-docs

# Install dependencies and pre-commit hooks
make install
```

> **Note:** Run `git init -b main` first if you're starting from a cookiecutter template.

### Commands

```bash
make install    # Install dependencies and pre-commit hooks
make check      # Run linting, formatting, and type checks
make test       # Run tests with coverage
make docs       # Serve documentation locally
make docs-test  # Test documentation build
```

### First-time setup for new projects

If you just created this project from the cookiecutter template:

1. Create a GitHub repository with the same name
2. Push your code:

   ```bash
   git init -b main
   git add .
   git commit -m "Initial commit"
   git remote add origin git@github.com:samuelduchesne/idfkit-docs.git
   git push -u origin main
   ```

3. Install dependencies: `make install`
4. Fix formatting and commit:

   ```bash
   git add .
   uv run pre-commit run -a
   git add .
   git commit -m "Apply formatting"
   git push
   ```

For detailed setup instructions, see the [cookiecutter-gi tutorial](https://samuelduchesne.github.io/cookiecutter-gi/tutorial/).


## Contributing

Contributions are welcome! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

---

*Built with [cookiecutter-gi](https://github.com/samuelduchesne/cookiecutter-gi)*
