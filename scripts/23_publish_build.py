#!/usr/bin/env python3
"""
Step 21 - build a publishable static site for the atlas.

Produces docs/, which GitHub Pages serves directly and which can equally be
uploaded to any static host.

IMPORTANT - what is deliberately removed before publication:

The working GeoPackage's `riparian_parcels` layer carries **owner names and
home mailing addresses for eleven named private individuals**, taken from
county assessment records. Those records are public, and looking one up to
write and ask a landowner for permission is a normal, proportionate thing to
do. **Republishing them, aggregated, on the open web, in a dataset captioned
"riverbank you might want to camp on", is a different act.** It changes the
cost of finding them from "visit the county office" to "one search", and the
people concerned never chose to be in a public dataset about a stranger's
expedition.

So the public build keeps the parcel identifier, county, municipality and
river mile - everything a third party needs to do their own lookup through
the proper channel - and drops the name and address columns. The full version
stays local for the trip's own use.

Outputs
  docs/index.html
  docs/allegheny_river_atlas.gpkg      public build, no personal data
  docs/DATA_DICTIONARY.md
  docs/LICENSE.txt
  docs/CNAME.example
"""
from __future__ import annotations

import datetime as dt
import shutil
import sys
from pathlib import Path

import geopandas as gpd
import pandas as pd
import pyogrio

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common
import config

DOCS = config.ROOT / "docs"
SRC_GPKG = config.OUT / "allegheny_river_atlas.gpkg"
PUB_GPKG = DOCS / "allegheny_river_atlas.gpkg"
REDACT = {"owner", "owner_address"}
TODAY = dt.date.today().isoformat()


def build_public_gpkg() -> list[tuple[str, int, str]]:
    DOCS.mkdir(exist_ok=True)
    if PUB_GPKG.exists():
        PUB_GPKG.unlink()
    layers = [str(n) for n in pyogrio.list_layers(SRC_GPKG)[:, 0]]
    written, first, redacted = [], True, 0
    for name in layers:
        g = gpd.read_file(SRC_GPKG, layer=name)
        drop = [c for c in g.columns if c in REDACT]
        if drop:
            g = g.drop(columns=drop)
            redacted += 1
            g["owner_lookup"] = (
                "Owner of record not republished. Take the parcel_id to the "
                "county assessment office named in `lookup`.")
        spatial = (isinstance(g, gpd.GeoDataFrame)
                   and g.geometry is not None
                   and g.geometry.notna().any())
        if spatial:
            g.to_file(PUB_GPKG, layer=name, driver="GPKG",
                      mode="w" if first else "a")
            first = False
            written.append((name, len(g), g.geometry.geom_type.iloc[0]))
        else:
            flat = pd.DataFrame(g).drop(
                columns=[c for c in ("geometry",) if c in g.columns])
            pyogrio.write_dataframe(flat, PUB_GPKG, layer=name,
                                    append=not first)
            first = False
            written.append((name, len(g), "table"))
    print(f"  public GeoPackage: {len(written)} layers, "
          f"{redacted} layer(s) redacted, "
          f"{PUB_GPKG.stat().st_size / 1024 / 1024:.1f} MB")
    return written


def main() -> None:
    common.banner("STEP 21 - build the publishable site")
    written = build_public_gpkg()

    shutil.copy(config.OUT / "DATA_DICTIONARY.md", DOCS / "DATA_DICTIONARY.md")

    (DOCS / "LICENSE.txt").write_text(f"""Allegheny River Atlas
Compiled {TODAY} by Michael Perry.

THE COMPILATION
The derived layers in this package - camping legality, measured public-land
frontage, traverse mode, water quality extents, fishing regulation extents,
drone restrictions and county extents along the river - are released under
CC BY 4.0. Use them, change them, build on them; credit the compilation.

THE SOURCES
Underlying data remains under its own terms and must be attributed:

  USGS - NHDPlus High Resolution, NWIS, The National Map, 3DEP
         US Government work, public domain
  US EPA - ATTAINS assessed waters
         US Government work, public domain
  USDA Forest Service - EDW ownership, wilderness, recreation sites
         US Government work, public domain
  PA Fish & Boat Commission, PA DCNR, PA Game Commission
         via PASDA (Pennsylvania Spatial Data Access) - attribution required
  NYSDEC - state land, parks, tax parcels, tribal territory boundary
  County assessment offices - parcel identifiers
  OpenStreetMap contributors - campgrounds and the Kinzua portage route
         Open Database License (ODbL) - share-alike applies to these layers

NOT INCLUDED
Owner names and mailing addresses from county assessment records are
deliberately excluded from this public release. Parcel identifiers are
included so anyone may make their own enquiry through the county office.

NO WARRANTY
Camping legality classifications are an interpretation of published rules,
not an agency determination. Flow-derived layers are median estimates, not
measurements or forecasts. Verify anything you intend to rely on with the
responsible agency or nation before acting on it.
""", encoding="utf-8")

    (DOCS / "CNAME.example").write_text(
        "allegheny.michaelperry.org\n", encoding="utf-8")

    rows = "\n".join(
        f'      <tr><td><code>{n}</code></td><td class="n">{c}</td>'
        f'<td>{t}</td></tr>' for n, c, t in written)
    size_mb = PUB_GPKG.stat().st_size / 1024 / 1024

    (DOCS / "index.html").write_text(f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Allegheny River Atlas</title>
<meta name="description" content="An open GIS dataset of the Allegheny River
from its source in Potter County to Pittsburgh: camping legality, public-land
frontage, water quality and access, by river mile.">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600&family=IBM+Plex+Mono:wght@400;500&display=swap">
<style>
:root{{--ground:#f6f5f1;--panel:#fffefb;--ink:#1b2023;--ink2:#5f6a70;
--ink3:#8d979c;--rule:#dedbd3;--water:#2d6b7c;--ok:#3e7a4b;--warn:#a6433b;}}
@media (prefers-color-scheme:dark){{:root{{--ground:#15181b;--panel:#1c2125;
--ink:#e8e6e0;--ink2:#a3adb2;--ink3:#6f797e;--rule:#2c3338;--water:#6ba8ba;
--ok:#6aa878;--warn:#d9756b;}}}}
*{{box-sizing:border-box}}
body{{margin:0;background:var(--ground);color:var(--ink);
font-family:"IBM Plex Sans",ui-sans-serif,system-ui,sans-serif;
font-size:16px;line-height:1.6}}
.wrap{{max-width:820px;margin:0 auto;padding:0 16px}}
header{{border-bottom:1px solid var(--rule);background:var(--panel);
padding-block:48px 36px}}
h1{{font-size:clamp(28px,5vw,40px);margin:0 0 10px;letter-spacing:-.02em;
text-wrap:balance}}
.sub{{color:var(--ink2);font-size:18px;margin:0;max-width:60ch}}
.mono{{font-family:"IBM Plex Mono",ui-monospace,monospace;
font-variant-numeric:tabular-nums}}
h2{{font-size:22px;margin:40px 0 12px;letter-spacing:-.01em}}
h3{{font-size:17px;margin:26px 0 8px}}
p,li{{max-width:65ch}}
.dl{{display:flex;flex-wrap:wrap;gap:12px;margin:24px 0 8px}}
.btn{{display:inline-flex;flex-direction:column;gap:2px;padding:14px 18px;
border-radius:8px;text-decoration:none;border:1px solid var(--rule);
background:var(--panel);color:var(--ink)}}
.btn.primary{{background:var(--water);color:#fff;border-color:var(--water)}}
.btn b{{font-size:15px;font-weight:600}}
.btn span{{font-size:12.5px;opacity:.8}}
.tw{{overflow-x:auto;-webkit-overflow-scrolling:touch}}
table{{border-collapse:collapse;width:100%;font-size:14px;margin:12px 0;
min-width:340px}}
th,td{{text-align:left;padding:7px 10px;border-bottom:1px solid var(--rule)}}
th{{font-size:11px;text-transform:uppercase;letter-spacing:.08em;
color:var(--ink3);font-weight:600}}
td.n{{text-align:right;font-family:"IBM Plex Mono",monospace}}
code{{font-family:"IBM Plex Mono",monospace;font-size:.9em;
background:var(--rule);padding:1px 5px;border-radius:4px;
overflow-wrap:anywhere;word-break:break-word}}
pre{{overflow-x:auto;background:var(--rule);padding:12px 14px;border-radius:6px;
font-size:13px;margin:12px 0}}
pre code{{background:none;padding:0}}
.note{{border-left:3px solid var(--warn);padding:2px 0 2px 16px;
color:var(--ink2);margin:20px 0}}
.stats{{display:flex;flex-wrap:wrap;gap:28px;margin:20px 0 0}}
.stat b{{display:block;font-size:24px;font-family:"IBM Plex Mono",monospace}}
.stat span{{font-size:11px;text-transform:uppercase;letter-spacing:.07em;
color:var(--ink3)}}
footer{{margin-top:56px;border-top:1px solid var(--rule);padding-block:28px 56px;
color:var(--ink3);font-size:13.5px}}
a{{color:var(--water)}}
</style>
</head>
<body>
<header><div class="wrap">
  <h1>Allegheny River Atlas</h1>
  <p class="sub">An open GIS dataset of the Allegheny River from its source in
  Potter County, Pennsylvania to the Point at Pittsburgh — camping legality,
  public-land frontage, water quality and access, indexed by river mile.</p>
  <div class="stats">
    <div class="stat"><b>312</b><span>river miles</span></div>
    <div class="stat"><b>{len(written)}</b><span>layers</span></div>
    <div class="stat"><b>0.049</b><span>mi index error</span></div>
    <div class="stat"><b>{size_mb:.1f}</b><span>MB</span></div>
  </div>
</div></header>

<div class="wrap">
  <div class="dl">
    <a class="btn primary" href="allegheny_river_atlas.gpkg" download>
      <b>Download the GeoPackage</b><span>{size_mb:.1f} MB · EPSG:4326 ·
      opens in QGIS</span></a>
    <a class="btn" href="DATA_DICTIONARY.md"><b>Data dictionary</b>
      <span>Layers, fields, provenance, limits</span></a>
    <a class="btn" href="LICENSE.txt"><b>Licence &amp; attribution</b>
      <span>CC BY 4.0 compilation</span></a>
  </div>

  <h2>What this is</h2>
  <p>The Allegheny is well mapped as a <em>line</em> and poorly mapped as a
  <em>place you are allowed to be</em>. This dataset answers the second
  question. It was compiled while planning a source-to-mouth descent, and the
  planning turned out to be less interesting than what the data said about
  public access to an American river.</p>

  <p>Three findings drove the rest of it:</p>
  <ul>
    <li><b>Only about 12% of the river has legal public dispersed
    camping.</b> Three separate stretches longer than 25 miles have none of
    any kind reachable from the water — the longest runs 107 miles.</li>
    <li><b>Inside the Allegheny National Forest proclamation boundary, less
    than half the river frontage is actually federal land.</b> Of 94 frontage
    miles, 44 are federal and 50 are private inholdings that read as National
    Forest on a general-purpose map.</li>
    <li><b>Roughly 175 river miles — over half the route — carry a “Not
    Supporting” water-quality status</b> in EPA ATTAINS.</li>
  </ul>

  <h2>The river-mile convention</h2>
  <p>Everything is keyed to <b>river mile 0.0 at the mouth, increasing
  upstream</b>, the USACE Allegheny navigation convention. Coudersport is
  RM 312.2. Every layer carries a <code>river_mile</code>, or an upstream and
  downstream pair, so any two layers join on position without a spatial
  operation.</p>
  <p>The centerline is the USGS NHDPlus High Resolution mainstem — 652
  flowlines on one level path with an unbroken node chain, measured
  geodesically. It validates against NHD’s own mapped lock chambers to a
  <b>mean absolute deviation of 0.049 mile</b>.</p>

  <h2>Layers</h2>
  <div class="tw"><table>
    <thead><tr><th>Layer</th><th>Features</th><th>Geometry</th></tr></thead>
    <tbody>
{rows}
    </tbody>
  </table></div>
  <p>Seven of those exist nowhere else. They were river-mile span tables —
  the analytical output — cut from the centerline into real geometry so they
  can be mapped and intersected: camping legality, measured public-land
  frontage, traverse mode, water quality, fishing regulations, drone
  restrictions and county extents.</p>

  <h2>What is deliberately not here</h2>
  <div class="note">
    <p>The working dataset identifies riparian parcels for stretches with no
    lawful public campsite, and for two counties those records carry owner
    names and home mailing addresses. <b>Those are not republished here.</b>
    They are public records, and looking one up to write and ask a landowner
    for permission is proportionate. Aggregating them onto the open web
    under a heading about where to camp is not.</p>
    <p>Parcel identifiers, county and municipality are included, so anyone
    can make their own enquiry through the county assessment office.</p>
  </div>

  <h2>Use it</h2>
  <p>Drag the <code>.gpkg</code> into QGIS. Or:</p>
  <pre><code>gpd.read_file("allegheny_river_atlas.gpkg",
             layer="river_camping_legality")</code></pre>
  <p>Camping classifications are an interpretation of published rules, not an
  agency determination. Flow layers are median estimates, not measurements.
  34.8 miles run through the Seneca Nation’s Allegany Territory, where the
  Nation — not a state agency — is the authority. Verify anything you intend
  to rely on.</p>

  <footer>
    <p>Compiled {TODAY}. Sources: USGS · US EPA · USDA Forest Service ·
    PA Fish &amp; Boat Commission, PA DCNR and PA Game Commission via PASDA ·
    NYSDEC · county assessment offices · OpenStreetMap contributors (ODbL).</p>
    <p>Compilation released under CC BY 4.0. Underlying data remains under
    its own terms.</p>
  </footer>
</div>
</body>
</html>
""", encoding="utf-8")

    for f in sorted(DOCS.iterdir()):
        print(f"    docs/{f.name:<34} {f.stat().st_size / 1024:8.1f} KB")
    print(f"\n  site ready in docs/ — GitHub Pages serves this directly, "
          f"or upload it anywhere static")


if __name__ == "__main__":
    main()
