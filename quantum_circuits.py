"""
Quantum Circuit Simulations with Qiskit (No IBM Key Required)
=============================================================
All circuits run on the LOCAL Aer simulator.
Covers: Bell State, GHZ State, Quantum Teleportation,
        Deutsch-Jozsa, Bernstein-Vazirani, Grover's Search,
        Quantum Fourier Transform, and Quantum Phase Estimation.
"""

import numpy as np
import matplotlib
matplotlib.use('Agg')          # non-interactive backend for saving PNGs
import matplotlib.pyplot as plt
from qiskit import QuantumCircuit, transpile
from qiskit_aer import Aer
from qiskit.visualization import plot_histogram, circuit_drawer
import os

# ─── Global Settings ────────────────────────────────────────────────
SHOTS = 4096
SIM_QASM = Aer.get_backend('qasm_simulator')
SIM_SV   = Aer.get_backend('statevector_simulator')
OUT_DIR  = "quantum_outputs"
os.makedirs(OUT_DIR, exist_ok=True)


def run_and_plot(circuit, name, shots=SHOTS):
    """Transpile → simulate → print counts → save histogram + circuit image."""
    transpiled = transpile(circuit, SIM_QASM)
    job = SIM_QASM.run(transpiled, shots=shots)
    counts = job.result().get_counts()

    print(f"\n{'='*60}")
    print(f"  {name}")
    print(f"{'='*60}")
    print(f"  Qubits: {circuit.num_qubits}  |  Depth: {circuit.depth()}  |  Shots: {shots}")
    print(f"  Counts: {dict(sorted(counts.items(), key=lambda x: -x[1]))}")

    # Save circuit diagram
    circuit_path = os.path.join(OUT_DIR, f"{name.lower().replace(' ', '_')}_circuit.png")
    circuit_drawer(circuit, output='mpl', filename=circuit_path)
    print(f"  📐 Circuit saved → {circuit_path}")

    # Save histogram
    hist_path = os.path.join(OUT_DIR, f"{name.lower().replace(' ', '_')}_histogram.png")
    fig = plot_histogram(counts, title=name, figsize=(10, 5))
    fig.savefig(hist_path, dpi=150, bbox_inches='tight')
    plt.close(fig)
    print(f"  📊 Histogram saved → {hist_path}")

    return counts


# ═══════════════════════════════════════════════════════════════════
# 1. BELL STATE (|Φ⁺⟩ = (|00⟩ + |11⟩)/√2)
# ═══════════════════════════════════════════════════════════════════
def bell_state():
    """Creates maximal entanglement between 2 qubits.
    Expected output: ~50% |00⟩ and ~50% |11⟩ (never |01⟩ or |10⟩).
    """
    qc = QuantumCircuit(2, 2, name="Bell State")
    qc.h(0)          # Hadamard → superposition on q0
    qc.cx(0, 1)      # CNOT → entangle q0 and q1
    qc.barrier()
    qc.measure([0, 1], [0, 1])
    return run_and_plot(qc, "Bell State")


# ═══════════════════════════════════════════════════════════════════
# 2. GHZ STATE (|000⟩ + |111⟩)/√2  — 3-qubit entanglement
# ═══════════════════════════════════════════════════════════════════
def ghz_state(n=3):
    """Generalised GHZ: all qubits 0 or all qubits 1, nothing in between."""
    qc = QuantumCircuit(n, n, name=f"GHZ-{n}")
    qc.h(0)
    for i in range(1, n):
        qc.cx(0, i)
    qc.barrier()
    qc.measure(range(n), range(n))
    return run_and_plot(qc, f"GHZ State ({n}-qubit)")


# ═══════════════════════════════════════════════════════════════════
# 3. QUANTUM TELEPORTATION
# ═══════════════════════════════════════════════════════════════════
def quantum_teleportation():
    """Teleport |ψ⟩ = Ry(π/4)|0⟩ from q0 → q2 using entanglement + classical bits.
    After correction, q2 should match the original state of q0.
    """
    qc = QuantumCircuit(3, 3, name="Teleportation")

    # Prepare the state to teleport on q0
    qc.ry(np.pi / 4, 0)
    qc.barrier()

    # Create Bell pair between q1 and q2
    qc.h(1)
    qc.cx(1, 2)
    qc.barrier()

    # Alice's operations (q0, q1)
    qc.cx(0, 1)
    qc.h(0)
    qc.barrier()

    # Measure Alice's qubits
    qc.measure(0, 0)
    qc.measure(1, 1)
    qc.barrier()

    # Bob's corrections (classically controlled)
    qc.x(2).c_if(1, 1)    # if c1 == 1, apply X
    qc.z(2).c_if(0, 1)    # if c0 == 1, apply Z
    qc.barrier()

    # Measure Bob's qubit
    qc.measure(2, 2)
    return run_and_plot(qc, "Quantum Teleportation")


# ═══════════════════════════════════════════════════════════════════
# 4. DEUTSCH-JOZSA ALGORITHM
# ═══════════════════════════════════════════════════════════════════
def deutsch_jozsa(oracle_type="balanced"):
    """Determines if a function is CONSTANT or BALANCED in one query.
    - constant → all 0s measured
    - balanced → at least one non-zero measured
    """
    n = 3  # input qubits
    qc = QuantumCircuit(n + 1, n, name="Deutsch-Jozsa")

    # Initialise: input qubits in |+⟩, output qubit in |−⟩
    qc.x(n)               # output qubit → |1⟩
    qc.h(range(n + 1))    # all → superposition
    qc.barrier()

    # Oracle
    if oracle_type == "constant":
        pass  # f(x) = 0  → do nothing
    else:  # balanced
        # f(x) = x₀ ⊕ x₁ ⊕ x₂  (balanced)
        for i in range(n):
            qc.cx(i, n)
    qc.barrier()

    # Hadamard on input qubits + measure
    qc.h(range(n))
    qc.barrier()
    qc.measure(range(n), range(n))

    return run_and_plot(qc, f"Deutsch-Jozsa ({oracle_type})")


# ═══════════════════════════════════════════════════════════════════
# 5. BERNSTEIN-VAZIRANI ALGORITHM
# ═══════════════════════════════════════════════════════════════════
def bernstein_vazirani(secret="10110"):
    """Finds the hidden bit-string s in ONE query.
    f(x) = s·x (mod 2). Expected output = the secret string.
    """
    n = len(secret)
    qc = QuantumCircuit(n + 1, n, name="Bernstein-Vazirani")

    # Put auxiliary qubit in |−⟩
    qc.x(n)
    qc.h(range(n + 1))
    qc.barrier()

    # Oracle: CNOT from qubit i to auxiliary if secret[i] == '1'
    for i, bit in enumerate(reversed(secret)):
        if bit == '1':
            qc.cx(i, n)
    qc.barrier()

    # Hadamard + measure
    qc.h(range(n))
    qc.barrier()
    qc.measure(range(n), range(n))

    counts = run_and_plot(qc, f"Bernstein-Vazirani (s={secret})")
    top = max(counts, key=counts.get)
    print(f"  🔑 Recovered secret: {top}  (expected: {secret})")
    return counts


# ═══════════════════════════════════════════════════════════════════
# 6. GROVER'S SEARCH (2-qubit, target |11⟩)
# ═══════════════════════════════════════════════════════════════════
def grovers_search():
    """Finds |11⟩ among 4 states with high probability in ~1 iteration.
    Expected output: |11⟩ with ~100% probability.
    """
    qc = QuantumCircuit(2, 2, name="Grover Search")

    # Initialise superposition
    qc.h([0, 1])
    qc.barrier()

    # ── Oracle: mark |11⟩ (CZ gate) ──
    qc.cz(0, 1)
    qc.barrier()

    # ── Diffusion operator ──
    qc.h([0, 1])
    qc.z([0, 1])
    qc.cz(0, 1)
    qc.h([0, 1])
    qc.barrier()

    qc.measure([0, 1], [0, 1])
    return run_and_plot(qc, "Grover Search (target=11)")


# ═══════════════════════════════════════════════════════════════════
# 7. QUANTUM FOURIER TRANSFORM (QFT) — 3 qubit
# ═══════════════════════════════════════════════════════════════════
def qft_circuit(n=3):
    """Applies QFT to the state |5⟩ = |101⟩ and measures.
    QFT is the quantum analogue of the discrete Fourier transform.
    """
    qc = QuantumCircuit(n, n, name="QFT")

    # Encode |5⟩ = |101⟩
    qc.x(0)
    qc.x(2)
    qc.barrier()

    # QFT
    for i in range(n):
        qc.h(i)
        for j in range(i + 1, n):
            qc.cp(np.pi / (2 ** (j - i)), j, i)
        qc.barrier()

    # Swap to get correct bit ordering
    for i in range(n // 2):
        qc.swap(i, n - i - 1)

    qc.barrier()
    qc.measure(range(n), range(n))
    return run_and_plot(qc, "Quantum Fourier Transform")


# ═══════════════════════════════════════════════════════════════════
# 8. QUANTUM PHASE ESTIMATION (QPE)
# ═══════════════════════════════════════════════════════════════════
def quantum_phase_estimation():
    """Estimates the phase θ of U|ψ⟩ = e^{2πiθ}|ψ⟩.
    Here U = T gate (θ = 1/8), using 3 counting qubits.
    Expected output: |001⟩ = 1/8 in binary.
    """
    n_count = 3   # counting qubits
    qc = QuantumCircuit(n_count + 1, n_count, name="QPE")

    # Initialise eigenstate |1⟩ on target qubit
    qc.x(n_count)

    # Hadamard on counting qubits
    qc.h(range(n_count))
    qc.barrier()

    # Controlled-U^(2^k) operations
    for k in range(n_count):
        for _ in range(2 ** k):
            qc.cp(np.pi / 4, k, n_count)  # T gate has phase π/4
    qc.barrier()

    # Inverse QFT on counting qubits
    for i in range(n_count // 2):
        qc.swap(i, n_count - 1 - i)
    for i in range(n_count - 1, -1, -1):
        for j in range(i - 1, -1, -1):
            qc.cp(-np.pi / (2 ** (i - j)), i, j)
        qc.h(i)
    qc.barrier()

    qc.measure(range(n_count), range(n_count))

    counts = run_and_plot(qc, "Quantum Phase Estimation")
    top = max(counts, key=counts.get)
    estimated_phase = int(top, 2) / (2 ** n_count)
    print(f"  🎯 Estimated phase: {estimated_phase} (expected: 0.125 = 1/8)")
    return counts


# ═══════════════════════════════════════════════════════════════════
# 9. SUPERDENSE CODING
# ═══════════════════════════════════════════════════════════════════
def superdense_coding(message="11"):
    """Send 2 classical bits using 1 qubit + shared entanglement.
    Alice encodes, Bob decodes. Output should match the message.
    """
    qc = QuantumCircuit(2, 2, name="Superdense Coding")

    # Create Bell pair
    qc.h(0)
    qc.cx(0, 1)
    qc.barrier()

    # Alice encodes message on her qubit (q0)
    if message == "00":
        pass              # I  → |Φ⁺⟩
    elif message == "01":
        qc.x(0)          # X  → |Ψ⁺⟩
    elif message == "10":
        qc.z(0)          # Z  → |Φ⁻⟩
    elif message == "11":
        qc.x(0)          # XZ → |Ψ⁻⟩
        qc.z(0)
    qc.barrier()

    # Bob decodes
    qc.cx(0, 1)
    qc.h(0)
    qc.barrier()

    qc.measure([0, 1], [0, 1])
    counts = run_and_plot(qc, f"Superdense Coding (msg={message})")
    top = max(counts, key=counts.get)
    print(f"  📨 Decoded message: {top}  (sent: {message})")
    return counts


# ═══════════════════════════════════════════════════════════════════
# 10. STATEVECTOR VISUALIZATION (no measurement)
# ═══════════════════════════════════════════════════════════════════
def statevector_demo():
    """Visualise the full quantum state without collapsing it."""
    qc = QuantumCircuit(2, name="Statevector Demo")
    qc.h(0)
    qc.cx(0, 1)

    transpiled = transpile(qc, SIM_SV)
    job = SIM_SV.run(transpiled)
    sv = job.result().get_statevector()

    print(f"\n{'='*60}")
    print("  Statevector Demo (Bell State)")
    print(f"{'='*60}")
    print(f"  |ψ⟩ = {sv}")

    # Save Qsphere / bar plot
    from qiskit.visualization import plot_state_city
    fig = plot_state_city(sv, title="Bell State Amplitudes")
    sv_path = os.path.join(OUT_DIR, "statevector_city.png")
    fig.savefig(sv_path, dpi=150, bbox_inches='tight')
    plt.close(fig)
    print(f"  🌐 State city plot saved → {sv_path}")


# ═══════════════════════════════════════════════════════════════════
#  MAIN — run all demos
# ═══════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    print("╔══════════════════════════════════════════════════════════╗")
    print("║   Quantum Circuit Simulations — Local Aer Simulator    ║")
    print("║   No IBM API key required!                             ║")
    print("╚══════════════════════════════════════════════════════════╝")

    bell_state()
    ghz_state(3)
    quantum_teleportation()
    deutsch_jozsa("balanced")
    deutsch_jozsa("constant")
    bernstein_vazirani("10110")
    grovers_search()
    qft_circuit(3)
    quantum_phase_estimation()
    superdense_coding("11")
    statevector_demo()

    print(f"\n✅ All outputs saved to '{OUT_DIR}/' folder.")
    print("🎉 Done! Open the PNG files to see circuits & histograms.")
