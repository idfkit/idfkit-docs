# Contributing to `idfkit-docs`

Contributions are welcome, and they are greatly appreciated!
Every little bit helps, and credit will always be given.

You can contribute in many ways:

# Types of Contributions

## Report Bugs

Report bugs at https://github.com/samuelduchesne/idfkit-docs/issues

If you are reporting a bug, please include:

- Your operating system name and version.
- Any details about your local setup that might be helpful in troubleshooting.
- Detailed steps to reproduce the bug.

## Write Documentation

idfkit-docs could always use more documentation. Whether fixing a typo or adding a new section, all improvements are appreciated.

## Submit Feedback

The best way to send feedback is to file an issue at https://github.com/samuelduchesne/idfkit-docs/issues.

# Get Started!

Ready to contribute? Here's how to set up `idfkit-docs` for local development.
Please note this documentation assumes you already have `uv` and `Git` installed and ready to go.

1. Fork the `idfkit-docs` repo on GitHub.

2. Clone your fork locally:

```bash
cd <directory_in_which_repo_should_be_created>
git clone git@github.com:YOUR_NAME/idfkit-docs.git
```

3. Navigate into the directory and install the environment:

```bash
cd idfkit-docs
make install
```

4. Create a branch for local development:

```bash
git checkout -b name-of-your-contribution
```

Now you can make your changes locally.

1. Preview the documentation locally:

```bash
make docs
```

1. When you're done making changes, check that the documentation builds correctly:

```bash
make check
make docs-test
```

1. Commit your changes and push your branch to GitHub:

```bash
git add .
git commit -m "Your detailed description of your changes."
git push origin name-of-your-contribution
```

1. Submit a pull request through the GitHub website.

# Pull Request Guidelines

Before you submit a pull request, check that it meets these guidelines:

1. The documentation should build without errors (`make docs-test`).
2. Pre-commit hooks should pass (`make check`).
