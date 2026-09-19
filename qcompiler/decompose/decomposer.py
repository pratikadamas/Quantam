"""
decomposer.py — Recursive gate decomposer.

GateDecomposer walks a QuantumCircuit and recursively replaces every
non-basis gate with its decomposition from the rule table until only
basis gates remain.

The decomposer does NOT modify the input circuit; it returns a new one.
"""
from __future__ import annotations

from typing import List

from qcompiler.core.circuit import QuantumCircuit
from qcompiler.core.gate import StandardGate
from qcompiler.core.instruction import CircuitInstruction
from qcompiler.core.qubit import Qubit
from qcompiler.decompose.rules import BASIS_GATES, DECOMPOSITION_RULES


_MAX_DEPTH = 20  # recursion safety cap


class GateDecomposer:
    """Decompose all non-basis gates in a circuit down to the basis gate set.

    Parameters
    ----------
    basis_gates : frozenset of str, optional
        Override the default basis gate set. Gates whose names are in this
        set are left unchanged.

    Examples
    --------
    >>> decomposer = GateDecomposer()
    >>> final = decomposer.run(circuit)
    """

    def __init__(self, basis_gates=None) -> None:
        self._basis = basis_gates if basis_gates is not None else BASIS_GATES

    def run(self, circuit: QuantumCircuit) -> QuantumCircuit:
        """Return a new circuit containing only basis gates."""
        out = QuantumCircuit(circuit.num_qubits, circuit.num_clbits, name=circuit.name)

        for instr in circuit.data:
            decomposed = self._decompose_instr(instr, depth=0)
            for d_instr in decomposed:
                out._data.append(d_instr)

        return out

    def _decompose_instr(
        self, instr: CircuitInstruction, depth: int
    ) -> List[CircuitInstruction]:
        gate = instr.gate

        # Already in basis
        if gate.name in self._basis:
            return [instr]

        if depth >= _MAX_DEPTH:
            # Give up — pass through opaque
            return [instr]

        rule_fn = DECOMPOSITION_RULES.get(gate.name)
        if rule_fn is None:
            # No rule — pass through as-is
            return [instr]

        sub_ops = rule_fn(gate.params)
        result: List[CircuitInstruction] = []

        for sub_name, sub_params, qubit_indices in sub_ops:
            sub_qubits = [instr.qubits[i] for i in qubit_indices]
            try:
                sub_gate = StandardGate.get(sub_name, sub_params)
            except ValueError:
                # Fallback: treat as opaque (unknown custom gate)
                from qcompiler.core.gate import Gate
                sub_gate = Gate(sub_name, len(sub_qubits), sub_params)

            sub_instr = CircuitInstruction(sub_gate, sub_qubits)
            result.extend(self._decompose_instr(sub_instr, depth + 1))

        return result
