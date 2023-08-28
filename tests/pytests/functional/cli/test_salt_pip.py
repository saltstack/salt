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
