"""
cancel_inverses.py — Cancellation pass for adjacent inverse gate pairs.

For each qubit wire, scans the sequence of OP nodes and removes
consecutive pairs where gate B is the inverse of gate A
(e.g. H·H = I, S·Sdg = I, T·Tdg = I, Rx(θ)·Rx(-θ) = I).

Self-inverse gates (H, X, Y, Z, CX, CZ, SWAP) also cancel when repeated.
"""
from __future__ import annotations

import math
from typing import List

from qcompiler.dag.dag_circuit import DAGCircuit
from qcompiler.dag.dag_node import DAGNode, DAGNodeType
from qcompiler.passes.base_pass import TransformationPass


# Known self-inverse gate names
_SELF_INVERSE = {"h", "x", "y", "z", "cx", "cy", "cz", "swap", "ccx", "id"}

# Known inverse pairs (name → inverse_name)
_INVERSE_PAIRS = {
    "s": "sdg", "sdg": "s",
    "t": "tdg", "tdg": "t",
    "sx": "sxdg", "sxdg": "sx",
}


def _gates_cancel(a: DAGNode, b: DAGNode) -> bool:
    """Return True if op nodes a and b cancel each other on their shared wire."""
    if a.instruction is None or b.instruction is None:
        return False
    ga = a.instruction.gate
    gb = b.instruction.gate

    # Must act on same qubits in same order
    if a.instruction.qubits != b.instruction.qubits:
        return False

    # Self-inverse
    if ga.name in _SELF_INVERSE and ga.name == gb.name:
        return True

    # Known named inverse pairs
    if _INVERSE_PAIRS.get(ga.name) == gb.name:
        return True

    # Parameterised: same gate family, opposite angles
    param_families = {"rx", "ry", "rz", "p", "u1"}
    if ga.name in param_families and ga.name == gb.name:
        if len(ga.params) == 1 and len(gb.params) == 1:
            return math.isclose(ga.params[0] + gb.params[0], 0.0, abs_tol=1e-10)

    # General: check via matrix product ≈ identity
    try:
        product = ga.to_matrix() @ gb.to_matrix()
        import numpy as np
        dim = 2 ** ga.num_qubits
        if np.allclose(product, np.eye(dim), atol=1e-10):
            return True
    except Exception:
        pass

    return False


class CancelInverses(TransformationPass):
    """Remove adjacent pairs of mutually-inverse gates on each wire.

    The pass repeatedly scans until no more cancellations are possible
    (fixed-point iteration).
    """

    def run(self, dag: DAGCircuit) -> DAGCircuit:
        changed = True
        while changed:
            changed = False
            op_nodes = dag.op_nodes()
            removed: set = set()

            for i, node_a in enumerate(op_nodes):
                if node_a.node_id in removed:
                    continue
                if node_a.instruction is None:
                    continue
                if node_a.instruction.gate.is_barrier:
                    continue

                # Find the next op node on each wire of node_a
                for wire in node_a.instruction.qubits:
                    succs = dag.wire_successors(node_a, wire)
                    for node_b in succs:
                        if node_b.kind != DAGNodeType.OP:
                            continue
                        if node_b.node_id in removed:
                            continue
                        if node_b.instruction is None:
                            continue
                        if node_b.instruction.gate.is_barrier:
                            continue

                        if _gates_cancel(node_a, node_b):
                            dag.remove_op_node(node_b)
                            dag.remove_op_node(node_a)
                            removed.add(node_a.node_id)
                            removed.add(node_b.node_id)
                            changed = True
                            break
                    if node_a.node_id in removed:
                        break

        return dag
