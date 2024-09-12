from GeoKernel import GeoKernel
from AppKernel import AppKernel
from utils.Config import ConfigApp
from utils.Errors import ErrorManager
from utils.SummaryInfo import SummaryInfo

class GeoCase:
    def __init__(self, base_feature_type: str, superior_feature_type: str, config: ConfigApp, geo: GeoKernel):
        self.base_name = base_feature_type
        self.base_id = config.nodes_type_id[base_feature_type]
        self.super_name = superior_feature_type
        self.super_id = config.nodes_type_id[superior_feature_type]
        self.geo = geo
        self.connectivity = {}
        self.set_connectivity()

    # Gets the type id of the element with the given id
    def get_element_type(self, element_id: int):
        return self.geo.nodes[element_id]['type_id']

    # Set the connectivity "matrix" for the given case, these could be made so you only iterate through
    # the arcs once, maybe later.
    def set_connectivity(self):
        self.connectivity = {}
        # _ is arc_id, not used currently
        for _ , value in self.geo.arcs.items():
            arc_type_id = value['type_id'] #maybe check that it is the appropriate type
                                           #if it's necessary add the info to the case structure

            # this ids are element id not type id
            src_id = value['src_id']
            dst_id = value['dst_id']
            # these are the type ids
            src_type_id = self.get_element_type(src_id)
            dst_type_id = self.get_element_type(dst_id)
            # then i'm saving the elements in a dictionary of lists
            if src_type_id == self.base_id and dst_type_id == self.super_id:
                if self.connectivity.get(src_id):
                    self.connectivity[src_id].append(dst_id)
                else:
                    self.connectivity[src_id] = [dst_id]
            elif src_type_id == self.super_id and dst_type_id == self.base_id:
                if self.connectivity.get(dst_id):
                    self.connectivity[dst_id].append(src_id)
                else:
                    self.connectivity[dst_id] = [src_id]
    
    def check_cell(self, cell: dict):
        base_element = cell[self.base_name]
        super_element = cell[self.super_name]

        return super_element in self.connectivity[base_element]
    
class GeoCheck:
    def __init__(self, geo: GeoKernel, app: AppKernel, config: ConfigApp, error: ErrorManager, epsg_code: str, gisdb: str, location: str, mapset: str, check: bool):
        self._config = config
        self._error = error
        self._geo = geo
        self._app = app
        self._check = check
        self._cases = [
                    GeoCase("groundwater", "demand_site", config, geo),
                    GeoCase("groundwater", "catchment", config, geo),
        ]

    # Check the cells from AppKernel for errors.
    def check_geometry(self):
        cells = self._app.get_consolidate_cells()

        for cell_id, info in cells.items():
            for case in self._cases:
                if not case.check_cell(info):
                    self._error.add_error("geometry", "The geometry is not correct", cell_id, info)

    def run(self):
        self.check_geometry()
        return self._error.get_errors()