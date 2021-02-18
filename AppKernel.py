import os
import threading
import time

from grass.pygrass.utils import copy
from grass.pygrass.vector import VectorTopo
from grass_session import Session

import ui

import Utils
from CatchmentProcess import CatchmentProcess
from Config import ConfigApp
from DemandSiteProcess import DemandSiteProcess
from GeoKernel import GeoKernel
from GroundwaterProcess import GroundwaterProcess
from RiverProcess import RiverProcess
from Errors import ErrorManager
from SummaryInfo import SummaryInfo

from decorator import main_task
from decorator import TimerSummary


class AppKernel:
    def __init__(self, gisdb: str, location: str, mapset: str, epsg_code: int = None):
        self.__debug = False

        self.config = ConfigApp(epsg_code=epsg_code, gisdb=gisdb, location=location, mapset=mapset)
        self._err = ErrorManager(config=self.config)

        self.geo_processor = GeoKernel(config=self.config, err=self._err)
        self.catchment_processor = CatchmentProcess(geo=self.geo_processor, config=self.config, err=self._err)
        self.groundwater_processor = GroundwaterProcess(geo=self.geo_processor, config=self.config, err=self._err)
        self.demand_site_processor = DemandSiteProcess(geo=self.geo_processor, config=self.config, err=self._err)
        self.river_processor = RiverProcess(geo=self.geo_processor, config=self.config, err=self._err)
        self.consolidate_cells = None

        self._feature_type = self.config.type_names[self.__class__.__name__]

        # file paths
        self.linkage_in_paths = {}
        self.linkage_out_paths = {}
        self.arc_paths = {}
        self.node_paths = {}
        self.demand_site_paths = {}
        self.demand_site_wells_paths = {}
        self.gw_paths = {}
        self.catchment_paths = {}
        self.river_paths = {}

        self.stats = {}
        self.summary = SummaryInfo(prefix=self.get_feature_type(), errors=self._err, config=self.config)

    def set_origin(self, x_ll: float, y_ll: float, z_rotation: float):
        self.geo_processor.set_origin(x_ll=x_ll, y_ll=y_ll, z_rotation=z_rotation)
        self.catchment_processor.set_origin(x_ll=x_ll, y_ll=y_ll, z_rotation=z_rotation)
        self.groundwater_processor.set_origin(x_ll=x_ll, y_ll=y_ll, z_rotation=z_rotation)
        self.demand_site_processor.set_origin(x_ll=x_ll, y_ll=y_ll, z_rotation=z_rotation)
        self.river_processor.set_origin(x_ll=x_ll, y_ll=y_ll, z_rotation=z_rotation)

    def set_epsg(self, epsg_code: int):
        self.config.set_epsg(epsg_code=epsg_code)

    def set_gisdb(self, gisdb: str):
        self.config.set_gisdb(gisdb=gisdb)

    def set_location(self, location: str):
        self.config.set_location(location=location)

    def set_mapset(self, mapset: str):
        self.config.set_mapset(mapset=mapset)

    def get_main_summary(self):
        return self.summary

    def get_catchment_summary(self):
        return self.catchment_processor.get_summary()

    def get_gw_summary(self):
        return self.groundwater_processor.get_summary()

    def get_ds_summary(self):
        return self.demand_site_processor.get_summary()

    def get_river_summary(self):
        return self.river_processor.get_summary()

    def check_input_paths(self, required: bool = True, additional: bool = True):
        code_errors = []
        code_errors = code_errors + [str(num) for num in range(-11, -15, -1)] if required else code_errors
        code_errors = code_errors + [str(num) for num in range(-15, -19, -1)] if additional else code_errors

        errors = []
        for code in code_errors:
            err = self._err.get_errors(typ=self.get_feature_type(), code=code)
            errors = errors + err if err else errors

        return errors

    def exist_linkage_in_paths(self):
        map_data = self.get_linkage_in_names()
        return len(map_data) > 0

    def exist_linkage_out_paths(self):
        map_data = self.get_linkage_out_names()
        return len(map_data) > 0

    def exist_arc_paths(self):
        map_data = self.get_arc_map_names()
        return len(map_data) > 0

    def exist_node_paths(self):
        map_data = self.get_node_map_names()
        return len(map_data) > 0

    def exist_catchment_paths(self):
        map_data = self.get_catchment_map_names()
        return len(map_data) > 0

    def exist_groundwater_paths(self):
        map_data = self.get_groundwater_map_names()
        return len(map_data) > 0

    def exist_river_paths(self):
        map_data = self.get_river_map_names()
        return len(map_data) > 0

    def exist_demand_site_paths(self):
        map_data = self.get_demand_site_map_names()
        return len(map_data) > 0

    def get_arc_map_names(self):
        ret = self.geo_processor.get_arc_map_names()
        if not ret:
            ret = [('', '', '')]
        return ret

    def get_node_map_names(self):
        ret = self.geo_processor.get_node_map_names()
        if not ret:
            ret = [('', '', '')]
        return ret

    def get_linkage_in_names(self):
        ret = [(m['name'], m['path']) for m in self.linkage_in_paths.values()]
        if not ret:
            ret = [('', '')]
        return ret

    def get_linkage_out_names(self):
        ret = [(m['name'], m['path']) for m in self.linkage_out_paths.values()]
        if not ret:
            ret = [('', '')]
        return ret

    def get_demand_site_map_names(self):
        ret = self.demand_site_processor.get_map_names()
        if not ret:
            ret = [('', '', '')]
        return ret

    def get_catchment_map_names(self):
        ret = self.catchment_processor.get_map_names()
        if not ret:
            ret = [('', '', '')]
        return ret

    def get_groundwater_map_names(self):
        ret = self.groundwater_processor.get_map_names()
        if not ret:
            ret = [('', '', '')]
        return ret

    def get_river_map_names(self):
        ret = self.river_processor.get_map_names()
        if not ret:
            ret = [('', '', '')]
        return ret

    def set_linkage_in_file(self, file_path: str):
        if not file_path:
            return False, []

        exist_files, _ = Utils.check_paths_exist(files=[file_path])

        if exist_files[0][0]:
            # map_name = os.path.splitext(os.path.basename(file_path))[0][0:30].lower()  # truncate to 30 chars and lower case
            # check if it is a shapefile
            if Utils.check_file_extension(file_path=file_path, ftype='shp'):
                map_name = Utils.get_map_name_standard(f_path=file_path)  # truncate to 30 chars and lower case
                self.linkage_in_paths[map_name] = {
                    'name': map_name,
                    'path': file_path
                }
            else:
                msg_error = 'El archivo [{}] no es un shapefile'.format(file_path)
                self.append_error(msg=msg_error, is_warn=False, code='-11')
        else:
            # linkage-in problem with error code [-11]
            self.append_error(msg=exist_files[0][1], is_warn=False, code='-11')

        return self.check_errors(code='-11'), self.get_errors(code='-11')

    def set_linkage_out_file(self, folder_path: str):
        if not folder_path:
            return False, []

        _, exist_folders = Utils.check_paths_exist(folders=[folder_path])

        if exist_folders[0][0]:
            file_name = self.config.get_linkage_out_file_name()
            file_name_full_path = os.path.join(folder_path, file_name)
            # map_name = self.config.linkage_out
            map_name = Utils.get_map_name_standard(f_path=file_name_full_path)  # truncate to 30 chars and lower case
            self.linkage_out_paths[map_name] = {
                'name': map_name,
                'path': folder_path  # os.path.join(folder_path, map_name)
            }
        else:
            # linkage-out problem with error code [-12]
            self.append_error(msg=exist_folders[0][1], is_warn=False, code='-12')

        return self.check_errors(code='-12'), self.get_errors(code='-12')

    def set_node_file(self, file_path: str):
        if not file_path:
            return False, []

        exist_files, _ = Utils.check_paths_exist(files=[file_path])

        if exist_files[0][0]:
            # map_name = os.path.splitext(os.path.basename(file_path))[0][0:30].lower()  # truncate to 30 chars and lower case
            # check if it is a shapefile
            if Utils.check_file_extension(file_path=file_path, ftype='shp'):
                map_name = Utils.get_map_name_standard(f_path=file_path)  # truncate to 30 chars and lower case
                self.node_paths[map_name] = {
                    'name': map_name,
                    'path': file_path
                }
            else:
                msg_error = 'El archivo [{}] no es un shapefile'.format(file_path)
                self.append_error(msg=msg_error, is_warn=False, code='-13')
        else:
            # node file problem with error code [-13]
            self.append_error(msg=exist_files[0][1], is_warn=False, code='-13')

        return self.check_errors(code='-13'), self.get_errors('-13')

    def set_arc_file(self, file_path: str, is_main_file: bool = False):
        if not file_path:
            return False, []

        exist_files, _ = Utils.check_paths_exist(files=[file_path])

        if exist_files[0][0]:
            # map_name = os.path.splitext(os.path.basename(file_path))[0][0:30].lower()  # truncate to 30 chars and lower case
            # check if it is a shapefile
            if Utils.check_file_extension(file_path=file_path, ftype='shp'):
                map_name = Utils.get_map_name_standard(f_path=file_path)  # truncate to 30 chars and lower case
                self.arc_paths[map_name] = {
                    'name': map_name,
                    'path': file_path
                }
            else:
                msg_error = 'El archivo [{}] no es un shapefile'.format(file_path)
                self.append_error(msg=msg_error, is_warn=False, code='-14')
        else:
            # arc file problem with error code [-14]
            self.append_error(msg=exist_files[0][1], is_warn=False, code='-14')

        return self.check_errors(code='-14'), self.get_errors(code='-14')

    def set_groundwater_file(self, file_path: str, is_main_file: bool = False):
        if not file_path:
            return False, []

        exist_files, _ = Utils.check_paths_exist(files=[file_path])

        if exist_files[0][0]:
            # map_name = os.path.splitext(os.path.basename(file_path))[0][0:30].lower()  # truncate to 30 chars and lower case
            # check if it is a shapefile
            if Utils.check_file_extension(file_path=file_path, ftype='shp'):
                map_name = Utils.get_map_name_standard(f_path=file_path)  # truncate to 30 chars and lower case
                self.gw_paths[map_name] = {
                    'name': map_name,
                    'path': file_path,
                    'is_main': is_main_file
                }
            else:
                msg_error = 'El archivo [{}] no es un shapefile'.format(file_path)
                self.append_error(msg=msg_error, is_warn=False, code='-16')
        else:
            # gw file problem with error code [-16]
            self.append_error(msg=exist_files[0][1], is_warn=False, code='-16')

        return self.check_errors(code='-16'), self.get_errors(code='-16')

    def set_catchment_file(self, file_path: str, is_main_file: bool = False):
        if not file_path:
            return False, []

        exist_files, _ = Utils.check_paths_exist(files=[file_path])

        if exist_files[0][0]:
            # map_name = os.path.splitext(os.path.basename(file_path))[0][0:30].lower()  # truncate to 30 chars and lower case
            # check if it is a shapefile
            if Utils.check_file_extension(file_path=file_path, ftype='shp'):
                map_name = Utils.get_map_name_standard(f_path=file_path)  # truncate to 30 chars and lower case
                self.catchment_paths[map_name] = {
                    'name': map_name,
                    'path': file_path,
                    'is_main': is_main_file
                }
            else:
                msg_error = 'El archivo [{}] no es un shapefile'.format(file_path)
                self.append_error(msg=msg_error, is_warn=False, code='-15')
        else:
            # catchment file problem with error code [-15]
            self.append_error(msg=exist_files[0][1], is_warn=False, code='-15')

        return self.check_errors(code='-15'), self.get_errors(code='-15')

    def set_river_file(self, file_path: str, is_main_file: bool = False):
        if not file_path:
            return False, []

        exist_files, _ = Utils.check_paths_exist(files=[file_path])

        if exist_files[0][0]:
            # map_name = os.path.splitext(os.path.basename(file_path))[0][0:30].lower()  # truncate to 30 chars and lower case
            # check if it is a shapefile
            if Utils.check_file_extension(file_path=file_path, ftype='shp'):
                map_name = Utils.get_map_name_standard(f_path=file_path)  # truncate to 30 chars and lower case
                self.river_paths[map_name] = {
                    'name': map_name,
                    'path': file_path,
                    'is_main': is_main_file
                }
            else:
                msg_error = 'El archivo [{}] no es un shapefile'.format(file_path)
                self.append_error(msg=msg_error, is_warn=False, code='-18')
        else:
            # river file problem with error code [-18]
            self.append_error(msg=exist_files[0][1], is_warn=False, code='-18')

        return self.check_errors(code='-18'), self.get_errors(code='-18')

    def set_demand_site_folder(self, folder_path):
        if not folder_path:
            return False, []

        # check if path exists
        _, exist_folders = Utils.check_paths_exist(folders=[folder_path])
        if exist_folders[0][0]:
            # load files in path
            files = Utils.get_file_names(folder_path=folder_path, ftype='shp')

            # put in [demand_site_paths]
            for file_name in files:
                # map_name = os.path.splitext(os.path.basename(file_name))[0][0:30].lower()  # truncate to 30 chars and lower case
                map_name = Utils.get_map_name_standard(f_path=file_name)  # truncate to 30 chars and lower case
                self.demand_site_paths[map_name] = {
                    'name': map_name,
                    'path': file_name,
                    'is_main': False
                }

            files = Utils.get_file_names(folder_path=folder_path, ftype='txt')

            # put in [demand_site_wells_paths]
            for file_name in files:
                wells_name = os.path.splitext(os.path.basename(file_name))[0][0:30].lower()
                self.demand_site_wells_paths[wells_name] = {
                    'name': wells_name,
                    'path': file_name
                }

        else:
            # ds folder problem with error code [-17]
            self.append_error(msg=exist_folders[0][1], is_warn=False, code='-17')

        return self.check_errors(code='-17'), self.get_errors(code='-17')

    def get_feature_type(self):
        return self._feature_type

    def set_config_field(self, catchment_field: str = None, modflow_field: str = None,
                         groundwater_field: str = None, demand_site_field: str = None):
        _err = False
        if catchment_field:
            domain = self.catchment_processor.get_feature_type()
            _err += self.config.set_config_field(feature_type=domain, field_type='main', field_new_name=catchment_field)

        if modflow_field:
            domain = self.catchment_processor.get_feature_type()
            _err += self.config.set_config_field(feature_type=domain, field_type='limit', field_new_name=modflow_field)

        if groundwater_field:
            domain = self.groundwater_processor.get_feature_type()
            _err += self.config.set_config_field(feature_type=domain, field_type='main', field_new_name=groundwater_field)

        if demand_site_field:
            domain = self.demand_site_processor.get_feature_type()
            _err += self.config.set_config_field(feature_type=domain, field_type='main', field_new_name=demand_site_field)

        return _err

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
        # TODO: refactor function to be similar to get_errors in FeatureProcess
        errors = {}
        procs = (self.geo_processor, self.catchment_processor, self.groundwater_processor, self.demand_site_processor, self.river_processor)
        for proc in procs:
            feature_type = proc.get_feature_type()

            errors[feature_type] = proc.get_errors(code=code).copy()
        errors[self.get_feature_type()] = self._err.get_errors(typ=self.get_feature_type(), code=code)

        return errors

    def get_general_linkage_columns(self):  # get general columns
        ret = [self.config.cols_linkage['row']]

    @TimerSummary.timeit
    # @main_task
    def export_to_shapefile(self, map_name, output_path):
        _err, _errors = Utils.export_to_shapefile(map_name, output_path, file_name='{}.shp'.format(map_name), verbose=False, quiet=True)
        self.append_error(msgs=_errors) if _err else None

        msg_info = self.config.get_process_msg(msg_name='export_to_shapefile')
        if _err:
            self.append_error(msgs=_errors)

        self.summary.set_process_line(msg_name='export_to_shapefile', check_error=_err,
                                      map_name=map_name, output_path=output_path)

        return _err, _errors

    def check_path_exist(self, file: str = None, folder: str = None):
        if file:
            result_files, result_folders = Utils.check_paths_exist(files=[file])
            _exist, _error = result_files[0]
        elif folder:
            result_files, result_folders = Utils.check_paths_exist(folders=[folder])
            _exist, _error = result_folders[0]
        else:
            _exist, _error = False, 'Falta indicar path a validar (file | folder)'

        return _exist, _error

    def get_consolidate_cells(self):
        _err, _errors = False, []

        alldata = [self.catchment_processor.get_cell_keys(), self.groundwater_processor.get_cell_keys(),
                   self.demand_site_processor.get_cell_keys(), self.river_processor.get_cell_keys()]
        cell_keys = set().union(*alldata)

        consolidate_cells = {}
        for cell in cell_keys:
            consolidate_cells[cell] = {
                'catchment': None,
                'groundwater': None,
                'river': None,
                'demand_site': None
            }

            consolidate_cells[cell]['catchment'] = self.catchment_processor.get_cell_id_data(cell)
            consolidate_cells[cell]['groundwater'] = self.groundwater_processor.get_cell_id_data(cell)
            consolidate_cells[cell]['demand_site'] = self.demand_site_processor.get_cell_id_data(cell)
            consolidate_cells[cell]['river'] = self.river_processor.get_cell_id_data(cell)

        self.consolidate_cells = consolidate_cells
        return _err, _errors

    @TimerSummary.timeit
    # @main_task
    def init_linkage_file(self, linkage_name: str, linkage_new_name: str = 'linkage_new'):
        import sqlite3
        from grass.pygrass.vector.table import Columns

        _err, _errors = False, []

        copy(linkage_name, linkage_new_name, 'vect', overwrite=True)  # get a copy from linkage map

        # TODO: need to check if sqlite is the database engine
        vector_map = VectorTopo(linkage_new_name)
        vector_map.open('r')
        db_path = vector_map.dblinks[0].database
        vector_map.close()

        cols_sqlite = Columns(linkage_new_name, sqlite3.connect(db_path))
        # print('COLUMNS INIT: ', cols_sqlite.items()) if self.__debug else None

        # check if linkage vector map has base fields (flopy way)
        __columns_from_in = [x for l in [(t[0], t[0].lower()) for t in cols_sqlite.items()] for x in l]

        # remove al old columns
        # TODO: do not remove row and col, because it only fill cells with value, not all cells
        fields = self.get_needed_field_names()
        row_field, col_field = fields['main']['name'], fields['secondary']['name']
        for col_in in [c[0] for c in cols_sqlite.items() if c[0] != cols_sqlite.key]:
            if col_in not in (row_field, col_field):
                cols_sqlite.drop(col_in)  # remove

        # add columns in config
        cols = self.get_linkage_out_columns()
        for col_name, col_type in cols:
            cols_sqlite.add([col_name], [col_type])

        self.summary.set_process_line(msg_name='init_linkage_file', check_error=self.check_errors(),
                                      linkage_name=linkage_name, linkage_new_name=linkage_new_name)

        return self.check_errors(), self.get_errors()

    @TimerSummary.timeit
    # @main_task
    def mark_linkage_active(self, linkage_name, save_changes=100):
        # consolidate [catchment_cells], [gw_cells], [river_cells] and [demand_site_cells]
        _, _ = self.get_consolidate_cells()

        linkage_map = VectorTopo(linkage_name)
        linkage_map.open('rw')

        for i, cell in enumerate(self.consolidate_cells):
            catchment_data = self.consolidate_cells[cell]['catchment']
            gw_data = self.consolidate_cells[cell]['groundwater']
            river_data = self.consolidate_cells[cell]['river']
            demand_site_data = self.consolidate_cells[cell]['demand_site']

            feature_id = None
            demand_names = ['', '', '', '']
            if catchment_data:
                feature_id = catchment_data['cell_id']
            if gw_data:
                feature_id = gw_data['cell_id']
            if river_data:
                feature_id = river_data['cell_id']
            if demand_site_data:
                feature_id = demand_site_data['cell_id']

            values_dict_catchment = self.catchment_processor.get_data_to_save(cell=cell, main_data=True)
            values_dict_gw = self.groundwater_processor.get_data_to_save(cell=cell, main_data=True)
            values_dict_river = self.river_processor.get_data_to_save(cell=cell, main_data=True)
            values_dict_ds = self.demand_site_processor.get_data_to_save(cell=cell, main_data=True)
            values_required = dict(**values_dict_catchment, **values_dict_gw, **values_dict_river, **values_dict_ds)

            values_dict_ad_catchment = self.catchment_processor.get_data_to_save(cell=cell, main_data=False)
            values_dict_ad_gw = self.groundwater_processor.get_data_to_save(cell=cell, main_data=False)
            values_dict_ad_river = self.river_processor.get_data_to_save(cell=cell, main_data=False)
            values_dict_ad_ds = self.demand_site_processor.get_data_to_save(cell=cell, main_data=False)
            values_ad = dict(**values_dict_ad_catchment, **values_dict_ad_gw, **values_dict_ad_river, **values_dict_ad_ds)

            values_dict = dict(**values_required, **values_ad)
            values_dict[self.config.cols_linkage['row']['name']] = cell.row
            values_dict[self.config.cols_linkage['col']['name']] = cell.col
            values_dict[self.config.cols_linkage['MF_RC']['name']] = '{}x{}'.format(cell.row, cell.col)

            # prepare data to save
            feature = linkage_map.read(feature_id)
            col_keys, col_values = Utils.make_values_to_db(vector_map=linkage_map, values_dict=values_dict)

            # save values in [linkage]
            linkage_map.rewrite(feature, cat=feature_id, attrs=col_values)
            # linkage_map.table.conn.commit()

            if i % save_changes == 0:  # save changes into DB
                linkage_map.table.conn.commit()

            i += 1
        else:
            linkage_map.table.conn.commit()

        linkage_map.close()

        self.summary.set_process_line(msg_name='mark_linkage_active', check_error=self.check_errors(),
                                      linkage_name=linkage_name)

        return self.check_errors(), self.get_errors()

    @TimerSummary.timeit
    def import_vector_map(self, map_paths: list, output_names: list):
        for ind, map_path in enumerate(map_paths):
            output_name = output_names[ind]
            _err_o, _errors = Utils.import_vector_map(map_path=map_path, output_name=output_name)
            self.append_error(msgs=_errors) if _err_o else None

            self.summary.set_process_line(msg_name='import_maps', check_error=_err_o,
                                          map_path=map_path, output_name=output_name)

    def check_errors(self, types: list = None, opc_all: bool = False, is_warn: bool = False, code: str = ''):
        if is_warn:
            if opc_all:
                types = self._err.get_error_types()
                return self._err.check_warning(types=types, code=code)
            else:
                if types:
                    return self._err.check_warning(types=types, code=code)
                else:
                    return self._err.check_warning(typ=self.get_feature_type(), code=code)
        else:
            if opc_all:
                types = self._err.get_error_types()
                return self._err.check_error(types=types, code=code)
            else:
                if types:
                    return self._err.check_error(types=types, code=code)
                else:
                    return self._err.check_error(typ=self.get_feature_type(), code=code)

    def print_errors(self, words: list = [], all_errors: bool = False, is_warn: bool = False, ui_opt: bool = True):
        prefix_err = 'ERRORS' if not is_warn else 'WARNINGS'
        Utils.show_title(msg_title='{} SUMMARY'.format(prefix_err), title_color=ui.red)

        if all_errors:
            types = self._err.get_error_types()
            self._err.print_ui(types=types, is_warn=is_warn)
        else:
            self._err.print_ui(typ=self.get_feature_type(), is_warn=is_warn)

    def get_needed_field_names(self):
        fields = {
            'main': {
                'name': self.config.fields_db['linkage-in']['row'],
                'needed': True
            },
            'secondary': {
                'name': self.config.fields_db['linkage-in']['col'],
                'needed': True
            },
            'limit': {
                'name': self.config.fields_db['linkage-in']['col'],
                'needed': True
            },
        }

        return fields

    def check_basic_columns(self, map_name: str):
        _err, _errors = False, []
        fields = self.get_needed_field_names()

        column_names = []
        needed = []
        for field_key in fields:
            field_name = fields[field_key]['name']
            needed = fields[field_key]['needed']

            if field_name not in column_names:
                __err, __errors = Utils.check_basic_columns(map_name=map_name, columns=[field_name], needed=[needed])
                self.summary.set_process_line(msg_name='check_basic_columns', check_error=__err,
                                              map_name=map_name, columns=[field_name], needed=[needed])

                _errors += __errors
                if needed:
                    _err |= __err

                column_names.append(field_name)

        self.append_error(msgs=_errors, typ='other')

        return _err, _errors

    def set_map_names(self):

        for map_name, map_path in [(m['name'], m['path']) for m in self.arc_paths.values()]:
            self.geo_processor.set_arc_map_names(map_name=map_name, map_path=map_path)

        for map_name, map_path in [(m['name'], m['path']) for m in self.node_paths.values()]:
            self.geo_processor.set_node_map_names(map_name=map_name, map_path=map_path)

        for map_name, map_path, is_main in [(m['name'], m['path'], m['is_main']) for m in self.catchment_paths.values()]:
            self.catchment_processor.set_map_name(map_name=map_name, map_path=map_path, is_main_file=is_main)

        for map_name, map_path, is_main in [(m['name'], m['path'], m['is_main']) for m in self.gw_paths.values()]:
            self.groundwater_processor.set_map_name(map_name=map_name, map_path=map_path, is_main_file=is_main)

        for map_name, map_path, is_main in [(m['name'], m['path'], m['is_main']) for m in self.river_paths.values()]:
            self.river_processor.set_map_name(map_name=map_name, map_path=map_path, is_main_file=is_main)

            # if map is arc map, the intersection map is with 'lines' geos
            if map_name in self.arc_paths:
                self.river_processor.set_inter_map_geo_type(map_key=map_name, geo_map_type='lines')

        # demand sites
        for map_name, map_path, is_main in [(m['name'], m['path'], m['is_main']) for m in self.demand_site_paths.values()]:
            self.demand_site_processor.set_map_name(map_name=map_name, map_path=map_path, is_main_file=False)

        # demand site wells
        for well_name, well_path in [(m['name'], m['path']) for m in self.demand_site_wells_paths.values()]:
            self.demand_site_processor.set_well(well_name=well_name, well_path=well_path)

    def get_linkage_out_columns(self):
        tmp = ('MF_RC', 'LANDUSE')
        cols_general = [(self.config.cols_linkage[c]['name'], self.config.cols_linkage[c]['type']) for c in tmp]

        catchment_cols_general = self.catchment_processor.get_columns(main_data=True, with_type=True)
        gw_cols_general = self.groundwater_processor.get_columns(main_data=True, with_type=True)
        river_cols_general = self.river_processor.get_columns(main_data=True, with_type=True)
        ds_cols_general = self.demand_site_processor.get_columns(main_data=True, with_type=True)
        cols_general += catchment_cols_general + gw_cols_general + river_cols_general + ds_cols_general

        catchment_cols_adt = self.catchment_processor.get_columns(main_data=False, with_type=True)
        gw_cols_adt = self.groundwater_processor.get_columns(main_data=False, with_type=True)
        river_cols_adt = self.river_processor.get_columns(main_data=False, with_type=True)
        ds_cols_adt = self.demand_site_processor.get_columns(main_data=False, with_type=True)
        cols_adt = catchment_cols_adt + gw_cols_adt + river_cols_adt + ds_cols_adt

        return cols_general + cols_adt

    def set_origin_in_node_arc_maps(self, map_names: list):
        x_ll, y_ll, z_rotation = self.geo_processor.x_ll, self.geo_processor.y_ll, self.geo_processor.z_rotation

        if x_ll is not None and y_ll is not None and z_rotation is not None:
            for map_name in map_names:
                # get map lower left edge
                x_ini_ll, y_ini_ll = Utils.get_origin_from_map(map_name=map_name)

                # set the new origin
                x_offset_ll = x_ll - x_ini_ll
                y_offset_ll = y_ll - y_ini_ll
                map_name_out = '{}_transform'.format(map_name)
                _err, _errors = Utils.set_origin_in_map(map_name=map_name, map_name_out=map_name_out,
                                                        x_offset_ll=x_offset_ll, y_offset_ll=y_offset_ll, z_rotation=z_rotation)

                self.summary.set_process_line(msg_name='set_origin_in_map', check_error=_err,
                                              map_name=map_name, x_ll=x_ll, y_ll=y_ll, z_rot=z_rotation)
                if not _err:
                    self.geo_processor.update_map_name(map_name=map_name, map_new_name=map_name_out)
                else:
                    msg_error = 'Can not reproject map [{}] to x_ll=[{}], y_ll=[{}], z_rot=[{}]'.format(
                        map_name, x_ll, y_ll, z_rotation
                    )
                    self.append_error(msg=msg_error, typ=self.get_feature_type())

    def run(self):
        ts = time.time()
        _err = False

        # ==============================================================================================================
        # Path and Map names
        # ==============================================================================================================
        # set map names into de Processors (catchments, groundwaters, rivers and demand sites)
        self.set_map_names()

        # Necessary Files
        if not (self.exist_arc_paths() and self.exist_node_paths() and self.exist_linkage_in_paths() and self.exist_linkage_out_paths()):
            raise RuntimeError('[EXIT] UNO DE LOS ARCHIVOS IMPORTANTES NO EXISTE')

        linkage_name, linkage_file_path = self.get_linkage_in_names()[0]  # only one file
        linkage_new_name, linkage_out_folder_path = self.get_linkage_out_names()[0]  # only one file
        arc_name, weaparc_file_path, _ = self.get_arc_map_names()[0]  # only one file
        node_name, weapnode_file_path, _ = self.get_node_map_names()[0]  # only one file

        # import files (and clean [v.clean])
        self.import_vector_map(map_paths=[linkage_file_path, weaparc_file_path, weapnode_file_path],
                               output_names=[linkage_name, arc_name, node_name])

        # re-projecting map if exists lower left edge
        if self.geo_processor.x_ll is not None and self.geo_processor.y_ll is not None \
                and self.geo_processor.z_rotation is not None:
            self.set_origin_in_node_arc_maps(map_names=[arc_name, node_name])

        # check needed columns in linkage map
        _err, _ = self.check_basic_columns(map_name=linkage_name)
        if _err:
            raise RuntimeError('[EXIT] ARCHIVO LINKAGE DE ENTRADA NO TIENE COLUMNAS BASE')

        # Open map and topology
        arc_map = VectorTopo(arc_name)
        arc_map.open()
        node_map = VectorTopo(node_name)
        node_map.open()

        # basic geometries processing
        _err, _ = self.geo_processor.setup_arcs(arcmap=arc_map, nodemap=node_map)
        if _err:
            self.print_errors()
            raise RuntimeError('[EXIT] ERROR AL LEER GEOMETRIAS DESDE ESQUEMA WEAP')

        # -------------------------------------------------------------------------------
        # Catchments Logic
        # -------------------------------------------------------------------------------
        # import files to vector maps
        self.catchment_processor.run(linkage_name=linkage_name)

        # -------------------------------------------------------------------------------
        # GWS Logic
        # -------------------------------------------------------------------------------
        # import files to vector maps
        self.groundwater_processor.run(linkage_name=linkage_name)

        # -------------------------------------------------------------------------------
        # Demand Sites Logic
        # -------------------------------------------------------------------------------
        # import files to vector maps
        self.demand_site_processor.run(linkage_name=linkage_name)

        # -------------------------------------------------------------------------------
        # Rivers Logic
        # -------------------------------------------------------------------------------
        # import files to vector maps
        self.river_processor.run(linkage_name=linkage_name)

        # -------------------------------------------------------------------------------
        # General Logic
        # -------------------------------------------------------------------------------
        # Utils.show_title(msg_title='GENERAL', title_color=ui.green)

        # make a linkage map copy and format with the base linkage cols
        _err, _ = self.init_linkage_file(linkage_name, linkage_new_name=linkage_new_name)
        if _err:
            self.print_errors()
            raise RuntimeError('[EXIT] NO ES POSIBLE FORMATEAR LINKAGE')

        # copy active cells and put catchment names into linkage map
        _err, _ = self.mark_linkage_active(linkage_new_name, save_changes=100)
        if _err:
            self.print_errors()
            raise RuntimeError('[EXIT] NO ES POSIBLE ESCRIBIR EN LINKAGE')

        # export to shapefile
        self.export_to_shapefile(map_name=linkage_new_name, output_path=linkage_out_folder_path)

        arc_map.close()
        node_map.close()

        # _err = self.check_errors(types=self._err.get_error_types())
        # if _err:
        #     self.print_errors(all_errors=True, is_warn=False)
        # self.print_errors(all_errors=True, is_warn=True)

        # print processing times
        # Utils.show_title(msg_title='PROCESSING TIMES', title_color=ui.brown)
        # headers = ["FUNCTION", "ms"]
        # ui.info_table(TimerSummary.get_summary_by_function(), headers=headers)

        # te = time.time()
        # ui.info('FINAL TIME: [{}] ms'.format((te-ts) * 1000))

        return _err, self.get_errors()
