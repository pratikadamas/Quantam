"""Bell state example."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from qcompiler import QuantumCircuit, compile

qc = QuantumCircuit(2, 2, name="bell_state")
qc.h(0)
qc.cx(0, 1)
qc.measure(0, 0)
qc.measure(1, 1)

result = compile(qc, optimization_level=1)
print(result)
