/**
 * app.js — qcompiler web frontend
 *
 * Responsibilities:
 *   - Bootstrap Monaco Editor with custom quantum Python theme
 *   - Load example circuits from /api/examples
 *   - POST to /api/compile on Run click or Ctrl+Enter
 *   - Animate the pipeline progress steps
 *   - Render QASM3, stats, DAG layers, ASCII circuit in output tabs
 */

'use strict';

const API_BASE = '';  // same origin

// ─── State ───────────────────────────────────────────────────
let editor = null;
let currentResult = null;
let isRunning = false;

// ─── DOM refs ────────────────────────────────────────────────
const $ = id => document.getElementById(id);

const btnRun      = $('btn-run');
const btnRunText  = $('btn-run-text');
const optLevel    = $('opt-level');
const statusText  = $('status-text');
const statusTime  = $('status-time');
const btnCopyQasm = $('btn-copy-qasm');
const btnDocs     = $('btn-docs');
const docsModal   = $('docs-modal');
const btnCloseDocs= $('btn-close-docs');
const toastEl     = $('toast');
const examplesList= $('examples-list');

// Pipeline steps
const pipeSteps = {
  code:   $('ps-code'),
  ir:     $('ps-ir'),
  dag:    $('ps-dag'),
  opt:    $('ps-opt'),
  decomp: $('ps-decomp'),
  qasm:   $('ps-qasm'),
};

// ─── Monaco setup ────────────────────────────────────────────
require.config({
  paths: { vs: 'https://cdnjs.cloudflare.com/ajax/libs/monaco-editor/0.44.0/min/vs' }
});

require(['vs/editor/editor.main'], () => {
  // Register a custom "quantum" color theme
  monaco.editor.defineTheme('quantum-dark', {
    base: 'vs-dark',
    inherit: true,
    rules: [
      { token: 'keyword',        foreground: '818cf8', fontStyle: 'bold' },
      { token: 'string',         foreground: '34d399' },
      { token: 'number',         foreground: 'fbbf24' },
      { token: 'comment',        foreground: '475569', fontStyle: 'italic' },
      { token: 'identifier',     foreground: 'e2e8f0' },
      { token: 'type.identifier',foreground: '38bdf8' },
      { token: 'delimiter',      foreground: '94a3b8' },
    ],
    colors: {
      'editor.background':            '#06080f',
      'editor.foreground':            '#e2e8f0',
      'editor.lineHighlightBackground':'#0f172a',
      'editor.selectionBackground':   '#1e3a5f',
      'editorCursor.foreground':      '#818cf8',
      'editorLineNumber.foreground':  '#334155',
      'editorLineNumber.activeForeground': '#64748b',
      'editorGutter.background':      '#06080f',
      'editor.inactiveSelectionBackground': '#0f1e38',
      'scrollbarSlider.background':   '#1e293b80',
      'scrollbarSlider.hoverBackground': '#334155aa',
      'editorWidget.background':      '#0c1120',
      'editorSuggestWidget.background': '#0c1120',
      'editorSuggestWidget.border':   '#1e293b',
      'input.background':             '#0f172a',
    }
  });

  editor = monaco.editor.create($('monaco-container'), {
    value: getDefaultCode(),
    language: 'python',
    theme: 'quantum-dark',
    fontSize: 13,
    lineHeight: 22,
    fontFamily: "'JetBrains Mono', 'Fira Code', monospace",
    fontLigatures: true,
    minimap: { enabled: false },
    scrollBeyondLastLine: false,
    automaticLayout: true,
    padding: { top: 14, bottom: 14 },
    suggest: { showWords: true },
    quickSuggestions: { other: true, comments: false, strings: false },
    cursorBlinking: 'smooth',
    cursorSmoothCaretAnimation: 'on',
    smoothScrolling: true,
    renderLineHighlight: 'all',
    bracketPairColorization: { enabled: true },
    guides: { bracketPairs: true },
    scrollbar: { verticalScrollbarSize: 6, horizontalScrollbarSize: 6 },
  });

  // Ctrl+Enter → run
  editor.addCommand(
    monaco.KeyMod.CtrlCmd | monaco.KeyCode.Enter,
    () => runCompile()
  );

  // Load examples
  loadExamples();
});

// ─── Default starter code ────────────────────────────────────
function getDefaultCode() {
  return `# qcompiler — write your quantum circuit below
# Press Ctrl+Enter or click Run to compile

from qcompiler import QuantumCircuit, compile

# Bell state example
qc = QuantumCircuit(2, 2, name="bell_state")
qc.h(0)          # Hadamard on qubit 0
qc.cx(0, 1)      # CNOT: control=0, target=1
qc.measure(0, 0) # measure qubit 0 → clbit 0
qc.measure(1, 1) # measure qubit 1 → clbit 1

result = compile(qc, optimization_level=1)
`;
}

// ─── Examples ────────────────────────────────────────────────
async function loadExamples() {
  try {
    const res = await fetch(`${API_BASE}/api/examples`);
    const examples = await res.json();

    examplesList.innerHTML = '';
    examples.forEach(ex => {
      const chip = document.createElement('button');
      chip.className = 'chip';
      chip.textContent = ex.name.replace(/_/g, ' ');
      chip.title = ex.description;
      chip.id = `chip-${ex.name}`;
      chip.onclick = () => loadExample(ex.name);
      examplesList.appendChild(chip);
    });
  } catch (e) {
    console.warn('Could not load examples:', e);
  }
}

async function loadExample(name) {
  try {
    const res = await fetch(`${API_BASE}/api/examples/${name}`);
    const data = await res.json();
    if (editor && data.code) {
      editor.setValue(data.code);
      editor.focus();
    }
  } catch (e) {
    console.error('Could not load example:', e);
  }
}

// ─── Compile ─────────────────────────────────────────────────
async function runCompile() {
  if (isRunning) return;
  if (!editor) return;

  const code = editor.getValue().trim();
  if (!code) return;

  isRunning = true;
  const startTime = performance.now();

  // UI: loading state
  btnRun.disabled = true;
  btnRun.classList.add('loading');
  btnRunText.textContent = 'Compiling…';
  setStatus('running', 'Compiling quantum circuit…');
  setPipelineState('running');

  try {
    const optLevelVal = parseInt(optLevel.value, 10);

    const res = await fetch(`${API_BASE}/api/compile`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ code, optimization_level: optLevelVal }),
    });

    const data = await res.json();
    const elapsed = ((performance.now() - startTime) / 1000).toFixed(3);

    if (data.success) {
      currentResult = data;
      renderSuccess(data, elapsed);
      setPipelineState('done');
      setStatus('success', `✓ Compiled in ${elapsed}s`);
      statusTime.textContent = new Date().toLocaleTimeString();
    } else {
      renderError(data.error || 'Unknown compilation error');
      setPipelineState('error');
      setStatus('error', '✗ Compilation failed');
    }
  } catch (err) {
    renderError(`Network error: ${err.message}\n\nIs the FastAPI server running?\n  uvicorn qcompiler.server.app:app --reload`);
    setPipelineState('error');
    setStatus('error', '✗ Server unreachable');
  } finally {
    isRunning = false;
    btnRun.disabled = false;
    btnRun.classList.remove('loading');
    btnRunText.textContent = 'Run';
  }
}

// ─── Render success ───────────────────────────────────────────
function renderSuccess(data, elapsed) {
  // ── QASM tab ──
  const qcode = $('qasm-code');
  const qpre  = $('qasm-output');
  const qph   = $('qasm-placeholder');

  qcode.textContent = data.qasm || '';
  hljs.highlightElement(qcode);
  qph.classList.add('hidden');
  qpre.classList.remove('hidden');

  // ── Stats tab ──
  const statsContent  = $('stats-content');
  const statsPholder  = $('stats-placeholder');
  const s = data.stats || {};

  const gateReduction = s.original_gate_count > 0
    ? Math.round((1 - s.optimized_gate_count / s.original_gate_count) * 100)
    : 0;

  statsContent.innerHTML = `
    <div class="stats-grid">
      <div class="stat-card">
        <div class="stat-label">Qubits</div>
        <div class="stat-value indigo">${s.num_qubits ?? '—'}</div>
        <div class="stat-sub">${s.num_clbits ?? 0} classical bits</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">Circuit Depth</div>
        <div class="stat-value sky">${s.final_depth ?? '—'}</div>
        <div class="stat-sub">was ${s.original_depth ?? '—'} before opt</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">Gates (final)</div>
        <div class="stat-value emerald">${s.final_gate_count ?? '—'}</div>
        <div class="stat-sub">after decomposition</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">Opt Level</div>
        <div class="stat-value amber">O${s.optimization_level ?? 0}</div>
        <div class="stat-sub">gate reduction: ${gateReduction}%</div>
      </div>
    </div>

    <div>
      <div class="section-title">Gate Reduction</div>
      <div style="font-size:0.75rem;color:var(--text-muted);margin-bottom:6px">
        ${s.original_gate_count} → ${s.optimized_gate_count} gates after optimization
      </div>
      <div class="reduction-bar">
        <div class="reduction-fill" style="width:${Math.max(2, 100 - gateReduction)}%"></div>
      </div>
    </div>

    <div>
      <div class="section-title">Gate Counts (final basis)</div>
      ${renderGateCounts(s.gate_counts || {})}
    </div>
  `;

  statsPholder.classList.add('hidden');
  statsContent.classList.remove('hidden');

  // ── DAG tab ──
  const dagContent  = $('dag-content');
  const dagPlholder = $('dag-placeholder');
  const d = data.dag_info || {};

  dagContent.innerHTML = `
    <div class="dag-summary">
      <div class="dag-chip indigo">⬡ ${d.num_nodes ?? 0} ops</div>
      <div class="dag-chip sky">⊞ ${d.num_layers ?? 0} layers</div>
      <div class="dag-chip violet">↕ depth ${d.depth ?? 0}</div>
    </div>
    <div>
      <div class="section-title">Topological Layers</div>
      <div class="dag-layers">
        ${(d.layers || []).map((layer, i) => `
          <div class="dag-layer" style="animation-delay:${i * 30}ms">
            <div class="dag-layer-num">${i + 1}</div>
            <div class="dag-layer-gates">
              ${layer.map(g => `<span class="gate-badge ${gateClass(g)}">${g}</span>`).join('')}
            </div>
          </div>
        `).join('')}
      </div>
    </div>
  `;

  dagPlholder.classList.add('hidden');
  dagContent.classList.remove('hidden');

  // ── Circuit tab ──
  const circDraw  = $('circuit-draw');
  const circPlhol = $('circuit-placeholder');

  circDraw.textContent = data.circuit_draw || 'No circuit draw available.';
  circPlhol.classList.add('hidden');
  circDraw.classList.remove('hidden');

  // Switch to QASM tab
  switchTab('qasm');
}

function renderGateCounts(counts) {
  const entries = Object.entries(counts)
    .filter(([k]) => k !== 'barrier')
    .sort((a, b) => b[1] - a[1]);

  if (!entries.length) return '<p style="color:var(--text-muted);font-size:0.8rem">No gates.</p>';

  return `
    <table class="gate-counts-table">
      <thead><tr><th>Gate</th><th>Count</th></tr></thead>
      <tbody>
        ${entries.map(([name, cnt]) => `
          <tr>
            <td><code>${name}</code></td>
            <td>${cnt}</td>
          </tr>
        `).join('')}
      </tbody>
    </table>
  `;
}

function gateClass(name) {
  if (['measure'].includes(name)) return 'measure';
  if (['cx','cy','cz','swap','cp','crz'].includes(name)) return 'two-q';
  if (['ccx','cswap'].includes(name)) return 'three-q';
  return '';
}

// ─── Render error ─────────────────────────────────────────────
function renderError(errText) {
  const qpre   = $('qasm-output');
  const qph    = $('qasm-placeholder');
  const qcode  = $('qasm-code');

  // Clear code block, show error as styled block
  if (qcode) qcode.textContent = '';
  if (qpre) {
    qpre.innerHTML = `<div class="error-block">${escHtml(errText)}</div>`;
    qpre.classList.remove('hidden');
  }
  if (qph) qph.classList.add('hidden');

  switchTab('qasm');
}

function escHtml(s) {
  return s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
}

// ─── Pipeline animation ───────────────────────────────────────
const pipeOrder = ['code','ir','dag','opt','decomp','qasm'];

function setPipelineState(state) {
  // Reset
  pipeOrder.forEach(k => {
    pipeSteps[k].className = 'pipe-step';
  });

  if (state === 'running') {
    // Animate steps sequentially
    pipeOrder.forEach((k, i) => {
      setTimeout(() => {
        if (pipeSteps[k]) {
          // Clear all running first
          pipeOrder.forEach(j => pipeSteps[j].classList.remove('running'));
          pipeSteps[k].classList.add('running');
        }
      }, i * 180);
    });
  } else if (state === 'done') {
    pipeOrder.forEach(k => pipeSteps[k].classList.add('done'));
    pipeSteps['code'].classList.add('active');
  } else if (state === 'error') {
    pipeSteps['code'].classList.add('active');
  } else {
    pipeSteps['code'].classList.add('active');
  }
}

// ─── Status bar ───────────────────────────────────────────────
function setStatus(type, text) {
  statusText.className = `status-${type}`;
  statusText.textContent = text;
}

// ─── Tabs ─────────────────────────────────────────────────────
function switchTab(name) {
  document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
  document.querySelectorAll('.tab-pane').forEach(p => p.classList.add('hidden'));

  const tab  = $(`tab-${name}`);
  const pane = $(`pane-${name}`);
  if (tab)  tab.classList.add('active');
  if (pane) pane.classList.remove('hidden');
}

document.querySelectorAll('.tab').forEach(tab => {
  tab.addEventListener('click', () => switchTab(tab.dataset.tab));
});

// ─── Run button ───────────────────────────────────────────────
btnRun.addEventListener('click', runCompile);

// ─── Copy QASM ───────────────────────────────────────────────
btnCopyQasm.addEventListener('click', () => {
  if (!currentResult?.qasm) return;
  navigator.clipboard.writeText(currentResult.qasm).then(() => showToast('QASM copied!'));
});

// ─── Docs modal ───────────────────────────────────────────────
btnDocs.addEventListener('click', () => docsModal.classList.remove('hidden'));
btnCloseDocs.addEventListener('click', () => docsModal.classList.add('hidden'));
docsModal.addEventListener('click', e => {
  if (e.target === docsModal) docsModal.classList.add('hidden');
});
document.addEventListener('keydown', e => {
  if (e.key === 'Escape') docsModal.classList.add('hidden');
});

// ─── Toast ────────────────────────────────────────────────────
function showToast(msg = 'Copied!') {
  toastEl.textContent = msg;
  toastEl.classList.remove('hidden');
  setTimeout(() => toastEl.classList.add('hidden'), 1800);
}

// ─── Init pipeline ────────────────────────────────────────────
setPipelineState('idle');
