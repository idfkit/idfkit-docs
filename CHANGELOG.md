# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.2.1] - 2026-11-13

### Changed

- The site and the README move to the idfkit visual identity at `identity-2026.5`. The vendored files under `identity/` differ from `identity-2026.4` only in the tag they name; `pyproject.toml` and `.github/workflows/check-identity.yml` declare the new tag (#48).

### Fixed

- The deploy job publishes the identity files at the site root. Previously the landing page on docs.idfkit.com linked a stylesheet, the lockup and the favicon set that all returned 404 (#47).
- The `rehearse-candidate.yml` workflow runs at `governance-2026.32`, which installs the idfkit candidate into this repository's own environment. At the previous tag the install step failed before any check ran (#50).

## [0.2.0] - 2026-11-04

### Added

- EnergyPlus 26.2.0 documentation, now designated the latest version (#39).
- Four documentation sets restored for EnergyPlus 24.2.0 and later: Auxiliary Programs, EMS Application Guide, Tips and Tricks and EnergyPlus Essentials. Upstream moved them from LaTeX to reStructuredText, and the converter now reads both source trees. On v26.1.0 this raises the converted pages from 455 to 755 (#32).
- A warning when a configured documentation set is found in neither upstream source tree, so a future upstream reorganisation no longer drops a set silently (#32).
- The idfkit visual identity at `identity-2026.4`: the lockup and version in the header of every per-version site, the identity colours on the version picker, and the identity header in the README (#44).
- An `adopt-energyplus.yml` workflow and `scripts/adopt_release.py`, which add an EnergyPlus release to the target list and report upstream documentation sets that are new, renamed or have changed source format (#36).
- A `bump-idfkit.yml` workflow, dispatched by an idfkit release, that opens a pull request raising the idfkit dependency.
- Membership in the consumer register of idfkit-conformance, with a `rehearse-candidate.yml` workflow for testing an unpublished idfkit candidate (#33).

### Changed

- The IDF editor in code blocks is built on the published `@idfkit/core`, `@idfkit/language` and `@idfkit/schemas` packages (0.4.0) instead of its own grammar and schema loader. Each page selects the schema of its EnergyPlus version, and schema data (about 1.1 MB) is fetched when the first editor is created rather than on page load (#46).
- The idfkit dependency is raised from 0.8.0 to 1.2.0 (#23, #25, #38, #41, #42, #43).

### Removed

- The weekly upstream release check, whose schedule GitHub had disabled for inactivity. Upstream releases are now detected centrally in idfkit-conformance (#35).

### Fixed

- The "latest" badge on the version picker is legible in the dark theme; its contrast rises from 2.28:1 to 8.68:1 (#45).
- Hover documentation in the IDF editor shows placeholders such as `<Zone Name>` instead of dropping them as markup (#46).
- Repository links point to the `idfkit` organisation.

## [0.1.0] - 2026-04-16

### Added

- EnergyPlus 26.1.0 documentation, designated the latest version; 17 versions are covered, from 8.9.0 through 26.1.0.
- A Monaco editor for IDF code blocks, with schema-driven field metadata (#19).
- Equation numbering, figure numbering, figure caption preservation and cross-reference anchors with interactive tooltips (#10, #13).
- The full set of Zensical admonition types, where only warnings were converted before (#11).
- Search tags for filtering by documentation set, hidden from the rendered page (#7, #12).
- SEO metadata and sitemap generation (#20).
- Documentation previews on pull requests (#8).

### Changed

- Documentation files are converted in parallel, which shortens full rebuilds (#9).
- Figures and their captions are centred (#15).
- The idfkit dependency is raised to 0.8.0.

### Fixed

- Schema serialisation no longer fails on EnergyPlus 8.9 through 9.5 (#21).
- Deploying to GitHub Pages no longer resets the custom domain (#22).
- Deploying a single version no longer removes the other published versions.

## [0.0.1] - 2026-02-24

### Added

- A pipeline that converts the EnergyPlus LaTeX documentation to Markdown and builds a Zensical site per EnergyPlus version, with navigation, theming, admonitions, code copy and per-document tables of contents.

### Fixed

- Equation labels, Pandoc reference attributes and image caption artifacts in converted pages (#2).
- Running the conversion on Python 3.10 (#6).

[unreleased]: https://github.com/idfkit/idfkit-docs/compare/v0.2.1...HEAD
[0.2.1]: https://github.com/idfkit/idfkit-docs/compare/v0.2.0...v0.2.1
[0.2.0]: https://github.com/idfkit/idfkit-docs/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/idfkit/idfkit-docs/compare/v0.0.1...v0.1.0
[0.0.1]: https://github.com/idfkit/idfkit-docs/releases/tag/v0.0.1
