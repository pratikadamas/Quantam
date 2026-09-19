"""
qasm3.py — Pure-Python OpenQASM 3 emitter.

Converts a QuantumCircuit to a valid OpenQASM 3.0 string.
No Qiskit dependency.

OpenQASM 3 reference: https://openqasm.com/

Optionally, if Qiskit is installed, you can use the Qiskit bridge
(QASM3Backend.to_qasm3_via_qiskit) for validation purposes.
"""
from __future__ import annotations

import math
from typing import Dict, List, Optional

from qcompiler.core.circuit import QuantumCircuit
from qcompiler.core.instruction import CircuitInstruction

# ---------------------------------------------------------------------------
# Gate name → QASM3 built-in name mapping
# ---------------------------------------------------------------------------
_QASM3_GATE_NAMES: Dict[str, str] = {
    "id":    "id",
    "x":     "x",
    "y":     "y",
    "z":     "z",
    "h":     "h",
    "s":     "s",
    "sdg":   "sdg",
    "t":     "t",
    "tdg":   "tdg",
    "sx":    "sx",
    "rx":    "rx",
    "ry":    "ry",
    "rz":    "rz",
    "p":     "p",
    "u1":    "U",   # U(0,0,λ) in QASM3
    "u2":    "U",
    "u3":    "U",
    "cx":    "cx",
    "cy":    "cy",
    "cz":    "cz",
    "swap":  "swap",
    "cp":    "cp",
    "crz":   "crz",
    "ccx":   "ccx",
    "cswap": "cswap",
}

_STDLIB_INCLUDE = 'include "stdgates.inc";'


def _fmt_angle(a: float) -> str:
    """Format a float angle for QASM output (use π notation where possible)."""
    pi = math.pi
    # Common multiples of π
    for num in range(1, 9):
        for den in range(1, 9):
            if math.isclose(a, num * pi / den, rel_tol=1e-9):
                return f"{num}*pi/{den}" if den != 1 else f"{num}*pi"
            if math.isclose(a, -num * pi / den, rel_tol=1e-9):
                return f"-{num}*pi/{den}" if den != 1 else f"-{num}*pi"
    if math.isclose(a, 0.0, abs_tol=1e-12):
        return "0"
    return f"{a:.10g}"


class QASM3Backend:
    """Emit OpenQASM 3 from a QuantumCircuit.

    Parameters
    ----------
    use_qiskit_bridge : bool
        If True *and* Qiskit is installed, delegate to Qiskit's QASM3
        serialiser for better compatibility. Falls back to pure-Python
        emitter if Qiskit is not available.

    Examples
    --------
    >>> backend = QASM3Backend()
    >>> qasm_str = backend.dumps(circuit)
    >>> print(qasm_str)
    """

    def __init__(self, use_qiskit_bridge: bool = False) -> None:
        self._use_qiskit = use_qiskit_bridge

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def dumps(self, circuit: QuantumCircuit) -> str:
        """Serialise *circuit* to an OpenQASM 3 string."""
        if self._use_qiskit:
            try:
                return self._qiskit_dumps(circuit)
            except ImportError:
                pass  # fall through to pure-Python emitter
        return self._pure_python_dumps(circuit)

    def dump(self, circuit: QuantumCircuit, path: str) -> None:
        """Write OpenQASM 3 to *path*."""
        with open(path, "w", encoding="utf-8") as f:
            f.write(self.dumps(circuit))

    # ------------------------------------------------------------------
    # Pure-Python emitter
    # ------------------------------------------------------------------

    def _pure_python_dumps(self, circuit: QuantumCircuit) -> str:
        lines: List[str] = []

        # Header
        lines.append("OPENQASM 3.0;")
        lines.append(_STDLIB_INCLUDE)
        lines.append("")

        # Quantum register(s)
        lines.append(f"qubit[{circuit.num_qubits}] q;")

        # Classical register(s)
        if circuit.num_clbits > 0:
            lines.append(f"bit[{circuit.num_clbits}] c;")

        lines.append("")

        # Instructions
        for instr in circuit.data:
            line = self._emit_instruction(instr)
            if line:
                lines.append(line)

        return "\n".join(lines) + "\n"

    def _emit_instruction(self, instr: CircuitInstruction) -> Optional[str]:
        gate = instr.gate

        # Barrier
        if gate.is_barrier:
            qbs = ", ".join(f"q[{q.index}]" for q in instr.qubits)
            return f"barrier {qbs};"

        # Measure
        if gate.name == "measure":
            q = instr.qubits[0]
            c = instr.clbits[0]
            return f"c[{c.index}] = measure q[{q.index}];"

        # Gate name
        qasm_name = _QASM3_GATE_NAMES.get(gate.name, gate.name)

        # Special U-gate handling (u1/u2/u3 → U(θ,φ,λ))
        if gate.name == "u3":
            theta, phi, lam = gate.params
            params_str = f"({_fmt_angle(theta)}, {_fmt_angle(phi)}, {_fmt_angle(lam)})"
        elif gate.name == "u2":
            phi, lam = gate.params
            params_str = f"(pi/2, {_fmt_angle(phi)}, {_fmt_angle(lam)})"
        elif gate.name == "u1":
            lam = gate.params[0]
            params_str = f"(0, 0, {_fmt_angle(lam)})"
        elif gate.params:
            args = ", ".join(_fmt_angle(p) for p in gate.params)
            params_str = f"({args})"
        else:
            params_str = ""

        # Qubit targets
        qbs = ", ".join(f"q[{q.index}]" for q in instr.qubits)

        return f"{qasm_name}{params_str} {qbs};"

    # ------------------------------------------------------------------
    # Qiskit bridge (optional)
    # ------------------------------------------------------------------

    def _qiskit_dumps(self, circuit: QuantumCircuit) -> str:
        """Convert via Qiskit: our QuantumCircuit → Qiskit circuit → QASM3."""
        from qiskit import QuantumCircuit as QkCircuit
        from qiskit import QuantumRegister, ClassicalRegister
        from qiskit.qasm3 import dumps as qk_dumps

        qr = QuantumRegister(circuit.num_qubits, "q")
        cr = ClassicalRegister(circuit.num_clbits, "c") if circuit.num_clbits else None
        qk_args = [qr, cr] if cr else [qr]
        qk_circ = QkCircuit(*qk_args, name=circuit.name)

        _qk_gate_map = {
            "id": "id", "x": "x", "y": "y", "z": "z",
            "h": "h", "s": "s", "sdg": "sdg", "t": "t", "tdg": "tdg",
            "sx": "sx", "rx": "rx", "ry": "ry", "rz": "rz",
            "cx": "cx", "cy": "cy", "cz": "cz", "swap": "swap",
            "cp": "cp", "crz": "crz", "ccx": "ccx", "cswap": "cswap",
            "p": "p", "u1": "u", "u2": "u", "u3": "u",
        }

        for instr in circuit.data:
            gname = instr.gate.name
            qidxs = [q.index for q in instr.qubits]
            cidxs = [c.index for c in instr.clbits]
            qk_qubits = [qr[i] for i in qidxs]

            if gname == "measure":
                qk_circ.measure(qk_qubits[0], cr[cidxs[0]])
            elif gname == "barrier":
                qk_circ.barrier(*qk_qubits)
            else:
                method = getattr(qk_circ, _qk_gate_map.get(gname, gname), None)
                if method:
                    method(*instr.gate.params, *qk_qubits)
                else:
                    qk_circ.append(
                        __import__("qiskit.circuit").circuit.library.standard_gates.__dict__.get(
                            gname.upper() + "Gate", None
                        )(*instr.gate.params),
                        qk_qubits,
                    )

        return qk_dumps(qk_circ)
