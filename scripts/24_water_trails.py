#!/usr/bin/env python3
"""
Step 24 - who stewards each reach of this river.

A water trail confers no right of access. What it gives a paddler is a named
body that signs the reach, keeps the launches open and will answer the phone
about a closed one - which is the fact worth carrying on a map, and the fact
that was missing from it.

Pennsylvania's published GIS maps exactly one Allegheny mainstem trail, so
its span is measured from that geometry. The other stewarded reaches are real
and unmapped, so their extents are anchored to launches and towns already
located on this project's own centerline, and every row says which it was.

Outputs
  data/processed/water_trails.csv
  data/processed/water_trails.geojson
  data/processed/water_trail_gaps.csv    reaches with no steward at all
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import geopandas as gpd
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common
import config
import riverindex

TRAIL_SNAP_M = 800.0


def _merge(spans):
    """Union of (upstream, downstream) river-mile spans, upstream first."""
    out = []
    for a, b in sorted(spans, key=lambda t: -t[0]):
        if out and a >= out[-1][1]:
            out[-1] = (out[-1][0], min(out[-1][1], b))
        else:
            out.append((a, b))
    return out


def _mapped_trail_span(ri: riverindex.RiverIndex):
    """River-mile span of the one Allegheny trail PASDA actually maps."""
    g = common.arcgis_query(config.PFBC_WATER_TRAILS, where="PFBC_ID=1")
    if g.empty:
        return None, {}
    geom = g.geometry.iloc[0]
    parts = list(geom.geoms) if geom.geom_type.startswith("Multi") else [geom]
    rms = []
    for ln in parts:
        for x, y in ln.coords:
            rm, off = ri.rm_and_offset(x, y)
            if off <= TRAIL_SNAP_M:
                rms.append(rm)
    if not rms:
        return None, {}
    r = g.iloc[0]
    attrs = {k: ("" if pd.isna(r.get(k)) else str(r.get(k)).strip())
             for k in ("WT_Name", "Web_link", "Trail_spon", "Sponsor_li",
                       "Trail_sp_1", "Sponsor__1", "Gen_Info")}
    return (max(rms), min(rms)), attrs


def build(ri: riverindex.RiverIndex,
          access: pd.DataFrame) -> pd.DataFrame:
    """Who stewards each reach of this river, and where to read about it.

    A water trail grants no access right. What it gives a paddler is a named
    body that signs the reach, keeps the launches open and answers the phone
    about them - so the column that matters here is the steward, not the fact
    of designation.
    """
    print("  water trails and the bodies that steward them ...")
    span, attrs = _mapped_trail_span(ri)
    if span:
        print(f"    PASDA maps 1 trail: {attrs['WT_Name']} "
              f"RM {span[0]:.2f}-{span[1]:.2f}")
    else:
        print("    PASDA returned no mapped Allegheny trail")

    towns = gpd.read_file(config.PROC / "towns.geojson")
    counties = pd.read_csv(config.PROC / "route_counties.csv")

    def anchor(kind, value):
        if kind == "rm":
            return float(value)
        if kind == "town":
            t = towns[towns["name"] == value]
            if t.empty:
                raise KeyError(f"water-trail anchor town not found: {value}")
            return float(t["river_mile"].iloc[0])
        if kind == "county_line":
            c = counties[counties["county"] == value]
            if c.empty:
                raise KeyError(f"water-trail anchor county not found: {value}")
            return float(c["rm_lo"].iloc[0])
        if kind == "mapped":
            return None
        raise ValueError(kind)

    rows = []
    for t in config.WATER_TRAILS:
        if t["rm_hi_anchor"][0] == "mapped":
            if not span:
                continue
            hi, lo = span
        else:
            hi = anchor(*t["rm_hi_anchor"])
            lo = anchor(*t["rm_lo_anchor"])
        n_access = int(((access["river_mile"] <= hi)
                        & (access["river_mile"] >= lo)).sum())
        rows.append(dict(
            trail_key=t["key"], name=t["name"],
            alt_name=t.get("alt_name", ""), status=t["status"],
            rm_hi=round(hi, 2), rm_lo=round(lo, 2), span_mi=round(hi - lo, 1),
            designated=not t["status"].startswith("promoted"),
            steward=t["steward"], steward_address=t["steward_address"],
            steward_phone=t["steward_phone"],
            steward_email=t.get("steward_email", ""),
            cosponsor=t.get("cosponsor", ""),
            cosponsor_phone=t.get("cosponsor_phone", ""),
            cosponsor_url=t.get("cosponsor_url", ""),
            guide_url=t["guide_url"], span_basis=t["span_basis"],
            public_access_points=n_access, note=t["note"]))

    df = pd.DataFrame(rows).sort_values("rm_hi", ascending=False)
    df.to_csv(config.PROC / "water_trails.csv", index=False)

    # the reaches nobody stewards - what is left once the trails are removed
    covered = _merge([(r["rm_hi"], r["rm_lo"]) for _, r in df.iterrows()])
    top = float(json.loads(
        (config.PROC / "river_geometry_meta.json").read_text()
    )["start"]["river_mile"])
    gaps, cur = [], top
    for hi, lo in covered:
        if cur - hi > 0.1:
            gaps.append((cur, hi))
        cur = min(cur, lo)
    if cur > 0.1:
        gaps.append((cur, 0.0))
    pd.DataFrame([dict(rm_hi=round(h, 2), rm_lo=round(l, 2),
                       span_mi=round(h - l, 1)) for h, l in gaps]
                 ).to_csv(config.PROC / "water_trail_gaps.csv", index=False)

    geoms = [ri.substring_between(r["rm_hi"], r["rm_lo"])
             for _, r in df.iterrows()]
    common.save_geojson(gpd.GeoDataFrame(df, geometry=geoms,
                                         crs=config.GEO_CRS),
                        config.PROC / "water_trails.geojson",
                        "water trails")
    tot = sum(min(h, top) - max(l, 0.0) for h, l in covered)
    print(f"    {len(df)} stewarded reaches covering {tot:.0f} of "
          f"{top:.0f} river miles; "
          f"{len(gaps)} reach(es) with no steward")
    for _, r in df.iterrows():
        print(f"      RM {r['rm_hi']:6.1f}-{r['rm_lo']:5.1f}  "
              f"{r['steward'][:44]:<44} {r['steward_phone']}")
    return df


def main() -> None:
    common.banner("STEP 24 - water trails and their stewards")
    ri = riverindex.load()
    access = pd.read_csv(config.PROC / "access_points.csv")
    build(ri, access)


if __name__ == "__main__":
    main()
