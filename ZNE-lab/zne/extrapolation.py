"""Extrapolation methods for Zero Noise Extrapolation.

Fits noisy expectation values at different scale factors to a model,
then extrapolates to the zero-noise (λ=0) limit.
"""

from __future__ import annotations
import numpy as np
from scipy.optimize import curve_fit


def linear_extrapolation(
    scale_factors: list[float],
    expectation_values: list[float],
) -> dict:
    """Linear fit: E(λ) = a·λ + b, extrapolate to λ=0.

    Args:
        scale_factors: List of noise scale factors [1, 2, 3, ...].
        expectation_values: Corresponding noisy expectation values.

    Returns:
        Dict with 'mitigated_value', 'fit_params', and 'curve_points'.
    """
    factors = np.array(scale_factors, dtype=float)
    values = np.array(expectation_values, dtype=float)

    coeffs = np.polyfit(factors, values, deg=1)
    poly = np.poly1d(coeffs)

    mitigated = float(poly(0))

    # Generate smooth curve for plotting
    x_plot = np.linspace(0, max(factors) * 1.1, 100)
    y_plot = poly(x_plot)

    return {
        'mitigated_value': mitigated,
        'fit_params': {'coefficients': coeffs.tolist()},
        'curve_points': {
            'x': x_plot.tolist(),
            'y': y_plot.tolist(),
        },
        'method': 'linear',
    }


def polynomial_extrapolation(
    scale_factors: list[float],
    expectation_values: list[float],
    degree: int = 2,
) -> dict:
    """Polynomial fit: E(λ) = Σ aₖ·λᵏ, extrapolate to λ=0.

    Args:
        scale_factors: List of noise scale factors.
        expectation_values: Corresponding noisy expectation values.
        degree: Polynomial degree (default 2 = quadratic).

    Returns:
        Dict with 'mitigated_value', 'fit_params', and 'curve_points'.
    """
    factors = np.array(scale_factors, dtype=float)
    values = np.array(expectation_values, dtype=float)

    # Ensure degree is not higher than number of data points - 1
    degree = min(degree, len(factors) - 1)

    coeffs = np.polyfit(factors, values, deg=degree)
    poly = np.poly1d(coeffs)

    mitigated = float(poly(0))

    x_plot = np.linspace(0, max(factors) * 1.1, 100)
    y_plot = poly(x_plot)

    return {
        'mitigated_value': mitigated,
        'fit_params': {
            'degree': degree,
            'coefficients': coeffs.tolist(),
        },
        'curve_points': {
            'x': x_plot.tolist(),
            'y': y_plot.tolist(),
        },
        'method': f'polynomial (deg={degree})',
    }


def exponential_extrapolation(
    scale_factors: list[float],
    expectation_values: list[float],
) -> dict:
    """Exponential fit: E(λ) = a·exp(b·λ) + c, extrapolate to λ=0.

    Args:
        scale_factors: List of noise scale factors.
        expectation_values: Corresponding noisy expectation values.

    Returns:
        Dict with 'mitigated_value', 'fit_params', and 'curve_points'.
    """
    factors = np.array(scale_factors, dtype=float)
    values = np.array(expectation_values, dtype=float)

    def exp_model(x, a, b, c):
        return a * np.exp(b * x) + c

    try:
        # Initial guesses
        a0 = values[0] - values[-1]
        b0 = -0.5
        c0 = values[-1]

        popt, _ = curve_fit(
            exp_model, factors, values,
            p0=[a0, b0, c0],
            maxfev=10000,
        )

        mitigated = float(exp_model(0, *popt))

        x_plot = np.linspace(0, max(factors) * 1.1, 100)
        y_plot = exp_model(x_plot, *popt).tolist()

        return {
            'mitigated_value': mitigated,
            'fit_params': {
                'a': float(popt[0]),
                'b': float(popt[1]),
                'c': float(popt[2]),
            },
            'curve_points': {
                'x': x_plot.tolist(),
                'y': y_plot,
            },
            'method': 'exponential',
        }

    except (RuntimeError, ValueError):
        # Fall back to polynomial if exponential fit fails
        return polynomial_extrapolation(scale_factors, expectation_values, degree=2)


def extrapolate(
    scale_factors: list[float],
    expectation_values: list[float],
    method: str = 'polynomial',
    degree: int = 2,
) -> dict:
    """Dispatch to the appropriate extrapolation method.

    Args:
        scale_factors: List of noise scale factors.
        expectation_values: Corresponding noisy expectation values.
        method: One of 'linear', 'polynomial', 'exponential'.
        degree: Polynomial degree (only for polynomial method).

    Returns:
        Dict with 'mitigated_value', 'fit_params', 'curve_points', and 'method'.
    """
    if method == 'linear':
        return linear_extrapolation(scale_factors, expectation_values)
    elif method == 'exponential':
        return exponential_extrapolation(scale_factors, expectation_values)
    else:
        return polynomial_extrapolation(scale_factors, expectation_values, degree)
