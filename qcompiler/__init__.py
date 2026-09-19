"""
qcompiler — A from-scratch quantum compiler pipeline.

Pipeline:
  QuantumCircuit IR → DAG → Optimization Passes → Gate Decomposition → OpenQASM 3

No Qiskit required for the core pipeline.
Qiskit is an optional dependency used only in the QASM3 bridge backend.
"""

from qcompiler.core.circuit import QuantumCircuit
from qcompiler.compiler import compile  # noqa: F401

__version__ = "0.1.0"
__all__ = ["QuantumCircuit", "compile"]
