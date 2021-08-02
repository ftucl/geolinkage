import os
from abc import abstractmethod, ABCMeta
import ui

from utils.Utils import GrassCoreAPI, UtilMisc
from utils.Config import ConfigApp
from utils.Errors import ErrorManager


class ErrorProtocol:
    """
    El objetivo de esta clase utilitaria es proveer de los distintos metodos para manejar los errores y advertencias que ocurren
    durante la ejecucion.

    * Archivo de configuracion: ./config/config.json

    """

    def __init__(self, config: ConfigApp, error: ErrorManager):
        self._err = error
        self.__config = config

    def append_error(self, typ: str, msg: str = None, msgs: list = (), is_warn: bool = False, code: str = ''):
        typ = typ if typ else self.__config.type_names['AppKernel']

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
        return self._err.get_errors(code=code)

    def check_errors(self, types: list = (), opc_all: bool = False, is_warn: bool = False, code: str = ''):
        if is_warn:
            if opc_all:
                types = self._err.get_error_types()
                return self._err.check_warning(types=types, code=code)
            else:
                if len(types) > 1:
                    return self._err.check_warning(types=types, code=code)
                elif len(types) == 1:
                    feature_type = types[0]
                    return self._err.check_warning(typ=feature_type, code=code)
                else:
                    return self._err.check_warning(code=code)
        else:
            if opc_all:
                types = self._err.get_error_types()
                return self._err.check_error(types=types, code=code)
            else:
                if len(types) > 1:
                    return self._err.check_error(types=types, code=code)
                elif len(types) == 1:
                    feature_type = types[0]
                    return self._err.check_error(typ=feature_type, code=code)
                else:
                    return self.check_errors(opc_all=True, is_warn=is_warn, code=code)

    def print_errors(self, feature_type: str, words: list = (), all_errors: bool = False, is_warn: bool = False, ui_opt: bool = True):
        prefix_err = 'ERRORS' if not is_warn else 'WARNINGS'
        UtilMisc.show_title(msg_title='{} SUMMARY'.format(prefix_err), title_color=ui.red)

        if all_errors:
            types = self._err.get_error_types()
            self._err.print_ui(types=types, is_warn=is_warn)
        else:
            self._err.print_ui(typ=feature_type, is_warn=is_warn)

    def check_input_path_errors(self, required: bool = True, additional: bool = True):
        codes = ConfigApp.error_codes

        input_codes = []
        if required:
            input_codes += [codes['node_file'], codes['arc_file'], codes['not_found_file'],
                            codes['linkage_in_file'], codes['linkage_out_file']]
        if additional:
            input_codes.append(codes['feature_file'])

        errors = []
        for code in input_codes:
            err = self._err.get_errors(code=code)
            errors = errors + err if err else errors

        return errors


class MapFileManagerProtocol(ErrorProtocol, metaclass=ABCMeta):
    """
    El objetivo de esta clase utilitaria es trabajar con los archivos de las distintas entradas a la aplicacion, su
    transformacion en los mapas vectoriales asociados en GRASS y el manejo de las columnas en la metadata tanto de las
    entradas como del archivo final.

    * Archivo de configuracion: ./config/config.json

    Attributes:
    ----------

    feature_file_paths : Dict[str, Dict[str, Dict[str, Any]]]
        Usado para almacenar estados y ruta de malla inicial.
        Usado para almacenar ruta de malla final.
        Usado para almacenar estados y ruta de del SHP de nodos.
        Usado para almacenar estados y ruta del SHP de arcos.
        Usado para almacenar ruta del directorio de mapas de DS.
        Usado para almacenar estados y ruta del archivo de pozos (.txt).
        Usado para almacenar estados y ruta del mapa de acuiferos.
        Usado para almacenar estados y ruta del mapa de cuencas.
        Usado para almacenar estados y ruta del mapa de rios (actualmente es el mismo que el SHP del esquema superficial).

    cells_by_map :
        Ordena las celdas por los mapas asociados. Almacena por cada mapa vectorial las celdas asociadas.

    map_names : Dict[str, Dict[str, bool | str ]
        Usado para administrar el estado de los mapas vectorial(es) asociado(s) a la caracteristica.

    arc_map_names : Dict[str, Dict[str, bool | str ]

    node_map_names : Dict[str, Dict[str, bool | str ]


    Methods:
    -------

    """
    feature_file_paths = {}

    @classmethod
    def build_path_structure(cls):
        if len(cls.feature_file_paths) == 0:
            tmp_conf = ConfigApp()

            feature_names = tmp_conf.get_feature_names()
            for feature_name in feature_names:
                cls.feature_file_paths[feature_name] = {}
                if feature_name not in (tmp_conf.type_names['AppKernel'], tmp_conf.type_names['GeoKernel']):
                    cls.feature_file_paths[feature_name]['path'] = {}

            cls.feature_file_paths[tmp_conf.type_names['DemandSiteProcess']]['well_path'] = {}
            cls.feature_file_paths[tmp_conf.type_names['GeoKernel']]['node_path'] = {}
            cls.feature_file_paths[tmp_conf.type_names['GeoKernel']]['arc_path'] = {}
            cls.feature_file_paths[tmp_conf.type_names['AppKernel']]['linkage_in_path'] = {}
            cls.feature_file_paths[tmp_conf.type_names['AppKernel']]['linkage_out_path'] = {}

    def __init__(self, config: ConfigApp, error: ErrorManager):
        super().__init__(config=config, error=error)

        self.__err = error
        self.__config = config

        self.arc_map_names = {}  # 'name' 'path' 'inter' 'imported'
        self.node_map_names = {}  # 'name' 'path' 'inter' 'imported'
        self.map_names = {}  # 'name' 'path' 'inter' 'inter_geo_type' 'is_main' 'imported'
        self.cells_by_map = {}  # [map_name_i] = [cell_i_1, ..., cell_i_j]

        # build basic structure of path
        MapFileManagerProtocol.build_path_structure()

    def set_feature_file_path(self, feature_type: str, file_path: str, is_main_file: bool = False):
        code_error = ConfigApp.error_codes['feature_file']  # code error for feature input files

        if not file_path:
            return False, []

        exist_files, _ = UtilMisc.check_paths_exist(files=[file_path])
        if exist_files[0][0]:
            if feature_type in MapFileManagerProtocol.feature_file_paths:
                feature = MapFileManagerProtocol.feature_file_paths[feature_type]

                # check if it is a shapefile
                if UtilMisc.check_file_extension(file_path=file_path, ftype='shp'):
                    map_name = UtilMisc.get_map_name_standard(f_path=file_path)  # truncate to 30 chars and lower case
                    feature['path'][map_name] = {
                        'name': map_name,
                        'path': file_path,
                        'is_main': is_main_file
                    }
                else:
                    msg_error = 'El archivo [{}] no es un shapefile'.format(file_path)
                    self.append_error(typ=feature_type, msg=msg_error, is_warn=False, code=code_error)
            else:
                msg_error = 'Feature type [{}] for file [{}] is not implemented'.format(feature_type, file_path)
                self.append_error(typ=feature_type, msg=msg_error, is_warn=False, code=code_error)

        else:
            self.append_error(typ=feature_type, msg=exist_files[0][1], is_warn=False, code=code_error)

        return self.check_errors(code=code_error), self.get_errors(code=code_error)

    def set_demand_site_well(self, file_path: str):
        if not file_path:
            return False, []

        code_error = ConfigApp.error_codes['well_file']  # code error for well input file
        feature_type = self.__config.type_names['DemandSiteProcess']

        exist_files, _ = UtilMisc.check_paths_exist(files=[file_path])
        if exist_files[0][0]:
            well_var_path = MapFileManagerProtocol.feature_file_paths[feature_type]['well_path']

            well_name = os.path.splitext(os.path.basename(file_path))[0][0:30].lower()
            well_var_path[well_name] = {
                'name': well_name,
                'path': file_path
            }
        else:
            self.append_error(typ=feature_type, msg=exist_files[0][1], is_warn=False, code=code_error)

        return self.check_errors(code=code_error), self.get_errors(code=code_error)

    def set_linkage_out_file(self, folder_path: str):
        code_error = ConfigApp.error_codes['linkage_out_file']   # code error for output file
        feature_type = self.__config.type_names['AppKernel']

        if not folder_path:
            return False, []

        _, exist_folders = UtilMisc.check_paths_exist(folders=[folder_path])

        if exist_folders[0][0]:
            feature = MapFileManagerProtocol.feature_file_paths[feature_type]

            file_name = self.__config.get_linkage_out_file_name()
            file_name_full_path = os.path.join(folder_path, file_name)

            map_name = UtilMisc.get_map_name_standard(f_path=file_name_full_path)  # truncate to 30 chars and lower case
            feature['linkage_out_path'][map_name] = {
                'name': map_name,
                'path': folder_path  # os.path.join(folder_path, map_name)
            }
        else:
            # linkage-out problem with error code
            self.append_error(typ=feature_type, msg=exist_folders[0][1], is_warn=False, code=code_error)

        return self.check_errors(code=code_error), self.get_errors(code=code_error)

    def set_linkage_in_file(self, file_path: str):
        code_error = ConfigApp.error_codes['linkage_in_file']  # code error for input linkage file
        feature_type = self.__config.type_names['AppKernel']

        if not file_path:
            return False, []

        exist_files, _ = UtilMisc.check_paths_exist(files=[file_path])

        if exist_files[0][0]:
            # check if it is a shapefile
            if UtilMisc.check_file_extension(file_path=file_path, ftype='shp'):
                feature = MapFileManagerProtocol.feature_file_paths[feature_type]

                map_name = UtilMisc.get_map_name_standard(f_path=file_path)  # truncate to 30 chars and lower case
                feature['linkage_in_path'][map_name] = {
                    'name': map_name,
                    'path': file_path
                }
            else:
                msg_error = 'El archivo [{}] no es un shapefile'.format(file_path)
                self.append_error(typ=feature_type, msg=msg_error, is_warn=False, code=code_error)
        else:
            # linkage-in problem with error code
            self.append_error(typ=feature_type, msg=exist_files[0][1], is_warn=False, code=code_error)

        return self.check_errors(code=code_error), self.get_errors(code=code_error)

    def set_geo_file_path(self, file_path: str, is_arc: bool = False, is_node: bool = False):
        if not file_path:
            return False, []

        feature_type = self.__config.type_names['GeoKernel']
        if is_arc:
            code_error = ConfigApp.error_codes['arc_file']  # code error for arc shapefile
            feature = MapFileManagerProtocol.feature_file_paths[feature_type]['arc_path']
        elif is_node:
            code_error = ConfigApp.error_codes['node_file']  # code error for node shapefile
            feature = MapFileManagerProtocol.feature_file_paths[feature_type]['node_path']
        else:
            feature = None
            code_error = ConfigApp.error_codes['not_found_file']
            msg_error = 'File [{}] must be an arc or node file. None selected.'.format(file_path)
            self.append_error(typ=feature_type, msg=msg_error, is_warn=False)

        exist_files, _ = UtilMisc.check_paths_exist(files=[file_path])
        if feature is not None and exist_files[0][0]:
            # check if it is a shapefile
            if UtilMisc.check_file_extension(file_path=file_path, ftype='shp'):
                map_name = UtilMisc.get_map_name_standard(f_path=file_path)  # truncate to 30 chars and lower case
                feature[map_name] = {
                    'name': map_name,
                    'path': file_path
                }
            else:
                msg_error = 'El archivo [{}] no es un shapefile'.format(file_path)
                self.append_error(typ=feature_type, msg=msg_error, is_warn=False, code=code_error)
        else:
            # node/arc file problem with error code
            self.append_error(typ=feature_type, msg=exist_files[0][1], is_warn=False, code=code_error)

        return self.check_errors(code=code_error), self.get_errors(code=code_error)

    def get_feature_file_paths(self, feature_type: str):
        f_main, f_geo = self.__config.type_names['AppKernel'], self.__config.type_names['GeoKernel']

        ret = [('', '', '')]
        if feature_type in MapFileManagerProtocol.feature_file_paths:
            if feature_type not in (f_main, f_geo):
                out_path = MapFileManagerProtocol.feature_file_paths[feature_type]['path']

                ret = [(m['name'], m['path'], m['is_main']) for m in out_path.values()]

        return ret

    def get_demand_site_well_paths(self):
        feature_ds_type = self.__config.type_names['DemandSiteProcess']

        ret = [('', '')]
        if feature_ds_type in MapFileManagerProtocol.feature_file_paths:
            out_path = MapFileManagerProtocol.feature_file_paths[feature_ds_type]['well_path']

            ret = [(m['name'], m['path']) for m in out_path.values()]

        return ret

    def get_linkage_out_file(self):
        feature_type = self.__config.type_names['AppKernel']
        out_path = MapFileManagerProtocol.feature_file_paths[feature_type]['linkage_out_path']

        ret = [('', '')]
        if feature_type in MapFileManagerProtocol.feature_file_paths:
            ret = [(m['name'], m['path']) for m in out_path.values()]

        return ret

    def get_linkage_in_file(self):
        feature_type = self.__config.type_names['AppKernel']
        out_path = MapFileManagerProtocol.feature_file_paths[feature_type]['linkage_in_path']

        ret = [('', '')]
        if feature_type in MapFileManagerProtocol.feature_file_paths:
            ret = [(m['name'], m['path']) for m in out_path.values()]

        return ret

    def get_geo_file_path(self, is_arc: bool = False, is_node: bool = False):
        feature_type = self.__config.type_names['GeoKernel']

        ret = [('', '')]
        if feature_type in MapFileManagerProtocol.feature_file_paths:
            if is_arc:
                out_path = MapFileManagerProtocol.feature_file_paths[feature_type]['arc_path']
            elif is_node:
                out_path = MapFileManagerProtocol.feature_file_paths[feature_type]['node_path']
            else:
                out_path = None

            if out_path is not None:
                ret = [(m['name'], m['path']) for m in out_path.values()]

        return ret

    def check_input_files_error(self):
        code_errors = (ConfigApp.error_codes['linkage_out_file'], ConfigApp.error_codes['linkage_in_file'],
                       ConfigApp.error_codes['arc_file'], ConfigApp.error_codes['node_file'],
                       ConfigApp.error_codes['not_found_file'])

        error = False
        for code_error in code_errors:
            error = error or self.check_errors(code=code_error)

        return error

    def set_map_name(self, map_name: str, map_path: str = None, is_main_file: bool = None, map_new_name: str = None):
        if len(map_name) == 0:
            return

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

    def set_arc_map_names(self, map_name: str, map_path: str = None, map_new_name: str = None):
        if len(map_name) == 0:
            return

        # set arc
        if map_name in self.arc_map_names:
            self.arc_map_names[map_name]['path'] = map_path if map_path else self.arc_map_names[map_name]['path']

            if map_new_name is not None:
                self.arc_map_names[map_name]['name'] = map_new_name
                self.arc_map_names[map_new_name] = self.arc_map_names.pop(map_name)
                map_name = map_new_name
        else:
            self.arc_map_names[map_name] = {
                'name': map_name,
                'path': map_path,
                'inter': 'output_inter_linkage_' + map_name,
                'imported': False
            }

    def set_node_map_names(self, map_name: str, map_path: str = None, map_new_name: str = None):
        if len(map_name) == 0:
            return

        # set node
        if map_name in self.node_map_names:
            self.node_map_names[map_name]['path'] = map_path if map_path else self.node_map_names[map_name]['path']

            if map_new_name is not None:
                self.node_map_names[map_name]['name'] = map_new_name
                self.node_map_names[map_new_name] = self.node_map_names.pop(map_name)
                map_name = map_new_name
        else:
            self.node_map_names[map_name] = {
                'name': map_name,
                'path': map_path,
                'inter': 'output_inter_linkage_' + map_name,
                'imported': False
            }

    def update_arc_node_map_name(self, map_name: str, map_path: str = None, map_new_name: str = None):
        if map_name in self.node_map_names:
            self.set_node_map_names(map_name=map_name, map_path=map_path, map_new_name=map_new_name)

        if map_name in self.arc_map_names:
            self.set_arc_map_names(map_name=map_name, map_path=map_path, map_new_name=map_new_name)

    def get_arc_map_names(self):
        return [self.get_arc_name(map_key=m) for m in self.arc_map_names]

    def get_node_map_names(self):
        return [self.get_node_name(map_key=m) for m in self.node_map_names]

    def get_arc_name(self, map_key: str) -> [str, str, str]:
        return self.arc_map_names[map_key]['name'], self.arc_map_names[map_key]['path'], self.arc_map_names[map_key]['inter']

    def get_node_name(self, map_key: str) -> [str, str, str]:
        return self.node_map_names[map_key]['name'], self.node_map_names[map_key]['path'], self.node_map_names[map_key]['inter']

    def is_arc_map(self, map_name: str):
        return map_name in self.arc_map_names

    def is_node_map(self, map_name: str):
        return map_name in self.node_map_names

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

    def get_arc_needed_field_names(self):
        alias = self.__config.type_names['GeoKernel']
        fields = self.get_needed_field_names(alias=alias, is_arc=True)
        return fields

    def get_node_needed_field_names(self):
        alias = self.__config.type_names['GeoKernel']
        fields = self.get_needed_field_names(alias=alias, is_node=True)
        return fields

    def all_files_imported(self):
        if len(self.map_names) > 0:
            imported = True
            for f_key in self.map_names:  # maps
                file_data = self.map_names[f_key]
                imported = imported and file_data['imported']

        elif len(self.arc_map_names) > 0 and len(self.node_map_names) > 0:
            imported = True
            for f_key in self.arc_map_names:  # arcs
                file_data = self.arc_map_names[f_key]
                imported = imported and file_data['imported']

            for f_key in self.node_map_names:  # nodes
                file_data = self.node_map_names[f_key]
                imported = imported and file_data['imported']
        else:
            imported = False

        return imported

    def make_vector_map(self, map_name):
        """
        Make an vector map into GRASS. The tool [v.ogr.import] is used for this.

        Parameters:
        ----------
        map_name : str
            Map name used in GRASS.

        """
        err, errors = False, []

        if map_name in self.map_names:
            maps = self.map_names
        elif map_name in self.node_map_names:
            maps = self.node_map_names
        elif map_name in self.arc_map_names:
            maps = self.arc_map_names
        else:
            maps = {}
            err = True
            errors.append("El mapa [{}] no esta registrado.".format(map_name))

        if map_name in maps:
            path_name = maps[map_name]['path']
            _err, _errors = GrassCoreAPI.import_vector_map(map_path=path_name, output_name=map_name)

            if not _err:
                # check mandatory field
                _err_bc, _ = self.check_basic_columns(map_name=map_name)
                if not _err_bc:
                    maps[map_name]['imported'] = True
            else:
                err = _err
                errors += _errors

        return err, errors

    def get_needed_field_names(self, alias: str, is_arc: bool = False, is_node: bool = False):
        fields = self.__config.get_needed_fields(alias=alias, is_arc=is_arc, is_node=is_node)
        return fields

    def get_column_to_export(self, alias: str, with_type: bool = False, truncate: int = 8):
        """
        Return one or more columns associated with parameter 'alias'. The 'alias' parameter refers to feature_type, but
        in some cases could be linkage-out columns.

        Parameters:
        ----------
        alias : str
            Used to determinate the correct column to return.
        with_type : bool
            Used to determinat if return type column with correct column.
        truncate : int
            Used to truncate column length. (SQLite permits columns names with max 10 caracters.)

        Returns:
        -------
            Return an list with an column name and some time with its type (when with_type is True).

        """
        conf = self.__config
        feature_types = list(conf.type_names.values())

        cols_to_export = []
        if alias in conf.cols_linkage:
            col_name = conf.cols_linkage[alias]['name']
            col_type = conf.cols_linkage[alias]['type']
            cols_number = 1

            if alias in feature_types:
                cols_number = conf.default_opts[alias]['columns_to_save']

            if len(col_name) > 8:
                col_name = col_name[0:truncate]

            if cols_number > 1:
                if with_type:
                    for i in range(cols_number):
                        cols_to_export.append(('{}{}'.format(col_name, i + 1), col_type))
                else:
                    for i in range(cols_number):
                        cols_to_export.append('{}{}'.format(col_name, i + 1))
            else:
                if with_type:
                    cols_to_export.append((col_name, col_type))
                else:
                    cols_to_export.append(col_name)

        return cols_to_export

    def get_columns_to_export(self, with_type: bool = False, truncate: int = 8):
        conf = self.__config

        cols_to_export = []
        for col_key in conf.cols_linkage:
            cols = self.get_column_to_export(alias=col_key, with_type=with_type, truncate=truncate)
            cols_to_export += cols

        return cols_to_export

    def get_info_columns_to_export(self, feature_type: str, with_type: bool = False,  truncate: int = 8):
        col_prefix = '{}_'.format(feature_type[0].upper())

        # secondary maps to info columns
        cols_to_export = []
        for col in self.get_map_names(only_names=True, with_main_file=False, imported=True):
            if with_type:
                col_name = ('{}{}'.format(col_prefix, col[0:truncate]), 'VARCHAR')
            else:
                col_name = '{}{}'.format(col_prefix, col[0:truncate])
            cols_to_export.append(col_name)

        return cols_to_export

    @abstractmethod
    def set_map_names(self):
        pass

    @abstractmethod
    def check_basic_columns(self, map_name: str):
        pass

    @abstractmethod
    def import_maps(self, verbose: bool = False, quiet: bool = True):
        pass




