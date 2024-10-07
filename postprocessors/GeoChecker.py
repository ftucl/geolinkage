from utils.SummaryInfo import SummaryInfo
from utils.Errors import ErrorManager

class GeoChecker:
    def __init__(self, checks, config):
        self.arcs = None
        self.nodes = None
        self.cells = None

        self.checks = checks

        self.config = config
        self.error = ErrorManager(config)
        self.summary = SummaryInfo('GeoChecker', self.error, config)

    def set_arcs_and_nodes(self, arcs, nodes):
        self.arcs = arcs
        self.nodes = nodes
    
    def set_consolidate_cells(self, cells):
        self.cells = cells

    def get_summary(self):
        return self.summary

    def print_checks(self):
        checks_str = ''
        for check in self.checks:
            checks_str += '     [{}]: {} \n'.format(check.get_name(), check.get_description())
        return checks_str
    
    def checking_errors(self):
        for check in self.checks:
            for error in check.get_errors():
                self.error.append(msg= error, typ= 'gc', is_warn= True)
        
    def setup(self, consolidate_cells, arcs, nodes):
        self.set_consolidate_cells(consolidate_cells)
        self.set_arcs_and_nodes(arcs, nodes)
        
    def init_nodes_loop(self):
        # Node structure                 
        #        - 'type_id': geometry type ID.
        #        - 'name': node name.
        #        - 'x': x-axis position of the node.
        #        - 'y': y-axis position of the node.
        #        - 'cat': node internal ID (used by 'pygrass library').


        for node_id, node in self.nodes.items():
            for check in self.checks:
                check.node_init_operation(node_id ,node)
        
        self.summary.set_process_line("init_check_node", check_error = False)

    def init_arcs_loop(self):
        # Arc structure
        #       - 'type_id': geometry type ID.
        #       - 'src_id': source node ID (or None)
        #       - 'dst_id': destination node ID (or None).

        for arc_id , arc in self.arcs.items():
            for check in self.checks:
                check.arc_init_operation(arc_id, arc)
        
        self.summary.set_process_line("init_check_arc", check_error = False)
        
    def init_cells_loop(self):
        # Cell structure
        # {
        # 'catchment': {number_of_data : int, cell_id : int, row : int, col : int, data : [{area : float, cell_id : int, name : str, map_name : str}]},
        # 'groundwater': {number_of_data : int, cell_id : int, row : int, col : int, data : [{area : float, cell_id : int, name : str, map_name : str}]},
        # 'river': {number_of_data : int, cell_id : int, row : int, col : int, data : [{area : float, cell_id : int, name : str, map_name : str}]},
        # 'demand_site': {number_of_data : int, cell_id : int, row : int, col : int, data : [{area : float, cell_id : int, name : str, map_name : str}]}
        # }
        for cell_id, cell in self.cells.items():
            for check in self.checks:
                check.cell_init_operation(cell_id, cell)

        self.summary.set_process_line("init_check_cell", check_error = False)

    def check_nodes_loop(self):
        for node_id, node in self.nodes.items():
            for check in self.checks:
                check.node_check_operation(node_id, node)
        
        self.summary.set_process_line("perform_check_node", check_error = False)

    def check_arcs_loop(self):
        for arc_id, arc in self.arcs.items():
            for check in self.checks:
                check.arc_check_operation(arc_id, arc)
        
        self.summary.set_process_line("perform_check_arc", check_error = False)

    def check_cells_loop(self):
        for cell_id, cell in self.cells.items():
            for check in self.checks:
                check.cell_check_operation(cell_id, cell)

        self.summary.set_process_line("perform_check_cell", check_error = False)

    def build_checks(self):
        self.init_arcs_loop()
        self.init_nodes_loop()
        self.init_cells_loop()

    def perform_checks(self):
        self.check_arcs_loop()
        self.check_nodes_loop()
        self.check_cells_loop()
        
    def run(self):
        self.summary.set_input_param('checks', self.print_checks())
        # Initializing secuence
        self.build_checks()
        # Checking secuence
        self.perform_checks()
        # Return errors.
        self.checking_errors()
        # Here somebody should ask for the summary



        

