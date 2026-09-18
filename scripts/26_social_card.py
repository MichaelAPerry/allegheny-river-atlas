#!/usr/bin/env python3
"""
Step 26 - the link preview card.

A link with no preview looks like spam. This river gets shared by text
message, in Messenger, in Facebook groups and in Slack, and every one of
those unfurls og:image - so the card is the first thing anyone sees of this
project, before they decide whether to tap.

Draws the river's own shape, which is the one image this project has that
nobody else's page has, and renders it to a 1200x630 PNG.

Rendering needs a browser. Playwright's chromium is used when it is present;
without it the step writes the card's HTML and says so, and the committed
og.png stays as it is - it only changes when the river does.

Outputs
  docs/og.html   the card source, for regenerating by hand if need be
  docs/og.png    1200x630, referenced by og:image
"""
from __future__ import annotations

import math
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
W, H = 1200, 630


def river_svg(ri, modes) -> str:
    """The river alone, rotated to fill a portrait panel, no labels."""
    river = gpd.read_file(config.PROC / "river_centerline.geojson")
    b = river.total_bounds
    lat0 = (b[1] + b[3]) / 2
    k = math.cos(math.radians(lat0))
    cx, cy = (b[0] + b[2]) / 2, (b[1] + b[3]) / 2

    # the route runs NNE to SSW; a small rotation squares it into the panel
    t = math.radians(18.0)
    cos_t, sin_t = math.cos(t), math.sin(t)

    def rot(lon, lat):
        x, y = (lon - cx) * k, lat - cy
        return x * cos_t - y * sin_t, x * sin_t + y * cos_t

    runs = sitesvg.mode_runs(modes)
    segs = []
    for hi, lo, mode in runs:
        g = (gpd.GeoSeries([ri.substring_between(hi, lo)], crs=config.GEO_CRS)
             .to_crs(config.METRIC_CRS).simplify(220.0)
             .to_crs(config.GEO_CRS).iloc[0])
        segs.append((mode, [rot(x, y) for x, y in g.coords]))

    xs = [p[0] for _, pts in segs for p in pts]
    ys = [p[1] for _, pts in segs for p in pts]
    # the panel must also hold the two end labels, so the line gets less
    # than the full width
    pw, ph = 470.0, 566.0
    padx, pady = 104.0, 30.0
    s = min((pw - 2 * padx) / (max(xs) - min(xs)),
            (ph - 2 * pady) / (max(ys) - min(ys)))
    ox = padx + (pw - 2 * padx - (max(xs) - min(xs)) * s) / 2
    oy = pady + (ph - 2 * pady - (max(ys) - min(ys)) * s) / 2

    def px(p):
        return (ox + (p[0] - min(xs)) * s, oy + (max(ys) - p[1]) * s)

    out = [f'<svg viewBox="0 0 {pw:.0f} {ph:.0f}" width="{pw:.0f}" '
           f'height="{ph:.0f}">']
    for mode, pts in segs:
        d = "M" + "L".join(f"{x:.1f},{y:.1f}" for x, y in map(px, pts))
        out.append(f'<path d="{d}" fill="none" stroke="var(--m-{mode})" '
                   f'stroke-width="7" stroke-linecap="round" '
                   f'stroke-linejoin="round"/>')
    # the two ends, the only marks the card can carry at thumbnail size
    # Coudersport sits top-right and Pittsburgh bottom-left, so each label
    # goes on its inboard side to stay inside the panel
    for pt, lab, ta, dy in (
            (px(rot(*sitesvg_end("start"))), "Coudersport", "end", -15.0),
            (px(rot(*sitesvg_end("end"))), "Pittsburgh", "start", 6.0)):
        out.append(f'<circle cx="{pt[0]:.1f}" cy="{pt[1]:.1f}" r="7.5" '
                   f'fill="var(--ink)" stroke="var(--ground)" '
                   f'stroke-width="3"/>')
        dx = -14 if ta == "end" else 14
        out.append(f'<text x="{pt[0] + dx:.1f}" y="{pt[1] + dy:.1f}" '
                   f'text-anchor="{ta}" font-size="20" font-weight="600" '
                   f'fill="var(--ink)">{lab}</text>')
    out.append("</svg>")
    return "\n".join(out)


_META = {}


def sitesvg_end(which: str):
    import json
    if not _META:
        _META.update(json.loads(
            (config.PROC / "river_geometry_meta.json").read_text()))
    e = _META[which]
    return e["lon"], e["lat"]


CARD = """<!doctype html>
<html><head><meta charset="utf-8">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600;700&family=IBM+Plex+Mono:wght@500&display=swap">
<style>
:root{--ground:#f6f5f1;--ink:#1b2023;--ink2:#5f6a70;--ink3:#8d979c;
  --m-float:#2d6b7c;--m-wade:#bf8a2c;--m-drag:#a6433b;--camp:#3e7a4b;
  --rule:#dedbd3;}
*{box-sizing:border-box;margin:0}
body{width:__W__px;height:__H__px;background:var(--ground);color:var(--ink);
  font-family:"IBM Plex Sans",sans-serif;display:flex;overflow:hidden}
.l{flex:1;padding:62px 0 52px 68px;display:flex;flex-direction:column;
  justify-content:center}
.kicker{font-size:17px;letter-spacing:.17em;text-transform:uppercase;
  color:var(--ink3);font-weight:600;margin-bottom:16px}
h1{font-size:66px;line-height:1.02;letter-spacing:-.025em;font-weight:600;
  margin-bottom:20px}
p{font-size:25px;line-height:1.36;color:var(--ink2);max-width:19ch}
.stats{display:flex;gap:40px;margin-top:34px}
.s b{display:block;font-family:"IBM Plex Mono",monospace;font-size:34px;
  font-weight:500;letter-spacing:-.02em}
.s span{font-size:14px;letter-spacing:.08em;text-transform:uppercase;
  color:var(--ink3);font-weight:600}
.r{width:490px;display:flex;align-items:center;justify-content:center;
  border-left:1px solid var(--rule)}
</style></head>
<body>
  <div class="l">
    <div class="kicker">Coudersport to Pittsburgh</div>
    <h1>Paddling the<br>Allegheny</h1>
    <p>Launches, legal camping, live flow and who to ring — by river mile.</p>
    <div class="stats">
      <div class="s"><b>__RM__</b><span>river miles</span></div>
      <div class="s"><b>__LAUNCH__</b><span>public launches</span></div>
      <div class="s"><b>__GAGE__</b><span>live gages</span></div>
    </div>
  </div>
  <div class="r">__RIVER__</div>
</body></html>
"""


def main() -> None:
    common.banner("STEP 26 - the link preview card")
    DOCS.mkdir(exist_ok=True)
    ri = riverindex.load()
    modes = pd.read_csv(config.PROC / "traverse_mode_by_rm.csv")
    acc = pd.read_csv(config.PROC / "access_points.csv")
    gages = pd.read_csv(config.PROC / "gage_current.csv", dtype={"site_no": str})

    river = river_svg(ri, modes)      # also populates _META
    html = (CARD.replace("__W__", str(W)).replace("__H__", str(H))
            .replace("__RIVER__", river)
            .replace("__RM__", f"{_META['start']['river_mile']:.0f}")
            .replace("__LAUNCH__",
                     str(acc.drop_duplicates(subset=["river_mile"]).shape[0]))
            .replace("__GAGE__", str(len(gages))))
    card = DOCS / "og.html"
    card.write_text(html, encoding="utf-8")

    png = DOCS / "og.png"
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("  playwright not installed - wrote docs/og.html only; "
              f"{'og.png is unchanged' if png.exists() else 'og.png MISSING'}")
        return
    exe = Path("/opt/pw-browsers/chromium")
    with sync_playwright() as pw:
        b = pw.chromium.launch(executable_path=str(exe) if exe.exists()
                               else None)
        pg = b.new_page(viewport={"width": W, "height": H},
                        device_scale_factor=1)
        pg.goto(card.resolve().as_uri())
        pg.wait_for_timeout(1400)
        pg.screenshot(path=str(png))
        b.close()
    print(f"  wrote docs/og.png  {W}x{H}  "
          f"{png.stat().st_size / 1024:.0f} KB")


if __name__ == "__main__":
    main()
