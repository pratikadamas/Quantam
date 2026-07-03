"""Database models for ZNE Lab experiments."""

import json
from datetime import datetime, timezone
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


class Experiment(db.Model):
    """Stores a single ZNE experiment run."""

    __tablename__ = 'experiments'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False, default='Untitled Experiment')
    circuit_code = db.Column(db.Text, nullable=False)
    folding_method = db.Column(db.String(50), nullable=False, default='global')
    scale_factors = db.Column(db.Text, nullable=False)          # JSON list
    extrapolation_method = db.Column(db.String(50), nullable=False, default='polynomial')
    poly_degree = db.Column(db.Integer, default=2)
    noise_error_rate = db.Column(db.Float, nullable=False, default=0.02)
    shots = db.Column(db.Integer, nullable=False, default=8192)

    # Results (stored as JSON)
    noisy_results = db.Column(db.Text, nullable=True)           # JSON list of expectation values
    mitigated_result = db.Column(db.Float, nullable=True)
    ideal_result = db.Column(db.Float, nullable=True)
    fit_curve_data = db.Column(db.Text, nullable=True)          # JSON for fitted curve points

    status = db.Column(db.String(20), nullable=False, default='pending')  # pending | running | completed | failed
    error_message = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

    def get_scale_factors(self):
        """Return scale_factors as a Python list."""
        return json.loads(self.scale_factors)

    def set_scale_factors(self, factors):
        """Store scale_factors from a Python list."""
        self.scale_factors = json.dumps(factors)

    def get_noisy_results(self):
        """Return noisy_results as a Python list."""
        if self.noisy_results:
            return json.loads(self.noisy_results)
        return []

    def set_noisy_results(self, results):
        """Store noisy_results from a Python list."""
        self.noisy_results = json.dumps(results)

    def get_fit_curve_data(self):
        """Return fit_curve_data as a Python dict."""
        if self.fit_curve_data:
            return json.loads(self.fit_curve_data)
        return {}

    def set_fit_curve_data(self, data):
        """Store fit_curve_data from a Python dict."""
        self.fit_curve_data = json.dumps(data)

    def to_dict(self):
        """Serialize experiment to a JSON-friendly dict."""
        return {
            'id': self.id,
            'name': self.name,
            'circuit_code': self.circuit_code,
            'folding_method': self.folding_method,
            'scale_factors': self.get_scale_factors(),
            'extrapolation_method': self.extrapolation_method,
            'poly_degree': self.poly_degree,
            'noise_error_rate': self.noise_error_rate,
            'shots': self.shots,
            'noisy_results': self.get_noisy_results(),
            'mitigated_result': self.mitigated_result,
            'ideal_result': self.ideal_result,
            'fit_curve_data': self.get_fit_curve_data(),
            'status': self.status,
            'error_message': self.error_message,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }
