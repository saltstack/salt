import os
import pathlib

import pytest

import salt.scripts
import salt.utils.platform
from tests.conftest import CODE_DIR
from tests.support.mock import MagicMock, patch


def test_within_onedir_env(shell):
    if os.environ.get("ONEDIR_TESTRUN", "0") == "0":
        return

    script_name = "salt-pip"
    if salt.utils.platform.is_windows():
        script_name += ".exe"

    script_path = CODE_DIR / "artifacts" / "salt" / script_name
    assert script_path.exists()

    ret = shell.run(str(script_path), "list")
    assert ret.returncode == 0


def test_outside_onedir_env(capsys):
    with patch("salt.scripts._get_onedir_env_path", return_value=None):
        with pytest.raises(SystemExit) as exc:
            salt.scripts.salt_pip()
    captured = capsys.readouterr()
    assert "'salt-pip' is only meant to be used from a Salt onedir." in captured.err


def _run_salt_pip_capturing_subprocess(tmp_path, monkeypatch, env_overrides):
    """
    Drive ``salt.scripts.salt_pip`` end-to-end while stubbing out the
    actual ``python -m pip`` invocation. Returns the ``env`` mapping
    that ``salt_pip`` handed to ``subprocess.run``.

    ``env_overrides`` is applied to ``os.environ`` via ``monkeypatch``
    *before* ``salt_pip`` runs so the test controls whether
    ``PIP_DISABLE_PIP_VERSION_CHECK`` is already set by the "operator".
    """
    # Scrub any inherited copy of the var first, then apply overrides.
    monkeypatch.delenv("PIP_DISABLE_PIP_VERSION_CHECK", raising=False)
    for key, value in env_overrides.items():
        monkeypatch.setenv(key, value)

    # Force a deterministic argv so _pip_args stays a no-op.
    monkeypatch.setattr("sys.argv", ["salt-pip", "--version"])

    # Pretend we're inside an onedir; the path only feeds the
    # ``extras-X.Y`` string appended to PYTHONPATH.
    fake_relenv = pathlib.Path(tmp_path)
    fake_subprocess_result = MagicMock()
    fake_subprocess_result.returncode = 0

    recorded = {}

    def fake_run(command, shell, check, env):
        recorded["command"] = command
        recorded["env"] = env
        return fake_subprocess_result

    with patch("salt.scripts._get_onedir_env_path", return_value=fake_relenv), patch(
        "salt.config.minion_config", return_value={"user": None}
    ), patch("salt.utils.user.get_user", return_value="root"), patch(
        "salt.scripts.subprocess.run", side_effect=fake_run
    ):
        with pytest.raises(SystemExit) as exc:
            salt.scripts.salt_pip()

    assert exc.value.code == 0
    assert "command" in recorded, "subprocess.run was never invoked"
    return recorded


def test_salt_pip_subprocess_gets_disable_version_check_env(tmp_path, monkeypatch):
    """
    Regression test for #70024, end-to-end.

    Drive ``salt.scripts.salt_pip`` with a stubbed ``subprocess.run`` and
    assert the ``env`` dict handed to the child ``python -m pip`` process
    has ``PIP_DISABLE_PIP_VERSION_CHECK=1``. This catches a future
    refactor that stopped routing ``salt_pip`` through
    ``_pip_environment`` — the unit test on ``_pip_environment`` alone
    would still pass in that case.
    """
    recorded = _run_salt_pip_capturing_subprocess(
        tmp_path, monkeypatch, env_overrides={}
    )
    assert recorded["env"].get("PIP_DISABLE_PIP_VERSION_CHECK") == "1"


def test_salt_pip_subprocess_respects_operator_override(tmp_path, monkeypatch):
    """
    Regression test for #70024, end-to-end.

    If an operator has already exported ``PIP_DISABLE_PIP_VERSION_CHECK=0``
    (i.e., they want pip's periodic version check back), ``salt-pip``
    must not stomp on it.
    """
    recorded = _run_salt_pip_capturing_subprocess(
        tmp_path,
        monkeypatch,
        env_overrides={"PIP_DISABLE_PIP_VERSION_CHECK": "0"},
    )
    assert recorded["env"].get("PIP_DISABLE_PIP_VERSION_CHECK") == "0"
