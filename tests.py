import unittest
from graph import *

def find_wire(name: str, nodes: List[GraphVertex]):
    for node in nodes:
        if node.name == name:
            return node
    return None

class TestSingleCycle(unittest.TestCase):

    def test_xor_from_nands(self) -> List[GraphVertex]:
        # Nodes are a topologically sorted graph representing an XOR circuit from 4 NANDs.
        # The output is the last wire.
        for a, b in ((0, 0), (0, 1), (1, 0), (1, 1)):
            nand = lambda a, b: int(not bool(a & b & 0b1))
            m1 = nand(a, b)
            m2 = nand(a, m1)
            m3 = nand(b, m1)
            c = nand(m2, m3)
            edge_a_m1 = Edge1B(0, a)
            edge_b_m1 = Edge1B(0, b)
            edge_a_m2 = Edge1B(0, a)
            edge_b_m3 = Edge1B(0, b)
            edge_m1_m2 = Edge1B(0, m1)
            edge_m1_m3 = Edge1B(0, m1)
            edge_m2_c = Edge1B(0, m2)
            edge_m3_c = Edge1B(0, m3)
            # Peculiarity: create an edge with no ending node
            edge_c_out = Edge1B(0, c, usage=WireUsage.OUTPUT)
            nodes = [
                Input1B("a", [], [edge_a_m1, edge_a_m2]),
                Input1B("b", [], [edge_b_m1, edge_b_m3]),
                NandGate1B("m1", [edge_a_m1, edge_b_m1], [edge_m1_m2, edge_m1_m3]),
                NandGate1B("m2", [edge_a_m2, edge_m1_m2], [edge_m2_c]),
                NandGate1B("m3", [edge_m1_m3, edge_b_m3], [edge_m3_c]),
                NandGate1B("c", [edge_m2_c, edge_m3_c], [edge_c_out])
            ]
            used = compute_usage(nodes)
            # Output should always be used
            self.assertIsNotNone(find_wire("c", used))
            # For an XOR, a and b should always be used
            self.assertIsNotNone(find_wire("a", used))
            self.assertIsNotNone(find_wire("b", used))


    def test_and(self) -> List[GraphVertex]:
        for a, b in ((0, 0), (0, 1), (1, 0), (1, 1)):
            w_a = Edge1B(0, a)
            w_b = Edge1B(0, b)
            nodes = [
                Input1B("a", [], [w_a]),
                Input1B("b", [], [w_b]),
                AndGate1B("and", [w_a, w_b], [Edge1B(0, a & b, usage=WireUsage.OUTPUT)])
            ]
            used = compute_usage(nodes)
            self.assertIsNotNone(find_wire("and", used))
            # If both inputs are 0, both are used
            if a == 0 and b == 0:
                self.assertIsNotNone(find_wire("a", used))
                self.assertIsNotNone(find_wire("b", used))
            elif a == 0:
                # a used, b unused
                self.assertIsNotNone(find_wire("a", used))
                self.assertIsNone(find_wire("b", used))
            elif b == 0:
                # a unused, b used
                self.assertIsNone(find_wire("a", used))
                self.assertIsNotNone(find_wire("b", used))
            else:
                # both used
                self.assertIsNotNone(find_wire("a", used))
                self.assertIsNotNone(find_wire("b", used))

    def test_orphan_inputs(self) -> List[GraphVertex]:
        a = Edge1B(0, 1)
        b = Edge1B(0, 1)
        c = Edge1B(0, 0)
        d = Edge1B(0, 1)
        # c and d should be skipped due to mark and sweep
        nodes = [
            Input1B("a", [], [a]),
            Input1B("b", [], [b]),
            Input1B("c", [], [c]),
            Input1B("d", [], [d]),
            AndGate1B("and", [a, b], [Edge1B(0, 1, usage=WireUsage.OUTPUT)])
        ]
        used = compute_usage(nodes)
        self.assertIsNotNone(find_wire("a", used))
        self.assertIsNotNone(find_wire("b", used))
        self.assertIsNotNone(find_wire("and", used))
        # orphaned inputs
        self.assertIsNone(find_wire("c", used))
        self.assertIsNone(find_wire("d", used))
