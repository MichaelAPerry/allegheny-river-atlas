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
  docs/index.html                      with an inline SVG plan map and river-mile strip
  docs/map.html                        the full interactive map, self-contained
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
import sitesvg

DOCS = config.ROOT / "docs"
SRC_GPKG = config.OUT / "allegheny_river_atlas.gpkg"
PUB_GPKG = DOCS / "allegheny_river_atlas.gpkg"
REDACT = {"owner", "owner_address"}
TODAY = dt.date.today().isoformat()


LEGEND = """\
    <div class="leg">
      <div class="grp"><h4>In-channel mode, July median flow</h4>
        <div class="row"><i class="ln" style="background:var(--m-float)"></i>
          Floatable<span class="mi">{float_mi:.0f} mi</span></div>
        <div class="row"><i class="ln" style="background:var(--m-wade)"></i>
          Wadeable<span class="mi">{wade_mi:.1f} mi</span></div>
        <div class="row"><i class="ln" style="background:var(--m-drag)"></i>
          Below wading flow<span class="mi">{drag_mi:.1f} mi</span></div>
      </div>
      <div class="grp"><h4>Public land</h4>
        <div class="row"><i class="sw" style="background:var(--l-nf)"></i>
          National Forest</div>
        <div class="row"><i class="sw" style="background:var(--l-wild)"></i>
          Designated Wilderness</div>
        <div class="row"><i class="sw" style="background:var(--l-sf)"></i>
          State Forest</div>
        <div class="row"><i class="sw" style="background:var(--l-sgl)"></i>
          State Game Land</div>
        <div class="row"><i class="sw" style="background:var(--l-sp)"></i>
          State Park</div>
        <div class="row"><i class="sw" style="background:var(--l-trb)"></i>
          Seneca Nation, Allegany Territory</div>
      </div>
      <div class="grp"><h4>On the water</h4>
        <div class="row"><i class="dot" style="background:var(--m-drag)"></i>
          Kinzua Dam — portage, RM {kinzua_rm:.0f}</div>
        <div class="row"><i class="dot" style="background:var(--ink3)"></i>
          Lock &amp; Dam — {locks}, free to pass</div>
        <div class="row"><i class="dot" style="background:none;
          box-shadow:inset 0 0 0 2px var(--m-float)"></i>
          First floatable public put-in</div>
      </div>
    </div>"""


def build_trail_rows(trails) -> str:
    """One row per stewarded reach: who to ring, and what to read first."""
    out = []
    for _, r in trails.iterrows():
        tag = ("" if r["designated"] else
               '<br><span class="q">promoted route, not a designated '
               'trail</span>')
        co = (f'<br><span class="q">with {r["cosponsor"]} · '
              f'{r["cosponsor_phone"]}</span>' if r["cosponsor"] else "")
        host = (str(r["guide_url"]).split("//")[-1].split("/")[0]
                .replace("www.", ""))
        out.append(
            f'      <tr><td class="n">{r["rm_hi"]:.0f}–{r["rm_lo"]:.0f}'
            f'<br><span class="q">{r["span_mi"]:.0f} mi</span></td>'
            f'<td>{r["name"]}{tag}</td>'
            f'<td>{r["steward"]}{co}</td>'
            f'<td class="mono"><a href="tel:{r["steward_phone"]}">'
            f'{r["steward_phone"]}</a></td>'
            f'<td><a href="{r["guide_url"]}" rel="noopener">{host}</a></td>'
            f'</tr>')
    return "\n".join(out)


def describe_trail_gaps() -> str:
    """The unstewarded reaches, named by the towns that bracket them."""
    import pandas as _pd
    g = _pd.read_csv(config.PROC / "water_trail_gaps.csv")
    parts = [f'RM&nbsp;{r["rm_hi"]:.0f}–{r["rm_lo"]:.0f}'
             for _, r in g.iterrows()]
    if len(parts) > 1:
        return ", ".join(parts[:-1]) + " and " + parts[-1]
    return parts[0] if parts else "none"


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

    # The interactive map is already self-contained - no tiles, no images,
    # no external requests - so it drops onto a static host unchanged. The one
    # thing it lacks as a standalone file is a way back, which only exists once
    # it sits beside index.html, so the link is added on the way in.
    m = (config.OUT / "map.html").read_text(encoding="utf-8")
    back = ('<a class="back" href="./">&larr; Atlas</a>\n'
            '    <h1>Allegheny Descent</h1>')
    assert "<h1>Allegheny Descent</h1>" in m
    m = m.replace("<h1>Allegheny Descent</h1>", back, 1)
    m = m.replace(".head .sub{",
                  ".head .back{color:var(--ink-2);text-decoration:none;"
                  "font-size:12.5px;border:1px solid var(--rule);"
                  "border-radius:6px;padding:4px 9px;white-space:nowrap}\n"
                  ".head .back:hover{color:var(--ink);border-color:var(--ink-3)}\n"
                  ".head .sub{", 1)
    (DOCS / "map.html").write_text(m, encoding="utf-8")

    print("  drawing the landing-page figures ...")
    figs = sitesvg.build()
    f = figs["facts"]
    legend = LEGEND.format(**f)
    trail_rows = build_trail_rows(figs["trails"])
    gap_list = describe_trail_gaps()


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
--ink3:#8d979c;--rule:#dedbd3;--water:#2d6b7c;--ok:#3e7a4b;--warn:#a6433b;
--band:#e7e4dc;--m-float:#2d6b7c;--m-wade:#bf8a2c;--m-drag:#a6433b;
--l-nf:#dde7d9;--l-wild:#c3d8bd;--l-sf:#e4ebe0;--l-sgl:#ece7d4;
--l-sp:#d9e7ea;--l-trb:#eddfe6;--camp:#3e7a4b;--trb:#8d6a86;
--cty-pa:#dcd8ce;--cty-ny:#cfd6d8;--trail:#3f6f86;--trail-soft:#a9c2cd;}}
@media (prefers-color-scheme:dark){{:root{{--ground:#15181b;--panel:#1c2125;
--ink:#e8e6e0;--ink2:#a3adb2;--ink3:#6f797e;--rule:#2c3338;--water:#6ba8ba;
--ok:#6aa878;--warn:#d9756b;
--band:#232a2f;--m-float:#6ba8ba;--m-wade:#d9a441;--m-drag:#d9756b;
--l-nf:#1e2a22;--l-wild:#28392b;--l-sf:#222c25;--l-sgl:#2b2a22;
--l-sp:#1e2a2d;--l-trb:#2c2129;--camp:#6aa878;--trb:#a4809c;
--cty-pa:#272d31;--cty-ny:#20292d;--trail:#4d8098;--trail-soft:#33505e;}}}}
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
td.n{{text-align:right;font-family:"IBM Plex Mono",monospace;white-space:nowrap}}
.q{{color:var(--ink3);font-size:11.5px}}
td.mono{{font-family:"IBM Plex Mono",monospace;white-space:nowrap}}
code{{font-family:"IBM Plex Mono",monospace;font-size:.9em;
background:var(--rule);padding:1px 5px;border-radius:4px;
overflow-wrap:anywhere;word-break:break-word}}
pre{{overflow-x:auto;background:var(--rule);padding:12px 14px;border-radius:6px;
font-size:13px;margin:12px 0}}
pre code{{background:none;padding:0}}
.stats{{display:flex;flex-wrap:wrap;gap:28px;margin:20px 0 0}}
.stat b{{display:block;font-size:24px;font-family:"IBM Plex Mono",monospace}}
.stat span{{font-size:11px;text-transform:uppercase;letter-spacing:.07em;
color:var(--ink3)}}
footer{{margin-top:56px;border-top:1px solid var(--rule);padding-block:28px 56px;
color:var(--ink3);font-size:13.5px}}
a{{color:var(--water)}}

/* figures - inline SVG, no images, no scripts, no external requests */
figure{{margin:30px 0 0}}
.figwrap{{background:var(--panel);border:1px solid var(--rule);
border-radius:10px;padding:16px 16px 12px}}
.fig{{display:block;width:100%;height:auto;overflow:visible}}
.scrollx{{overflow-x:auto;-webkit-overflow-scrolling:touch}}
@media (max-width:880px){{.scrollx .strip{{min-width:860px}}}}
.plan{{max-width:520px;margin:0 auto}}
figcaption{{color:var(--ink2);font-size:13.5px;margin-top:10px;
padding-top:10px;border-top:1px solid var(--rule);max-width:none}}
.figh{{margin:0 0 10px;font-size:15px;letter-spacing:.01em}}
.heroGrid{{display:grid;grid-template-columns:1fr 218px;gap:18px;
align-items:start}}
@media (max-width:640px){{.heroGrid{{grid-template-columns:1fr}}}}
.leg{{font-size:12.5px;line-height:1.5}}
.leg h4{{margin:0 0 6px;font-size:10.5px;letter-spacing:.09em;
text-transform:uppercase;color:var(--ink3);font-weight:600}}
.leg .grp{{margin:0 0 14px}}
.leg .row{{display:flex;align-items:baseline;gap:7px;margin:2px 0}}
.leg .sw{{flex:0 0 14px;height:9px;border-radius:2px;
border:1px solid var(--rule)}}
.leg .ln{{flex:0 0 14px;height:3px;border-radius:2px}}
.leg .dot{{flex:0 0 9px;height:9px;border-radius:50%;margin-left:2px}}
.key{{display:flex;flex-wrap:wrap;gap:6px 18px;font-size:12.5px;
color:var(--ink2);margin:0 0 14px}}
.key span{{display:inline-flex;align-items:center;gap:6px;white-space:nowrap}}
.key i{{width:14px;height:9px;border-radius:2px;
border:1px solid var(--rule)}}
.leg .mi{{margin-left:auto;color:var(--ink3);
font-family:"IBM Plex Mono",monospace;font-size:11.5px;
font-variant-numeric:tabular-nums}}

/* plan view */
.plan .l-nf{{fill:var(--l-nf)}} .plan .l-wild{{fill:var(--l-wild)}}
.plan .l-sf{{fill:var(--l-sf)}} .plan .l-sgl{{fill:var(--l-sgl)}}
.plan .l-sp{{fill:var(--l-sp)}} .plan .l-trb{{fill:var(--l-trb)}}
.plan .land path{{stroke:none}}
.plan .river path{{fill:none;stroke-linecap:round;stroke-linejoin:round}}
.plan .r-float{{stroke:var(--m-float);stroke-width:2.6}}
.plan .r-wade{{stroke:var(--m-wade);stroke-width:2.6}}
.plan .r-drag{{stroke:var(--m-drag);stroke-width:2.6}}
.plan .border{{stroke:var(--ink3);stroke-width:.8;stroke-dasharray:5 4}}
.plan .m-kinzua{{fill:var(--m-drag);stroke:var(--panel);stroke-width:1.4}}
.plan .m-lock{{fill:var(--ink2);stroke:var(--panel);stroke-width:1.2}}
.plan .m-putin{{fill:none;stroke:var(--m-float);stroke-width:2.2}}
.plan .m-end{{fill:var(--ink);stroke:var(--panel);stroke-width:1.6}}
.plan .m-town{{fill:var(--ink3)}}
.plan text{{font-family:"IBM Plex Sans",sans-serif}}
.plan .t-end{{font-size:12px;font-weight:600;fill:var(--ink)}}
.plan .t-sub,.plan .t-rose{{font-size:9px;fill:var(--ink3);
font-family:"IBM Plex Mono",monospace}}
.plan .t-town{{font-size:9.5px;fill:var(--ink2)}}
.plan .t-call{{font-size:10.5px;font-weight:600;fill:var(--m-drag)}}
.plan .t-border{{font-size:8.5px;letter-spacing:.12em;fill:var(--ink3)}}
.plan .rose line,.plan .scale line{{stroke:var(--ink3);stroke-width:1}}
.plan .rose path{{fill:var(--ink3)}}
.plan .leader{{stroke:var(--m-drag);stroke-width:1}}

/* river-mile strip */
.strip text{{font-family:"IBM Plex Sans",sans-serif}}
.strip .band-bg{{fill:var(--band)}}
.strip .s-float{{fill:var(--m-float)}} .strip .s-wade{{fill:var(--m-wade)}}
.strip .s-drag{{fill:var(--m-drag)}}
.strip .s-camp{{fill:var(--camp)}} .strip .s-tribal{{fill:var(--trb)}}
.strip .s-cty-pa{{fill:var(--cty-pa)}} .strip .s-cty-ny{{fill:var(--cty-ny)}}
.strip .s-trail{{fill:var(--trail)}}
.strip .s-trail-soft{{fill:var(--trail-soft)}}
.strip .t-trail{{font-size:9px;fill:#fff}}
.strip .t-nosteward{{font-size:9px;fill:var(--ink3)}}
.strip .t-trail-out{{font-size:9px;fill:var(--trail);font-weight:600}}
.strip .leader-t{{stroke:var(--trail);stroke-width:1}}
.strip .t-lane{{font-size:9px;letter-spacing:.09em;fill:var(--ink3);
font-weight:600}}
.strip .t-cty{{font-size:9px;fill:var(--ink2)}}
.strip .t-strip-town{{font-size:10px;fill:var(--ink2)}}
.strip .tick-town{{stroke:var(--rule);stroke-width:1}}
.strip .b-dam{{fill:var(--m-drag)}} .strip .b-lock{{fill:var(--ink3)}}
.strip .t-call2{{font-size:9.5px;font-weight:600;fill:var(--ink2)}}
.strip .gapbar{{stroke:var(--warn);stroke-width:2.2;stroke-linecap:round}}
.strip .t-gap{{font-size:9.5px;fill:var(--warn);font-weight:600}}
.strip .axis{{stroke:var(--ink3);stroke-width:.8}}
.strip .t-axis{{font-size:9px;fill:var(--ink3);
font-family:"IBM Plex Mono",monospace}}
.strip .t-axis-lab{{font-size:9.5px;fill:var(--ink3)}}
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
  <figure class="figwrap">
    <div class="heroGrid">
      <div>{figs['plan']}</div>
      {legend}
    </div>
    <figcaption>The corridor, north up. The centerline is the USGS NHDPlus
    High Resolution mainstem, coloured by whether July median discharge will
    carry a loaded boat. The first {f['start_rm'] - f['putin_rm']:.0f} miles
    below the source will not: that stretch is walked in the channel, and the
    first public land where the river is floatable is
    {f['putin_name']} at RM {f['putin_rm']:.1f}.
    <a href="map.html">Open the interactive version</a> for access points,
    gages, campgrounds, the nightly stops and every layer toggled
    separately.</figcaption>
  </figure>

  <div class="dl">
    <a class="btn primary" href="map.html"><b>Open the interactive map</b>
      <span>Pan, zoom, toggle layers, click anything</span></a>
    <a class="btn" href="allegheny_river_atlas.gpkg" download>
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

  <figure class="figwrap">
    <h3 class="figh">The same {f['start_rm']:.0f} miles on one axis</h3>
    <div class="key">
      <span><i style="background:var(--m-float)"></i>Floatable</span>
      <span><i style="background:var(--m-wade)"></i>Wadeable</span>
      <span><i style="background:var(--m-drag)"></i>Below wading flow</span>
      <span><i style="background:var(--camp)"></i>Legal public camping</span>
      <span><i style="background:var(--trb)"></i>Seneca Nation — ask the
        Nation</span>
      <span><i style="background:var(--band)"></i>No lawful public
        campsite</span>
      <span><i style="background:var(--trail)"></i>Designated water
        trail</span>
      <span><i style="background:var(--trail-soft)"></i>Promoted paddling
        reach</span>
    </div>
    <div class="scrollx">{figs['strip']}</div>
    <figcaption>This is how a river is actually read. Every layer in the
    dataset keys to this axis, so any two of them join on position without a
    spatial operation. The middle band is the finding the rest of the
    project turned on: the green is everywhere along {f['start_rm']:.0f} miles
    of river where the public may lawfully camp, reached from the water. The
    band below it answers a different question — who, if anyone, stewards the
    reach you are standing in. Scroll it sideways on a phone; on a desktop,
    hovering any band gives the reach, the rule and the steward behind
    it.</figcaption>
  </figure>

  <h2>Who stewards each reach</h2>
  <p>A water trail grants nobody a right of access. What it gives a paddler is
  a named body that signs the reach, keeps the launches open and will pick up
  the phone about a closed one. That is the useful fact, and it is the one
  that is hardest to find — Pennsylvania's published GIS maps
  <b>one</b> of the four stewarded reaches below. The rest are real, and
  unmapped.</p>
  <div class="tw"><table>
    <thead><tr><th>Reach</th><th>Trail</th><th>Steward</th>
      <th>Call</th><th>Guide</th></tr></thead>
    <tbody>
{trail_rows}
    </tbody>
  </table></div>
  <p><b>{f['trail_unstewarded_mi']:.0f} river miles have no steward at
  all</b> — the {gap_list}. On those reaches there is no one whose job it is
  to tell you a launch has washed out.</p>

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
