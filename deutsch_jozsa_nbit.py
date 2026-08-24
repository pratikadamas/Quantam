import random
from qiskit import QuantumCircuit, transpile
from qiskit_aer import AerSimulator

def create_dj_oracle(n: int, case: str = "balanced", bitstring: str = None) -> QuantumCircuit:
    """
    Creates an n-bit Deutsch-Jozsa Oracle.
    
    Parameters
    ----------
    n : int
        Number of input qubits.
    case : str
        'constant' or 'balanced'.
    bitstring : str, optional
        A binary string of length n used to customize balanced oracle behavior.
        If None, a random bitstring is generated.
        
    Returns
    -------
    QuantumCircuit
        An (n+1)-qubit circuit representing the oracle U_f.
    """
    # (n + 1) qubits: q_0 .. q_{n-1} are input, q_n is ancilla
    oracle_circuit = QuantumCircuit(n + 1, name=f"Oracle ({case})")

    if case == "constant":
        # Randomly pick f(x) = 0 or f(x) = 1
        output = random.choice([0, 1])
        if output == 1:
            oracle_circuit.x(n) # Flip ancilla qubit unconditionally
    elif case == "balanced":
        if bitstring is None:
            # Generate a random bitstring mask of length n
            bitstring = "".join(random.choice(['0', '1']) for _ in range(n))
        
        # Place X-gates to wrap qubits where bitstring has '1'
        for qubit_idx, bit in enumerate(bitstring):
            if bit == '1':
                oracle_circuit.x(qubit_idx)
        
        oracle_circuit.barrier()
        
        # Apply CNOT from each input qubit to the ancilla qubit
        for qubit_idx in range(n):
            oracle_circuit.cx(qubit_idx, n)
            
        oracle_circuit.barrier()
        
        # Un-wrap X-gates
        for qubit_idx, bit in enumerate(bitstring):
            if bit == '1':
                oracle_circuit.x(qubit_idx)
    else:
        raise ValueError("case must be 'constant' or 'balanced'")

    return oracle_circuit


def build_deutsch_jozsa_circuit(n: int, oracle_gate) -> QuantumCircuit:
    """
    Constructs the full n-bit Deutsch-Jozsa quantum circuit.
    
    Parameters
    ----------
    n : int
        Number of input qubits.
    oracle_gate : Gate or QuantumCircuit
        The (n+1)-qubit oracle circuit/gate.
        
    Returns
    -------
    QuantumCircuit
        Full circuit with state prep, oracle, inverse Hadamard, and measurement.
    """
    # n input qubits + 1 ancilla qubit, n classical bits
    circuit = QuantumCircuit(n + 1, n)

    # Step 1: Initialize ancilla qubit to |1>
    circuit.x(n)

    # Step 2: Apply Hadamard gates to all (n + 1) qubits
    for i in range(n + 1):
        circuit.h(i)

    circuit.barrier()

    # Step 3: Apply Oracle U_f
    circuit.append(oracle_gate, range(n + 1))

    circuit.barrier()

    # Step 4: Apply Hadamard gates to input qubits (q_0 .. q_{n-1})
    for i in range(n):
        circuit.h(i)

    circuit.barrier()

    # Step 5: Measure all input qubits into classical bits
    for i in range(n):
        circuit.measure(i, i)

    return circuit


def run_deutsch_jozsa(n: int, case: str = "balanced", shots: int = 1024):
    """
    Builds, transpiles, and runs an n-bit Deutsch-Jozsa algorithm simulation.
    """
    # 1. Create Oracle
    oracle = create_dj_oracle(n, case=case)
    
    # 2. Build full DJ circuit
    dj_circuit = build_deutsch_jozsa_circuit(n, oracle)
    
    # 3. Simulate on AerSimulator
    simulator = AerSimulator()
    transpiled_circuit = transpile(dj_circuit, simulator)
    job = simulator.run(transpiled_circuit, shots=shots)
    counts = job.result().get_counts()
    
    # Determine result: all '0's means constant, otherwise balanced
    all_zeros = '0' * n
    measured_type = "constant" if (all_zeros in counts and counts[all_zeros] == shots) else "balanced"
    
    print(f"--- {n}-Bit Deutsch-Jozsa Execution ---")
    print(f"Target Oracle Type: {case}")
    print(f"Measurement Counts: {counts}")
    print(f"Measured Function Type: {measured_type}")
    print(f"Result: {'PASS' if measured_type == case else 'FAIL'}\n")
    return dj_circuit, counts


if __name__ == "__main__":
    print("Testing 4-bit Constant Oracle:")
    run_deutsch_jozsa(n=4, case="constant")
    
    print("Testing 4-bit Balanced Oracle:")
    run_deutsch_jozsa(n=4, case="balanced")
    
    print("Testing 8-bit Balanced Oracle:")
    run_deutsch_jozsa(n=8, case="balanced")
