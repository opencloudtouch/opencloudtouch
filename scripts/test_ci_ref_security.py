"""Regression tests for the auto-format PR branch handling (issue #589)."""

import os
import subprocess
import tempfile
import unittest
from pathlib import Path

WORKFLOW = Path(__file__).resolve().parents[1] / ".github/workflows/ci.yml"


class TestAutoformatBranchSafety(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.workflow = WORKFLOW.read_text(encoding="utf-8")
        step = cls.workflow.split("      - name: Determine branch ref\n", 1)[1].split(
            "      - name: Checkout code\n", 1
        )[0]
        cls.step = step
        cls.script = "\n".join(
            line[10:] if line.startswith("          ") else line
            for line in step.split("        run: |\n", 1)[1].splitlines()
        )

    def test_no_direct_expression_in_shell(self):
        self.assertIn("HEAD_REF: ${{ github.event.pull_request.head.ref }}", self.step)
        self.assertIn("REF_NAME: ${{ github.ref_name }}", self.step)
        self.assertNotIn("${{", self.script)

    def test_push_uses_quoted_ref_from_environment(self):
        push_step = self.workflow.split("      - name: Commit and push if changed\n", 1)[1]
        self.assertIn("BRANCH: ${{ steps.ref.outputs.branch }}", push_step)
        self.assertIn('git push origin "refs/heads/$BRANCH"', push_step)
        self.assertNotIn("${{", push_step.split("        run: |\n", 1)[1])

    def run_branch(self, value):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "output"
            marker = Path(directory) / "injected"
            env = dict(os.environ, EVENT_NAME="pull_request", HEAD_REF=value,
                       REF_NAME="unused", GITHUB_OUTPUT=str(output))
            result = subprocess.run(
                ["bash", "-e", "-c", self.script], env=env,
                capture_output=True, text=True, check=False
            )
            self.assertFalse(marker.exists(), "Injected command executed")
            return result, output.read_text() if output.exists() else ""

    def test_valid_unusual_branch(self):
        result, output = self.run_branch("test/ci-589.valid_name-01")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(output, "branch=test/ci-589.valid_name-01\n")

    def test_injection_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            marker = Path(directory) / "injected"
            attacks = [
                f"test; echo INJECTION_SUCCEEDED > {marker}",
                f"test/$(touch {marker})",
                "test/`echo INJECTION_SUCCEEDED`",
                "test/ok\nINJECTION_SUCCEEDED=true",
                "",
            ]
            for attack in attacks:
                with self.subTest(attack=attack):
                    result, output = self.run_branch(attack)
                    self.assertNotEqual(result.returncode, 0)
                    self.assertIn("Invalid branch name", result.stdout)
                    self.assertEqual(output, "")
                    self.assertFalse(marker.exists())


if __name__ == "__main__":
    unittest.main()
