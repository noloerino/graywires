
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


@dataclass
class GraphVertex:
    name: str
    inputs: List[GraphEdge]
    outputs: List[GraphEdge]

    def update_input_usage(self):
        """
        Updates the usage of input edges based on the values of outputs, assuming that
        inputs are initialized to USED.
        """
        raise NotImplementedError()

    def get_node_usage(self):
        """
        This node is used iff all its outgoing edges are used.
        """
        usages = map(lambda e: e.usage, self.outputs)
        if WireUsage.OUTPUT in usages:
            return WireUsage.OUTPUT
        elif WireUsage.UNUSED in usages:
            return WireUsage.UNUSED
        else:
            return WireUsage.USED


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
    n_a = Input1B("a", [], [edge_a_m1, edge_a_m2])
    n_b = Input1B("b", [], [edge_b_m1, edge_b_m3])
    # Usage rules of AND and NAND gates are identical
    n_m1 = NandGate1B("m1", [edge_a_m1, edge_b_m1], [edge_m1_m2, edge_m1_m3])
    n_m2 = NandGate1B("m2", [edge_a_m2, edge_m1_m2], [edge_m2_c])
    n_m3 = NandGate1B("m3", [edge_b_m3, edge_m1_m3], [edge_m3_c])
    n_c = Output1B("c", [edge_m2_c, edge_m3_c], [edge_c_out])
    return [
        n_a,
        n_b,
        n_m1,
        n_m2,
        n_m3,
        n_c
    ]

def get_used_nodes(nodes):
    # Assume last node is output (root set)
    # Perform mark and sweep
    # output = 
    ...

def main():
    # nodes = xor_from_nands_toposort(0, 0)
    nodes = orphan_inputs()
    for node in nodes:
        node.update_input_usage()
    for node in nodes:
        print(f"{node.name}: {node.get_node_usage()}")

if __name__ == '__main__':
    main()
