# Allegheny River Atlas — Data Dictionary

`allegheny_river_atlas.gpkg` — OGC GeoPackage, **EPSG:4326 (WGS 84)**, 21 spatial layers plus a metadata table. Compiled 2026-09-18.

Opens directly in QGIS (drag the file in), ArcGIS Pro, R (`sf`), Python (`geopandas`) and GDAL/OGR. One file, no dependencies, no projection guessing.

## The convention everything is keyed to

**River mile 0.0 is the mouth at Point State Park, Pittsburgh, increasing upstream** — the USACE Allegheny navigation convention. Coudersport is RM 312.2. Every layer in this package carries a `river_mile`, or a `river_mile_upstream` / `river_mile_downstream` pair, so any two layers can be joined on position along the river without a spatial operation.

The centerline is the USGS NHDPlus High Resolution mainstem: 652 flowlines on a single level path with an unbroken FromNode/ToNode chain. Mileage is geodesic on the WGS 84 ellipsoid. The index validates against NHD's own mapped lock chambers to a **mean absolute deviation of 0.049 mile** through the locked reach. Above RM 62 the high-resolution trace resolves roughly 1% more sinuosity than historic chart mileage, so computed and published river miles diverge by about two miles at Kinzua Dam; the `barriers` layer carries both.

## Layers

| Layer | Features | Geometry | Source |
|---|---:|---|---|
| `river_centerline` | 1 | LineString | USGS |
| `public_lands` | 72 | MultiPolygon | USFS / PA DCNR / PGC / PFBC / NYSDEC |
| `barriers` | 9 | Point | USACE / USGS |
| `access_points` | 16 | Point | PA Fish & Boat Commission / NYSDEC |
| `gages` | 14 | Point | USGS |
| `campgrounds` | 84 | Point | USFS / USGS TNM / NYSDEC / OpenStreetMap |
| `nightly_stops` | 24 | Point | derived |
| `towns` | 39 | Point | USGS |
| `water_trails` | 1 | LineString | PA Fish & Boat Commission |
| `kinzua_portage_route` | 1 | LineString | OpenStreetMap + USGS 3DEP |
| `river_traverse_mode` | 3 | LineString | derived |
| `river_camping_legality` | 113 | LineString | derived |
| `river_public_land_frontage` | 113 | LineString | USFS / PA DCNR / PGC / PFBC / NYSDEC |
| `river_water_quality` | 24 | LineString | US EPA |
| `river_fishing_regulations` | 89 | LineString | PA Fish & Boat Commission |
| `river_drone_restrictions` | 8 | LineString | derived |
| `river_fish_advisories` | 3 | LineString | PA DEP / PFBC |
| `river_counties` | 10 | LineString | USGS |
| `hospitals` | 63 | Point | USGS |
| `riparian_parcels` | 52 | Point | County assessment offices |
| `river_mile_markers` | 65 | Point | derived |

### What the derived line layers are

Seven layers exist only because this project made them. They were river-mile span *tables* with no geometry — the analytical output of the pipeline — and they have been cut from the centerline into real LineStrings so they can be mapped and intersected:

* **`river_camping_legality`** — every public tract's river frontage, classified against that jurisdiction's actual camping rules. This is the layer nobody else has.
* **`river_public_land_frontage`** — measured along-channel frontage per tract, not centroid proximity. National Forest frontage is filtered to federal ownership, excluding the inholdings that make up over half the proclamation boundary on this river.
* **`river_traverse_mode`** — estimated median discharge applied to NHD drainage area, classified into drag / wade / float.
* **`river_water_quality`** — EPA ATTAINS impairment, merged to non-overlapping blocks and clipped to the mainstem.
* **`river_fishing_regulations`**, **`river_fish_advisories`**, **`river_drone_restrictions`**, **`river_counties`** — regulatory extents expressed as river geometry.

## Field conventions

| Field | Meaning |
|---|---|
| `river_mile` | Distance from the mouth at Point State Park, statute miles, increasing upstream (USACE convention) |
| `river_mile_upstream` | Upstream end of the span, river miles from the mouth |
| `river_mile_downstream` | Downstream end of the span, river miles from the mouth |
| `length_mi` | Along-channel length of the span, statute miles |
| `offset_from_centerline_m` | Perpendicular distance from the NHD centerline, metres |
| `median_discharge_cfs` | Estimated median discharge, cubic feet per second |
| `drainage_area_sqmi` | Upstream drainage area, square miles |
| `traverse_mode` | drag (<70 cfs), wade (70-120), float (>=120) - the in-channel travel mode implied by estimated flow |
| `camping_class` | Camping rule class for the managing jurisdiction |
| `camping_legal` | True where dispersed camping is permitted |
| `epa_ir_category` | EPA Integrated Report category; 5 = impaired and needing a TMDL, 4C = impaired by a non-pollutant |

Every layer also carries `source_agency`, `source_dataset`, `source_licence` and `retrieved`, and the same information is in the `dataset_metadata` table.

## Provenance and terms

| Layer | Dataset | Terms |
|---|---|---|
| `river_centerline` | NHDPlus High Resolution, NetworkNHDFlowline | US Government work, public domain |
| `public_lands` | Ownership and boundary polygons | Public agency data; check each agency |
| `barriers` | Published navigation river miles, cross-checked against NHD lock chambers | US Government work, public domain |
| `access_points` | PFBC Access and Properties; NYSDEC boat launches | PASDA and NYSDEC terms |
| `gages` | NWIS site and instantaneous-values services | US Government work, public domain |
| `campgrounds` | Recreation sites, TNM Structures, OSM camp_site | Mixed; OSM portion is ODbL |
| `nightly_stops` | Output of the pacing model | Derived |
| `towns` | The National Map, geonames incorporated places | US Government work, public domain |
| `water_trails` | Water Trails, via PASDA | PASDA terms; attribution required |
| `kinzua_portage_route` | OSM highway network, USGS elevation | OSM: ODbL, attribution required |
| `river_traverse_mode` | USGS daily-median discharge applied to NHD drainage area | Derived |
| `river_camping_legality` | Agency land layers classified against published camping rules | Derived |
| `river_public_land_frontage` | Ownership and boundary layers | Public agency data; check each agency |
| `river_water_quality` | ATTAINS Assessment Lines | US Government work, public domain |
| `river_fishing_regulations` | Fisheries All Sections, via PASDA | PASDA terms; attribution required |
| `river_drone_restrictions` | Wilderness Act s.4(c) applied to USFS Wilderness boundaries | Derived |
| `river_fish_advisories` | Fish consumption advisory tables | Public health guidance; verify before use |
| `river_counties` | The National Map, govunits | US Government work, public domain |
| `hospitals` | The National Map, structures | US Government work, public domain |
| `riparian_parcels` | Potter, Forest, Butler, Warren, Venango, Allegheny, Westmoreland, NYSDEC tax parcels | Public records; owner names are assessment data |
| `river_mile_markers` | Computed from the NHD centerline | Derived; same terms as source |

**Attribution that must travel with this data:** USGS (NHDPlus HR, NWIS, The National Map, 3DEP), US EPA (ATTAINS), USDA Forest Service (EDW), Pennsylvania Fish & Boat Commission, PA DCNR and PA Game Commission via **PASDA**, NYSDEC, and **OpenStreetMap contributors (ODbL)** for the campground and portage-route layers.

## Known limitations — read before using

1. **Camping classifications are an interpretation**, not an agency determination. They encode published rules per jurisdiction as of compilation. Verify before relying on them.
2. **`riparian_parcels` positions are approximate.** Parcel records are real and carry their county parcel identifier, but each is placed at its river mile on the centerline rather than at its true parcel centroid. Owner names are public assessment records and only Potter and Forest counties publish them; McKean, Armstrong and Clarion publish no reachable parcel service at all.
3. **New York coverage is thin and that is a real finding**, not an omission: no NY public land fronts the centerline anywhere in the corridor, and NYSDEC publishes no designated-launch layer for the Cattaraugus reach.
4. **34.8 miles run through the Seneca Nation's Allegany Territory**, where the Nation, not a state agency, is the authority. The boundary is included; the rules that apply inside it are not state rules.
5. **Flow-derived layers are median estimates**, interpolated from unit runoff between gages. They are not measurements and not a forecast.
6. **Campground coverage is uneven** — agency layers cover the National Forest well and the private sector barely; the OSM portion is volunteer-maintained.

## Reproducing it

Everything here is rebuilt from public services by `python3 scripts/run_all.py`, about ten minutes end to end. No layer is hand-digitised and no figure is hand-entered.

