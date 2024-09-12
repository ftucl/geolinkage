from grass.pygrass.utils import copy
from grass.pygrass.vector import VectorTopo

from utils.Utils import GrassCoreAPI, TimerSummary, UtilMisc
from processors.CatchmentProcessor import CatchmentProcess
from utils.Config import ConfigApp
from processors.DemandSiteProcessor import DemandSiteProcess
from processors.GeoKernel import GeoKernel
from processors.GroundwaterProcessor import GroundwaterProcess
from utils.Protocols import MapFileManagerProtocol
from processors.RiverProcessor import RiverProcess
from utils.Errors import ErrorManager
from utils.SummaryInfo import SummaryInfo


class AppKernel(MapFileManagerProtocol):
    """
    Initializes groundwater, catchment, rivers and demand sites processors. In addition, it initializes the kernel
    that processes the geometry, which will be used to validate the information from the geometry processor.

    It receives the inputs from UI interfaces.

    * Config file: ./config/config.json


    Attributes:
    ----------
    geo_processor : GeoKernel
        Used to read the surface scheme geometry (node and arc files).

    catchment_processor : CatchmentProcess
        Used to process catchment map.

    groundwater_processor : GroundwaterProcess
        Used to process groundwater map.

    demand_site_processor : DemandSiteProcess
        Used to process demand sites main map. That map is obtained from the surface scheme.
        Additionally it also processes additional maps with demand site areas.

    river_processor : RiverProcess
        Used to process the segments map obtained from rivers in surface scheme.

    consolidate_cells : Dict[namedtuple<Cell>, Dict[str, Any]]
        Used to consolidate groundwater, catchment, river and demand site cells in order to check them only once.

    config : ConfigApp
        Used to access to configuration parameters (constants, texts, input columns, ...).

    summary : SummaryInfo
        Used to access the results generated by AppKernel (errors, warnings, input parameters, statistics) and
        deliver them in a standard way.

    stats : Dict[str, str]
        Used to store the general process basic statistics.

    _err : ErrorManager
        Used to store errors and warnings found while running.

    __debug : bool
        Not used.

    _feature_type : str
        Text used to identify the main process (value: self.config.type_names[self.__class__.__name__]).


    Methods:
    -------
    get_feature_type(self)
        Get a name to identify processors or main program.

    set_config_field(self, catchment_field, modflow_field, groundwater_field, demand_site_field)
        Sets  geometry name columns in input maps to processors.

    export_to_shapefile(self, map_name, output_path)
        Export the 'map_name' map in ESRI Shapefile format (.shp) to the 'output_path' path.

    get_consolidate_cells(self)
        Unify all intersecting cells in processors in order to check them only once.

    init_linkage_file(self, linkage_name, linkage_new_name)
        Initialize the final grid map with the necessary and informative columns. The 'linkage_name' parameter
        is the input groundwater grid map and 'linkage_new_name' parameter is the final map name.

    mark_linkage_active(self, linkage_name, save_changes)
        Saves the cells information in the final map metadata ('linkage_name') to export.
        The 'save_changes' parameter sets the number of cells to review before committing the transaction.

    set_map_names(self)
        In case there is no error in the input files, register these files in the different processors to relate them
        to the vector maps to be imported.

    set_origin_in_node_arc_maps(self, map_names: list)
        Set lower left edge in vector map list 'map_names'.

    run(self)
        Runs the correct order of methods to perform the processing of the implemented processors.

    """

    def __init__(self, gisdb: str, location: str, mapset: str, epsg_code: int = None):
        self.__debug = False

        self.config = ConfigApp(epsg_code=epsg_code, gisdb=gisdb, location=location, mapset=mapset)
        self._err = ErrorManager(config=self.config)
        super(AppKernel, self).__init__(config=self.config, error=self._err)

        self.geo_processor = GeoKernel(config=self.config, err=self._err)
        self.catchment_processor = CatchmentProcess(geo=self.geo_processor, config=self.config, err=self._err)
        self.groundwater_processor = GroundwaterProcess(geo=self.geo_processor, config=self.config, err=self._err)
        self.demand_site_processor = DemandSiteProcess(geo=self.geo_processor, config=self.config, err=self._err)
        self.river_processor = RiverProcess(geo=self.geo_processor, config=self.config, err=self._err)
        self.consolidate_cells = None

        self._feature_type = self.config.type_names[self.__class__.__name__]

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

    def get_geo_summary(self):
        return self.geo_processor.get_summary()

    def get_catchment_summary(self):
        return self.catchment_processor.get_summary()

    def get_gw_summary(self):
        return self.groundwater_processor.get_summary()

    def get_ds_summary(self):
        return self.demand_site_processor.get_summary()

    def get_river_summary(self):
        return self.river_processor.get_summary()

    def set_demand_site_folder(self, folder_path):
        if not folder_path:
            return False, []

        code_error = ConfigApp.error_codes['ds_folder']  # code error for DS input folder

        # check if path exists
        _, exist_folders = UtilMisc.check_paths_exist(folders=[folder_path])
        if exist_folders[0][0]:
            # load files in path
            files = UtilMisc.get_file_names(folder_path=folder_path, ftype='shp')

            # put in [demand_site_paths]
            for file_name in files:
                f_type = self.demand_site_processor.get_feature_type()
                self.set_feature_file_path(feature_type=f_type, file_path=file_name, is_main_file=False)

            files = UtilMisc.get_file_names(folder_path=folder_path, ftype='txt')
            for file_name in files:
                self.set_demand_site_well(file_path=file_name)
        else:
            # ds folder problem with error code [-17]
            self.append_error(msg=exist_folders[0][1], is_warn=False, code=code_error, typ=self.demand_site_processor.get_feature_type())

        return self.check_errors(code=code_error), self.get_errors(code=code_error)

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
            _err += self.config.set_config_field(feature_type=domain, field_type='main',
                                                 field_new_name=groundwater_field)

        if demand_site_field:
            domain = self.demand_site_processor.get_feature_type()
            _err += self.config.set_config_field(feature_type=domain, field_type='main',
                                                 field_new_name=demand_site_field)

        return _err

    @TimerSummary.timeit
    # @main_task
    def export_to_shapefile(self, map_name, output_path):
        _err, _errors = GrassCoreAPI.export_to_shapefile(map_name, output_path, file_name='{}.shp'.format(map_name),
                                                         verbose=False, quiet=True)
        self.append_error(msgs=_errors) if _err else None

        msg_info = self.config.get_process_msg(msg_name='export_to_shapefile')
        if _err:
            self.append_error(msgs=_errors)

        self.summary.set_process_line(msg_name='export_to_shapefile', check_error=_err,
                                      map_name=map_name, output_path=output_path)

        return _err, _errors

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

        # TODO: to future it need to check if sqlite is the database engine
        vector_map = VectorTopo(linkage_new_name)
        vector_map.open('r')
        db_path = vector_map.dblinks[0].database
        vector_map.close()

        cols_sqlite = Columns(linkage_new_name, sqlite3.connect(db_path))

        # check if linkage vector map has base fields (flopy way)
        __columns_from_in = [x for l in [(t[0], t[0].lower()) for t in cols_sqlite.items()] for x in l]

        # remove al old columns
        # # do not remove row and col, because they have cell values
        fields = self.get_needed_field_names(alias=self.get_feature_type())
        row_field, col_field = fields['main']['name'], fields['secondary']['name']
        for col_in in [c[0] for c in cols_sqlite.items() if c[0] != cols_sqlite.key]:
            if col_in not in (row_field, col_field):
                cols_sqlite.drop(col_in)  # remove

        # add columns in config
        # cols = self.get_linkage_out_columns()
        f_ds_type = self.demand_site_processor.get_feature_type()
        cols_info = self.demand_site_processor.get_info_columns_to_export(feature_type=f_ds_type, with_type=True)
        cols_main = self.get_columns_to_export(with_type=True)
        
        cols = cols_main + cols_info        
        for col_name, col_type in cols:
            if col_name not in (row_field, col_field):
                cols_sqlite.add([col_name], [col_type])

        self.summary.set_process_line(msg_name='init_linkage_file', check_error=self.check_errors(types=(self.get_feature_type())),
                                      linkage_name=linkage_name, linkage_new_name=linkage_new_name)

        return self.check_errors(types=(self.get_feature_type())), self.get_errors()

    @TimerSummary.timeit
    # @main_task
    def mark_linkage_active(self, linkage_name: str, save_changes=100):
        # consolidate [catchment_cells], [gw_cells], [river_cells] and [demand_site_cells]
        _, _ = self.get_consolidate_cells()


        # DB connection ? 
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
            values_ad = dict(**values_dict_ad_catchment, **values_dict_ad_gw, **values_dict_ad_river,
                             **values_dict_ad_ds)

            values_dict = dict(**values_required, **values_ad)
            values_dict[self.config.cols_linkage['row']['name']] = cell.row
            values_dict[self.config.cols_linkage['col']['name']] = cell.col
            values_dict[self.config.cols_linkage['rc']['name']] = '{}x{}'.format(cell.row, cell.col)

            # prepare data to save
            feature = linkage_map.read(feature_id)
            col_keys, col_values = GrassCoreAPI.get_values_from_map_db(vector_map=linkage_map, data_values=values_dict)

            # save values in [linkage]
            linkage_map.rewrite(feature, cat=feature_id, attrs=col_values)
            # linkage_map.table.conn.commit()

            if i % save_changes == 0:  # save changes into DB
                linkage_map.table.conn.commit()

            i += 1
        else:
            linkage_map.table.conn.commit()

        linkage_map.close()

        self.summary.set_process_line(msg_name='mark_linkage_active', check_error=self.check_errors(types=(self.get_feature_type())),
                                      linkage_name=linkage_name)

        return self.check_errors(types=(self.get_feature_type())), self.get_errors()

    @TimerSummary.timeit
    def import_maps(self, map_paths: list, output_names: list):
        for ind, map_path in enumerate(map_paths):
            output_name = output_names[ind]
            _err_o, _errors = GrassCoreAPI.import_vector_map(map_path=map_path, output_name=output_name)
            self.append_error(msgs=_errors) if _err_o else None

            self.summary.set_process_line(msg_name='import_maps', check_error=_err_o,
                                          map_path=map_path, output_name=output_name)

    def check_basic_columns(self, map_name: str):
        _err, _errors = False, []
        fields = self.get_needed_field_names(alias=self.get_feature_type())

        column_names = []
        needed = []
        for field_key in fields:
            field_name = fields[field_key]['name']
            needed = fields[field_key]['needed']

            if field_name not in column_names:
                __err, __errors = GrassCoreAPI.check_basic_columns(map_name=map_name, columns=[field_name], needed=[needed])
                self.summary.set_process_line(msg_name='check_basic_columns', check_error=__err,
                                              map_name=map_name, columns=[field_name], needed=[needed])

                _errors += __errors
                if needed:
                    _err |= __err

                column_names.append(field_name)

        self.append_error(msgs=_errors, typ='other')

        return _err, _errors

    def set_map_names(self):
        self.geo_processor.set_map_names()
        self.catchment_processor.set_map_names()
        self.groundwater_processor.set_map_names()
        self.demand_site_processor.set_map_names()
        self.river_processor.set_map_names()

    def set_origin_in_node_arc_maps(self, map_names: list):
        x_ll, y_ll, z_rotation = self.geo_processor.x_ll, self.geo_processor.y_ll, self.geo_processor.z_rotation

        if x_ll is not None and y_ll is not None and z_rotation is not None:
            for map_name in map_names:
                # get map lower left edge
                x_ini_ll, y_ini_ll = UtilMisc.get_origin_from_map(map_name=map_name)

                # set the new origin
                x_offset_ll = x_ll - x_ini_ll
                y_offset_ll = y_ll - y_ini_ll
                map_name_out = '{}_transform'.format(map_name)
                _err, _errors = GrassCoreAPI.set_origin_in_map(map_name=map_name, map_name_out=map_name_out,
                                                               x_offset_ll=x_offset_ll, y_offset_ll=y_offset_ll,
                                                               z_rotation=z_rotation)

                self.summary.set_process_line(msg_name='set_origin_in_map', check_error=_err,
                                              map_name=map_name, x_ll=x_ll, y_ll=y_ll, z_rot=z_rotation)
                if not _err:
                    self.geo_processor.update_arc_node_map_name(map_name=map_name, map_new_name=map_name_out)
                else:
                    msg_error = 'Can not reproject map [{}] to x_ll=[{}], y_ll=[{}], z_rot=[{}]'.format(
                        map_name, x_ll, y_ll, z_rotation
                    )
                    self.append_error(msg=msg_error, typ=self.get_feature_type())

    def run(self):
        _err = False

        # ==============================================================================================================
        # Path and Map names
        # ==============================================================================================================
        # set map names into de Processors (catchments, groundwaters, rivers and demand sites)
        self.set_map_names()

        # Necessary Files
        if self.check_input_files_error():
            self.print_errors(feature_type=self.get_feature_type())
            raise RuntimeError('[EXIT] UNO DE LOS ARCHIVOS IMPORTANTES NO EXISTE')

        linkage_name, linkage_file_path = self.get_linkage_in_file()[0]  # only one file
        linkage_new_name, linkage_out_folder_path = self.get_linkage_out_file()[0]  # only one file
        arc_name, arc_file_path, _ = self.geo_processor.get_arc_map_names()[0]  # only one file
        node_name, node_file_path, _ = self.geo_processor.get_node_map_names()[0]  # only one file

        # import arc and node files
        self.geo_processor.import_maps()
        # re-projecting map if exists lower left edge
        if self.geo_processor.x_ll is not None and self.geo_processor.y_ll is not None \
                and self.geo_processor.z_rotation is not None:
            self.set_origin_in_node_arc_maps(map_names=[arc_name, node_name])

        # import init gw grid
        self.import_maps(map_paths=[linkage_file_path], output_names=[linkage_name])
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
        _err, _ = self.geo_processor.processing_nodes_arcs(arcmap=arc_map, nodemap=node_map)
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
        # self.river_processor.run(linkage_name=linkage_name)

        # -------------------------------------------------------------------------------
        # General Logic
        # -------------------------------------------------------------------------------
        # make a linkage map copy and format with the base linkage cols
        _err, _ = self.init_linkage_file(linkage_name, linkage_new_name=linkage_new_name)
        if _err:
            self.print_errors(feature_type=self.get_feature_type())
            raise RuntimeError('[EXIT] NO ES POSIBLE FORMATEAR LINKAGE')

        # copy active cells and put catchment names into linkage map
        _err, _ = self.mark_linkage_active(linkage_new_name, save_changes=100)
        if _err:
            self.print_errors(feature_type=self.get_feature_type())
            raise RuntimeError('[EXIT] NO ES POSIBLE ESCRIBIR EN LINKAGE')

        # export to shapefile
        self.export_to_shapefile(map_name=linkage_new_name, output_path=linkage_out_folder_path)

        arc_map.close()
        node_map.close()

        # print processing times
        # Utils.show_title(msg_title='PROCESSING TIMES', title_color=ui.brown)
        # headers = ["FUNCTION", "ms"]
        # ui.info_table(TimerSummary.get_summary_by_function(), headers=headers)

        return _err, self.get_errors()
