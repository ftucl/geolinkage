from anytree import Node, RenderTree, NodeMixin, AsciiStyle
from anytree.search import find_by_attr


class RiverNode(NodeMixin):

    segments_list = {}

    def __init__(self, node_id, node_name, node_type, node_distance, root_node=None, parent=None, children=None):
        super(RiverNode, self).__init__()

        if root_node:
            self.root_node = root_node

        self.node_id = node_id
        self.node_name = node_name
        self.node_type = node_type
        self.node_distance = node_distance  # if it is a inflow node, use the main_river_distance
        self.x = None
        self.y = None
        self.node_cat = -1  # TODO: Should be the main_river_cat from childs

        self.parent = parent
        if children:
            self.children = children

        self.river_segments = []

        # main river or parent river
        self.main_river_cat = None
        self.main_river_name = None
        self.main_river_id = None
        self.main_river_distance = self.node_distance

        # secondary river or subflow river
        self.secondary_river_cat = None
        self.secondary_river_name = None
        self.secondary_river_id = None
        self.secondary_river_distance = None

    @classmethod
    def get_segment_break_name(cls, segment_line_cat):
        segment_break_name = RiverNode.segments_list[segment_line_cat]['break_name']
        river_name = RiverNode.segments_list[segment_line_cat]['river_name']

        return segment_break_name, river_name

    def set_main_river(self, river_id, river_name, river_cat, river_distance):
        # make an node representing main river (parent river)
        # if not self.parent == self.root_node:
        main_river = find_by_attr(self.root_node, name="node_id", value=river_id)

        if not main_river:
            _river_type = 13
            main_river = RiverNode(river_id, river_name, _river_type, river_distance, self.root_node, parent=self.root_node)
            main_river.node_cat = river_cat  # TODO: refactor to include it into constructor

        self.parent = main_river

        self.main_river_id = river_id
        self.main_river_name = river_name
        self.main_river_cat = river_cat
        self.main_river_distance = river_distance

    def set_secondary_river(self, river_id, river_name, river_cat, river_distance):
        self.secondary_river_id = river_id
        self.secondary_river_name = river_name
        self.secondary_river_cat = river_cat
        self.secondary_river_distance = river_distance

    def set_coords(self, node_x, node_y):
        self.x = node_x
        self.y = node_y

    def get_order_children_by_distance(self):
        if self.is_root:
            return self.children
        else:
            children = sorted(self.children, key=lambda x: x.node_distance, reverse=False)
            return children

    def get_segments_list(self):
        segments = []
        for child_node in self.children:
            segment = child_node.get_break_input_by_river()

            segments += segment

        self.river_segments = segments

        return segments

    def get_segments_format(self, river_node_id=None):
        if river_node_id:
            river_node = find_by_attr(self, name="node_id", value=river_node_id)
        else:
            river_node = self

        segments_str = ''
        for ind, segment in enumerate(self.river_segments):
            # set class variable [segments_list] to link with segments
            segment['feature_id'] = ind + 1
            RiverNode.segments_list[ind + 1] = segment

            # make string to use like input in [v.segment]
            segments_str += '{} {} {} {} {} \n'.format(
                segment['type'], segment['feature_id'], segment['cat'], segment['start_offset'], segment['end_offset'])
        # print(segments_str)

        return segments_str

    def get_break_input_by_river(self, river_node_id=None):
        if river_node_id:
            river_node = find_by_attr(self, name="node_id", value=river_node_id)
        else:
            river_node = self

        # river data
        river_node_id = river_node.node_id
        river_node_name = river_node.node_name
        river_node_cat = river_node.node_cat
        river_node_distance = river_node.node_distance

        children = river_node.get_order_children_by_distance()

        # inital condition
        segments = []
        node_before_name = river_node_name
        node_before_distance = 0
        last_child = river_node
        for i, child_node in enumerate(children):
            # (1) make segments from this child
            if not child_node.is_leaf:
                child_node.get_break_input_by_river()
            else:  # to keep the river segment if it has a secondary river
                if child_node.node_type == 13 and child_node.secondary_river_id:  # is a Tributary Inflow
                    break_name = "Below {} Headflow".format(child_node.secondary_river_name)
                    segment = {
                        'type': 'L',
                        'cat': child_node.secondary_river_cat,
                        'start_offset': '0',
                        'end_offset': '100%',
                        'break_name': break_name,
                        'river_name': child_node.secondary_river_name
                    }
                    segments.append(segment)

            # (2) make input from child to parent river
            child_name = child_node.node_name
            child_distance = child_node.node_distance  # distance from main river
            child_id = child_node.node_id  # id from WEAPNode map

            if i == 0:
                break_name = "Below {} Headflow".format(node_before_name)
            else:
                break_name = "Below {}".format(node_before_name)

            segment = {
                'type': 'L',
                'cat': river_node_cat,
                'start_offset': node_before_distance,
                'end_offset': child_distance,
                'break_name': break_name,
                'river_name': river_node_name
            }
            segments.append(segment)

            # final conditions
            node_before_name = child_name
            node_before_distance = child_distance
            last_child = child_node
        else:
            child_name = last_child.node_name
            child_distance = last_child.node_distance  # distance from main river
            child_id = last_child.node_id * 100  # unique ID using double 0's for final segment

            break_name = "Below {}".format(child_name)

            segment = {
                'type': 'L',
                'cat': river_node_cat,
                'start_offset': child_distance,
                'end_offset': '100%',
                'break_name': break_name,
                'river_name': river_node_name
            }
            segments.append(segment)

        river_node.river_segments = segments

        return segments
