"""Quantum ZNE Lab — Flask application.

Main entry point: routes for the experiment UI, API endpoints for
running ZNE experiments, and experiment history dashboard.
"""

from __future__ import annotations
import json
import traceback

from flask import Flask, render_template, request, jsonify, send_file
from config import Config
from models import db, Experiment
from zne.folding import fold_global, fold_local
from zne.executor import execute_with_noise, execute_ideal, build_noise_model
from zne.extrapolation import extrapolate
from zne.report import generate_pdf_report


def create_app() -> Flask:
    """Application factory."""
    app = Flask(__name__)
    app.config.from_object(Config)
    Config.init_app(app)

    db.init_app(app)
    with app.app_context():
        db.create_all()

    register_routes(app)
    return app


def register_routes(app: Flask):
    """Register all routes on the app."""

    # ── Page routes ─────────────────────────────────────────────

    @app.route('/')
    def index():
        """Main experiment page."""
        return render_template('index.html')

    @app.route('/dashboard')
    def dashboard():
        """Experiment history dashboard."""
        experiments = Experiment.query.order_by(Experiment.created_at.desc()).all()
        return render_template('dashboard.html', experiments=experiments)

    # ── API routes ──────────────────────────────────────────────

    @app.route('/api/run', methods=['POST'])
    def run_experiment():
        """Execute a ZNE experiment.

        Expects JSON body:
        {
            "name": "My Experiment",
            "circuit_code": "from qiskit import QuantumCircuit\\nqc = ...",
            "folding_method": "global" | "local",
            "scale_factors": [1, 2, 3, 4, 5],
            "extrapolation_method": "linear" | "polynomial" | "exponential",
            "poly_degree": 2,
            "noise_error_rate": 0.02,
            "shots": 8192
        }
        """
        try:
            data = request.get_json()
            if not data:
                return jsonify({'error': 'No JSON data provided'}), 400

            # Extract parameters
            name = data.get('name', 'Untitled Experiment')
            circuit_code = data.get('circuit_code', '')
            folding_method = data.get('folding_method', Config.DEFAULT_FOLDING_METHOD)
            scale_factors = data.get('scale_factors', Config.DEFAULT_SCALE_FACTORS)
            extrap_method = data.get('extrapolation_method', Config.DEFAULT_EXTRAPOLATION_METHOD)
            poly_degree = int(data.get('poly_degree', Config.DEFAULT_POLY_DEGREE))
            noise_error_rate = float(data.get('noise_error_rate', Config.DEFAULT_NOISE_ERROR_RATE))
            shots = int(data.get('shots', Config.DEFAULT_SHOTS))

            if not circuit_code.strip():
                return jsonify({'error': 'Circuit code is required'}), 400

            # Create experiment record
            experiment = Experiment(
                name=name,
                circuit_code=circuit_code,
                folding_method=folding_method,
                extrapolation_method=extrap_method,
                poly_degree=poly_degree,
                noise_error_rate=noise_error_rate,
                shots=shots,
                status='running',
            )
            experiment.set_scale_factors(scale_factors)
            db.session.add(experiment)
            db.session.commit()

            # ── Build the quantum circuit from user code ──
            circuit = _build_circuit(circuit_code)

            # ── Build noise model ──
            noise_model = build_noise_model(noise_error_rate)

            # ── Fold selection ──
            fold_fn = fold_global if folding_method == 'global' else fold_local

            # ── Execute at each scale factor ──
            noisy_values = []
            for sf in scale_factors:
                folded_circuit = fold_fn(circuit, sf)
                exp_val = execute_with_noise(
                    folded_circuit,
                    noise_model=noise_model,
                    shots=shots,
                )
                noisy_values.append(exp_val)

            # ── Get ideal result ──
            ideal_value = execute_ideal(circuit, shots=shots)

            # ── Extrapolate to zero noise ──
            extrap_result = extrapolate(
                scale_factors, noisy_values,
                method=extrap_method,
                degree=poly_degree,
            )

            # ── Save results ──
            experiment.set_noisy_results(noisy_values)
            experiment.mitigated_result = extrap_result['mitigated_value']
            experiment.ideal_result = ideal_value
            experiment.set_fit_curve_data(extrap_result['curve_points'])
            experiment.status = 'completed'
            db.session.commit()

            return jsonify({
                'success': True,
                'experiment': experiment.to_dict(),
                'extrapolation': {
                    'method': extrap_result['method'],
                    'fit_params': extrap_result['fit_params'],
                },
            })

        except Exception as e:
            # Save error state
            if 'experiment' in locals():
                experiment.status = 'failed'
                experiment.error_message = str(e)
                db.session.commit()

            traceback.print_exc()
            return jsonify({'error': str(e)}), 500

    @app.route('/api/experiments', methods=['GET'])
    def list_experiments():
        """List all experiments."""
        experiments = Experiment.query.order_by(Experiment.created_at.desc()).all()
        return jsonify([e.to_dict() for e in experiments])

    @app.route('/api/experiment/<int:exp_id>', methods=['GET'])
    def get_experiment(exp_id):
        """Get a single experiment by ID."""
        experiment = Experiment.query.get_or_404(exp_id)
        return jsonify(experiment.to_dict())

    @app.route('/api/experiment/<int:exp_id>', methods=['DELETE'])
    def delete_experiment(exp_id):
        """Delete an experiment."""
        experiment = Experiment.query.get_or_404(exp_id)
        db.session.delete(experiment)
        db.session.commit()
        return jsonify({'success': True})

    @app.route('/api/report/<int:exp_id>', methods=['GET'])
    def download_report(exp_id):
        """Generate and download a PDF report."""
        experiment = Experiment.query.get_or_404(exp_id)
        if experiment.status != 'completed':
            return jsonify({'error': 'Experiment not completed'}), 400

        filepath = generate_pdf_report(experiment.to_dict(), Config.REPORTS_DIR)
        return send_file(filepath, as_attachment=True, download_name=f'zne_report_{exp_id}.pdf')

    @app.route('/api/templates', methods=['GET'])
    def get_circuit_templates():
        """Return pre-built circuit templates."""
        templates = {
            'bell_state': {
                'name': 'Bell State (2 qubits)',
                'code': '''from qiskit import QuantumCircuit

qc = QuantumCircuit(2)
qc.h(0)
qc.cx(0, 1)
''',
            },
            'ghz_state': {
                'name': 'GHZ State (3 qubits)',
                'code': '''from qiskit import QuantumCircuit

qc = QuantumCircuit(3)
qc.h(0)
qc.cx(0, 1)
qc.cx(1, 2)
''',
            },
            'random_circuit': {
                'name': 'Random Circuit (2 qubits)',
                'code': '''from qiskit import QuantumCircuit
import numpy as np

qc = QuantumCircuit(2)
qc.rx(np.pi/4, 0)
qc.ry(np.pi/3, 1)
qc.cx(0, 1)
qc.rz(np.pi/6, 0)
qc.h(1)
''',
            },
            'variational': {
                'name': 'Variational Ansatz (2 qubits)',
                'code': '''from qiskit import QuantumCircuit
import numpy as np

qc = QuantumCircuit(2)
# Layer 1
qc.ry(np.pi/4, 0)
qc.ry(np.pi/3, 1)
qc.cx(0, 1)
# Layer 2
qc.ry(np.pi/6, 0)
qc.ry(np.pi/5, 1)
qc.cx(1, 0)
''',
            },
            'quantum_fourier': {
                'name': 'QFT (3 qubits)',
                'code': '''from qiskit import QuantumCircuit
import numpy as np

qc = QuantumCircuit(3)
# Initialize with some state
qc.x(0)
qc.x(2)

# QFT
qc.h(0)
qc.cp(np.pi/2, 1, 0)
qc.cp(np.pi/4, 2, 0)
qc.h(1)
qc.cp(np.pi/2, 2, 1)
qc.h(2)
qc.swap(0, 2)
''',
            },
        }
        return jsonify(templates)


def _build_circuit(code: str):
    """Execute user code and extract the QuantumCircuit.

    The user code must define a variable named `qc` that is
    a qiskit.QuantumCircuit instance.

    WARNING: This uses exec() which can run arbitrary code.
    Only suitable for trusted / local environments.
    """
    # pyrefly: ignore [missing-import]
    from qiskit import QuantumCircuit
    import numpy as np

    local_ns = {'QuantumCircuit': QuantumCircuit, 'np': np}
    exec(code, {'__builtins__': __builtins__}, local_ns)

    if 'qc' not in local_ns:
        raise ValueError(
            "Circuit code must define a variable named 'qc' "
            "as a QuantumCircuit instance."
        )

    circuit = local_ns['qc']
    if not isinstance(circuit, QuantumCircuit):
        raise TypeError(f"'qc' must be a QuantumCircuit, got {type(circuit).__name__}")

    return circuit


# ── Entry point ────────────────────────────────────────────────

app = create_app()

if __name__ == '__main__':
    app.run(debug=True, port=5000)
