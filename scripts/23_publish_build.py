#!/usr/bin/env python3
"""Publish the static atlas files and omit private contact fields from the public GeoPackage."""
from __future__ import annotations

import datetime as dt
import json
import re
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
        if name == "water_trails" and "steward_email" in g.columns:
            g["steward_email"] = None
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

    # Refresh the data in the checked-in offline map presentation.
    payload_pattern = re.compile(r"^const D = (.*);$", re.MULTILINE)
    generated_map = (config.OUT / "map.html").read_text(encoding="utf-8")
    payload_match = payload_pattern.search(generated_map)
    if payload_match is None:
        raise ValueError("Generated map is missing its embedded data")
    payload = json.loads(payload_match[1])
    for trail in payload.get("trails", []):
        trail.pop("email", None)

    map_path = DOCS / "map.html"
    map_html = map_path.read_text(encoding="utf-8")
    data_line = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).replace(
        "<", r"\u003c")
    map_html, replaced = payload_pattern.subn(
        lambda _: f"const D = {data_line};", map_html)
    if replaced != 1:
        raise ValueError("Expected one embedded data block in the public map")
    map_path.write_text(map_html, encoding="utf-8")

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

PARCEL RECORDS
Use the parcel identifier to consult county assessment records.

NO WARRANTY
Camping classifications reflect published rules at compilation. This is
not legal advice. Check current regulations and permits with the responsible
agency or nation. Flow-derived layers use historical median estimates.
""", encoding="utf-8")

    (DOCS / "CNAME.example").write_text(
        "allegheny.michaelperry.org\n", encoding="utf-8")

    for f in sorted(DOCS.iterdir()):
        print(f"    docs/{f.name:<34} {f.stat().st_size / 1024:8.1f} KB")
    print(f"\n  site ready in docs/ — GitHub Pages serves this directly, "
          f"or upload it anywhere static")


if __name__ == "__main__":
    main()
