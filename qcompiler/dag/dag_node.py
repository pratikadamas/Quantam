"""
dag_node.py — Node types for the DAGCircuit.

Every node in the DAG is one of three kinds:
  IN   — wire-input  node (one per qubit/clbit, no predecessors)
  OUT  — wire-output node (one per qubit/clbit, no successors)
  OP   — gate-operation node (holds a CircuitInstruction)

Edges connect nodes along qubit/clbit wires and carry a wire label
(the Qubit or Clbit that flows through that edge).
"""
from __future__ import annotations

from enum import Enum, auto
from typing import Optional

from qcompiler.core.instruction import CircuitInstruction
from qcompiler.core.qubit import Clbit, Qubit


class DAGNodeType(Enum):
    IN = auto()
    OUT = auto()
    OP = auto()


class DAGNode:
    """A node in the DAGCircuit.

    Parameters
    ----------
    node_id : int
        Unique integer identifier assigned by DAGCircuit.
    kind : DAGNodeType
        IN, OUT, or OP.
    wire : Qubit | Clbit | None
        For IN/OUT nodes: the wire this node represents.
        For OP nodes: None (the op touches multiple wires).
    instruction : CircuitInstruction | None
        For OP nodes: the gate instruction. None for IN/OUT.
    """

    __slots__ = ("node_id", "kind", "wire", "instruction")

    def __init__(
        self,
        node_id: int,
        kind: DAGNodeType,
        wire: Optional[object] = None,
        instruction: Optional[CircuitInstruction] = None,
    ) -> None:
        self.node_id = node_id
        self.kind = kind
        self.wire = wire
        self.instruction = instruction

    @property
    def name(self) -> str:
        if self.kind == DAGNodeType.OP:
            assert self.instruction is not None
            return self.instruction.gate.name
        elif self.kind == DAGNodeType.IN:
            return f"in[{self.wire}]"
        else:
            return f"out[{self.wire}]"

    def __repr__(self) -> str:
        if self.kind == DAGNodeType.OP:
            return f"DAGNode(OP, id={self.node_id}, gate={self.instruction!r})"
        return f"DAGNode({self.kind.name}, id={self.node_id}, wire={self.wire})"

    def __hash__(self) -> int:
        return hash(self.node_id)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, DAGNode):
            return NotImplemented
        return self.node_id == other.node_id
