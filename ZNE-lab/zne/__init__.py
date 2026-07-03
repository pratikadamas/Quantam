"""ZNE Engine — Zero Noise Extrapolation for quantum circuits.

Provides circuit folding, noisy execution, and extrapolation to the
zero-noise limit.
"""

from .folding import fold_global, fold_local
from .executor import execute_with_noise, build_noise_model
from .extrapolation import (
    linear_extrapolation,
    polynomial_extrapolation,
    exponential_extrapolation,
)
from .report import generate_pdf_report

__all__ = [
    'fold_global',
    'fold_local',
    'execute_with_noise',
    'build_noise_model',
    'linear_extrapolation',
    'polynomial_extrapolation',
    'exponential_extrapolation',
    'generate_pdf_report',
]
