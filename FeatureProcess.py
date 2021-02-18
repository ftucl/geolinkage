from abc import abstractmethod, ABCMeta
from collections import namedtuple

from grass.pygrass.utils import copy, remove
from grass.pygrass.vector import Vector
from grass.pygrass.vector import VectorTopo
from grass.pygrass.modules import Module

from subprocess import PIPE

import Utils
from Errors import ErrorManager
from GeoKernel import GeoKernel
from SummaryInfo import SummaryInfo
from decorator import main_task
from Config import ConfigApp


class FeatureProcess(metaclass=ABCMeta):

    _errors = []

    def __init__(self, geo: GeoKernel, config: ConfigApp = None, debug=None, err: ErrorManager = None):
        self.geo = geo
        self.config = config
        self._err = err

        self.cells = {}
        self.cell_ids = {}
        self.map_names = {}

        self._features_by_map = {}  # [feature_name] = [[map_name_1],... , [map_name_i]]
        self.cells_by_map = {}  # [map_name_i] = [cell_i_1, ..., cell_i_j]

        if debug is None:
            self.__debug = self.config.debug if self.config is not None else False

        self._feature_type = self.config.type_names[self.__class__.__name__]
        self._feature_opts = {
            'order_criteria': None,
            'columns_to_save': None
        }

        # stats
        self.stats = {}

        self.z_rotation = None
        self.x_ll = None  # real world model coords (lower left)
        self.y_ll = None  # real world model coords (lower left)

        self.summary = SummaryInfo(prefix=self.get_feature_type(), errors=err, config=self.config)

    def set_origin(self, x_ll: float, y_ll: float, z_rotation: float):
        self.x_ll = x_ll
        self.y_ll = y_ll
        self.z_rotation = z_rotation

    def get_epsg(self):
        return self.config.get_epsg()

    def get_gisdb(self):
        return self.config.get_gisdb()

    def get_location(self):
        return self.config.get_location()

    def get_mapset(self):
        return self.config.get_mapset()

    @abstractmethod
    def run(self, linkage_name: str):
        pass

    def get_summary(self):
        return self.summary

    def set_map_name(self, map_name: str, map_path: str = None, is_main_file: bool = None, map_new_name: str = None):
        if map_name in self.map_names:
            self.map_names[map_name]['path'] = map_path if map_path else self.map_names[map_name]['path']
            self.map_names[map_name]['is_main'] = is_main_file if is_main_file is not None else self.map_names[map_name]['is_main']

            if map_new_name is not None:
                # dictionary[new_key] = dictionary.pop(old_key)
                self.map_names[map_name]['name'] = map_new_name
                self.map_names[map_new_name] = self.map_names.pop(map_name)
                map_name = map_new_name
        else:
            self.map_names[map_name] = {
                'name': map_name,
                'path': map_path,
                'inter': 'output_inter_linkage_' + map_name,
                'inter_geo_type': 'areas',  # default geometries type in intersection map. it could be 'lines'
                'is_main': is_main_file,
                'imported': False
            }

        self.cells_by_map[map_name] = []

    def get_main_map_name(self, only_name: bool = False, imported: bool = True):
        all_names = self.get_map_names(only_names=True, with_main_file=True, imported=imported)
        without_main_names = self.get_map_names(only_names=True, with_main_file=False, imported=imported)
        main_name = [e for e in all_names if e not in without_main_names]

        if len(main_name) > 0:
            if only_name:
                ret = self.get_map_name(map_key=main_name[0], only_name=only_name, with_main_file=True)
            else:
                ret = self.get_map_name(map_key=main_name[0], only_name=only_name, with_main_file=True)
                ret = ret[0], ret[1], ret[2]
        else:
            ret = None if only_name else (None, None, None)

        return ret

    def get_map_name(self, map_key: str, only_name: bool = False, with_main_file: bool = True):
        if not with_main_file:
            name = self.map_names[map_key]['name'] if not self.map_names[map_key]['is_main'] else None
            if only_name:
                ret = name
            else:
                path = self.map_names[map_key]['path'] if not self.map_names[map_key]['is_main'] else None
                inter = self.map_names[map_key]['path'] if not self.map_names[map_key]['is_main'] else None
                ret = name, path, inter
        else:
            if only_name:
                ret = self.map_names[map_key]['name']
            else:
                ret = self.map_names[map_key]['name'], self.map_names[map_key]['path'], self.map_names[map_key]['inter']

        return ret

    def get_inter_map_name(self, map_key: str) -> str:
        return self.map_names[map_key]['inter']

    def set_inter_map_geo_type(self, map_key: str, geo_map_type: str = 'areas'):
        self.map_names[map_key]['inter_geo_type'] = geo_map_type  # lines or areas

    def get_inter_map_geo_type(self, map_key: str) -> str:
        return self.map_names[map_key]['inter_geo_type']

    def get_map_path(self, map_key: str) -> str:
        return self.map_names[map_key]['path']

    def get_map_names(self, only_names: bool = False, with_main_file: bool = True, imported: bool = False):
        ret = []

        map_names = self.map_names
        if imported:
            map_names = dict([(m, map_names[m]) for m in map_names if map_names[m]['imported']])

        for m_key in map_names:
            if only_names:
                map_name = self.get_map_name(map_key=m_key, only_name=only_names, with_main_file=with_main_file)
                map_info = map_name
            else:
                map_name, map_path, map_inter = self.get_map_name(map_key=m_key, only_name=only_names, with_main_file=with_main_file)
                map_info = (map_name, map_path, map_inter)
            ret.append(map_info) if map_name else None

        return ret

    def append_error(self, msg: str = None, msgs: list = None, typ: str = None, is_warn: bool = False, code: str = ''):
        typ = self.get_feature_type() if not typ else typ

        if is_warn:
            if msg:
                self._err.append(msg=msg, typ=typ, is_warn=is_warn, code=code)
            elif msgs:
                for msg_str in msgs:
                    self._err.append(msg=msg_str, typ=typ, is_warn=is_warn, code=code)
        else:
            if msg:
                self._err.append(msg=msg, typ=typ, code=code)
            elif msgs:
                for msg_str in msgs:
                    self._err.append(msg=msg_str, typ=typ, code=code)

    def get_errors(self, code: str = ''):
        # return self._err.get_errors(typ=self.config.type_names[self.__class__.__name__], code=code)
        return self._err.get_errors(typ=self.get_feature_type(), code=code)

    def check_errors(self, is_warn: bool = False, code: str = ''):
        if is_warn:
            return self._err.check_warning(typ=self.config.type_names[self.__class__.__name__], code=code)
        else:
            return self._err.check_error(typ=self.config.type_names[self.__class__.__name__], code=code)

    def print_errors(self, words: list = None):
        self._err.print(typ=self.config.type_names[self.__class__.__name__])

    def get_feature_type(self):
        return self._feature_type

    @abstractmethod
    def set_data_from_geo(self):
        pass

    @abstractmethod
    def get_feature_id_by_name(self, feature_name):
        pass

    def set_feature_names_in_maps(self, imported: bool = True):
        map_names = self.map_names
        if imported:
            map_names = dict([(m, map_names[m]) for m in map_names if map_names[m]['imported']])

        for map_key in map_names:
            map_name = map_names[map_key]['name']

            vector_map = VectorTopo(map_name)
            vector_map.open('r')

            fields = self.get_needed_field_names()
            main_field, main_needed = fields['main']['name'], fields['main']['needed']

            for a in vector_map.viter('areas'):
                if a.cat is None or not a.attrs[main_field]:
                    # print("[ERROR - {}] ".format(gws_name), a.cat, a.id)
                    continue

                feature_name = a.attrs[main_field]

                if feature_name in self._features_by_map:
                    self._features_by_map[feature_name].add(map_name)
                else:
                    self._features_by_map[feature_name] = {map_name}

            vector_map.close()

    # @main_task
    def check_names_with_geo(self):
        self.set_data_from_geo()  # get the feature names in geo maps (node and arc)

        if len(self._features_by_map) == 0:
            self.set_feature_names_in_maps(imported=True)

        for feature_name in self._features_by_map.keys():
            feature_id = self.get_feature_id_by_name(feature_name)  # find [feature_name] in geo features
            map_names = ', '.join(self._features_by_map[feature_name])

            if not feature_id:  # not exists in geometries (arcs and nodes)
                msg_error = 'El nombre [{}] en los mapas [{}] no existe en las geometrias bases de arcos y nodos.'.format(
                    feature_name, map_names
                )
                self.append_error(msg=msg_error, typ=self.get_feature_type(), code='10')  # check error codes = 1[x]

        self.summary.set_process_line(msg_name='check_names_with_geo', check_error=self.check_errors(code='10'))

        return self.check_errors(code='10'), self.get_errors(code='10')

    # @main_task
    def check_names_between_maps(self):
        self.set_data_from_geo()  # get the feature names in geo maps (node and arc)

        if len(self._features_by_map) == 0:
            self.set_feature_names_in_maps(imported=True)

        check_maps = [f_name for f_name in self._features_by_map if len(self._features_by_map[f_name]) > 1]
        for feature_name in check_maps:
            map_names = ', '.join(self._features_by_map[feature_name])
            msg_error = 'El nombre [{}] se encuentra en mas de un mapa ([{}]) al mismo tiempo.'.format(
                feature_name, map_names
            )
            self.append_error(msg=msg_error, code='11', typ=self.get_feature_type())  # check error codes = 1[x]

        self.summary.set_process_line(msg_name='check_names_between_maps', check_error=self.check_errors(code='11'))

        return self.check_errors(code='11'), self.get_errors(code='11')

    @staticmethod
    def _cell_order_criteria_default(cell, cells_dict, by_field='area'):
        area_targets = cells_dict[cell]
        area_targets_sorted = sorted(area_targets.items(), key=lambda x: x[1][by_field], reverse=True)
        area_targets_sorted = [area_target for area_key, area_target in area_targets_sorted]

        return area_targets_sorted  # (key, data_key)

    def _set_cell(self, cell, area_name, data, by_field='area'):
        if cell in self.cells:
            # watch if exist catchment
            if area_name in self.cells[cell]:
                area_area = data[by_field]
                self.cells[cell][area_name][by_field] += area_area
            else:
                self.cells[cell][area_name] = data
        else:
            self.cells[cell] = {}

            self.cells[cell][area_name] = data

    def _set_cell_by_criteria(self, criteria_func, by_field='area'):
        # watch what is the best area by criteria for a cell
        for cell in self.cells:
            area_targets_ordered = criteria_func(cell, self.cells, by_field=by_field)

            self.cell_ids[cell] = {
                'number_of_data': len(area_targets_ordered),
                'cell_id': area_targets_ordered[0]['cell_id'],
                'row': cell.row,
                'col': cell.col,
                'data': area_targets_ordered
            }

    def get_cell_keys(self):
        if self.cell_ids:
            return self.cell_ids.keys()
        else:
            return []

    def get_cell_id_data(self, cell):
        data = None
        if cell in self.cell_ids:
            data = self.cell_ids[cell]

        return data

    def get_order_criteria_name(self) -> str:  # 'area' or 'length'
        order_c = self._feature_opts['order_criteria'] if self._feature_opts['order_criteria'] else ''
        return order_c

    def get_columns_to_save(self) -> int:
        c_to_save = self._feature_opts['columns_to_save'] if self._feature_opts['columns_to_save'] else -1
        return c_to_save

    @abstractmethod
    def make_cell_data_by_main_map(self, map_name, inter_map_name, inter_map_geo_type):
        pass

    @abstractmethod
    def make_cell_data_by_secondary_maps(self, map_name, inter_map_name, inter_map_geo_type):
        pass

    def make_grid_cell(self):
        map_names = self.get_map_names(only_names=False, with_main_file=True, imported=True)
        main_map_name, main_map_path, main_map_inter = self.get_main_map_name(only_name=False)

        for map_name, map_path, map_inter in map_names:

            inter_map_name = self.get_inter_map_name(map_key=map_name)  # get the intersection map name
            inter_map_geo_type = self.get_inter_map_geo_type(map_key=map_name)

            if map_name == main_map_name:
                self.make_cell_data_by_main_map(map_name=map_name, inter_map_name=inter_map_name,
                                                inter_map_geo_type=inter_map_geo_type)
            else:
                self.make_cell_data_by_secondary_maps(map_name=map_name, inter_map_name=inter_map_name,
                                                      inter_map_geo_type=inter_map_geo_type)

            # watch what is the best area for a cell by criteria
            self._set_cell_by_criteria(criteria_func=self._cell_order_criteria_default,
                                       by_field=self.get_order_criteria_name())

        return self.check_errors(), self.get_errors()

    @abstractmethod
    def get_needed_field_names(self):
        pass

    def inter_map_with_linkage(self, linkage_name, snap='1e-12', verbose: bool = False, quiet: bool = True):
        map_names = self.get_map_names(only_names=False, with_main_file=True, imported=True)
        for map_name, path_name, inter_name in map_names:
            self._inter_map_with_linkage(map_name=map_name, linkage_name=linkage_name, output_name=inter_name,
                                         snap=snap, verbose=verbose, quiet=quiet)

        return self.check_errors(), self.get_errors()

    # @main_task
    def _inter_map_with_linkage(self, map_name, linkage_name, output_name, snap='1e-12', verbose: bool = False, quiet: bool = True):
        _err = False

        # select only features with names
        if self.get_needed_field_names()['main']:
            col_query = self.get_needed_field_names()['main']['name']
            Utils.extract_map_with_condition(map_name, map_name + '_extract', col_query, '', '!=')
            map_name = map_name + '_extract'

        map_copy_name = map_name + '_copy'

        # get a copy from map
        copy(map_name, map_copy_name, 'vect', overwrite=True)

        vector_map = Vector(map_copy_name)
        if vector_map.exist():
            # intersect vector maps
            overlay = Module('v.overlay', run_=False, stdout_=PIPE, stderr_=PIPE, overwrite=True, verbose=verbose, quiet=quiet)
            overlay.flags.c = True

            overlay.inputs.ainput = map_copy_name
            # overlay.inputs.atype = 'area'
            overlay.inputs.binput = linkage_name
            # overlay.inputs.btype = 'area'

            overlay.inputs.operator = 'and'
            overlay.inputs.snap = snap
            overlay.outputs.output = output_name

            # print(overlay.get_bash())
            overlay.run()
            # print(overlay.outputs["stdout"].value)
            # print(overlay.outputs["stderr"].value)

            vector_map = Vector(output_name)
            if not vector_map.exist():
                msg_error = 'El mapa [{}] presenta errores o no pudo ser creado por funcion [{}].'.format(overlay, 'v.overlay')
                # FeatureProcess._errors.append(msg_error)
                # FeatureProcess._errors.append(overlay.outputs["stderr"].value)
                self.append_error(msg=msg_error)

                _err = True
        else:
            msg_error = 'El mapa [{}] no pudo ser creado por funcion [{}].'.format(map_copy_name, 'v.copy')
            # FeatureProcess._errors.append(msg_error)

            _err = True
            self.append_error(msg=msg_error)

        self.summary.set_process_line(msg_name='_inter_map_with_linkage', check_error=self.check_errors(),
                                      map_name=map_name, linkage_name=linkage_name, output_name=output_name)

        return self.check_errors(), self.get_errors()

    def get_data_to_save(self, cell, main_data: bool = True):
        if main_data:
            main_map = self.get_main_map_name(only_name=True, imported=True)
            col_data = self.get_cell_data_by_map(map_name=main_map, cell=cell)
            col_names = self.get_columns(main_data=main_data)
            cols_number = int(self._feature_opts['columns_to_save'] if self._feature_opts['columns_to_save'] else 0)

            if col_data:
                if len(col_data) > cols_number and self.__class__.__name__ == 'DemandSiteProcess':
                    msg_error = "Error en la [celda=(r={}, c={})] para mapa [{}]. El numero a almacenar es [{}], " \
                                "pero no debe ser mayor que [{}]. Se considera sólo [{}]"\
                        .format(cell.row, cell.col, main_map, len(col_data), cols_number, cols_number)
                    self.append_error(msg=msg_error, typ=self.config.type_names[self.__class__.__name__])

                values_to_save = min(cols_number, len(col_data))

                data = dict([(col_names[i], col_data[i]['name']) for i in range(values_to_save)])
                for j in range(cols_number-values_to_save):
                    data[col_names[cols_number-(j+1)]] = ''
            else:
                data = dict([(col_names[i], '') for i in range(cols_number)])
        else:
            # col_prefix = self.config.fields_db['linkage'][self.get_feature_type()]

            data = {}
            col_names = self.get_columns(main_data=main_data)
            map_names = self.get_map_names(only_names=False, with_main_file=False, imported=True)
            for ind, (map_name, map_path, map_inter) in enumerate(map_names):
                cell_data = self.get_cell_data_by_map(map_name=map_name, cell=cell)

                data[col_names[ind]] = cell_data[0]['name'] if cell_data else ''

                if len(cell_data) > 1:
                    msg_error = 'El mapa [{}] tiene mas de un valor en la [celda: ({}, {})]. Se considera el primero: [{}]'\
                        .format(map_name, cell.row, cell.col, cell_data[0]['name'])
                    self.append_error(msg=msg_error, typ=self.config.type_names[self.__class__.__name__])

        return data

    def get_columns(self, main_data: bool = True, with_type: bool = False):

        # the max column name to export to shapefile is 9: prefix chars (7) + number (2)
        col_prefix = self.config.fields_db['linkage'][self.get_feature_type()][0:7]

        # TODO: else code can be do it with recursive code
        if not with_type:
            if main_data:
                col_names = []
                cols_number = int(self._feature_opts['columns_to_save'] if self._feature_opts['columns_to_save'] else 0)

                for i in range(cols_number):
                    col_names.append('{}{}'.format(col_prefix, i+1))

                return col_names
            else:
                # col_prefix = col_prefix[0] + '_'
                col_prefix = self.config.fields_db['linkage'][self.get_feature_type()]
                col_names = ['{}{}'.format(col_prefix[0], m_name[0:9])
                             for m_name in self.get_map_names(only_names=True, with_main_file=main_data, imported=True)]

                return col_names
        else:
            col_prefix_name = self.config.cols_linkage[self.get_feature_type()]['name'][0:7]
            col_type = self.config.cols_linkage[self.get_feature_type()]['type']

            if main_data:
                col_names = []
                cols_number = int(self._feature_opts['columns_to_save'] if self._feature_opts['columns_to_save'] else 0)

                for i in range(cols_number):
                    col_names.append(('{}{}'.format(col_prefix_name, i+1), col_type))

                return col_names
            else:
                col_prefix = self.config.fields_db['linkage'][self.get_feature_type()]
                col_names = [('{}{}'.format(col_prefix[0], col[0:9]), 'VARCHAR')
                             for col in self.get_map_names(only_names=True, with_main_file=main_data, imported=True)]

                return col_names

    def get_cell_data_by_map(self, map_name: str, cell):
        ret = []
        if cell in self.cell_ids:
            ret = [d for d in self.cell_ids[cell]['data'] if d['map_name'] == map_name]
        return ret

    def import_maps(self, verbose: bool = False, quiet: bool = True):
        map_names = [m for m in self.get_map_names(only_names=False, with_main_file=True, imported=False) if m[1]]

        for map_name, path_name, inter_name in map_names:
            _err, _errors = Utils.import_vector_map(map_path=path_name, output_name=map_name,
                                                    verbose=verbose, quiet=quiet)
            if _err:
                self.append_error(msgs=_errors, typ=self.get_feature_type())
            else:
                self.summary.set_process_line(msg_name='import_maps', check_error=_err,
                                              map_path=path_name, output_name=map_name)
                # check mandatory field
                _err, _ = self.check_basic_columns(map_name=map_name)
                if not _err:
                    self.map_names[map_name]['imported'] = True

        # re-projecting map if exists lower left edge
        if self.x_ll is not None and self.y_ll is not None and self.z_rotation is not None:
            self.set_origin_in_map()

        return self.check_errors(), self.get_errors()

    def set_origin_in_map(self):
        map_names = [m for m in self.get_map_names(only_names=False, with_main_file=True, imported=True) if m[1]]

        if self.x_ll is not None and self.y_ll is not None and self.z_rotation is not None:
            for map_name, path_name, inter_name in map_names:
                # get map lower left edge
                x_ini_ll, y_ini_ll = Utils.get_origin_from_map(map_name=map_name)

                # set the new origin
                x_offset_ll = self.x_ll - x_ini_ll
                y_offset_ll = self.y_ll - y_ini_ll
                map_name_out = '{}_transform'.format(map_name)
                _err, _errors = Utils.set_origin_in_map(map_name=map_name, map_name_out=map_name_out,
                                                        x_offset_ll=x_offset_ll, y_offset_ll=y_offset_ll, z_rotation=self.z_rotation)

                self.summary.set_process_line(msg_name='set_origin_in_map', check_error=_err,
                                              map_name=map_name, x_ll=self.x_ll, y_ll=self.y_ll, z_rot=self.z_rotation)
                if not _err:
                    self.set_map_name(map_name=map_name, map_path=path_name, map_new_name=map_name_out)
                else:
                    msg_error = 'Can not reproject map [{}] to x_ll=[{}], y_ll=[{}], z_rot=[{}]'.format(
                        map_name, self.x_ll, self.y_ll, self.z_rotation
                    )
                    self.append_error(msg=msg_error, typ=self.get_feature_type())

    def check_basic_columns(self, map_name: str):
        _err, _errors = False, []
        fields = self.get_needed_field_names()

        for field_key in [field for field in fields if fields[field]]:
            field_name = fields[field_key]['name']
            needed = fields[field_key]['needed']

            __err, __errors = Utils.check_basic_columns(map_name=map_name, columns=[field_name], needed=[needed])

            self.summary.set_process_line(msg_name='check_basic_columns', check_error=__err,
                                          map_name=map_name, columns=field_name)
            if needed:
                self.append_error(msgs=__errors, is_warn=False, typ=self.get_feature_type(), code='20')  # error code = 20
            else:
                self.append_error(msgs=__errors, is_warn=True, typ=self.get_feature_type(), code='20')

        return self.check_errors(code='20'), self.get_errors(code='20')

    def all_files_imported(self):
        imported = False
        for f_key in self.map_names:
            file_data = self.map_names[f_key]
            imported = imported and file_data['imported']

        return imported



