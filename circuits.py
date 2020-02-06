from typing import Dict
from gates import *

def BF1(value):
    return BitField(1, value)

class XorFromNands1B(Block):
    expected_inputs = [Wire("a", 1), Wire("b", 1)]
    expected_outputs = [Wire("c", 1)]

    def _compute_output_value(self, inputs: Dict[Wire, BitField], out: Wire) -> BitField:
        if out.name == "c":
            a, b = inputs[W1("a")], inputs[W1("b")]
            m1 = NandGate1B({W1("a"): a, W1("b"): b}).compute_outputs()[W1("c")]
            m2 = NandGate1B({W1("a"): a, W1("b"): m1}).compute_outputs()[W1("c")]
            m3 = NandGate1B({W1("a"): m1, W1("b"): b}).compute_outputs()[W1("c")]
            return NandGate1B({W1("a"): m2, W1("b"): m3}).compute_outputs()[W1("c")]
        return super()._compute_output_value(inputs, out)

def main():
    for a, b in ([0, 0], [0, 1], [1, 0], [1, 1]):
        print(
            f"a={a}, b={b}:",
            XorFromNands1B({W1("a"): BF1(a), W1("b"): BF1(b)}).compute_outputs()
        )

if __name__ == '__main__':
    main()
