"""
remove_barriers.py — Strip all Barrier pseudo-gates from the DAG.

Barriers carry no quantum semantics; they are used to prevent optimisers
from moving gates across them. Removing them before further passes allows
the other passes to work across barrier boundaries.
"""
from __future__ import annotations

from qcompiler.dag.dag_circuit import DAGCircuit
from qcompiler.dag.dag_node import DAGNodeType
from qcompiler.passes.base_pass import TransformationPass


class RemoveBarriers(TransformationPass):
    """Remove all barrier nodes from the DAG."""

    def run(self, dag: DAGCircuit) -> DAGCircuit:
        barriers = [
            node
            for node in dag.op_nodes()
            if node.instruction is not None and node.instruction.gate.is_barrier
        ]
        for node in barriers:
            dag.remove_op_node(node)
        return dag
