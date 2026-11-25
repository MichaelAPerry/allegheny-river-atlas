# Allegheny River Atlas

The Allegheny River Atlas is an open GIS dataset covering the river from its headwaters in Potter County, Pennsylvania, to the Point in Pittsburgh. I compiled it for paddlers and campers looking for access and overnight options, and for anglers and planners who need river-mile data on water quality, public land, or fishing regulations.

## Use the maps

- [Paddling the Allegheny](https://michaelaperry.github.io/allegheny-river-atlas/) is the online trip map, starting at Coudersport. Search for a town, launch, campground, or river mile. Select a feature for details. The basemap and current USGS gage readings require a connection.
- [Offline river map](https://michaelaperry.github.io/allegheny-river-atlas/map.html) shows selected atlas layers. Save `map.html` and open it in a browser. Drag to pan, use the zoom buttons, and use the layer checkboxes to choose what to display. Select a marker or a trail segment for details. The map works from that one file. Links to guides and downloads require a connection.

[Report a missing launch or a correction](https://github.com/MichaelAPerry/allegheny-river-atlas/issues/new?title=Launch%20or%20correction). A road name and town or coordinates will help me locate it.

## Get the data

[Download the GeoPackage](docs/allegheny_river_atlas.gpkg) and open it in QGIS, ArcGIS Pro, or another GIS that reads GeoPackage. The file has 22 spatial layers and one metadata table in a single package. Spatial layers use WGS 84 (EPSG:4326). The [data dictionary](docs/DATA_DICTIONARY.md) lists the layers, fields, and sources.

River miles increase upstream from mile 0 at the mouth in Pittsburgh. The trip maps begin near Coudersport at mile 312.2. The GIS centerline extends farther upstream and measures 322.579 miles. It follows 652 USGS NHDPlus High Resolution flowlines. The atlas records a mean absolute difference of 0.049 mile against mapped NHD lock chambers. The five published lock comparisons round to a mean of 0.050 mile. At Kinzua Dam, the atlas mile is 200.05 and the published navigation mile is 197.9.

## What the data shows

- The atlas classifies about **12% of the Coudersport-to-Pittsburgh route** as having public frontage where dispersed camping is permitted. That is 37.41 river miles after combining overlapping spans.
- The EPA ATTAINS layer records **175.39 river miles as “Not Supporting”** in the September 2026 compilation.
- Four water-trail reaches are recorded in the atlas. About **71 miles** of the trip route fall outside those reaches.
- The frontage layer records about **44 miles** under the National Forest designation and lists designated wilderness separately. Check mapped ownership before using land within the broader forest boundary.

## Limits and attribution

Camping classifications reflect my reading of the published rules at compilation. **This is not legal advice. Check current regulations, access and any permit requirements with the land manager before camping.** About 34.8 river miles cross the Seneca Nation’s Allegany Territory. Check with the Nation about access, fishing and camping there.

The travel bands use estimated July median flows. Check current conditions before a trip. Launch and campground coverage varies by area. A campground marker shows its location and distance from the river. Confirm access from the water with the operator. The parcel layer includes parcel identifiers and approximate locations along the river.

The [license](LICENSE) covers the compilation and attribution. The derived layers are released under CC BY 4.0. Source data retains its own terms, including ODbL for the OpenStreetMap contributions to campground and portage data. The data dictionary lists the source for each layer.

The scripts in `scripts/` are the packaging and publication stages. They depend on processed files and helper modules from the full source project.
