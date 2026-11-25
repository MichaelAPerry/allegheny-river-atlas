#!/usr/bin/env python3
"""Package processed river data as a GeoPackage and write its data dictionary."""
from __future__ import annotations

import datetime as dt
import json
import sys
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
from shapely.geometry import Point

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common
import config
import riverindex

GPKG = config.OUT / "allegheny_river_atlas.gpkg"
TODAY = dt.date.today().isoformat()

# layer -> (source agency, dataset, licence/terms)
PROVENANCE = {
    "river_centerline": ("USGS", "NHDPlus High Resolution, NetworkNHDFlowline",
                         "US Government work, public domain"),
    "river_mile_markers": ("derived", "Computed from the NHD centerline",
                           "Derived; same terms as source"),
    "river_traverse_mode": ("derived", "USGS daily-median discharge applied "
                            "to NHD drainage area", "Derived"),
    "river_camping_legality": ("derived", "Agency land layers classified "
                               "against published camping rules", "Derived"),
    "river_public_land_frontage": ("USFS / PA DCNR / PGC / PFBC / NYSDEC",
                                   "Ownership and boundary layers",
                                   "Public agency data; check each agency"),
    "river_water_quality": ("US EPA", "ATTAINS Assessment Lines",
                            "US Government work, public domain"),
    "river_fishing_regulations": ("PA Fish & Boat Commission",
                                  "Fisheries All Sections, via PASDA",
                                  "PASDA terms; attribution required"),
    "river_fish_advisories": ("PA DEP / PFBC",
                              "Fish consumption advisory tables",
                              "Public health guidance; verify before use"),
    "river_drone_restrictions": ("derived", "Wilderness Act s.4(c) applied "
                                 "to USFS Wilderness boundaries", "Derived"),
    "river_counties": ("USGS", "The National Map, govunits",
                       "US Government work, public domain"),
    "kinzua_portage_route": ("OpenStreetMap + USGS 3DEP",
                             "OSM highway network, USGS elevation",
                             "OSM: ODbL, attribution required"),
    "water_trails": ("PA Fish & Boat Commission (mapped extent) + each "
                     "steward's own published material",
                     "Water Trails via PASDA; steward contacts verified "
                     "against each organisation's own page",
                     "PASDA terms; attribution required"),
    "water_trail_gaps": ("Derived", "Reaches no water trail covers",
                         "CC BY 4.0"),
    "public_lands": ("USFS / PA DCNR / PGC / PFBC / NYSDEC",
                     "Ownership and boundary polygons",
                     "Public agency data; check each agency"),
    "barriers": ("USACE / USGS", "Published navigation river miles, "
                 "cross-checked against NHD lock chambers",
                 "US Government work, public domain"),
    "access_points": ("PA Fish & Boat Commission / NYSDEC",
                      "PFBC Access and Properties; NYSDEC boat launches",
                      "PASDA and NYSDEC terms"),
    "gages": ("USGS", "NWIS site and instantaneous-values services",
              "US Government work, public domain"),
    "campgrounds": ("USFS / USGS TNM / NYSDEC / OpenStreetMap",
                    "Recreation sites, TNM Structures, OSM camp_site",
                    "Mixed; OSM portion is ODbL"),
    "hospitals": ("USGS", "The National Map, structures",
                  "US Government work, public domain"),
    "towns": ("USGS", "The National Map, geonames incorporated places",
              "US Government work, public domain"),
    "nightly_stops": ("derived", "Output of the pacing model", "Derived"),
    "riparian_parcels": ("County assessment offices",
                         "Potter, Forest, Butler, Warren, Venango, "
                         "Allegheny, Westmoreland, NYSDEC tax parcels",
                         "Public county assessment records"),
}

# raw source field -> documented name
RENAME = {
    "dec_lat_va": "latitude", "dec_long_va": "longitude",
    "drain_area_va": "drainage_area_sqmi", "alt_va": "elevation_ft",
    "huc_cd": "huc_code", "state_cd": "state_fips",
    "site_no": "usgs_site_no", "station_nm": "station_name",
    "camp_class": "camping_class", "rm_hi": "river_mile_upstream",
    "rm_lo": "river_mile_downstream", "span_mi": "length_mi",
    "access_name": "site_name", "offset_m": "offset_from_centerline_m",
    "on_river_100m": "within_100m_of_centerline",
    "nhd_check_rm": "nhd_crosscheck_river_mile",
    "nhd_check_delta_mi": "nhd_crosscheck_delta_mi",
    "unit": "assessment_unit_name", "unit_id": "assessment_unit_id",
    "ir_category": "epa_ir_category", "cycle": "reporting_cycle",
    "traverse_mode": "traverse_mode", "median_cfs": "median_discharge_cfs",
    "p25_cfs": "p25_discharge_cfs", "da_sqmi": "drainage_area_sqmi",
}

FIELD_DOCS = {
    "river_mile": "Distance from the mouth at Point State Park, statute "
                  "miles, increasing upstream (USACE convention)",
    "river_mile_upstream": "Upstream end of the span, river miles from the "
                           "mouth",
    "river_mile_downstream": "Downstream end of the span, river miles from "
                             "the mouth",
    "length_mi": "Along-channel length of the span, statute miles",
    "offset_from_centerline_m": "Perpendicular distance from the NHD "
                                "centerline, metres",
    "median_discharge_cfs": "Estimated median discharge, cubic feet per "
                            "second",
    "drainage_area_sqmi": "Upstream drainage area, square miles",
    "traverse_mode": "drag (<70 cfs), wade (70-120), float (>=120) - the "
                     "in-channel travel mode implied by estimated flow",
    "camping_class": "Camping rule class for the managing jurisdiction",
    "camping_legal": "True where dispersed camping is permitted",
    "epa_ir_category": "EPA Integrated Report category; 5 = impaired and "
                       "needing a TMDL, 4C = impaired by a non-pollutant",
}


def stamp(gdf: gpd.GeoDataFrame, layer: str) -> gpd.GeoDataFrame:
    agency, dataset, licence = PROVENANCE.get(
        layer, ("unknown", "unknown", "unknown"))
    out = gdf.rename(columns={k: v for k, v in RENAME.items()
                              if k in gdf.columns}).copy()
    out["source_agency"] = agency
    out["source_dataset"] = dataset
    out["source_licence"] = licence
    out["retrieved"] = TODAY
    # GeoPackage dislikes object columns holding non-strings
    for c in out.columns:
        if c == "geometry":
            continue
        if out[c].dtype == object:
            out[c] = out[c].astype(str).replace({"nan": None, "None": None})
    return out


def spans_to_lines(ri, df: pd.DataFrame, hi="rm_hi", lo="rm_lo"
                   ) -> gpd.GeoDataFrame:
    """Turn a river-mile span table into real LineString geometry."""
    geoms, keep = [], []
    for i, r in df.iterrows():
        a, b = float(r[hi]), float(r[lo])
        if not np.isfinite(a) or not np.isfinite(b) or abs(a - b) < 0.02:
            continue
        try:
            geoms.append(ri.substring_between(a, b))
            keep.append(i)
        except Exception:                                   # noqa: BLE001
            continue
    if not keep:
        return gpd.GeoDataFrame(columns=list(df.columns) + ["geometry"],
                                geometry="geometry", crs=config.GEO_CRS)
    return gpd.GeoDataFrame(df.loc[keep].reset_index(drop=True),
                            geometry=geoms, crs=config.GEO_CRS)


def points_from_cols(df: pd.DataFrame, lon="lon", lat="lat"
                     ) -> gpd.GeoDataFrame:
    d = df.dropna(subset=[lon, lat]).copy()
    return gpd.GeoDataFrame(d, geometry=gpd.points_from_xy(d[lon], d[lat]),
                            crs=config.GEO_CRS)


def merge_spans(df, hi="rm_hi", lo="rm_lo"):
    iv = sorted(((float(r[hi]), float(r[lo])) for _, r in df.iterrows()),
                key=lambda t: -t[0])
    out = []
    for a, b in iv:
        if out and a >= out[-1][1]:
            out[-1] = (out[-1][0], min(out[-1][1], b))
        else:
            out.append((a, b))
    return pd.DataFrame(out, columns=[hi, lo])


def main() -> None:
    common.banner("STEP 20 - package as a GeoPackage")
    ri = riverindex.load()
    P = config.PROC
    if GPKG.exists():
        GPKG.unlink()

    layers: dict[str, gpd.GeoDataFrame] = {}

    # ---------------- existing spatial layers
    for name, f in [("river_centerline", "river_centerline.geojson"),
                    ("public_lands", "public_lands.geojson"),
                    ("barriers", "barriers.geojson"),
                    ("access_points", "access_points.geojson"),
                    ("gages", "gages.geojson"),
                    ("campgrounds", "campgrounds.geojson"),
                    ("nightly_stops", "nightly_stops.geojson"),
                    ("towns", "towns.geojson"),
                    ("water_trails", "water_trails.geojson"),
                    ("kinzua_portage_route", "kinzua_portage_route.geojson")]:
        p = P / f
        if p.exists():
            layers[name] = gpd.read_file(p)

    # ---------------- span tables that had no geometry at all
    tm = pd.read_csv(P / "traverse_mode_by_rm.csv")
    runs, cur, hi = [], None, None
    for _, r in tm.sort_values("river_mile", ascending=False).iterrows():
        if r["traverse_mode"] != cur:
            if cur is not None:
                runs.append(dict(rm_hi=hi, rm_lo=r["river_mile"],
                                 traverse_mode=cur))
            cur, hi = r["traverse_mode"], r["river_mile"]
    runs.append(dict(rm_hi=hi, rm_lo=tm["river_mile"].min(),
                     traverse_mode=cur))
    layers["river_traverse_mode"] = spans_to_lines(ri, pd.DataFrame(runs))

    ci = pd.read_csv(P / "camping_intervals.csv")
    layers["river_camping_legality"] = spans_to_lines(ri, ci)

    layers["river_public_land_frontage"] = spans_to_lines(
        ri, pd.read_csv(P / "river_frontage.csv"))

    wq = pd.read_csv(P / "water_quality.csv")
    imp = wq[wq["status"].str.contains("Not Supporting", case=False,
                                       na=False)]
    m = merge_spans(imp)
    m["status"] = "Not Supporting"
    m["span_mi"] = (m["rm_hi"] - m["rm_lo"]).round(2)
    layers["river_water_quality"] = spans_to_lines(ri, m)

    layers["river_fishing_regulations"] = spans_to_lines(
        ri, pd.read_csv(P / "fishing_sections.csv"))
    layers["river_drone_restrictions"] = spans_to_lines(
        ri, pd.read_csv(P / "drone_restrictions.csv"))
    fa = pd.read_csv(P / "fish_advisories.csv")
    layers["river_fish_advisories"] = spans_to_lines(ri, fa)
    rc = pd.read_csv(P / "route_counties.csv")
    layers["river_counties"] = spans_to_lines(ri, rc)
    tg = pd.read_csv(P / "water_trail_gaps.csv")
    layers["water_trail_gaps"] = spans_to_lines(ri, tg)

    # ---------------- point tables that had only lon/lat columns
    hosp = pd.read_csv(P / "hospitals.csv")
    layers["hospitals"] = points_from_cols(hosp)

    parc = pd.read_csv(P / "riparian_parcels.csv")
    parc = parc[parc["parcel_id"].notna()].copy()
    pts = [Point(*ri.point_at_rm(float(r))) for r in parc["river_mile"]]
    layers["riparian_parcels"] = gpd.GeoDataFrame(
        parc.reset_index(drop=True), geometry=pts, crs=config.GEO_CRS)

    # ---------------- mile markers, generated
    start = ri._rm.max()
    mm = []
    for rm in np.arange(np.floor(start / 5) * 5, -0.1, -5.0):
        lon, lat = ri.point_at_rm(float(rm))
        mm.append(dict(river_mile=float(rm), lon=round(lon, 6),
                       lat=round(lat, 6)))
    layers["river_mile_markers"] = points_from_cols(pd.DataFrame(mm))

    # ---------------- write
    print(f"  writing {len(layers)} layers to "
          f"{GPKG.relative_to(config.ROOT)}")
    first = True
    written = []
    for name, g in layers.items():
        if g is None or g.empty:
            print(f"    skip {name}: empty")
            continue
        g = stamp(g, name)
        g = g.set_crs(config.GEO_CRS, allow_override=True)
        g.to_file(GPKG, layer=name, driver="GPKG",
                  mode="w" if first else "a")
        first = False
        written.append((name, len(g), g.geometry.geom_type.iloc[0]))
        print(f"    {name:<30} {len(g):5d} {g.geometry.geom_type.iloc[0]}")

    meta = pd.DataFrame(
        [dict(layer=n, features=c, geometry=t,
              source_agency=PROVENANCE.get(n, ("?",))[0],
              source_dataset=PROVENANCE.get(n, ("?", "?"))[1],
              licence=PROVENANCE.get(n, ("?", "?", "?"))[2],
              retrieved=TODAY)
         for n, c, t in written])
    # A non-spatial table inside the GeoPackage: pandas has no to_file, and
    # pyogrio writes attribute-only tables directly.
    try:
        import pyogrio
        pyogrio.write_dataframe(meta, GPKG, layer="dataset_metadata",
                                append=True)
        print(f"    {'dataset_metadata':<30} {len(meta):5d} attribute table")
    except Exception as exc:                                # noqa: BLE001
        meta.to_csv(config.OUT / "dataset_metadata.csv", index=False)
        print(f"    dataset_metadata written as CSV instead: "
              f"{str(exc)[:70]}")

    print(f"\n  GeoPackage: {GPKG.stat().st_size / 1024 / 1024:.1f} MB")
    write_dictionary(written, layers)


def write_dictionary(written, layers) -> None:
    L: list[str] = []
    A = L.append
    A("# Allegheny River Atlas — Data Dictionary")
    A("")
    A(f"`allegheny_river_atlas.gpkg` — OGC GeoPackage, **EPSG:4326 "
      f"(WGS 84)**, {len(written)} spatial layers plus a metadata table. "
      f"Compiled {TODAY}.")
    A("")
    A("""Open the GeoPackage in QGIS, ArcGIS Pro, or another GIS that supports the format.

## River miles

River mile 0 is the mouth at Point State Park, Pittsburgh. Miles increase upstream. Use the relevant mile fields to compare locations and overlapping reaches.""")
    A("")
    A("## Layers")
    A("")
    A("| Layer | Features | Geometry | Source |")
    A("|---|---:|---|---|")
    for n, c, t in written:
        src = PROVENANCE.get(n, ("unknown",))[0]
        A(f"| `{n}` | {c} | {t} | {src} |")
    A("")
    A("""### River reach layers

The reach layers represent spans along the centerline. A frontage line identifies a stretch of river next to a tract. Use the land polygons to inspect the tract boundaries.""")
    A("")
    A("## Field conventions")
    A("")
    A("| Field | Meaning |")
    A("|---|---|")
    for k, v in FIELD_DOCS.items():
        A(f"| `{k}` | {v} |")
    A("")
    A("Every layer also carries `source_agency`, `source_dataset`, "
      "`source_licence` and `retrieved`, and the same information is in the "
      "`dataset_metadata` table.")
    A("")
    A("## Provenance and terms")
    A("")
    A("| Layer | Dataset | Terms |")
    A("|---|---|---|")
    for n, _, _ in written:
        a, d, lic = PROVENANCE.get(n, ("?", "?", "?"))
        A(f"| `{n}` | {d} | {lic} |")
    A("")
    A("**Attribution that must travel with this data:** USGS (NHDPlus HR, "
      "NWIS, The National Map, 3DEP), US EPA (ATTAINS), USDA Forest Service "
      "(EDW), Pennsylvania Fish & Boat Commission, PA DCNR and PA Game "
      "Commission via **PASDA**, NYSDEC, and **OpenStreetMap contributors "
      "(ODbL)** for the campground and portage-route layers.")
    A("")
    A("""## Coverage and limits

- Camping classifications reflect published rules at compilation. This is not legal advice. Check current regulations and permit requirements with the land manager.
- Parcel points sit on the centerline at the associated river mile.
- Launch and campground inventories are incomplete.
- Travel estimates use historical median flows. Check current conditions separately.""")
    A("")
    out = config.OUT / "DATA_DICTIONARY.md"
    out.write_text("\n".join(L) + "\n", encoding="utf-8")
    print(f"  wrote DATA_DICTIONARY.md "
          f"({out.stat().st_size / 1024:.0f} KB)")


if __name__ == "__main__":
    main()
