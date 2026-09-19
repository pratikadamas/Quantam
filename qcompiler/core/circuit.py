"""
circuit.py — QuantumCircuit IR (Intermediate Representation).

This is the primary user-facing object. It supports:
  - n qubits and m classical bits
  - All standard gates via convenience methods
  - Barriers and measurements
  - Iteration over instructions
  - String representation

No Qiskit dependency whatsoever.
"""
from __future__ import annotations

import math
from typing import Dict, Iterable, Iterator, List, Optional, Sequence, Tuple, Union

from qcompiler.core.gate import Gate, StandardGate
from qcompiler.core.instruction import CircuitInstruction
from qcompiler.core.qubit import Clbit, Qubit


class QuantumCircuit:
    """An n-qubit quantum circuit.

    Parameters
    ----------
    num_qubits : int
        Number of quantum bits.
    num_clbits : int, optional
        Number of classical bits (default 0).
    name : str, optional
        Human-readable circuit name.

    Examples
    --------
    >>> qc = QuantumCircuit(2, 2, name="bell")
    >>> qc.h(0)
    >>> qc.cx(0, 1)
    >>> qc.measure(0, 0)
    >>> qc.measure(1, 1)
    >>> print(qc)
    """

    def __init__(
        self,
        num_qubits: int,
        num_clbits: int = 0,
        name: str = "circuit",
    ) -> None:
        if num_qubits < 1:
            raise ValueError("num_qubits must be >= 1.")
        self.name = name
        self._qubits: List[Qubit] = [Qubit("q", i) for i in range(num_qubits)]
        self._clbits: List[Clbit] = [Clbit("c", i) for i in range(num_clbits)]
        self._data: List[CircuitInstruction] = []

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def num_qubits(self) -> int:
        return len(self._qubits)

    @property
    def num_clbits(self) -> int:
        return len(self._clbits)

    @property
    def qubits(self) -> List[Qubit]:
        return list(self._qubits)

    @property
    def clbits(self) -> List[Clbit]:
        return list(self._clbits)

    @property
    def data(self) -> List[CircuitInstruction]:
        """Read-only view of circuit instructions."""
        return list(self._data)

    def __len__(self) -> int:
        return len(self._data)

    def __iter__(self) -> Iterator[CircuitInstruction]:
        return iter(self._data)

    # ------------------------------------------------------------------
    # Qubit resolution helpers
    # ------------------------------------------------------------------

    def _resolve_qubit(self, q: Union[int, Qubit]) -> Qubit:
        if isinstance(q, int):
            if not (0 <= q < self.num_qubits):
                raise IndexError(f"Qubit index {q} out of range for {self.num_qubits}-qubit circuit.")
            return self._qubits[q]
        if q not in self._qubits:
            raise ValueError(f"Qubit {q} is not part of this circuit.")
        return q

    def _resolve_clbit(self, c: Union[int, Clbit]) -> Clbit:
        if isinstance(c, int):
            if not (0 <= c < self.num_clbits):
                raise IndexError(f"Clbit index {c} out of range.")
            return self._clbits[c]
        if c not in self._clbits:
            raise ValueError(f"Clbit {c} is not part of this circuit.")
        return c

    def _resolve_qubits(self, qs: Sequence[Union[int, Qubit]]) -> List[Qubit]:
        return [self._resolve_qubit(q) for q in qs]

    # ------------------------------------------------------------------
    # Low-level append
    # ------------------------------------------------------------------

    def append(self, gate: Gate, qubits: Sequence[Union[int, Qubit]],
               clbits: Optional[Sequence[Union[int, Clbit]]] = None) -> "QuantumCircuit":
        """Append any Gate to the circuit.

        Parameters
        ----------
        gate : Gate
        qubits : sequence of int or Qubit
        clbits : sequence of int or Clbit, optional

        Returns
        -------
        self  (for method chaining)
        """
        resolved_q = self._resolve_qubits(qubits)
        resolved_c = [self._resolve_clbit(c) for c in clbits] if clbits else []
        instr = CircuitInstruction(gate, resolved_q, resolved_c)
        self._data.append(instr)
        return self

    # ------------------------------------------------------------------
    # Single-qubit fixed gates
    # ------------------------------------------------------------------

    def id(self, qubit: Union[int, Qubit]) -> "QuantumCircuit":
        """Identity gate."""
        return self.append(StandardGate.id(), [qubit])

    def x(self, qubit: Union[int, Qubit]) -> "QuantumCircuit":
        """Pauli-X gate."""
        return self.append(StandardGate.x(), [qubit])

    def y(self, qubit: Union[int, Qubit]) -> "QuantumCircuit":
        """Pauli-Y gate."""
        return self.append(StandardGate.y(), [qubit])

    def z(self, qubit: Union[int, Qubit]) -> "QuantumCircuit":
        """Pauli-Z gate."""
        return self.append(StandardGate.z(), [qubit])

    def h(self, qubit: Union[int, Qubit]) -> "QuantumCircuit":
        """Hadamard gate."""
        return self.append(StandardGate.h(), [qubit])

    def s(self, qubit: Union[int, Qubit]) -> "QuantumCircuit":
        """S gate."""
        return self.append(StandardGate.s(), [qubit])

    def sdg(self, qubit: Union[int, Qubit]) -> "QuantumCircuit":
        """S-dagger gate."""
        return self.append(StandardGate.sdg(), [qubit])

    def t(self, qubit: Union[int, Qubit]) -> "QuantumCircuit":
        """T gate."""
        return self.append(StandardGate.t(), [qubit])

    def tdg(self, qubit: Union[int, Qubit]) -> "QuantumCircuit":
        """T-dagger gate."""
        return self.append(StandardGate.tdg(), [qubit])

    def sx(self, qubit: Union[int, Qubit]) -> "QuantumCircuit":
        """√X gate."""
        return self.append(StandardGate.sx(), [qubit])

    # ------------------------------------------------------------------
    # Parameterised single-qubit gates
    # ------------------------------------------------------------------

    def rx(self, theta: float, qubit: Union[int, Qubit]) -> "QuantumCircuit":
        """Rotation around X axis by angle theta."""
        return self.append(StandardGate.rx(theta), [qubit])

    def ry(self, theta: float, qubit: Union[int, Qubit]) -> "QuantumCircuit":
        """Rotation around Y axis by angle theta."""
        return self.append(StandardGate.ry(theta), [qubit])

    def rz(self, lam: float, qubit: Union[int, Qubit]) -> "QuantumCircuit":
        """Rotation around Z axis by angle lam."""
        return self.append(StandardGate.rz(lam), [qubit])

    def p(self, lam: float, qubit: Union[int, Qubit]) -> "QuantumCircuit":
        """Phase gate P(λ)."""
        return self.append(StandardGate.p(lam), [qubit])

    def u1(self, lam: float, qubit: Union[int, Qubit]) -> "QuantumCircuit":
        return self.append(StandardGate.u1(lam), [qubit])

    def u2(self, phi: float, lam: float, qubit: Union[int, Qubit]) -> "QuantumCircuit":
        return self.append(StandardGate.u2(phi, lam), [qubit])

    def u3(self, theta: float, phi: float, lam: float,
           qubit: Union[int, Qubit]) -> "QuantumCircuit":
        """General single-qubit unitary U3(θ,φ,λ)."""
        return self.append(StandardGate.u3(theta, phi, lam), [qubit])

    # ------------------------------------------------------------------
    # Two-qubit gates
    # ------------------------------------------------------------------

    def cx(self, control: Union[int, Qubit], target: Union[int, Qubit]) -> "QuantumCircuit":
        """Controlled-X (CNOT)."""
        return self.append(StandardGate.cx(), [control, target])

    def cnot(self, control: Union[int, Qubit], target: Union[int, Qubit]) -> "QuantumCircuit":
        """Alias for cx."""
        return self.cx(control, target)

    def cy(self, control: Union[int, Qubit], target: Union[int, Qubit]) -> "QuantumCircuit":
        return self.append(StandardGate.cy(), [control, target])

    def cz(self, control: Union[int, Qubit], target: Union[int, Qubit]) -> "QuantumCircuit":
        return self.append(StandardGate.cz(), [control, target])

    def swap(self, q0: Union[int, Qubit], q1: Union[int, Qubit]) -> "QuantumCircuit":
        return self.append(StandardGate.swap(), [q0, q1])

    def cp(self, lam: float, control: Union[int, Qubit],
           target: Union[int, Qubit]) -> "QuantumCircuit":
        """Controlled-phase gate."""
        return self.append(StandardGate.cp(lam), [control, target])

    def crz(self, lam: float, control: Union[int, Qubit],
            target: Union[int, Qubit]) -> "QuantumCircuit":
        """Controlled-Rz gate."""
        return self.append(StandardGate.crz(lam), [control, target])

    # ------------------------------------------------------------------
    # Three-qubit gates
    # ------------------------------------------------------------------

    def ccx(self, c0: Union[int, Qubit], c1: Union[int, Qubit],
            target: Union[int, Qubit]) -> "QuantumCircuit":
        """Toffoli gate."""
        return self.append(StandardGate.ccx(), [c0, c1, target])

    def toffoli(self, c0, c1, target) -> "QuantumCircuit":
        """Alias for ccx."""
        return self.ccx(c0, c1, target)

    def cswap(self, control: Union[int, Qubit], q0: Union[int, Qubit],
              q1: Union[int, Qubit]) -> "QuantumCircuit":
        """Fredkin gate."""
        return self.append(StandardGate.cswap(), [control, q0, q1])

    # ------------------------------------------------------------------
    # Measurement and barrier
    # ------------------------------------------------------------------

    def measure(self, qubit: Union[int, Qubit],
                clbit: Union[int, Clbit]) -> "QuantumCircuit":
        """Measure a qubit into a classical bit."""
        if self.num_clbits == 0:
            raise ValueError("Circuit has no classical bits. Add clbits to measure.")
        return self.append(StandardGate.measure(), [qubit], [clbit])

    def measure_all(self) -> "QuantumCircuit":
        """Measure all qubits. Adds classical bits if needed."""
        if self.num_clbits < self.num_qubits:
            extra = self.num_qubits - self.num_clbits
            start = self.num_clbits
            self._clbits.extend([Clbit("c", start + i) for i in range(extra)])
        for i in range(self.num_qubits):
            self.measure(i, i)
        return self

    def barrier(self, *qubits: Union[int, Qubit]) -> "QuantumCircuit":
        """Insert a barrier across specified qubits (or all qubits if none given)."""
        targets = list(qubits) if qubits else list(range(self.num_qubits))
        resolved = self._resolve_qubits(targets)
        gate = StandardGate.barrier(len(resolved))
        instr = CircuitInstruction(gate, resolved)
        self._data.append(instr)
        return self

    # ------------------------------------------------------------------
    # Circuit operations
    # ------------------------------------------------------------------

    def inverse(self) -> "QuantumCircuit":
        """Return the inverse (dagger) of this circuit."""
        inv = QuantumCircuit(self.num_qubits, self.num_clbits, name=f"{self.name}_inv")
        for instr in reversed(self._data):
            if instr.gate.is_barrier:
                continue
            inv._data.append(CircuitInstruction(instr.gate.inverse(),
                                                list(instr.qubits),
                                                list(instr.clbits)))
        return inv

    def compose(self, other: "QuantumCircuit",
                qubits: Optional[List[Union[int, Qubit]]] = None) -> "QuantumCircuit":
        """Append another circuit onto this one.

        Parameters
        ----------
        other : QuantumCircuit
            Circuit to append. Must have <= this circuit's num_qubits.
        qubits : list, optional
            Qubit mapping. If None, maps qubit i → qubit i.
        """
        if other.num_qubits > self.num_qubits:
            raise ValueError("other circuit has more qubits than self.")
        if qubits is None:
            mapping = {Qubit("q", i): self._qubits[i] for i in range(other.num_qubits)}
        else:
            resolved = self._resolve_qubits(qubits)
            mapping = {other._qubits[i]: resolved[i] for i in range(other.num_qubits)}
        for instr in other._data:
            new_qubits = [mapping[q] for q in instr.qubits]
            self._data.append(CircuitInstruction(instr.gate, new_qubits, list(instr.clbits)))
        return self

    def copy(self) -> "QuantumCircuit":
        """Return a deep copy of this circuit."""
        new = QuantumCircuit(self.num_qubits, self.num_clbits, name=self.name)
        new._data = list(self._data)
        return new

    # ------------------------------------------------------------------
    # Gate counts / stats
    # ------------------------------------------------------------------

    def gate_counts(self) -> Dict[str, int]:
        """Return a dict mapping gate name → count."""
        counts: Dict[str, int] = {}
        for instr in self._data:
            n = instr.gate.name
            counts[n] = counts.get(n, 0) + 1
        return counts

    def depth(self) -> int:
        """Return the circuit depth (longest gate path, ignoring barriers)."""
        qubit_depth: Dict[Qubit, int] = {q: 0 for q in self._qubits}
        for instr in self._data:
            if instr.gate.is_barrier:
                continue
            d = max(qubit_depth[q] for q in instr.qubits)
            for q in instr.qubits:
                qubit_depth[q] = d + 1
        return max(qubit_depth.values()) if qubit_depth else 0

    # ------------------------------------------------------------------
    # ASCII drawing
    # ------------------------------------------------------------------

    def draw(self) -> str:
        """Return a simple ASCII representation of the circuit."""
        lines = [f"Circuit: {self.name}  ({self.num_qubits}q / {self.num_clbits}c)\n"]
        lines.append("─" * 60)
        for i, instr in enumerate(self._data):
            qbs = ", ".join(str(q) for q in instr.qubits)
            cbs = (" → " + ", ".join(str(c) for c in instr.clbits)) if instr.clbits else ""
            params = ""
            if instr.gate.params:
                fmt = ", ".join(f"{p:.4f}" for p in instr.gate.params)
                params = f"({fmt})"
            lines.append(f"  [{i:3d}] {instr.gate.name.upper()}{params}  {qbs}{cbs}")
        lines.append("─" * 60)
        lines.append(f"Depth: {self.depth()}  |  Gates: {sum(self.gate_counts().values())}")
        return "\n".join(lines)

    def __repr__(self) -> str:
        return (f"QuantumCircuit(name={self.name!r}, "
                f"num_qubits={self.num_qubits}, "
                f"num_clbits={self.num_clbits}, "
                f"instructions={len(self._data)})")

    def __str__(self) -> str:
        return self.draw()
