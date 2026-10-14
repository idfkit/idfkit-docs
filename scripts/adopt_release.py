"""Commands that the adoption of an EnergyPlus release runs in this repository.

The adoption procedure is held in idfkit-conformance (``energyplus/README.md``). Its version roster
declares two commands for this project, and both are defined here.

``target-list TAG``
    Adds the release to ``TARGET_VERSIONS`` in ``scripts/config.py`` and designates it
    ``LATEST_VERSION``. The command refuses, with exit status 1, when the installed idfkit does not
    list the release. idfkit returns the newest schema it holds for a release it does not list, so
    a conversion against an older level would publish the field metadata of the previous release
    under the heading of the new one without failing.

``doc-sets TAG``
    Reports how the documentation directories of the upstream release map onto ``DOC_SET_INFO``:
    LaTeX directories that no configured set matches (converted under a generated title), Sphinx
    directories that no configured set matches (omitted from the site), configured sets found in
    neither tree, and sets whose source format differs from the preceding release. The command
    changes no file and exits with status 0 whatever it finds. A person accepts the report.

Both commands are idempotent.
"""

# Each refusal states its own reason, so the messages are composed where they are raised.
# ruff: noqa: TRY003

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from idfkit.versions import ENERGYPLUS_VERSIONS

from scripts.config import DOC_SET_INFO, ENERGYPLUS_REPO, EXCLUDED_DIRS, TARGET_VERSIONS
from scripts.rst_doc_sets import SPHINX_EXCLUDED_DIRS, SPHINX_SUBDIR, discover_rst_doc_sets

CONFIG_PATH = Path(__file__).parent / "config.py"

_TAG = re.compile(r"v(\d+)\.(\d+)\.(\d+)")
_TARGET_BLOCK = re.compile(
    r"(?P<head>^TARGET_VERSIONS: list\[str\] = \[\n)(?P<body>(?:    \"v\d+\.\d+\.\d+\",\n)+)(?P<tail>\]\n)",
    re.MULTILINE,
)
_LATEST_LINE = re.compile(r'^LATEST_VERSION: str = "v\d+\.\d+\.\d+"$', re.MULTILINE)


class AdoptionError(Exception):
    """The command cannot be performed. The message states the reason."""


@dataclass(frozen=True, order=True)
class ReleaseTag:
    """An EnergyPlus release, written ``vMAJOR.MINOR.PATCH`` in this repository."""

    major: int
    minor: int
    patch: int

    @classmethod
    def parse(cls, text: str) -> ReleaseTag:
        match = _TAG.fullmatch(text)
        if match is None:
            raise AdoptionError(f"'{text}' is not a release tag of the form vMAJOR.MINOR.PATCH")
        return cls(int(match.group(1)), int(match.group(2)), int(match.group(3)))

    def as_tuple(self) -> tuple[int, int, int]:
        return (self.major, self.minor, self.patch)

    def __str__(self) -> str:
        return f"v{self.major}.{self.minor}.{self.patch}"


# ── The target list ───────────────────────────────────────────────────────────


def require_library_lists(release: ReleaseTag) -> None:
    """Raise unless the installed idfkit lists *release* among its supported versions."""
    if release.as_tuple() not in ENERGYPLUS_VERSIONS:
        newest = ReleaseTag(*ENERGYPLUS_VERSIONS[-1])
        raise AdoptionError(
            f"the installed idfkit does not list {release}; its newest release is {newest}. "
            "Move the idfkit pin in pyproject.toml to a version that carries the release "
            "(bump-idfkit.yml) before adding the release to the target list."
        )


def with_release(config_text: str, release: ReleaseTag) -> str:
    """Return *config_text* with *release* in ``TARGET_VERSIONS`` and the newest entry as ``LATEST_VERSION``."""
    block = _TARGET_BLOCK.search(config_text)
    if block is None:
        raise AdoptionError("TARGET_VERSIONS was not found in scripts/config.py in the expected layout")
    if len(_LATEST_LINE.findall(config_text)) != 1:
        raise AdoptionError("LATEST_VERSION was not found exactly once in scripts/config.py")
    listed = {ReleaseTag.parse(tag) for tag in re.findall(r'"(v\d+\.\d+\.\d+)"', block.group("body"))}
    ordered = sorted(listed | {release})
    body = "".join(f'    "{tag}",\n' for tag in ordered)
    text = config_text[: block.start("body")] + body + config_text[block.end("body") :]
    return _LATEST_LINE.sub(f'LATEST_VERSION: str = "{ordered[-1]}"', text)


def add_to_target_list(release: ReleaseTag, config_path: Path = CONFIG_PATH) -> bool:
    """Write *release* into the configuration. Returns whether the file changed."""
    require_library_lists(release)
    before = config_path.read_text(encoding="utf-8")
    after = with_release(before, release)
    if after == before:
        return False
    config_path.write_text(after, encoding="utf-8")
    return True


# ── The documentation sets ────────────────────────────────────────────────────


@dataclass(frozen=True)
class DocSetSurvey:
    """How the documentation directories of one upstream release map onto ``DOC_SET_INFO``."""

    release: ReleaseTag
    #: Configured set name to the source format it is found in, ``latex`` or ``rst``.
    formats: dict[str, str] = field(default_factory=dict)
    #: LaTeX directories with a main document that no configured set names.
    unmatched_latex: tuple[str, ...] = ()
    #: Sphinx directories with a main document that no configured set or alias matches.
    unmatched_sphinx: tuple[str, ...] = ()

    @property
    def missing(self) -> tuple[str, ...]:
        return tuple(name for name in DOC_SET_INFO if name not in self.formats)


def _directories(parent: Path, excluded: frozenset[str] | set[str], suffix: str) -> list[Path]:
    if not parent.is_dir():
        return []
    return [
        entry
        for entry in sorted(parent.iterdir())
        if entry.is_dir()
        and entry.name not in excluded
        and not entry.name.startswith(".")
        and (entry / f"{entry.name}{suffix}").exists()
    ]


def survey(source_dir: Path, release: ReleaseTag) -> DocSetSurvey:
    """Survey a source tree with the rules ``discover_doc_sets`` applies in ``scripts/convert.py``.

    The LaTeX tree takes precedence. A Sphinx directory is used only for a configured set that the
    LaTeX tree does not provide.
    """
    doc_dir = source_dir / "doc"
    if not doc_dir.is_dir():
        raise AdoptionError(f"no doc/ directory at {source_dir}")
    latex = [entry.name for entry in _directories(doc_dir, EXCLUDED_DIRS, ".tex")]
    formats = {name: "latex" for name in latex if name in DOC_SET_INFO}
    matched_sphinx: set[str] = set()
    for doc_set in discover_rst_doc_sets(source_dir, DOC_SET_INFO):
        matched_sphinx.add(doc_set.source_dir.name)
        formats.setdefault(doc_set.dir_name, "rst")
    sphinx = [entry.name for entry in _directories(doc_dir / SPHINX_SUBDIR, SPHINX_EXCLUDED_DIRS, ".rst")]
    return DocSetSurvey(
        release=release,
        formats=formats,
        unmatched_latex=tuple(name for name in latex if name not in DOC_SET_INFO),
        unmatched_sphinx=tuple(name for name in sphinx if name not in matched_sphinx),
    )


def fetch_entry_documents(release: ReleaseTag, destination: Path) -> Path:
    """Check out the entry document of every documentation directory of *release*, and nothing else."""
    target = destination / str(release)
    commands = [
        ["git", "clone", "--quiet", "--filter=blob:none", "--no-checkout", "--depth=1", "--branch", str(release), "--single-branch", ENERGYPLUS_REPO, str(target)],
        ["git", "-C", str(target), "sparse-checkout", "set", "--no-cone", "/doc/*/*.tex", f"/doc/{SPHINX_SUBDIR}/*/*.rst"],
        ["git", "-C", str(target), "checkout", "--quiet"],
    ]  # fmt: skip
    for command in commands:
        done = subprocess.run(command, capture_output=True, text=True, check=False)
        if done.returncode != 0:
            raise AdoptionError(f"{' '.join(command[:3])} failed for {release}: {done.stderr.strip()}")
    return target


def preceding(release: ReleaseTag) -> ReleaseTag | None:
    """The newest configured release older than *release*, or ``None``."""
    older = [tag for tag in map(ReleaseTag.parse, TARGET_VERSIONS) if tag < release]
    return max(older) if older else None


def render(current: DocSetSurvey, previous: DocSetSurvey | None) -> str:
    """The report a person accepts, as Markdown."""

    def listing(names: tuple[str, ...] | list[str]) -> list[str]:
        return [f"- `{name}`" for name in names] or ["- none"]

    lines = [f"### Documentation sets of EnergyPlus {current.release}", ""]
    lines += [f"Configured sets found: {len(current.formats)} of {len(DOC_SET_INFO)}.", ""]
    lines += ["**Sphinx directories that no configured set matches (omitted from the site):**", ""]
    lines += [*listing(current.unmatched_sphinx), ""]
    lines += ["**LaTeX directories that no configured set matches (converted under a generated title):**", ""]
    lines += [*listing(current.unmatched_latex), ""]
    lines += ["**Configured sets found in neither tree (absent from the build):**", ""]
    lines += [*listing(current.missing), ""]
    if previous is not None:
        moved = [
            f"{name}: {previous.formats[name]} in {previous.release}, {fmt} in {current.release}"
            for name, fmt in current.formats.items()
            if name in previous.formats and previous.formats[name] != fmt
        ]
        new = [name for name in (*current.unmatched_latex, *current.unmatched_sphinx) if name not in (*previous.unmatched_latex, *previous.unmatched_sphinx)]  # fmt: skip
        lines += [f"**Sets whose source format differs from {previous.release}:**", "", *listing(moved), ""]
        lines += [f"**Unmatched directories that {previous.release} did not have:**", "", *listing(new), ""]
    lines += [
        "Accept when each unmatched directory is either configured in `DOC_SET_INFO` or `DOC_SET_ALIASES` "
        "with a title, or stated as excluded, and each set that changed format has been converted once "
        f"(`make convert VERSION={current.release}`) and read.",
    ]
    return "\n".join(lines) + "\n"


def report_doc_sets(release: ReleaseTag, source: Path | None) -> str:
    with tempfile.TemporaryDirectory() as scratch:
        current = survey(source or fetch_entry_documents(release, Path(scratch)), release)
        before = preceding(release)
        previous = survey(fetch_entry_documents(before, Path(scratch)), before) if before and source is None else None
        return render(current, previous)


# ── The command line ──────────────────────────────────────────────────────────


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Commands of an EnergyPlus release adoption")
    commands = parser.add_subparsers(dest="command", required=True)
    target = commands.add_parser(
        "target-list", help="Add a release to TARGET_VERSIONS and designate the newest as latest"
    )
    target.add_argument("release", help="Release tag (e.g., v25.2.0)")
    sets = commands.add_parser("doc-sets", help="Report how upstream documentation directories map onto DOC_SET_INFO")
    sets.add_argument("release", help="Release tag (e.g., v25.2.0)")
    sets.add_argument("--source", type=Path, help="An EnergyPlus source tree to survey instead of fetching the release")
    args = parser.parse_args(argv)

    try:
        release = ReleaseTag.parse(args.release)
        if args.command == "target-list":
            changed = add_to_target_list(release)
            print(f"{release}: {'added to' if changed else 'already in'} scripts/config.py")
            return 0
        report = report_doc_sets(release, args.source)
    except AdoptionError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    print(report)
    # A command the adoption run executes has its output kept only on failure. The job summary is
    # where a successful run shows the report.
    if summary := os.environ.get("GITHUB_STEP_SUMMARY"):
        with Path(summary).open("a", encoding="utf-8") as handle:
            handle.write(report)
    return 0


if __name__ == "__main__":
    sys.exit(main())
