"""
Tests circuits constructed strictly using the graph primitives in graph.py.9gg
"""

import unittest
from graph import *

def find_wire(nodes: List[GraphVertex], name: str, cycle=0):
    for node, n_cycle in nodes:
        if node.name == name and cycle == n_cycle:
            return node
    return None


class TestMultiCycle(unittest.TestCase):

    def test_xor_fb(self):
        # Tests a circuit that looks like
        # input wire a;
        # reg out = 0;
        # wire m = a ^ out
        # always @posedge clk: out <= m
        # The circuit is run for two cycles, with a = 1 for both:
        # - At cycle 0: a = 1, out = 0, m = 1
        # - At cycle 1: a = 1, out = 1, m = 0
        # All the values in cycle 0 matter, but only OUT in cycle 1 matters.
        a_m_0 = Edge1B(0, 1)
        out_m_0 = Edge1B(0, 0) # Register reset value is 0
        m_out_0 = Edge1B(0, 1)
        out_m_1 = Edge1B(1, 1, usage=WireUsage.OUTPUT) # It's an output
        a_m_1 = Edge1B(1, 1)
        m_out_1 = Edge1B(1, 0)
        # For multi-cycle gates, be sure that wires are in order of cycle
        nodes = [
            Input1B("a", {}, {0: [a_m_0], 1: [a_m_1]}),
            XorGate1B("m", {0: [a_m_0, out_m_0], 1: [a_m_1, out_m_1]}, {0: [m_out_0], 1: [m_out_1]}),
            Output1B("out", {1: [m_out_0], 2: [m_out_1]}, {0: [out_m_0], 1: [out_m_1]})
        ]
        used = compute_usage(nodes, last_cycle=1)
        # All cycle 0 wires should be used
        self.assertIsNotNone(find_wire(used, "a", 0))
        self.assertIsNotNone(find_wire(used, "m", 0))
        self.assertIsNotNone(find_wire(used, "out", 0))
        # Only out is used on cycle 1
        self.assertIsNone(find_wire(used, "a", 1))
        self.assertIsNone(find_wire(used, "m", 1))
        self.assertIsNotNone(find_wire(used, "out", 1))
        return (nodes, used)


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
                Input1B("a", {}, {0: [edge_a_m1, edge_a_m2]}),
                Input1B("b", {}, {0: [edge_b_m1, edge_b_m3]}),
                NandGate1B("m1", {0: [edge_a_m1, edge_b_m1]}, {0: [edge_m1_m2, edge_m1_m3]}),
                NandGate1B("m2", {0: [edge_a_m2, edge_m1_m2]}, {0: [edge_m2_c]}),
                NandGate1B("m3", {0: [edge_m1_m3, edge_b_m3]}, {0: [edge_m3_c]}),
                NandGate1B("c", {0: [edge_m2_c, edge_m3_c]}, {0: [edge_c_out]})
            ]
            used = compute_usage(nodes)
            # Output should always be used
            self.assertIsNotNone(find_wire(used, "c"))
            # For an XOR, a and b should always be used
            self.assertIsNotNone(find_wire(used, "a"))
            self.assertIsNotNone(find_wire(used, "b"))


    def test_and(self) -> List[GraphVertex]:
        for a, b in ((0, 0), (0, 1), (1, 0), (1, 1)):
            w_a = Edge1B(0, a)
            w_b = Edge1B(0, b)
            nodes = [
                Input1B("a", {}, {0: [w_a]}),
                Input1B("b", {}, {0: [w_b]}),
                AndGate1B("and", {0: [w_a, w_b]}, {0: [Edge1B(0, a & b, usage=WireUsage.OUTPUT)]})
            ]
            used = compute_usage(nodes)
            self.assertIsNotNone(find_wire(used, "and"))
            # If both inputs are 0, both are used
            if a == 0 and b == 0:
                self.assertIsNotNone(find_wire(used, "a"))
                self.assertIsNotNone(find_wire(used, "b"))
            elif a == 0:
                # a used, b unused
                self.assertIsNotNone(find_wire(used, "a"))
                self.assertIsNone(find_wire(used, "b"))
            elif b == 0:
                # a unused, b used
                self.assertIsNone(find_wire(used, "a"))
                self.assertIsNotNone(find_wire(used, "b"))
            else:
                # both used
                self.assertIsNotNone(find_wire(used, "a"))
                self.assertIsNotNone(find_wire(used, "b"))

    def test_orphan_inputs(self) -> List[GraphVertex]:
        a = Edge1B(0, 1)
        b = Edge1B(0, 1)
        c = Edge1B(0, 0)
        d = Edge1B(0, 1)
        # c and d should be skipped due to mark and sweep
        nodes = [
            Input1B("a", {}, {0: [a]}),
            Input1B("b", {}, {0: [b]}),
            Input1B("c", {}, {0: [c]}),
            Input1B("d", {}, {0: [d]}),
            AndGate1B("and", {0: [a, b]}, {0: [Edge1B(0, 1, usage=WireUsage.OUTPUT)]})
        ]
        used = compute_usage(nodes)
        self.assertIsNotNone(find_wire(used, "a"))
        self.assertIsNotNone(find_wire(used, "b"))
        self.assertIsNotNone(find_wire(used, "and"))
        # orphaned inputs
        self.assertIsNone(find_wire(used, "c"))
        self.assertIsNone(find_wire(used, "d"))
        return (nodes, used)
