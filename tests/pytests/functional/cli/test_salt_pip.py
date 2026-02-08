import os

import pytest

import salt.scripts
import salt.utils.platform
from tests.conftest import CODE_DIR
from tests.support.mock import patch


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


def test_salt_pip_checks_minion_user(tmp_path):
    relenv_path = tmp_path / "relenv"
    config_dir = relenv_path / "etc" / "salt"
    config_dir.mkdir(parents=True)
    minion_config_path = config_dir / "minion"
    with patch(
        "salt.scripts._get_onedir_env_path", return_value=relenv_path
    ), patch(
        "salt.config.minion_config", return_value={"user": "salt"}
    ) as minion_config_mock, patch(
        "salt.utils.verify.check_user_from_opts", return_value=True
    ) as check_user_mock, patch(
        "subprocess.run"
    ) as run_mock, patch(
        "sys.argv", ["salt-pip", "list"]
    ):
        run_mock.return_value.returncode = 0
        with pytest.raises(SystemExit) as exc:
            salt.scripts.salt_pip()
        assert exc.value.code == 0
        minion_config_mock.assert_called_once_with(str(minion_config_path))
        check_user_mock.assert_called_once()