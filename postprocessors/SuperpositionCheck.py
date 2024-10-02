from Check import Check

class SuperpositionCheck(Check):
    def __init__(self):
        super().__init__()

    # We use a structure to save the connections between nodes.

    def arc_init_operation(self, arc_id, arc):
        pass

    def node_init_operation(self, node_id, node):
        pass

    def cell_init_operation(self, cell_id, cell):
        pass

    def node_check_operation(self, node_id, node):
        pass

    def arc_check_operation(self, arc_id, arc):
        pass

    def cell_check_operation(self, cell_id, cell):
        pass