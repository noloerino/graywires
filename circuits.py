
import collections.abc
from dataclasses import dataclass
from enum import Enum
from typing import Dict, Set
import vcd # type: ignore

@dataclass(frozen=True)
class BitVector:
    value: int
    width: int

    def __getattr__(self, name: str):
        if name == "value":
            return ((0xffffffff + (1 << self.width)) & 0xffffffff) & self.value
        raise AttributeError()


class WireUsage(Enum):
    UNUSED = 0
    USED = 1
    OUTPUT = 2


@dataclass(frozen=True)
class ConcreteWire:
    """
    The concrete value of a named wire on a given cycle.

    Overriding operators allows us to perform analyses and create metadata on these objects.
    """
    name: str
    bv: BitVector
    cycle: int
    usage: WireUsage = WireUsage.UNUSED

    def __and__(self, o) -> BitVector:
        # TODO add usage checks
        return BitVector(self.bv.value & o.bv.value, min(self.bv.width, o.bv.width))

    def __xor__(self, o) -> BitVector:
        return BitVector(self.bv.value ^ o.bv.value, min(self.bv.width, o.bv.width))


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

    def __setitem__(self, key: str, value: BitVector):
        if self.frozen:
            raise KeyError("Cannot write to a frozen WireBundle")
        self.wires[key] = ConcreteWire(key, value, self.cycle)

    def __delitem__(self, key: str):
        del self.wires[key]

    def __iter__(self):
        return iter(self.wires)

    def __len__(self):
        return len(self.wires)

    def freeze(self):
        """
        Prevents modifications from being made to the WireBundle, e.g. once computation of a state
        has been completed.
        """
        self.frozen = True


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
                vcd_var_dict = {}
                curr_state = self.get_initial_state()
                curr_state.freeze()
                # Initialize dict of vcd variables
                def vcd_register(wire):
                    vcd_var_dict[wire.name] = writer.register_var("module", wire.name, "integer", size=wire.bv.width)
                for wire in curr_state.values():
                    vcd_register(wire)
                # Run no-op simulation of cycle 0 to get all inputs and outputs registered
                vcd_inputs_0 = WireBundle(0)
                for name, value in input_values[0].items():
                    vcd_inputs_0[name] = value
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
                        curr_inputs[name] = value
                    curr_inputs.freeze()
                    next_state = WireBundle(i)
                    curr_outputs = WireBundle(i)
                    # Update VCD values for the last cycle
                    def update_wire(i, wire):
                        assert i == wire.cycle
                        var = vcd_var_dict[wire.name]
                        print(f"{wire}@{i}={wire.bv.value}")
                        writer.change(var, i * CYCLE_LEN_NS, wire.bv.value)
                    for wire in curr_inputs.values():
                        update_wire(i, wire)
                    for wire in curr_state.values():
                        update_wire(i, wire)
                    for wire in curr_outputs.values():
                        update_wire(i, wire)
                    writer.change(clk, i * CYCLE_LEN_NS, 1) # posedge
                    writer.change(clk, i * CYCLE_LEN_NS + CYCLE_LEN_NS // 2, 0) # negedge
                    # Tick clock
                    self.at_posedge_clk(curr_state, curr_inputs, next_state, curr_outputs)
                    curr_state = next_state
                    curr_state.freeze()
        # TODO just need to perform mark and sweep here, with READ_OUTPUTS as root set


# === Simple CL Gates ===
class AndGate1B(Circuit):
    def at_posedge_clk(self, curr_state, inputs, next_state, outputs):
        outputs["q"] = inputs["a"] & inputs["b"]

# === Circuit Implementations ===
class XorFeedback(Circuit):
    def get_initial_state(self):
        w = WireBundle(0)
        w["m"] = BitVector(0, 1)
        return w

    def at_posedge_clk(self, curr_state, inputs, next_state, outputs):
        next_state["m"] = inputs["a"] ^ curr_state["m"]
        outputs["q"] = curr_state["m"].bv

def BV1(value):
    return BitVector(value, 1)

if __name__ == '__main__':
    circ1 = AndGate1B()
    circ1.dump("and1b.vcd", 4, {
        0: {"a": BV1(0), "b": BV1(0)},
        1: {"a": BV1(0), "b": BV1(1)},
        2: {"a": BV1(1), "b": BV1(0)},
        3: {"a": BV1(1), "b": BV1(1)},
    }, {})

    circ2 = XorFeedback()
    circ2.dump("xor_fb.vcd", 4, {
        0: {"a": BV1(1)},
        1: {"a": BV1(1)},
        2: {"a": BV1(1)},
        3: {"a": BV1(1)},
    }, {})
