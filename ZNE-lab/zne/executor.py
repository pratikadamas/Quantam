"""Noisy circuit execution using Qiskit Aer.

Provides functions to build noise models and execute quantum circuits
with depolarizing noise on the AerSimulator.
"""
# pyright: ignore [reportMissingImports]
from __future__ import annotations
# pyrefly: ignore [missing-import]
from qiskit import QuantumCircuit
# pyrefly: ignore [missing-import]
from qiskit.transpiler.preset_passmanagers import generate_preset_pass_manager
# pyrefly: ignore [missing-import]
from qiskit_aer import AerSimulator
# pyrefly: ignore [missing-import]
from qiskit_aer.noise import NoiseModel, depolarizing_error

# Creates a noise model.
# That's depolarizing noise. add noise evey gate
# ---------------------------------------------------------------------    
def build_noise_model(error_rate: float = 0.02) -> NoiseModel:
    """Create a depolarizing noise model.

    Args:
        error_rate: Single-qubit depolarizing error probability.
                    Two-qubit error is set to 2× this value.

    Returns:
        A Qiskit NoiseModel with depolarizing errors on all gates.
    """
    noise_model = NoiseModel()

    # Single-qubit depolarizing error
    error_1q = depolarizing_error(error_rate, 1)
    # Two-qubit depolarizing error (typically higher)
    error_2q = depolarizing_error(min(error_rate * 2, 1.0), 2)

    # Apply to common gate sets
    single_qubit_gates = ['u1', 'u2', 'u3', 'rx', 'ry', 'rz', 'x', 'y', 'z',
                          'h', 's', 'sdg', 't', 'tdg', 'id', 'sx', 'sxdg']
    two_qubit_gates = ['cx', 'cz', 'cy', 'swap', 'ecr', 'rzz']

    for gate in single_qubit_gates:
        noise_model.add_all_qubit_quantum_error(error_1q, gate)
    for gate in two_qubit_gates:
        noise_model.add_all_qubit_quantum_error(error_2q, gate)

    return noise_model

# Quantum simulators need measurements.
# Create noisy simulator.
# may not be directly supported.
# Transpiler converts it into backend-supported gate
# --------------------------------
def execute_with_noise(
    circuit: QuantumCircuit,
    noise_model: NoiseModel | None = None,
    shots: int = 8192,
    error_rate: float = 0.02,
) -> float:
    """Execute a quantum circuit on the noisy AerSimulator.

    The expectation value is computed as:
        <Z> = (count_of_|0⟩ - count_of_|1⟩) / total_shots

    For multi-qubit circuits, this computes the expectation value of
    Z⊗Z⊗...⊗Z (all-zeros bitstring probability-based).

    Args:
        circuit: A quantum circuit (must include measurements).
        noise_model: Optional noise model. Built from error_rate if None.
        shots: Number of measurement shots.
        error_rate: Depolarizing error rate (used if noise_model is None).

    Returns:
        The expectation value as a float.
    """
    if noise_model is None:
        noise_model = build_noise_model(error_rate)

    # Ensure circuit has measurements
    meas_circuit = _ensure_measurements(circuit)

    # Create noisy simulator backend
    backend = AerSimulator(noise_model=noise_model)

    # Transpile for the backend
    pm = generate_preset_pass_manager(optimization_level=1, backend=backend)
    transpiled = pm.run(meas_circuit)

    # Execute
    result = backend.run(transpiled, shots=shots).result()
    counts = result.get_counts()

    return _counts_to_expectation(counts, shots)

#1.copair the circuit 
# Ideal result
# vs
# Noisy result
#---------------------------------------------------------------------
def execute_ideal(circuit: QuantumCircuit, shots: int = 8192) -> float:
    """Execute a circuit on a noiseless simulator for reference.

    Args:
        circuit: A quantum circuit.
        shots: Number of shots.

    Returns:
        The ideal expectation value.
    """
    meas_circuit = _ensure_measurements(circuit)
    backend = AerSimulator()
    pm = generate_preset_pass_manager(optimization_level=1, backend=backend)
    transpiled = pm.run(meas_circuit)
    result = backend.run(transpiled, shots=shots).result()
    counts = result.get_counts()
    return _counts_to_expectation(counts, shots)


# qc.h(0)
# ⬇️
# qc.h(0)
#qc.measure_all()
# ----------------------
def _ensure_measurements(circuit: QuantumCircuit) -> QuantumCircuit:
    """Add measurement gates if the circuit doesn't have them."""
    has_measure = any(
        instr.operation.name == 'measure' for instr in circuit.data
    )
    if not has_measure:
        meas = circuit.copy()
        meas.measure_all()
        return meas
    return circuit.copy()


def _counts_to_expectation(counts: dict, shots: int) -> float:
    """Convert measurement counts to a Z-basis expectation value.

    For each bitstring, the eigenvalue is (-1)^(number of 1s).
    <Z⊗n> = Σ_b (-1)^|b| * count(b) / shots
    """
    expectation = 0.0
    for bitstring, count in counts.items():
        # Count number of '1' bits → parity
        parity = bitstring.count('1')
        eigenvalue = (-1) ** parity
        expectation += eigenvalue * count / shots
    return expectation
