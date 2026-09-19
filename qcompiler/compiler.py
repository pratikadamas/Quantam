"""
compiler.py — Top-level compile() function.

This is the single entry-point for the full pipeline:

  QuantumCircuit IR
       ↓
  DAGCircuit
       ↓
  Optimization (PassManager)
       ↓
  Gate Decomposition
       ↓
  Final QuantumCircuit
       ↓
  OpenQASM 3 string

Usage
-----
>>> from qcompiler import QuantumCircuit, compile
>>> qc = QuantumCircuit(2, 2)
>>> qc.h(0)
>>> qc.cx(0, 1)
>>> qc.measure_all()
>>> result = compile(qc)
>>> print(result.qasm)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

from qcompiler.backend.qasm3 import QASM3Backend
from qcompiler.core.circuit import QuantumCircuit
from qcompiler.dag.dag_circuit import DAGCircuit
from qcompiler.decompose.decomposer import GateDecomposer
from qcompiler.passes.base_pass import PassManager
from qcompiler.passes.cancel_inverses import CancelInverses
from qcompiler.passes.merge_rotations import MergeRotations
from qcompiler.passes.remove_barriers import RemoveBarriers


@dataclass
class CompileResult:
    """Result object returned by :func:`compile`.

    Attributes
    ----------
    qasm : str
        The final OpenQASM 3 string.
    original_circuit : QuantumCircuit
        The input circuit (before any transformation).
    final_circuit : QuantumCircuit
        The fully compiled circuit (after optimisation + decomposition).
    dag : DAGCircuit
        The optimised DAG (before decomposition).
    stats : dict
        Summary statistics comparing input and output.
    """
    qasm: str
    original_circuit: QuantumCircuit
    final_circuit: QuantumCircuit
    dag: DAGCircuit
    stats: Dict = field(default_factory=dict)

    def __str__(self) -> str:
        lines = [
            "=== CompileResult ===",
            f"Qubits      : {self.stats.get('num_qubits')}",
            f"Clbits      : {self.stats.get('num_clbits')}",
            f"Gates before: {self.stats.get('original_gate_count')}",
            f"Gates after : {self.stats.get('final_gate_count')}",
            f"Depth before: {self.stats.get('original_depth')}",
            f"Depth after : {self.stats.get('final_depth')}",
            "",
            "--- OpenQASM 3 ---",
            self.qasm,
        ]
        return "\n".join(lines)


def compile(
    circuit: QuantumCircuit,
    optimization_level: int = 1,
    basis_gates=None,
    use_qiskit_bridge: bool = False,
    custom_pass_manager: Optional[PassManager] = None,
) -> CompileResult:
    """Compile a QuantumCircuit through the full pipeline.

    Parameters
    ----------
    circuit : QuantumCircuit
        The source circuit to compile.
    optimization_level : int
        0 = no optimization
        1 = cancel inverses + merge rotations  (default)
        2 = level-1 + repeated passes until fixed point
    basis_gates : frozenset of str, optional
        Override default basis gate set.
    use_qiskit_bridge : bool
        Use Qiskit for QASM3 output instead of pure-Python emitter.
    custom_pass_manager : PassManager, optional
        Override the built-in pass manager entirely.

    Returns
    -------
    CompileResult
    """
    original_circuit = circuit.copy()

    # 1. Build DAG
    dag = DAGCircuit.from_circuit(circuit)
    original_gate_count = dag.num_ops()
    original_depth = dag.depth()

    # 2. Optimization passes
    if custom_pass_manager is not None:
        pm = custom_pass_manager
    elif optimization_level == 0:
        pm = PassManager([])
    else:
        pm = PassManager([
            RemoveBarriers(),
            CancelInverses(),
            MergeRotations(),
        ])
        if optimization_level >= 2:
            # Run passes a second time after merging
            pm.append(CancelInverses())
            pm.append(MergeRotations())

    dag = pm.run(dag)

    # 3. Reconstruct circuit from DAG
    optimized_circuit = dag.to_circuit()

    # 4. Gate decomposition
    decomposer = GateDecomposer(basis_gates=basis_gates)
    final_circuit = decomposer.run(optimized_circuit)

    # 5. QASM3 emission
    backend = QASM3Backend(use_qiskit_bridge=use_qiskit_bridge)
    qasm_str = backend.dumps(final_circuit)

    # 6. Collect stats
    final_counts = final_circuit.gate_counts()
    final_gate_count = sum(v for k, v in final_counts.items()
                           if k not in {"barrier", "measure"})

    stats = {
        "num_qubits": circuit.num_qubits,
        "num_clbits": circuit.num_clbits,
        "original_gate_count": original_gate_count,
        "optimized_gate_count": dag.num_ops(),
        "final_gate_count": sum(final_circuit.gate_counts().values()),
        "original_depth": original_depth,
        "final_depth": final_circuit.depth(),
        "gate_counts": final_counts,
        "optimization_level": optimization_level,
    }

    return CompileResult(
        qasm=qasm_str,
        original_circuit=original_circuit,
        final_circuit=final_circuit,
        dag=dag,
        stats=stats,
    )
