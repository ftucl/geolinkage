import threading
import time

import ui
from grass_session import Session

import Utils
from Config import ConfigApp
from Errors import ErrorManager
from FeatureProcess import FeatureProcess
from GeoKernel import GeoKernel
from decorator import main_task, TimerSummary

from grass.pygrass.vector import VectorTopo

from collections import namedtuple


class CatchmentProcess(FeatureProcess):

    def __init__(self, geo: GeoKernel = None, config: ConfigApp = None, debug: bool = False, err: ErrorManager = None):
        super().__init__(geo=geo, config=config, debug=debug, err=err)

        self.catchments = {}
        self._catchment_names = {}

        self._feature_opts = {
            'order_criteria': 'area',
            'columns_to_save': 1
        }

    def _start(self, linkage_name: str):
        # import files to vector maps
        self.import_maps()

        # check catchment maps with geo maps (nodes and arcs)
        self.check_names_with_geo()

        # check catchment geometries
        self.check_names_between_maps()

        if not self.check_errors():
            # intersection between C (catchments map) and L (linkage map)
            _err_c, _errors_c = self.inter_map_with_linkage(linkage_name=linkage_name, snap='1e-12')
            if _err_c:
                self.print_errors()
                raise RuntimeError('[EXIT] ERROR AL INTERSECTAR CON [{}]'.format(linkage_name))

            # make a dictionary grid with cells information in intersection map
            self.make_grid_cell()
        # else:
        #     self.print_errors()

        # stats
        self.stats['PROCESSED CELLS'] = len(self.cells)

    @TimerSummary.timeit
    def run(self, linkage_name: str):
        ts = time.time()
        self._start(linkage_name=linkage_name)
        te = time.time()

        self.stats['FEATURES PROCESSED'] = '{}'.format(len(self._catchment_names))
        self.stats['PROCESSED TIME'] = '{0:.2f} seg'.format(te - ts)

        # Set inputs into summary
        # # set main field in map
        field = self.config.get_config_field_name(feature_type=self.get_feature_type(), name='name')
        self.summary.set_input_param(param_name='FIELD NAME', param_value='[{}]'.format(field))

        # # imported file
        map_names = [m for m in self.get_map_names(only_names=True, with_main_file=True, imported=True) if m[1]]
        for map_name in map_names:
            imported = self.map_names[map_name]['imported']
            if imported:
                self.summary.set_input_param(param_name='MAP {}'.format(map_name), param_value='[imported]')
            else:
                self.summary.set_input_param(param_name='MAP {}'.format(map_name), param_value='[not imported]')

        # Set stats into summary
        # # set cells
        self.stats['PROCESSED CELLS'] = len(self.cells)
        for stat_key in self.stats:
            self.summary.set_input_param(param_name=stat_key, param_value='[{}]'.format(self.stats[stat_key]))

    def set_data_from_geo(self):
        if self.geo:  # set [self.catchments] and [self._catchment_names]
            self.set_catchments(self.geo.get_catchments())

        return True, []

    def get_feature_id_by_name(self, feature_name):
        feature_id = self._catchment_names[feature_name] if feature_name in self._catchment_names else None
        return feature_id

    def set_catchments(self, catchments):
        self.catchments = catchments

        self._catchment_names = {}
        for point_id in self.catchments:
            catchment_data = self.catchments[point_id]
            self._catchment_names[catchment_data['name']] = point_id

    # @main_task
    def make_cell_data_by_main_map(self, map_name, inter_map_name, inter_map_geo_type):
        inter_map = VectorTopo(inter_map_name)
        inter_map.open('r')

        for feature_data in inter_map.viter(vtype=inter_map_geo_type):
            if feature_data.cat is None:  # when topology has some errors
                # print("[ERROR] ", a.cat, a.id)
                continue

            Cell = namedtuple('Cell_catchment', ['row', 'col'])

            fields = self.get_needed_field_names()
            main_field, main_needed = fields['main']['name'], fields['main']['needed']
            field_feature_name = 'a_' + main_field
            col_field = 'b_' + self.config.fields_db['linkage']['col_in']
            row_field = 'b_' + self.config.fields_db['linkage']['row_in']

            feature_name = feature_data.attrs[field_feature_name]
            cell_area_id = feature_data.attrs['b_cat']  # id from cell in linkage map
            area_row, area_col = feature_data.attrs[row_field], feature_data.attrs[col_field]
            feature_area = feature_data.area()

            data = {
                'area': feature_area,
                'cell_id': cell_area_id,
                'name': feature_name,
                'map_name': map_name
            }

            cell = Cell(area_row, area_col)

            self._set_cell(cell, feature_name, data, by_field=self.get_order_criteria_name()) if cell else None

            self.cells_by_map[map_name].append(cell) if cell else None  # order cells by map name (be used in DS)

        inter_map.close()

        self.summary.set_process_line(msg_name='make_cell_data_by_main_map', check_error=self.check_errors(),
                                      map_name=map_name, inter_map_name=inter_map_name,
                                      inter_map_geo_type=inter_map_geo_type)

        return self.check_errors(), self.get_errors()

    # @main_task
    def make_cell_data_by_secondary_maps(self, map_name, inter_map_name, inter_map_geo_type):
        # in this case is the same but done with main map to secondary maps
        return self.make_cell_data_by_main_map(map_name=map_name, inter_map_name=inter_map_name,
                                               inter_map_geo_type=inter_map_geo_type)

    # @main_task
    # def make_grid_cell(self, map_name: str):
    #     # get the intersection map name
    #     inter_map_name = self.get_inter_map_name(map_key=map_name)
    #
    #     inter_map = VectorTopo(inter_map_name)
    #     inter_map.open('r')
    #
    #     fields = self.get_needed_field_names()
    #     main_field, main_needed = fields['main']['name'], fields['main']['needed']
    #     limit = (fields['limit']['name'], fields['limit']['needed']) if fields['limit'] else ('', None)
    #     limit_field, limit_needed = limit[0], limit[1]
    #
    #     Cell = namedtuple('Cell_catchment', ['row', 'col'])
    #     field_catchment = 'a_' + main_field
    #     field_modflow = 'a_' + limit_field
    #
    #     col_field = 'b_' + self.config.fields_db['linkage']['col_in']
    #     row_field = 'b_' + self.config.fields_db['linkage']['row_in']
    #     for a in inter_map.viter('areas'):
    #         if a.cat is None:  # when topology has some errors
    #             # print("[ERROR] ", a.cat, a.id)
    #             continue
    #
    #         area_name = a.attrs[field_catchment]
    #
    #         cell_area_id = a.attrs['b_cat']  # id from cell in linkage map
    #         area_row, area_col = a.attrs[row_field], a.attrs[col_field]
    #         area_area = a.area()
    #
    #         if limit_needed:  # TODO: never it will reviwed if [needed] = False. Update it is present
    #             area_in_modflow = a.attrs[field_modflow]
    #         else:
    #             area_in_modflow = 1
    #
    #         if area_in_modflow == 1:
    #             data = {
    #                 'area': area_area,
    #                 'cell_id': cell_area_id,
    #                 'name': area_name
    #             }
    #
    #             cell = Cell(area_row, area_col)
    #             self._set_cell(cell, area_name, data, by_field='area')
    #
    #     # watch what is the best area for a cell by criteria
    #     self._set_cell_by_criteria(CatchmentProcess.__cell_order_criteria(), by_field='area')
    #
    #     inter_map.close()
    #
    #     return self.check_errors(), self.get_errors()

    # @main_task
    # def get_catchments_from_map(self, map_name):
    #     catchment_map = VectorTopo(map_name)
    #     catchment_map.open()
    #
    #     fields = self.get_needed_field_names()
    #     main_field, main_needed = fields['main']['name'], fields['main']['needed']
    #     limit = (fields['limit']['name'], fields['limit']['needed']) if fields['limit'] else ('', None)
    #     limit_field, limit_needed = limit[0], limit[1]
    #
    #     # check names between WEAPNode data and GW data
    #     for a in catchment_map.viter('areas'):
    #         if a.cat is None or not a.attrs[main_field]:
    #             # print("[ERROR - {}] ".format(gws_name), a.cat, a.id)
    #             continue
    #         area_name = a.attrs[main_field]
    #
    #         if area_name in self.catchments:
    #             feature_id = self.catchments[area_name]
    #
    #             if limit_needed:
    #                 modflow = a.attrs[limit_field]
    #                 # watch if it will be used
    #                 if modflow:
    #                     self.catchments[feature_id]['in_modflow'] = True
    #                 else:
    #                     self.catchments[feature_id]['in_modflow'] = False
    #             else:
    #                 self.catchments[feature_id]['in_modflow'] = True
    #         else:
    #             msg_err = 'Cuenca [{}] del [mapa] no se encuentra en [esquema WEAP].'\
    #                 .format(area_name)
    #             # _errors.append(msg_err)
    #             self.append_error(msg=msg_err)
    #
    #     catchment_map.close()
    #
    #     return self.check_errors(), self.get_errors()

    def get_needed_field_names(self):
        fields = {
            'main': {
                'name': self.config.fields_db['catchment']['name'],
                'needed': True
            },
            'secondary': None,
            'limit': {
                'name': self.config.fields_db['catchment']['modflow'],
                'needed': False
            },
        }

        return fields
