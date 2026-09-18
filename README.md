# Allegheny River Atlas

An open GIS dataset of the Allegheny River from its source in Potter County,
Pennsylvania to the Point at Pittsburgh — **camping legality, public-land
frontage, water quality and access, indexed by river mile**.

**→ [Browse the dataset](https://michaelaperry.github.io/allegheny-river-atlas/)**

`docs/allegheny_river_atlas.gpkg` — one OGC GeoPackage, 22 layers, EPSG:4326,
3 MB. Drag it into QGIS. Works in ArcGIS Pro, R `sf`, `geopandas`, GDAL/OGR.

## Why this exists

The Allegheny is well mapped as a *line* and poorly mapped as a *place you are
allowed to be*. This dataset answers the second question.

Three findings drove the rest of it:

- **Only about 12% of the river has legal public dispersed camping.** Three
  separate stretches longer than 25 miles have none of any kind reachable from
  the water — the longest runs 107 miles.
- **Inside the Allegheny National Forest proclamation boundary, less than half
  the river frontage is actually federal land.** Of 94 frontage miles, 44 are
  federal and 50 are private inholdings that read as National Forest on a
  general-purpose map.
- **Roughly 175 river miles — over half the route — carry a "Not Supporting"
  water-quality status** in EPA ATTAINS.

## The river-mile convention

Everything is keyed to **river mile 0.0 at the mouth, increasing upstream** —
the USACE Allegheny navigation convention. Coudersport is RM 312.2. Every layer
carries a `river_mile`, or an upstream/downstream pair, so any two layers join
on position without a spatial operation.

The centerline is the USGS NHDPlus High Resolution mainstem: 652 flowlines on a
single level path with an unbroken FromNode/ToNode chain, measured geodesically
on the WGS 84 ellipsoid. It validates against NHD's own mapped lock chambers to
a **mean absolute deviation of 0.049 mile**.

## Seven layers that exist nowhere else

These were river-mile span tables — the analytical output — cut from the
centerline into real geometry so they can be mapped and intersected:

| Layer | What it is |
|---|---|
| `river_camping_legality` | Every public tract's frontage, classified against that jurisdiction's actual camping rules |
| `river_public_land_frontage` | Measured along-channel frontage per tract, federal ownership only |
| `river_traverse_mode` | Estimated median discharge applied to drainage area: drag / wade / float |
| `river_water_quality` | EPA ATTAINS impairment, merged and clipped to the mainstem |
| `river_fishing_regulations` | PFBC regulation sections as river geometry |
| `river_fish_advisories` | Consumption advisory extents |
| `river_drone_restrictions` | Wilderness Act §4(c) applied to wilderness boundaries |

See [`docs/DATA_DICTIONARY.md`](docs/DATA_DICTIONARY.md) for every layer, field
meanings, provenance and stated limitations.

## What is deliberately not here

The working dataset identifies riparian parcels along stretches with no lawful
public campsite, and for two counties those records carry owner names and home
mailing addresses. **Those are not republished here.** They are public records,
and looking one up to write and ask a landowner for permission is
proportionate; aggregating them onto the open web under a heading about where
to camp is not. Parcel identifiers, county and municipality are included, so
anyone can make their own enquiry through the county assessment office.

## Limitations — read before relying on it

1. **Camping classifications are an interpretation** of published rules, not an
   agency determination.
2. **Flow-derived layers are median estimates**, interpolated from unit runoff
   between gages. Not measurements, not a forecast.
3. **34.8 miles run through the Seneca Nation's Allegany Territory**, where the
   Nation — not a state agency — is the authority. The boundary is included;
   the rules that apply inside it are not state rules.
4. **No New York public land fronts the centerline** anywhere in the corridor,
   and NYSDEC publishes no designated-launch layer for the Cattaraugus reach.
   That is a finding, not an omission.
5. **Campground coverage is uneven** — agency layers cover the National Forest
   well and the private sector barely.

## Licence

The compilation is **CC BY 4.0**. Underlying data remains under its own terms
and must be attributed: USGS · US EPA · USDA Forest Service · PA Fish & Boat
Commission, PA DCNR and PA Game Commission via PASDA · NYSDEC · county
assessment offices · **OpenStreetMap contributors (ODbL)** for the campground
and Kinzua portage layers. See [`LICENSE`](LICENSE).

## Rebuilding it

Both scripts in `scripts/` rebuild the package from the full pipeline in the
source project. Nothing here is hand-digitised and no figure is hand-entered.
