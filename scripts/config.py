"""Configuration constants for the EnergyPlus documentation conversion pipeline."""

from __future__ import annotations

# Target EnergyPlus versions to convert (oldest to newest)
TARGET_VERSIONS: list[str] = [
    "v8.9.0",
    "v9.0.1",
    "v9.1.0",
    "v9.2.0",
    "v9.3.0",
    "v9.4.0",
    "v9.5.0",
    "v9.6.0",
    "v22.1.0",
    "v22.2.0",
    "v23.1.0",
    "v23.2.0",
    "v24.1.0",
    "v24.2.0",
    "v25.1.0",
    "v25.2.0",
]

LATEST_VERSION: str = "v25.2.0"

ENERGYPLUS_REPO: str = "https://github.com/NatLabRockies/EnergyPlus.git"

# Display titles and URL slugs for each doc set directory name.
# Keys are directory names under doc/ in the EnergyPlus repo.
DOC_SET_INFO: dict[str, tuple[str, str]] = {
    "input-output-reference": ("Input Output Reference", "io-reference"),
    "engineering-reference": ("Engineering Reference", "engineering-reference"),
    "getting-started": ("Getting Started", "getting-started"),
    "external-interfaces-application-guide": ("External Interfaces", "external-interfaces"),
    "interface-developer": ("Interface Developer", "interface-developer"),
    "module-developer": ("Module Developer", "module-developer"),
    "output-details-and-examples": ("Output Details", "output-details"),
    "plant-application-guide": ("Plant Application Guide", "plant-guide"),
    "using-energyplus-for-compliance": ("Compliance", "compliance"),
    "ems-application-guide": ("EMS Application Guide", "ems-guide"),
    "tips-and-tricks-using-energyplus": ("Tips and Tricks", "tips-and-tricks"),
    "auxiliary-programs": ("Auxiliary Programs", "auxiliary-programs"),
    "essentials": ("EnergyPlus Essentials", "essentials"),
}

# Directories under doc/ to exclude (not documentation sets)
EXCLUDED_DIRS: set[str] = {
    "cmake",
    "tools",
    "test",
    "man",
    ".gitignore",
}

# Image file extensions to copy
IMAGE_EXTENSIONS: set[str] = {
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".svg",
    ".pdf",
    ".eps",
}


def version_to_short(version: str) -> str:
    """Convert a full version tag like 'v25.2.0' to a short form like 'v25.2'."""
    parts = version.lstrip("v").split(".")
    return f"v{parts[0]}.{parts[1]}"


def version_to_title(version: str) -> str:
    """Convert a version tag like 'v25.2.0' to a display title like '25.2.0'."""
    return version.lstrip("v")
