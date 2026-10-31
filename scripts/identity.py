"""The vendored idfkit identity derivation.

``identity/`` at the repository root is a copy of ``idfkit-brand/dist/`` at the tag
``pyproject.toml`` declares under ``[tool.idfkit.identity]``: the ``material`` derivation for
the per-version sites, the ``css`` derivation for the version picker, and the per-host files of
``docs.idfkit.com``. Nothing in this repository edits those files. This module copies them into
the generated sites and composes the head and footer fragments the sites include, marking the
current family link as the derivation contract asks the consumer to do.
"""

from __future__ import annotations

import re
import shutil
from dataclasses import dataclass
from pathlib import Path

IDENTITY_DIR: Path = Path(__file__).resolve().parent.parent / "identity"
MATERIAL_DIR: Path = IDENTITY_DIR / "material"
CSS_DIR: Path = IDENTITY_DIR / "css"
HOST_DIR: Path = IDENTITY_DIR / "hosts" / "docs.idfkit.com"

#: The host and its property name, as touchpoints.toml in idfkit-brand records them.
HOST_URL: str = "https://docs.idfkit.com"
PROPERTY_NAME: str = "EnergyPlus docs"

#: Where the material derivation lands inside a per-version site's docs/ directory, and the
#: stylesheet paths the generated zensical.toml links, in the order the derivation contract fixes:
#: the derivation first, the site's own stylesheets after it.
MATERIAL_SITE_DIR: str = "identity/material"
MATERIAL_EXTRA_CSS: tuple[str, ...] = (f"{MATERIAL_SITE_DIR}/material.css", f"{MATERIAL_SITE_DIR}/fonts.css")
MATERIAL_LOGO: str = f"{MATERIAL_SITE_DIR}/logo.svg"
MATERIAL_FAVICON: str = f"{MATERIAL_SITE_DIR}/favicon.svg"

#: Where the css derivation lands inside the deployment root, for the version picker.
CSS_SITE_DIR: str = "identity/css"
CSS_LINKS: tuple[str, ...] = (
    f"{CSS_SITE_DIR}/tokens.css",
    f"{CSS_SITE_DIR}/fonts.css",
    f"{CSS_SITE_DIR}/motion.css",
    f"{CSS_SITE_DIR}/forced-colors.css",
)

_LEADING_COMMENT = re.compile(r"\A\s*<!--.*?-->\s*", re.DOTALL)


@dataclass(frozen=True)
class IdentityFragments:
    """The HTML fragments the derivation provides, ready to inline."""

    head: str
    """``hosts/docs.idfkit.com/head.html``: favicons, theme colours and the social image."""

    footer: str
    """``material/footer.html``: the ownership line and the family links, the current one marked."""

    attribution: str
    """``material/attribution.html``: the sentence identifying the site and attributing the content."""

    family_links: str
    """``css/family-links.html``: the seven links, the current one marked."""

    ownership: str
    """``css/ownership.html``: the ownership line."""


def _fragment(path: Path) -> str:
    """Read a vendored fragment without the generator's leading comment."""
    return _LEADING_COMMENT.sub("", path.read_text(encoding="utf-8")).strip()


def mark_current(html: str) -> str:
    """Add ``aria-current="page"`` to this host's family link (FR-019)."""
    return html.replace(f'<a href="{HOST_URL}">', f'<a href="{HOST_URL}" aria-current="page">', 1)


def load_fragments() -> IdentityFragments:
    """Read the fragments from the vendored derivation."""
    return IdentityFragments(
        head=_fragment(HOST_DIR / "head.html"),
        footer=mark_current(_fragment(MATERIAL_DIR / "footer.html")),
        attribution=_fragment(MATERIAL_DIR / "attribution.html"),
        family_links=mark_current(_fragment(CSS_DIR / "family-links.html")),
        ownership=_fragment(CSS_DIR / "ownership.html"),
    )


def copy_material(docs_dir: Path) -> Path:
    """Copy the material derivation into a per-version site's docs/ directory."""
    target = docs_dir / MATERIAL_SITE_DIR
    if target.exists():
        shutil.rmtree(target)
    shutil.copytree(MATERIAL_DIR, target)
    return target


def copy_css(root_dir: Path) -> Path:
    """Copy the css derivation into the deployment root, for the version picker."""
    target = root_dir / CSS_SITE_DIR
    if target.exists():
        shutil.rmtree(target)
    shutil.copytree(CSS_DIR, target)
    return target


def copy_host_files(root_dir: Path) -> list[Path]:
    """Copy the per-host files to the deployment root, where head.html's paths point.

    ``head.html`` itself is not served; the sites inline it.
    """
    root_dir.mkdir(parents=True, exist_ok=True)
    copied: list[Path] = []
    for source in sorted(HOST_DIR.iterdir()):
        if not source.is_file() or source.name == "head.html":
            continue
        target = root_dir / source.name
        shutil.copy2(source, target)
        copied.append(target)
    return copied
