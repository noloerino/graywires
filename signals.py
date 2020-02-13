from typing import List, Tuple
import vcd
from graph import *
from test_graph import TestMultiCycle, TestSingleCycle

def dump(path, nodes: List[GraphVertex], used: Tuple[List[GraphVertex], int] = None, last_cycle=0):
    # Assume that all nodes have only one output
    with open(path, "w") as f:
        with vcd.VCDWriter(f, timescale="1 ns", date="today") as writer:
            clk = writer.register_var("module", "clk", "time", size=1)
            var_dict = {}
            for node in nodes:
                # Assume only one edge
                output_edge = list(node.outputs.values())[0][0]
                var_dict[node.name] = writer.register_var("module", node.name, "integer", size=output_edge.width)
            for cycle in range(last_cycle + 1):
                for node in nodes:
                    var = var_dict[node.name]
                    if cycle in node.outputs and (used is None or (node, cycle) in used):
                        value = node.outputs[cycle][0].value
                    else:
                        value = "x"
                    print(f"{node}@{cycle}={value}")
                    writer.change(var, cycle * 2, value)
                writer.change(clk, cycle * 2, 1)
                writer.change(clk, cycle * 2 + 1, 0)

def main():
    xor_wires, xor_used = TestMultiCycle().test_xor_fb()
    dump("xor_2cyc.vcd", xor_wires, xor_used, last_cycle=2)
    orphan_wires, orphan_used = TestSingleCycle().test_orphan_inputs()
    dump("orphan_1cyc.vcd", orphan_wires, orphan_used, last_cycle=1)

if __name__ == '__main__':
    main()
