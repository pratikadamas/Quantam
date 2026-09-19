"""
rules.py — Decomposition rule table for standard gates.

Each rule maps a gate name to a callable that takes the gate's params list
and returns a list of (gate_name, params, qubit_offsets) tuples.

qubit_offsets is a list of indices into the original gate's qubit list,
so decomposition rules are qubit-agnostic.

Basis gate set (target — not decomposed further):
  {id, x, y, z, h, s, sdg, t, tdg, cx, cz, rz, rx, ry, measure}
"""
from __future__ import annotations

import math
from typing import Callable, Dict, List, Tuple

# A DecompRule is: params → list of (gate_name, gate_params, qubit_indices)
DecompRule = Callable[[List[float]], List[Tuple[str, List[float], List[int]]]]

# Gates that are already in the basis set — no decomposition needed
BASIS_GATES = frozenset({
    "id", "x", "y", "z", "h", "s", "sdg", "t", "tdg",
    "cx", "cz", "rz", "rx", "ry",
    "barrier", "measure",
})


def _rule_sx(_: List[float]):
    """SX = H · S · H  (up to global phase, using basis gates)"""
    return [
        ("h",   [], [0]),
        ("s",   [], [0]),
        ("h",   [], [0]),
    ]


def _rule_p(params: List[float]):
    """P(λ) = Rz(λ)  (up to global phase)"""
    return [("rz", [params[0]], [0])]


def _rule_u1(params: List[float]):
    """U1(λ) = P(λ) = Rz(λ)"""
    return [("rz", [params[0]], [0])]


def _rule_u2(params: List[float]):
    """U2(φ, λ) = Rz(φ) · H · Rz(λ)  (up to global phase)"""
    phi, lam = params
    return [
        ("rz", [lam],  [0]),
        ("h",  [],     [0]),
        ("rz", [phi],  [0]),
    ]


def _rule_u3(params: List[float]):
    """U3(θ, φ, λ) = Rz(φ) · Ry(θ) · Rz(λ)"""
    theta, phi, lam = params
    return [
        ("rz", [lam],   [0]),
        ("ry", [theta], [0]),
        ("rz", [phi],   [0]),
    ]


def _rule_cy(_: List[float]):
    """CY = CX with S/Sdg wrapper on target."""
    return [
        ("sdg", [], [1]),
        ("cx",  [], [0, 1]),
        ("s",   [], [1]),
    ]


def _rule_swap(_: List[float]):
    """SWAP = 3×CX."""
    return [
        ("cx", [], [0, 1]),
        ("cx", [], [1, 0]),
        ("cx", [], [0, 1]),
    ]


def _rule_cz(_: List[float]):
    """CZ = H·CX·H on target."""
    return [
        ("h",  [], [1]),
        ("cx", [], [0, 1]),
        ("h",  [], [1]),
    ]


def _rule_cp(params: List[float]):
    """CP(λ) = controlled-phase decomposition."""
    lam = params[0]
    return [
        ("p",  [lam / 2], [0]),
        ("cx", [],        [0, 1]),
        ("p",  [-lam / 2],[1]),
        ("cx", [],        [0, 1]),
        ("p",  [lam / 2], [1]),
    ]


def _rule_crz(params: List[float]):
    """CRz(λ) decomposition."""
    lam = params[0]
    return [
        ("rz", [lam / 2],  [1]),
        ("cx", [],         [0, 1]),
        ("rz", [-lam / 2], [1]),
        ("cx", [],         [0, 1]),
    ]


def _rule_ccx(_: List[float]):
    """Toffoli (CCX) decomposition into CX, H, T, Tdg (standard 6-CX form)."""
    return [
        ("h",   [], [2]),
        ("cx",  [], [1, 2]),
        ("tdg", [], [2]),
        ("cx",  [], [0, 2]),
        ("t",   [], [2]),
        ("cx",  [], [1, 2]),
        ("tdg", [], [2]),
        ("cx",  [], [0, 2]),
        ("t",   [], [1]),
        ("t",   [], [2]),
        ("h",   [], [2]),
        ("cx",  [], [0, 1]),
        ("t",   [], [0]),
        ("tdg", [], [1]),
        ("cx",  [], [0, 1]),
    ]


def _rule_cswap(_: List[float]):
    """Fredkin (CSWAP) → CCX-based decomposition."""
    return [
        ("cx",  [], [2, 1]),
        ("ccx", [], [0, 1, 2]),
        ("cx",  [], [2, 1]),
    ]


DECOMPOSITION_RULES: Dict[str, DecompRule] = {
    "sx":    _rule_sx,
    "p":     _rule_p,
    "u1":    _rule_u1,
    "u2":    _rule_u2,
    "u3":    _rule_u3,
    "cy":    _rule_cy,
    "swap":  _rule_swap,
    "cz":    _rule_cz,
    "cp":    _rule_cp,
    "crz":   _rule_crz,
    "ccx":   _rule_ccx,
    "cswap": _rule_cswap,
}
