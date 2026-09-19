"""
base_pass.py — Abstract base class for transformation passes and PassManager.

Every optimization pass subclasses TransformationPass and implements run().
The PassManager chains passes and applies them to a DAGCircuit.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List

from qcompiler.dag.dag_circuit import DAGCircuit


class TransformationPass(ABC):
    """Base class for all DAG transformation (optimization) passes.

    Subclasses must implement :meth:`run` which receives a DAGCircuit,
    modifies it in-place (or returns a new one), and returns it.
    """

    @property
    def name(self) -> str:
        return self.__class__.__name__

    @abstractmethod
    def run(self, dag: DAGCircuit) -> DAGCircuit:
        """Apply the pass to the DAG and return the (modified) DAG."""
        ...

    def __repr__(self) -> str:
        return f"{self.name}()"


class PassManager:
    """Chains multiple TransformationPass instances and runs them in order.

    Parameters
    ----------
    passes : list of TransformationPass
        The passes to apply, in order.

    Examples
    --------
    >>> pm = PassManager([RemoveBarriers(), CancelInverses(), MergeRotations()])
    >>> optimized_dag = pm.run(dag)
    """

    def __init__(self, passes: List[TransformationPass] | None = None) -> None:
        self._passes: List[TransformationPass] = list(passes) if passes else []

    def append(self, pass_: TransformationPass) -> "PassManager":
        self._passes.append(pass_)
        return self

    def run(self, dag: DAGCircuit) -> DAGCircuit:
        """Run all passes sequentially on the DAG."""
        for p in self._passes:
            dag = p.run(dag)
        return dag

    def __repr__(self) -> str:
        names = ", ".join(p.name for p in self._passes)
        return f"PassManager([{names}])"
