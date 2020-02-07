
from dataclasses import dataclass
from enum import Enum
from typing import Dict, List


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
    # Inputs and outputs are keyed on cycle.
    # It should be interpreted as "on cycle [key], these inputs produce these outputs."
    # Even though edges encode cycles, it is possible for a value from cycle 0 to be used on cycle 1,
    # which is how we represent registers.
    inputs: Dict[int, List[GraphEdge]]
    outputs: Dict[int, List[GraphEdge]]

    def __post_init__(self):
        for _, input_list in self.inputs.items():
            for e in input_list:
                e.dest = self
        for _, output_list in self.outputs.items():
            for e in output_list:
                e.src = self

    def __repr__(self):
        return f"GraphVertex(name={self.name})"

    def update_input_usage(self, inputs, outputs):
        """
        Updates the usage of the given input edges on a given cycle based on the values
        of the given outputs, assuming that inputs are initialized to USED.
        """
        raise NotImplementedError()

    def get_node_usage(self, cycle=0):
        """
        Calculates whether or not this node is used on the specified cycle.

        A quirk of the current system is that all outgoing edges actually represent
        a single output wire coming from the gate represented by this GraphVertex.
        Consequently, this wire is USED if any of its "outputs" are USED.
        """
        usages = [e.usage for e in self.outputs.get(cycle, [])]
        if WireUsage.OUTPUT in usages:
            return WireUsage.OUTPUT
        elif WireUsage.USED in usages:
            return WireUsage.USED
        else:
            return WireUsage.UNUSED


# === Usage rules for simple gates ===
class Input1B(GraphVertex):
    def update_input_usage(self, inputs, outputs):
        assert len(inputs) == 0

class Output1B(GraphVertex):
    def update_input_usage(self, inputs, outputs):
        pass

class AndGate1B(GraphVertex):
    def update_input_usage(self, inputs, outputs):
        a = inputs[0].value
        b = inputs[1].value
        # TODO
        # Since there's a single output, all should be of the same value
        # How do we propagate this?
        if outputs[0].value == 1:
            # Both certainly used
            pass
        else:
            if a == 0 and b == 0:
                # Conservatively both used
                pass
            elif a == 0:
                # a used, b unused
                inputs[1].usage = WireUsage.UNUSED
            elif b == 0:
                inputs[0].usage = WireUsage.UNUSED
            else:
                assert False, "Impossible case in AndGate1B"

class NandGate1B(GraphVertex):
    def update_input_usage(self, inputs, outputs):
        a = inputs[0].value
        b = inputs[1].value
        if outputs[0].value == 0:
            # Both certainly used
            pass
        else:
            if a == 0 and b == 0:
                # Conservatively both used
                pass
            elif a == 0:
                # a used, b unused
                inputs[1].usage = WireUsage.UNUSED
            elif b == 0:
                inputs[0].usage = WireUsage.UNUSED
            else:
                assert False, "Impossible case in NandGate1B"

class OrGate1B(GraphVertex):
    def update_input_usage(self, inputs, outputs):
        a = inputs[0].value
        b = inputs[1].value
        if outputs[0].value == 0:
            # Both certainly used
            pass
        else:
            if a == 1 and b == 1:
                # Conservatively both used
                pass
            elif a == 1:
                # a used, b unused
                inputs[1].usage = WireUsage.UNUSED
            elif b == 1:
                inputs[0].usage = WireUsage.UNUSED
            else:
                assert False, "Impossible case in OrGate1B"

class NotGate1B(GraphVertex):
    def update_input_usage(self, inputs, outputs):
        # Input is always used
        assert bool(outputs[0].value) is not bool(inputs[0].value)

class XorGate1B(GraphVertex):
    def update_input_usage(self, inputs, outputs):
        # Everything's used
        assert bool(outputs[0].value) is bool(inputs[0].value ^ inputs[1].value)

class Mux4B(GraphVertex):
    def update_input_usage(self, inputs, outputs):
        # TODO
        pass

def compute_usage(nodes: List[GraphVertex], last_cycle=0) -> List[GraphVertex]:
    # Iterate forwards through cycles - though outputs affect inputs, we still propagate forwards
    for i in range(last_cycle + 1):
        for node in nodes:
            node.update_input_usage(node.inputs.get(i, []), node.outputs.get(i, []))
        # print([f"usage: {node.name}@{i} {node.get_node_usage(i)}" for node in nodes])
    return mark_and_sweep(nodes, last_cycle)

def mark_and_sweep(nodes: List[GraphVertex], last_cycle=0) -> List[GraphVertex]:
    root_set = []
    for i in range(last_cycle + 1):
        root_set = [(node, i) for node in nodes if node.get_node_usage(i) is WireUsage.OUTPUT]
    marked = root_set[:]
    # Track which nodes to traverse backwards
    stack = root_set[:]
    while len(stack) != 0:
        (node, cycle) = stack.pop()
        for in_wire in node.inputs.get(cycle, []):
            pair = (in_wire.src, in_wire.cycle)
            if in_wire.usage != WireUsage.UNUSED and pair not in marked:
                marked.append(pair)
                stack.append(pair)
    return marked[::-1]
