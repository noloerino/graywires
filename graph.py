
from dataclasses import dataclass
from enum import Enum
from typing import List


class WireUsage(Enum):
    UNUSED = 0
    USED = 1
    OUTPUT = 2


@dataclass
class GraphEdge:
    cycle: int
    value: int
    width: int
    usage: WireUsage = WireUsage.USED
    src: "GraphVertex" = None
    dest: "GraphVertex" = None


def Edge1B(cycle, value, usage=WireUsage.USED):
    return GraphEdge(cycle, value, 1, usage)


@dataclass
class GraphVertex:
    name: str
    inputs: List[GraphEdge]
    outputs: List[GraphEdge]

    def __post_init__(self):
        for e in self.inputs:
            e.dest = self
        for e in self.outputs:
            e.src = self

    def update_input_usage(self):
        """
        Updates the usage of input edges based on the values of outputs, assuming that
        inputs are initialized to USED.
        """
        raise NotImplementedError()

    def get_node_usage(self):
        """
        This node is used iff any of its outgoing edges are used.
        """
        usages = [e.usage for e in self.outputs]
        if WireUsage.OUTPUT in usages:
            return WireUsage.OUTPUT
        elif WireUsage.USED in usages:
            return WireUsage.USED
        else:
            return WireUsage.UNUSED


# === Usage rules for simple gates ===
class Input1B(GraphVertex):
    def update_input_usage(self):
        pass

class Output1B(GraphVertex):
    def update_input_usage(self):
        pass

class AndGate1B(GraphVertex):
    def update_input_usage(self):
        a = self.inputs[0].value
        b = self.inputs[1].value
        # TODO
        # Since there's a single output, all should be of the same value
        # How do we propagate this?
        if self.outputs[0].value == 1:
            # Both certainly used
            pass
        else:
            if a == 0 and b == 0:
                # Conservatively both used
                pass
            elif a == 0:
                # a used, b unused
                self.inputs[1].usage = WireUsage.UNUSED
            elif b == 0:
                self.inputs[0].usage = WireUsage.UNUSED
            else:
                assert False, "Impossible case in AndGate1B"

class NandGate1B(GraphVertex):
    def update_input_usage(self):
        a = self.inputs[0].value
        b = self.inputs[1].value
        if self.outputs[0].value == 0:
            # Both certainly used
            pass
        else:
            if a == 0 and b == 0:
                # Conservatively both used
                pass
            elif a == 0:
                # a used, b unused
                self.inputs[1].usage = WireUsage.UNUSED
            elif b == 0:
                self.inputs[0].usage = WireUsage.UNUSED
            else:
                assert False, "Impossible case in NandGate1B"

class OrGate1B(GraphVertex):
    def update_input_usage(self):
        a = self.inputs[0].value
        b = self.inputs[1].value
        if self.outputs[0].value == 0:
            # Both certainly used
            pass
        else:
            if a == 1 and b == 1:
                # Conservatively both used
                pass
            elif a == 1:
                # a used, b unused
                self.inputs[1].usage = WireUsage.UNUSED
            elif b == 1:
                self.inputs[0].usage = WireUsage.UNUSED
            else:
                assert False, "Impossible case in OrGate1B"

class NotGate1B(GraphVertex):
    def update_input_usage(self):
        # Input is always used
        assert bool(self.inputs[0].value) is not bool(self.outputs[0].value)

class Mux4B(GraphVertex):
    def update_input_usage(self):
        pass

def compute_usage(nodes: List[GraphVertex]) -> List[GraphVertex]:
    for node in nodes:
        node.update_input_usage()
    return mark_and_sweep(nodes)

def mark_and_sweep(nodes: List[GraphVertex]) -> List[GraphVertex]:
    root_set = [node for node in nodes if node.get_node_usage() is WireUsage.OUTPUT]
    marked = root_set[:]
    # Track which nodes to traverse backwards
    stack = root_set[:]
    while len(stack) != 0:
        node = stack.pop()
        for in_wire in node.inputs:
            if in_wire.usage != WireUsage.UNUSED and in_wire.src not in marked:
                marked.append(in_wire.src)
                stack.append(in_wire.src)
    return marked[::-1]
