from grass.pygrass.vector.geometry import Point

import Utils
from Config import ConfigApp
from Errors import ErrorManager
from SummaryInfo import SummaryInfo
from decorator import main_task, TimerSummary


class GeoKernel:
    def __init__(self, config: ConfigApp = None, debug=None, err: ErrorManager = None):

        self.config = config

        if debug is None:
            self.__debug = self.config.debug if self.config is not None else False

        self._err = err

        self.nodes = {}  # weapnode
        self.arcs = {}  # weaparc
        self.links = {
            'tl': {},  # transmission link
            'ri': {},  # runoff infiltration
            'rf': {}  # return flow
        }

        self.gws = {}
        self.catchments = {}
        self.demand_sites = {}
        self.other_nodes = {}
        self.river_break_nodes = {}
        self.rivers = {}

        self._errors = {
            'catchments': [],
            'gws': [],
            'rivers': [],
            'demand_sites': [],
            'tls': [],  # transmission links
            'ris': [],  # runoff infiltrations
            'rfs': [],  # return flows
            'others': []
        }

        self.arc_map_names = {}
        self.node_map_names = {}

        self._feature_type = self.config.type_names[self.__class__.__name__]

        self.summary = SummaryInfo(prefix=self.get_feature_type(), errors=self._err, config=self.config)

        self.z_rotation = None
        self.x_ll = None  # real world model coords (lower left)
        self.y_ll = None  # real world model coords (lower left)

    def set_origin(self, x_ll: float, y_ll: float, z_rotation: float):
        self.x_ll = x_ll
        self.y_ll = y_ll
        self.z_rotation = z_rotation

    def get_summary(self):
        return self.summary

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

    def set_arc_map_names(self, map_name: str, map_path: str = None, map_new_name: str = None):
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
                'inter': 'output_inter_linkage_' + map_name
            }

    def set_node_map_names(self, map_name: str, map_path: str = None, map_new_name: str = None):
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
                'inter': 'output_inter_linkage_' + map_name
            }

    def update_map_name(self, map_name: str, map_path: str = None, map_new_name: str = None):
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
        return self._err.get_errors(typ=self.get_feature_type(), code=code)

    def print_errors(self, code: str = ''):
        # self._err.print(typ=self.config.type_names[self.__class__.__name__], words=words)
        return self._err.get_errors(typ=self.get_feature_type(), code=code)

    def get_feature_type(self):
        return self._feature_type

    def get_catchments(self):
        return self.catchments

    def get_groundwaters(self):
        return self.gws

    def get_demand_sites(self):
        return self.demand_sites

    def get_rivers(self):
        return self.rivers

    def get_river_break_nodes(self):
        return self.river_break_nodes

    @staticmethod
    def _check_point_on_line(line, pt):
        closest_pont_on_line, dst_bt_two_pts, dst_from_segment_beginning, dst_from_line_beg = line.distance(pt)

        return closest_pont_on_line == pt, dst_from_line_beg

    def _get_break_node_distance_from_arc(self, river_arc, min_rate=0.9):
        for break_node_id in self.river_break_nodes:

            if break_node_id != '_by_name':  # TODO: FIX IT - remove '_by_name'
                break_node = self.river_break_nodes[break_node_id]

                if break_node['node_name']:
                    point_node = Point(break_node['x'], break_node['y'])
                    arc_name = river_arc.attrs['Name']
                    arc_id = river_arc.attrs['ObjID']

                    pt_on_line, dist = GeoKernel._check_point_on_line(river_arc, point_node)

                    if pt_on_line:
                        if break_node['node_type'] == 13:  # Tributary Node
                            if break_node['node_name'] == arc_name + ' Inflow':  # it is the seconday river
                                break_node['secondary_river_id'] = arc_id
                                break_node['secondary_distance'] = dist
                            elif Utils.get_similarity_rate(break_node['node_name'], arc_name + ' Inflow', min_rate=min_rate):  # it is the seconday river
                                msg_error = "[ADVERTENCIA] El nodo del tipo [Tributary Inflow] tiene un nombre={} levemente" \
                                            " diferente al rio que esta conectado, de nombre={}.".format(break_node['node_name'], arc_name)
                                self._errors['rivers'].append(msg_error)

                                break_node['secondary_river_id'] = arc_id
                                break_node['secondary_distance'] = dist
                            else:  # it is the main river
                                break_node['main_river_id'] = arc_id
                                break_node['main_distance'] = dist  # use main distance like node distance
                                break_node['distance'] = dist
                        else:
                            break_node['main_river_id'] = arc_id
                            break_node['main_distance'] = dist  # use main distance like node distance
                            break_node['distance'] = dist

    @TimerSummary.timeit
    # @main_task
    def setup_arcs(self, arcmap, nodemap):
        _err = False

        for p in nodemap.viter('points'):
            point_name = p.attrs['Name']  # [nombre] | [nombre rio] Inflow
            point_type_id = p.attrs['TypeID']  # 3: GW; 21: Catchment; 13: Inflow
            point_id = p.attrs['ObjID']

            point_x, point_y = p.x, p.y
            point_cat = p.attrs['cat']

            self.nodes[point_id] = {
                'type_id': point_type_id,
                'name': point_name,
                'x': point_x,
                'y': point_y,
                'cat': point_cat
            }

            if point_type_id == 3:  # gw
                _point_name = 'groundwater'

                self.gws[point_id] = {
                    'name': point_name
                }
                # self.gws[point_name] = point_id

            elif point_type_id == 21:  # catchment
                _point_name = 'catchment'

                self.catchments[point_id] = {
                    'name': point_name
                }
                # self.catchments[point_name] = point_id

            elif point_type_id == 1:  # demand site
                _point_name = 'demand site'

                self.demand_sites[point_id] = {
                    'name': point_name,
                    'x': point_x,
                    'y': point_y,
                    'cat': point_cat,
                    'processed': False,
                    'is_well': False  # it is preliminarily assumed to be a well
                }

            elif point_type_id == 17:  # return flow node
                _point_name = 'return flow node'

                self.other_nodes[point_id] = {
                    'name': point_name or _point_name,
                    'type': point_name,
                    'x': point_x,
                    'y': point_y
                }

            elif point_type_id == 13:  # inflow
                _point_name = 'tributary inflow'
                _point_type = 13

                if point_name:
                    self.river_break_nodes[point_id] = {
                        'node_id': point_id,
                        'node_name': point_name,
                        'node_type': _point_type,
                        'node_type_name': _point_name,
                        'x': point_x,
                        'y': point_y,
                        'distance': None,
                        'main_river_id': None,  # it will set by WEAPArc, when it will calculate the distance
                        'main_distance': None,
                        'secondary_river_id': None,  # it will set by WEAPArc
                        'secondary_distance': None,
                    }
                else:
                    msg_error = "[{}] inflow node node (ObjID=[{}]) without name. It will be ignorated." \
                        .format(_point_name.title(), point_id)
                    # self._errors['ris'].append(msg_error)
                    # self.append_error(msg=msg_error, typ=self.get_feature_type(), is_warn=True)

            elif point_type_id == 23:  # catchment inflow node
                _point_name = 'catchment inflow node'
                _point_type = 23

                if point_name:
                    self.river_break_nodes[point_id] = {
                        'node_id': point_id,
                        'node_name': point_name,
                        'node_type': _point_type,
                        'node_type_name': _point_name,
                        'x': point_x,
                        'y': point_y,
                        'distance': None,
                        'main_river_id': None,  # it will set by WEAPArc, when it will calculate the distance
                        'main_distance': None
                    }
                else:
                    msg_error = "[{}] inflow node node (ObjID=[{}]) without name. It will be ignorated." \
                        .format(_point_name.title(), point_id)
                    # self._errors['ris'].append(msg_error)
                    # self.append_error(msg=msg_error, typ=self.get_feature_type(), is_warn=True)

            elif point_type_id == 10:  # river withdrawal
                _point_name = 'river withdrawal'
                _point_type = 10

                if point_name:
                    self.river_break_nodes[point_id] = {
                        'node_id': point_id,
                        'node_name': point_name,
                        'node_type': _point_type,
                        'node_type_name': _point_name,
                        'x': point_x,
                        'y': point_y,
                        'distance': None,
                        'main_river_id': None,  # it will set by WEAPArc, when it will calculate the distance
                        'main_distance': None
                    }
                else:
                    msg_error = "[{}] inflow node node (ObjID=[{}]) without name. It will be ignorated."\
                        .format(_point_name.title(), point_id)
                    # self._errors['ris'].append(msg_error)
                    # self.append_error(msg=msg_error, typ=self.get_feature_type(), is_warn=True)

            elif point_type_id == 11:  # diversion outflow
                _point_name = 'diversion outflow'
                _point_type = 11

                if point_name:
                    self.river_break_nodes[point_id] = {
                        'node_id': point_id,
                        'node_name': point_name,
                        'node_type': _point_type,
                        'node_type_name': _point_name,
                        'x': point_x,
                        'y': point_y,
                        'distance': None,
                        'main_river_id': None,  # it will set by WEAPArc, when it will calculate the distance
                        'main_distance': None
                    }
                else:
                    msg_error = "[{}] inflow node node (ObjID=[{}]) without name. It will be ignorated."\
                        .format(_point_name.title(), point_id)
                    # self._errors['ris'].append(msg_error)
                    # self.append_error(msg=msg_error, typ=self.get_feature_type(), is_warn=True)

            else:
                _point_name = 'other'

                self.other_nodes[point_id] = {
                    'name': point_name or _point_name,
                    'type': point_type_id,
                    'x': point_x,
                    'y': point_y
                }

            # check if 'name' is null
            if not point_name:
                point_name = _point_name
                self.nodes[point_id]['name'] = point_name

        for l in arcmap.viter('lines'):
            line_name = l.attrs['Name']
            line_type_id = l.attrs['TypeID']  # 22: Runoff/Infiltration; 6: River
            line_type_name = l.attrs['TypeName']
            line_id = l.attrs['ObjID']

            line_cat = l.attrs['cat']
            node_src_id, node_dst_id = l.attrs['SrcObjID'], l.attrs['DestObjID']  # src: catchment; dst: gw

            if line_type_id == 22:  # Runoff/Infiltration
                # cases: catchment->[groundwater | catchment inflow node]
                node_src = self.nodes[node_src_id]
                node_dst = self.nodes[node_dst_id]

                if node_src['type_id'] == 21:  # catchment
                    self.arcs[line_id] = {
                        'type_id': line_type_id,
                        'src_id': node_src_id,
                        'dst_id': node_dst_id
                    }

                    if node_dst['type_id'] == 3 or node_dst['type_id'] == 23:  # groundwater | catchment inflow node
                        self.links['ri'][node_src_id] = node_dst_id
                    else:
                        msg_error = "Tipos permitidos para Runoff/Infiltration: catchment->[groundwater | catchment inflow node]. " \
                                    "Pero se encontro en el nodo [fin]: nombre={}, tipo={}.".format(node_dst['name'],
                                                                                                    node_dst['type_id'])
                        # self._errors['ris'].append(msg_error)
                        self.append_error(msg=msg_error, typ=self.get_feature_type(), is_warn=True)
                else:
                    msg_error = "Tipos permitidos para Runoff/Infiltration: catchment->[groundwater | catchment inflow node]. " \
                                "Pero se encontro en el nodo [inicio]: nombre={}, tipo={}.".format(node_src['name'],
                                                                                                   node_src['type_id'])
                    # self._errors['ris'].append(msg_error)
                    self.append_error(msg=msg_error, typ=self.get_feature_type(), is_warn=True)

            elif line_type_id == 7:  # transmission link
                # cases: groundwater->[demand site | catchment] or demand site->[catchment | tributary inflow] or river withdrawal->demand site
                node_src = self.nodes[node_src_id]
                node_dst = self.nodes[node_dst_id]

                if node_src['type_id'] == 3:  # groundwater
                    self.arcs[line_id] = {
                        'type_id': line_type_id,
                        'src_id': node_src_id,
                        'dst_id': node_dst_id
                    }

                    if node_dst['type_id'] == 1 or node_dst['type_id'] == 21:  # demand site | catchment
                        self.links['tl'][node_src_id] = node_dst_id
                    else:
                        msg_error = "Tipos permitidos para [Transmission Link]: (*)[groundwater]->[demand site] | [catchment] | " \
                                    "[demand site]->[catchment] | [tributary inflow] | [river withdrawal]->[demand site] | [catchment] | " \
                                    "[reservoir]->[demand site] | [catchment]" \
                                    "Pero se encontro en el nodo [fin]: [nombre={}], [tipo={}].".format(
                            node_dst['name'],
                            node_dst['type_id'])
                        # self._errors['tls'].append(msg_error)
                        self.append_error(msg=msg_error, typ=self.get_feature_type(), is_warn=True)
                elif node_src['type_id'] == 1:  # demand site
                    self.arcs[line_id] = {
                        'type_id': line_type_id,
                        'src_id': node_src_id,
                        'dst_id': node_dst_id
                    }

                    if node_dst['type_id'] == 21 or node_dst['type_id'] == 10 or node_dst['type_id'] == 13:  # catchment | tributary inflow
                        self.links['tl'][node_src_id] = node_dst_id
                    else:
                        msg_error = "Tipos permitidos para [Transmission Link]: [groundwater]->[demand site] | [catchment] | " \
                                    "(*)[demand site]->[catchment] | [tributary inflow] | [river withdrawal]->[demand site] | [catchment] | " \
                                    "[reservoir]->[demand site] | [catchment]" \
                                    "Pero se encontro en el nodo [fin]: [nombre={}], [tipo={}].".format(
                            node_dst['name'],
                            node_dst['type_id'])
                        # self._errors['tls'].append(msg_error)
                        self.append_error(msg=msg_error, typ=self.get_feature_type(), is_warn=True)
                elif node_src['type_id'] == 10:  # river withdrawal
                    self.arcs[line_id] = {
                        'type_id': line_type_id,
                        'src_id': node_src_id,
                        'dst_id': node_dst_id
                    }
                    if node_dst['type_id'] == 1 or node_dst['type_id'] == 21:  # demand site or catchment
                        self.links['tl'][node_src_id] = node_dst_id
                    else:
                        msg_error = msg_error = "Tipos permitidos para [Transmission Link]: [groundwater]->[demand site] | [catchment] | " \
                                    "[demand site]->[catchment] | [tributary inflow] | (*)[river withdrawal]->[demand site] | [catchment] | " \
                                    "[reservoir]->[demand site] | [catchment]" \
                                    "Pero se encontro en el nodo [fin]: [nombre={}], [tipo={}].".format(node_dst['name'],
                                                                                                    node_dst['type_id'])
                        # self._errors['tls'].append(msg_error)
                        self.append_error(msg=msg_error, typ=self.get_feature_type(), is_warn=True)
                elif node_src['type_id'] == 4:  # reservoir
                    self.arcs[line_id] = {
                        'type_id': line_type_id,
                        'src_id': node_src_id,
                        'dst_id': node_dst_id
                    }
                    if node_dst['type_id'] == 1 or node_dst['type_id'] == 21:  # demand site or catchment
                        self.links['tl'][node_src_id] = node_dst_id
                    else:
                        msg_error = "Tipos permitidos para [Transmission Link]: [groundwater]->[demand site] | [catchment] | " \
                                    "[demand site]->[catchment] | [tributary inflow] | [river withdrawal]->[demand site] | [catchment] | " \
                                    "[reservoir]->[demand site] | [catchment]" \
                                    "Pero se encontro en el nodo [fin]: [nombre={}], [tipo={}].".format(node_dst['name'],
                                                                                                    node_dst['type_id'])
                        # self._errors['tls'].append(msg_error)
                        self.append_error(msg=msg_error, typ=self.get_feature_type(), is_warn=True)
                else:
                    msg_error = "Tipos permitidos para [Transmission Link]: [groundwater]->[demand site] | [catchment] | " \
                                    "[demand site]->[catchment] | [tributary inflow] | [river withdrawal]->[demand site] | [catchment] | " \
                                    "[reservoir]->[demand site] | [catchment]" \
                                "Pero se encontro en el nodo [inicio]: [nombre={}], [tipo={}].".format(node_src['name'],
                                                                                                   node_src['type_id'])
                    # self._errors['tls'].append(msg_error)
                    self.append_error(msg=msg_error, typ=self.get_feature_type(), is_warn=True)

            elif line_type_id == 6 or line_type_id == 15:  # River or Canal
                if line_name:
                    self.rivers[line_id] = {
                        'name': line_name,
                        'id': line_id,
                        'cat': line_cat,
                        'type': line_type_id
                    }
                    # self.rivers[line_name] = line_id

                    self.arcs[line_id] = {
                        'type_id': line_type_id,
                        'src_id': None,
                        'dst_id': None
                    }

                    # complete distances in river break nodes (order <= [river arcs number]*[brak nodes number])
                    self._get_break_node_distance_from_arc(l)
                else:  # river without name
                    # TODO: add is_warn no append GeoKernel methods
                    msg_error = "River or Canal (ObjID=[{}]) without name".format(line_id)
                    self.append_error(msg=msg_error, typ=self.get_feature_type(), is_warn=True)

            elif line_type_id == 8:  # return flow
                # cases: demand site->[groundwater | return flow node]
                node_src = self.nodes[node_src_id]
                node_dst = self.nodes[node_dst_id]

                if node_src['type_id'] == 1:  # demand site
                    self.arcs[line_id] = {
                        'type_id': line_type_id,
                        'src_id': node_src_id,
                        'dst_id': node_dst_id
                    }

                    if node_dst['type_id'] == 3 or node_dst['type_id'] == 17:  # groundwater | return flow node
                        self.links['rf'][node_src_id] = node_dst_id
                        # catchment_to_gw[node_src_id] = node_dst_id
                    else:
                        msg_error = "Tipos permitidos para Return Flow: demand site->[groundwater | return flow node]. " \
                                    "Pero se encontro en el nodo [fin]: nombre={}, tipo={}.".format(node_dst['name'],
                                                                                                    node_dst['type_id'])
                        # self._errors['rfs'].append(msg_error)
                        self.append_error(msg=msg_error, typ=self.get_feature_type(), is_warn=True)
                else:
                    msg_error = "Tipos permitidos para Return Flow: demand site->[groundwater | return flow node]. " \
                                "Pero se encontro en el nodo [inicio]: nombre={}, tipo={}.".format(node_src['name'],
                                                                                                   node_src['type_id'])
                    # self._errors['rfs'].append(msg_error)
                    self.append_error(msg=msg_error, typ=self.get_feature_type(), is_warn=True)
            else:
                msg_error = "Tipos de enlaces permitidos: Runoff/Infiltration | Return Flow | River | Transmission Link. " \
                            "Datos de geometria encontrada: nombre={}, tipo={}, id={}".format(line_name, line_type_id,
                                                                                              line_id)
                # self._errors['others'].append(msg_error)
                self.append_error(msg=msg_error, typ=self.get_feature_type(), is_warn=True)

        self.summary.set_process_line(msg_name='setup_arcs', check_error=self.check_errors(),
                                      arcmap=arcmap, nodemap=nodemap)

        return self.check_errors(), self.get_errors()

    def get_arc_needed_field_names(self):
        fields = {
            'main': {  # arc name
                'name': self.config.fields_db[self.get_feature_type()]['arc_name'],
                'needed': True
            },
            'secondary': {  # arc type id
                'name': self.config.fields_db[self.get_feature_type()]['arc_type'],
                'needed': True
            },
            'limit': '',
        }

        return fields

    def get_node_needed_field_names(self):
        fields = {
            'main': {  # arc name
                'name': self.config.fields_db[self.get_feature_type()]['node_name'],
                'needed': True
            },
            'secondary': {  # arc type id
                'name': self.config.fields_db[self.get_feature_type()]['node_type'],
                'needed': True
            },
            'limit': '',
        }

        return fields
