from GeoKernel import GeoKernel
from AppKernel import AppKernel
from utils.Config import ConfigApp
from utils.Errors import ErrorManager
from utils.SummaryInfo import SummaryInfo

class GeoCase:
    def __init__(self, base_feature_type: str, superior_feature_type: str, config: ConfigApp):
        self.base_name = base_feature_type
        self.base_id = config.nodes_type_id[base_feature_type]
        self.super_name = superior_feature_type
        self.super_id = config.nodes_type_id[superior_feature_type]
        self.arcs = None
        self.nodes = None
        self.connectivity = {}
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
        err = []
        
        base_element = cell[self.base_name]
        super_element = cell[self.super_name]

        if base_element not in self.connectivity:
            err.append(f"Element {base_element} is not connected to {self.super_name} in the WEAP model.")

        return super_element in self.connectivity[base_element], err
    
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

    def set_consolidate_cells(self, app_kernel: AppKernel):
        if self._consolidate_cells:
            return self._consolidate_cells
        else:
            self._consolidate_cells = app_kernel.get_consolidate_cells()
            return self._consolidate_cells

    # Check the cells from AppKernel for errors.
    def check_geometry(self):
        if not self._check:
            return
        for _, info in self._consolidate_cells.items():
            for case in self._cases:
                status, err = case.check_cell(info)
                if not status:
                    self.append_err(msg=err, typ="gc", is_warn=True) #code="GC-01"?

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

    def run(self):
        self.check_geometry()