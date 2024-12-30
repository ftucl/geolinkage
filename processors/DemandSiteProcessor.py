import time
from collections import namedtuple

from grass.pygrass.vector import VectorTopo

from utils.Utils import GrassCoreAPI, TimerSummary
from utils.Config import ConfigApp
from utils.Errors import ErrorManager
from processors.FeatureProcessor import FeatureProcess
from processors.GeoKernel import GeoKernel


class DemandSiteProcess(FeatureProcess):
    """
        It contains the DS processor particular logic.

        Processes well-type demand sites generating a vector map from surface maps (node map and arc map),
        being this the main map. A plain text file identifies by name which demand sites are actually
        wells on the surface map.

        Any other demand site will be treated as a demand area and can be specified by a secondary map that correctly
        indicates its boundaries. The secondary maps are created from the ESRI Shapefiles located inside the folder
        indicated in input parameters.

        By default, 4 columns are generated in final file metadata, being able to have a maximum of 4 wells
        per cell (this number can be changed in the configuration file).

        For secondary maps, a column will be generated for each map found. The name of this column is obtained from
        first 10 characters of the file name (shapefile name).
        These columns are only informative for the link between models.


        Attributes:
        ----------
        cells : Dict[namedtuple<Cell>, Dict[str, Dict[str, str|int]]
            Inherited from FeatureProcess class.
            It is used to store cell-feature relationship. It is indexed by DS grid cells that
            they have been intersected with the feature map. Because a cell can be intersected by more than one
            map geometry, access is given by: [cell] -> [geo_intersected] -> [cell_feature_relationship_data].
            The stored values are:
                - 'area': area occupied by geometry on the map.
                - 'cell_id': cell ID. (ID in gw vector map grid)
                - 'name': DS name.
                - 'map_name': DS map name. (name used by GRASS Platform)

        cell_ids: Dict[namedtuple<Cell>, Dict[str, str|int|List<data>]]
            Inherited from FeatureProcess class.
            Store for each cell the geometry (s) that will actually be stored in final file. Structure and stored
            values details are in FeatureProcess class.

        demand_sites : Dict[int, Dict[str, str | int]]
            It is used to store DS information obtained from surface map analysis.
            (Stored data details are in GeoKernel class)

        _demand_site_names : Dict[str, int]
            It is used internally to directly access DS data by name.

        wells : Dict[str, Dict[str, str | int | bool]]
            Stores wells that come from the plain text file.
            The stored values are:
                - 'name': well name.
                - 'path': well file path.
                - 'type': not used.
                - 'is_well': Identify whether or not it is a well (common). Currently, it is always True.
                - 'processed': Identifies if it was found in surface maps. (True | False).


        Methods:
        -------
        _start(self, linkage_name: str)
            Runs procedure for successful processing between feature map and inital GW grid.
            The 'linkage_name' parameter refers to GW grid vector map.

        run(self, linkage_name: str):
            Start processing and records basic statistics of the execution.
            The 'linkage_name' parameter refers to groundwater grid vector map.

        set_data_from_geo(self):
            Extracts demand sites data from geometries analyzed of the surface scheme.

        make_cell_data_by_main_map(self, map_name, inter_map_name, inter_map_geo_type)
            Creates structure that store the necessary well data from main map.
            The main map generates 4 (default value en config file) mandatory columns in final file (metadata)
            for the demand sites (even if their values are null).

        make_cell_data_by_secondary_maps(self, map_name, inter_map_name, inter_map_geo_type)
            Creates structure that store the necessary data of demand sites areas from secondary maps.
            A column be generated for each map found. The column name is get from the first 10 characters of
            the file name.

        get_ds_map_from_node_map(self, is_main_file: bool = False, verbose: bool = False, quiet: bool = True)
            Creates a vector map from demand site nodes registered in the surface map.
            The 'is_main_file' parameter determines whether you leave it as main map (mandatory column) or
            secondary map (informative column).

        read_well_files(self)
            Reads the plain text file with well names and stores them.

        _read_well_files(self, well_name, well_path, well_lines)
            Validate that the wells read exist in surface map (node) or report their absence.



        Example:
        --------
        >>> from processors.GeoKernel import GeoKernel
        >>> from processors.DemandSiteProcessor import DemandSiteProcess
        >>> from utils.Config import ConfigApp
        >>> from utils.Errors import ErrorManager

        >>> epsg_code, gisdb, location, mapset = 30719, '/tmp', 'test', 'PERMANENT'
        >>> main_map_file, well_file = '/tmp/arc_map.shp', '/tmp/well_file.txt'
        >>> ds_area1_map_file, ds_area2_map_file = '/tmp/ds1_map.shp', '/tmp/ds2_map.shp'
        >>> grid_vector_map = 'initial_gw_grid'

        >>> config = ConfigApp(epsg_code=epsg_code, gisdb=gisdb, location=location, mapset=mapset)
        >>> error = ErrorManager(config=config)
        >>> geo = GeoKernel(config=config, err=error)

        >>> processor = DemandSiteProcess(geo=geo, config=config, err=error)
        >>> processor.config.set_columns_to_save(processor.get_feature_type(), columns_to_save=4)
        >>> processor.config.set_order_criteria(processor.get_feature_type(), order_criteria='area')
        >>> processor.set_map_name(map_name='arc_vector_map', map_path=main_map_file, is_main_file=True)
        >>> processor.set_map_name(map_name='ds1_vector_map', map_path=ds_area1_map_file, is_main_file=False)
        >>> processor.set_map_name(map_name='ds2_vector_map', map_path=ds_area2_map_file, is_main_file=False)
        >>> processor.set_well(well_name='wells', well_path=well_file)

        >>> processor.import_maps()
        >>> processor.check_names_with_geo()
        >>> processor.check_names_between_maps()
        >>> processor.get_ds_map_from_node_map(is_main_file=True)
        >>> processor.read_well_files()

        >>> if not processor.check_errors():  # or processor.run(linkage_name=grid_vector_map)
        >>>     processor.inter_map_with_linkage(linkage_name=grid_vector_map)
        >>>     processor.make_grid_cell()

        >>>     summary = processor.get_summary()

        >>>     inputs = summary.print_input_params()  # inputs and stats
        >>>     real_lines = summary.get_process_lines(with_ui=True)
        >>>     errors = summary.print_errors()
        >>>     warnings = summary.print_warnings()

        >>>     print(inputs)

    """

    def __init__(self, geo: GeoKernel = None, config: ConfigApp = None, debug: bool = False, err: ErrorManager = None):
        super().__init__(geo=geo, config=config, debug=debug, err=err)

        self.demand_sites = {}
        self.wells = {}  # [well_name] = {'name': '', 'path': '', 'type': '', 'is_well':(T|F), 'processed': (T|F)}
        self._demand_site_names = None

    def _start(self, linkage_name: str):
        # import files to vector maps
        self.import_maps()

        # check ds maps with geo maps (nodes and arcs)
        # self.check_names_with_geo()

        # check ds geometries
        self.check_names_between_maps()

        # get and set the DS main file from Node map
        self.get_ds_map_from_node_map(is_main_file=True)

        self.read_well_files()  # read TXT with the wells (all will be considered wells if not)

        if not self.check_errors(types=[self.get_feature_type()]):
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
        field = self.config.get_config_field_name(feature_type=self.get_feature_type(), field_type='main')
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

    # @main_task
    def get_ds_map_from_node_map(self, is_main_file: bool = False, verbose: bool = False, quiet: bool = True):
        import sqlite3
        from grass.pygrass.vector.table import Columns

        node_map_name, node_map_path, node_map_inter = self.geo.get_node_map_names()[0]  # get the node map
        ds_extract_out_name = node_map_name + '_extract_ds'
        ds_buffer_out_name = node_map_name + '_extract_with_buffer_ds'

        # extract nodes for DS
        col_query, op_query, val_query = self.geo.get_node_needed_field_names()['secondary']['name'], '=', '1'
        _err, _errors = GrassCoreAPI.extract_map_with_condition(map_name=node_map_name,
                                                                output_name=ds_extract_out_name,
                                                                col_query=col_query, val_query=val_query,
                                                                op_query=op_query, geo_check='point',
                                                                verbose=verbose, quiet=quiet)
        if not _err:
            # make a buffer in each node founded
            GrassCoreAPI.make_buffer_in_point(map_pts_name=ds_extract_out_name, out_name=ds_buffer_out_name,
                                              map_type='point', distance=10, verbose=verbose, quiet=quiet)

            # change the column name from Node map's main field to DS map's main field
            node_main_field = self.geo.get_node_needed_field_names()['main']['name']
            ds_main_field = self.get_needed_field_names(alias=self.get_feature_type())['main']['name']

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

        self.summary.set_process_line(msg_name='get_ds_map_from_node_map', check_error=self.check_errors(types=[self.get_feature_type()]))

        return self.check_errors(types=[self.get_feature_type()]), self.get_errors()

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

            fields = self.get_needed_field_names(alias=self.get_feature_type())
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

        self.summary.set_process_line(msg_name='make_cell_data_by_main_map', check_error=self.check_errors(types=[self.get_feature_type()]),
                                      map_name=map_name, inter_map_name=inter_map_name,
                                      inter_map_geo_type=inter_map_geo_type)

        return self.check_errors(types=[self.get_feature_type()]), self.get_errors()

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

            fields = self.get_needed_field_names(alias=self.get_feature_type())
            main_field, main_needed = fields['main']['name'], fields['main']['needed']
            field_feature_name = 'a_' + main_field
            col_field = 'b_' + self.config.fields_db['linkage']['col_in']
            row_field = 'b_' + self.config.fields_db['linkage']['row_in']

            feature_name = feature_data.attrs[field_feature_name]
            cell_area_id = feature_data.attrs['b_cat']  # id from cell in linkage map
            area_row, area_col = feature_data.attrs[row_field], feature_data.attrs[col_field]
            feature_area = feature_data.area()

            # get id from demand site map (Node map) - its geometry id
            # if it fails here the demand site does not exist in weap
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

        self.summary.set_process_line(msg_name='make_cell_data_by_secondary_maps', check_error=self.check_errors(types=[self.get_feature_type()]),
                                      map_name=map_name, inter_map_name=inter_map_name,
                                      inter_map_geo_type=inter_map_geo_type)

        return self.check_errors(types=[self.get_feature_type()]), self.get_errors()

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

    def set_map_names(self):
        # demand site area maps
        super().set_map_names()

        # demand site wells
        for well_name, well_path in self.get_demand_site_well_paths():
            self.set_well(well_name=well_name, well_path=well_path)
