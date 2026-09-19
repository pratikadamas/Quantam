"""
dag_circuit.py — Directed Acyclic Graph (DAG) representation of a QuantumCircuit.

The DAG encodes data-dependency between gates:
  - Each qubit/clbit has an IN node and an OUT node.
  - Each gate is an OP node.
  - A directed edge from node A to node B on wire W means "B must execute
    after A on wire W".
  - Edges carry a 'wire' attribute (the Qubit or Clbit).

The DAG enables:
  - Topological ordering (scheduling)
  - Identifying commuting gates
  - Optimization passes (cancel adjacent inverse pairs, etc.)
  - Conversion back to a QuantumCircuit

Dependencies: networkx (pure Python graph library — no Qiskit).
"""
from __future__ import annotations

from typing import Any, Dict, Generator, Iterable, Iterator, List, Optional, Set, Tuple, Union

import networkx as nx

from qcompiler.core.circuit import QuantumCircuit
from qcompiler.core.gate import Gate
from qcompiler.core.instruction import CircuitInstruction
from qcompiler.core.qubit import Clbit, Qubit
from qcompiler.dag.dag_node import DAGNode, DAGNodeType


class DAGCircuit:
    """DAG representation of a quantum circuit.

    Parameters
    ----------
    name : str
        Circuit name (copied from the source QuantumCircuit).

    Build the DAG from a QuantumCircuit with :meth:`from_circuit`.
    Convert back with :meth:`to_circuit`.
    """

    def __init__(self, name: str = "dag") -> None:
        self.name = name
        self._graph: nx.DiGraph = nx.DiGraph()
        self._node_counter = 0
        # wire → current "frontier" node (last node on that wire)
        self._wire_last: Dict[object, DAGNode] = {}
        self._input_nodes: Dict[object, DAGNode] = {}
        self._output_nodes: Dict[object, DAGNode] = {}
        self._qubits: List[Qubit] = []
        self._clbits: List[Clbit] = []

    # ------------------------------------------------------------------
    # Node creation helpers
    # ------------------------------------------------------------------

    def _new_id(self) -> int:
        nid = self._node_counter
        self._node_counter += 1
        return nid

    def _add_node(self, node: DAGNode) -> DAGNode:
        self._graph.add_node(node.node_id, data=node)
        return node

    def _add_edge(self, src: DAGNode, dst: DAGNode, wire: object) -> None:
        self._graph.add_edge(src.node_id, dst.node_id, wire=wire)

    def _get_node(self, node_id: int) -> DAGNode:
        return self._graph.nodes[node_id]["data"]

    # ------------------------------------------------------------------
    # Wires
    # ------------------------------------------------------------------

    def _add_wire(self, wire: Union[Qubit, Clbit]) -> None:
        in_node = self._add_node(DAGNode(self._new_id(), DAGNodeType.IN, wire=wire))
        out_node = self._add_node(DAGNode(self._new_id(), DAGNodeType.OUT, wire=wire))
        self._add_edge(in_node, out_node, wire)
        self._wire_last[wire] = in_node
        self._input_nodes[wire] = in_node
        self._output_nodes[wire] = out_node

    # ------------------------------------------------------------------
    # Instruction appending
    # ------------------------------------------------------------------

    def _apply_instruction(self, instr: CircuitInstruction) -> DAGNode:
        """Insert a gate op into the DAG, wiring it onto the qubit/clbit wires."""
        wires = list(instr.qubits) + list(instr.clbits)
        op_node = self._add_node(DAGNode(self._new_id(), DAGNodeType.OP, instruction=instr))

        for wire in wires:
            prev = self._wire_last[wire]
            out_node = self._output_nodes[wire]

            # Remove the direct edge prev → out_node
            if self._graph.has_edge(prev.node_id, out_node.node_id):
                self._graph.remove_edge(prev.node_id, out_node.node_id)

            # Insert: prev → op_node → out_node
            self._add_edge(prev, op_node, wire)
            self._add_edge(op_node, out_node, wire)
            self._wire_last[wire] = op_node

        return op_node

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------

    @classmethod
    def from_circuit(cls, circuit: QuantumCircuit) -> "DAGCircuit":
        """Build a DAGCircuit from a QuantumCircuit.

        Parameters
        ----------
        circuit : QuantumCircuit
            Source circuit.

        Returns
        -------
        DAGCircuit
        """
        dag = cls(name=circuit.name)
        dag._qubits = list(circuit.qubits)
        dag._clbits = list(circuit.clbits)

        for q in circuit.qubits:
            dag._add_wire(q)
        for c in circuit.clbits:
            dag._add_wire(c)

        for instr in circuit.data:
            dag._apply_instruction(instr)

        return dag

    # ------------------------------------------------------------------
    # Conversion back to QuantumCircuit
    # ------------------------------------------------------------------

    def to_circuit(self) -> QuantumCircuit:
        """Reconstruct a QuantumCircuit from this DAG (topological order)."""
        qc = QuantumCircuit(len(self._qubits), len(self._clbits), name=self.name)

        # Remap DAG Qubit objects → circuit Qubit objects
        q_map = {q: qc._qubits[i] for i, q in enumerate(self._qubits)}
        c_map = {c: qc._clbits[i] for i, c in enumerate(self._clbits)}

        for node_id in nx.topological_sort(self._graph):
            node: DAGNode = self._graph.nodes[node_id]["data"]
            if node.kind != DAGNodeType.OP:
                continue
            instr = node.instruction
            assert instr is not None
            new_qubits = [q_map[q] for q in instr.qubits]
            new_clbits = [c_map[c] for c in instr.clbits]
            qc.append(instr.gate, new_qubits, new_clbits)

        return qc

    # ------------------------------------------------------------------
    # DAG queries
    # ------------------------------------------------------------------

    def op_nodes(self) -> List[DAGNode]:
        """Return all OP nodes in topological order."""
        return [
            self._graph.nodes[nid]["data"]
            for nid in nx.topological_sort(self._graph)
            if self._graph.nodes[nid]["data"].kind == DAGNodeType.OP
        ]

    def layers(self) -> List[List[DAGNode]]:
        """Return gates grouped into parallel layers (topological generations)."""
        result: List[List[DAGNode]] = []
        for gen in nx.topological_generations(self._graph):
            ops = [
                self._graph.nodes[nid]["data"]
                for nid in gen
                if self._graph.nodes[nid]["data"].kind == DAGNodeType.OP
            ]
            if ops:
                result.append(ops)
        return result

    def predecessors(self, node: DAGNode) -> List[DAGNode]:
        return [self._graph.nodes[p]["data"] for p in self._graph.predecessors(node.node_id)]

    def successors(self, node: DAGNode) -> List[DAGNode]:
        return [self._graph.nodes[s]["data"] for s in self._graph.successors(node.node_id)]

    def wire_predecessors(self, node: DAGNode, wire: Union[Qubit, Clbit]) -> List[DAGNode]:
        """Predecessors of node on a specific wire."""
        return [
            self._graph.nodes[p]["data"]
            for p in self._graph.predecessors(node.node_id)
            if self._graph[p][node.node_id].get("wire") == wire
        ]

    def wire_successors(self, node: DAGNode, wire: Union[Qubit, Clbit]) -> List[DAGNode]:
        """Successors of node on a specific wire."""
        return [
            self._graph.nodes[s]["data"]
            for s in self._graph.successors(node.node_id)
            if self._graph[node.node_id][s].get("wire") == wire
        ]

    # ------------------------------------------------------------------
    # Node removal / substitution (used by passes)
    # ------------------------------------------------------------------

    def remove_op_node(self, node: DAGNode) -> None:
        """Remove an OP node and reconnect its predecessor/successor pairs."""
        assert node.kind == DAGNodeType.OP
        instr = node.instruction
        assert instr is not None
        wires = list(instr.qubits) + list(instr.clbits)

        for wire in wires:
            preds = self.wire_predecessors(node, wire)
            succs = self.wire_successors(node, wire)
            for pred in preds:
                for succ in succs:
                    self._add_edge(pred, succ, wire)

        self._graph.remove_node(node.node_id)

    def substitute_node(self, node: DAGNode, new_instruction: CircuitInstruction) -> DAGNode:
        """Replace a node's instruction in-place (same qubits, different gate)."""
        assert node.kind == DAGNodeType.OP
        new_node = DAGNode(node.node_id, DAGNodeType.OP, instruction=new_instruction)
        self._graph.nodes[node.node_id]["data"] = new_node
        return new_node

    # ------------------------------------------------------------------
    # Stats
    # ------------------------------------------------------------------

    def num_ops(self) -> int:
        return sum(1 for n in self._graph.nodes
                   if self._graph.nodes[n]["data"].kind == DAGNodeType.OP)

    def depth(self) -> int:
        return len(self.layers())

    def gate_counts(self) -> Dict[str, int]:
        counts: Dict[str, int] = {}
        for node in self.op_nodes():
            assert node.instruction is not None
            name = node.instruction.gate.name
            counts[name] = counts.get(name, 0) + 1
        return counts

    def to_dict(self) -> Dict[str, Any]:
        """Serialize the DAG to a JSON-compatible dictionary."""
        nodes = []
        for nid in sorted(self._graph.nodes):
            data: DAGNode = self._graph.nodes[nid]["data"]
            node_info: Dict[str, Any] = {
                "id": nid,
                "type": data.kind.name.lower(),
            }
            if data.kind == DAGNodeType.OP and data.instruction:
                instr = data.instruction
                node_info["name"] = instr.gate.name.upper()
                node_info["gate"] = instr.gate.name
                node_info["qubits"] = [q.name for q in instr.qubits]
                node_info["clbits"] = [c.name for c in instr.clbits]
                node_info["params"] = [float(p) for p in instr.gate.params]
                q_targets = ", ".join(q.name for q in instr.qubits)
                if instr.clbits:
                    q_targets += f" → {', '.join(c.name for c in instr.clbits)}"
                node_info["label"] = f"{instr.gate.name.upper()}({q_targets})"
                node_info["is_barrier"] = instr.gate.is_barrier
            elif data.wire is not None:
                w_name = getattr(data.wire, "name", str(data.wire))
                node_info["name"] = f"{data.kind.name}[{w_name}]"
                node_info["wire"] = w_name
                node_info["label"] = f"{data.kind.name}[{w_name}]"
            else:
                node_info["name"] = f"node_{nid}"
                node_info["label"] = f"node_{nid}"
            node_info["in_degree"] = self._graph.in_degree(nid)
            node_info["out_degree"] = self._graph.out_degree(nid)
            nodes.append(node_info)

        edges = []
        for u, v, attrs in self._graph.edges(data=True):
            wire = attrs.get("wire")
            w_name = getattr(wire, "name", str(wire)) if wire is not None else ""
            edges.append({
                "source": u,
                "target": v,
                "wire": w_name,
            })

        # Calculate topological generations (parallel scheduling stages)
        try:
            generations = [list(gen) for gen in nx.topological_generations(self._graph)]
        except Exception:
            generations = []

        # Calculate critical path (longest causality bottleneck through DAG)
        try:
            critical_path = list(nx.dag_longest_path(self._graph))
        except Exception:
            critical_path = []

        return {
            "num_nodes": len(nodes),
            "num_edges": len(edges),
            "num_ops": self.num_ops(),
            "depth": self.depth(),
            "critical_path": critical_path,
            "nodes": nodes,
            "edges": edges,
            "layers": generations,
        }

    def draw_ascii(self) -> str:
        """Render a readable text-based ASCII representation of the DAG."""
        lines = [
            f"DAGCircuit: {self.name} (Ops: {self.num_ops()}, Total Nodes: {self._graph.number_of_nodes()}, Depth: {self.depth()})",
            "=" * 60,
        ]
        try:
            generations = list(nx.topological_generations(self._graph))
        except Exception:
            generations = []

        for layer_idx, gen in enumerate(generations):
            lines.append(f"Layer {layer_idx}:")
            for nid in sorted(gen):
                node: DAGNode = self._graph.nodes[nid]["data"]
                successors = list(self._graph.successors(nid))
                succ_strs = []
                for s in successors:
                    edge_data = self._graph.get_edge_data(nid, s, default={})
                    wire = edge_data.get("wire")
                    w_str = getattr(wire, "name", str(wire)) if wire else "?"
                    s_node: DAGNode = self._graph.nodes[s]["data"]
                    succ_strs.append(f"--({w_str})--> [{s_node.node_id}] {s_node.name}")

                if succ_strs:
                    lines.append(f"  [{nid:2d}] {node.name:15s} " + "; ".join(succ_strs))
                else:
                    lines.append(f"  [{nid:2d}] {node.name:15s} (terminal)")
        return "\n".join(lines)

    def draw_mermaid(self) -> str:
        """Render the DAG in Mermaid diagram format."""
        lines = ["graph LR"]
        for nid in sorted(self._graph.nodes):
            data: DAGNode = self._graph.nodes[nid]["data"]
            if data.kind == DAGNodeType.OP and data.instruction:
                instr = data.instruction
                q_str = ", ".join(q.name for q in instr.qubits)
                lines.append(f'    n{nid}["{instr.gate.name.upper()}<br/><small>{q_str}</small>"]')
            elif data.kind == DAGNodeType.IN:
                lines.append(f'    n{nid}(["IN: {data.wire}"])')
            else:
                lines.append(f'    n{nid}(["OUT: {data.wire}"])')

        for u, v, attrs in self._graph.edges(data=True):
            wire = attrs.get("wire")
            w_name = getattr(wire, "name", str(wire)) if wire else ""
            lines.append(f"    n{u} -->|{w_name}| n{v}")
        return "\n".join(lines)

    def __repr__(self) -> str:
        return (f"DAGCircuit(name={self.name!r}, "
                f"ops={self.num_ops()}, depth={self.depth()})")
