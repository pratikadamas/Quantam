"""Circuit folding for noise amplification in ZNE.

Implements global and local unitary folding:
  U → U · U† · U   (one fold, scale_factor ≈ 3)

Partial folds are supported for non-integer scale factors.
"""

from __future__ import annotations
import math

# pyrefly: ignore [missing-import]
from qiskit import QuantumCircuit


def fold_global(circuit: QuantumCircuit, scale_factor: float) -> QuantumCircuit:
    """Apply global unitary folding to amplify noise.

    For scale_factor = 1, returns the original circuit.
    For scale_factor = 3, returns U · U† · U.
    Non-integer factors are handled via partial folding of individual gates.

    Args:
        circuit: The original quantum circuit.
        scale_factor: Noise amplification factor (>= 1).

    Returns:
        A new QuantumCircuit with folded gates.
    """
    if scale_factor < 1:
        raise ValueError("scale_factor must be >= 1")

    if abs(scale_factor - 1.0) < 1e-9:
        return circuit.copy()

    # Number of complete fold rounds: each round adds U† · U (factor increases by 2)
    num_full_folds = int((scale_factor - 1) // 2)
    remainder = scale_factor - 1 - 2 * num_full_folds

    folded = QuantumCircuit(circuit.num_qubits, circuit.num_clbits)
    folded.metadata = {'scale_factor': scale_factor, 'folding': 'global'}

    # Original circuit
    folded.compose(circuit, inplace=True)

    # Full fold rounds: append U† · U for each round
    for _ in range(num_full_folds):
        folded.compose(circuit.inverse(), inplace=True)
        folded.compose(circuit, inplace=True)

    # Partial fold: fold a fraction of the gates
    if remainder > 1e-9:
        num_gates_to_fold = max(1, int(round(remainder / 2 * len(circuit.data))))
        partial_circuit = QuantumCircuit(circuit.num_qubits, circuit.num_clbits)

        for gate_data in circuit.data[-num_gates_to_fold:]:
            partial_circuit.append(gate_data)

        folded.compose(partial_circuit.inverse(), inplace=True)
        folded.compose(partial_circuit, inplace=True)

    return folded


def fold_local(circuit: QuantumCircuit, scale_factor: float) -> QuantumCircuit:
    """Apply local (per-gate) folding to amplify noise.

    Each gate G is replaced with G · G† · G (one fold).
    For scale_factor = 1, the circuit is unchanged.
    Gates are folded uniformly until the target scale factor is reached.

    Args:
        circuit: The original quantum circuit.
        scale_factor: Noise amplification factor (>= 1).

    Returns:
        A new QuantumCircuit with locally folded gates.
    """
    if scale_factor < 1:
        raise ValueError("scale_factor must be >= 1")

    if abs(scale_factor - 1.0) < 1e-9:
        return circuit.copy()

    total_gates = len(circuit.data)
    if total_gates == 0:
        return circuit.copy()

    # Each folded gate triples its contribution to depth.
    # Target total gate-depth: scale_factor * total_gates
    target_total = scale_factor * total_gates
    # Each fold of one gate adds 2 extra gates
    num_gates_to_fold = int(round((target_total - total_gates) / 2))
    num_gates_to_fold = min(num_gates_to_fold, total_gates)

    # Number of complete passes over all gates
    full_passes = num_gates_to_fold // total_gates
    extra_gates = num_gates_to_fold % total_gates

    folded = QuantumCircuit(circuit.num_qubits, circuit.num_clbits)
    folded.metadata = {'scale_factor': scale_factor, 'folding': 'local'}

    for idx, gate_data in enumerate(circuit.data):
        # Append the original gate
        folded.append(gate_data)

        # Determine how many folds for this gate
        folds = full_passes
        if idx < extra_gates:
            folds += 1

        for _ in range(folds):
            # Create a tiny circuit for this single gate to invert it
            single = QuantumCircuit(circuit.num_qubits, circuit.num_clbits)
            single.append(gate_data)
            inv = single.inverse()
            # Append G† then G
            for inv_gate in inv.data:
                folded.append(inv_gate)
            folded.append(gate_data)

    return folded
