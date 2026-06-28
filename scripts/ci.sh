#!/usr/bin/env bash
set -euo pipefail

python -m pip install --upgrade pip setuptools wheel
pip install -e ".[dev]"
ruff check scope tests evals adapters
mypy scope
pytest
python evals/run_review_cases.py --extended