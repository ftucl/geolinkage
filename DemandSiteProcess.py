import time
from subprocess import PIPE

import ui
from grass_session import Session

import Utils
from Config import ConfigApp
from Errors import ErrorManager
from FeatureProcess import FeatureProcess
from GeoKernel import GeoKernel

from grass.pygrass.vector import Vector, VectorTopo
from grass.pygrass.modules import Module
from grass.pygrass.utils import copy, remove

from collections import namedtuple

from decorator import main_task, TimerSummary


class DemandSiteProcess(FeatureProcess):

    def __init__(self, geo: GeoKernel = None, config: ConfigApp = None, debug: bool = False, err: ErrorManager = None):
        super().__init__(geo=geo, config=config, debug=debug, err=err)

        self.demand_sites = {}
        self.wells = {}  # [well_name] = {'name': '', 'path': '', 'type': '', 'is_well':(T|F), 'processed': (T|F)}
        self._demand_site_names = None

        self._feature_opts = {
            'order_criteria': 'area',
            'columns_to_save': 4
        }

    def _start(self, linkage_name: str):
        # import files to vector maps
        self.import_maps()

        # check ds maps with geo maps (nodes and arcs)
        self.check_names_with_geo()

        # check ds geometries
        self.check_names_between_maps()

        # get and set the DS main file from Node map
        self.get_ds_map_from_node_map(is_main_file=True)

        self.read_well_files()  # read TXT with the wells (all will be considered wells if not)

        if not self.check_errors():
            # intersection between C (gw map) and L (linkage map)
            _err_gw, _errors_gw = self.inter_map_with_linkage(linkage_name=linkage_name,
                                                              snap='1e-12')
            if _err_gw:
                # self.print_errors()
                raise RuntimeError('[EXIT] ERROR AL INTERSECTAR CON [{}]'.format(linkage_name))

            # make a dictionary grid with cell information in intersection map
            self.make_grid_cell()
        # else:
        #     self.print_errors()

        # stats
        self.stats['PROCESSED CELLS'] = len(self.cells)

    @TimerSummary.timeit
    def run(self, linkage_name: str):
        # Utils.show_title(msg_title='DEMAND SITES', title_color=ui.green)
        ts = time.time()
        self._start(linkage_name=linkage_name)
        te = time.time()

        self.stats['FEATURES PROCESSED'] = '{}'.format(len(self._demand_site_names))
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

    def set_well(self, well_name: str, well_path: str, well_type: str = 'well_normal', is_well: bool = True):
        self.wells[well_name] = {
            'name': well_name,
            'path': well_path,
            'type': well_type,
            'is_well': is_well,
            'processed': False
        }

    def get_wells(self, well_type: str = 'well_normal', is_well: bool = True):
        ret = []
        if self.wells:
            ret = [(w['name'], w['path'], w['type'], w['is_well'], w['processed']) for k, w in self.wells.items() if w['is_well'] == is_well and w['type'] == well_type]
        else:
            ret = []

        return ret

    def exist_files_with_wells(self):
        return len(self.get_wells(well_type='well_normal', is_well=True)) > 0

    def set_data_from_geo(self):
        if self.geo:  # set [self.gws] and [self._gw_names]
            self.set_demand_sites(self.geo.get_demand_sites())

    def get_feature_id_by_name(self, feature_name):
        feature_id = self._demand_site_names[feature_name] if feature_name in self._demand_site_names else None
        return feature_id

    def set_demand_sites(self, demand_site):
        self.demand_sites = demand_site

        self._demand_site_names = {}
        for point_id in self.demand_sites:
            demand_site_data = self.demand_sites[point_id]
            self._demand_site_names[demand_site_data['name']] = point_id

    @classmethod
    def make_buffer_in_point(cls, map_pts_name, out_name, map_type='point', distance=1000, verbose: bool = False, quiet: bool = True):
        buffer = Module('v.buffer', run_=False, stdout_=PIPE, stderr_=PIPE, overwrite=True, verbose=verbose, quiet=quiet)

        buffer.inputs.input = map_pts_name
        buffer.inputs.type = map_type
        buffer.inputs.distance = distance

        buffer.outputs.output = out_name

        buffer.flags.t = True
        buffer.flags.s = True

        # print(buffer.get_bash())
        buffer.run()
        print(buffer.outputs["stdout"].value)

    # @main_task
    def get_ds_map_from_node_map(self, is_main_file: bool = False, verbose: bool = False, quiet: bool = True):
        import sqlite3
        from grass.pygrass.vector.table import Columns

        node_map_name, node_map_path, node_map_inter = self.geo.get_node_map_names()[0]  # get the node map
        ds_extract_out_name = node_map_name + '_extract_ds'
        ds_buffer_out_name = node_map_name + '_extract_with_buffer_ds'

        # extract nodes for DS
        col_query, op_query, val_query = self.geo.get_node_needed_field_names()['secondary']['name'], '=', '1'
        _err, _errors = Utils.extract_map_with_condition(map_name=node_map_name, output_name=ds_extract_out_name,
                                                         col_query=col_query, val_query=val_query,
                                                         op_query=op_query, geo_check='point',
                                                         verbose=verbose, quiet=quiet)
        if not _err:
            # make a buffer in each node founded
            self.make_buffer_in_point(map_pts_name=ds_extract_out_name, out_name=ds_buffer_out_name,
                                      map_type='point', distance=10, verbose=verbose, quiet=quiet)

            # change the column name from Node map's main field to DS map's main field
            node_main_field = self.geo.get_node_needed_field_names()['main']['name']
            ds_main_field = self.get_needed_field_names()['main']['name']

            vector_map = VectorTopo(ds_buffer_out_name)
            vector_map.open('r')
            db_path = vector_map.dblinks[0].database
            vector_map.close()

            cols_sqlite = Columns(ds_buffer_out_name, sqlite3.connect(db_path))
            cols_sqlite.rename(node_main_field, ds_main_field)

            # set new map like main DS map
            self.set_map_name(map_name=ds_buffer_out_name, map_path=node_map_path, is_main_file=is_main_file)

            # it was imported because it is based in Node map
            self.map_names[ds_buffer_out_name]['imported'] = True

            # the intersection map is with 'areas' geos
            self.set_inter_map_geo_type(map_key=ds_buffer_out_name, geo_map_type='lines')
        else:
            msg_error = 'No se han encontrado [Sitios de Demanda] en el [mapa de nodos].'
            self.append_error(msg=msg_error, typ=self.get_feature_type(), is_warn=True)

        self.summary.set_process_line(msg_name='get_ds_map_from_node_map', check_error=self.check_errors())

        return self.check_errors(), self.get_errors()

    # @main_task
    # def _inter_map_with_linkage(self, map_name, linkage_name, output_name, snap='1e-12', verbose: bool = False, quiet: bool = True):
    #     ds_copy_out_name = 'ds_copy'
    #     ds_extract_out_name = 'ds_extract'
    #     ds_buffer_out_name = 'ds_points_with_buffer'
    #
    #     # get a copy from map
    #     copy(map_name, ds_copy_out_name, 'vect', overwrite=True)
    #
    #     err = False
    #     vector_map = Vector(ds_copy_out_name)
    #     if vector_map.exist():  # copy works
    #         # extract only [TypeID]=1 in WEAPNode map
    #         extract = Module('v.extract', run_=False, stdout_=PIPE, stderr_=PIPE, overwrite=True, verbose=verbose, quiet=quiet)
    #         extract.inputs.input = ds_copy_out_name
    #         extract.outputs.output = ds_extract_out_name
    #
    #         extract.inputs.where = "TypeID=\'{}\'".format(1)
    #         extract.inputs.type = 'point'
    #         # print(extract.get_bash())
    #         extract.run()
    #         # print(extract.outputs["stdout"].value)
    #         # print(extract.outputs["stderr"].value)
    #
    #         vector_map = VectorTopo(ds_extract_out_name)
    #         vector_map.open('r')
    #         if vector_map.exist() and vector_map.num_primitive_of('point') > 0:  # extract works
    #             # make a buffer by each point
    #             DemandSiteProcess.make_buffer_in_point(ds_extract_out_name, ds_buffer_out_name, map_type='point', distance=10)
    #
    #             vector_map.close()
    #             vector_map = Vector(ds_buffer_out_name)
    #             if vector_map.exist():  # buffer works
    #                 # intersect vector maps
    #                 overlay = Module('v.overlay', run_=False, stdout_=PIPE, stderr_=PIPE, overwrite=True, verbose=verbose, quiet=quiet)
    #                 overlay.flags.c = True
    #
    #                 overlay.inputs.ainput = ds_buffer_out_name
    #                 overlay.inputs.binput = linkage_name
    #                 overlay.inputs.operator = 'and'
    #                 overlay.inputs.snap = snap
    #                 overlay.outputs.output = output_name
    #
    #                 # print(overlay.get_bash())
    #                 overlay.run()
    #                 # print(overlay.outputs["stdout"].value)
    #                 # print(overlay.outputs["stderr"].value)
    #
    #                 vector_map.close()
    #                 vector_map = Vector(output_name)
    #                 err = False if vector_map.exist() else True
    #             else:
    #                 msg_error = 'El mapa [{}] presenta errores o no pudo ser creado por funcion [{}].'.format(
    #                     ds_buffer_out_name, 'v.buffer')
    #                 self.append_error(msg=msg_error)
    #
    #                 err = True
    #         else:
    #             vector_map.close()
    #             msg_error = 'No se encontraron [sitios de demanda] en [WEAPNode].'
    #             self.append_error(msg=msg_error)
    #
    #             err = True
    #     else:
    #         msg_error = 'El mapa [{}] no pudo ser creado por funcion [{}].'.format(ds_copy_out_name, 'v.copy')
    #         self.append_error(msg=msg_error)
    #
    #         err = True
    #
    #     return self.check_errors(), self.get_errors()
    # @main_task
    def make_cell_data_by_main_map(self, map_name, inter_map_name, inter_map_geo_type):
        inter_map = VectorTopo(inter_map_name)
        inter_map.open('r')

        for feature_data in inter_map.viter(vtype=inter_map_geo_type):
            if feature_data.cat is None:  # when topology has some errors
                # print("[ERROR] ", a.cat, a.id)
                continue

            # cell, feature_name, data = self._make_cell_data(feature_data=a, map_name=map_name)
            Cell = namedtuple('Cell_ds', ['row', 'col'])

            fields = self.get_needed_field_names()
            main_field, main_needed = fields['main']['name'], fields['main']['needed']
            field_feature_name = 'a_' + main_field
            col_field = 'b_' + self.config.fields_db['linkage']['col_in']
            row_field = 'b_' + self.config.fields_db['linkage']['row_in']

            feature_name = feature_data.attrs[field_feature_name]
            cell_area_id = feature_data.attrs['b_cat']  # id from cell in linkage map
            area_row, area_col = feature_data.attrs[row_field], feature_data.attrs[col_field]
            feature_area = feature_data.area()

            # get id from demand site map (Node map) - its geometry id
            feature_id = self._demand_site_names[feature_name]

            if self.demand_sites[feature_id]['is_well']:
                is_geometry_processed = self.demand_sites[feature_id]['processed']
                if not is_geometry_processed:
                    self.demand_sites[feature_id]['processed'] = True

                    data = {
                        'area': feature_area,
                        'cell_id': cell_area_id,
                        'name': feature_name,
                        'map_name': map_name
                    }

                    cell = Cell(area_row, area_col)
                else:
                    cell, feature_name, data = None, None, None

                self._set_cell(cell, feature_name, data, by_field=self.get_order_criteria_name()) if cell else None

                self.cells_by_map[map_name].append(cell) if cell else None  # order cells by map name (be used in DS)

        inter_map.close()

        self.summary.set_process_line(msg_name='make_cell_data_by_main_map', check_error=self.check_errors(),
                                      map_name=map_name, inter_map_name=inter_map_name,
                                      inter_map_geo_type=inter_map_geo_type)

        return self.check_errors(), self.get_errors()

    # @main_task
    def make_cell_data_by_secondary_maps(self, map_name, inter_map_name, inter_map_geo_type):
        inter_map = VectorTopo(inter_map_name)
        inter_map.open('r')

        for feature_data in inter_map.viter(vtype=inter_map_geo_type):
            if feature_data.cat is None:  # when topology has some errors
                # print("[ERROR] ", a.cat, a.id)
                continue

            # cell, feature_name, data = self._make_cell_data(feature_data=a, map_name=map_name)
            Cell = namedtuple('Cell_ds', ['row', 'col'])

            fields = self.get_needed_field_names()
            main_field, main_needed = fields['main']['name'], fields['main']['needed']
            field_feature_name = 'a_' + main_field
            col_field = 'b_' + self.config.fields_db['linkage']['col_in']
            row_field = 'b_' + self.config.fields_db['linkage']['row_in']

            feature_name = feature_data.attrs[field_feature_name]
            cell_area_id = feature_data.attrs['b_cat']  # id from cell in linkage map
            area_row, area_col = feature_data.attrs[row_field], feature_data.attrs[col_field]
            feature_area = feature_data.area()

            # get id from demand site map (Node map) - its geometry id
            feature_id = self._demand_site_names[feature_name]
            # feature_id = feature_data.attrs['a_ObjID']

            data = {
                'area': feature_area,
                'cell_id': cell_area_id,
                'name': feature_name,
                'map_name': map_name
            }

            cell = Cell(area_row, area_col)

            self._set_cell(cell, feature_name, data, by_field=self.get_order_criteria_name())

            self.cells_by_map[map_name].append(cell) if cell else None  # order cells by map name (will be used in DS)

        inter_map.close()

        self.summary.set_process_line(msg_name='make_cell_data_by_secondary_maps', check_error=self.check_errors(),
                                      map_name=map_name, inter_map_name=inter_map_name,
                                      inter_map_geo_type=inter_map_geo_type)

        return self.check_errors(), self.get_errors()

    # @main_task
    # def make_grid_cell(self, map_name: str):
    #     # get the intersection map name
    #     inter_map_name = self.get_inter_map_name(map_key=map_name)
    #
    #     inter_map = VectorTopo(inter_map_name)
    #     inter_map.open('r')
    #
    #     col_field = 'b_' + self.config.fields_db['linkage']['col_in']
    #     row_field = 'b_' + self.config.fields_db['linkage']['row_in']
    #     Cell = namedtuple('Cell_ds', ['row', 'col'])
    #     for a in inter_map.viter('areas'):
    #         if a.cat is None:
    #             # print("[ERROR] ", a.cat, a.id)
    #             continue
    #
    #         area_name = a.attrs['a_Name']
    #
    #         cell_area_id = a.attrs['b_cat']  # id from cell in linkage map
    #         area_row, area_col = a.attrs[row_field], a.attrs[col_field]
    #         area_area = a.area()
    #
    #         feature_id = a.attrs['a_ObjID']  # id from demand site map (WEAPNode) and its geometry id
    #         is_geometry_processed = self.demand_sites[feature_id]['processed']
    #         if not is_geometry_processed:
    #             data = {
    #                 'area': area_area,
    #                 'cell_id': cell_area_id,
    #                 'name': area_name
    #             }
    #
    #             cell = Cell(area_row, area_col)
    #             self._set_cell(map_name, cell, area_name, data, by_field='area')
    #
    #             self.demand_sites[feature_id]['processed'] = True
    #
    #     for cell in self.cells:
    #         area_targets = self.cells[cell]
    #         key_target = list(area_targets.keys())[0]  # get any item is the same
    #
    #         cell_id = area_targets[key_target]['cell_id']
    #
    #         self.cell_ids[cell] = {
    #             'number_demand_sites': len(area_targets.keys()),
    #             'cell_id': cell_id,
    #             'row': cell.row,
    #             'col': cell.col,
    #             'demand_sites': area_targets
    #         }
    #
    #     inter_map.close()
    #
    #     return self.check_errors(), self.get_errors()

    def get_needed_field_names(self):
        fields = {
            'main': {
                'name': self.config.fields_db[self.get_feature_type()]['name'],
                'needed': True
            },
            'secondary': '',
            'limit': '',
        }

        return fields

    def read_well_files(self):
        if self.exist_files_with_wells():
            wells = self.get_wells(well_type='well_normal', is_well=True)
            for w_name, w_path, *_ in wells:
                with open(w_path, 'r', encoding='utf-8', errors='replace') as file:
                    try:
                        well_lines = file.readlines()
                        self._read_well_files(well_name=w_name, well_path=w_path, well_lines=well_lines)
                    except UnicodeDecodeError as e:
                        msg_error = 'Error al leer el archivo de pozos [{}]'.format(w_path)
                        self.append_error(msg=msg_error, typ=self.get_feature_type(), is_warn=False)
        else:
            msg_info = 'No se ha encontrado archivo con identificación de pozos.' \
                       ' Los sitios de demanda del mapa de Nodos no serán considerados.'
            self.append_error(msg=msg_info, typ=self.get_feature_type(), code='12', is_warn=True)

        return self.check_errors(code='12'), self.get_errors(code='12')

    # @main_task
    def _read_well_files(self, well_name, well_path, well_lines):
        wells_count = 0
        for well_name in well_lines:
            well_name = well_name.strip()

            if well_name and well_name[0] != '#':
                wells_count += 1
                # check if it exists in demand_sites list
                feature_id = self.get_feature_id_by_name(well_name)
                if not feature_id:  # not exists in geometries (arcs and nodes)
                    msg_error = 'El nombre [{}] encontrado en el archivo de pozos [{}] no existe en los ' \
                                'sitios de demanda iniciales.'.format(well_name, well_path)
                    self.append_error(msg=msg_error, typ=self.get_feature_type(), code='12')  # check codes = 1[x]
                else:
                    # set like a well initial demand sites
                    self.demand_sites[feature_id]['is_well'] = True

        if wells_count == 0:
            msg_error = 'Wells file ([{}]) without wells'.format(well_path)
            self.append_error(msg=msg_error, typ=self.get_feature_type(), code='12', is_warn=True)  # check codes = 1[x]

        self.summary.set_process_line(msg_name='_read_well_files', check_error=self.check_errors(code='12'),
                                      well_path=well_path)

        return self.check_errors(code='12'), self.get_errors(code='12')


    # def check_basic_columns(self, map_name: str):
    #     _err, _errors = False, []
    #     fields = self.get_needed_field_names()
    #
    #     for field_key in [field for field in fields if fields[field]]:
    #         field_name = fields[field_key]['name']
    #         needed = fields[field_key]['needed']
    #
    #         __err, __errors = Utils.check_basic_columns(map_name=map_name, columns=[field_name], needed=[needed])
    #
    #         _errors += __errors
    #         if needed:
    #             _err |= __err
    #
    #     self.append_error(msgs=_errors, typ='other')
    #
    #     return _err, _errors
