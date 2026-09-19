"""
app.py — FastAPI server for the qcompiler web application.

Endpoints:
  GET  /                    → serve webapp/index.html
  GET  /api/examples        → list available example names
  GET  /api/examples/{name} → return example source code
  POST /api/compile         → compile user-submitted quantum code

Run with:
  cd e:\\Quantam
  uvicorn qcompiler.server.app:app --reload --port 8000
"""
from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

# Ensure the qcompiler package root is importable
_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from qcompiler.server.sandbox import run_user_code

# ---------------------------------------------------------------------------
# App setup
# ---------------------------------------------------------------------------

app = FastAPI(
    title="qcompiler",
    description="From-scratch quantum compiler pipeline: Python → DAG → OpenQASM 3",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static files (webapp/)
_WEBAPP_DIR = Path(__file__).parent.parent / "webapp"
app.mount("/static", StaticFiles(directory=str(_WEBAPP_DIR)), name="static")

# ---------------------------------------------------------------------------
# Example registry
# ---------------------------------------------------------------------------

_EXAMPLES_DIR = Path(__file__).parent.parent / "examples"

_EXAMPLE_DESCRIPTIONS = {
    "bell_state": "2-qubit Bell (maximally entangled) state",
    "ghz_state":  "4-qubit GHZ (Greenberger–Horne–Zeilinger) state",
    "qft":        "4-qubit Quantum Fourier Transform",
}

_EXAMPLE_SOURCES = {
    "bell_state": """\
# Bell State — 2 qubits
from qcompiler import QuantumCircuit, compile

qc = QuantumCircuit(2, 2, name="bell_state")
qc.h(0)
qc.cx(0, 1)
qc.measure(0, 0)
qc.measure(1, 1)

result = compile(qc, optimization_level=1)
""",
    "ghz_state": """\
# GHZ State — n qubits
from qcompiler import QuantumCircuit, compile

n = 4  # change me!
qc = QuantumCircuit(n, n, name=f"ghz_{n}")
qc.h(0)
for i in range(n - 1):
    qc.cx(i, i + 1)
qc.measure_all()

result = compile(qc, optimization_level=1)
""",
    "qft": """\
# Quantum Fourier Transform — n qubits
import math
from qcompiler import QuantumCircuit, compile

n = 4  # change me!
qc = QuantumCircuit(n, name=f"qft_{n}")

for j in range(n):
    qc.h(j)
    for k in range(j + 1, n):
        angle = math.pi / (2 ** (k - j))
        qc.cp(angle, k, j)

for i in range(n // 2):
    qc.swap(i, n - i - 1)

result = compile(qc, optimization_level=1)
""",
    "cancel_demo": """\
# Optimization demo: H·H cancellation
from qcompiler import QuantumCircuit, compile

qc = QuantumCircuit(2, name="cancel_demo")
# H·H = I — will be cancelled at opt level 1
qc.h(0)
qc.h(0)
# These survive
qc.cx(0, 1)
qc.t(1)
qc.tdg(1)   # T·Tdg = I — also cancelled

result = compile(qc, optimization_level=1)
""",
    "toffoli": """\
# Toffoli (CCX) gate — decomposes into CX, H, T, Tdg
from qcompiler import QuantumCircuit, compile

qc = QuantumCircuit(3, 3, name="toffoli")
qc.x(0)      # Set control qubits
qc.x(1)
qc.ccx(0, 1, 2)
qc.measure_all()

result = compile(qc, optimization_level=1)
""",
}


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------

class CompileRequest(BaseModel):
    code: str = Field(..., description="Python quantum circuit source code")
    optimization_level: int = Field(1, ge=0, le=2, description="0=none, 1=default, 2=aggressive")


class GateCountEntry(BaseModel):
    gate: str
    count: int


class CompileStats(BaseModel):
    num_qubits: int
    num_clbits: int
    original_gate_count: int
    optimized_gate_count: int
    final_gate_count: int
    original_depth: int
    final_depth: int
    optimization_level: int
    gate_counts: Dict[str, int]


class CompileResponse(BaseModel):
    success: bool
    qasm: Optional[str] = None
    circuit_draw: Optional[str] = None
    stats: Optional[CompileStats] = None
    dag_info: Optional[Dict[str, Any]] = None
    stdout: Optional[str] = None
    error: Optional[str] = None


class ExampleInfo(BaseModel):
    name: str
    description: str


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get("/", response_class=FileResponse)
async def serve_webapp():
    """Serve the main web application."""
    index = _WEBAPP_DIR / "index.html"
    if not index.exists():
        raise HTTPException(status_code=404, detail="webapp/index.html not found")
    return FileResponse(str(index))


@app.get("/api/examples", response_model=List[ExampleInfo])
async def list_examples():
    """Return all available example circuits."""
    return [
        ExampleInfo(name=name, description=desc)
        for name, desc in _EXAMPLE_DESCRIPTIONS.items()
    ]


@app.get("/api/examples/{name}")
async def get_example(name: str):
    """Return the source code for a named example."""
    src = _EXAMPLE_SOURCES.get(name)
    if src is None:
        raise HTTPException(status_code=404, detail=f"Example '{name}' not found.")
    return {"name": name, "code": src}


@app.post("/api/compile", response_model=CompileResponse)
async def compile_circuit(req: CompileRequest):
    """Compile user quantum code through the full pipeline."""
    sandbox_result = run_user_code(req.code, optimization_level=req.optimization_level)

    if not sandbox_result.success:
        return CompileResponse(
            success=False,
            error=sandbox_result.error,
            stdout=sandbox_result.stdout,
        )

    cr = sandbox_result.compile_result
    assert cr is not None

    # DAG layer info
    try:
        layers = cr.dag.layers()
        dag_info = {
            "num_layers": len(layers),
            "num_nodes": cr.dag.num_ops(),
            "depth": cr.dag.depth(),
            "layers": [
                [node.instruction.gate.name for node in layer if node.instruction]
                for layer in layers
            ],
        }
    except Exception:
        dag_info = {}

    return CompileResponse(
        success=True,
        qasm=cr.qasm,
        circuit_draw=cr.final_circuit.draw(),
        stats=CompileStats(**cr.stats),
        dag_info=dag_info,
        stdout=sandbox_result.stdout,
    )


@app.get("/api/health")
async def health():
    return {"status": "ok", "version": "0.1.0"}


# ---------------------------------------------------------------------------
# Dev runner
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("qcompiler.server.app:app", host="0.0.0.0", port=8000, reload=True)
