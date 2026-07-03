"""PDF report generation for ZNE experiments.

Uses ReportLab to create professional PDF reports with experiment
parameters, results, and embedded charts.
"""

from __future__ import annotations
import os
import io
import matplotlib
matplotlib.use('Agg')  # Non-interactive backend
import matplotlib.pyplot as plt
import numpy as np
from datetime import datetime

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import inch, cm
from reportlab.lib.colors import HexColor
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image as RLImage
)


def generate_pdf_report(experiment_data: dict, output_dir: str) -> str:
    """Generate a PDF report for a completed ZNE experiment.

    Args:
        experiment_data: Dict with experiment details (from Experiment.to_dict()).
        output_dir: Directory to save the report.

    Returns:
        Absolute path to the generated PDF file.
    """
    os.makedirs(output_dir, exist_ok=True)
    filename = f"zne_report_{experiment_data['id']}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
    filepath = os.path.join(output_dir, filename)

    doc = SimpleDocTemplate(
        filepath, pagesize=A4,
        topMargin=1.5 * cm, bottomMargin=1.5 * cm,
        leftMargin=2 * cm, rightMargin=2 * cm,
    )

    styles = getSampleStyleSheet()
    elements = []

    # --- Custom styles ---
    title_style = ParagraphStyle(
        'CustomTitle', parent=styles['Title'],
        fontSize=22, textColor=HexColor('#1e293b'),
        spaceAfter=20,
    )
    heading_style = ParagraphStyle(
        'CustomHeading', parent=styles['Heading2'],
        fontSize=14, textColor=HexColor('#0891b2'),
        spaceBefore=16, spaceAfter=8,
    )
    body_style = styles['Normal']

    # --- Title ---
    elements.append(Paragraph("⚛ Zero Noise Extrapolation Report", title_style))
    elements.append(Paragraph(
        f"Experiment: <b>{experiment_data.get('name', 'Untitled')}</b>", body_style
    ))
    elements.append(Paragraph(
        f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", body_style
    ))
    elements.append(Spacer(1, 20))

    # --- Parameters table ---
    elements.append(Paragraph("Experiment Parameters", heading_style))
    params_data = [
        ['Parameter', 'Value'],
        ['Folding Method', experiment_data.get('folding_method', 'N/A').capitalize()],
        ['Scale Factors', str(experiment_data.get('scale_factors', []))],
        ['Extrapolation', experiment_data.get('extrapolation_method', 'N/A').capitalize()],
        ['Noise Error Rate', str(experiment_data.get('noise_error_rate', 'N/A'))],
        ['Shots', str(experiment_data.get('shots', 'N/A'))],
    ]
    params_table = Table(params_data, colWidths=[3 * inch, 3.5 * inch])
    params_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), HexColor('#0891b2')),
        ('TEXTCOLOR', (0, 0), (-1, 0), HexColor('#ffffff')),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('GRID', (0, 0), (-1, -1), 0.5, HexColor('#cbd5e1')),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [HexColor('#f8fafc'), HexColor('#f1f5f9')]),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
    ]))
    elements.append(params_table)
    elements.append(Spacer(1, 16))

    # --- Results ---
    elements.append(Paragraph("Results", heading_style))

    noisy_results = experiment_data.get('noisy_results', [])
    mitigated = experiment_data.get('mitigated_result')
    ideal = experiment_data.get('ideal_result')

    results_data = [['Scale Factor', 'Noisy ⟨Z⟩']]
    scale_factors = experiment_data.get('scale_factors', [])
    for sf, val in zip(scale_factors, noisy_results):
        results_data.append([str(sf), f"{val:.6f}"])

    if mitigated is not None:
        results_data.append(['ZNE (λ→0)', f"{mitigated:.6f}"])
    if ideal is not None:
        results_data.append(['Ideal', f"{ideal:.6f}"])

    results_table = Table(results_data, colWidths=[3 * inch, 3.5 * inch])
    results_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), HexColor('#7c3aed')),
        ('TEXTCOLOR', (0, 0), (-1, 0), HexColor('#ffffff')),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('GRID', (0, 0), (-1, -1), 0.5, HexColor('#cbd5e1')),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [HexColor('#f8fafc'), HexColor('#f1f5f9')]),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
    ]))
    elements.append(results_table)
    elements.append(Spacer(1, 16))

    # --- Chart image ---
    if noisy_results and scale_factors:
        chart_path = _generate_chart_image(experiment_data, output_dir)
        if chart_path:
            elements.append(Paragraph("Extrapolation Plot", heading_style))
            elements.append(RLImage(chart_path, width=5.5 * inch, height=3.5 * inch))
            elements.append(Spacer(1, 12))

    # --- Circuit code ---
    elements.append(Paragraph("Circuit Code", heading_style))
    code = experiment_data.get('circuit_code', 'N/A')
    code_escaped = code.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
    code_style = ParagraphStyle(
        'Code', parent=styles['Code'],
        fontSize=8, leading=11,
        backColor=HexColor('#f1f5f9'),
        borderColor=HexColor('#cbd5e1'),
        borderWidth=1,
        borderPadding=8,
    )
    elements.append(Paragraph(f"<pre>{code_escaped}</pre>", code_style))

    # Build PDF
    doc.build(elements)

    # Clean up temp chart image
    chart_tmp = os.path.join(output_dir, f"_chart_{experiment_data['id']}.png")
    if os.path.exists(chart_tmp):
        os.remove(chart_tmp)

    return filepath


def _generate_chart_image(experiment_data: dict, output_dir: str) -> str | None:
    """Render the extrapolation chart as a PNG for embedding in the PDF."""
    try:
        scale_factors = experiment_data.get('scale_factors', [])
        noisy_results = experiment_data.get('noisy_results', [])
        fit_data = experiment_data.get('fit_curve_data', {})
        mitigated = experiment_data.get('mitigated_result')
        ideal = experiment_data.get('ideal_result')

        fig, ax = plt.subplots(figsize=(8, 5))
        fig.patch.set_facecolor('#0f172a')
        ax.set_facecolor('#1e293b')

        # Noisy data points
        ax.scatter(scale_factors, noisy_results, color='#f97316', s=80,
                   zorder=5, label='Noisy ⟨Z⟩', edgecolors='white', linewidth=0.5)

        # Fitted curve
        if fit_data and 'x' in fit_data and 'y' in fit_data:
            ax.plot(fit_data['x'], fit_data['y'], color='#22d3ee',
                    linewidth=2, linestyle='--', label='Extrapolation Fit', alpha=0.8)

        # Mitigated value
        if mitigated is not None:
            ax.scatter([0], [mitigated], color='#22c55e', s=120, zorder=6,
                       marker='*', label=f'ZNE = {mitigated:.4f}', edgecolors='white')

        # Ideal value
        if ideal is not None:
            ax.axhline(y=ideal, color='#a78bfa', linestyle=':', linewidth=1.5,
                       label=f'Ideal = {ideal:.4f}', alpha=0.7)

        ax.set_xlabel('Scale Factor (λ)', color='white', fontsize=11)
        ax.set_ylabel('Expectation Value ⟨Z⟩', color='white', fontsize=11)
        ax.set_title('Zero Noise Extrapolation', color='white', fontsize=14, fontweight='bold')
        ax.tick_params(colors='white')
        ax.legend(facecolor='#334155', edgecolor='#475569', labelcolor='white', fontsize=9)

        for spine in ax.spines.values():
            spine.set_color('#475569')

        ax.grid(True, alpha=0.15, color='white')

        chart_path = os.path.join(output_dir, f"_chart_{experiment_data['id']}.png")
        fig.savefig(chart_path, dpi=150, bbox_inches='tight', facecolor=fig.get_facecolor())
        plt.close(fig)

        return chart_path

    except Exception:
        return None
