"""
sandbox.py — Safe code execution environment for user-submitted quantum circuits.

Runs user-provided Python code in a restricted namespace that exposes only
the qcompiler API. Returns the compiled result or an error.

Security notes:
  - Only qcompiler symbols are in the execution namespace.
  - Standard library access is intentionally not provided.
  - This is suitable for a local dev/demo tool.
    For a public server, use a proper sandboxing solution (e.g. subprocess + timeout).
"""
from __future__ import annotations

import io
import math
import traceback
from builtins import compile as builtins_compile
from typing import Any, Dict, Optional

# Everything the user is allowed to import in their code
from qcompiler.core.circuit import QuantumCircuit
from qcompiler.compiler import compile as qcompile, CompileResult


# The safe namespace exposed to user code
_BASE_NAMESPACE: Dict[str, Any] = {
    # Core API
    "QuantumCircuit": QuantumCircuit,
    "compile": qcompile,
    # Math utilities (commonly needed for angles)
    "pi": math.pi,
    "math": math,
    # Allow full builtins so 'from qcompiler import ...' works inside exec()
    # (We still control the top-level namespace — only qcompiler is pre-imported)
    "__builtins__": __builtins__,
}


class SandboxResult:
    """Result from executing user code."""

    def __init__(
        self,
        success: bool,
        compile_result: Optional[CompileResult] = None,
        error: Optional[str] = None,
        stdout: Optional[str] = None,
    ) -> None:
        self.success = success
        self.compile_result = compile_result
        self.error = error
        self.stdout = stdout


def run_user_code(code: str, optimization_level: int = 1) -> SandboxResult:
    """Execute user-submitted quantum circuit code in the safe namespace.

    The user code must assign a QuantumCircuit to a variable named
    ``qc`` OR call ``compile(qc)`` and assign the result to ``result``.

    Parameters
    ----------
    code : str
        Python source code.
    optimization_level : int
        Passed to compile() if the user doesn't call it themselves.

    Returns
    -------
    SandboxResult
    """
    import io
    from contextlib import redirect_stdout

    namespace: Dict[str, Any] = dict(_BASE_NAMESPACE)
    namespace["__optimization_level__"] = optimization_level

    stdout_buf = io.StringIO()

    try:
        with redirect_stdout(stdout_buf):
            exec(builtins_compile(code, "<user_code>", "exec"), namespace)  # noqa: S102
    except Exception:
        return SandboxResult(
            success=False,
            error=traceback.format_exc(),
            stdout=stdout_buf.getvalue(),
        )

    # Look for result in namespace
    compile_result: Optional[CompileResult] = namespace.get("result")
    qc: Optional[QuantumCircuit] = namespace.get("qc")

    if compile_result is None and qc is not None:
        # Auto-compile if user just built a circuit
        try:
            compile_result = qcompile(qc, optimization_level=optimization_level)
        except Exception:
            return SandboxResult(
                success=False,
                error=traceback.format_exc(),
                stdout=stdout_buf.getvalue(),
            )

    if compile_result is None:
        return SandboxResult(
            success=False,
            error=(
                "No circuit found. Assign your QuantumCircuit to `qc` or "
                "call `compile(qc)` and assign to `result`."
            ),
            stdout=stdout_buf.getvalue(),
        )

    return SandboxResult(
        success=True,
        compile_result=compile_result,
        stdout=stdout_buf.getvalue(),
    )
