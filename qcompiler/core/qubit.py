"""
qubit.py — Qubit and classical bit abstractions.

Qubits and Clbits are lightweight value objects identified by their
register name and index. They are immutable and hashable so they can
be used as DAG node keys and dictionary keys.
"""
from __future__ import annotations
from dataclasses import dataclass


@dataclass(frozen=True, order=True)
class Qubit:
    """A single quantum bit.

    Parameters
    ----------
    register : str
        Name of the qubit register this bit belongs to.
    index : int
        Zero-based position within the register.

    Examples
    --------
    >>> q0 = Qubit("q", 0)
    >>> q1 = Qubit("q", 1)
    >>> q0 == q1
    False
    """

    register: str
    index: int

    def __repr__(self) -> str:
        return f"Qubit({self.register!r}, {self.index})"

    def __str__(self) -> str:
        return f"{self.register}[{self.index}]"


@dataclass(frozen=True, order=True)
class Clbit:
    """A single classical bit.

    Parameters
    ----------
    register : str
        Name of the classical register.
    index : int
        Zero-based position within the register.
    """

    register: str
    index: int

    def __repr__(self) -> str:
        return f"Clbit({self.register!r}, {self.index})"

    def __str__(self) -> str:
        return f"{self.register}[{self.index}]"
