from AppKernel import AppKernel
from utils.Config import ConfigApp
from utils.Errors import ErrorManager
from utils.SummaryInfo import SummaryInfo

class GeoCase:
    def __init__(self, base_feature_type: str, superior_feature_type: str, config: ConfigApp, one_to_one: bool = False):
        self.base_name = base_feature_type
        self.base_id = config.nodes_type_id[base_feature_type]
        self.super_name = superior_feature_type
        self.super_id = config.nodes_type_id[superior_feature_type]
        # self.one_to_one = one_to_one
        self.arcs = None
        self.nodes = None
        self.connectivity = {}
        self.errors = {}

        self.set_connectivity()

    def set_arcs_and_nodes(self, arcs, nodes):
        self.arcs = arcs
        self.nodes = nodes

    # Set the connectivity "matrix" for the given case, these could be made so you only iterate through
    # the arcs once, maybe later.
    def set_connectivity(self):
        self.connectivity = {}
        # _ is arc_id, not used currently
        for _ , value in self.arcs.items():
            arc_type_id = value['type_id'] #maybe check that it is the appropriate type
                                           #if it's necessary add the info to the case structure

            # this ids are element id not type id
            src_id = value['src_id']
            dst_id = value['dst_id']
            # these are the type ids
            src_info = self.get_element_info(src_id)
            dst_info = self.get_element_info(dst_id)
            # then i'm saving the elements in a dictionary of lists
            if src_info['type_id'] == self.base_id and dst_info['type_id'] == self.super_id:
                if self.connectivity.get(src_info['name']):
                    self.connectivity[src_info['name']].append(dst_info['name'])
                else:
                    self.connectivity[src_info['name']] = [dst_info['name']]
            elif src_info['type_id'] == self.super_id and dst_info['type_id'] == self.base_id:
                if self.connectivity.get(dst_info['name']):
                    self.connectivity[dst_info['name']].append(src_info['name'])
                else:
                    self.connectivity[dst_info['name']] = [src_info['name']]
    
    # Gets the information of the element with the given id returns the following structure:
    # {
            # 'type_id': point_type_id,
            # 'name': point_name,
            # 'x': point_x,
            # 'y': point_y,
            # 'cat': point_cat
    # }
    def get_element_info(self, element_id: int):
        return self.nodes.get(element_id)

    def check_cell(self, cell: dict):
        # This should be working, but i don't know if the names are the same as the ones in the connectivity matrix
        base_element = cell[self.base_name]
        super_element = cell[self.super_name]
        
        ## meant to treat the case where the existence of an object implies the existence of another (GW-CATCH)
        ## not sure if necessary
        # if self.one_to_one and (not base_element or not super_element):
        #     err.append(f"La celda {cell['cell_id']} no tiene un elemento {self.base_name} o {self.super_name} asociado.")

        check = super_element in self.connectivity[base_element]

        if not check:
            if not self.errors.get(base_element):
                self.errors[base_element] = [super_element]
            else:
                self.errors[base_element].append(super_element)

        return check
    
class GeoCheck:
    def __init__(self,  config: ConfigApp, error: ErrorManager, check: bool):
        self._config = config
        self._error = error
        self._check = check
        self._consolidate_cells = None
        self.summary = SummaryInfo(prefix="GeoCheck", errors=error, config=config)
        self.arcs = None
        self.nodes = None 
        self._cases = [
                    GeoCase("groundwater", "demand_site", config),
                    GeoCase("groundwater", "catchment", config),
        ]

    def set_arcs_and_nodes(self, arcs, nodes):
        self.arcs = arcs
        self.nodes = nodes
        for case in self._cases:
            case.set_arcs_and_nodes(arcs, nodes)

    def set_consolidate_cells(self, consolidate_cells):
        self._consolidate_cells = consolidate_cells
        return self._consolidate_cells
    
    # Meant to be called by AppKernel when all the other processors are finished.
    def setup(self, consolidate_cells, arcs, nodes):
        self.set_consolidate_cells(consolidate_cells)
        self.set_arcs_and_nodes(arcs, nodes)

    def append_err(self, typ: str = None, msg: str = None, msgs: list = (), is_warn: bool = False, code: str = ''):
        typ = typ if typ else "gc"

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

    # Check the cells from AppKernel for errors.
    def check_geometry(self):
        if not self._check:
            return
        for _, info in self._consolidate_cells.items():
            for case in self._cases:
                case.check_cell(info)
        
        for case in self._cases:
            for base_element, super_elements in case.errors.items():
                msg = f"El elemento {base_element} del tipo {case.base_name} no está conectado a los elementos {super_elements} de tipo {case.super_name}."
                self.append_err(msg=msg, is_warn=False)

    def run(self):
        if self._check and self._consolidate_cells and self.arcs and self.nodes:
            print("HOLA")
            # self.check_geometry()
        else: 
            print("HOLAn't")
            self.append_err(msg="GeoCheck couldn't run, missing data.", is_warn=False)