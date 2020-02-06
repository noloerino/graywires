
from dataclasses import dataclass
from enum import Enum
from typing import Dict, List
from networkx import DiGraph


class WireUsage(Enum):
    UNUSED = 0
    USED = 1
    OUTPUT = 2


@dataclass
class GraphEdge:
    value: int
    width: int
    usage: WireUsage = WireUsage.USED
    src: "GraphVertex" = None
    dest: "GraphVertex" = None


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

def xor_from_nands_toposort(a: int, b: int) -> List[GraphVertex]:
    # Returns a topologically sorted graph representing an XOR circuit from 4 NANDs.
    # The output is the last wire.
    nand = lambda a, b: int(not bool(a & b & 0b1))
    m1 = nand(a, b)
    m2 = nand(a, m1)
    m3 = nand(b, m1)
    c = nand(m2, m3)
    edge_a_m1 = GraphEdge(a, 1)
    edge_b_m1 = GraphEdge(b, 1)
    edge_a_m2 = GraphEdge(a, 1)
    edge_b_m3 = GraphEdge(b, 1)
    edge_m1_m2 = GraphEdge(m1, 1)
    edge_m1_m3 = GraphEdge(m1, 1)
    edge_m2_c = GraphEdge(m2, 1)
    edge_m3_c = GraphEdge(m3, 1)
    # Peculiarity: create an edge with no ending node
    edge_c_out = GraphEdge(c, 1, usage=WireUsage.OUTPUT)
    return [
        Input1B("a", [], [edge_a_m1, edge_a_m2]),
        Input1B("b", [], [edge_b_m1, edge_b_m3]),
        NandGate1B("m1", [edge_a_m1, edge_b_m1], [edge_m1_m2, edge_m1_m3]),
        NandGate1B("m2", [edge_a_m2, edge_m1_m2], [edge_m2_c]),
        NandGate1B("m3", [edge_m1_m3, edge_b_m3], [edge_m3_c]),
        NandGate1B("c", [edge_m2_c, edge_m3_c], [edge_c_out])
    ]

def zero_and() -> List[GraphVertex]:
    a = GraphEdge(0, 1)
    b = GraphEdge(1, 1)
    return [
        Input1B("a", [], [a]),
        Input1B("b", [], [b]),
        AndGate1B("and", [a, b], [GraphEdge(0, 1, usage=WireUsage.OUTPUT)])
    ]

def orphan_inputs() -> List[GraphVertex]:
    a = GraphEdge(0, 1)
    b = GraphEdge(1, 1)
    c = GraphEdge(0, 1)
    d = GraphEdge(1, 1)
    # TODO c and d should be skipped due to mark and sweep
    return [
        Input1B("a", [], [a]),
        Input1B("b", [], [b]),
        Input1B("c", [], [c]),
        Input1B("d", [], [d]),
        AndGate1B("and", [a, b], [GraphEdge(0, 1, usage=WireUsage.OUTPUT)])
    ]

def mark_and_sweep(nodes: List[GraphVertex]) -> List[GraphVertex]:
    # Assume the output (root set) is the last element
    root = nodes[-1]
    marked = [root]
    # Track which nodes to traverse backwards
    stack = [root]
    while len(stack) != 0:
        node = stack.pop()
        for in_wire in node.inputs:
            if in_wire.usage != WireUsage.UNUSED and in_wire.src not in marked:
                marked.append(in_wire.src)
                stack.append(in_wire.src)
    return marked[::-1]


def main():
    # nodes = xor_from_nands_toposort(1, 1)
    # nodes = zero_and()
    nodes = orphan_inputs()
    for node in nodes:
        node.update_input_usage()
    for node in mark_and_sweep(nodes):
        print(f"{node.name}: {node.get_node_usage()}")
        # print(node)

if __name__ == '__main__':
    main()
