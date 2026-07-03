"""Flask application configuration for ZNE Lab."""

import os

BASE_DIR = os.path.abspath(os.path.dirname(__file__))


class Config:
    """Base configuration."""
    SECRET_KEY = os.environ.get('SECRET_KEY', 'zne-lab-secret-key-change-in-production')
    SQLALCHEMY_DATABASE_URI = f"sqlite:///{os.path.join(BASE_DIR, 'instance', 'zne.db')}"
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    REPORTS_DIR = os.path.join(BASE_DIR, 'reports')

    # Default ZNE parameters
    DEFAULT_SCALE_FACTORS = [1, 2, 3, 4, 5]
    DEFAULT_FOLDING_METHOD = 'global'
    DEFAULT_EXTRAPOLATION_METHOD = 'polynomial'
    DEFAULT_NOISE_ERROR_RATE = 0.02
    DEFAULT_SHOTS = 8192
    DEFAULT_POLY_DEGREE = 2

    @staticmethod
    def init_app(app):
        """Ensure required directories exist."""
        os.makedirs(os.path.join(BASE_DIR, 'instance'), exist_ok=True)
        os.makedirs(os.path.join(BASE_DIR, 'reports'), exist_ok=True)
