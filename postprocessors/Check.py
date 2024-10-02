from abc import ABC, abstractmethod

class Check(ABC):
    def __init__(self):
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
    def node_check_operation(self, node_id, node):
        pass

    @abstractmethod
    def arc_check_operation(self, arc_id, arc):
        pass

    @abstractmethod
    def cell_check_operation(self, cell_id, cell):
        pass