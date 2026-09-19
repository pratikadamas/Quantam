"""n-qubit GHZ state example."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from qcompiler import QuantumCircuit, compile

def ghz(n: int):
    qc = QuantumCircuit(n, n, name=f"ghz_{n}")
    qc.h(0)
    for i in range(n - 1):
        qc.cx(i, i + 1)
    qc.measure_all()
    return qc

qc = ghz(4)
result = compile(qc, optimization_level=1)
print(result)
