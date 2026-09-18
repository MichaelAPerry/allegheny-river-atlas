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

The landing page itself is step 25, which links to everything here.

Outputs
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

    for f in sorted(DOCS.iterdir()):
        print(f"    docs/{f.name:<34} {f.stat().st_size / 1024:8.1f} KB")
    print(f"\n  site ready in docs/ — GitHub Pages serves this directly, "
          f"or upload it anywhere static")


if __name__ == "__main__":
    main()
