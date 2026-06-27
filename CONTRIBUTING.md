# Contributing

Thank you for contributing to SCOPE.

## Development setup

```bash
git clone https://github.com/fraware/SCOPE.git
cd SCOPE
pip install -e ".[dev]"
pytest
```

## Pre-push checklist

CI runs on **Python 3.10, 3.11, and 3.12** (see `.github/workflows/ci.yml`). Before you push, run the same pipeline locally:

**Linux / macOS / GitHub Actions:**

```bash
bash scripts/ci.sh
```

**Windows (PowerShell):**

```powershell
.\scripts\ci.ps1
```

Equivalent manual steps:

```bash
python -m pip install --upgrade pip setuptools wheel
pip install -e ".[dev]"
ruff check scope tests evals adapters
mypy scope
pytest
python evals/run_review_cases.py
```

Ensure `pyproject.toml` is saved as UTF-8 **without** a BOM (a BOM breaks `pip install -e`).

## Pull requests

1. Fork and create a feature branch
2. Add tests for behavior changes
3. Run the pre-push checklist above
4. Update docs if schemas or policy semantics change

## Code style

- Type hints on public APIs
- Minimal, focused diffs
- Match existing module structure

See [docs/limitations.md](docs/limitations.md) for v0.1 scope boundaries.