# GeoLinkage

## Help
- Grass Console: (or  *File -> Launch Script*)
```
    v.geolinkage.py --help
```

- Terminal:
```bash
    python3.12 CmdInterface.py -h
```

## Examples
### Azapa example with MODFLOW model (*-g option*) and GeoCheck option (*-c option*):

```bash
python3 CmdInterface.py
  -g 
  -c
  --linkage_in_folder=./examples/azapa/linkage
  --gw_model=./examples/azapa/gw/model/mf2005.nam
  --linkage_out_folder=./examples/azapa/out
  --node=./examples/azapa/weap/WEAPNode.shp
  --arc=./examples/azapa/weap/WEAPArc.shp
  --epsg_code=32719
  --catchment=./examples/azapa/catchment/Catchments_v1.shp
  --gw=./examples/azapa/gw/GW_para_linkage_v1.shp
  --ds_folder=./examples/azapa/ds
  --zrotation=0.0
  --coords_ll=100,100
  --geo_check_folder=./examples/azapa/check_results
```

### Azapa example without MODFLOW model and without Geocheck

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