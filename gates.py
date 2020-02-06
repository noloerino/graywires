from dataclasses import dataclass
from typing import Dict, List


@dataclass
class BitField:
    width: int
    value: int

    def __post_init__(self):
        self.value = ((0xffffffff + (1 << self.width)) & 0xffffffff) & self.value


@dataclass(frozen=True)
class Wire:
    name: str
    width: int

def W1(name: str):
    return Wire(name, 1)


class Block:
    """
    Represents a circuit block of some kind. Inputs and outputs are specified by subclasses implementing
    the expected_inputs field, expected_outputs field, and _compute_output method.
    """

    expected_inputs: List[Wire]
    expected_outputs: List[Wire]

    def __init__(self, inputs: Dict[Wire, BitField]):
        """
        Takes in a dict mapping wire names to values.
        """
        self.validate_inputs(inputs)
        self.inputs = inputs

    def validate_inputs(self, inputs: Dict[Wire, BitField]):
        """
        Ensures that all required inputs are provided and of expected width, no extra inputs are provided.
        """
        error_message = None
        width_dict = {wire.name: wire.width for wire in self.expected_inputs}
        in_width_dict = {wire.name: wire.width for wire in inputs}
        # Check extra wires
        unexpected = width_dict.keys() ^ in_width_dict.keys()
        if unexpected:
            error_message += f"Unexpected input wire(s): {unexpected}\n"
        # Check presence of all wires
        missing = width_dict.keys() - in_width_dict.keys()
        if missing:
            error_message += f"Missing input wire(s): {missing}\n"
        common = width_dict.keys() & in_width_dict.keys()
        wrong_widths = {wire_name for wire_name in common if width_dict[wire_name] != in_width_dict[wire_name]}
        if wrong_widths:
            error_message += f"Input wire(s) with wrong width: {wrong_widths}\n"
        if error_message is not None:
            raise Exception(error_message[:-1])

    def _compute_output_value(self, inputs: Dict[Wire, BitField], out: Wire) -> BitField:
        """
        Computes the value of wire OUT with the specified inputs.
        """
        raise Exception(f"No method described for computing output wire: {out}")

    def compute_outputs(self) -> Dict[Wire, BitField]:
        """
        Returns a dict mapping output names to values.
        """
        return {
            out_wire: self._compute_output_value(self.inputs, out_wire)
            for out_wire in self.expected_outputs
        }


class AndGate1B(Block):
    expected_inputs = [Wire("a", 1), Wire("b", 1)]
    expected_outputs = [Wire("c", 1)]

    def _compute_output_value(self, inputs: Dict[Wire, BitField], out: Wire) -> BitField:
        if out.name == "c":
            return BitField(out.width, inputs[W1("a")].value & inputs[W1("b")].value)
        return super()._compute_output_value(inputs, out)

class OrGate1B(Block):
    expected_inputs = [Wire("a", 1), Wire("b", 1)]
    expected_outputs = [Wire("c", 1)]

    def _compute_output_value(self, inputs: Dict[Wire, BitField], out: Wire) -> BitField:
        if out.name == "c":
            return BitField(out.width, inputs[W1("a")].value | inputs[W1("b")].value)
        return super()._compute_output_value(inputs, out)


class XorGate1B(Block):
    expected_inputs = [Wire("a", 1), Wire("b", 1)]
    expected_outputs = [Wire("c", 1)]

    def _compute_output_value(self, inputs: Dict[Wire, BitField], out: Wire) -> BitField:
        if out.name == "c":
            return BitField(out.width, inputs[W1("a")].value ^ inputs[W1("b")].value)
        return super()._compute_output_value(inputs, out)


class NandGate1B(Block):
    expected_inputs = [Wire("a", 1), Wire("b", 1)]
    expected_outputs = [Wire("c", 1)]

    def _compute_output_value(self, inputs: Dict[Wire, BitField], out: Wire) -> BitField:
        if out.name == "c":
            return BitField(out.width, ~(inputs[W1("a")].value & inputs[W1("b")].value))
        return super()._compute_output_value(inputs, out)
