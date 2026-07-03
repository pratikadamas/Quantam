/**
 * CodeMirror editor initialization, template loading, and
 * experiment execution logic.
 */

// ── Global State ──────────────────────────────────────────────
let editor = null;
let zneChart = null;
let currentExperimentId = null;
let circuitTemplates = {};

// ── Default Circuit Code ──────────────────────────────────────
const DEFAULT_CODE = `from qiskit import QuantumCircuit

# Create a Bell state circuit (2 qubits)
qc = QuantumCircuit(2)
qc.h(0)        # Hadamard on qubit 0
qc.cx(0, 1)    # CNOT: entangle qubits 0 and 1
`;

// ── Initialize on DOM Ready ──────────────────────────────────
document.addEventListener('DOMContentLoaded', function () {
    initEditor();
    loadTemplates();
    initControls();
});

// ── CodeMirror Setup ──────────────────────────────────────────
function initEditor() {
    const editorElement = document.getElementById('code-editor');
    if (!editorElement) return;

    editor = CodeMirror(editorElement, {
        value: DEFAULT_CODE,
        mode: 'python',
        theme: 'dracula',
        lineNumbers: true,
        indentUnit: 4,
        tabSize: 4,
        indentWithTabs: false,
        lineWrapping: false,
        matchBrackets: true,
        autoCloseBrackets: true,
        styleActiveLine: { nonEmpty: true },
        viewportMargin: Infinity,
        extraKeys: {
            'Ctrl-Enter': runExperiment,
            'Cmd-Enter': runExperiment,
            'Tab': function (cm) {
                cm.replaceSelection('    ', 'end');
            },
        },
    });
}

// ── Load Circuit Templates ────────────────────────────────────
async function loadTemplates() {
    try {
        const resp = await fetch('/api/templates');
        circuitTemplates = await resp.json();
        renderTemplateChips();
    } catch (err) {
        console.warn('Failed to load templates:', err);
    }
}

function renderTemplateChips() {
    const container = document.getElementById('template-chips');
    if (!container) return;

    container.innerHTML = '';
    for (const [key, tmpl] of Object.entries(circuitTemplates)) {
        const chip = document.createElement('button');
        chip.className = 'template-chip';
        chip.textContent = tmpl.name;
        chip.dataset.key = key;
        chip.addEventListener('click', () => loadTemplate(key));
        container.appendChild(chip);
    }
}

function loadTemplate(key) {
    if (!circuitTemplates[key] || !editor) return;

    editor.setValue(circuitTemplates[key].code);

    // Update experiment name
    const nameInput = document.getElementById('experiment-name');
    if (nameInput) {
        nameInput.value = circuitTemplates[key].name + ' ZNE';
    }

    // Highlight active chip
    document.querySelectorAll('.template-chip').forEach(c => c.classList.remove('active'));
    const activeChip = document.querySelector(`.template-chip[data-key="${key}"]`);
    if (activeChip) activeChip.classList.add('active');
}

// ── UI Controls ───────────────────────────────────────────────
function initControls() {
    // Noise rate slider display
    const noiseSlider = document.getElementById('noise-rate');
    const noiseDisplay = document.getElementById('noise-rate-value');
    if (noiseSlider && noiseDisplay) {
        noiseSlider.addEventListener('input', () => {
            noiseDisplay.textContent = parseFloat(noiseSlider.value).toFixed(3);
        });
    }

    // Show/hide polynomial degree based on extrapolation method
    const extrapSelect = document.getElementById('extrapolation-method');
    const polyGroup = document.getElementById('poly-degree-group');
    if (extrapSelect && polyGroup) {
        extrapSelect.addEventListener('change', () => {
            polyGroup.style.display = extrapSelect.value === 'polynomial' ? 'block' : 'none';
        });
    }
}

// ── Run Experiment ────────────────────────────────────────────
async function runExperiment() {
    if (!editor) return;

    const code = editor.getValue().trim();
    if (!code) {
        showToast('Please write some circuit code first.', 'error');
        return;
    }

    // Parse scale factors
    const scaleFactorsStr = document.getElementById('scale-factors').value;
    let scaleFactors;
    try {
        scaleFactors = scaleFactorsStr.split(',').map(s => {
            const num = parseFloat(s.trim());
            if (isNaN(num) || num < 1) throw new Error('Invalid');
            return num;
        });
    } catch {
        showToast('Invalid scale factors. Use comma-separated numbers ≥ 1.', 'error');
        return;
    }

    // Gather parameters
    const params = {
        name: document.getElementById('experiment-name').value || 'Untitled',
        circuit_code: code,
        folding_method: document.getElementById('folding-method').value,
        scale_factors: scaleFactors,
        extrapolation_method: document.getElementById('extrapolation-method').value,
        poly_degree: parseInt(document.getElementById('poly-degree').value),
        noise_error_rate: parseFloat(document.getElementById('noise-rate').value),
        shots: parseInt(document.getElementById('shots').value),
    };

    // Show loading
    const loadingOverlay = document.getElementById('loading-overlay');
    const runBtn = document.getElementById('run-btn');
    loadingOverlay.classList.remove('hidden');
    runBtn.disabled = true;
    runBtn.innerHTML = '<span class="spinner"></span> Running...';

    try {
        const resp = await fetch('/api/run', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(params),
        });

        const result = await resp.json();

        if (!resp.ok) {
            throw new Error(result.error || 'Experiment failed');
        }

        currentExperimentId = result.experiment.id;
        displayResults(result.experiment, result.extrapolation);
        showToast('Experiment completed successfully!', 'success');

    } catch (err) {
        showToast('Error: ' + err.message, 'error');
        console.error('Experiment error:', err);
    } finally {
        loadingOverlay.classList.add('hidden');
        runBtn.disabled = false;
        runBtn.innerHTML = `
            <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="2">
                <path d="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z"/>
                <path d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/>
            </svg>
            Run ZNE Experiment
        `;
    }
}

// ── Display Results ───────────────────────────────────────────
function displayResults(experiment, extrapolation) {
    const section = document.getElementById('results-section');
    section.classList.remove('hidden');
    section.style.animation = 'slideUp 0.6s ease-out both';

    // Scroll to results
    setTimeout(() => {
        section.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }, 200);

    // Metric cards
    const mitigated = experiment.mitigated_result;
    const ideal = experiment.ideal_result;
    const noisyFirst = experiment.noisy_results[0];

    document.getElementById('mitigated-value').textContent =
        mitigated !== null ? mitigated.toFixed(6) : '—';
    document.getElementById('ideal-value').textContent =
        ideal !== null ? ideal.toFixed(6) : '—';

    // Calculate improvement
    if (noisyFirst !== undefined && ideal !== null && mitigated !== null) {
        const noisyError = Math.abs(noisyFirst - ideal);
        const mitigatedError = Math.abs(mitigated - ideal);
        if (noisyError > 1e-10) {
            const improvement = ((noisyError - mitigatedError) / noisyError * 100).toFixed(1);
            document.getElementById('improvement-value').textContent = `${improvement}%`;
        } else {
            document.getElementById('improvement-value').textContent = '—';
        }
    }

    // Method badge
    const methodBadge = document.getElementById('method-badge');
    if (extrapolation) {
        methodBadge.textContent = extrapolation.method;
    }

    // Data table
    const tbody = document.getElementById('results-table-body');
    tbody.innerHTML = '';

    // ZNE row first
    if (mitigated !== null) {
        tbody.innerHTML += `
            <tr class="bg-green-500/5">
                <td class="font-mono font-semibold text-green-400">λ → 0 (ZNE)</td>
                <td class="font-mono font-semibold text-green-400">${mitigated.toFixed(6)}</td>
            </tr>`;
    }

    // Noisy results
    experiment.scale_factors.forEach((sf, i) => {
        const val = experiment.noisy_results[i];
        tbody.innerHTML += `
            <tr>
                <td class="font-mono text-quantum-300">${sf}</td>
                <td class="font-mono text-dark-300">${val !== undefined ? val.toFixed(6) : '—'}</td>
            </tr>`;
    });

    // Ideal row
    if (ideal !== null) {
        tbody.innerHTML += `
            <tr class="bg-nebula-500/5">
                <td class="font-mono font-semibold text-nebula-300">Ideal</td>
                <td class="font-mono font-semibold text-nebula-300">${ideal.toFixed(6)}</td>
            </tr>`;
    }

    // Chart
    if (zneChart) zneChart.destroy();
    const ctx = document.getElementById('zne-chart').getContext('2d');
    zneChart = createZNEChart(ctx, experiment);

    // Show report button
    document.getElementById('download-report-btn').classList.remove('hidden');
}

// ── Download PDF Report ───────────────────────────────────────
function downloadReport() {
    if (currentExperimentId) {
        window.open(`/api/report/${currentExperimentId}`, '_blank');
    }
}

// ── Toast Notifications ───────────────────────────────────────
function showToast(message, type = 'success') {
    const existing = document.querySelector('.toast');
    if (existing) existing.remove();

    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    toast.textContent = message;
    document.body.appendChild(toast);

    requestAnimationFrame(() => {
        toast.classList.add('show');
    });

    setTimeout(() => {
        toast.classList.remove('show');
        setTimeout(() => toast.remove(), 400);
    }, 4000);
}
