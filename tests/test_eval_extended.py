"""Run extended evaluation scenarios."""

import subprocess
import sys
from pathlib import Path


def test_extended_eval_scenarios_pass():
    root = Path(__file__).resolve().parent.parent
    import os

    env = os.environ.copy()
    env["PYTHONPATH"] = str(root)
    result = subprocess.run(
        [sys.executable, str(root / "evals" / "run_review_cases.py"), "--extended"],
        cwd=root,
        capture_output=True,
        text=True,
        env=env,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "19/19 scenarios passed" in result.stdout
