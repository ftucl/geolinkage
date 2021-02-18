import json
import os
import pathlib


class ConfigApp:

    def __init__(self, epsg_code: int, gisdb: str, location: str, mapset: str, debug: bool = False):

        # read JSON config file
        current_folder = pathlib.Path(__file__).parent.absolute()
        with open(os.path.join(current_folder, 'config/config.json')) as json_data_file:
            config_data = json.load(json_data_file)

        self.grass_internals = {
            'EPSG_CODE': epsg_code,
            'GISDB': gisdb,
            'LOCATION': location,
            'MAPSET': mapset
        }

        self.debug = debug

        self.linkage_out = config_data["DEFAULT MAP NAMES"]["LINKAGE FINAL MAP"]
        self.segments_map_name = config_data["DEFAULT MAP NAMES"]["RIVER SEGMENTS MAP"]
        self.inter_river_linkage_name = config_data["DEFAULT MAP NAMES"]["LINKAGE INTER RIVER SEGMENTS MAP"]
        self.inter_ds_linkage_name = config_data["DEFAULT MAP NAMES"]["LINKAGE INTER DEMAND SITE MAP"]

        self.type_names = {
            'GroundwaterProcess': config_data["FEATURE NAMES"]["groundwater"],
            'CatchmentProcess': config_data["FEATURE NAMES"]["catchment"],
            'RiverProcess': config_data["FEATURE NAMES"]["river"],
            'DemandSiteProcess': config_data["FEATURE NAMES"]["demand sites"],
            'GeoKernel': config_data["FEATURE NAMES"]["geometry"],
            'AppKernel': config_data["FEATURE NAMES"]["main program"]
        }

        self.fields_db = {
            self.type_names['GeoKernel']: {
                'arc_name': 'Name',
                'node_name': 'Name',
                'arc_type': 'TypeID',
                'node_type': 'TypeID'
            },
            'linkage': {
                self.type_names['CatchmentProcess']: 'CATCHMENT',
                self.type_names['GroundwaterProcess']: 'GROUNDWAT',  # or GROUNDWAT
                self.type_names['RiverProcess']: 'RIVERREAC',
                self.type_names['DemandSiteProcess']: 'DEMAND',
                'row': 'row',
                'col': 'column',
                'rc': 'rc',
                'row_in': 'row',
                'col_in': 'column'
            },
            self.type_names['CatchmentProcess']: {
                'name': 'Catchment',
                'modflow': 'MODFLOW'
            },
            self.type_names['GroundwaterProcess']: {
                'name': 'GW'  # or  GROUNDWAT
            },
            self.type_names['RiverProcess']: {
                'priority': 'principal',
                'segment_break_name': 'segment_break_name',
                'river_name': 'river_name'
            },
            self.type_names['DemandSiteProcess']: {
                'name': 'DS'
            },
            'linkage-in': {
                'row': 'row',
                'col': 'column',
            }
        }

        self.cols_linkage = {  # linkage-out is based from this
            'row': {'action': 'rename', 'name': 'row', 'name_new': 'row', 'type': 'INT', '_type_name': 'integer',
                    '_necessary': True},
            'col': {'action': 'rename', 'name': 'column', 'name_new': 'column', 'type': 'INT', '_type_name': 'integer',
                    '_necessary': True},
            'MF_RC': {'action': 'add', 'name': 'MF_RC', 'type': 'VARCHAR', '_type_name': 'varchar', '_necessary': True},
            self.type_names['CatchmentProcess']:
                {'action': 'add', 'name': self.fields_db['linkage'][self.type_names['CatchmentProcess']],
                 'type': 'VARCHAR', '_type_name': 'varchar',
                 '_necessary': True},
            'LANDUSE':
                {'action': 'add', 'name': 'LANDUSE',
                 'type': 'VARCHAR', '_type_name': 'varchar',
                 '_necessary': True},
            self.type_names['GroundwaterProcess']:
                {'action': 'add', 'name': self.fields_db['linkage'][self.type_names['GroundwaterProcess']],
                 'type': 'VARCHAR', '_type_name': 'varchar',
                 '_necessary': True},
            self.type_names['RiverProcess']:
                {'action': 'add', 'name': self.fields_db['linkage'][self.type_names['RiverProcess']],
                 'type': 'VARCHAR', '_type_name': 'varchar',
                 '_necessary': True},
            self.type_names['DemandSiteProcess']:
                {'action': 'add', 'name': self.fields_db['linkage'][self.type_names['DemandSiteProcess']],
                 'type': 'VARCHAR', '_type_name': 'varchar',
                 '_necessary': True},
        }

        self.process_msgs = config_data['PROCESSING LINES']

    def get_feature_names(self):
        return self.type_names.values()

    def set_epsg(self, epsg_code: int):
        self.grass_internals['EPSG_CODE'] = epsg_code

    def get_epsg(self):
        return self.grass_internals['EPSG_CODE']

    def set_gisdb(self, gisdb: str):
        self.grass_internals['GISDB'] = gisdb

    def get_gisdb(self):
        return self.grass_internals['GISDB']

    def set_location(self, location: str):
        self.grass_internals['LOCATION'] = location

    def get_location(self):
        return self.grass_internals['LOCATION']

    def set_mapset(self, mapset: str):
        self.grass_internals['MAPSET'] = mapset

    def get_mapset(self):
        return self.grass_internals['MAPSET']

    def set_config_field(self, feature_type: str, field_type: str, field_new_name: str):
        _err = False

        if field_type == 'main':
            self.fields_db[feature_type]['name'] = field_new_name
        elif field_type == 'limit' and feature_type == 'catchment':
            self.fields_db[feature_type]['modflow'] = field_new_name
        else:
            _err = True

        return _err

    def get_config_field_name(self, feature_type: str, name: str = 'name'):
        return self.fields_db[feature_type][name]

    def get_linkage_out_file_name(self):
        return self.linkage_out

    def get_process_msg(self, msg_name: str):
        if msg_name in self.process_msgs:
            msg_info = self.process_msgs[msg_name]
        else:
            msg_info = 'Message for [{}] not found!'.format(msg_name)

        return msg_info
