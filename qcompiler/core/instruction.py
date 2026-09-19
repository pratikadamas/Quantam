"""
instruction.py — CircuitInstruction: a gate applied to specific qubits/bits.

A CircuitInstruction is the atomic element stored in a QuantumCircuit.
It binds a Gate to a concrete list of Qubits (and optionally Clbits for
measure/reset operations).
"""
from __future__ import annotations

from typing import List, Optional, Tuple

from qcompiler.core.gate import Gate
from qcompiler.core.qubit import Qubit, Clbit


class CircuitInstruction:
    """A Gate bound to specific qubit (and clbit) targets.

    Parameters
    ----------
    gate : Gate
        The quantum gate to apply.
    qubits : sequence of Qubit
        Qubit targets, in the gate's qubit order.
    clbits : sequence of Clbit, optional
        Classical bit targets (used for Measure / Reset).

    Examples
    --------
    >>> from qcompiler.core.gate import StandardGate
    >>> from qcompiler.core.qubit import Qubit
    >>> h = StandardGate.h()
    >>> instr = CircuitInstruction(h, [Qubit("q", 0)])
    """

    __slots__ = ("gate", "qubits", "clbits")

    def __init__(
        self,
        gate: Gate,
        qubits: List[Qubit],
        clbits: Optional[List[Clbit]] = None,
    ) -> None:
        if len(qubits) != gate.num_qubits and not gate.is_barrier:
            raise ValueError(
                f"Gate '{gate.name}' requires {gate.num_qubits} qubit(s), "
                f"but {len(qubits)} provided."
            )
        self.gate = gate
        self.qubits: Tuple[Qubit, ...] = tuple(qubits)
        self.clbits: Tuple[Clbit, ...] = tuple(clbits) if clbits else ()

    def replace_gate(self, new_gate: Gate) -> "CircuitInstruction":
        """Return a new instruction with the same qubits but a different gate."""
        return CircuitInstruction(new_gate, list(self.qubits), list(self.clbits))

    def __repr__(self) -> str:
        qbs = ", ".join(str(q) for q in self.qubits)
        cbs = (", " + ", ".join(str(c) for c in self.clbits)) if self.clbits else ""
        return f"CircuitInstruction({self.gate!r}, [{qbs}]{cbs})"

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, CircuitInstruction):
            return NotImplemented
        return (
            self.gate.name == other.gate.name
            and self.gate.params == other.gate.params
            and self.qubits == other.qubits
            and self.clbits == other.clbits
        )
