"""
merge_rotations.py — Merge consecutive single-qubit rotation gates.

Consecutive Rz (or Rx or Ry) gates on the same qubit with no intervening
gates on that qubit can be merged into a single rotation:
  Rz(a) · Rz(b) = Rz(a + b)

If the merged angle is (close to) zero the gate is dropped entirely.
"""
from __future__ import annotations

import math
from typing import Dict, List, Tuple

from qcompiler.core.gate import StandardGate
from qcompiler.core.instruction import CircuitInstruction
from qcompiler.dag.dag_circuit import DAGCircuit
from qcompiler.dag.dag_node import DAGNode, DAGNodeType
from qcompiler.passes.base_pass import TransformationPass

_ROTATION_FAMILIES = {"rz", "rx", "ry"}
_ANGLE_ZERO_TOL = 1e-10
_ANGLE_2PI_TOL = 1e-10


def _angle_is_trivial(theta: float) -> bool:
    """True if the rotation is effectively zero (mod 2π)."""
    return math.isclose(theta % (2 * math.pi), 0.0, abs_tol=_ANGLE_ZERO_TOL)


class MergeRotations(TransformationPass):
    """Merge consecutive Rz/Rx/Ry gates on each qubit wire.

    For each qubit:
      1. Walk the wire in topological order.
      2. Collect consecutive runs of the same rotation family.
      3. Replace the run with a single gate (or remove if angle ≈ 0).
    """

    def run(self, dag: DAGCircuit) -> DAGCircuit:
        changed = True
        while changed:
            changed = False
            op_nodes = dag.op_nodes()

            for node_a in list(op_nodes):
                # Skip if already removed
                try:
                    _ = dag._graph.nodes[node_a.node_id]
                except KeyError:
                    continue

                instr_a = node_a.instruction
                if instr_a is None:
                    continue
                gate_a = instr_a.gate
                if gate_a.name not in _ROTATION_FAMILIES:
                    continue
                if len(gate_a.params) != 1:
                    continue

                # Look for immediate successor on the same (single) qubit wire
                wire = instr_a.qubits[0]
                succs = dag.wire_successors(node_a, wire)
                if not succs:
                    continue
                node_b = succs[0]
                if node_b.kind != DAGNodeType.OP:
                    continue

                try:
                    _ = dag._graph.nodes[node_b.node_id]
                except KeyError:
                    continue

                instr_b = node_b.instruction
                if instr_b is None:
                    continue
                gate_b = instr_b.gate

                # Must be same rotation family, same qubit
                if gate_b.name != gate_a.name:
                    continue
                if instr_b.qubits != instr_a.qubits:
                    continue
                if len(gate_b.params) != 1:
                    continue

                # Merge
                merged_angle = gate_a.params[0] + gate_b.params[0]

                # Remove node_b first, then substitute node_a
                dag.remove_op_node(node_b)

                if _angle_is_trivial(merged_angle):
                    dag.remove_op_node(node_a)
                else:
                    factory = {"rz": StandardGate.rz, "rx": StandardGate.rx, "ry": StandardGate.ry}
                    new_gate = factory[gate_a.name](merged_angle)
                    new_instr = CircuitInstruction(new_gate, list(instr_a.qubits))
                    dag.substitute_node(node_a, new_instr)

                changed = True

        return dag
