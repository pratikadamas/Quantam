import csv
import json
import os
import random
import numpy as np
from qiskit import QuantumCircuit, transpile, qasm2
from qiskit_aer import Aer
from qiskit.visualization import circuit_drawer

# ===================== CONFIGURATION =====================
NUM_CIRCUITS = 100
NUM_QUBITS = 5
SHOTS = 1024
CSV_FILENAME = "circuit_results.csv"
IMG_DIR = "circuit_images"
SIMULATOR = Aer.get_backend('qasm_simulator')

# Probabilities for gate sizes (adjust as you like)
P_SINGLE = 0.6      # rx, ry, rz on 1 qubit
P_TWO = 0.25         # cx (CNOT)
P_THREE = 0.08       # ccx (Toffoli, 3-qubit)
P_FOUR = 0.05        # mcx with 3 controls (4-qubit)
P_FIVE = 0.02        # mcx with 4 controls (5-qubit)

# ===================== CIRCUIT GENERATION =====================
def random_angle():
    return random.uniform(0, 2 * np.pi)

def random_single_qubit_gate(circuit, qubit):
    gate = random.choice(['rx', 'ry', 'rz'])
    angle = random_angle()
    if gate == 'rx':
        circuit.rx(angle, qubit)
    elif gate == 'ry':
        circuit.ry(angle, qubit)
    else:
        circuit.rz(angle, qubit)

def random_two_qubit_gate(circuit, q1, q2):
    circuit.cx(q1, q2)

def random_three_qubit_gate(circuit, q1, q2, q3):
    circuit.ccx(q1, q2, q3)

def random_four_qubit_gate(circuit, q1, q2, q3, q4):
    circuit.mcx([q1, q2, q3], q4)   # 3 controls, 1 target

def random_five_qubit_gate(circuit, q1, q2, q3, q4, q5):
    circuit.mcx([q1, q2, q3, q4], q5)   # 4 controls, 1 target

def generate_random_circuit():
    """5‑qubit circuit with parallel layers of gates sized 1 to 5."""
    circuit = QuantumCircuit(NUM_QUBITS)
    depth = random.randint(5, 15)   # number of layers

    for _ in range(depth):
        free_qubits = set(range(NUM_QUBITS))
        layer_gates = []   # (gate_function, qubit_list)

        while free_qubits:
            # Choose gate size according to probabilities
            r = random.random()
            if r < P_SINGLE:
                size = 1
            elif r < P_SINGLE + P_TWO:
                size = 2
            elif r < P_SINGLE + P_TWO + P_THREE:
                size = 3
            elif r < P_SINGLE + P_TWO + P_THREE + P_FOUR:
                size = 4
            else:
                size = 5

            if len(free_qubits) < size:
                break   # not enough qubits left

            chosen = sorted(random.sample(list(free_qubits), size))
            free_qubits -= set(chosen)

            # Pick the appropriate gate function
            if size == 1:
                fn = random_single_qubit_gate
            elif size == 2:
                fn = random_two_qubit_gate
            elif size == 3:
                fn = random_three_qubit_gate
            elif size == 4:
                fn = random_four_qubit_gate
            else:
                fn = random_five_qubit_gate

            layer_gates.append((fn, chosen))

        # Apply all gates of this layer (they act on disjoint qubits → parallel)
        for gate_fn, qubits in layer_gates:
            gate_fn(circuit, *qubits)

        circuit.barrier()   # optional visual separation between layers

    # ✅ FIX 1: Add measurements — the qasm_simulator REQUIRES classical
    #           measurement operations to produce counts.
    circuit.measure_all()

    return circuit

# ===================== SIMULATION =====================
def simulate_circuit(circuit):
    """Run on the local simulator and return counts dictionary."""
    transpiled = transpile(circuit, SIMULATOR)
    job = SIMULATOR.run(transpiled, shots=SHOTS)
    # ✅ FIX 2: Don't pass the transpiled circuit object as key;
    #           just call get_counts() with no args (single circuit).
    return job.result().get_counts()

# ===================== DRAWING & SAVING IMAGES =====================
def draw_circuit(circuit, filepath):
    """Save a matplotlib drawing of the circuit as a PNG."""
    circuit_drawer(circuit, output='mpl', filename=filepath)

# ===================== CSV STORAGE =====================
def save_results_to_csv(data, filename):
    fieldnames = ['circuit_id', 'circuit_qasm', 'theoretical_counts',
                  'practical_counts', 'image_path']
    with open(filename, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction='ignore')
        writer.writeheader()
        writer.writerows(data)

# ===================== MAIN =====================
def main():
    os.makedirs(IMG_DIR, exist_ok=True)
    all_results = []

    print(f"Generating and simulating {NUM_CIRCUITS} random circuits...")
    for i in range(NUM_CIRCUITS):
        # 1. Create circuit
        qc = generate_random_circuit()

        # 2. Draw and save image
        img_path = os.path.join(IMG_DIR, f"circuit_{i:03d}.png")
        draw_circuit(qc, img_path)

        # 3. Simulate
        counts = simulate_circuit(qc)

        # 4. Prepare row for CSV
        row = {
            'circuit_id': i,
            # ✅ FIX 3: qc.qasm() is removed in Qiskit 1.x+;
            #           use qasm2.dumps() instead.
            'circuit_qasm': qasm2.dumps(qc),
            'theoretical_counts': json.dumps(counts),
            'practical_counts': json.dumps({}),   # placeholder for future hardware run
            'image_path': img_path
        }
        all_results.append(row)

        if (i+1) % 10 == 0:
            print(f"  {i+1}/{NUM_CIRCUITS} done.")

    # 5. Write CSV
    save_results_to_csv(all_results, CSV_FILENAME)
    print(f"\n✅ All results saved to {CSV_FILENAME}")
    print(f"✅ Circuit images saved in folder: {IMG_DIR}")

if __name__ == "__main__":
    main()
