"""Data models for the EnergyPlus documentation conversion pipeline."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class DocSet:
    """A single EnergyPlus documentation set (e.g., getting-started)."""

    dir_name: str
    title: str
    slug: str
    source_dir: Path
    main_tex: Path

    @property
    def media_dir(self) -> Path:
        return self.source_dir / "media"

    @property
    def src_dir(self) -> Path:
        return self.source_dir / "src"


@dataclass
class InputEntry:
    r"""An \input{} entry parsed from a main .tex file."""

    rel_path: str
    tex_path: Path
    heading_level: int = 0
    heading_title: str = ""


@dataclass
class NavItem:
    """A navigation item for the Zensical config."""

    title: str
    path: str
    children: list[NavItem] = field(default_factory=list)


@dataclass
class LabelRef:
    """A LaTeX label mapped to its output markdown path."""

    label: str
    output_path: str
    heading_anchor: str = ""
    label_type: str = ""  # "equation" | "figure" | "" (for future: "table")
    equation_latex: str = ""  # Raw LaTeX content (for tooltip data-equation attribute)
    equation_number: int = 0  # MathJax AMS equation number on the target page (1-based)
    figure_number: int = 0  # Doc-set-wide figure number (1-based)


@dataclass
class ConversionResult:
    """Result of converting a single .tex file."""

    source: Path
    output: Path
    success: bool
    warnings: list[str] = field(default_factory=list)
    error: str = ""


@dataclass
class DocSetResult:
    """Result of converting an entire doc set."""

    doc_set: DocSet
    file_results: list[ConversionResult] = field(default_factory=list)

    @property
    def success_count(self) -> int:
        return sum(1 for r in self.file_results if r.success)

    @property
    def failure_count(self) -> int:
        return sum(1 for r in self.file_results if not r.success)


@dataclass
class VersionResult:
    """Result of converting all doc sets for a single version."""

    version: str
    doc_set_results: list[DocSetResult] = field(default_factory=list)
    build_success: bool = False
    build_error: str = ""

    @property
    def total_files(self) -> int:
        return sum(len(r.file_results) for r in self.doc_set_results)

    @property
    def total_successes(self) -> int:
        return sum(r.success_count for r in self.doc_set_results)

    @property
    def total_failures(self) -> int:
        return sum(r.failure_count for r in self.doc_set_results)


@dataclass
class VersionEntry:
    """An entry in the versions.json manifest."""

    version: str
    title: str
    aliases: list[str] = field(default_factory=list)
