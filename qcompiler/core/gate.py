"""
gate.py — Gate definitions with unitary matrices.

A Gate stores:
  - name          : human-readable identifier used in QASM output
  - num_qubits    : how many qubits the gate acts on
  - params        : list of floating-point angle parameters (e.g. for Rx)
  - matrix        : (2**n × 2**n) complex numpy array representing the unitary
  - is_barrier    : True only for the special Barrier pseudo-gate

StandardGate is a factory that creates all common single- and two-qubit gates
so the rest of the pipeline can refer to them by name without duplicating
matrix definitions.
"""
from __future__ import annotations

import math
from typing import List, Optional
import numpy as np


class Gate:
    """Quantum gate with an associated unitary matrix.

    Parameters
    ----------
    name : str
        Gate identifier, e.g. ``"h"``, ``"cx"``, ``"rz"``.
    num_qubits : int
        Number of qubits the gate acts on.
    params : list of float
        Rotation angles or other continuous parameters.
    matrix : np.ndarray, optional
        The unitary matrix. If *None* the gate is treated as opaque
        (useful for custom / user-defined gates).
    is_barrier : bool
        Mark this gate as the special Barrier pseudo-gate.
    """

    def __init__(
        self,
        name: str,
        num_qubits: int,
        params: Optional[List[float]] = None,
        matrix: Optional[np.ndarray] = None,
        is_barrier: bool = False,
    ) -> None:
        self.name = name
        self.num_qubits = num_qubits
        self.params: List[float] = params if params is not None else []
        self._matrix = matrix
        self.is_barrier = is_barrier

    # ------------------------------------------------------------------
    # Matrix access
    # ------------------------------------------------------------------

    @property
    def matrix(self) -> Optional[np.ndarray]:
        return self._matrix

    def to_matrix(self) -> np.ndarray:
        if self._matrix is None:
            raise ValueError(f"Gate '{self.name}' has no matrix defined (opaque gate).")
        return self._matrix.copy()

    # ------------------------------------------------------------------
    # Inverse
    # ------------------------------------------------------------------

    def inverse(self) -> "Gate":
        """Return the conjugate-transpose (dagger) of this gate."""
        if self._matrix is None:
            raise ValueError(f"Cannot invert opaque gate '{self.name}'.")
        inv_matrix = self._matrix.conj().T
        inv_params = [-p for p in self.params]
        # Known named inverses
        named_inv = {
            "s": "sdg", "sdg": "s",
            "t": "tdg", "tdg": "t",
            "h": "h", "x": "x", "y": "y", "z": "z",
            "cx": "cx", "cz": "cz", "swap": "swap",
            "id": "id",
        }
        inv_name = named_inv.get(self.name, f"{self.name}_dg")
        return Gate(inv_name, self.num_qubits, inv_params, inv_matrix)

    # ------------------------------------------------------------------
    # Equality
    # ------------------------------------------------------------------

    def is_inverse_of(self, other: "Gate") -> bool:
        """Check whether this gate and *other* are each other's inverse."""
        if self.num_qubits != other.num_qubits:
            return False
        if self._matrix is None or other._matrix is None:
            return False
        product = self._matrix @ other._matrix
        dim = 2 ** self.num_qubits
        return np.allclose(product, np.eye(dim), atol=1e-10)

    def __repr__(self) -> str:
        p = f", params={self.params}" if self.params else ""
        return f"Gate({self.name!r}, num_qubits={self.num_qubits}{p})"


# ---------------------------------------------------------------------------
# Standard gate library
# ---------------------------------------------------------------------------

class StandardGate:
    """Factory for standard quantum gates.

    All matrices follow the computational basis convention |0⟩, |1⟩.
    Two-qubit matrices are in the standard tensor product order:
    first qubit is the *most* significant bit.
    """

    # ---- Single-qubit fixed gates ----

    @staticmethod
    def id() -> Gate:
        return Gate("id", 1, [], np.eye(2, dtype=complex))

    @staticmethod
    def x() -> Gate:
        return Gate("x", 1, [], np.array([[0, 1], [1, 0]], dtype=complex))

    @staticmethod
    def y() -> Gate:
        return Gate("y", 1, [], np.array([[0, -1j], [1j, 0]], dtype=complex))

    @staticmethod
    def z() -> Gate:
        return Gate("z", 1, [], np.array([[1, 0], [0, -1]], dtype=complex))

    @staticmethod
    def h() -> Gate:
        s = 1 / math.sqrt(2)
        return Gate("h", 1, [], np.array([[s, s], [s, -s]], dtype=complex))

    @staticmethod
    def s() -> Gate:
        return Gate("s", 1, [], np.array([[1, 0], [0, 1j]], dtype=complex))

    @staticmethod
    def sdg() -> Gate:
        return Gate("sdg", 1, [], np.array([[1, 0], [0, -1j]], dtype=complex))

    @staticmethod
    def t() -> Gate:
        return Gate("t", 1, [], np.array([[1, 0], [0, np.exp(1j * math.pi / 4)]], dtype=complex))

    @staticmethod
    def tdg() -> Gate:
        return Gate("tdg", 1, [], np.array([[1, 0], [0, np.exp(-1j * math.pi / 4)]], dtype=complex))

    @staticmethod
    def sx() -> Gate:
        """Square-root of X gate."""
        m = np.array([[1 + 1j, 1 - 1j], [1 - 1j, 1 + 1j]], dtype=complex) / 2
        return Gate("sx", 1, [], m)

    # ---- Parameterised single-qubit gates ----

    @staticmethod
    def rx(theta: float) -> Gate:
        c, s = math.cos(theta / 2), math.sin(theta / 2)
        m = np.array([[c, -1j * s], [-1j * s, c]], dtype=complex)
        return Gate("rx", 1, [theta], m)

    @staticmethod
    def ry(theta: float) -> Gate:
        c, s = math.cos(theta / 2), math.sin(theta / 2)
        m = np.array([[c, -s], [s, c]], dtype=complex)
        return Gate("ry", 1, [theta], m)

    @staticmethod
    def rz(lam: float) -> Gate:
        m = np.array([[np.exp(-1j * lam / 2), 0], [0, np.exp(1j * lam / 2)]], dtype=complex)
        return Gate("rz", 1, [lam], m)

    @staticmethod
    def p(lam: float) -> Gate:
        """Phase gate P(λ) = diag(1, e^{iλ})."""
        m = np.array([[1, 0], [0, np.exp(1j * lam)]], dtype=complex)
        return Gate("p", 1, [lam], m)

    @staticmethod
    def u1(lam: float) -> Gate:
        """IBM-style U1 gate (phase gate up to global phase)."""
        m = np.array([[1, 0], [0, np.exp(1j * lam)]], dtype=complex)
        return Gate("u1", 1, [lam], m)

    @staticmethod
    def u2(phi: float, lam: float) -> Gate:
        s = 1 / math.sqrt(2)
        m = s * np.array(
            [[1, -np.exp(1j * lam)],
             [np.exp(1j * phi), np.exp(1j * (phi + lam))]],
            dtype=complex,
        )
        return Gate("u2", 1, [phi, lam], m)

    @staticmethod
    def u3(theta: float, phi: float, lam: float) -> Gate:
        """General single-qubit unitary (IBM U3 convention)."""
        c, s = math.cos(theta / 2), math.sin(theta / 2)
        m = np.array(
            [
                [c, -np.exp(1j * lam) * s],
                [np.exp(1j * phi) * s, np.exp(1j * (phi + lam)) * c],
            ],
            dtype=complex,
        )
        return Gate("u3", 1, [theta, phi, lam], m)

    # ---- Two-qubit gates ----

    @staticmethod
    def cx() -> Gate:
        """Controlled-X (CNOT). Control = qubit 0, target = qubit 1."""
        m = np.array(
            [[1, 0, 0, 0],
             [0, 1, 0, 0],
             [0, 0, 0, 1],
             [0, 0, 1, 0]],
            dtype=complex,
        )
        return Gate("cx", 2, [], m)

    @staticmethod
    def cy() -> Gate:
        m = np.array(
            [[1, 0, 0, 0],
             [0, 1, 0, 0],
             [0, 0, 0, -1j],
             [0, 0, 1j, 0]],
            dtype=complex,
        )
        return Gate("cy", 2, [], m)

    @staticmethod
    def cz() -> Gate:
        m = np.diag([1, 1, 1, -1]).astype(complex)
        return Gate("cz", 2, [], m)

    @staticmethod
    def swap() -> Gate:
        m = np.array(
            [[1, 0, 0, 0],
             [0, 0, 1, 0],
             [0, 1, 0, 0],
             [0, 0, 0, 1]],
            dtype=complex,
        )
        return Gate("swap", 2, [], m)

    @staticmethod
    def cp(lam: float) -> Gate:
        """Controlled-phase gate."""
        m = np.diag([1, 1, 1, np.exp(1j * lam)]).astype(complex)
        return Gate("cp", 2, [lam], m)

    @staticmethod
    def crz(lam: float) -> Gate:
        m = np.array(
            [[1, 0, 0, 0],
             [0, 1, 0, 0],
             [0, 0, np.exp(-1j * lam / 2), 0],
             [0, 0, 0, np.exp(1j * lam / 2)]],
            dtype=complex,
        )
        return Gate("crz", 2, [lam], m)

    # ---- Three-qubit gates ----

    @staticmethod
    def ccx() -> Gate:
        """Toffoli gate (CCX / CCNOT)."""
        m = np.eye(8, dtype=complex)
        m[6, 6], m[6, 7] = 0, 1
        m[7, 6], m[7, 7] = 1, 0
        return Gate("ccx", 3, [], m)

    @staticmethod
    def cswap() -> Gate:
        """Fredkin gate (Controlled-SWAP)."""
        m = np.eye(8, dtype=complex)
        m[5, 5], m[5, 6] = 0, 1
        m[6, 5], m[6, 6] = 1, 0
        return Gate("cswap", 3, [], m)

    # ---- Pseudo-gate ----

    @staticmethod
    def barrier(num_qubits: int) -> Gate:
        return Gate("barrier", num_qubits, [], None, is_barrier=True)

    @staticmethod
    def measure() -> Gate:
        """Measurement pseudo-gate (not unitary)."""
        return Gate("measure", 1, [], None)

    # ---- Lookup by name ----

    _FIXED_GATES = {
        "id", "x", "y", "z", "h", "s", "sdg", "t", "tdg", "sx",
        "cx", "cy", "cz", "swap", "ccx", "cswap",
    }
    _PARAM_GATES = {"rx", "ry", "rz", "p", "u1", "u2", "u3", "cp", "crz"}

    @classmethod
    def get(cls, name: str, params: Optional[List[float]] = None) -> Gate:
        """Look up a standard gate by name.

        Parameters
        ----------
        name : str
            Case-insensitive gate name.
        params : list of float, optional
            Parameters for parameterised gates.
        """
        name = name.lower()
        params = params or []
        fixed = {
            "id": cls.id, "x": cls.x, "y": cls.y, "z": cls.z,
            "h": cls.h, "s": cls.s, "sdg": cls.sdg, "t": cls.t, "tdg": cls.tdg,
            "sx": cls.sx, "cx": cls.cx, "cy": cls.cy, "cz": cls.cz,
            "swap": cls.swap, "ccx": cls.ccx, "cswap": cls.cswap,
        }
        if name in fixed:
            return fixed[name]()
        parameterised = {
            "rx": lambda p: cls.rx(p[0]),
            "ry": lambda p: cls.ry(p[0]),
            "rz": lambda p: cls.rz(p[0]),
            "p": lambda p: cls.p(p[0]),
            "u1": lambda p: cls.u1(p[0]),
            "u2": lambda p: cls.u2(p[0], p[1]),
            "u3": lambda p: cls.u3(p[0], p[1], p[2]),
            "cp": lambda p: cls.cp(p[0]),
            "crz": lambda p: cls.crz(p[0]),
        }
        if name in parameterised:
            return parameterised[name](params)
        raise ValueError(f"Unknown standard gate: '{name}'")
