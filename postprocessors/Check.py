from abc import ABC, abstractmethod

class Check(ABC):
    def __init__(self):
        self.errors = []

    # Space for auxiliary functions

    def get_cell_feature_data(self, cell, feature_type):
        # 
        feature = cell[feature_type]
        if feature:
            return feature["data"]
        else: 
            return None
    
    # This one incurs in a mistake when dealing with demand_sites, it only gives you the first demand site name.
    def get_cell_feature_names(self, cell, feature_type):
        names = []
        feature = cell[feature_type]
        if feature:
            for f in feature["data"]:
                names.append(f["name"])
        else: 
            return None

    # Abstract methods

    @abstractmethod
    def get_name(self):
        pass

    @abstractmethod
    def get_description(self):
        pass

    @abstractmethod
    def arc_init_operation(self, arc_id, arc):
        pass

    @abstractmethod
    def node_init_operation(self, node_id, node):
        pass

    @abstractmethod
    def cell_init_operation(self, cell_id, cell):
        pass

    @abstractmethod
    def arc_check_operation(self, arc_id, arc):
        pass

    @abstractmethod
    def node_check_operation(self, node_id, node):
        pass

    @abstractmethod
    def cell_check_operation(self, cell_id, cell):
        pass
    
    def get_errors(self):
        for value in self.errors:
            yield value