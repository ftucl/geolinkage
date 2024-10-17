from postprocessors.Check import Check
import numpy as np

class SuperpositionCheck(Check):
    """
    SuperpositionCheck class is a subclass of Check class.

    This class is used to check if a superposition between two features is corresponded
    by a connection in the WEAP model.

    Attributes:
    ----------
    base_feature : str
        Name of the base feature to check.
    secondary_feature : str
        Name of the secondary feature to check.
    base_feature_type_id : int
        Type ID of the base feature.
    secondary_feature_type_id : int
        Type ID of the secondary feature.
    base_names : dict
        Dictionary to store the names of the base features and the amount of cells
        it has in the linkage file.
    secondary_names : dict
        Dictionary to store the names of the secondary features and the amount of cells
        it has in the linkage file.
    nodes : dict
        Dictionary to store the nodes data.
    connections : dict
        Dictionary to store all the base features and the secondary features
        they are connected to.
    connection_error : dict
        Dictionary to store the errors found in the connections between the base
        and secondary features.

    Methods:
    --------
    add_error(base_element, super_element)
        Add an error to the connection_error dictionary, checks if the base element
        is already in the dictionary and if the super element is already in the base element
        dictionary.
    make_errors()
        Converts the connection_error dictionary into a list of errors strings.
    set_connection(base_info, secondary_info)
        Set the connection between the base and secondary features.
    check_connection(base_name, secondary_name)
        Check if the base element is connected to the secondary element. 
        It returns True if the connection exists or if the base element is not part
        of the WEAP model, False otherwise.
    make_connection_matrix()
        Create a matrix with the connections between the base and secondary features,
        used for visualization.
    make_error_matrix()
        Create a matrix with the amount of errors in the connections between the base
        and secondary features, used for visualization.
    get_name()
        Return the name of the check.
    get_description()
        Return the description of the check.
    plot(visualizator)
        Plot the results of the check, uses the Visualizator instance to write the
        images to files.
        Uses as subroutines the make_connection_matrix and make_error_matrix methods to
        create the necesary data for the visualization.
    arc_init_operation(arc_id, arc)
        Does nothing.
    node_init_operation(node_id, node)
        Saves the information for all the relevant nodes.
    cell_init_operation(cell_id, cell)
        Does nothing.
    arc_check_operation(arc_id, arc)
        Builds the connections between the base and secondary features.
    node_check_operation(node_id, node)
        Does nothing.
    cell_check_operation(cell_id, cell)
        Checks the connections between the base and secondary features present in
        each cell.
    """

    def __init__(self, base_feature, secondary_feature, config):
        super().__init__()
        self.base_feature = base_feature
        self.secondary_feature = secondary_feature

        self.base_feature_type_id = config.nodes_type_id[self.base_feature]
        self.secondary_feature_type_id = config.nodes_type_id[self.secondary_feature]

        self.base_names = {}
        self.secondary_names = {}
        self.nodes = {}

        self.connections = {}
        self.connection_error = {} 

    # Space for auxiliary functions specific to this class.

    def add_error(self, base_element, super_element):
        if not self.connection_error.get(base_element):
            self.connection_error[base_element] = {}
        if not self.connection_error[base_element].get(super_element):
            self.connection_error[base_element][super_element] = 0
        self.connection_error[base_element][super_element] += 1

    def make_errors(self):
        for base, secondaries in self.connection_error.items():
            self.errors.append(f"El elemento {base} del tipo {self.base_feature} no está conectado a los elementos {secondaries} de tipo {self.secondary_feature}.")

    def set_connection(self, base_info, secondary_info):
        if not self.connections.get(base_info["name"]):
            # should never happen because we already set every node with an empty dict 
            self.connections[base_info["name"]] = dict()
        self.connections[base_info["name"]][secondary_info["name"]] = 0

    def check_connection(self, base_name, secondary_name):
        if self.connections.get(base_name):
            return secondary_name in self.connections[base_name]
        
        # Solo llega aquí si no existe el elemento base en WEAP.
        return True

    def make_connection_matrix(self):
            base_names = list(self.base_names.keys())
            secondary_names = list(self.secondary_names.keys())

            matrix = np.ones((len(base_names), len(secondary_names)), dtype=float)

            for i, base in enumerate(base_names):
                for j, secondary in enumerate(secondary_names):
                    if secondary in self.connections[base]:
                        matrix[i][j] = 0
            
            # Add the errors in red
            for base, secondaries in self.connection_error.items():
                i = base_names.index(base)
                for secondary in secondaries:
                    j = secondary_names.index(secondary)
                    matrix[i][j] = 0.5

            # this made a simple connection matrix
            return matrix, base_names, secondary_names
    
    def make_error_matrix(self):
        base_names = list(self.base_names.keys())
        secondary_names = list(self.secondary_names.keys())

        matrix = np.zeros((len(base_names), len(secondary_names)), dtype=float)

        # Fill the matrix with the amount of cells in error for each connection
        for base, secondaries in self.connection_error.items():
            i = base_names.index(base)
            for secondary in secondaries:
                j = secondary_names.index(secondary)
                magnitud = self.connection_error[base][secondary] / self.secondary_names[secondary]
                print(magnitud)
                matrix[i][j] = magnitud
                
        return matrix, base_names, secondary_names
    # We use a structure to save the connections between nodes.e
    # We use another one to save a translation between the node ID and the node name.

    def get_name(self):
        return f"Superposition check between {self.base_feature} and {self.secondary_feature}"
    
    def get_description(self):
        return "Check if the base feature is superposed with the secondary feature."

    def plot(self, visualizator):
        matrix, base_labels, secondary_labels= self.make_connection_matrix()
        visualizator.write_matrix_img(matrix, "connection_matrix_"+self.base_feature+"_"+self.secondary_feature,
                                       base_labels, secondary_labels, cmap='rocket', linewidth=0.5,
                                       title="En negro conexiones entre "+self.base_feature+" y "+self.secondary_feature+".\nEn rojo las celdas con incongruencias entre modelos.")
        matrix, base_labels, secondary_labels= self.make_error_matrix()
        visualizator.write_matrix_img(matrix, "area_matrix_"+self.base_feature+"_"+self.secondary_feature,
                                       base_labels, secondary_labels, cmap='rocket_r', linewidth=0.5,
                                       title="Magnitud de errores en las conexiones entre "+self.base_feature+" y "+self.secondary_feature)

    def arc_init_operation(self, arc_id, arc):
        pass

    def node_init_operation(self, node_id, node):
        type_id = node['type_id']
        if type_id == self.base_feature_type_id or type_id == self.secondary_feature_type_id:
            self.nodes[node_id] = node
            if type_id == self.base_feature_type_id:
                self.base_names[node["name"]] = 0
                self.connections[node["name"]] = dict()
            else: 
                self.secondary_names[node["name"]] = 0

    def cell_init_operation(self, cell_id, cell):
        pass

    def arc_check_operation(self, arc_id, arc):
        src_id = arc["src_id"]
        dst_id = arc["dst_id"]

        if (src_id and dst_id) and (src_id in self.nodes and dst_id in self.nodes):
            if self.nodes[src_id]["type_id"] == self.base_feature_type_id and self.nodes[dst_id]["type_id"] == self.secondary_feature_type_id:
                self.set_connection(self.nodes[src_id], self.nodes[dst_id])
            elif self.nodes[src_id]["type_id"] == self.secondary_feature_type_id and self.nodes[dst_id]["type_id"] == self.base_feature_type_id:
                self.set_connection(self.nodes[dst_id], self.nodes[src_id])

    def node_check_operation(self, node_id, node):
        pass

    def cell_check_operation(self, cell_id, cell):
        base_element = self.get_cell_feature_names(cell, self.base_feature)
        secondary_element = self.get_cell_feature_names(cell, self.secondary_feature)

        for base_name in base_element:
            self.base_names[base_name] += 1
            for secondary_name in secondary_element:
                self.secondary_names[secondary_name] += 1
                if not self.check_connection(base_name, secondary_name):
                    self.add_error(base_name, secondary_name)
                else:
                    if self.connections.get(base_name):
                        self.connections[base_name][secondary_name] += 1
        
        self.make_errors()
        
                    

