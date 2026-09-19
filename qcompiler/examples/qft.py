"""Quantum Fourier Transform (QFT) example."""
import sys, os, math
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from qcompiler import QuantumCircuit, compile

def qft(n: int) -> QuantumCircuit:
    qc = QuantumCircuit(n, name=f"qft_{n}")
    for j in range(n):
        qc.h(j)
        for k in range(j + 1, n):
            angle = math.pi / (2 ** (k - j))
            qc.cp(angle, k, j)
    # Swap to bit-reverse
    for i in range(n // 2):
        qc.swap(i, n - i - 1)
    return qc

qc = qft(4)
result = compile(qc, optimization_level=1)
print(result)
