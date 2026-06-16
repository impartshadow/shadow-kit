"""Tests for the public demo entrypoint."""

import subprocess
import sys


def test_module_demo_runs():
    result = subprocess.run(
        [sys.executable, "-m", "shadow_kit.demo"],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "Example 1: Verify before push" in result.stdout
    assert "[BLOCK] verify-before-push" in result.stdout
    assert "Example 6: Signed receipt" in result.stdout
    assert "Signature valid: True" in result.stdout
