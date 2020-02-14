
import collections.abc
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Set, Tuple, Union
import vcd # type: ignore

@dataclass(frozen=True)
class BitVector:
    value: int
    width: int

def BV1(value):
    return BitVector(value, 1)

GraphNode = Tuple[BitVector, List["ConcreteWire"]]

@dataclass
class ConcreteWire:
    """
    The concrete value of a named wire on a given cycle.

    Overriding operators allows us to perform analyses and create metadata on these objects.
    """
    name: str
    bv: BitVector
    cycle: int
    # Represents the wires that are used to compute this wire
    # This also gives us muxes for free using ternaries, with the one caveat that the select bit
    # cannot be checked.
    srcs: List["ConcreteWire"] = field(default_factory=list)

    def __and__(self, o) -> GraphNode:
        bv = BitVector(self.bv.value & o.bv.value, min(self.bv.width, o.bv.width))
        if self.bv.value == 1 and o.bv.value == 1:
            return (bv, [self, o])
        elif self.bv.value == 1 and o.bv.value == 0:
            return (bv, [o])
        elif self.bv.value == 0 and o.bv.value == 1:
            return (bv, [self])
        else:
            return (bv, [self, o])

    def __or__(self, o) -> GraphNode:
        bv = BitVector(self.bv.value | o.bv.value, min(self.bv.width, o.bv.width))
        if self.bv.value == 0 and o.bv.value == 0:
            return (bv, [self, o])
        elif self.bv.value == 0 and o.bv.value == 1:
            return (bv, [o])
        elif self.bv.value == 1 and o.bv.value == 0:
            return (bv, [self])
        else:
            return (bv, [self, o])

    def __xor__(self, o) -> GraphNode:
        return (
            BitVector(self.bv.value ^ o.bv.value, min(self.bv.width, o.bv.width)),
            [self, o]
        )

    def __lt__(self, o) -> GraphNode:
        return (BV1(self.bv.value < o.bv.value), [self, o])

    def __le__(self, o) -> GraphNode:
        return (BV1(self.bv.value <= o.bv.value), [self, o])

    def __eq__(self, o) -> GraphNode:
        return (BV1(self.bv.value == o.bv.value), [self, o])

    def __ne__(self, o) -> GraphNode:
        return (BV1(self.bv.value != o.bv.value), [self, o])

    def __ge__(self, o) -> GraphNode:
        return (BV1(self.bv.value >= o.bv.value), [self, o])

    def __gt__(self, o) -> GraphNode:
        return (BV1(self.bv.value > o.bv.value), [self, o])

    def __add__(self, o) -> GraphNode:
        return (BitVector(self.bv.value + o.bv.value, max(self.bv.width, o.bv.width)), [self, o])

    def __inv__(self) -> GraphNode:
        return (BitVector(~self.bv.value, self.bv.width), [self])

    def mux(self, on_zero: "ConcreteWire", *args: "ConcreteWire") -> GraphNode:
        """
        Computes the result of a mux, where self is the select port and the values are given
        in order (i.e. the 0 value is on_zero, 1 is the first of args).
        """
        used_list = [] if all([on_zero.bv == w.bv for w in args]) else [self]
        if self.bv.value != 0:
            return (on_zero.bv, used_list + [on_zero])
        else:
            idx = self.bv.value - 1
            assert idx < len(args), f"Mux attempted to access {idx + 1}th value out of {len(args) + 1} inputs"
            wire = args[idx]
            return (wire.bv, used_list + [wire])

    def __repr__(self) -> str:
        return f"ConcreteWire(name={self.name}, bv={self.bv}, cycle={self.cycle})"


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

    def initial_state_values(self) -> Dict[str, BitVector]:
        return {}

    def _get_initial_state(self) -> WireBundle:
        w = WireBundle(0)
        for name, bv in self.initial_state_values().items():
            w[name] = (bv, [])
        return w

    def _vcd_init_vars(self, writer, input_values): # (Dict[str, vcd variable], clk)
        clk = writer.register_var("module", "clk", "time", size=1)
        vcd_var_dict = {} # holds stuff to write to vcd
        # Initialize dict of vcd variables
        def vcd_register(wire):
            vcd_var_dict[wire.name] = writer.register_var("module", wire.name, "integer", size=wire.bv.width)
        vcd_state_0 = self._get_initial_state().freeze()
        for wire in vcd_state_0.values():
            vcd_register(wire)
        # Run no-op simulation of cycle 0 to get all inputs and outputs registered
        vcd_inputs_0 = WireBundle(0)
        for name, value in input_values[0].items():
            vcd_inputs_0[name] = (value, [])
        for wire in vcd_inputs_0.values():
            vcd_register(wire)
        vcd_outputs_0 = WireBundle(0)
        self.at_posedge_clk(vcd_state_0, vcd_inputs_0, WireBundle(0), vcd_outputs_0)
        for wire in vcd_outputs_0.values():
            vcd_register(wire)
        return vcd_var_dict, clk

    def _simulate_raw(
        self,
        writer,
        sim_cycles,
        input_values: Dict[int, Dict[str, BitVector]],
        read_outputs: Dict[int, Set[str]]
        ) -> List[ConcreteWire]:
        """
        Simulates the circuit for SIM_CYCLES and writes a VCD of the run.

        INPUT_VALUES maps cycles to a map of wires to values.
        READ_OUTPUTS maps cycles to the list of values read on every cycle, which forms

        Returns the concrete wires in the root set.
        """
        # Must be root list rather than set since ConcreteWire isn't hashable
        roots: List[ConcreteWire] = []
        vcd_var_dict, clk = self._vcd_init_vars(writer, input_values)
        curr_state = self._get_initial_state().freeze()
        
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
                    roots.append(wire)
            # Write outputs to VCD
            for wire in curr_outputs.values():
                update_wire(i, wire)
            writer.change(clk, i * CYCLE_LEN_NS, 1) # posedge
            writer.change(clk, i * CYCLE_LEN_NS + CYCLE_LEN_NS // 2, 0) # negedge
        writer.change(clk, (i + 1) * CYCLE_LEN_NS, 1)
        return roots


    def _simulate_with_usage(
        self,
        writer,
        sim_cycles,
        input_values: Dict[int, Dict[str, BitVector]],
        used_wires: List[ConcreteWire]
        ):
        """
        Simulates the circuit and writes a VCD, this time Xing out any wire that's not used.

        USED_WIRES comes from the mark and sweep phas.
        """
        vcd_var_dict, clk = self._vcd_init_vars(writer, input_values)
        curr_state = self._get_initial_state().freeze()

        used_lookup_list = [(wire.name, wire.cycle) for wire in used_wires]
        
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
                value = wire.bv.value
                if (wire.name, wire.cycle) not in used_lookup_list:
                    # print(f"{wire} was not in used")
                    value = "x"
                writer.change(var, i * CYCLE_LEN_NS, value)
            for wire in curr_inputs.values():
                update_wire(i, wire)
            for wire in curr_state.values():
                update_wire(i, wire)
            # Tick clock
            self.at_posedge_clk(curr_state, curr_inputs, next_state, curr_outputs)
            curr_state = next_state.freeze()
            # Write outputs to VCD
            for wire in curr_outputs.values():
                update_wire(i, wire)
            writer.change(clk, i * CYCLE_LEN_NS, 1) # posedge
            writer.change(clk, i * CYCLE_LEN_NS + CYCLE_LEN_NS // 2, 0) # negedge
        # Tick one more posedge
        writer.change(clk, (i + 1) * CYCLE_LEN_NS, 1)


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
                roots = self._simulate_raw(writer, sim_cycles, input_values, read_outputs)
                # Root set was populated during simulation - now, we mark and sweep
                # print(f"Roots: {roots}")
                marked = roots[:]
                stack = roots[:]
                while len(stack) != 0:
                    wire = stack.pop()
                    for in_wire in wire.srcs:
                        if in_wire not in marked:
                            marked.append(in_wire)
                            stack.append(in_wire)
                with open(f"usage_{path}", "w") as f:
                    with vcd.VCDWriter(f, timescale="1 ns", date="today") as writer:
                        self._simulate_with_usage(writer, sim_cycles, input_values, marked)
                return marked
        raise ValueError("Unreachable code")


# === Simple CL Gates ===
class AndGate1B(Circuit):
    def at_posedge_clk(self, curr_state, inputs, next_state, outputs):
        outputs["q"] = inputs["a"] & inputs["b"]

# === Circuit Implementations ===
class XorFeedback(Circuit):
    def initial_state_values(self) -> Dict[str, BitVector]:
        return {"m": BV1(0)}

    def at_posedge_clk(self, curr_state, inputs, next_state, outputs):
        next_state["m"] = inputs["a"] ^ curr_state["m"]
        outputs["q"] = curr_state["m"]

class AndFeedback(Circuit):
    def initial_state_values(self) -> Dict[str, BitVector]:
        return {"m": BV1(0)}

    def at_posedge_clk(self, curr_state, inputs, next_state, outputs):
        outputs["q"] = inputs["sel"].mux(inputs["a"], curr_state["m"])
        next_state["m"] = inputs["a"] & outputs["q"]

class SmallRegfile(Circuit):
    """
    Implementation of a 4-element 1-bit register file. It has one address port
    and one r/w port.
    """

    def initial_state_values(self) -> Dict[str, BitVector]:
        return {
            "r0": BV1(0),
            "r1": BV1(0),
            "r2": BV1(0),
            "r3": BV1(0),
        }

    def at_posedge_clk(self, curr_state, inputs, next_state, outputs):
        pass

if __name__ == '__main__':
    # circ1 = AndGate1B()
    # circ1.dump("and1b.vcd", 4, {
    #     0: {"a": BV1(0), "b": BV1(0)},
    #     1: {"a": BV1(0), "b": BV1(1)},
    #     2: {"a": BV1(1), "b": BV1(0)},
    #     3: {"a": BV1(1), "b": BV1(1)},
    # }, {
    #     0: {"q"},
    #     1: {"q"},
    #     2: {"q"},
    #     3: {"q"},
    # })

    # circ2 = XorFeedback()
    # circ2.dump("xor_fb.vcd", 4, {
    #     0: {"a": BV1(1)},
    #     1: {"a": BV1(1)},
    #     2: {"a": BV1(1)},
    #     3: {"a": BV1(1)},
    # }, {
    #     3: {"q"},
    # })

    circ3 = AndFeedback()
    circ3.dump("and_fb.vcd", 6, {
        0: {"a": BV1(1), "sel": BV1(1)},
        1: {"a": BV1(1), "sel": BV1(0)},
        2: {"a": BV1(1), "sel": BV1(1)},
        3: {"a": BV1(1), "sel": BV1(1)},
        4: {"a": BV1(1), "sel": BV1(1)},
        5: {"a": BV1(0), "sel": BV1(1)},
    }, {
        5: {"q"},
    })
