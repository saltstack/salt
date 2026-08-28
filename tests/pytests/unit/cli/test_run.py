"""
Unit tests for the salt-run CLI (salt.cli.run.SaltRun).
"""

import pytest

from salt.cli.run import SaltRun
from salt.exceptions import SaltClientError
from tests.support.mock import MagicMock, patch


def _fake_saltrun():
    """
    A stand-in SaltRun self with just the attributes run() touches, so the
    method can be exercised without full CLI parsing.
    """
    fake = MagicMock()
    fake.options.profiling_enabled = False
    fake.options.doc = False
    fake.config = {"user": "root"}
    # Mirrors optparse.OptionParser.exit(): raises SystemExit for real
    # instead of being swallowed as a no-op mock call.
    fake.exit.side_effect = SystemExit(0)
    return fake


def test_run_destroys_runner_on_normal_exit():
    """
    Regression test for GH #70174: salt-run leaked its Runner (and the
    MasterMinion it lazily creates) because it was never destroy()'d,
    relying instead on __del__'s GC-time safety net -- which now logs a
    loud "unclosed Runner"/"unclosed MasterMinion" WARNING. destroy() must
    run on the normal, successful exit path too.
    """
    fake = _fake_saltrun()
    fake_runner = MagicMock()
    fake_runner.run.return_value = {"retcode": 0}
    with (
        patch("salt.runner.Runner", return_value=fake_runner),
        patch("salt.cli.run.check_user", return_value=True),
    ):
        with pytest.raises(SystemExit):
            SaltRun.run(fake)
    fake_runner.destroy.assert_called_once()


def test_run_destroys_runner_on_doc_exit():
    """
    ``--doc`` exits early, before the runner is ever executed; destroy()
    must still run.
    """
    fake = _fake_saltrun()
    fake.options.doc = True
    fake_runner = MagicMock()
    with patch("salt.runner.Runner", return_value=fake_runner):
        with pytest.raises(SystemExit):
            SaltRun.run(fake)
    fake_runner.print_docs.assert_called_once()
    fake_runner.destroy.assert_called_once()


def test_run_destroys_runner_on_saltclienterror():
    """
    destroy() must still run when runner.run() raises SaltClientError.
    """
    fake = _fake_saltrun()
    fake_runner = MagicMock()
    fake_runner.run.side_effect = SaltClientError("boom")
    with (
        patch("salt.runner.Runner", return_value=fake_runner),
        patch("salt.cli.run.check_user", return_value=True),
    ):
        with pytest.raises(SystemExit):
            SaltRun.run(fake)
    fake_runner.destroy.assert_called_once()
