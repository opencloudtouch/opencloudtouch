"""
Regression test for Python module importability (E2E Runner PYTHONPATH).

Bug History:
- Date: 2026-02-13
- Symptom: E2E tests showed black screen with "Fehler beim Laden der Geräte"
- Root Cause #1: E2E runner didn't set PYTHONPATH → ModuleNotFoundError
- Root Cause #2: Backend couldn't start → Frontend got Connection Refused
- Impact: All E2E tests failed (0/36 passing)
- Fix: Added PYTHONPATH=src to e2e-runner.mjs

This test ensures the opencloudtouch package is importable without editable install.
It runs in the same environment as the E2E runner (PYTHONPATH-based, not pip install -e).
"""

import sys
from pathlib import Path

import pytest


class TestModuleImportability:
    """Verify opencloudtouch module can be imported without editable install."""

    def test_opencloudtouch_importable(self):
        """
        Regression test: opencloudtouch module must be importable.

        This simulates what happens in E2E runner when starting uvicorn:
        `python -m uvicorn opencloudtouch.main:app`

        Without PYTHONPATH=src, this fails with ModuleNotFoundError.
        """
        try:
            import opencloudtouch

            assert opencloudtouch is not None
        except ModuleNotFoundError as e:
            pytest.fail(
                f"Failed to import opencloudtouch: {e}\n"
                "Ensure PYTHONPATH includes 'src' directory or package is installed."
            )

    def test_main_module_importable(self):
        """Verify opencloudtouch.main (FastAPI app) is importable."""
        try:
            from opencloudtouch.main import app

            assert app is not None
            assert hasattr(app, "routes")  # FastAPI app has routes
        except ModuleNotFoundError as e:
            pytest.fail(
                f"Failed to import opencloudtouch.main: {e}\n"
                "E2E runner cannot start backend without this!"
            )

    def test_pythonpath_includes_src(self):
        """
        Verify PYTHONPATH includes src directory (pytest.ini config).

        This is critical for:
        1. pytest (configured in pytest.ini)
        2. E2E runner (configured in e2e-runner.mjs)
        3. CI/CD (must work without editable install)
        """
        # Get backend src directory
        backend_dir = Path(__file__).parent.parent.parent
        src_dir = backend_dir / "src"

        # Check if src is in sys.path (added by pytest.ini or editable install)
        src_in_path = any(Path(p).resolve() == src_dir.resolve() for p in sys.path if p)

        assert src_in_path or self._is_editable_install(), (
            f"src directory ({src_dir}) not in sys.path. "
            "This will break E2E tests! "
            "Ensure pytest.ini has 'pythonpath = src' or run 'pip install -e .'"
        )

    def _is_editable_install(self) -> bool:
        """Check if package is installed in editable mode."""
        try:
            import opencloudtouch

            # Editable installs have __file__ in src directory
            return "src" in str(Path(opencloudtouch.__file__).parent)
        except Exception:
            return False

    def test_uvicorn_can_find_app(self):
        """
        Simulate what uvicorn does: import app from string path.

        This is exactly what fails in E2E runner if PYTHONPATH is wrong:
        `python -m uvicorn opencloudtouch.main:app`
        """
        import importlib

        try:
            # Simulate uvicorn's import_from_string
            module_path, app_name = "opencloudtouch.main", "app"
            module = importlib.import_module(module_path)
            app = getattr(module, app_name)

            assert app is not None
            assert callable(getattr(app, "routes", None)) or hasattr(app, "routes")
        except (ModuleNotFoundError, AttributeError) as e:
            pytest.fail(
                f"uvicorn cannot import app: {e}\n"
                "E2E runner will fail to start backend!"
            )
