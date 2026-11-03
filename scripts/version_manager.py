"""Version manifest generation for the EnergyPlus documentation site.

Generates:
- versions.json: Manifest read by Zensical's built-in version selector
- Root index.html: The version picker, carrying the idfkit identity
- The css derivation and the host's favicon set beside it
"""

from __future__ import annotations

import json
import re
import shutil
from dataclasses import asdict
from pathlib import Path

from scripts.config import LATEST_VERSION, version_to_short, version_to_title
from scripts.identity import CSS_LINKS, PROPERTY_NAME, copy_css, copy_host_files, load_fragments
from scripts.models import VersionEntry


def generate_versions_json(versions: list[str], output_dir: Path) -> Path:
    """Generate the versions.json manifest for the built-in version selector.

    Args:
        versions: List of version tags (e.g., ["v25.2.0", "v25.1.0", ...])
        output_dir: Root output directory for the site

    Returns:
        Path to the generated versions.json
    """
    entries = []
    for v in versions:
        short = version_to_short(v)
        title = version_to_title(v)
        aliases = ["latest"] if v == LATEST_VERSION else []
        entries.append(VersionEntry(version=short, title=title, aliases=aliases))

    output_path = output_dir / "versions.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps([asdict(e) for e in entries], indent=2) + "\n")

    return output_path


def generate_root_landing(output_dir: Path, versions: list[str]) -> Path:
    """Generate the root landing page with a visual version picker.

    The page reads every colour, font and easing through the vendored css derivation
    (``identity/css/``), which :func:`copy_identity_root_files` places beside it, and carries the
    host's head fragment, the lockup, the family links with this site marked current, the
    attribution sentence and the ownership line (FR-028). Both themes follow the visitor's system
    preference (FR-014).

    Args:
        output_dir: Root output directory for the site
        versions: Sorted list of version tags (newest first)

    Returns:
        Path to the generated index.html
    """
    latest_short = version_to_short(LATEST_VERSION)
    latest_title = version_to_title(LATEST_VERSION)
    fragments = load_fragments()
    css_links = "\n".join(f'<link rel="stylesheet" href="{href}">' for href in CSS_LINKS)

    # Build version cards HTML
    version_cards = []
    for i, v in enumerate(versions):
        short = version_to_short(v)
        title = version_to_title(v)
        is_latest = v == LATEST_VERSION
        badge = '<span class="badge">latest</span>' if is_latest else ""
        # Assign era labels
        major = int(title.split(".")[0])
        era = f"20{title[:2]}" if major >= 22 else f"v{major}"
        delay = i * 0.04
        version_cards.append(
            f'<a href="{short}/" class="card{" card--latest" if is_latest else ""}" '
            f'style="animation-delay:{delay:.2f}s">'
            f'<span class="card__version">{title}</span>'
            f'<span class="card__era">{era}</span>'
            f"{badge}</a>"
        )

    cards_html = "\n        ".join(version_cards)

    html = f"""\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="color-scheme" content="light dark">
<title>EnergyPlus docs, every version | idfkit</title>
<meta name="description" content="idfkit's rendering of the EnergyPlus documentation for every version (v8.9 through {latest_title}): Input/Output Reference, Engineering Reference, Getting Started guides and more, searchable and hyperlinked.">
<meta name="keywords" content="EnergyPlus, documentation, building energy simulation, HVAC, Input Output Reference, Engineering Reference, energy modeling, idfkit">
<link rel="canonical" href="https://docs.idfkit.com/">

<!-- idfkit identity: the css derivation, linked before this page's own stylesheet -->
{css_links}

<!-- idfkit identity: hosts/docs.idfkit.com/head.html, inlined by scripts/version_manager.py -->
{fragments.head}

<!-- Open Graph -->
<meta property="og:title" content="EnergyPlus docs, every version">
<meta property="og:description" content="idfkit's rendering of the EnergyPlus documentation for every version. Input/Output Reference, Engineering Reference and more, searchable and hyperlinked.">
<meta property="og:type" content="website">
<meta property="og:url" content="https://docs.idfkit.com/">
<meta property="og:site_name" content="idfkit">
<meta property="og:locale" content="en_US">

<!-- Twitter Card -->
<meta name="twitter:title" content="EnergyPlus docs, every version">
<meta name="twitter:description" content="idfkit's rendering of the EnergyPlus documentation for every version. Input/Output Reference, Engineering Reference and more.">

<!-- JSON-LD Structured Data -->
<script type="application/ld+json">
{{
  "@context": "https://schema.org",
  "@type": "WebSite",
  "name": "EnergyPlus docs",
  "url": "https://docs.idfkit.com/",
  "description": "idfkit's rendering of the EnergyPlus documentation for every version, searchable and hyperlinked.",
  "publisher": {{
    "@type": "Organization",
    "name": "idfkit",
    "url": "https://idfkit.com"
  }},
  "isPartOf": {{
    "@type": "WebSite",
    "name": "idfkit",
    "url": "https://idfkit.com"
  }}
}}
</script>

<style>
/* Every colour, font and easing below is a property of identity/css/tokens.css or fonts.css. */
*,*::before,*::after{{box-sizing:border-box;margin:0;padding:0}}
html{{height:100%}}
body{{
  min-height:100%;font-family:var(--idfkit-font-text);
  background:var(--idfkit-color-ground);color:var(--idfkit-color-ink);
  display:flex;flex-direction:column;align-items:center;overflow-x:hidden;
}}
a:focus-visible{{outline:2px solid var(--idfkit-color-focus);outline-offset:2px}}
.hero{{
  width:100%;padding:var(--idfkit-space-8) var(--idfkit-space-3) var(--idfkit-space-6);text-align:center;
  background:var(--idfkit-color-surface);border-bottom:1px solid var(--idfkit-color-border);
}}
.hero .idfkit-lockup{{--idfkit-lockup-mark:2rem}}
.rule{{
  width:var(--idfkit-space-8);height:4px;margin:var(--idfkit-space-3) auto 0;
  border-radius:var(--idfkit-radius-pill);background:var(--idfkit-gradient-brand);
}}
h1{{
  margin-top:var(--idfkit-space-3);font-size:clamp(2.25rem,6vw,4rem);
  font-weight:var(--idfkit-font-weight-extrabold);letter-spacing:-.03em;line-height:1.05;
}}
.subtitle{{
  margin-top:var(--idfkit-space-2);font-size:clamp(1rem,2vw,1.2rem);color:var(--idfkit-color-ink-muted);
  max-width:36rem;margin-inline:auto;line-height:1.6;
}}
.cta{{
  display:inline-flex;align-items:center;gap:var(--idfkit-space-1);
  margin-top:var(--idfkit-space-4);padding:.85rem 2rem;
  background:var(--idfkit-color-accent);color:var(--idfkit-color-accent-ink);
  font-weight:var(--idfkit-font-weight-semibold);font-size:1.05rem;border-radius:var(--idfkit-radius-md);
  text-decoration:none;box-shadow:var(--idfkit-elevation-raised);
  transition:transform var(--idfkit-motion-duration-fast) var(--idfkit-motion-ease-out-quart),
    box-shadow var(--idfkit-motion-duration-fast) var(--idfkit-motion-ease-out-quart);
}}
.cta:hover{{transform:translateY(-2px);box-shadow:var(--idfkit-elevation-overlay)}}
.cta svg{{width:20px;height:20px}}
main{{width:100%;max-width:52rem}}
.section-label{{
  margin-top:var(--idfkit-space-6);margin-bottom:var(--idfkit-space-3);
  font-family:var(--idfkit-font-code);font-size:.8rem;font-weight:var(--idfkit-font-weight-medium);
  letter-spacing:.15em;text-transform:uppercase;color:var(--idfkit-color-ink-label);text-align:center;
}}
.grid{{
  display:grid;grid-template-columns:repeat(auto-fill,minmax(130px,1fr));
  gap:var(--idfkit-space-2);width:100%;max-width:52rem;padding:0 var(--idfkit-space-3) var(--idfkit-space-8);
}}
.card{{
  position:relative;display:flex;flex-direction:column;align-items:center;justify-content:center;
  padding:var(--idfkit-space-3) var(--idfkit-space-1);border-radius:var(--idfkit-radius-md);
  background:var(--idfkit-color-surface);border:1px solid var(--idfkit-color-border);
  text-decoration:none;color:var(--idfkit-color-ink);
  transition:border-color var(--idfkit-motion-duration-fast) var(--idfkit-motion-ease-out-quart),
    background var(--idfkit-motion-duration-fast) var(--idfkit-motion-ease-out-quart),
    transform var(--idfkit-motion-duration-fast) var(--idfkit-motion-ease-out-quart),
    box-shadow var(--idfkit-motion-duration-fast) var(--idfkit-motion-ease-out-quart);
  animation:fadeUp var(--idfkit-motion-duration-slow) var(--idfkit-motion-ease-out-expo) both;
}}
.card:hover{{
  border-color:var(--idfkit-color-accent);background:var(--idfkit-color-surface-raised);
  transform:translateY(-3px);box-shadow:var(--idfkit-elevation-overlay);
}}
.card--latest{{border-color:var(--idfkit-color-status-success)}}
.card--latest:hover{{border-color:var(--idfkit-color-status-success)}}
.card__version{{
  font-family:var(--idfkit-font-code);font-size:1.3rem;font-weight:var(--idfkit-font-weight-bold);
  font-variant-numeric:tabular-nums;
}}
.card__era{{font-size:.7rem;color:var(--idfkit-color-ink-label);margin-top:var(--idfkit-space-half);letter-spacing:.05em}}
.badge{{
  position:absolute;top:-.5rem;right:-.5rem;
  background:var(--idfkit-color-status-success);color:var(--idfkit-color-ground);
  font-size:.55rem;font-weight:var(--idfkit-font-weight-bold);text-transform:uppercase;letter-spacing:.08em;
  padding:.2rem .5rem;border-radius:var(--idfkit-radius-sm);
}}
footer{{
  padding:var(--idfkit-space-4) var(--idfkit-space-3);text-align:center;font-size:.8rem;
  color:var(--idfkit-color-ink-muted);border-top:1px solid var(--idfkit-color-border);
  width:100%;margin-top:auto;
}}
.idfkit-family{{display:flex;flex-wrap:wrap;justify-content:center;gap:var(--idfkit-space-1) var(--idfkit-space-2)}}
.idfkit-family a{{color:var(--idfkit-color-link);text-decoration:none}}
.idfkit-family a:hover{{text-decoration:underline}}
.idfkit-family a[aria-current="page"]{{color:var(--idfkit-color-ink);font-weight:var(--idfkit-font-weight-semibold)}}
.idfkit-attribution{{margin:var(--idfkit-space-2) auto 0;max-width:40rem;line-height:1.5}}
.idfkit-ownership{{margin-top:var(--idfkit-space-1);color:var(--idfkit-color-ink-label)}}
@keyframes fadeUp{{
  from{{opacity:0;transform:translateY(12px)}}
  to{{opacity:1;transform:translateY(0)}}
}}
</style>
</head>
<body>
  <header class="hero">
    <a class="idfkit-lockup" href="https://idfkit.com" aria-label="idfkit {PROPERTY_NAME}"></a>
    <div class="rule" aria-hidden="true"></div>
    <h1>EnergyPlus documentation</h1>
    <p class="subtitle">
      Whole-building energy simulation. Every version, every reference, one place.
    </p>
    <a href="{latest_short}/" class="cta">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"
           stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
        <path d="M13 5l7 7-7 7M5 12h14"/>
      </svg>
      Open {latest_title}
    </a>
  </header>

  <main>
    <h2 class="section-label">All versions</h2>
    <div class="grid">
    {cards_html}
    </div>
  </main>

  <footer>
    {fragments.family_links}
    {fragments.attribution}
    {fragments.ownership}
  </footer>
</body>
</html>
"""
    output_path = output_dir / "index.html"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html)

    return output_path


def copy_identity_root_files(deploy_dir: Path) -> None:
    """Place the css derivation and the host's files where the picker and head.html point."""
    copy_css(deploy_dir)
    copy_host_files(deploy_dir)


def generate_robots_txt(output_dir: Path) -> Path:
    """Generate robots.txt for the documentation site.

    Args:
        output_dir: Root output directory for the site

    Returns:
        Path to the generated robots.txt
    """
    content = """\
User-agent: *
Allow: /

Sitemap: https://docs.idfkit.com/sitemap.xml
"""
    output_path = output_dir / "robots.txt"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(content)
    return output_path


def generate_sitemap(output_dir: Path, versions: list[str]) -> Path:
    """Generate a sitemap.xml listing the root and all version landing pages.

    Individual version sub-sitemaps (if generated by Zensical) are referenced
    via a sitemap index.  This function always generates at minimum the
    top-level version landing pages.

    Args:
        output_dir: Root output directory for the site
        versions: Sorted list of version tags (newest first)

    Returns:
        Path to the generated sitemap.xml
    """
    from datetime import date

    today = date.today().isoformat()
    latest_short = version_to_short(LATEST_VERSION)

    urls = []
    # Root page
    urls.append(
        f"  <url>\n"
        f"    <loc>https://docs.idfkit.com/</loc>\n"
        f"    <lastmod>{today}</lastmod>\n"
        f"    <changefreq>monthly</changefreq>\n"
        f"    <priority>1.0</priority>\n"
        f"  </url>"
    )

    for v in versions:
        short = version_to_short(v)
        priority = "0.9" if short == latest_short else "0.5"
        urls.append(
            f"  <url>\n"
            f"    <loc>https://docs.idfkit.com/{short}/</loc>\n"
            f"    <lastmod>{today}</lastmod>\n"
            f"    <changefreq>monthly</changefreq>\n"
            f"    <priority>{priority}</priority>\n"
            f"  </url>"
        )

        # Check for per-version sitemap generated by Zensical
        version_sitemap = output_dir / short / "sitemap.xml"
        if version_sitemap.exists():
            # Include entries from the per-version sitemap
            import xml.etree.ElementTree as ET

            try:
                tree = ET.parse(version_sitemap)  # noqa: S314 - trusted build output
                ns = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
                for url_el in tree.findall(".//sm:url", ns):
                    loc_el = url_el.find("sm:loc", ns)
                    if loc_el is not None and loc_el.text:
                        loc = loc_el.text
                        # Rewrite relative URLs to absolute
                        if not loc.startswith("http"):
                            loc = f"https://docs.idfkit.com/{short}/{loc.lstrip('/')}"
                        urls.append(
                            f"  <url>\n"
                            f"    <loc>{loc}</loc>\n"
                            f"    <lastmod>{today}</lastmod>\n"
                            f"    <changefreq>monthly</changefreq>\n"
                            f"    <priority>{priority}</priority>\n"
                            f"  </url>"
                        )
            except ET.ParseError as e:
                print(f"Warning: Could not parse {version_sitemap}: {e}")

    sitemap = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n' + "\n".join(urls) + "\n</urlset>\n"
    )

    output_path = output_dir / "sitemap.xml"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(sitemap)
    return output_path


def _version_sort_key(v: str) -> tuple[int, ...]:
    """Parse a version tag into a sortable tuple of ints."""
    return tuple(int(x) for x in v.lstrip("v").split("."))


def _discover_versions(deploy_dir: Path) -> list[str]:
    """Scan deploy_dir for v* directories and return full version tags, newest first."""
    versions: list[str] = []
    for d in deploy_dir.iterdir():
        if d.is_dir() and re.match(r"^v\d+\.\d+$", d.name):
            # Convert short form (v25.2) back to full tag (v25.2.0)
            versions.append(f"{d.name}.0")
    return sorted(versions, key=_version_sort_key, reverse=True)


def deploy_single_version(version: str, build_dir: Path, deploy_dir: Path) -> None:
    """Copy one version's built site to the deployment directory and regenerate root files.

    Args:
        version: Full version tag (e.g., "v25.2.0")
        build_dir: The version's build directory (containing a site/ subdirectory)
        deploy_dir: Root deployment directory (e.g., dist/)
    """
    short = version_to_short(version)
    site_dir = build_dir / "site"
    if not site_dir.exists():
        site_dir = build_dir

    target = deploy_dir / short
    if target.exists():
        shutil.rmtree(target)
    deploy_dir.mkdir(parents=True, exist_ok=True)
    shutil.copytree(site_dir, target)

    # Regenerate root files for all versions currently in dist/
    versions = _discover_versions(deploy_dir)
    copy_identity_root_files(deploy_dir)
    generate_versions_json(versions, deploy_dir)
    generate_root_landing(deploy_dir, versions)
    generate_robots_txt(deploy_dir)
    generate_sitemap(deploy_dir, versions)


def merge_version_outputs(
    version_build_dirs: dict[str, Path],
    deploy_dir: Path,
) -> None:
    """Merge individual version build outputs into the final deployment directory.

    Args:
        version_build_dirs: Mapping of version tag -> build output directory
                            (each containing a site/ subdirectory from zensical build)
        deploy_dir: Final deployment directory
    """
    deploy_dir.mkdir(parents=True, exist_ok=True)

    for version, build_dir in version_build_dirs.items():
        short = version_to_short(version)
        site_dir = build_dir / "site"

        if not site_dir.exists():
            site_dir = build_dir

        target = deploy_dir / short
        if target.exists():
            shutil.rmtree(target)
        shutil.copytree(site_dir, target)

    # Generate versions.json, landing page, robots.txt, and sitemap (newest first)
    versions = sorted(version_build_dirs.keys(), key=_version_sort_key, reverse=True)
    copy_identity_root_files(deploy_dir)
    generate_versions_json(versions, deploy_dir)
    generate_root_landing(deploy_dir, versions)
    generate_robots_txt(deploy_dir)
    generate_sitemap(deploy_dir, versions)
