from utils.Config import ConfigApp
from utils.Errors import ErrorManager
from utils.SummaryInfo import SummaryInfo

class GeoCase:
    """
    GeoCase class is meant to represent a case of connectivity between two feature types in the WEAP model.
    A superposition of two features in a cell must be corresponded by a link between those elements in the
    WEAP model.

    Attributes:
    ----------
    base_name : str
        The name of the base feature type. 
    super_name : str
        The name of the secondary feature type.
    config : ConfigApp
        The configuration object.
    arcs : dict
        A dictionary containing all the arcs of the WEAP model.
    nodes : dict
        A dictionary containing all the nodes of the WEAP model.
    connectivity : dict
        A dictionary meant to contain a connectivity map. The keys are primary objects and the values 
        are lists of secondary objects.
    errors : dict
        A dictionary meant to contain the errors found in the connectivity map. The keys are primary objects
        and the values are lists of secondary objects which are not connected to the primary object in WEAP.

    Methods:
    -------
    set_arcs_and_nodes(arcs, nodes)
        Set the arcs and nodes of the WEAP model for the case.
    
    set_connection(src_info, dst_info)
        Sets a connection between two elements if they are of the correct type for this case.
        
    get_element_info(element_id: int)
        Gets the information of the element with the given id returns the following structure:
        {       'type_id': point_type_id,
                'name': point_name,
                'x': point_x,
                'y': point_y,
                'cat': point_cat        }
    
    get_cell_element_data(cell: dict, feature_type: str)
        Gets the element data of the cell for the given feature type.
    
    check_cell(cell: dict)
        Checks if the case is correct for the given cell.

    """
    def __init__(self, base_feature_type: str, superior_feature_type: str, config: ConfigApp, one_to_one: bool = False):
        self.config = config

        self.base_name = base_feature_type
        self.super_name = superior_feature_type

        self.arcs = None
        self.nodes = None

        self.connectivity = {}
        self.errors = {}

    def set_arcs_and_nodes(self, arcs, nodes):
        self.arcs = arcs
        self.nodes = nodes

    def set_connection(self, src_info, dst_info):
        if src_info['type_id'] == self.config.nodes_type_id[self.base_name] and dst_info['type_id'] == self.config.nodes_type_id[self.super_name]:
            if self.connectivity.get(src_info['name']):
                self.connectivity[src_info['name']].append(dst_info['name'])
            else:
                self.connectivity[src_info['name']] = [dst_info['name']]
        elif src_info['type_id'] == self.config.nodes_type_id[self.super_name] and dst_info['type_id'] == self.config.nodes_type_id[self.base_name]:
            if self.connectivity.get(dst_info['name']):
                self.connectivity[dst_info['name']].append(src_info['name'])
            else:
                self.connectivity[dst_info['name']] = [src_info['name']]
    
    def get_element_info(self, element_id: int):
        return self.nodes.get(element_id)
    
    def get_cell_element_data(self, cell: dict, feature_type: str):
        feature = cell[feature_type]
        if feature:
            return feature["data"][0]["name"]
        else: 
            return None

    def check_cell(self, cell: dict):
        base_element = self.get_cell_element_data(cell, self.base_name)
        super_element = self.get_cell_element_data(cell, self.super_name)

        if not base_element or not super_element: # might depend on the case
            return True
        
        # ERROR: EXISTS IN MAP BUT NOT IN WEAP
        existence_in_weap = self.connectivity.get(base_element)
        if not existence_in_weap:
            return True
        
        check = super_element in self.connectivity[base_element]

        if not check:
            if not self.errors.get(base_element):
                self.errors[base_element] = set()
            self.errors[base_element].add(super_element)

        return check

class GeoCheck:
    """
    GeoCheck conducts superposition checks between the elements of the WEAP model and the elements of the linkage file.
    The class is meant to be used as a processor in the main pipeline.
    It loops over the arcs and cells only once.

    Attributes:
    ----------
    config : ConfigApp
        The configuration object.
    error : ErrorManager
        The error manager object.
    check : bool
        A flag to indicate if the check should be performed.
    _consolidate_cells : dict
        A dictionary containing the consolidated cells.
    arcs : dict
        A dictionary containing the information of all the arcs of the WEAP model.
    nodes : dict
        A dictionary containing the information of all the nodes of the WEAP model.
    _cases : list
        A list containing the GeoCase objects. Each one represents a superposition case to be checked.
    summary : SummaryInfo
        A summary object to store the results of the check.

    Methods:
    -------
    set_arcs_and_nodes(arcs, nodes)
        Set the arcs and nodes of the WEAP model as a dictionary.
    
    set_connectivity_cases()
        Set the connectivity cases for the GeoCheck object. Loops over the arcs and sets the connections
        for all cases.
    
    set_consolidate_cells(consolidate_cells)
        Set the consolidated cells for the GeoCheck object.
    
    get_summary()
        Get the summary object.
    
    setup(consolidate_cells, arcs, nodes)
        Setup the GeoCheck object with the consolidated cells, arcs and nodes.
    
    append_err(typ: str = None, msg: str = None, msgs: list = (), is_warn: bool = False, code: str = '')
        Append an error to the error manager.
    
    check_geometry()
        Checks the cells for errors in the superposition cases.
    
    run()
        Runs the GeoCheck object. If the check flag is set, it will run the check.
    """
    def __init__(self,  config: ConfigApp, error: ErrorManager, check: bool):
        self._config = config
        self._error = error
        self._check = check
        self._consolidate_cells = None
        self.arcs = None
        self.nodes = None 
        self._cases = [
                    GeoCase("groundwater", "demand_site", config),
                    GeoCase("groundwater", "catchment", config),
        ]
        self.summary = SummaryInfo(prefix="GeoCheck", errors=error, config=config)

    def set_arcs_and_nodes(self, arcs, nodes):
        self.arcs = arcs
        self.nodes = nodes
        for case in self._cases:
            case.set_arcs_and_nodes(arcs, nodes)

    def get_element_info(self, element_id: int):
        return self.nodes.get(element_id)

    def set_connectivity_cases(self):
        for _ , arc in self.arcs.items():
            arc_type_id = arc['type_id']

            if arc_type_id == self._config.arc_type_id['river']:
                continue

            src_info = self.get_element_info(arc['src_id'])
            dst_info = self.get_element_info(arc['dst_id'])

            if not src_info or not dst_info:
                continue
            
            for case in self._cases:
                case.set_connection(src_info, dst_info)

    def set_consolidate_cells(self, consolidate_cells):
        self._consolidate_cells = consolidate_cells
        return self._consolidate_cells
    
    def get_summary(self):
        return self.summary
    
    def setup(self, consolidate_cells, arcs, nodes):
        self.set_consolidate_cells(consolidate_cells)
        self.set_arcs_and_nodes(arcs, nodes)
        self.set_connectivity_cases()

    def append_err(self, typ: str = None, msg: str = None, msgs: list = (), is_warn: bool = False, code: str = ''):
        typ = typ if typ else "gc"

        if is_warn:
            if msg:
                self._error.append(msg=msg, typ=typ, is_warn=is_warn, code=code)
            elif msgs:
                for msg_str in msgs:
                    self._error.append(msg=msg_str, typ=typ, is_warn=is_warn, code=code)
        else:
            if msg:
                self._error.append(msg=msg, typ=typ, code=code)
            elif msgs:
                for msg_str in msgs:
                    self._error.append(msg=msg_str, typ=typ, code=code)

    def check_geometry(self):
        if not self._check:
            return
        for _, info in self._consolidate_cells.items():
            for case in self._cases:
                case.check_cell(info)
        
        for case in self._cases:
            for base_element, super_elements in case.errors.items():
                msg = f"El elemento {base_element} del tipo {case.base_name} no está conectado a los elementos {super_elements} de tipo {case.super_name}."
                self.append_err(msg=msg, is_warn=True)

    def run(self):
        if self._check and self._consolidate_cells and self.arcs and self.nodes:
            self.check_geometry()
        else: 
            self.append_err(msg="No se pudieron llevar a cabo los chequeos de geometría por falta de data.", is_warn=False)
