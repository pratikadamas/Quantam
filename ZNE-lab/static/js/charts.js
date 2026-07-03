/**
 * Chart.js configuration for ZNE result visualization.
 * Creates responsive, interactive extrapolation plots.
 */

/**
 * Create a ZNE extrapolation chart.
 * @param {CanvasRenderingContext2D} ctx - Canvas 2D context
 * @param {Object} data - Experiment data from the API
 * @returns {Chart} Chart.js instance
 */
function createZNEChart(ctx, data) {
    const scaleFactors = data.scale_factors || [];
    const noisyResults = data.noisy_results || [];
    const fitData = data.fit_curve_data || {};
    const mitigated = data.mitigated_result;
    const ideal = data.ideal_result;

    const datasets = [];

    // 1. Fitted extrapolation curve (rendered first, behind data points)
    if (fitData.x && fitData.y) {
        datasets.push({
            label: 'Extrapolation Fit',
            data: fitData.x.map((x, i) => ({ x: x, y: fitData.y[i] })),
            type: 'line',
            borderColor: 'rgba(34, 211, 238, 0.6)',
            borderWidth: 2,
            borderDash: [6, 4],
            pointRadius: 0,
            fill: false,
            tension: 0.4,
            order: 3,
        });
    }

    // 2. Noisy measurement points
    if (scaleFactors.length && noisyResults.length) {
        datasets.push({
            label: 'Noisy ⟨Z⟩',
            data: scaleFactors.map((sf, i) => ({ x: sf, y: noisyResults[i] })),
            type: 'scatter',
            backgroundColor: '#f97316',
            borderColor: '#fb923c',
            borderWidth: 2,
            pointRadius: 7,
            pointHoverRadius: 10,
            pointStyle: 'circle',
            order: 1,
        });
    }

    // 3. Mitigated value (ZNE result at λ=0)
    if (mitigated !== null && mitigated !== undefined) {
        datasets.push({
            label: `ZNE = ${mitigated.toFixed(4)}`,
            data: [{ x: 0, y: mitigated }],
            type: 'scatter',
            backgroundColor: '#22c55e',
            borderColor: '#4ade80',
            borderWidth: 2,
            pointRadius: 10,
            pointHoverRadius: 13,
            pointStyle: 'star',
            order: 0,
        });
    }

    // 4. Ideal value (horizontal line)
    if (ideal !== null && ideal !== undefined) {
        const xMax = Math.max(...scaleFactors, 5) * 1.1;
        datasets.push({
            label: `Ideal = ${ideal.toFixed(4)}`,
            data: [{ x: 0, y: ideal }, { x: xMax, y: ideal }],
            type: 'line',
            borderColor: 'rgba(167, 139, 250, 0.5)',
            borderWidth: 1.5,
            borderDash: [3, 3],
            pointRadius: 0,
            fill: false,
            order: 4,
        });
    }

    return new Chart(ctx, {
        type: 'scatter',
        data: { datasets },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            interaction: {
                mode: 'nearest',
                intersect: false,
            },
            plugins: {
                legend: {
                    position: 'top',
                    labels: {
                        color: '#94a3b8',
                        font: {
                            family: "'Inter', sans-serif",
                            size: 11,
                            weight: 500,
                        },
                        usePointStyle: true,
                        pointStyleWidth: 12,
                        padding: 16,
                    },
                },
                tooltip: {
                    backgroundColor: 'rgba(15, 23, 42, 0.95)',
                    titleColor: '#e2e8f0',
                    bodyColor: '#94a3b8',
                    borderColor: 'rgba(71, 85, 105, 0.5)',
                    borderWidth: 1,
                    cornerRadius: 8,
                    padding: 12,
                    titleFont: {
                        family: "'Inter', sans-serif",
                        size: 12,
                        weight: 600,
                    },
                    bodyFont: {
                        family: "'JetBrains Mono', monospace",
                        size: 11,
                    },
                    callbacks: {
                        label: function(context) {
                            const label = context.dataset.label || '';
                            if (context.parsed) {
                                return `${label}: λ=${context.parsed.x.toFixed(2)}, ⟨Z⟩=${context.parsed.y.toFixed(6)}`;
                            }
                            return label;
                        }
                    }
                },
            },
            scales: {
                x: {
                    title: {
                        display: true,
                        text: 'Scale Factor (λ)',
                        color: '#64748b',
                        font: {
                            family: "'Inter', sans-serif",
                            size: 12,
                            weight: 600,
                        },
                    },
                    grid: {
                        color: 'rgba(71, 85, 105, 0.15)',
                    },
                    ticks: {
                        color: '#64748b',
                        font: {
                            family: "'JetBrains Mono', monospace",
                            size: 10,
                        },
                    },
                    min: -0.2,
                },
                y: {
                    title: {
                        display: true,
                        text: 'Expectation Value ⟨Z⟩',
                        color: '#64748b',
                        font: {
                            family: "'Inter', sans-serif",
                            size: 12,
                            weight: 600,
                        },
                    },
                    grid: {
                        color: 'rgba(71, 85, 105, 0.15)',
                    },
                    ticks: {
                        color: '#64748b',
                        font: {
                            family: "'JetBrains Mono', monospace",
                            size: 10,
                        },
                    },
                },
            },
        },
    });
}
