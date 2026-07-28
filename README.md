# Quantam

Quantam is a small collection of tools, notebooks and a lightweight web app for
building, simulating, benchmarking and analyzing quantum circuits. The project
includes utilities for circuit generation, random-circuit experiments, a Zero
Noise Extrapolation (ZNE) lab, and benchmarking harnesses used under
`quantum_benchmark`.

## Features

- Circuit utilities and example scripts (`quantum_circuits.py`, `random_circuit_fixed.py`).
- Jupyter notebooks with experiments and demos (e.g. `Grover's Algorithm.ipynb`).
- ZNE lab: a small web app to run and visualize extrapolation experiments
	(folder: ZNE-lab).
- Benchmarking framework located in `quantum_benchmark` for running tests
	and measurements.

## Repo structure (high level)

- `ZNE-lab/` — web app, configs and ZNE modules. See [ZNE-lab/app.py](ZNE-lab/app.py).
- `quantum_benchmark/` — circuits, simulators, tests and utilities.
- Notebooks such as `Grover's Algorithm.ipynb`, `randomcircuit.ipynb`, and others.
- Top-level scripts: `quantum_circuits.py`, `random_circuit_fixed.py`.

## Requirements & Setup

Recommended: create and use a virtual environment, then install requirements.

Windows (PowerShell):

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r "ZNE-lab\requirements.txt"
```

Unix / macOS (bash):

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r ZNE-lab/requirements.txt
```

If your environment already has the dependencies installed, you can skip
installing the requirements file.

## Running the ZNE Lab web app

From the repository root (with the virtualenv activated):

```bash
python ZNE-lab/app.py
```

Open http://localhost:5000 in your browser (or the address printed by the app).

## Running scripts and notebooks

- Run example scripts:

```bash
python quantum_circuits.py
python random_circuit_fixed.py
```

- Open notebooks with Jupyter:

```bash
jupyter notebook
```

## Tests and benchmarking

Run the test suite located under [quantum_benchmark/tests](quantum_benchmark/tests):

```bash
pip install pytest
pytest -q
```

## Contributing

Contributions are welcome. Please open issues or PRs describing the change.

## License

Add a `LICENSE` file to this repository to indicate the project's license.

## Contact

For questions or help, open an issue or contact the repository maintainer.

