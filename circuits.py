
import collections.abc
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Set, Tuple, Union
import vcd # type: ignore

@dataclass(frozen=True)
class BitVector:
    value: int
    width: int


class WireUsage(Enum):
    UNUSED = 0
    USED = 1
    OUTPUT = 2


@dataclass
class ConcreteWire:
    """
    The concrete value of a named wire on a given cycle.

    Overriding operators allows us to perform analyses and create metadata on these objects.
    """
    name: str
    bv: BitVector
    cycle: int
    usage: WireUsage = WireUsage.UNUSED
    srcs: List["ConcreteWire"] = field(default_factory=list) # Represents the wires that are used to compute this wire

    # TODO If we proceed with returning the list of sources anyway, we might not even need
    # the whole used/unused field, since the list populates edges anyway, and usage is a proxy
    # for the existence of an edge.
    def __and__(self, o) -> Tuple[BitVector, List["ConcreteWire"]]:
        if self.bv.value == 1 and o.bv.value == 1:
            self.usage = WireUsage.USED
            o.usage = WireUsage.USED
        elif self.bv.value == 1 and o.bv.value == 0:
            self.usage = WireUsage.UNUSED
            o.usage = WireUsage.USED
        elif self.bv.value == 0 and o.bv.value == 1:
            self.usage = WireUsage.USED
            o.usage = WireUsage.UNUSED
        else:
            self.usage = WireUsage.USED
            o.usage = WireUsage.USED
        return (
            BitVector(self.bv.value & o.bv.value, min(self.bv.width, o.bv.width)),
            [self, o]
        )

    def __xor__(self, o) -> Tuple[BitVector, List["ConcreteWire"]]:
        self.usage = WireUsage.USED
        o.usage = WireUsage.USED
        return (
            BitVector(self.bv.value ^ o.bv.value, min(self.bv.width, o.bv.width)),
            [self, o]
        )

    def __repr__(self) -> str:
        return f"ConcreteWire(name={self.name}, bv={self.bv}, cycle={self.cycle}, usage={self.usage})"


@dataclass
class WireBundle(collections.abc.MutableMapping):
    """
    Represents a concrete collection of wires (e.g. the state of a circuit) on a given cycle.
    """

    cycle: int
    wires: Dict[str, ConcreteWire]
    frozen: bool = False

    def __init__(self, cycle):
        self.wires = {}
        self.cycle = cycle

    def __getitem__(self, key: str) -> ConcreteWire:
        return self.wires[key]

    def __setitem__(self, key: str, value: Union[ConcreteWire, Tuple[BitVector, List[ConcreteWire]]]):
        if self.frozen:
            raise KeyError("Cannot write to a frozen WireBundle")
        wire: ConcreteWire
        if isinstance(value, ConcreteWire):
            wire = ConcreteWire(key, value.bv, self.cycle, srcs=[value])
        else:
            wire = ConcreteWire(key, value[0], self.cycle, srcs=value[1])
        self.wires[key] = wire

    def __delitem__(self, key: str):
        del self.wires[key]

    def __iter__(self):
        return iter(self.wires)

    def __len__(self):
        return len(self.wires)

    def freeze(self) -> "WireBundle":
        """
        Prevents modifications from being made to the WireBundle, e.g. once computation of a state
        has been completed.
        """
        self.frozen = True
        return self


CYCLE_LEN_NS = 2
assert CYCLE_LEN_NS & 1 == 0, "Cycle length must be even to accomodate falling edge"

class Circuit:
    def at_posedge_clk(self, curr_state: WireBundle, inputs: WireBundle,
                       next_state: WireBundle, outputs: WireBundle):
        """
        Updates the circuit's state and recomputes outputs on a given cycle.
        STATE refers to the value of state wires on the previous cycle.

        Subclasses should update the NEXT_STATE and OUTPUTS dicts as appropriate.
        CL blocks should have empty state dicts, and update outputs based on inputs.
        """
        raise NotImplementedError()

    def get_initial_state(self) -> WireBundle:
        return WireBundle(0)

    def dump(self, path, sim_cycles, input_values: Dict[int, Dict[str, BitVector]], read_outputs: Dict[int, Set[str]]):
        """
        Simulates the circuit for SIM_CYCLES, and writes the result to a VCD at PATH.

        INPUT_VALUES maps cycles to a map of wires to values.
        READ_OUTPUTS maps cycles to the list of values read on every cycle, which forms
        the root set.
        """
        assert sim_cycles > 0, "Must simulate for at least 1 cycle"
        with open(path, "w") as f:
            with vcd.VCDWriter(f, timescale="1 ns", date="today") as writer:
                clk = writer.register_var("module", "clk", "time", size=1)
                vcd_var_dict = {} # holds stuff to write to vcd
                # Must be root list rather than set since ConcreteWire isn't hashable
                roots: List[ConcreteWire] = []
                curr_state = self.get_initial_state().freeze()
                # Initialize dict of vcd variables
                def vcd_register(wire):
                    vcd_var_dict[wire.name] = writer.register_var("module", wire.name, "integer", size=wire.bv.width)
                for wire in curr_state.values():
                    vcd_register(wire)
                # Run no-op simulation of cycle 0 to get all inputs and outputs registered
                vcd_inputs_0 = WireBundle(0)
                for name, value in input_values[0].items():
                    vcd_inputs_0[name] = (value, [])
                for wire in vcd_inputs_0.values():
                    vcd_register(wire)
                vcd_outputs_0 = WireBundle(0)
                self.at_posedge_clk(curr_state, vcd_inputs_0, WireBundle(0), vcd_outputs_0)
                for wire in vcd_outputs_0.values():
                    vcd_register(wire)
                # Run actual simulation
                for i in range(sim_cycles):
                    curr_inputs = WireBundle(i)
                    for name, value in input_values[i].items():
                        curr_inputs[name] = (value, [])
                    curr_inputs.freeze()
                    next_state = WireBundle(i + 1)
                    curr_outputs = WireBundle(i)
                    # Update VCD values for the last cycle and stores it in the dict of all wires
                    def update_wire(i, wire):
                        assert i == wire.cycle, f"Wire {wire} was updated on cycle {i}"
                        var = vcd_var_dict[wire.name]
                        writer.change(var, i * CYCLE_LEN_NS, wire.bv.value)
                    for wire in curr_inputs.values():
                        update_wire(i, wire)
                    for wire in curr_state.values():
                        update_wire(i, wire)
                    # Tick clock
                    self.at_posedge_clk(curr_state, curr_inputs, next_state, curr_outputs)
                    curr_state = next_state.freeze()
                    # Update root set if necessary
                    if i in read_outputs:
                        for wire_name in read_outputs[i]:
                            wire = curr_outputs[wire_name]
                            wire.usage = WireUsage.OUTPUT
                            roots.append(wire)
                    # Write outputs to VCD
                    for wire in curr_outputs.values():
                        update_wire(i, wire)
                    writer.change(clk, i * CYCLE_LEN_NS, 1) # posedge
                    writer.change(clk, i * CYCLE_LEN_NS + CYCLE_LEN_NS // 2, 0) # negedge
        # Root set was populated during simulation - now, we mark and sweep
        # print(f"Roots: {roots}")
        marked = roots[:]
        stack = roots[:]
        while len(stack) != 0:
            wire = stack.pop()
            for in_wire in wire.srcs:
                if in_wire.usage != WireUsage.UNUSED and in_wire not in marked:
                    marked.append(in_wire)
                    stack.append(in_wire)
        print(marked)


# === Simple CL Gates ===
class AndGate1B(Circuit):
    def at_posedge_clk(self, curr_state, inputs, next_state, outputs):
        outputs["q"] = inputs["a"] & inputs["b"]

# === Circuit Implementations ===
class XorFeedback(Circuit):
    def get_initial_state(self):
        w = WireBundle(0)
        w["m"] = (BitVector(0, 1), [])
        return w

    def at_posedge_clk(self, curr_state, inputs, next_state, outputs):
        next_state["m"] = inputs["a"] ^ curr_state["m"]
        outputs["q"] = curr_state["m"]

def BV1(value):
    return BitVector(value, 1)

if __name__ == '__main__':
    circ1 = AndGate1B()
    circ1.dump("and1b.vcd", 4, {
        0: {"a": BV1(0), "b": BV1(0)},
        1: {"a": BV1(0), "b": BV1(1)},
        2: {"a": BV1(1), "b": BV1(0)},
        3: {"a": BV1(1), "b": BV1(1)},
    }, {
        3: {"q"}
    })

    # circ2 = XorFeedback()
    # circ2.dump("xor_fb.vcd", 4, {
    #     0: {"a": BV1(1)},
    #     1: {"a": BV1(1)},
    #     2: {"a": BV1(1)},
    #     3: {"a": BV1(1)},
    # }, {})
