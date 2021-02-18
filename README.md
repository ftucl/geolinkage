# geolinkage

## Help
- Grass Console: (or  *File -> Launch Script*)
```
    v.geolinkage.py --help
```

- Terminal:
```bash
    python3.8 CmdInterface.py -h
```

## Examples
### CHOAPA example with MODFLOW model (*-g option*):

```bash
python3 CmdInterface.py
  -g
  --linkage_in_folder examples/choapa/out
  --gw_model examples/choapa/modflow/MODFLOW_1/Choapa_corregido_transiente4.nam
  --zrotation 30.0
  --coords_ll 0.0,0.0
  --linkage_out_folder examples/choapa/out
  --node  examples/choapa/weap/WEAPNode.shp
  --arc  examples/choapa/weap/WEAPArc.shp
  --epsg_code 32718
  --catchment  examples/choapa/catchment/Catchment_v1.shp  --catchment_field Catchment
  --gw  examples/choapa/gw/GW_v1.shp  --gw_field GW
  --ds_folder  examples/choapa/ds  --ds_field DS
```

### CHOAPA example without MODFLOW model:

```bash
python3 CmdInterface.py
  --linkage_in examples/choapa/linkage/linkage_created_weap_v1.shp
  --linkage_out_folder  examples/choapa/out
  --node  examples/choapa/weap/WEAPNode.shp
  --arc  examples/choapa/weap/WEAPArc.shp
  --epsg_code 32719
  --catchment  examples/choapa/catchment/Catchment_v1.shp  --catchment_field Catchment
  --gw examples/choapa/gw/GW_v1.shp  --gw_field GW
  --ds_folder  examples/choapa/ds  --ds_field DS
```
