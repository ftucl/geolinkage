import time

import ui
from anytree import RenderTree
from grass.exceptions import GrassError
from grass.pygrass.modules import Module
from grass.pygrass.utils import copy
from grass.script import PIPE
from grass_session import Session

import Utils
from Config import ConfigApp
from Errors import ErrorManager
from FeatureProcess import FeatureProcess
from GeoKernel import GeoKernel
from RiverNode import RiverNode

from collections import namedtuple

from grass.pygrass.vector import VectorTopo

from decorator import main_task, TimerSummary


class RiverProcess(FeatureProcess):

    def __init__(self, geo: GeoKernel = None, config: ConfigApp = None, debug: bool = False, err: ErrorManager = None):
        super().__init__(geo=geo, config=config, debug=debug, err=err)

        self.rivers = {}
        self._river_names = {}
        self.river_break_nodes = {}
        self.root = RiverNode(node_id=-1, node_name='root', node_type=0, node_distance=0)

        self._feature_opts = {
            'order_criteria': 'length',
            'columns_to_save': 1
        }

    def _start(self, linkage_name: str):
        # import files to vector maps
        self.import_maps()

        # check catchment maps with geo maps (nodes and arcs)
        self.check_names_with_geo()

        # check catchment geometries
        self.check_names_between_maps()

        # make rivers hierarchy with tree segment nodes
        _err_r, _errors_r = self.make_segment_map(is_main_file=True)

        if not self.check_errors():
            # intersection between WEAPArc and L (linkage map)
            _err_r, _errors_r = self.inter_map_with_linkage(linkage_name=linkage_name, snap='1e-12')
            if _err_r:
                # self.print_errors()
                raise RuntimeError('[EXIT] ERROR AL INTERSECTAR CON [{}]'.format(linkage_name))
            else:
                # make a dictionary grid with cell information in intersection map
                self.make_grid_cell()

            # stats
            self.stats['PROCESSED CELLS'] = len(self.cells)

    @TimerSummary.timeit
    def run(self, linkage_name: str):
        # Utils.show_title(msg_title='RIVERS', title_color=ui.green)
        ts = time.time()
        self._start(linkage_name=linkage_name)
        te = time.time()

        self.stats['FEATURES PROCESSED'] = '{}'.format(len(self._river_names))
        self.stats['PROCESSED TIME'] = '{0:.2f} seg'.format(te - ts)

        # Set inputs into summary
        # # set main field in map
        field_river = self.config.get_config_field_name(feature_type=self.get_feature_type(), name='river_name')
        field_segment = self.config.get_config_field_name(feature_type=self.get_feature_type(), name='segment_break_name')
        self.summary.set_input_param(param_name='FIELDS NAME', param_value='[{}] and [{}]'.format(field_river, field_segment))

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
        if self.geo:  # set [self.gws] and [self._gw_names]
            self.set_rivers(rivers=self.geo.get_rivers(), river_break_nodes=self.geo.get_river_break_nodes())

    def get_feature_id_by_name(self, feature_name):
        feature_id = self._river_names[feature_name] if feature_name in self._river_names else None
        return feature_id

    def set_rivers(self, rivers, river_break_nodes):
        self.rivers = rivers
        self.river_break_nodes = river_break_nodes

        self._river_names = {}
        for point_id in self.rivers:
            river_data = self.rivers[point_id]
            self._river_names[river_data['name']] = point_id

    def _make_river_tree_segments_structure(self):
        root = self.root

        break_keys = [k for k in self.river_break_nodes.keys() if k != '_by_name']
        if break_keys:
            # make real structure (hierarchization of rivers into segments)
            for key_name in break_keys:
                break_node = self.river_break_nodes[key_name]

                # [CANAL NOT IMPLEMENTED] Canal must be ingnored because WEAP has not implemented this type to be linked.
                # delete Canal break nodes
                arc_id = break_node['main_river_id']
                arc_type = self.rivers[arc_id]['type']
                if arc_type == 15:  # it is a Canal
                    self.river_break_nodes.pop(key_name)
                    continue

                break_node_id = break_node['node_id']
                break_node_name = break_node['node_name']
                break_node_type = break_node['node_type']
                break_node_distance = break_node['distance']
                break_node_x, break_node_y = break_node['x'], break_node['y']

                # make an initial node
                river_node = RiverNode(node_id=break_node_id, node_name=break_node_name, node_type=break_node_type,
                                       node_distance=break_node_distance, root_node=root, parent=root)
                river_node.set_coords(break_node_x, break_node_y)

                # set main river
                main_river_id = self.river_break_nodes[key_name]['main_river_id']
                main_distance = self.river_break_nodes[key_name]['distance']
                main_river_data = self.rivers[main_river_id]
                river_node.set_main_river(main_river_data['id'], main_river_data['name'], main_river_data['cat'],
                                          main_distance)

                # if it is a inflow node, it marks secondary node
                if break_node_type == 13:  # Tributary node
                    # get secondary river data
                    secondary_river_id = self.river_break_nodes[key_name]['secondary_river_id']
                    secondary_distance = self.river_break_nodes[key_name]['secondary_distance']

                    if secondary_river_id in self.rivers:
                        secondary_river_data = self.rivers[secondary_river_id]
                        river_node.set_secondary_river(secondary_river_data['id'], secondary_river_data['name'],
                                                       secondary_river_data['cat'], secondary_distance)

            # for pre, fill, node in RenderTree(root):
            #     print("%s %s | x=%s | y=%s | dist=%s | id=%s | cat=%s" %
            #           (pre, node.node_name, node.x, node.y, node.node_distance, node.node_id, node.node_cat))

            segments = root.get_segments_list()
            # for seg in segments:
            #     print(seg)
        else:
            root = None

        return root

    def _make_segments(self, arc_map_name='WEAPArc', output_map='weaparc_segments', verbose: bool = False, quiet: bool = True):
        _err, _errors = False, []  # TODO: catch errors

        root_node = self.root
        arc_map_copy_name = arc_map_name + '_copy'
        rivers_map_name = 'weaparc_rivers'

        # (1) get only rivers
        # copy to new map to work
        copy(arc_map_name, arc_map_copy_name, 'vect', overwrite=True)  # get a copy from map

        # extract only [TypeID]=6 in WEAPArc map
        extract = Module('v.extract', run_=False, stdout_=PIPE, stderr_=PIPE, overwrite=True, quiet=quiet, verbose=verbose)
        extract.inputs.input = arc_map_copy_name
        extract.outputs.output = rivers_map_name

        extract.inputs.where = "TypeID=6"
        extract.inputs.type = 'line'
        # print(extract.get_bash())
        extract.run()
        # print(extract.outputs["stdout"].value)
        # print(extract.outputs["stderr"].value)

        # (2) apply river tree to divide them in segments
        segments_str = root_node.get_segments_format()

        vsegment = Module('v.segment', run_=False, stdout_=PIPE, stderr_=PIPE, overwrite=True, verbose=verbose,
                          quiet=quiet)
        vsegment.inputs.input = rivers_map_name
        vsegment.inputs.stdin = segments_str
        vsegment.outputs.output = output_map

        # print(vsegment.get_bash())
        vsegment.run()
        # print(vsegment.outputs["stdout"].value)
        # print(vsegment.outputs["stderr"].value)

        return _err, _errors

    def _set_break_names_in_segments_map(self, segments_map_name='arc_segments'):
        _err, _errors = False, []  # TODO: catch errors

        columns = [(u'cat', 'INTEGER PRIMARY KEY'),
                   (u'segment_break_name', 'TEXT'),
                   (u'river_name', 'TEXT')]

        root_node = self.root

        # create attribute table and link with vector map
        columns_str = ','.join(['{} {}'.format(col[0], col[1]) for col in columns])  # columns format
        Utils.create_table_attributes(segments_map_name, columns_str, layer=1, key='cat')

        # set break names in map
        segment_map = VectorTopo(segments_map_name)
        # segment_map.open('rw', tab_name=segments_map_name, tab_cols=cols, link_key='cat', overwrite=True)
        segment_map.open('rw')

        for feature in segment_map.viter('lines'):
            segment_break_name, river_name = root_node.get_segment_break_name(feature.cat)

            # table columns: ([cat], [segment_break_name] [river_name])
            f_attrs = (segment_break_name, river_name)
            try:
                segment_map.rewrite(feature, cat=feature.cat, attrs=f_attrs)
            except GrassError as e:
                # print('ERROR writing in segment map  - cat={}'.format(feature.cat))
                continue
        segment_map.table.conn.commit()

        segment_map.close()

        return _err, _errors

    # @main_task
    def make_segment_map(self, is_main_file: bool = False):
        err = False
        errors = []

        # get the arc map
        arc_map_name, arc_map_path, arc_map_inter = self.geo.get_arc_map_names()[0]  # get the arc map
        segments_map_name = 'segments_out_river'

        # make hierarchy of rivers with tree segment nodes
        self.root = self._make_river_tree_segments_structure()

        if self.root:
            # TODO: check if copy and extract maps were created
            # filter only rivers from WEAPArc and apply hierarchy to divide rivers in segment lines
            _err, _errors = self._make_segments(arc_map_name=arc_map_name, output_map=segments_map_name)
            self.append_error(msgs=_errors) if _err else None

            # put segment names in [river_segments_map]
            _err, _errors = self._set_break_names_in_segments_map(segments_map_name=segments_map_name)
            self.append_error(msgs=_errors) if _err else None

        # set segment map like the main river map
        self.set_map_name(map_name=segments_map_name, map_path='', is_main_file=is_main_file)

        # it was imported because it is based in Arc map
        self.map_names[segments_map_name]['imported'] = True

        # the intersection map is with 'lines' geos not the default 'areas'
        self.set_inter_map_geo_type(map_key=segments_map_name, geo_map_type='lines')

        self.summary.set_process_line(msg_name='make_segment_map', check_error=self.check_errors())

        return self.check_errors(), self.get_errors()

    # @main_task
    def make_cell_data_by_main_map(self, map_name, inter_map_name, inter_map_geo_type):
        inter_map = VectorTopo(inter_map_name)
        inter_map.open('r')

        for feature_data in inter_map.viter(vtype=inter_map_geo_type):
            if feature_data.cat is None:  # when topology has some errors
                # print("[ERROR] ", a.cat, a.id)
                continue

            Cell = namedtuple('Cell_river', ['row', 'col'])

            fields = self.get_needed_field_names()
            main_field, main_needed = fields['main']['name'], fields['main']['needed']
            second_field, second_needed = fields['secondary']['name'], fields['secondary']['needed']

            field_feature_name = 'a_' + main_field
            field_subfeature_name = 'a_' + second_field
            col_field = 'b_' + self.config.fields_db['linkage']['col_in']
            row_field = 'b_' + self.config.fields_db['linkage']['row_in']

            subfeature_name = feature_data.attrs[field_subfeature_name]
            feature_name = feature_data.attrs[field_feature_name]
            cell_area_id = feature_data.attrs['b_cat']  # id from cell in linkage map
            area_row, area_col = feature_data.attrs[row_field], feature_data.attrs[col_field]
            line_length = feature_data.length()

            data = {
                'length': line_length,
                'cell_id': cell_area_id,
                'segment_name': subfeature_name,
                'river_name': feature_name,
                'name': '{},{}'.format(feature_name, subfeature_name),
                'map_name': map_name
            }

            cell = Cell(area_row, area_col)

            self._set_cell(cell, feature_name, data, by_field=self.get_order_criteria_name())

            self.cells_by_map[map_name].append(cell)  # order cells by map name (be used in DS)

        inter_map.close()

        self.summary.set_process_line(msg_name='make_cell_data_by_main_map', check_error=self.check_errors(),
                                      map_name=map_name, inter_map_name=inter_map_name,
                                      inter_map_geo_type=inter_map_geo_type)

        return self.check_errors(), self.get_errors()

    # @main_task
    def make_cell_data_by_secondary_maps(self, map_name, inter_map_name, inter_map_geo_type):
        # in this case is the same done with main map to secondary maps
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
    #     Cell = namedtuple('Cell_river', ['row', 'col'])
    #     field_segment_break_name = 'a_' + self.config.fields_db['river']['segment_break_name']
    #     field_river_name = 'a_' + self.config.fields_db['river']['river_name']
    #     col_field = 'b_' + self.config.fields_db['linkage']['col_in']
    #     row_field = 'b_' + self.config.fields_db['linkage']['row_in']
    #     for a in inter_map.viter('lines'):
    #         area_name = a.attrs[field_segment_break_name]
    #         area_river_name = a.attrs[field_river_name]
    #
    #         area_id = a.attrs['b_cat']  # id from cell in linkage map
    #         area_row, area_col = a.attrs[row_field], a.attrs[col_field]
    #         line_length = a.length()
    #
    #         data = {
    #             'length': line_length,
    #             'cell_id': area_id,
    #             'segment_name': area_name,
    #             'river_name': area_river_name
    #         }
    #
    #         cell = Cell(area_row, area_col)
    #         self._set_cell(cell, area_name, data, by_field='length')
    #
    #     # watch what is the best area for a cell by criteria
    #     self._set_cell_by_criteria(RiverProcess.__cell_order_criteria(), by_field='length')
    #
    #     inter_map.close()
    #
    #     return self.check_errors(), self.get_errors()

    def get_needed_field_names(self):
        fields = {
            'main': {
                'name': self.config.fields_db['river']['river_name'],
                'needed': True
            },
            'secondary': {
                'name': self.config.fields_db['river']['segment_break_name'],
                'needed': True
            },
            'limit': None
        }

        return fields

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

