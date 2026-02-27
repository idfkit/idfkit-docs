"""Parallel orchestrator for converting all EnergyPlus versions locally.

Spawns convert.py for each target version using ProcessPoolExecutor,
then merges all outputs into a unified deployment directory.

Usage:
    python -m scripts.convert_all [--versions v25.2.0 v25.1.0] [--max-workers 4]
"""

from __future__ import annotations

import argparse
import logging
import os
import subprocess
import sys
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

from scripts.config import ENERGYPLUS_REPO, TARGET_VERSIONS, version_to_short
from scripts.convert import convert_version
from scripts.models import VersionResult
from scripts.version_manager import merge_version_outputs

logger = logging.getLogger(__name__)

BUILD_DIR = Path("build")
DEPLOY_DIR = Path("dist")
CLONE_DIR = BUILD_DIR / "sources"


def clone_version(version: str, clone_dir: Path) -> Path:
    """Sparse-clone only the doc/ directory of the EnergyPlus repo at a specific version tag.

    Uses --filter=blob:none with sparse-checkout so we download ~90 MB
    instead of ~1.4 GB per version.
    Returns the path to the cloned repo.
    """
    target = clone_dir / version
    if target.exists() and (target / "doc").exists() and (target / "idd").exists():
        logger.info("Source for %s already exists, reusing", version)
        return target

    # Clean up any partial clone
    if target.exists():
        import shutil

        shutil.rmtree(target)

    logger.info("Cloning EnergyPlus %s (sparse, doc/ only)...", version)

    subprocess.run(
        [
            "git",
            "clone",
            "--filter=blob:none",
            "--no-checkout",
            "--depth=1",
            "--branch",
            version,
            "--single-branch",
            ENERGYPLUS_REPO,
            str(target),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    subprocess.run(
        ["git", "-C", str(target), "sparse-checkout", "set", "doc", "idd"],
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "-C", str(target), "checkout"],
        check=True,
        capture_output=True,
    )

    return target


def process_version(
    version: str, *, force_rebuild: bool = False, skip_build: bool = False, file_workers: int = 1
) -> VersionResult:
    """Clone and convert a single version. Designed to run in a worker process."""
    short = version_to_short(version)
    output_dir = BUILD_DIR / short

    # Check cache
    if not force_rebuild and (output_dir / "site").exists():
        logger.info("Skipping %s (already built, use --force-rebuild to rebuild)", version)
        return VersionResult(version=version, build_success=True)

    # Clone
    source_dir = clone_version(version, CLONE_DIR)

    # Convert
    return convert_version(source_dir, output_dir, version, skip_build=skip_build, max_workers=file_workers)


def main() -> None:
    """CLI entry point for parallel multi-version conversion."""
    parser = argparse.ArgumentParser(description="Convert EnergyPlus docs for all versions")
    parser.add_argument(
        "--versions",
        nargs="*",
        default=None,
        help="Specific versions to convert (default: all target versions)",
    )
    parser.add_argument(
        "--max-workers",
        type=int,
        default=os.cpu_count() or 4,
        help="Maximum parallel workers (default: CPU count)",
    )
    parser.add_argument(
        "--file-workers",
        type=int,
        default=1,
        help="Parallel file conversions per version (default: 1, to avoid oversubscription with --max-workers)",
    )
    parser.add_argument("--force-rebuild", action="store_true", help="Force rebuild even if cached")
    parser.add_argument("--skip-build", action="store_true", help="Skip zensical build step")
    parser.add_argument("--verbose", "-v", action="store_true", help="Enable verbose logging")

    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s [%(processName)s]: %(message)s",
    )

    versions = args.versions or TARGET_VERSIONS

    logger.info("Converting %d versions with up to %d workers", len(versions), args.max_workers)

    results: dict[str, VersionResult] = {}

    with ProcessPoolExecutor(max_workers=args.max_workers) as executor:
        future_to_version = {
            executor.submit(
                process_version,
                v,
                force_rebuild=args.force_rebuild,
                skip_build=args.skip_build,
                file_workers=args.file_workers,
            ): v
            for v in versions
        }

        for future in as_completed(future_to_version):
            version = future_to_version[future]
            try:
                result = future.result()
                results[version] = result
            except Exception as e:
                logger.exception("Version %s failed", version)
                results[version] = VersionResult(version=version, build_error=str(e))

    # Merge outputs
    if not args.skip_build:
        successful_versions = {v: BUILD_DIR / version_to_short(v) for v, r in results.items() if r.build_success}

        if successful_versions:
            logger.info("Merging %d version outputs to %s", len(successful_versions), DEPLOY_DIR)
            merge_version_outputs(successful_versions, DEPLOY_DIR)
        else:
            logger.error("No versions built successfully, skipping merge")

    # Print summary
    print(f"\n{'=' * 60}")
    print("Conversion Summary")
    print(f"{'=' * 60}")
    for v in versions:
        r = results.get(v)
        if r is None:
            print(f"  [{v}] NOT STARTED")
        elif r.build_success:
            print(f"  [{v}] OK - {r.total_successes}/{r.total_files} files")
        else:
            print(f"  [{v}] FAILED - {r.build_error}")

    successful = sum(1 for r in results.values() if r.build_success)
    print(f"\n{successful}/{len(versions)} versions built successfully")

    sys.exit(0 if successful == len(versions) else 1)


if __name__ == "__main__":
    main()
