# Allegheny River Atlas — Data Dictionary

`allegheny_river_atlas.gpkg` — OGC GeoPackage, **EPSG:4326 (WGS 84)**, 22 spatial layers plus a metadata table. Compiled 2026-09-18.

Open the GeoPackage in QGIS, ArcGIS Pro, or another GIS that supports the format.

## River miles

River mile 0 is the mouth at Point State Park, Pittsburgh. Miles increase upstream. The trip maps begin near Coudersport at mile 312.2. The GeoPackage centerline covers 322.579 miles. Most river features carry a point mile or the endpoints of a span. The layer schema also uses fields such as `end_river_mile` for itinerary stops. Use the relevant mile fields to compare locations and overlapping reaches.

The centerline follows 652 USGS NHDPlus High Resolution flowlines on one connected path. Distance is measured geodesically on WGS 84. The atlas records a mean absolute difference of 0.049 mile against mapped NHD lock chambers. The five rounded comparisons in `barriers.nhd_crosscheck_delta_mi` average 0.050 mile. At Kinzua Dam, `barriers` records a computed mile of 200.05 and a published navigation mile of 197.9.

## Layers

`dataset_metadata` is a nonspatial table with one record for each of the 22 spatial layers.

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
| `water_trails` | 4 | LineString | PA Fish & Boat Commission (mapped extent) + each steward's own published material |
| `kinzua_portage_route` | 1 | LineString | OpenStreetMap + USGS 3DEP |
| `river_traverse_mode` | 3 | LineString | derived |
| `river_camping_legality` | 113 | LineString | derived |
| `river_public_land_frontage` | 113 | LineString | USFS / PA DCNR / PGC / PFBC / NYSDEC |
| `river_water_quality` | 24 | LineString | US EPA |
| `river_fishing_regulations` | 89 | LineString | PA Fish & Boat Commission |
| `river_drone_restrictions` | 8 | LineString | derived |
| `river_fish_advisories` | 3 | LineString | PA DEP / PFBC |
| `river_counties` | 10 | LineString | USGS |
| `water_trail_gaps` | 3 | LineString | Derived |
| `hospitals` | 63 | Point | USGS |
| `riparian_parcels` | 52 | Point | County assessment offices |
| `river_mile_markers` | 65 | Point | derived |

### River reach layers

The reach layers represent spans along the centerline. A frontage line identifies a stretch of river next to a tract. Use the land polygons to inspect the tract boundaries.

- `river_camping_legality` gives the camping classification and a rule summary for each mapped span. Overlapping spans can represent different tracts along the same reach. Combining overlapping spans where `camping_legal = 1` gives 37.41 miles, about 12% of the Coudersport-to-Pittsburgh route.
- `river_public_land_frontage` measures frontage along the channel. National Forest frontage uses federal ownership polygons. Designated wilderness is listed separately.
- `river_traverse_mode` classifies stretches by estimated July median flow.
- `river_water_quality` shows EPA ATTAINS assessment spans clipped to the mainstem. The 24 published spans total 175.39 miles and all carry “Not Supporting.”
- `river_fishing_regulations`, `river_fish_advisories`, `river_drone_restrictions` and `river_counties` locate rules, advisories and boundaries along the river.

## Field conventions

| Field | Meaning |
|---|---|
| `river_mile` | Distance from the mouth at Point State Park, statute miles, increasing upstream (USACE convention) |
| `river_mile_upstream` | Upstream end of the span, river miles from the mouth |
| `river_mile_downstream` | Downstream end of the span, river miles from the mouth |
| `length_mi` | Along-channel length of the span, statute miles |
| `offset_from_centerline_m` | Distance from the NHD centerline in meters |
| `median_discharge_cfs` | Estimated median discharge, cubic feet per second |
| `drainage_area_sqmi` | Upstream drainage area, square miles |
| `traverse_mode` | Model category based on estimated flow: drag below 70 cfs, wade from 70 to below 120 cfs, float at 120 cfs or more |
| `camping_class` | Camping rule class for the managing jurisdiction |
| `camping_legal` | Atlas flag for a span classified as allowing dispersed camping |

Each spatial layer carries `source_agency`, `source_dataset`, `source_licence` and `retrieved`, and the same information is in the `dataset_metadata` table.

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
| `water_trails` | Water Trails via PASDA; trail stewards’ published material | PASDA terms; attribution required |
| `kinzua_portage_route` | OSM highway network, USGS elevation | OSM: ODbL, attribution required |
| `river_traverse_mode` | USGS daily-median discharge applied to NHD drainage area | Derived |
| `river_camping_legality` | Agency land layers classified against published camping rules | Derived |
| `river_public_land_frontage` | Ownership and boundary layers | Public agency data; check each agency |
| `river_water_quality` | ATTAINS Assessment Lines | US Government work, public domain |
| `river_fishing_regulations` | Fisheries All Sections, via PASDA | PASDA terms; attribution required |
| `river_drone_restrictions` | Wilderness Act s.4(c) applied to USFS Wilderness boundaries | Derived |
| `river_fish_advisories` | Fish consumption advisory tables | Public health guidance; verify before use |
| `river_counties` | The National Map, govunits | US Government work, public domain |
| `water_trail_gaps` | Reaches no water trail covers | CC BY 4.0 |
| `hospitals` | The National Map, structures | US Government work, public domain |
| `riparian_parcels` | Potter, Forest, Butler, Warren, Venango, Allegheny, Westmoreland, NYSDEC tax parcels | Public assessment records. The atlas publishes parcel identifiers. |
| `river_mile_markers` | Computed from the NHD centerline | Derived; same terms as source |

**Source attribution**

 USGS (NHDPlus HR, NWIS, The National Map, 3DEP), US EPA (ATTAINS), USDA Forest Service (EDW), Pennsylvania Fish & Boat Commission, PA DCNR and PA Game Commission via **PASDA**, NYSDEC, and **OpenStreetMap contributors (ODbL)** for the campground and portage-route layers.

See the [license](LICENSE.txt) for compilation and source terms.

## Coverage and limits

- Camping classifications reflect the published rules available at compilation. **This is not legal advice. Check current regulations and permit requirements with the managing agency or nation before camping.**
- Parcel points are placed on the centerline at the associated river mile. Use the parcel identifier and county assessment records to locate the tract. County coverage varies.
- The atlas shows the Seneca Nation’s Allegany Territory along about 34.8 river miles. Check with the Nation about access, camping and fishing within its territory.
- Launch and campground inventories are incomplete, including in New York. Campground distances are offsets from the centerline. Confirm access and availability before traveling.
- The flow bands use estimated medians interpolated between gages. Check current conditions separately.
