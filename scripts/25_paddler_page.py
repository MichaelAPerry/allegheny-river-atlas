#!/usr/bin/env python3
"""
Step 25 - the landing page, rebuilt for the person in the boat.

The atlas page answered "what is in this dataset". That is the wrong first
question for almost everyone who arrives: they want to know where to put in,
whether the water is high enough today, where they may legally sleep, and who
to ring when a launch is gone. This page answers those, on a phone, over a
real basemap - and keeps the dataset, the dictionary and the licence, demoted
to the footer where the people who want them will still find them.

Two things here do not exist on the old page:

  * a real basemap. The atlas map is deliberately tile-free so it renders
    inside a sandboxed artifact viewer that blocks third-party images. That
    constraint does not apply on a static host, and without roads, bridges
    and terrain underneath, a river line is close to unreadable to anyone who
    does not already know the river.
  * live discharge. A flow number baked into a static page is stale the day
    after it is built, and a stale flow is worse than none. USGS Water
    Services sends `Access-Control-Allow-Origin: *`, so the page fetches the
    current reading itself and compares it against this river's own daily
    medians, which are baked in because they do not change.

Outputs
  docs/index.html
"""
from __future__ import annotations

import datetime as dt
import json
import re
import sys
from pathlib import Path

import geopandas as gpd
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common
import config
import riverindex
import sitesvg

DOCS = config.ROOT / "docs"
SITE = "https://michaelaperry.github.io/allegheny-river-atlas/"
REPO = "https://github.com/MichaelAPerry/allegheny-river-atlas"
SIMPLIFY_M = 90.0
TODAY = dt.date.today().isoformat()


def gage_label(name: str) -> str:
    """USGS station names are shouted and abbreviated; these are read by people."""
    s = re.sub(r"(?i)^\s*allegheny river\s*", "", str(name)).strip()
    s = re.sub(r"(?i)^bl\b", "below", s)
    s = re.sub(r"(?i)^at\b\s*", "", s).strip()
    s = s.title()
    s = re.sub(r"(?i)\bat\b", "at", s)
    s = re.sub(r"(?i)\bbelow\b", "below", s)
    s = re.sub(r"(?i)\bnear\b", "near", s)
    s = re.sub(r"(?i)[, ]+(pa|ny)$", lambda m: ", " + m.group(1).upper(), s)
    return s[0].upper() + s[1:] if s else s


def line_coords(ri, hi, lo, tol=SIMPLIFY_M):
    """Leaflet wants [lat, lon]; cut the reach and thin it for a phone."""
    g = (gpd.GeoSeries([ri.substring_between(hi, lo)], crs=config.GEO_CRS)
         .to_crs(config.METRIC_CRS).simplify(tol)
         .to_crs(config.GEO_CRS).iloc[0])
    return [[round(y, 5), round(x, 5)] for x, y in g.coords]


def build_payload() -> dict:
    ri = riverindex.load()
    P = config.PROC
    meta = json.loads((P / "river_geometry_meta.json").read_text())
    modes = pd.read_csv(P / "traverse_mode_by_rm.csv")
    access = pd.read_csv(P / "access_points.csv")
    camps = pd.read_csv(P / "campgrounds.csv")
    barriers = pd.read_csv(P / "barriers.csv")
    gages = pd.read_csv(P / "gage_current.csv", dtype={"site_no": str})
    iv = pd.read_csv(P / "camping_intervals.csv")
    trails = pd.read_csv(P / "water_trails.csv").fillna("")
    tgaps = pd.read_csv(P / "water_trail_gaps.csv")
    towns = gpd.read_file(P / "towns.geojson")
    frontage = pd.read_csv(P / "river_frontage.csv")

    print("  cutting reaches from the centerline ...")
    river = [dict(mode=m, hi=round(hi, 2), lo=round(lo, 2),
                  pts=line_coords(ri, hi, lo))
             for hi, lo, m in sitesvg.mode_runs(modes)]

    camp_ok = [dict(name=str(r["name"]), desig=str(r["designation"]),
                    rule=str(r["rule"]), hi=float(r["rm_hi"]),
                    lo=float(r["rm_lo"]),
                    pts=line_coords(ri, r["rm_hi"], r["rm_lo"], 150.0))
               for _, r in iv[iv["camping_legal"]].iterrows()
               if r["rm_hi"] - r["rm_lo"] > 0.05]

    tribal = [dict(name=str(r["name"]), hi=float(r["rm_hi"]),
                   lo=float(r["rm_lo"]),
                   pts=line_coords(ri, r["rm_hi"], r["rm_lo"]))
              for _, r in frontage[frontage["camp_class"] ==
                                   "tribal_permit_required"].iterrows()]

    trail_out = [dict(
        name=str(r["name"]), steward=str(r["steward"]),
        phone=str(r["steward_phone"]), url=str(r["guide_url"]),
        addr=str(r["steward_address"]), status=str(r["status"]),
        designated=bool(r["designated"]), hi=float(r["rm_hi"]),
        lo=float(r["rm_lo"]), mi=float(r["span_mi"]),
        pts=line_coords(ri, r["rm_hi"], r["rm_lo"]))
        for _, r in trails.iterrows()]

    def pt(lon, lat, **kw):
        d = dict(lat=round(float(lat), 5), lon=round(float(lon), 5))
        d.update(kw)
        return d

    # one row per named launch; the PFBC feed carries near-duplicates
    acc = access.sort_values("offset_m").drop_duplicates(
        subset=["river_mile"]).sort_values("river_mile", ascending=False)

    payload = dict(
        meta=dict(top_rm=meta["start"]["river_mile"], built=TODAY,
                  float_cfs=config.MIN_FLOAT_CFS,
                  wade_cfs=config.MARGINAL_FLOAT_CFS,
                  trip_month=config.TRIP_MONTH),
        river=river, camp_ok=camp_ok, tribal=tribal, trails=trail_out,
        tgaps=[dict(hi=float(r["rm_hi"]), lo=float(r["rm_lo"]),
                    mi=float(r["span_mi"])) for _, r in tgaps.iterrows()],
        launches=[pt(r["lon"], r["lat"], name=str(r["access_name"]),
                     agency=str(r["agency"]), rm=float(r["river_mile"]),
                     ramp=str(r.get("ramp", "")), state=str(r["state"]))
                  for _, r in acc.iterrows()],
        camps=[pt(r["lon"], r["lat"], name=str(r["name"]),
                  rm=float(r["river_mile"]), off=float(r["offset_m"]),
                  op=str(r.get("operator", "")), kind=str(r["kind"]))
               for _, r in camps.iterrows() if r["offset_m"] <= 1500],
        barriers=[pt(r["lon"], r["lat"], name=str(r["name"]),
                     rm=float(r["river_mile"]), kind=str(r["kind"]),
                     transit=str(r["transit"]), contact=str(r.get("contact", "")))
                  for _, r in barriers.iterrows()],
        gages=[pt(r["dec_long_va"], r["dec_lat_va"], site=str(r["site_no"]),
                  name=gage_label(r["station_nm"]), rm=float(r["river_mile"]),
                  med=(None if pd.isna(r["median_cfs_today"])
                       else float(r["median_cfs_today"])),
                  p25=(None if pd.isna(r.get("p25_cfs_today"))
                       else float(r["p25_cfs_today"])),
                  p75=(None if pd.isna(r.get("p75_cfs_today"))
                       else float(r["p75_cfs_today"])),
                  yrs=(None if pd.isna(r.get("years_of_record"))
                       else int(r["years_of_record"])))
               for _, r in gages.iterrows()],
        towns=[pt(r["lon"], r["lat"], name=str(r["name"]),
                  rm=float(r["river_mile"]), state=str(r["state"]))
               for _, r in towns.iterrows()],
    )
    return payload


TEMPLATE = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<title>Paddling the Allegheny — launches, camping and live flow by river mile</title>
<meta name="description" content="Where to put in, where you may legally camp, what the water is doing right now, and who to call — the Allegheny River from Coudersport to Pittsburgh, by river mile.">
<meta name="color-scheme" content="light dark">
<link rel="canonical" href="__SITE__">
<meta property="og:type" content="website">
<meta property="og:site_name" content="Paddling the Allegheny">
<meta property="og:title" content="Paddling the Allegheny">
<meta property="og:description" content="Launches, legal camping, live flow and who to ring — 312 miles from Coudersport to the Point at Pittsburgh, keyed to river mile.">
<meta property="og:url" content="__SITE__">
<meta property="og:image" content="__SITE__og.png">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta property="og:image:alt" content="The Allegheny River from Coudersport to Pittsburgh, drawn as a single line.">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="Paddling the Allegheny">
<meta name="twitter:description" content="Launches, legal camping, live flow and who to ring — by river mile.">
<meta name="twitter:image" content="__SITE__og.png">
<link rel="icon" href="data:image/svg+xml,%3Csvg xmlns=&apos;http://www.w3.org/2000/svg&apos; viewBox=&apos;0 0 32 32&apos;%3E%3Crect width=&apos;32&apos; height=&apos;32&apos; rx=&apos;7&apos; fill=&apos;%232d6b7c&apos;/%3E%3Cpath d=&apos;M7 9c4 0 4 4 8 4s4-4 8-4M7 16c4 0 4 4 8 4s4-4 8-4M7 23c4 0 4 4 8 4s4-4 8-4&apos; stroke=&apos;%23fff&apos; stroke-width=&apos;2.4&apos; fill=&apos;none&apos; stroke-linecap=&apos;round&apos;/%3E%3C/svg%3E">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600&family=IBM+Plex+Mono:wght@400;500&display=swap">
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.min.css"
  integrity="sha512-h9FcoyWjHcOcmEVkxOfTLnmZFWIH0iZhZT1H2TbOq55xssQGEJHEaIm+PgoUaZbRvQTNTluNOEfb1ZRy6D3BOw=="
  crossorigin="" referrerpolicy="no-referrer">
<style>
:root{
  --ground:#f6f5f1; --panel:#fffefb; --ink:#1b2023; --ink2:#5f6a70;
  --ink3:#8d979c; --rule:#dedbd3; --water:#2d6b7c; --ok:#3e7a4b;
  --warn:#a6433b; --band:#e7e4dc;
  --m-float:#2d6b7c; --m-wade:#bf8a2c; --m-drag:#a6433b;
  --launch:#2f6f95; --camp:#3e7a4b; --hazard:#a6433b; --gage:#7a5aa0;
  --trail:#3f6f86; --trail-soft:#a9c2cd; --trb:#8d6a86;
  --cty-pa:#dcd8ce; --cty-ny:#cfd6d8;
  --shadow:0 1px 2px rgba(20,25,30,.06),0 8px 24px rgba(20,25,30,.08);
}
@media (prefers-color-scheme:dark){:root{
  --ground:#15181b; --panel:#1c2125; --ink:#e8e6e0; --ink2:#a3adb2;
  --ink3:#6f797e; --rule:#2c3338; --water:#6ba8ba; --ok:#6aa878;
  --warn:#d9756b; --band:#232a2f;
  --m-float:#6ba8ba; --m-wade:#d9a441; --m-drag:#d9756b;
  --launch:#6fa6c8; --camp:#6aa878; --hazard:#d9756b; --gage:#a98fd0;
  --trail:#4d8098; --trail-soft:#33505e; --trb:#a4809c;
  --cty-pa:#272d31; --cty-ny:#20292d;
  --shadow:0 1px 2px rgba(0,0,0,.4),0 8px 24px rgba(0,0,0,.45);
}}
*{box-sizing:border-box}
html{-webkit-text-size-adjust:100%}
body{margin:0;background:var(--ground);color:var(--ink);
  font-family:"IBM Plex Sans",ui-sans-serif,system-ui,sans-serif;
  font-size:16px;line-height:1.6}
.wrap{max-width:900px;margin:0 auto;padding:0 16px}
a{color:var(--water)}
.mono{font-family:"IBM Plex Mono",ui-monospace,monospace;
  font-variant-numeric:tabular-nums}

/* ---------- header ---------- */
header{background:var(--panel);border-bottom:1px solid var(--rule);
  padding-block:22px 18px}
@media (max-width:640px){header{padding-block:16px 14px}
  header p{font-size:14.5px}
  section{padding-top:28px}}
h1{font-size:clamp(23px,5.2vw,32px);margin:0 0 6px;letter-spacing:-.02em}
header p{margin:0;color:var(--ink2);font-size:15px;max-width:62ch}

/* ---------- map ---------- */
.maprow{padding:14px 16px 0}
.mapbox{position:relative;max-width:1180px;margin:0 auto;
  border:1px solid var(--rule);border-radius:12px;overflow:hidden;
  box-shadow:var(--shadow);background:var(--panel)}
#map{height:min(70vh,660px);min-height:380px;width:100%;
  background:var(--band);z-index:0}
@media (max-width:640px){#map{height:64vh;min-height:340px}}
.leaflet-container{font-family:"IBM Plex Sans",sans-serif;
  background:var(--band)}
.leaflet-popup-content-wrapper,.leaflet-popup-tip{background:var(--panel);
  color:var(--ink);box-shadow:var(--shadow)}
.leaflet-popup-content{margin:12px 14px;line-height:1.5;font-size:13.5px}
.leaflet-popup-content b{font-size:14.5px}
.leaflet-bar a{background:var(--panel);color:var(--ink);
  border-bottom-color:var(--rule)}
.leaflet-bar a:hover{background:var(--band);color:var(--ink)}
.leaflet-control-attribution{background:rgba(255,255,255,.78)!important;
  color:var(--ink3)!important;font-size:10.5px}
@media (prefers-color-scheme:dark){
  .leaflet-control-attribution{background:rgba(20,24,27,.78)!important}
  .leaflet-control-attribution a{color:var(--ink2)!important}}

/* search + chips floating over the map */
.mapui{position:absolute;inset:10px 10px auto 10px;z-index:500;
  display:flex;flex-direction:column;gap:8px;pointer-events:none}
.searchwrap{position:relative;max-width:340px;pointer-events:auto}
#q{width:100%;padding:10px 34px 10px 13px;border-radius:9px;
  border:1px solid var(--rule);background:var(--panel);color:var(--ink);
  font:inherit;font-size:14.5px;box-shadow:var(--shadow)}
#q::placeholder{color:var(--ink3)}
#qclear{position:absolute;right:6px;top:50%;transform:translateY(-50%);
  border:0;background:none;color:var(--ink3);font-size:18px;cursor:pointer;
  padding:4px 6px;line-height:1}
#res{position:absolute;top:calc(100% + 5px);left:0;right:0;
  background:var(--panel);border:1px solid var(--rule);border-radius:9px;
  box-shadow:var(--shadow);max-height:46vh;overflow-y:auto;display:none}
#res button{display:block;width:100%;text-align:left;border:0;
  background:none;color:var(--ink);font:inherit;font-size:14px;
  padding:9px 13px;cursor:pointer;border-bottom:1px solid var(--rule)}
#res button:last-child{border-bottom:0}
#res button:hover,#res button.on{background:var(--band)}
#res .k{color:var(--ink3);font-size:11.5px;text-transform:uppercase;
  letter-spacing:.06em;margin-left:8px}
.chips{display:flex;flex-wrap:wrap;gap:6px;pointer-events:auto;
  padding-right:48px}
@media (max-width:700px){
  .chips{flex-wrap:nowrap;overflow-x:auto;scrollbar-width:none;
    padding-bottom:2px;-webkit-overflow-scrolling:touch}
  .chips::-webkit-scrollbar{display:none}
  .chip{flex:0 0 auto}
  .mapui{inset:8px 8px auto 8px;gap:7px}
  #q{padding:9px 32px 9px 12px;font-size:16px}
  /* drop the zoom and locate buttons below the search and chip row */
  .leaflet-top.leaflet-right{top:96px}
}
.chip{display:inline-flex;align-items:center;gap:6px;padding:6px 11px;
  border-radius:999px;border:1px solid var(--rule);background:var(--panel);
  color:var(--ink2);font-size:12.5px;cursor:pointer;box-shadow:var(--shadow);
  user-select:none}
.chip[aria-pressed="true"]{color:var(--ink);border-color:var(--ink3)}
.chip i{width:9px;height:9px;border-radius:50%;flex:0 0 9px;opacity:.28}
.chip[aria-pressed="true"] i{opacity:1}
.chip.line i{height:3px;border-radius:2px}
.maphint{padding:9px 14px;border-top:1px solid var(--rule);
  color:var(--ink3);font-size:12.5px;background:var(--panel)}
</style>
<style>
/* ---------- page sections ---------- */
section{padding-top:34px}
h2{font-size:21px;margin:0 0 6px;letter-spacing:-.01em}
h3{font-size:15.5px;margin:0 0 4px}
.lede{color:var(--ink2);margin:0 0 14px;max-width:64ch}
p,li{max-width:66ch}

/* live flow */
.flow{display:grid;gap:10px;
  grid-template-columns:repeat(auto-fill,minmax(212px,1fr))}
.g{background:var(--panel);border:1px solid var(--rule);border-radius:10px;
  padding:12px 13px}
.g .nm{font-size:13.5px;font-weight:500;line-height:1.35}
.g .rm{color:var(--ink3);font-size:11.5px;
  font-family:"IBM Plex Mono",monospace}
.g .now{font-family:"IBM Plex Mono",monospace;font-size:22px;
  margin:7px 0 1px;font-variant-numeric:tabular-nums}
.g .now s{text-decoration:none;font-size:12px;color:var(--ink3)}
.g .vs{font-size:12px;color:var(--ink2)}
.g .pill{display:inline-block;margin-top:7px;padding:2px 8px;
  border-radius:999px;font-size:11.5px;font-weight:500}
.p-ok{background:color-mix(in srgb,var(--ok) 16%,transparent);color:var(--ok)}
.p-lo{background:color-mix(in srgb,var(--m-wade) 20%,transparent);
  color:var(--m-wade)}
.p-hi{background:color-mix(in srgb,var(--warn) 16%,transparent);
  color:var(--warn)}
.p-na{background:var(--band);color:var(--ink3)}
.flownote{color:var(--ink3);font-size:12.5px;margin-top:10px}

/* cards */
.cards{display:grid;gap:12px;
  grid-template-columns:repeat(auto-fill,minmax(236px,1fr))}
.card{background:var(--panel);border:1px solid var(--rule);
  border-radius:10px;padding:14px}
.card p{margin:3px 0;font-size:13.5px}
.card .rm{color:var(--ink2);font-size:12.5px}
.card .q{color:var(--ink3);font-size:12px}
.tel{font-family:"IBM Plex Mono",monospace;font-size:15px;font-weight:500}
.cta{display:inline-block;margin-top:2px;padding:12px 18px;border-radius:9px;
  background:var(--water);color:#fff;text-decoration:none;font-weight:500;
  font-size:15px}
.cta:hover{filter:brightness(1.08)}

/* figure */
figure{margin:18px 0 0}
.figwrap{background:var(--panel);border:1px solid var(--rule);
  border-radius:10px;padding:14px}
.fig{display:block;width:100%;height:auto;overflow:visible}
.scrollx{overflow-x:auto;-webkit-overflow-scrolling:touch}
@media (max-width:880px){.scrollx .strip{min-width:860px}}
figcaption{color:var(--ink2);font-size:13px;margin-top:9px;padding-top:9px;
  border-top:1px solid var(--rule)}
.key{display:flex;flex-wrap:wrap;gap:5px 16px;font-size:12.5px;
  color:var(--ink2);margin:0 0 12px}
.key span{display:inline-flex;align-items:center;gap:6px;white-space:nowrap}
.key i{width:14px;height:9px;border-radius:2px;border:1px solid var(--rule)}
.strip text{font-family:"IBM Plex Sans",sans-serif}
.strip .band-bg{fill:var(--band)}
.strip .s-float{fill:var(--m-float)} .strip .s-wade{fill:var(--m-wade)}
.strip .s-drag{fill:var(--m-drag)}
.strip .s-camp{fill:var(--camp)} .strip .s-tribal{fill:var(--trb)}
.strip .s-cty-pa{fill:var(--cty-pa)} .strip .s-cty-ny{fill:var(--cty-ny)}
.strip .s-trail{fill:var(--trail)} .strip .s-trail-soft{fill:var(--trail-soft)}
.strip .t-trail{font-size:9px;fill:#fff}
.strip .t-nosteward{font-size:9px;fill:var(--ink3)}
.strip .t-trail-out{font-size:9px;fill:var(--trail);font-weight:600}
.strip .leader-t{stroke:var(--trail);stroke-width:1}
.strip .t-lane{font-size:9px;letter-spacing:.09em;fill:var(--ink3);
  font-weight:600}
.strip .t-cty{font-size:9px;fill:var(--ink2)}
.strip .t-strip-town{font-size:10px;fill:var(--ink2)}
.strip .tick-town{stroke:var(--rule);stroke-width:1}
.strip .b-dam{fill:var(--m-drag)} .strip .b-lock{fill:var(--ink3)}
.strip .t-call2{font-size:9.5px;font-weight:600;fill:var(--ink2)}
.strip .gapbar{stroke:var(--warn);stroke-width:2.2;stroke-linecap:round}
.strip .t-gap{font-size:9.5px;fill:var(--warn);font-weight:600}
.strip .axis{stroke:var(--ink3);stroke-width:.8}
.strip .t-axis{font-size:9px;fill:var(--ink3);
  font-family:"IBM Plex Mono",monospace}
.strip .t-axis-lab{font-size:9.5px;fill:var(--ink3)}

/* footer / the data */
.data{margin-top:44px;border-top:1px solid var(--rule);
  background:var(--panel)}
.data .wrap{padding-block:26px 44px}
.data h2{font-size:17px}
.dl{display:flex;flex-wrap:wrap;gap:10px;margin:12px 0 16px}
.btn{display:inline-flex;flex-direction:column;gap:1px;padding:11px 15px;
  border-radius:8px;text-decoration:none;border:1px solid var(--rule);
  background:var(--ground);color:var(--ink)}
.btn b{font-size:14px;font-weight:600}
.btn span{font-size:12px;color:var(--ink3)}
.tw{overflow-x:auto}
table{border-collapse:collapse;width:100%;font-size:13.5px;margin:10px 0;
  min-width:340px}
th,td{text-align:left;padding:6px 9px;border-bottom:1px solid var(--rule);
  vertical-align:top}
th{font-size:10.5px;text-transform:uppercase;letter-spacing:.08em;
  color:var(--ink3);font-weight:600}
td.n{text-align:right;font-family:"IBM Plex Mono",monospace;
  white-space:nowrap}
code{font-family:"IBM Plex Mono",monospace;font-size:.9em;
  background:var(--band);padding:1px 5px;border-radius:4px}
.fine{color:var(--ink3);font-size:12.5px}
</style>
</head>
<body>
<header><div class="wrap">
  <h1>Paddling the Allegheny</h1>
  <p>Where to put in, where you may lawfully camp, what the water is doing
  right now, and who to ring — from the source at Coudersport to the Point at
  Pittsburgh, keyed to river mile.</p>
</div></header>

<div class="maprow"><div class="mapbox">
  <div id="map"></div>
  <div class="mapui">
    <div class="searchwrap">
      <input id="q" type="search" autocomplete="off" spellcheck="false"
        placeholder="Search a town, launch or river mile…"
        aria-label="Search a town, launch, campground or river mile">
      <button id="qclear" hidden aria-label="Clear search">&times;</button>
      <div id="res" role="listbox"></div>
    </div>
    <div class="chips" id="chips"></div>
  </div>
  <div class="maphint">Tap anything for the detail. A green bank is one you
  may lawfully camp on &mdash; everything else is private or barred.</div>
</div></div>

<main class="wrap">

<section id="flow">
  <h2>What the water is doing</h2>
  <p class="lede">Live from the USGS gages on this river, fetched when you
  opened the page, next to what this river normally runs on today's date.
  Those medians come from decades of record and are baked in; the current
  reading is not.</p>
  <div class="flow" id="flowcards"></div>
  <p class="flownote" id="flownote">Fetching current readings…</p>
</section>

<section id="strip">
  <h2>The whole river on one line</h2>
  <p class="lede">Every mile of it, from the source on the left to Pittsburgh
  on the right.</p>
  <figure class="figwrap">
    <div class="key">
      <span><i style="background:var(--m-float)"></i>Floatable in July</span>
      <span><i style="background:var(--m-wade)"></i>Wadeable</span>
      <span><i style="background:var(--m-drag)"></i>Too low to float</span>
      <span><i style="background:var(--camp)"></i>Legal public camping</span>
      <span><i style="background:var(--trb)"></i>Seneca Nation — ask the
        Nation</span>
      <span><i style="background:var(--band)"></i>No lawful public
        campsite</span>
      <span><i style="background:var(--trail)"></i>Designated water trail</span>
      <span><i style="background:var(--trail-soft)"></i>Promoted reach</span>
    </div>
    <div class="scrollx">__STRIP__</div>
    <figcaption>Scroll it sideways on a phone; hover any band on a desktop.
    The camping band is the one that surprises people: about an eighth of this
    river has legal public dispersed camping reachable from the water, and
    three stretches over 25 miles have none at all.</figcaption>
  </figure>
</section>

<section id="stewards">
  <h2>Who to ring</h2>
  <p class="lede">A water trail grants nobody a right of access. What it gives
  you is a named body that signs the reach, keeps the launches open and will
  pick up the phone about a closed one. Pennsylvania's published mapping
  carries one of these four. <b>__NOSTEWARD__ river miles have no steward at
  all.</b></p>
  <div class="cards">
__STEWARDS__
  </div>
</section>

<section id="know">
  <h2>Three things to know before you go</h2>
  <div class="cards">
    <div class="card">
      <h3>The top of the river is a walk, not a paddle</h3>
      <p>At July median flow, __DRAGMI__ of the first __TOPUTIN__ miles below
      Coudersport are below floating depth — you are walking them, in the
      channel. The first public land where the river floats is State Game
      Land 301 at RM __PUTIN__. From there it is __FLOATMI__ miles of
      paddling.</p>
    </div>
    <div class="card">
      <h3>Kinzua Dam is a mandatory portage</h3>
      <p>No lockage, no passage, RM 200 — carry around it. The eight Locks
      &amp; Dams between RM 62 and the Point <em>do</em> lock recreational
      craft through, free: signal the lockmaster and wait your turn behind
      commercial traffic.</p>
    </div>
    <div class="card">
      <h3>34 miles run through the Seneca Nation</h3>
      <p>Between Salamanca and the state line the Allegany Territory is
      sovereign ground. The Nation, not a state agency, is the authority on
      access, camping and fishing there. Ask the Nation.</p>
    </div>
  </div>
</section>

<section id="gaps">
  <h2>Know a launch that is not on here?</h2>
  <p class="lede">This carries __NLAUNCH__ public launches and __NCAMP__
  campgrounds within a mile of the water, every one of them taken from state
  or federal mapping. <b>That mapping is incomplete and the people who
  steward these reaches know it.</b> Township ramps, club accesses and
  informal gravel bars turn over constantly and reach the state layers years
  late, if ever.</p>
  <p class="lede">If you know one that is missing, or one on here that is
  gone, send it. A town and a road name is enough — it gets snapped to the
  centerline and carries a river mile like everything else. Same for anything
  on this page you can see is wrong.</p>
  <p><a class="cta" href="__REPO__/issues/new?title=Launch%20or%20correction&amp;body=Where%20is%20it%20(town%2C%20road%2C%20or%20coordinates)%3A%0A%0AWhat%20kind%20of%20access%20is%20it%3A%0A%0AWho%20owns%20or%20maintains%20it%3A%0A%0AAnything%20else%3A%0A"
    rel="noopener">Send a launch or a correction &rarr;</a></p>
</section>

</main>

<div class="data"><div class="wrap">
  <h2>The data underneath</h2>
  <p class="fine">Everything above is drawn from one open dataset: 23 layers,
  EPSG:4326, keyed to river mile 0.0 at the mouth increasing upstream — the
  USACE Allegheny navigation convention. The centerline is the USGS NHDPlus
  High Resolution mainstem, 652 flowlines on one level path, measured
  geodesically; it validates against NHD's own mapped lock chambers to a mean
  absolute deviation of 0.049 mile.</p>
  <div class="dl">
    <a class="btn" href="map.html"><b>Full atlas map</b>
      <span>Every layer, toggled separately</span></a>
    <a class="btn" href="allegheny_river_atlas.gpkg" download>
      <b>GeoPackage</b><span>__SIZE__ MB · opens in QGIS</span></a>
    <a class="btn" href="DATA_DICTIONARY.md"><b>Data dictionary</b>
      <span>Layers, fields, provenance</span></a>
    <a class="btn" href="LICENSE.txt"><b>Licence</b>
      <span>CC BY 4.0 compilation</span></a>
  </div>
  <p class="fine">Camping classifications are an interpretation of published
  rules, not an agency determination. Flow bands are median estimates, not
  forecasts. Owner names and mailing addresses from county assessment records
  are not republished; parcel identifiers are, so anyone can make their own
  enquiry through the county office.</p>
  <p class="fine">Built __TODAY__. Sources: USGS (NHDPlus HR, NWIS, 3DEP,
  The National Map) · US EPA ATTAINS · USDA Forest Service · PA Fish &amp;
  Boat Commission, PA DCNR and PA Game Commission via PASDA · NYSDEC ·
  county assessment offices · OpenStreetMap contributors (ODbL) ·
  basemap © OpenStreetMap contributors, © CARTO. Compilation released under
  CC BY 4.0.</p>
</div></div>

<script src="https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.js"
  integrity="sha512-BwHfrr4c9kmRkLw6iXFdzcdWV/PGkVgiIyIWLLlTSXzWQzxuSg4DiQUCpauz/EWjgk5TYQqX/kvn9pG1NpYfqg=="
  crossorigin="" referrerpolicy="no-referrer"></script>
<script>
const D=__DATA__;

const M=D.meta;
const dark=matchMedia("(prefers-color-scheme: dark)");
const CV=n=>getComputedStyle(document.documentElement)
  .getPropertyValue(n).trim();

/* ---------- map ---------- */
const map=L.map("map",{zoomControl:false,scrollWheelZoom:false,
  tap:true,minZoom:6,maxZoom:17}).setView([41.3,-79.3],8);
L.control.zoom({position:"topright"}).addTo(map);
map.on("click",()=>map.scrollWheelZoom.enable());
map.on("mouseout",()=>map.scrollWheelZoom.disable());

const TILES={
  light:"https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png",
  dark:"https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png"};
const ATTR='&copy; <a href="https://www.openstreetmap.org/copyright">'+
  'OpenStreetMap</a> contributors, &copy; <a href="https://carto.com/attributions">CARTO</a>';
let base=null;
function setBase(){
  if(base) map.removeLayer(base);
  base=L.tileLayer(dark.matches?TILES.dark:TILES.light,
    {attribution:ATTR,subdomains:"abcd",maxZoom:19,detectRetina:true})
    .addTo(map);
  base.bringToBack();
}
setBase();
dark.addEventListener("change",()=>{setBase(); restyle();});

/* panes so the casings sit under the river and the pins on top */
["casing","river","pins"].forEach((n,i)=>{
  map.createPane(n); map.getPane(n).style.zIndex=400+i*10;});

const G={};                                   /* layer groups by key */
["trails","camping","river","launch","camp","hazard","gage","town"]
  .forEach(k=>G[k]=L.layerGroup());

const esc=s=>String(s??"").replace(/[&<>"]/g,c=>
  ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));
const rmTxt=rm=>`RM&nbsp;${rm.toFixed(1)}`;
const dirTo=(lat,lon)=>
  `<a href="https://www.openstreetmap.org/?mlat=${lat}&mlon=${lon}#map=15/${lat}/${lon}" `+
  `target="_blank" rel="noopener">Open location &rarr;</a>`;

/* ---------- geometry ---------- */
const MODE={float:"--m-float",wade:"--m-wade",drag:"--m-drag"};
const MODE_TXT={float:"Floatable at July median flow",
  wade:"Wadeable — too thin to float a loaded boat",
  drag:"Below wading flow — this is a carry"};
let paths=[];
function riverLines(){
  D.river.forEach(sg=>{
    const p=L.polyline(sg.pts,{pane:"river",color:CV(MODE[sg.mode]),
      weight:3.4,opacity:.95,lineJoin:"round"});
    p.bindPopup(`<b>${MODE_TXT[sg.mode]}</b><br>${rmTxt(sg.hi)}–${rmTxt(sg.lo)}`);
    paths.push([p,MODE[sg.mode]]); p.addTo(G.river);});
}
function campLines(){
  D.camp_ok.forEach(c=>{
    const p=L.polyline(c.pts,{pane:"casing",color:CV("--camp"),weight:9,
      opacity:.5,lineCap:"round"});
    p.bindPopup(`<b>${esc(c.name)}</b><br>${esc(c.desig)}<br>`+
      `${rmTxt(c.hi)}–${rmTxt(c.lo)}<br><br>${esc(c.rule)}`);
    paths.push([p,"--camp"]); p.addTo(G.camping);});
  D.tribal.forEach(t=>{
    const p=L.polyline(t.pts,{pane:"casing",color:CV("--trb"),weight:9,
      opacity:.5,lineCap:"round"});
    p.bindPopup(`<b>${esc(t.name)}</b><br>${rmTxt(t.hi)}–${rmTxt(t.lo)}`+
      `<br><br>Sovereign ground. The Nation, not a state agency, is the `+
      `authority on access, camping and fishing here.`);
    paths.push([p,"--trb"]); p.addTo(G.camping);});
}
function trailLines(){
  D.trails.forEach(t=>{
    const p=L.polyline(t.pts,{pane:"casing",color:CV("--trail"),weight:14,
      opacity:t.designated?.3:.16,lineCap:"round"});
    p.bindPopup(`<b>${esc(t.steward)}</b><br>${esc(t.name)}<br>`+
      `${rmTxt(t.hi)}–${rmTxt(t.lo)} · ${t.mi.toFixed(0)} mi<br>`+
      `<span style="color:var(--ink3)">${esc(t.status)}</span><br><br>`+
      `<a href="tel:${esc(t.phone)}">${esc(t.phone)}</a> · `+
      `<a href="${esc(t.url)}" target="_blank" rel="noopener">guide &rarr;</a>`+
      `<br><span style="color:var(--ink3)">${esc(t.addr)}</span>`);
    paths.push([p,"--trail"]); p.addTo(G.trails);});
}
function restyle(){paths.forEach(([p,v])=>p.setStyle({color:CV(v)}));}

/* ---------- markers ---------- */
function dot(o,color,r,pane){
  return L.circleMarker([o.lat,o.lon],{pane:pane||"pins",radius:r,
    color:"#fff",weight:1.6,fillColor:CV(color),fillOpacity:1});
}
const idx=[];   /* search index */
function addPoints(){
  D.launches.forEach(o=>{
    const m=dot(o,"--launch",6);
    m.bindPopup(`<b>${esc(o.name)}</b><br>Public launch · ${esc(o.agency)}`+
      `<br>${rmTxt(o.rm)}${o.ramp&&o.ramp!=="nan"?"<br>Ramp: "+esc(o.ramp):""}`+
      `<br><br>${dirTo(o.lat,o.lon)}`);
    m.addTo(G.launch); idx.push({n:o.name,k:"Launch",rm:o.rm,m:m,z:14});});
  D.camps.forEach(o=>{
    const m=dot(o,"--camp",5);
    m.bindPopup(`<b>${esc(o.name)}</b><br>Campground`+
      `${o.op&&o.op!=="nan"?" · "+esc(o.op):""}<br>${rmTxt(o.rm)}`+
      ` · ${(o.off/1609).toFixed(1)} mi from the water<br><br>${dirTo(o.lat,o.lon)}`);
    m.addTo(G.camp); idx.push({n:o.name,k:"Campground",rm:o.rm,m:m,z:14});});
  D.barriers.forEach(o=>{
    const dam=o.kind==="dam_portage";
    const m=L.circleMarker([o.lat,o.lon],{pane:"pins",radius:dam?8:6,
      color:"#fff",weight:1.8,fillColor:CV("--hazard"),fillOpacity:1});
    m.bindPopup(`<b>${esc(o.name)}</b><br>${rmTxt(o.rm)}<br><br>`+
      `${esc(o.transit)}`+
      (o.contact&&o.contact!=="nan"?`<br><br>${esc(o.contact)}`:""));
    m.addTo(G.hazard); idx.push({n:o.name,k:dam?"Portage":"Lock",rm:o.rm,m:m,z:13});});
  D.gages.forEach(o=>{
    const m=dot(o,"--gage",5);
    o._m=m; m.bindPopup(gagePopup(o));
    m.addTo(G.gage); idx.push({n:o.name,k:"USGS gage",rm:o.rm,m:m,z:13});});
  D.towns.forEach(o=>{
    const m=L.circleMarker([o.lat,o.lon],{pane:"pins",radius:3.4,
      color:CV("--ink3"),weight:1.4,fillColor:CV("--panel"),fillOpacity:1});
    m.bindPopup(`<b>${esc(o.name)}, ${esc(o.state)}</b><br>${rmTxt(o.rm)}`);
    m.addTo(G.town); idx.push({n:o.name,k:"Town",rm:o.rm,m:m,z:13});});
}
function gagePopup(o){
  const live=o._cfs==null?"":
    `<br><b style="font-size:17px">${Math.round(o._cfs).toLocaleString()} cfs</b>`+
    ` <span style="color:var(--ink3)">now</span>`+
    (o._ft!=null?`<br>${o._ft.toFixed(2)} ft gage height`:"");
  return `<b>${esc(o.name)}</b><br>${rmTxt(o.rm)}${live}`+
    (o.med!=null?`<br><span style="color:var(--ink3)">`+
      `${Math.round(o.med).toLocaleString()} cfs is the median for today`+
      (o.yrs?` over ${o.yrs} years`:"")+`</span>`:"")+
    `<br><br><a href="https://waterdata.usgs.gov/monitoring-location/${o.site}/"`+
    ` target="_blank" rel="noopener">USGS ${o.site} &rarr;</a>`;
}

riverLines(); campLines(); trailLines(); addPoints();

/* ---------- layer chips ---------- */
const CHIPS=[
  ["river","River",      "--m-float", true,  true],
  ["camping","Legal camping","--camp", true, true],
  ["launch","Launches",  "--launch",  true,  false],
  ["camp","Campgrounds", "--camp",    true,  false],
  ["hazard","Dams & locks","--hazard",true,  false],
  ["trails","Trail steward","--trail",true,  true],
  ["gage","Gages",       "--gage",    false, false],
  ["town","Towns",       "--ink3",    true,  false],
];
const chips=document.getElementById("chips");
CHIPS.forEach(([k,label,col,on,isLine])=>{
  const b=document.createElement("button");
  b.className="chip"+(isLine?" line":""); b.type="button";
  b.setAttribute("aria-pressed",on);
  b.innerHTML=`<i style="background:var(${col})"></i>${label}`;
  b.onclick=()=>{const v=b.getAttribute("aria-pressed")!=="true";
    b.setAttribute("aria-pressed",v);
    v?G[k].addTo(map):map.removeLayer(G[k]);};
  chips.appendChild(b);
  if(on) G[k].addTo(map);
});

/* fit to the river */
const bounds=L.latLngBounds([]);
D.river.forEach(s=>s.pts.forEach(p=>bounds.extend(p)));
map.fitBounds(bounds,{padding:[24,24]});

/* locate */
const Locate=L.Control.extend({options:{position:"topright"},
  onAdd(){const d=L.DomUtil.create("div","leaflet-bar");
    const a=L.DomUtil.create("a",'',d); a.href="#"; a.title="Where am I";
    a.innerHTML="&#9678;"; a.style.fontSize="17px";
    L.DomEvent.on(a,"click",e=>{L.DomEvent.stop(e);
      map.locate({setView:true,maxZoom:13});});
    return d;}});
map.addControl(new Locate());
map.on("locationfound",e=>L.circleMarker(e.latlng,{pane:"pins",radius:7,
  color:"#fff",weight:2,fillColor:CV("--water"),fillOpacity:1})
  .addTo(map).bindPopup("You are here").openPopup());
map.on("locationerror",()=>alert(
  "Could not get your location. Your browser may have blocked it."));

/* ---------- search ---------- */
const q=document.getElementById("q"), res=document.getElementById("res"),
      qclear=document.getElementById("qclear");
const norm=s=>s.toLowerCase().normalize("NFKD").replace(/[^a-z0-9 ]/g,"");
idx.forEach(o=>o._n=norm(o.n));
let hits=[], cur=-1;

function goto(o){
  res.style.display="none"; q.blur();
  const g=Object.entries(G).find(([,grp])=>grp.hasLayer(o.m));
  if(g&&!map.hasLayer(g[1])){
    g[1].addTo(map);
    const b=[...chips.children].find(c=>c.textContent.trim()===
      (CHIPS.find(c2=>c2[0]===g[0])||[])[1]);
    if(b) b.setAttribute("aria-pressed","true");
  }
  map.setView(o.m.getLatLng(),o.z,{animate:true});
  setTimeout(()=>o.m.openPopup(),260);
}
function gotoRM(rm){
  rm=Math.max(0,Math.min(rm,M.top_rm));
  /* interpolate along the reach that contains this mile */
  const sg=D.river.find(s=>rm<=s.hi&&rm>=s.lo)||D.river[0];
  const f=(sg.hi-rm)/Math.max(sg.hi-sg.lo,1e-6);
  const p=sg.pts[Math.min(Math.round(f*(sg.pts.length-1)),sg.pts.length-1)];
  res.style.display="none"; q.blur();
  map.setView(p,13,{animate:true});
  L.popup().setLatLng(p).setContent(
    `<b>River mile ${rm.toFixed(1)}</b><br>`+
    `<span style="color:var(--ink3)">0.0 is the mouth at Pittsburgh</span>`)
   .openOn(map);
}
function render(){
  if(!hits.length){res.style.display="none"; return;}
  res.innerHTML=hits.map((o,i)=>
    `<button role="option" data-i="${i}"${i===cur?' class="on"':""}>`+
    `${esc(o.n)}<span class="k">${esc(o.k)} · RM ${o.rm.toFixed(0)}</span>`+
    `</button>`).join("");
  res.style.display="block";
  [...res.children].forEach(b=>b.onclick=()=>goto(hits[+b.dataset.i]));
}
q.addEventListener("input",()=>{
  const v=q.value.trim(); qclear.hidden=!v; cur=-1;
  if(!v){hits=[]; res.style.display="none"; return;}
  const m=v.match(/^(?:rm\s*)?(\d{1,3}(?:\.\d)?)$/i);
  if(m&&+m[1]<=M.top_rm){
    hits=[]; res.innerHTML=`<button data-rm="${m[1]}">Go to river mile `+
      `${m[1]}<span class="k">River mile</span></button>`;
    res.style.display="block";
    res.firstChild.onclick=()=>gotoRM(parseFloat(m[1])); return;}
  const n=norm(v);
  hits=idx.filter(o=>o._n.includes(n))
    .sort((a,b)=>a._n.indexOf(n)-b._n.indexOf(n)||a.n.length-b.n.length)
    .slice(0,12);
  render();
});
q.addEventListener("keydown",e=>{
  if(e.key==="Escape"){q.value=""; hits=[]; res.style.display="none";
    qclear.hidden=true; return;}
  if(!hits.length) return;
  if(e.key==="ArrowDown"){cur=(cur+1)%hits.length; render(); e.preventDefault();}
  else if(e.key==="ArrowUp"){cur=(cur-1+hits.length)%hits.length; render();
    e.preventDefault();}
  else if(e.key==="Enter"&&cur>=0){goto(hits[cur]); e.preventDefault();}
  else if(e.key==="Enter"&&hits.length){goto(hits[0]); e.preventDefault();}
});
qclear.onclick=()=>{q.value=""; hits=[]; res.style.display="none";
  qclear.hidden=true; q.focus();};
document.addEventListener("click",e=>{
  if(!e.target.closest(".searchwrap")) res.style.display="none";});

/* ---------- live flow ---------- */
const cards=document.getElementById("flowcards"),
      note=document.getElementById("flownote");
function band(cfs,g){
  if(cfs==null) return ["p-na","no current reading"];
  if(cfs<M.wade_cfs) return ["p-hi","too low to float"];
  if(cfs<M.float_cfs) return ["p-lo","wadeable, not floatable"];
  if(g.p75!=null&&cfs>g.p75*2.5) return ["p-hi","running high"];
  return ["p-ok","floatable"];
}
function drawFlow(){
  cards.innerHTML=D.gages.map(g=>{
    const [cls,txt]=band(g._cfs,g);
    const pct=(g._cfs!=null&&g.med)?Math.round(g._cfs/g.med*100):null;
    return `<div class="g">
      <div class="nm">${esc(g.name)}</div>
      <div class="rm">RM ${g.rm.toFixed(1)}</div>
      <div class="now">${g._cfs!=null
        ?Math.round(g._cfs).toLocaleString()+' <s>cfs</s>'
        :'<s>—</s>'}</div>
      <div class="vs">${g.med!=null
        ?`median today ${Math.round(g.med).toLocaleString()} cfs`+
         (pct!=null?` · <b>${pct}%</b>`:"")
        :"no median on record"}</div>
      <span class="pill ${cls}">${txt}</span>
    </div>`;}).join("");
}
drawFlow();
const sites=D.gages.map(g=>g.site).join(",");
fetch("https://waterservices.usgs.gov/nwis/iv/?format=json&sites="+sites+
      "&parameterCd=00060,00065&siteStatus=all")
  .then(r=>r.ok?r.json():Promise.reject(r.status))
  .then(j=>{
    let newest=null;
    (j.value?.timeSeries||[]).forEach(ts=>{
      const site=ts.sourceInfo.siteCode[0].value;
      const code=ts.variable.variableCode[0].value;
      const v=ts.values?.[0]?.value?.[0];
      if(!v||v.value==="-999999") return;
      const g=D.gages.find(x=>x.site===site); if(!g) return;
      if(code==="00060") g._cfs=parseFloat(v.value);
      if(code==="00065") g._ft=parseFloat(v.value);
      if(v.dateTime&&(!newest||v.dateTime>newest)) newest=v.dateTime;});
    drawFlow();
    D.gages.forEach(g=>{if(g._m) g._m.setPopupContent(gagePopup(g));});
    const n=D.gages.filter(g=>g._cfs!=null).length;
    note.innerHTML=n
      ? `${n} of ${D.gages.length} gages reporting; latest reading `+
        new Date(newest).toLocaleString([], {dateStyle:"medium",
          timeStyle:"short"})+`. Source: USGS Water Services.`
      : "USGS returned no current readings just now.";
  })
  .catch(()=>{note.textContent=
    "Could not reach USGS for current readings — the medians above are "+
    "still this river's own, from decades of record.";});
</script>
</body>
</html>
"""


def main() -> None:
    common.banner("STEP 25 - the paddler landing page")
    DOCS.mkdir(exist_ok=True)
    payload = build_payload()
    figs = sitesvg.build()
    f = figs["facts"]
    trails = figs["trails"]

    gp = DOCS / "allegheny_river_atlas.gpkg"
    size_mb = gp.stat().st_size / 1024 / 1024 if gp.exists() else 0.0

    steward_cards = "\n".join(
        f'''    <div class="card">
      <h3>{r["steward"]}</h3>
      <p class="rm">RM {r["rm_hi"]:.0f}&ndash;{r["rm_lo"]:.0f}
        &middot; {r["span_mi"]:.0f} mi &middot; {r["name"]}</p>
      <p><a class="tel" href="tel:{r["steward_phone"]}">{r["steward_phone"]}</a></p>
      <p class="q">{r["steward_address"]}</p>
      <p><a href="{r["guide_url"]}" rel="noopener">Trail guide &rarr;</a></p>
    </div>''' for _, r in trails.iterrows())

    html = (TEMPLATE
            .replace("__DATA__", json.dumps(payload, separators=(",", ":")))
            .replace("__STRIP__", figs["strip"])
            .replace("__STEWARDS__", steward_cards)
            .replace("__SIZE__", f"{size_mb:.1f}")
            .replace("__FLOATMI__", f"{f['float_mi']:.0f}")
            .replace("__DRAGMI__", f"{f['drag_mi'] + f['wade_mi']:.0f}")
            .replace("__PUTIN__", f"{f['putin_rm']:.1f}")
            .replace("__TOPUTIN__",
                     f"{f['start_rm'] - f['putin_rm']:.0f}")
            .replace("__NOSTEWARD__", f"{f['trail_unstewarded_mi']:.0f}")
            .replace("__NLAUNCH__", str(len(payload["launches"])))
            .replace("__NCAMP__", str(len(payload["camps"])))
            .replace("__TODAY__", TODAY)
            .replace("__SITE__", SITE)
            .replace("__REPO__", REPO))
    out = DOCS / "index.html"
    out.write_text(html, encoding="utf-8")
    print(f"  wrote docs/index.html: {out.stat().st_size / 1024:.0f} KB")
    print(f"  {len(payload['launches'])} launches, {len(payload['camps'])} "
          f"campgrounds, {len(payload['gages'])} gages, "
          f"{len(payload['camp_ok'])} legal-camping reaches")


if __name__ == "__main__":
    main()
