#!/usr/bin/env python3
"""
Static SVG figures for the published site.

Two figures, both inline SVG with no images, no scripts and no external
requests, so they render on any static host, in any CSP, and in dark mode
(every colour is a CSS custom property inherited from the page):

  plan  - north-up plan view of the corridor: public land, the centerline
          coloured by in-channel traverse mode, barriers, the put-in, towns
  strip - the route as one linear river-mile axis carrying traverse mode,
          legal public camping, county and the barriers, which is how a
          river is actually read

Imported by 23_publish_build.py. Nothing here touches the network.
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import geopandas as gpd
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import config
import riverindex

SIMPLIFY_RIVER_M = 150.0
SIMPLIFY_LAND_M = 400.0

# Plan-view canvas (user units; the SVG scales to its container).
PLAN_W = 520.0
PAD = 26.0

# Strip canvas.
STRIP_W = 1000.0

LAND_KEEP = {
    "Designated Wilderness": ("wild", "Designated Wilderness"),
    "National Forest": ("nf", "National Forest"),
    "State Forest": ("sf", "State Forest"),
    "State Game Land": ("sgl", "State Game Land"),
    "State Park": ("sp", "State Park"),
    "Tribal Territory": ("trb", "Seneca Nation, Allegany Territory"),
}

# Towns worth a label on a figure this size, with the side the label sits on.
PLAN_TOWNS = {
    "Olean": ("r", 3.6), "Salamanca": ("l", -3.0), "Warren": ("l", 13.0),
    "Tionesta": ("r", 3.6), "Franklin": ("r", 3.6), "Emlenton": ("r", 3.6),
    "Kittanning": ("r", 3.6),
}
STRIP_TOWNS = ["Coudersport", "Eldred", "Olean", "Salamanca", "Warren",
               "Tionesta", "Franklin", "Emlenton", "Kittanning", "Pittsburgh"]


SHORT_STEWARD = {
    "Cattaraugus County Tourism (Enchanted Mountains of Western New York)":
        "Cattaraugus County Tourism",
    "USDA Forest Service - Allegheny National Forest":
        "Allegheny National Forest",
    "Experience Armstrong, Inc.": "Experience Armstrong",
    "Friends of the Riverfront": "Friends of the Riverfront",
}


def short_steward(name: str) -> str:
    return SHORT_STEWARD.get(name, name)


def esc(s: str) -> str:
    return (str(s).replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;"))


def _simplify(geom, tol_m: float):
    return (gpd.GeoSeries([geom], crs=config.GEO_CRS)
            .to_crs(config.METRIC_CRS).simplify(tol_m)
            .to_crs(config.GEO_CRS).iloc[0])


def _rings(geom, tol_m: float):
    gm = _simplify(geom, tol_m)
    if gm.is_empty:
        return []
    polys = ([gm] if gm.geom_type == "Polygon"
             else list(gm.geoms) if gm.geom_type == "MultiPolygon" else [])
    return [list(p.exterior.coords) for p in polys]


def mode_runs(modes: pd.DataFrame):
    """Centerline split into runs of constant traverse mode, upstream first."""
    m = modes.sort_values("river_mile", ascending=False).reset_index(drop=True)
    runs, cur, hi = [], m.loc[0, "traverse_mode"], float(m.loc[0, "river_mile"])
    for i in range(1, len(m)):
        if m.loc[i, "traverse_mode"] != cur:
            runs.append((hi, float(m.loc[i, "river_mile"]), cur))
            cur, hi = m.loc[i, "traverse_mode"], float(m.loc[i, "river_mile"])
    runs.append((hi, float(m["river_mile"].min()), cur))
    return [r for r in runs if r[0] - r[1] >= 0.05]


class Proj:
    """Equirectangular, x scaled by cos(mid-latitude). North is up."""

    def __init__(self, bounds, width, pad):
        lon0, lat0, lon1, lat1 = bounds
        self.k = math.cos(math.radians((lat0 + lat1) / 2))
        self.lon0, self.lat1 = lon0, lat1
        w = (lon1 - lon0) * self.k
        h = lat1 - lat0
        self.s = (width - 2 * pad) / w
        self.pad = pad
        self.w = width
        self.h = h * self.s + 2 * pad

    def __call__(self, lon, lat):
        return (self.pad + (lon - self.lon0) * self.k * self.s,
                self.pad + (self.lat1 - lat) * self.s)

    def path(self, coords, close=False):
        d = []
        for i, (lon, lat) in enumerate(coords):
            x, y = self(lon, lat)
            d.append(f"{'M' if i == 0 else 'L'}{x:.1f},{y:.1f}")
        if close:
            d.append("Z")
        return "".join(d)


def build_plan(ri, modes, lands, towns, barriers, putin, meta) -> str:
    river = gpd.read_file(config.PROC / "river_centerline.geojson")
    b = river.total_bounds
    bounds = (b[0] - 0.09, b[1] - 0.05, b[2] + 0.26, b[3] + 0.05)
    p = Proj(bounds, PLAN_W, PAD)
    out = [f'<svg class="fig plan" viewBox="0 0 {PLAN_W:.0f} {p.h:.0f}" '
           f'role="img" aria-label="Plan map of the Allegheny River corridor '
           f'from Coudersport, Pennsylvania to Pittsburgh, showing public '
           f'land, in-channel traverse mode, dams and locks.">']

    # --- public land -------------------------------------------------------
    out.append('<g class="land">')
    order = ["National Forest", "State Forest", "State Game Land",
             "State Park", "Designated Wilderness", "Tribal Territory"]
    for desig in order:
        sel = lands[lands["designation"] == desig]
        for _, r in sel.iterrows():
            if r.geometry is None or r.geometry.is_empty:
                continue
            key = LAND_KEEP[desig][0]
            for ring in _rings(r.geometry, SIMPLIFY_LAND_M):
                if len(ring) < 4:
                    continue
                out.append(f'<path class="l-{key}" d="{p.path(ring, True)}"/>')
    out.append('</g>')

    # --- state line --------------------------------------------------------
    xa, ya = p(bounds[0], 41.9993)
    xb, _ = p(bounds[2], 41.9993)
    out.append(f'<line class="border" x1="{xa:.1f}" y1="{ya:.1f}" '
               f'x2="{xb:.1f}" y2="{ya:.1f}"/>')
    out.append(f'<text class="t-border" x="{xb - 4:.1f}" y="{ya - 5:.1f}" '
               f'text-anchor="end">NEW YORK</text>')
    out.append(f'<text class="t-border" x="{xb - 4:.1f}" y="{ya + 13:.1f}" '
               f'text-anchor="end">PENNSYLVANIA</text>')

    # --- river, by traverse mode ------------------------------------------
    out.append('<g class="river">')
    for hi, lo, mode in mode_runs(modes):
        seg = _simplify(ri.substring_between(hi, lo), SIMPLIFY_RIVER_M)
        out.append(f'<path class="r-{mode}" d="{p.path(seg.coords)}"/>')
    out.append('</g>')

    # --- barriers ----------------------------------------------------------
    out.append('<g class="marks">')
    for _, r in barriers.iterrows():
        x, y = p(r["lon"], r["lat"])
        cls = "kinzua" if r["kind"] == "dam_portage" else "lock"
        out.append(f'<circle class="m-{cls}" cx="{x:.1f}" cy="{y:.1f}" '
                   f'r="{4.4 if cls == "kinzua" else 2.9:.1f}"/>')
    x, y = p(putin["lon"], putin["lat"])
    out.append(f'<circle class="m-putin" cx="{x:.1f}" cy="{y:.1f}" r="4"/>')
    out.append('</g>')

    # --- endpoints ---------------------------------------------------------
    for lon, lat, label, sub, side, dy in (
            (meta["start"]["lon"], meta["start"]["lat"],
             "Coudersport", f'RM {meta["start"]["river_mile"]:.1f}',
             "r", -3.0),
            (meta["end"]["lon"], meta["end"]["lat"],
             "Pittsburgh", "RM 0.0 · the Point", "r", -1.0)):
        x, y = p(lon, lat)
        dx = -10 if side == "l" else 10
        anc = "end" if side == "l" else "start"
        out.append(f'<circle class="m-end" cx="{x:.1f}" cy="{y:.1f}" r="4.5"/>')
        out.append(f'<text class="t-end" x="{x + dx:.1f}" y="{y + dy:.1f}" '
                   f'text-anchor="{anc}">{label}</text>')
        out.append(f'<text class="t-sub" x="{x + dx:.1f}" y="{y + dy + 12:.1f}" '
                   f'text-anchor="{anc}">{sub}</text>')

    # --- towns -------------------------------------------------------------
    out.append('<g class="towns">')
    for _, r in towns.iterrows():
        spec = PLAN_TOWNS.get(str(r["name"]))
        if spec is None:
            continue
        side, dy = spec
        x, y = p(r["lon"], r["lat"])
        dx = -8 if side == "l" else 8
        anc = "end" if side == "l" else "start"
        out.append(f'<circle class="m-town" cx="{x:.1f}" cy="{y:.1f}" r="2.4"/>')
        out.append(f'<text class="t-town" x="{x + dx:.1f}" y="{y + dy:.1f}" '
                   f'text-anchor="{anc}">{esc(r["name"])}</text>')
    out.append('</g>')

    # --- Kinzua callout ----------------------------------------------------
    kz = barriers[barriers["kind"] == "dam_portage"].iloc[0]
    x, y = p(kz["lon"], kz["lat"])
    out.append(f'<text class="t-call" x="{x - 9:.1f}" y="{y - 20:.1f}" '
               f'text-anchor="end">Kinzua Dam</text>')
    out.append(f'<text class="t-sub" x="{x - 9:.1f}" y="{y - 9:.1f}" '
               f'text-anchor="end">portage · RM {kz["river_mile"]:.1f}</text>')
    out.append(f'<line class="leader" x1="{x - 7:.1f}" y1="{y - 13:.1f}" '
               f'x2="{x - 2:.1f}" y2="{y - 4:.1f}"/>')

    # --- north arrow + scale ----------------------------------------------
    nx, ny = PLAN_W - 30, PAD + 6
    out.append(f'<g class="rose"><line x1="{nx}" y1="{ny + 22}" x2="{nx}" '
               f'y2="{ny}"/><path d="M{nx - 4},{ny + 6} L{nx},{ny} '
               f'L{nx + 4},{ny + 6} Z"/>'
               f'<text class="t-rose" x="{nx}" y="{ny + 33}" '
               f'text-anchor="middle">N</text></g>')
    bar_mi = 25.0
    bar = bar_mi / 69.05 * p.s          # degrees of latitude -> user units
    bx, by = PLAN_W * 0.62, p.h * 0.86
    out.append(f'<g class="scale"><line x1="{bx:.1f}" y1="{by:.1f}" '
               f'x2="{bx + bar:.1f}" y2="{by:.1f}"/>'
               f'<line x1="{bx:.1f}" y1="{by - 3.5:.1f}" x2="{bx:.1f}" '
               f'y2="{by + 3.5:.1f}"/>'
               f'<line x1="{bx + bar:.1f}" y1="{by - 3.5:.1f}" '
               f'x2="{bx + bar:.1f}" y2="{by + 3.5:.1f}"/>'
               f'<text class="t-rose" x="{bx + bar + 6:.1f}" '
               f'y="{by + 3.5:.1f}">{bar_mi:.0f} mi</text></g>')

    out.append('</svg>')
    return "\n".join(out)


# ---------------------------------------------------------------------------
# river-mile strip
# ---------------------------------------------------------------------------

STRIP_L, STRIP_R = 8.0, 8.0
BAND_H = 20.0
LANE_Y = {"mode": 62.0, "camp": 100.0, "trail": 158.0,
          "county": 196.0}
STRIP_H = 266.0


def build_strip(modes, intervals, frontage, counties, barriers, towns,
                gaps, trails, trail_gaps, start_rm) -> str:
    x0, x1 = STRIP_L, STRIP_W - STRIP_R
    hi_rm, lo_rm = start_rm, 0.0

    def X(rm: float) -> float:
        rm = min(max(rm, lo_rm), hi_rm)
        return x0 + (hi_rm - rm) / (hi_rm - lo_rm) * (x1 - x0)

    out = [f'<svg class="fig strip" viewBox="0 0 {STRIP_W:.0f} {STRIP_H:.0f}" '
           f'role="img" aria-label="The route as a single river-mile axis '
           f'from river mile {start_rm:.0f} at Coudersport to river mile 0 at '
           f'Pittsburgh, banded by in-channel traverse mode, legal public '
           f'camping and county.">']

    def band(y, label):
        out.append(f'<rect class="band-bg" x="{x0:.1f}" y="{y:.1f}" '
                   f'width="{x1 - x0:.1f}" height="{BAND_H:.1f}"/>')
        out.append(f'<text class="t-lane" x="{x0:.1f}" y="{y - 5:.1f}">'
                   f'{label}</text>')

    def seg(y, hi, lo, cls, title=None):
        a, b = X(hi), X(lo)
        w = max(b - a, 0.7)
        t = f'<title>{esc(title)}</title>' if title else ''
        out.append(f'<rect class="{cls}" x="{a:.2f}" y="{y:.1f}" '
                   f'width="{w:.2f}" height="{BAND_H:.1f}">{t}</rect>')

    # --- towns (above everything) -----------------------------------------
    tsel = towns[towns["name"].isin(STRIP_TOWNS)]
    for _, r in tsel.iterrows():
        x = X(float(r["river_mile"]))
        anc = ("start" if x < x0 + 30 else
               "end" if x > x1 - 30 else "middle")
        out.append(f'<text class="t-strip-town" x="{x:.1f}" y="14" '
                   f'text-anchor="{anc}">{esc(r["name"])}</text>')
        out.append(f'<line class="tick-town" x1="{x:.1f}" y1="19" '
                   f'x2="{x:.1f}" y2="{LANE_Y["mode"]:.1f}"/>')

    # --- barriers ----------------------------------------------------------
    for _, r in barriers.sort_values("river_mile").iterrows():
        x = X(float(r["river_mile"]))
        dam = r["kind"] == "dam_portage"
        out.append(f'<path class="{"b-dam" if dam else "b-lock"}" '
                   f'd="M{x:.1f},{LANE_Y["mode"] - 4:.1f} '
                   f'l-4,-7 l8,0 Z"><title>{esc(r["name"])} · RM '
                   f'{r["river_mile"]:.1f}</title></path>')
    kz = barriers[barriers["kind"] == "dam_portage"].iloc[0]
    kx = X(float(kz["river_mile"]))
    out.append(f'<text class="t-call2" x="{kx - 7:.1f}" '
               f'y="{LANE_Y["mode"] - 8:.1f}" text-anchor="end">'
               f'Kinzua Dam · portage</text>')
    lx = X(float(barriers[barriers["kind"] != "dam_portage"]["river_mile"].max()))
    out.append(f'<text class="t-call2" x="{lx - 11:.1f}" '
               f'y="{LANE_Y["mode"] - 8:.1f}" text-anchor="end">'
               f'8 locks</text>')

    # --- mode band ---------------------------------------------------------
    band(LANE_Y["mode"], "IN-CHANNEL MODE")
    MODE_LBL = {"float": "floatable at July median flow",
                "wade": "wadeable — too thin to float",
                "drag": "below wading flow — carry"}
    for hi, lo, mode in mode_runs(modes):
        seg(LANE_Y["mode"], hi, lo, f"s-{mode}",
            f"RM {hi:.1f}–{lo:.1f} · {MODE_LBL.get(mode, mode)}")

    # --- camping band ------------------------------------------------------
    band(LANE_Y["camp"], "LEGAL PUBLIC CAMPING FROM THE WATER")
    trb = frontage[frontage["camp_class"] == "tribal_permit_required"]
    for _, r in trb.iterrows():
        seg(LANE_Y["camp"], float(r["rm_hi"]), float(r["rm_lo"]), "s-tribal",
            f'{r["name"]} — the Nation, not a state agency, is the authority')
    ok = intervals[intervals["camping_legal"]]
    for _, r in ok.iterrows():
        seg(LANE_Y["camp"], float(r["rm_hi"]), float(r["rm_lo"]), "s-camp",
            f'{r["name"]} · {r["designation"]}')
    for _, r in gaps[gaps["exceeds_threshold"]].iterrows():
        a, b = X(float(r["rm_start"])), X(float(r["rm_end"]))
        y = LANE_Y["camp"] + BAND_H + 6
        out.append(f'<path class="gapbar" d="M{a:.1f},{y:.1f} L{b:.1f},{y:.1f}"/>')
        if float(r["length_mi"]) >= 25:
            out.append(f'<text class="t-gap" x="{(a + b) / 2:.1f}" '
                       f'y="{y + 11:.1f}" text-anchor="middle">'
                       f'{float(r["length_mi"]):.0f} mi with none</text>')

    # --- water-trail band --------------------------------------------------
    band(LANE_Y["trail"], "WATER TRAIL — WHO STEWARDS THE REACH")
    for _, r in trails.iterrows():
        hi, lo = float(r["rm_hi"]), float(r["rm_lo"])
        cls = "s-trail" if r["designated"] else "s-trail-soft"
        seg(LANE_Y["trail"], hi, lo, cls,
            f'{r["name"]} · {r["status"]} · stewarded by {r["steward"]} '
            f'({r["steward_phone"]}) · RM {hi:.1f}–{lo:.1f}')
        a, b = X(hi), X(lo)
        lab = short_steward(str(r["steward"]))
        if b - a > len(lab) * 4.8 + 8:
            out.append(f'<text class="t-trail" x="{(a + b) / 2:.1f}" '
                       f'y="{LANE_Y["trail"] + 13.5:.1f}" '
                       f'text-anchor="middle">{esc(lab)}</text>')
        else:
            # too narrow to letter inside - caption it above, with a leader
            anc = "end" if b > x1 - 90 else "middle"
            tx = b if anc == "end" else (a + b) / 2
            out.append(f'<text class="t-trail-out" x="{tx:.1f}" '
                       f'y="{LANE_Y["trail"] - 5:.1f}" '
                       f'text-anchor="{anc}">{esc(lab)}</text>')
            out.append(f'<line class="leader-t" x1="{(a + b) / 2:.1f}" '
                       f'y1="{LANE_Y["trail"] - 3:.1f}" '
                       f'x2="{(a + b) / 2:.1f}" '
                       f'y2="{LANE_Y["trail"]:.1f}"/>')

    for _, r in trail_gaps.iterrows():
        a, b = X(float(r["rm_hi"])), X(float(r["rm_lo"]))
        if b - a > 52:
            out.append(f'<text class="t-nosteward" x="{(a + b) / 2:.1f}" '
                       f'y="{LANE_Y["trail"] + 13.5:.1f}" '
                       f'text-anchor="middle">no steward</text>')

    # --- county band -------------------------------------------------------
    band(LANE_Y["county"], "COUNTY")
    cs = counties.sort_values("rm_hi", ascending=False).reset_index(drop=True)
    for i, r in cs.iterrows():
        hi = min(float(r["rm_hi"]), hi_rm)
        lo = max(float(r["rm_lo"]), lo_rm)
        if hi <= lo:
            continue
        ny = r["state"] == "New York"
        seg(LANE_Y["county"], hi, lo, "s-cty-ny" if ny else "s-cty-pa",
            f'{r["county"]} County, {r["state"]} · RM {hi:.1f}–{lo:.1f}')
        a, b = X(hi), X(lo)
        if b - a > len(str(r["county"])) * 5.0 + 6:
            out.append(f'<text class="t-cty" x="{(a + b) / 2:.1f}" '
                       f'y="{LANE_Y["county"] + 13.5:.1f}" '
                       f'text-anchor="middle">{esc(r["county"])}</text>')

    # --- axis --------------------------------------------------------------
    ay = LANE_Y["county"] + BAND_H + 14
    out.append(f'<line class="axis" x1="{x0:.1f}" y1="{ay:.1f}" '
               f'x2="{x1:.1f}" y2="{ay:.1f}"/>')
    for rm in range(0, int(hi_rm) + 1, 25):
        x = X(rm)
        out.append(f'<line class="axis" x1="{x:.1f}" y1="{ay:.1f}" '
                   f'x2="{x:.1f}" y2="{ay + 4:.1f}"/>')
        out.append(f'<text class="t-axis" x="{x:.1f}" y="{ay + 15:.1f}" '
                   f'text-anchor="middle">{rm}</text>')
    out.append(f'<text class="t-axis-lab" x="{x1:.1f}" y="{ay + 28:.1f}" '
               f'text-anchor="end">river mile — 0.0 at the mouth, '
               f'increasing upstream</text>')

    out.append('</svg>')
    return "\n".join(out)


def build() -> dict:
    ri = riverindex.load()
    meta = json.loads((config.PROC / "river_geometry_meta.json").read_text())
    tp = json.loads((config.PROC / "transition_point.json").read_text())
    modes = pd.read_csv(config.PROC / "traverse_mode_by_rm.csv")
    lands = gpd.read_file(config.PROC / "public_lands.geojson")
    lands = lands[lands["designation"].isin(LAND_KEEP)]
    towns = gpd.read_file(config.PROC / "towns.geojson")
    barriers = pd.read_csv(config.PROC / "barriers.csv")
    intervals = pd.read_csv(config.PROC / "camping_intervals.csv")
    frontage = pd.read_csv(config.PROC / "river_frontage.csv")
    counties = pd.read_csv(config.PROC / "route_counties.csv")
    gaps = pd.read_csv(config.PROC / "camping_gaps.csv")
    trails = pd.read_csv(config.PROC / "water_trails.csv").fillna("")
    tg = pd.read_csv(config.PROC / "water_trail_gaps.csv")
    start_rm = float(meta["start"]["river_mile"])

    plan = build_plan(ri, modes, lands, towns, barriers,
                      tp["recommended_putin"], meta)
    strip = build_strip(modes, intervals, frontage, counties, barriers, towns,
                        gaps, trails, tg, start_rm)

    mi = tp["in_channel_mode_miles"]
    facts = dict(
        float_mi=mi["float"], wade_mi=mi["wade"], drag_mi=mi["drag"],
        putin_rm=tp["recommended_putin"]["river_mile"],
        putin_name=tp["recommended_putin"]["name"],
        kinzua_rm=float(barriers[barriers["kind"] == "dam_portage"]
                        .iloc[0]["river_mile"]),
        locks=int((barriers["kind"] != "dam_portage").sum()),
        trails=int(len(trails)),
        trail_unstewarded_mi=round(float(tg["span_mi"].sum()), 0),
        start_rm=start_rm)
    return dict(plan=plan, strip=strip, facts=facts,
                trails=trails)


if __name__ == "__main__":
    r = build()
    print(f"plan  {len(r['plan']) / 1024:6.1f} KB")
    print(f"strip {len(r['strip']) / 1024:6.1f} KB")
    print(r["facts"])
