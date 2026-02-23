"""Version manifest generation for the EnergyPlus documentation site.

Generates:
- versions.json: Manifest read by Zensical's built-in version selector
- Root index.html: Redirect to the latest version
"""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from scripts.config import LATEST_VERSION, version_to_short, version_to_title
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

    Args:
        output_dir: Root output directory for the site
        versions: Sorted list of version tags (newest first)

    Returns:
        Path to the generated index.html
    """
    latest = versions[0] if versions else LATEST_VERSION
    latest_short = version_to_short(latest)
    latest_title = version_to_title(latest)

    # Build version cards HTML
    version_cards = []
    for i, v in enumerate(versions):
        short = version_to_short(v)
        title = version_to_title(v)
        is_latest = v == latest
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
<title>EnergyPlus Documentation</title>
<style>
*,*::before,*::after{{box-sizing:border-box;margin:0;padding:0}}
:root{{
  --bg:#0a0e1a;--surface:#131829;--border:#1e2640;
  --text:#e2e8f0;--dim:#64748b;--accent:#f59e0b;
  --glow:rgba(245,158,11,.12);--latest:#22c55e;
}}
html{{height:100%}}
body{{
  min-height:100%;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;
  background:var(--bg);color:var(--text);display:flex;flex-direction:column;
  align-items:center;overflow-x:hidden;
}}
.hero{{
  width:100%;padding:4rem 2rem 2rem;text-align:center;
  background:linear-gradient(180deg,#111827 0%,var(--bg) 100%);
  position:relative;overflow:hidden;
}}
.hero::before{{
  content:"";position:absolute;inset:0;
  background:radial-gradient(ellipse 60% 50% at 50% 0%,rgba(245,158,11,.08),transparent);
  pointer-events:none;
}}
.logo{{
  font-size:clamp(1rem,2vw,1.2rem);letter-spacing:.35em;text-transform:uppercase;
  color:var(--accent);font-weight:700;margin-bottom:1rem;
}}
h1{{
  font-size:clamp(2.5rem,6vw,4.5rem);font-weight:800;
  letter-spacing:-.03em;line-height:1.05;
  background:linear-gradient(135deg,#fff 0%,#94a3b8 100%);
  -webkit-background-clip:text;-webkit-text-fill-color:transparent;
  background-clip:text;
}}
.subtitle{{
  margin-top:1rem;font-size:clamp(1rem,2vw,1.25rem);color:var(--dim);
  max-width:540px;margin-inline:auto;line-height:1.6;
}}
.cta{{
  display:inline-flex;align-items:center;gap:.5rem;
  margin-top:2rem;padding:.85rem 2rem;
  background:var(--accent);color:#0a0e1a;
  font-weight:700;font-size:1.05rem;border-radius:10px;
  text-decoration:none;transition:all .2s;
  box-shadow:0 0 30px rgba(245,158,11,.25);
}}
.cta:hover{{transform:translateY(-2px);box-shadow:0 0 40px rgba(245,158,11,.4)}}
.cta svg{{width:20px;height:20px}}
.section-label{{
  margin-top:3.5rem;margin-bottom:1.5rem;
  font-size:.8rem;letter-spacing:.2em;text-transform:uppercase;
  color:var(--dim);text-align:center;
}}
.grid{{
  display:grid;grid-template-columns:repeat(auto-fill,minmax(130px,1fr));
  gap:.75rem;width:100%;max-width:820px;padding:0 2rem 4rem;
}}
.card{{
  position:relative;display:flex;flex-direction:column;align-items:center;justify-content:center;
  padding:1.25rem .75rem;border-radius:12px;
  background:var(--surface);border:1px solid var(--border);
  text-decoration:none;color:var(--text);
  transition:all .2s;
  animation:fadeUp .5s ease both;
}}
.card:hover{{
  border-color:var(--accent);background:#1a2035;
  transform:translateY(-3px);
  box-shadow:0 8px 30px rgba(0,0,0,.3),0 0 0 1px var(--accent);
}}
.card--latest{{border-color:rgba(34,197,94,.3);background:#0f1f15}}
.card--latest:hover{{border-color:var(--latest);box-shadow:0 8px 30px rgba(0,0,0,.3),0 0 0 1px var(--latest)}}
.card__version{{font-size:1.35rem;font-weight:700;font-variant-numeric:tabular-nums}}
.card__era{{font-size:.7rem;color:var(--dim);margin-top:.25rem;letter-spacing:.05em}}
.badge{{
  position:absolute;top:-.45rem;right:-.45rem;
  background:var(--latest);color:#fff;
  font-size:.55rem;font-weight:700;text-transform:uppercase;letter-spacing:.08em;
  padding:.2rem .5rem;border-radius:6px;
}}
footer{{
  padding:2rem;text-align:center;font-size:.8rem;color:var(--dim);
  border-top:1px solid var(--border);width:100%;margin-top:auto;
}}
footer a{{color:var(--accent);text-decoration:none}}
footer a:hover{{text-decoration:underline}}
@keyframes fadeUp{{
  from{{opacity:0;transform:translateY(12px)}}
  to{{opacity:1;transform:translateY(0)}}
}}
</style>
</head>
<body>
  <div class="hero">
    <div class="logo">EnergyPlus</div>
    <h1>Documentation</h1>
    <p class="subtitle">
      Whole-building energy simulation. Every version, every reference, one place.
    </p>
    <a href="{latest_short}/" class="cta">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"
           stroke-linecap="round" stroke-linejoin="round">
        <path d="M13 5l7 7-7 7M5 12h14"/>
      </svg>
      Open {latest_title}
    </a>
  </div>

  <div class="section-label">All versions</div>

  <div class="grid">
    {cards_html}
  </div>

  <footer>
    Built with <a href="https://zensical.org">Zensical</a> &middot;
    EnergyPlus is a trademark of the US Department of Energy
  </footer>
</body>
</html>
"""
    output_path = output_dir / "index.html"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html)

    return output_path


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
    import shutil

    deploy_dir.mkdir(parents=True, exist_ok=True)

    for version, build_dir in version_build_dirs.items():
        short = version_to_short(version)
        site_dir = build_dir / "site"

        if not site_dir.exists():
            # Try the build dir itself if site/ doesn't exist
            site_dir = build_dir

        target = deploy_dir / short
        if target.exists():
            shutil.rmtree(target)
        shutil.copytree(site_dir, target)

    # Generate versions.json and landing page
    versions = sorted(version_build_dirs.keys(), reverse=True)
    generate_versions_json(versions, deploy_dir)
    generate_root_landing(deploy_dir, versions)
