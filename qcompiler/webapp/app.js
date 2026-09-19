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
  renderDagSection(data.dag_info);

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

// ─── Visual DAG Graph & Controls ──────────────────────────────
let currentDagInfo = null;
let dagTransform = { x: 30, y: 30, scale: 1.0 };
let isDagPanning = false;
let dagPanStart = { x: 0, y: 0 };

function renderDagSection(dagInfo) {
  currentDagInfo = dagInfo || {};
  const d = currentDagInfo;
  const dagContent = $('dag-content');
  const dagPlholder = $('dag-placeholder');
  if (!dagContent || !dagPlholder) return;

  dagPlholder.classList.add('hidden');
  dagContent.classList.remove('hidden');

  // Summary chips
  const chipsEl = $('dag-summary-chips');
  if (chipsEl) {
    const numNodes = d.graph?.num_nodes ?? (d.num_nodes ?? 0);
    const numEdges = d.graph?.num_edges ?? 0;
    chipsEl.innerHTML = `
      <div class="dag-chip indigo">⬡ ${d.num_nodes ?? 0} ops</div>
      <div class="dag-chip sky">⊞ ${d.num_layers ?? 0} layers</div>
      <div class="dag-chip violet">↕ depth ${d.depth ?? 0}</div>
      <div class="dag-chip emerald">◈ ${numNodes} nodes</div>
      <div class="dag-chip indigo">⮂ ${numEdges} edges</div>
    `;
  }

  // ASCII pre
  const asciiPre = $('dag-ascii-pre');
  if (asciiPre) {
    asciiPre.textContent = d.ascii_draw || 'No ASCII representation available.';
  }

  // Layers view
  const layersView = $('dag-layers-view');
  if (layersView) {
    layersView.innerHTML = `
      <div class="section-title">Topological Layers</div>
      <div class="dag-layers">
        ${(d.layers || []).map((layer, i) => `
          <div class="dag-layer" style="animation-delay:${i * 30}ms">
            <div class="dag-layer-num">L${i + 1}</div>
            <div class="dag-layer-gates">
              ${layer.map(g => `<span class="gate-badge ${gateClass(g)}">${g}</span>`).join('')}
            </div>
          </div>
        `).join('')}
      </div>
    `;
  }

  // Visual SVG Graph
  const showWires = $('toggle-dag-wires') ? $('toggle-dag-wires').checked : true;
  drawDagSvg(d.graph, showWires);
}

let currentDagLayout = 'tree'; // 'tree' represents Stages (IR) parallel frontiers
let showDagCriticalPath = true; // Enabled by default to highlight circuit depth bottleneck

function drawDagSvg(graphData, showWires = true, layoutMode = currentDagLayout) {
  const svg = $('dag-svg');
  if (!svg) return;

  if (!graphData || !graphData.nodes || !graphData.nodes.length) {
    svg.innerHTML = `
      <text x="50%" y="50%" text-anchor="middle" fill="var(--text-muted)" font-family="var(--font-mono)" font-size="13">
        No DAG graph data available
      </text>
    `;
    return;
  }

  // Filter nodes if wire boundary nodes are hidden
  let activeNodes = graphData.nodes;
  let activeEdges = graphData.edges || [];

  if (!showWires) {
    activeNodes = graphData.nodes.filter(n => n.type === 'op');
    const opIds = new Set(activeNodes.map(n => n.id));
    activeEdges = activeEdges.filter(e => opIds.has(e.source) && opIds.has(e.target));
  }

  const nodeMap = new Map();
  activeNodes.forEach(n => nodeMap.set(n.id, n));

  // Critical path sets
  const critNodeSet = new Set(graphData.critical_path || []);
  const critEdgeSet = new Set();
  const cp = graphData.critical_path || [];
  for (let i = 0; i < cp.length - 1; i++) {
    critEdgeSet.add(`${cp[i]}->${cp[i+1]}`);
  }

  // Collect all unique quantum and classical wires
  const qWiresSet = new Set();
  const cWiresSet = new Set();

  activeNodes.forEach(n => {
    if (n.wire) {
      if (n.wire.startsWith('c')) cWiresSet.add(n.wire);
      else qWiresSet.add(n.wire);
    }
    (n.qubits || []).forEach(q => qWiresSet.add(q));
    (n.clbits || []).forEach(c => cWiresSet.add(c));
  });

  activeEdges.forEach(e => {
    if (e.wire) {
      if (e.wire.startsWith('c')) cWiresSet.add(e.wire);
      else qWiresSet.add(e.wire);
    }
  });

  function parseWireIdx(w) {
    const m = (w || '').match(/(?:q|c)\[(\d+)\]/);
    return m ? parseInt(m[1], 10) : 0;
  }

  const sortedQubitWires = Array.from(qWiresSet).sort((a, b) => parseWireIdx(a) - parseWireIdx(b));
  const sortedClbitWires = Array.from(cWiresSet).sort((a, b) => parseWireIdx(a) - parseWireIdx(b));
  const allOrderedWires = [...sortedQubitWires, ...sortedClbitWires];

  // Map wire to Y track position (for Rails layout)
  const trackYMap = new Map();
  const padYRails = 70;
  const trackSpacing = 110;
  let currentRailsY = padYRails;

  sortedQubitWires.forEach(w => {
    trackYMap.set(w, currentRailsY);
    currentRailsY += trackSpacing;
  });

  if (sortedClbitWires.length > 0) {
    currentRailsY += 25;
    sortedClbitWires.forEach(w => {
      trackYMap.set(w, currentRailsY);
      currentRailsY += 85;
    });
  }

  function getWireY(wireName) {
    return trackYMap.has(wireName) ? trackYMap.get(wireName) : padYRails;
  }

  // Column assignment based on topological order
  const nodeLayer = new Map();
  if (graphData.layers && graphData.layers.length) {
    graphData.layers.forEach((layerNids, layerIdx) => {
      layerNids.forEach(nid => {
        if (nodeMap.has(nid)) {
          nodeLayer.set(nid, layerIdx);
        }
      });
    });
  }

  activeNodes.forEach(n => {
    if (!nodeLayer.has(n.id)) {
      nodeLayer.set(n.id, n.type === 'in' ? 0 : (n.type === 'out' ? 999 : 1));
    }
  });

  const layerCols = new Map();
  activeNodes.forEach(n => {
    const l = nodeLayer.get(n.id);
    if (!layerCols.has(l)) layerCols.set(l, []);
    layerCols.get(l).push(n);
  });

  const sortedColKeys = Array.from(layerCols.keys()).sort((a, b) => a - b);
  const normalizedCol = new Map();
  sortedColKeys.forEach((key, idx) => normalizedCol.set(key, idx));

  // Geometry configuration
  const nodeCoords = new Map();
  const nodePorts = new Map(); // nid -> { in: { [wire]: {x,y} }, out: { [wire]: {x,y} } }
  let stageLanesHtml = '';
  let totalWidth = 800;
  let totalHeight = 520;

  if (layoutMode === 'rails') {
    // ─── 1. QUANTUM RAILS LAYOUT ───
    const colWidth = 160;
    const padX = 90;
    const maxColIdx = Math.max(1, sortedColKeys.length - 1);
    totalWidth = padX * 2 + (maxColIdx + 1) * colWidth + 60;
    totalHeight = Math.max(480, currentRailsY + 50);

    sortedColKeys.forEach(colKey => {
      const colIdx = normalizedCol.get(colKey);
      const nodesInCol = layerCols.get(colKey);
      const colX = padX + colIdx * colWidth;

      nodesInCol.forEach(node => {
        const isOp = node.type === 'op';
        const isIn = node.type === 'in';
        const isOut = node.type === 'out';
        const ports = { in: {}, out: {} };

        if (isIn) {
          const w = 76;
          const h = 28;
          const y = getWireY(node.wire) - h / 2;
          const x = colX;
          nodeCoords.set(node.id, { x, y, width: w, height: h, mode: 'in' });
          ports.out[node.wire] = { x: x + w, y: y + h / 2 };
        } else if (isOut) {
          const w = 76;
          const h = 28;
          const y = getWireY(node.wire) - h / 2;
          const x = colX;
          nodeCoords.set(node.id, { x, y, width: w, height: h, mode: 'out' });
          ports.in[node.wire] = { x: x, y: y + h / 2 };
        } else if (isOp) {
          const g = (node.gate || '').toLowerCase();
          const qubits = node.qubits || [];
          const clbits = node.clbits || [];

          if (['cx', 'cy', 'cz', 'swap', 'cp', 'crz'].includes(g) && qubits.length >= 2) {
            const y0 = getWireY(qubits[0]);
            const y1 = getWireY(qubits[1]);
            const topY = Math.min(y0, y1) - 22;
            const botY = Math.max(y0, y1) + 22;
            const w = 86;
            const h = botY - topY;
            const x = colX + 18;

            nodeCoords.set(node.id, { x, y: topY, width: w, height: h, mode: 'two-qubit', y0, y1 });
            ports.in[qubits[0]] = { x: x, y: y0 };
            ports.out[qubits[0]] = { x: x + w, y: y0 };
            ports.in[qubits[1]] = { x: x, y: y1 };
            ports.out[qubits[1]] = { x: x + w, y: y1 };
          } else if (g === 'measure') {
            const qWire = qubits[0] || 'q[0]';
            const cWire = clbits[0] || 'c[0]';
            const yQ = getWireY(qWire);
            const w = 92;
            const h = 54;
            const x = colX + 16;
            const y = yQ - h / 2;

            nodeCoords.set(node.id, { x, y, width: w, height: h, mode: 'measure', qWire, cWire });
            ports.in[qWire] = { x: x, y: yQ };
            ports.out[qWire] = { x: x + w, y: yQ };
            ports.out[cWire] = { x: x + w / 2, y: y + h };
          } else {
            const qWire = qubits[0] || 'q[0]';
            const yQ = getWireY(qWire);
            const w = 84;
            const h = 52;
            const x = colX + 20;
            const y = yQ - h / 2;

            nodeCoords.set(node.id, { x, y, width: w, height: h, mode: 'single-qubit', qWire });
            ports.in[qWire] = { x: x, y: yQ };
            ports.out[qWire] = { x: x + w, y: yQ };
          }
        }
        nodePorts.set(node.id, ports);
      });
    });
  } else {
    // ─── 2. COMPILER IR STAGES LAYOUT (Topological Frontiers) ───
    const colWidth = 230;
    const padX = 50;
    const padY = 95;
    const nodeGapY = 105;

    let maxNodesInCol = 1;
    sortedColKeys.forEach(colKey => {
      const count = layerCols.get(colKey).length;
      if (count > maxNodesInCol) maxNodesInCol = count;
    });

    totalHeight = Math.max(520, padY + maxNodesInCol * nodeGapY + 40);
    totalWidth = padX * 2 + sortedColKeys.length * colWidth + 40;

    sortedColKeys.forEach(colKey => {
      const colIdx = normalizedCol.get(colKey);
      const nodesInCol = layerCols.get(colKey);
      const colX = padX + colIdx * colWidth;

      // Draw background stage column (Frontier lane)
      const laneX = colX - 12;
      const laneW = colWidth - 20;
      const laneH = totalHeight - 45;

      const hasOnlyIn = nodesInCol.every(n => n.type === 'in');
      const hasOnlyOut = nodesInCol.every(n => n.type === 'out');
      let stageTitle = `STAGE ${colIdx + 1}: PARALLEL FRONTIER`;
      let stageSub = `Concurrent • 0 Dependencies`;

      if (hasOnlyIn) {
        stageTitle = `STAGE 0: INPUTS`;
        stageSub = `Qubit Initial States |0⟩`;
      } else if (hasOnlyOut) {
        stageTitle = `STAGE ${colIdx}: OUTPUTS`;
        stageSub = `Register Output Boundaries`;
      }

      stageLanesHtml += `
        <g class="stage-lane-group">
          <rect class="dag-stage-lane" x="${laneX}" y="20" width="${laneW}" height="${laneH}" rx="10"/>
          <g transform="translate(${laneX + 8}, 28)">
            <rect class="dag-stage-header-bg" width="${laneW - 16}" height="38" rx="6"/>
            <text x="${(laneW - 16)/2}" y="17" text-anchor="middle" font-size="9.5" font-weight="800" font-family="var(--font-mono)" fill="#c7d2fe">${stageTitle}</text>
            <text x="${(laneW - 16)/2}" y="31" text-anchor="middle" font-size="8" font-family="var(--font-mono)" fill="#94a3b8">${stageSub}</text>
          </g>
        </g>
      `;

      nodesInCol.forEach((node, rIdx) => {
        const isIn = node.type === 'in';
        const isOut = node.type === 'out';
        const w = (isIn || isOut) ? 140 : 175;
        const h = (isIn || isOut) ? 46 : 76;
        const x = colX + ((colWidth - 20) - w) / 2 - 2;
        const y = padY + rIdx * nodeGapY;

        nodeCoords.set(node.id, { x, y, width: w, height: h, mode: 'ir-card', colIdx });

        const ports = { in: {}, out: {} };
        const midY = y + h / 2;

        if (isIn) {
          ports.out[node.wire || 'q'] = { x: x + w, y: midY };
        } else if (isOut) {
          ports.in[node.wire || 'q'] = { x: x, y: midY };
        } else {
          // Op node with qubit / clbit ports
          const inWires = [...(node.qubits || []), ...(node.clbits || [])];
          const outWires = [...(node.qubits || []), ...(node.clbits || [])];
          
          if (inWires.length <= 1) {
            inWires.forEach(w => ports.in[w] = { x: x, y: midY });
          } else {
            const step = h / (inWires.length + 1);
            inWires.forEach((w, i) => ports.in[w] = { x: x, y: y + (i + 1) * step });
          }

          if (outWires.length <= 1) {
            outWires.forEach(w => ports.out[w] = { x: x + w, y: midY });
          } else {
            const step = h / (outWires.length + 1);
            outWires.forEach((w, i) => ports.out[w] = { x: x + w, y: y + (i + 1) * step });
          }
        }
        nodePorts.set(node.id, ports);
      });
    });
  }

  // SVG Defs
  const defs = `
    <defs>
      <marker id="dag-arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
        <path d="M 0 1.5 L 9 5 L 0 8.5 z" fill="#818cf8"/>
      </marker>
      <marker id="dag-arrow-clbit" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
        <path d="M 0 1.5 L 9 5 L 0 8.5 z" fill="#fbbf24"/>
      </marker>
      <marker id="dag-arrow-crit" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
        <path d="M 0 1.5 L 9 5 L 0 8.5 z" fill="#f59e0b"/>
      </marker>
      <marker id="dag-arrow-prereq" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
        <path d="M 0 1.5 L 9 5 L 0 8.5 z" fill="#f97316"/>
      </marker>
      <marker id="dag-arrow-dep" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
        <path d="M 0 1.5 L 9 5 L 0 8.5 z" fill="#a855f7"/>
      </marker>
      <linearGradient id="grad-node-op" x1="0" y1="0" x2="1" y2="1">
        <stop offset="0%" stop-color="#141c30"/>
        <stop offset="100%" stop-color="#0c1222"/>
      </linearGradient>
      <linearGradient id="grad-node-measure" x1="0" y1="0" x2="1" y2="1">
        <stop offset="0%" stop-color="#241b12"/>
        <stop offset="100%" stop-color="#120e0a"/>
      </linearGradient>
    </defs>
  `;

  // Draw Background Rails (only in Rails mode)
  let railsHtml = '';
  if (layoutMode === 'rails') {
    allOrderedWires.forEach(wire => {
      const y = getWireY(wire);
      const isClbit = wire.startsWith('c');
      const railClass = isClbit ? 'quantum-rail clbit' : 'quantum-rail';
      const badgeBorder = isClbit ? 'rgba(251,191,36,0.35)' : 'rgba(129,140,248,0.35)';
      const badgeFill = isClbit ? '#241b12' : '#0c1322';
      const textColor = isClbit ? '#fbbf24' : '#818cf8';

      railsHtml += `
        <g class="rail-track" data-wire="${wire}">
          <line x1="25" y1="${y}" x2="${totalWidth - 30}" y2="${y}" class="${railClass}"/>
          <g transform="translate(18, ${y - 12})">
            <rect width="48" height="24" rx="6" fill="${badgeFill}" stroke="${badgeBorder}" stroke-width="1.2"/>
            <text x="24" y="16" text-anchor="middle" font-size="11" font-weight="700" font-family="var(--font-mono)" fill="${textColor}">${wire}</text>
          </g>
        </g>
      `;
    });
  }

  // Draw Edges (Causal Dependencies)
  let edgesHtml = '';
  activeEdges.forEach(edge => {
    const srcPorts = nodePorts.get(edge.source);
    const dstPorts = nodePorts.get(edge.target);
    if (!srcPorts || !dstPorts) return;

    const wire = edge.wire || '';
    const srcPt = (srcPorts.out && srcPorts.out[wire]) || Object.values(srcPorts.out)[0];
    const dstPt = (dstPorts.in && dstPorts.in[wire]) || Object.values(dstPorts.in)[0];
    if (!srcPt || !dstPt) return;

    const x1 = srcPt.x;
    const y1 = srcPt.y;
    const x2 = dstPt.x;
    const y2 = dstPt.y;

    const isClbit = wire.startsWith('c');
    const isCriticalEdge = showDagCriticalPath && critEdgeSet.has(`${edge.source}->${edge.target}`);

    let marker = isClbit ? 'url(#dag-arrow-clbit)' : 'url(#dag-arrow)';
    if (isCriticalEdge) marker = 'url(#dag-arrow-crit)';

    let edgeClass = isClbit ? 'dag-edge clbit' : 'dag-edge';
    if (isCriticalEdge) edgeClass += ' on-critical-path';

    const strokeColor = isCriticalEdge ? '#f59e0b' : (isClbit ? '#fbbf24' : '#818cf8');
    const strokeDash = isClbit ? 'stroke-dasharray="4 3"' : '';

    let pathD = '';
    if (Math.abs(y1 - y2) < 2 && x2 > x1) {
      pathD = `M ${x1} ${y1} L ${x2} ${y2}`;
    } else {
      const dx = Math.max(30, Math.abs(x2 - x1) * 0.45);
      pathD = `M ${x1} ${y1} C ${x1 + dx} ${y1}, ${x2 - dx} ${y2}, ${x2} ${y2}`;
    }

    // Midpoint wire pill label
    const mx = (x1 + x2) / 2;
    const my = (y1 + y2) / 2;
    const pillBorder = isCriticalEdge ? '#f59e0b' : (isClbit ? 'rgba(251,191,36,0.5)' : 'rgba(129,140,248,0.4)');
    const pillColor = isCriticalEdge ? '#fbbf24' : (isClbit ? '#fbbf24' : '#38bdf8');

    edgesHtml += `
      <g class="edge-group" data-src="${edge.source}" data-dst="${edge.target}" data-wire="${wire}">
        <path d="${pathD}" class="${edgeClass}" stroke="${strokeColor}" stroke-width="${isCriticalEdge ? 3.5 : 2}" ${strokeDash} marker-end="${marker}"/>
        <g transform="translate(${mx}, ${my - 8})" class="edge-wire-pill" pointer-events="none">
          <rect x="-18" y="0" width="36" height="16" rx="4" fill="#0b1120" stroke="${pillBorder}" stroke-width="1"/>
          <text x="0" y="11" text-anchor="middle" font-size="8.5" font-weight="700" font-family="var(--font-mono)" fill="${pillColor}">${wire}</text>
        </g>
      </g>
    `;
  });

  // Draw Nodes
  let nodesHtml = '';
  activeNodes.forEach(node => {
    const pos = nodeCoords.get(node.id);
    if (!pos) return;

    const isCriticalNode = showDagCriticalPath && critNodeSet.has(node.id);
    const critClass = isCriticalNode ? ' on-critical-path' : '';

    if (pos.mode === 'ir-card') {
      // ─── COMPILER IR CARD NODE ───
      if (node.type === 'in') {
        const isClbit = (node.wire || '').startsWith('c');
        const borderColor = isCriticalNode ? '#f59e0b' : (isClbit ? '#fbbf24' : '#10b981');
        const badgeColor = isClbit ? '#fbbf24' : '#34d399';
        const label = isClbit ? `IN ${node.wire}` : `|0⟩ ${node.wire || ''}`;

        nodesHtml += `
          <g class="dag-node dag-in${critClass}" data-id="${node.id}" transform="translate(${pos.x}, ${pos.y})">
            <rect class="node-card-bg" width="${pos.width}" height="${pos.height}" rx="8" fill="#071d15" stroke="${borderColor}" stroke-width="1.6"/>
            <text x="12" y="16" font-size="8" font-weight="700" font-family="var(--font-mono)" fill="${badgeColor}">IN BOUNDARY</text>
            <text x="12" y="32" font-size="12" font-weight="800" font-family="var(--font-mono)" fill="#e2e8f0">${label}</text>
            <circle cx="${pos.width}" cy="${pos.height/2}" r="4" fill="${badgeColor}" stroke="#071d15" stroke-width="1.5"/>
            <text x="${pos.width - 8}" y="15" text-anchor="end" font-size="8.5" font-family="var(--font-mono)" fill="#64748b">#${node.id}</text>
          </g>
        `;
      } else if (node.type === 'out') {
        const isClbit = (node.wire || '').startsWith('c');
        const borderColor = isCriticalNode ? '#f59e0b' : (isClbit ? '#fbbf24' : '#f43f5e');
        const badgeColor = isClbit ? '#fbbf24' : '#fb7185';
        const label = isClbit ? `OUT ${node.wire}` : `OUT ${node.wire || ''}`;

        nodesHtml += `
          <g class="dag-node dag-out${critClass}" data-id="${node.id}" transform="translate(${pos.x}, ${pos.y})">
            <rect class="node-card-bg" width="${pos.width}" height="${pos.height}" rx="8" fill="#200d14" stroke="${borderColor}" stroke-width="1.6"/>
            <circle cx="0" cy="${pos.height/2}" r="4" fill="${badgeColor}" stroke="#200d14" stroke-width="1.5"/>
            <text x="12" y="16" font-size="8" font-weight="700" font-family="var(--font-mono)" fill="${badgeColor}">OUT BOUNDARY</text>
            <text x="12" y="32" font-size="12" font-weight="800" font-family="var(--font-mono)" fill="#e2e8f0">${label}</text>
            <text x="${pos.width - 8}" y="15" text-anchor="end" font-size="8.5" font-family="var(--font-mono)" fill="#64748b">#${node.id}</text>
          </g>
        `;
      } else {
        // Operation Node Card
        const gName = (node.gate || node.name || 'OP').toUpperCase();
        const isMeasure = gName === 'MEASURE';
        const isTwoQ = (node.qubits || []).length >= 2;
        const cardBg = isMeasure ? 'url(#grad-node-measure)' : 'url(#grad-node-op)';
        let cardBorder = isMeasure ? '#fbbf24' : (isTwoQ ? '#a78bfa' : '#818cf8');
        if (isCriticalNode) cardBorder = '#f59e0b';

        let targetText = (node.qubits || []).join(', ');
        if (node.clbits && node.clbits.length) {
          targetText += ` ⇒ ${node.clbits.join(', ')}`;
        }

        nodesHtml += `
          <g class="dag-node dag-op${critClass}" data-id="${node.id}" transform="translate(${pos.x}, ${pos.y})">
            <rect class="node-card-bg" width="${pos.width}" height="${pos.height}" rx="9" fill="${cardBg}" stroke="${cardBorder}" stroke-width="1.8"/>
            
            <!-- Header bar -->
            <rect x="0" y="0" width="${pos.width}" height="20" rx="9" fill="rgba(30, 41, 59, 0.45)"/>
            <text x="8" y="14" font-size="9" font-weight="700" font-family="var(--font-mono)" fill="#94a3b8">#${node.id}</text>
            ${isCriticalNode 
              ? `<text x="${pos.width - 8}" y="14" text-anchor="end" font-size="8" font-weight="800" font-family="var(--font-mono)" fill="#fbbf24">⚡ CRITICAL</text>`
              : `<text x="${pos.width - 8}" y="14" text-anchor="end" font-size="8" font-weight="600" font-family="var(--font-mono)" fill="#64748b">IR OP</text>`
            }

            <!-- Main Opcode -->
            <text x="10" y="40" font-size="15" font-weight="800" font-family="var(--font-mono)" fill="${isMeasure ? '#fbbf24' : (isTwoQ ? '#c4b5fd' : '#e2e8f0')}">${gName}</text>

            <!-- Wires / Targets -->
            <text x="10" y="55" font-size="9.5" font-family="var(--font-mono)" fill="#38bdf8">${targetText}</text>

            <!-- In/Out degree stats -->
            <text x="10" y="68" font-size="8" font-family="var(--font-mono)" fill="#64748b">In: ${node.in_degree ?? 1} • Out: ${node.out_degree ?? 1}</text>
          </g>
        `;
      }
    } else if (pos.mode === 'in') {
      const isClbit = (node.wire || '').startsWith('c');
      const pillBorder = isCriticalNode ? '#f59e0b' : (isClbit ? '#fbbf24' : '#10b981');
      const pillFill = isClbit ? '#241b12' : '#072218';
      const pillText = isClbit ? '#fbbf24' : '#34d399';
      const label = isClbit ? `IN ${node.wire}` : `|0⟩ ${node.wire || ''}`;

      nodesHtml += `
        <g class="dag-node dag-in${critClass}" data-id="${node.id}" transform="translate(${pos.x}, ${pos.y})">
          <rect class="node-card-bg" width="${pos.width}" height="${pos.height}" rx="14" fill="${pillFill}" stroke="${pillBorder}" stroke-width="1.6"/>
          <text x="${pos.width/2}" y="18" text-anchor="middle" font-size="11" font-weight="700" font-family="var(--font-mono)" fill="${pillText}">${label}</text>
        </g>
      `;
    } else if (pos.mode === 'out') {
      const isClbit = (node.wire || '').startsWith('c');
      const pillBorder = isCriticalNode ? '#f59e0b' : (isClbit ? '#fbbf24' : '#f43f5e');
      const pillFill = isClbit ? '#241b12' : '#290b12';
      const pillText = isClbit ? '#fbbf24' : '#fb7185';
      const label = isClbit ? `OUT ${node.wire}` : `OUT ${node.wire || ''}`;

      nodesHtml += `
        <g class="dag-node dag-out${critClass}" data-id="${node.id}" transform="translate(${pos.x}, ${pos.y})">
          <rect class="node-card-bg" width="${pos.width}" height="${pos.height}" rx="14" fill="${pillFill}" stroke="${pillBorder}" stroke-width="1.6"/>
          <text x="${pos.width/2}" y="18" text-anchor="middle" font-size="11" font-weight="700" font-family="var(--font-mono)" fill="${pillText}">${label}</text>
        </g>
      `;
    } else if (pos.mode === 'two-qubit') {
      const gName = (node.gate || 'CX').toUpperCase();
      const midY = (pos.y0 + pos.y1) / 2;
      const centerX = pos.x + pos.width / 2;
      const borderCol = isCriticalNode ? '#f59e0b' : 'rgba(99,131,255,0.35)';

      nodesHtml += `
        <g class="dag-node dag-two-q${critClass}" data-id="${node.id}">
          <rect class="node-card-bg" x="${pos.x}" y="${pos.y}" width="${pos.width}" height="${pos.height}" rx="12" fill="rgba(18,20,38,0.85)" stroke="${borderCol}" stroke-width="1.5" stroke-dasharray="3 3"/>
          <line x1="${centerX}" y1="${pos.y0}" x2="${centerX}" y2="${pos.y1}" stroke="${isCriticalNode ? '#f59e0b' : '#818cf8'}" stroke-width="3" stroke-linecap="round"/>
          <circle cx="${centerX}" cy="${pos.y0}" r="12" fill="#0f172a" stroke="#38bdf8" stroke-width="2"/>
          <circle cx="${centerX}" cy="${pos.y0}" r="5" fill="#38bdf8"/>
          <g transform="translate(${centerX - 20}, ${midY - 11})">
            <rect width="40" height="22" rx="6" fill="#1e1b4b" stroke="${isCriticalNode ? '#f59e0b' : '#a78bfa'}" stroke-width="1.6"/>
            <text x="20" y="15" text-anchor="middle" font-size="11" font-weight="800" font-family="var(--font-mono)" fill="#c4b5fd">${gName}</text>
          </g>
          <circle cx="${centerX}" cy="${pos.y1}" r="15" fill="#0f172a" stroke="#a78bfa" stroke-width="2"/>
          <circle cx="${centerX}" cy="${pos.y1}" r="11" fill="none" stroke="#c4b5fd" stroke-width="2"/>
          <line x1="${centerX - 7}" y1="${pos.y1}" x2="${centerX + 7}" y2="${pos.y1}" stroke="#c4b5fd" stroke-width="2"/>
          <line x1="${centerX}" y1="${pos.y1 - 7}" x2="${centerX}" y2="${pos.y1 + 7}" stroke="#c4b5fd" stroke-width="2"/>
          <text x="${pos.x + pos.width - 6}" y="${pos.y + 13}" text-anchor="end" font-size="8.5" font-family="var(--font-mono)" fill="#64748b">#${node.id}</text>
        </g>
      `;
    } else if (pos.mode === 'measure') {
      nodesHtml += `
        <g class="dag-node dag-measure${critClass}" data-id="${node.id}" transform="translate(${pos.x}, ${pos.y})">
          <rect class="node-card-bg" width="${pos.width}" height="${pos.height}" rx="10" fill="url(#grad-node-measure)" stroke="${isCriticalNode ? '#f59e0b' : '#fbbf24'}" stroke-width="1.8"/>
          <line x1="10" y1="0" x2="${pos.width - 10}" y2="0" stroke="#fbbf24" stroke-width="2.5" stroke-linecap="round"/>
          <path d="M 26 30 A 18 18 0 0 1 62 30" fill="none" stroke="#fbbf24" stroke-width="1.8"/>
          <line x1="44" y1="30" x2="55" y2="16" stroke="#fbbf24" stroke-width="2" stroke-linecap="round"/>
          <text x="${pos.width/2}" y="44" text-anchor="middle" font-size="9" font-weight="700" font-family="var(--font-mono)" fill="#fef08a">MEASURE</text>
          <text x="${pos.width - 6}" y="12" text-anchor="end" font-size="8.5" font-family="var(--font-mono)" fill="#92400e">#${node.id}</text>
        </g>
      `;
    } else {
      const gName = (node.name || 'OP').toUpperCase();
      nodesHtml += `
        <g class="dag-node dag-single${critClass}" data-id="${node.id}" transform="translate(${pos.x}, ${pos.y})">
          <rect class="node-card-bg" width="${pos.width}" height="${pos.height}" rx="10" fill="url(#grad-node-op)" stroke="${isCriticalNode ? '#f59e0b' : '#818cf8'}" stroke-width="1.8"/>
          <line x1="10" y1="0" x2="${pos.width - 10}" y2="0" stroke="#38bdf8" stroke-width="2.5" stroke-linecap="round"/>
          <text x="${pos.width/2}" y="27" text-anchor="middle" font-size="14" font-weight="800" font-family="var(--font-mono)" fill="#e2e8f0">${gName}</text>
          <text x="${pos.width/2}" y="42" text-anchor="middle" font-size="10" font-family="var(--font-mono)" fill="#818cf8">${pos.qWire || ''}</text>
          <text x="${pos.width - 6}" y="12" text-anchor="end" font-size="8.5" font-family="var(--font-mono)" fill="#64748b">#${node.id}</text>
        </g>
      `;
    }
  });

  svg.setAttribute('viewBox', `0 0 ${Math.max(680, totalWidth)} ${Math.max(400, totalHeight)}`);
  svg.innerHTML = `
    ${defs}
    <g id="dag-pan-zoom-root" transform="translate(${dagTransform.x}, ${dagTransform.y}) scale(${dagTransform.scale})">
      <g class="dag-stages-layer">${stageLanesHtml}</g>
      <g class="dag-rails-layer">${railsHtml}</g>
      <g class="dag-edges-layer">${edgesHtml}</g>
      <g class="dag-nodes-layer">${nodesHtml}</g>
    </g>
  `;

  attachDagNodeInteractions(activeNodes, activeEdges, nodeLayer, critNodeSet);
}

function attachDagNodeInteractions(nodes, edges, nodeLayer, critNodeSet) {
  const svg = $('dag-svg');
  if (!svg) return;

  const nodeEls = svg.querySelectorAll('.dag-node');
  const edgeEls = svg.querySelectorAll('.edge-group');

  const incoming = new Map();
  const outgoing = new Map();
  edges.forEach(e => {
    if (!outgoing.has(e.source)) outgoing.set(e.source, []);
    outgoing.get(e.source).push(e.target);
    if (!incoming.has(e.target)) incoming.set(e.target, []);
    incoming.get(e.target).push(e.source);
  });

  const nodeMap = new Map();
  nodes.forEach(n => nodeMap.set(n.id, n));

  nodeEls.forEach(nodeEl => {
    const id = parseInt(nodeEl.dataset.id, 10);
    const node = nodeMap.get(id);

    nodeEl.addEventListener('mouseenter', () => {
      const preds = new Set(incoming.get(id) || []);
      const succs = new Set(outgoing.get(id) || []);

      nodeEls.forEach(el => {
        const nid = parseInt(el.dataset.id, 10);
        if (nid === id) {
          el.classList.add('active-selected');
        } else if (preds.has(nid)) {
          el.classList.add('is-prerequisite');
        } else if (succs.has(nid)) {
          el.classList.add('is-dependent');
        } else {
          el.classList.add('is-independent');
        }
      });

      edgeEls.forEach(el => {
        const src = parseInt(el.dataset.src, 10);
        const dst = parseInt(el.dataset.dst, 10);
        const path = el.querySelector('.dag-edge');
        if (!path) return;

        if (dst === id) {
          path.classList.add('is-prereq-edge');
          path.setAttribute('marker-end', 'url(#dag-arrow-prereq)');
        } else if (src === id) {
          path.classList.add('is-dep-edge');
          path.setAttribute('marker-end', 'url(#dag-arrow-dep)');
        } else {
          path.classList.add('dimmed');
        }
      });
    });

    nodeEl.addEventListener('mouseleave', () => {
      nodeEls.forEach(el => el.classList.remove('active-selected', 'is-prerequisite', 'is-dependent', 'is-independent'));
      edgeEls.forEach(el => {
        const path = el.querySelector('.dag-edge');
        if (path) {
          path.classList.remove('is-prereq-edge', 'is-dep-edge', 'dimmed');
          const wire = el.dataset.wire || '';
          const isClbit = wire.startsWith('c');
          const src = parseInt(el.dataset.src, 10);
          const dst = parseInt(el.dataset.dst, 10);
          const isCrit = showDagCriticalPath && critNodeSet && critNodeSet.has(src) && critNodeSet.has(dst);
          path.setAttribute('marker-end', isCrit ? 'url(#dag-arrow-crit)' : (isClbit ? 'url(#dag-arrow-clbit)' : 'url(#dag-arrow)'));
        }
      });
    });

    nodeEl.addEventListener('click', (e) => {
      e.stopPropagation();
      openDagInspector(node, incoming.get(id) || [], outgoing.get(id) || [], nodeMap, nodeLayer, critNodeSet);
    });
  });
}

function openDagInspector(node, preds, succs, nodeMap, nodeLayer, critNodeSet) {
  const inspector = $('dag-inspector');
  const title = $('inspector-title');
  const body = $('inspector-body');
  if (!inspector || !title || !body || !node) return;

  title.textContent = `[IR Node #${node.id}] ${node.name || 'Node'}`;

  const predNames = preds.map(id => `#${id} ${nodeMap.get(id)?.name || ''}`).join(', ') || 'None (Roots)';
  const succNames = succs.map(id => `#${id} ${nodeMap.get(id)?.name || ''}`).join(', ') || 'None (Terminals)';
  const stageNum = nodeLayer?.has(node.id) ? `Stage ${nodeLayer.get(node.id)}` : '—';
  const isCrit = critNodeSet?.has(node.id);

  let extraRows = '';
  if (node.type === 'op') {
    extraRows += `
      <div class="inspector-row"><span class="inspector-key">Opcode:</span><span class="inspector-val" style="color:var(--indigo);font-weight:700;">${(node.gate || '').toUpperCase()}</span></div>
      <div class="inspector-row"><span class="inspector-key">Target Qubits:</span><span class="inspector-val">${node.qubits?.join(', ') || '—'}</span></div>
      ${node.clbits?.length ? `<div class="inspector-row"><span class="inspector-key">Classical Bits:</span><span class="inspector-val" style="color:var(--amber);">${node.clbits.join(', ')}</span></div>` : ''}
      ${node.params?.length ? `<div class="inspector-row"><span class="inspector-key">Gate Angles:</span><span class="inspector-val">[${node.params.map(p => Number(p).toFixed(3)).join(', ')}]</span></div>` : ''}
    `;
  } else {
    extraRows += `
      <div class="inspector-row"><span class="inspector-key">Wire Register:</span><span class="inspector-val">${node.wire || '—'}</span></div>
    `;
  }

  body.innerHTML = `
    <div class="inspector-row"><span class="inspector-key">IR Kind:</span><span class="inspector-val">${(node.type || '').toUpperCase()} IR NODE</span></div>
    <div class="inspector-row"><span class="inspector-key">Scheduling Tier:</span><span class="inspector-val" style="color:var(--sky);">${stageNum}</span></div>
    ${extraRows}
    <div class="inspector-row">
      <span class="inspector-key">Critical Path:</span>
      <span class="inspector-val" style="color:${isCrit ? '#fbbf24' : '#34d399'};font-weight:700;">
        ${isCrit ? '⚡ Yes (Depth Bottleneck)' : 'No (Slack available)'}
      </span>
    </div>
    <div class="inspector-row"><span class="inspector-key">Prerequisites:</span><span class="inspector-val">${predNames}</span></div>
    <div class="inspector-row"><span class="inspector-key">Dependents:</span><span class="inspector-val">${succNames}</span></div>
    <div style="font-size:0.69rem;color:#94a3b8;line-height:1.45;margin-top:8px;border-top:1px solid rgba(129,140,248,0.2);padding-top:6px;">
      <strong>Compiler IR Role:</strong> Preserves causality on wires. Any op in this stage without dependency can run in parallel; adjacent self-inverses can be collapsed by optimization passes.
    </div>
  `;

  inspector.classList.remove('hidden');
}

function setupDagControls() {
  const svgWrap = $('dag-svg-wrap');
  const btnZoomIn = $('btn-dag-zoom-in');
  const btnZoomOut = $('btn-dag-zoom-out');
  const btnZoomReset = $('btn-dag-zoom-reset');
  const btnVisual = $('btn-dag-visual');
  const btnLayers = $('btn-dag-layers');
  const btnAscii = $('btn-dag-ascii');
  const toggleWires = $('toggle-dag-wires');
  const btnCloseInspector = $('btn-close-inspector');
  const btnCopyAscii = $('btn-copy-dag-ascii');
  const btnCritical = $('btn-toggle-critical');

  function updateTransform() {
    const root = $('dag-pan-zoom-root');
    if (root) {
      root.setAttribute('transform', `translate(${dagTransform.x}, ${dagTransform.y}) scale(${dagTransform.scale})`);
    }
  }

  btnZoomIn?.addEventListener('click', () => {
    dagTransform.scale = Math.min(3.0, dagTransform.scale * 1.25);
    updateTransform();
  });
  btnZoomOut?.addEventListener('click', () => {
    dagTransform.scale = Math.max(0.3, dagTransform.scale * 0.8);
    updateTransform();
  });
  btnZoomReset?.addEventListener('click', () => {
    dagTransform = { x: 30, y: 30, scale: 1.0 };
    updateTransform();
  });

  if (svgWrap) {
    svgWrap.addEventListener('mousedown', (e) => {
      if (e.target.closest('.dag-node') || e.target.closest('.dag-inspector')) return;
      isDagPanning = true;
      dagPanStart = { x: e.clientX - dagTransform.x, y: e.clientY - dagTransform.y };
    });

    window.addEventListener('mousemove', (e) => {
      if (!isDagPanning) return;
      dagTransform.x = e.clientX - dagPanStart.x;
      dagTransform.y = e.clientY - dagPanStart.y;
      updateTransform();
    });

    window.addEventListener('mouseup', () => {
      isDagPanning = false;
    });

    svgWrap.addEventListener('wheel', (e) => {
      e.preventDefault();
      const zoomFactor = e.deltaY < 0 ? 1.12 : 0.89;
      dagTransform.scale = Math.max(0.25, Math.min(3.0, dagTransform.scale * zoomFactor));
      updateTransform();
    }, { passive: false });
  }

  function setDagMode(mode) {
    const visual = $('dag-visual-view');
    const layers = $('dag-layers-view');
    const ascii = $('dag-ascii-view');

    [btnVisual, btnLayers, btnAscii].forEach(b => b?.classList.remove('active'));
    [visual, layers, ascii].forEach(v => v?.classList.add('hidden'));

    if (mode === 'visual') {
      btnVisual?.classList.add('active');
      visual?.classList.remove('hidden');
    } else if (mode === 'layers') {
      btnLayers?.classList.add('active');
      layers?.classList.remove('hidden');
    } else if (mode === 'ascii') {
      btnAscii?.classList.add('active');
      ascii?.classList.remove('hidden');
    }
  }

  btnVisual?.addEventListener('click', () => setDagMode('visual'));
  btnLayers?.addEventListener('click', () => setDagMode('layers'));
  btnAscii?.addEventListener('click', () => setDagMode('ascii'));

  toggleWires?.addEventListener('change', () => {
    if (currentDagInfo && currentDagInfo.graph) {
      drawDagSvg(currentDagInfo.graph, toggleWires.checked, currentDagLayout);
    }
  });

  btnCritical?.addEventListener('click', () => {
    showDagCriticalPath = !showDagCriticalPath;
    btnCritical.classList.toggle('active', showDagCriticalPath);
    if (currentDagInfo && currentDagInfo.graph) {
      drawDagSvg(currentDagInfo.graph, toggleWires?.checked, currentDagLayout);
    }
  });

  const btnRails = $('btn-layout-rails');
  const btnTree = $('btn-layout-tree');

  btnRails?.addEventListener('click', () => {
    btnRails.classList.add('active');
    btnTree?.classList.remove('active');
    currentDagLayout = 'rails';
    if (currentDagInfo && currentDagInfo.graph) {
      drawDagSvg(currentDagInfo.graph, toggleWires?.checked, 'rails');
    }
  });

  btnTree?.addEventListener('click', () => {
    btnTree.classList.add('active');
    btnRails?.classList.remove('active');
    currentDagLayout = 'tree';
    if (currentDagInfo && currentDagInfo.graph) {
      drawDagSvg(currentDagInfo.graph, toggleWires?.checked, 'tree');
    }
  });

  btnCloseInspector?.addEventListener('click', () => {
    $('dag-inspector')?.classList.add('hidden');
  });

  btnCopyAscii?.addEventListener('click', () => {
    if (currentDagInfo?.ascii_draw) {
      navigator.clipboard.writeText(currentDagInfo.ascii_draw).then(() => {
        showToast('DAG ASCII copied!');
      });
    }
  });
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
setupDagControls();
