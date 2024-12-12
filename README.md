# GeoLinkage
GeoLinkage is a GRASS GIS plugin that automates the creation of linkage files for WEAP-MODFLOW integrated models.

It receives Shapefile maps containing the information for Catchments, Groundwater and Demand Sites, and overlays them over an empty linkage file provided by the user, or obtained directly from the MODFLOW model with FloPy.

It also receives the WEAP arcs and nodes in Shapefile format, and checks the consistency with the maps.

The newest update added a GeoChecker module, meant to check restrictions over the resulting Linkage file, currently checks if a superposition in one or more cells of Groundwater-Catchment and Groundwater-DemandSite is corresponded by a link in the WEAP model.

For more information about the installation process and use of GeoLinkage checkout the GeoLinkage official Manual.

## Use restrictions

Currently only available for Linux machines.

Not useful for unstructured grid subterranean models (e.g. MODFLOW USG).

## Relevant links
Showcase video:
Still not uploaded.

How to Geolinkage video:
Still not uploaded.

GeoLinkage Manual:
Still not uploaded.

## Help
- Grass Console: (or  *File -> Launch Script*)
```
    v.geolinkage.py --help
```

- Terminal:
```bash
    python3 CmdInterface.py -h
```

## Examples
### Azapa example with MODFLOW model (*-g option*):

```bash
python3 CmdInterface.py
  -g
  --linkage_in_folder=./examples/azapa/linkage
  --gw_model=./examples/azapa/gw/modflow_model/model/mf2005.nam
  --linkage_out_folder=./examples/azapa/out
  --node=./examples/azapa/weap/WEAPNode.shp
  --arc=./examples/azapa/weap/WEAPArc.shp
  --epsg_code=32719
  --catchment=./examples/azapa/catchment/Catchments_v1.shp
  --gw=./examples/azapa/gw/GW_para_linkage_v1.shp
  --ds_folder=./examples/azapa/ds
  --zrotation=0.0
  --coords_ll=100,100
```

### Azapa example without MODFLOW model:

```bash
python3 CmdInterface.py
  --linkage_in=./examples/azapa/linkage/linkage_in.shp
  --linkage_out_folder=./examples/azapa/out
  --node=./examples/azapa/weap/WEAPNode.shp
  --arc=./examples/azapa/weap/WEAPArc.shp
  --epsg_code=32719
  --catchment=./examples/azapa/catchment/Catchments_v1.shp
  --gw=./examples/azapa/gw/GW_para_linkage_v1.shp
  --ds_folder=./examples/azapa/ds
```
