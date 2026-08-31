import os

import salt.scripts
from tests.support.mock import MagicMock, patch


def test_salt_pip_checks_user():
    # Mock dependencies
    mock_minion_config = MagicMock(return_value={"user": "salt"})
    mock_get_user = MagicMock(return_value="root")  # Running as root
    mock_check_user = MagicMock()

    # Mock onedir path to proceed past initial check
    mock_onedir_path = MagicMock()
    mock_onedir_path.__truediv__.return_value = "extras"

    with patch(
        "salt.scripts._get_onedir_env_path", return_value=mock_onedir_path
    ), patch("salt.config.minion_config", mock_minion_config), patch(
        "salt.utils.user.get_user", mock_get_user
    ), patch(
        "salt.utils.verify.check_user", mock_check_user
    ), patch(
        "subprocess.run"
    ) as mock_run, patch(
        "sys.exit"
    ) as mock_exit:

        # We need to ensure we don't actually exit in a way that breaks test runner,
        # but salt_pip calls sys.exit.
        # mock_exit will catch it.

        salt.scripts.salt_pip()

        # Verify check_user was called with "salt"
        mock_check_user.assert_called_with("salt")


def test_salt_pip_no_user_switch_if_same():
    # Mock dependencies
    mock_minion_config = MagicMock(return_value={"user": "root"})
    mock_get_user = MagicMock(return_value="root")  # Running as root
    mock_check_user = MagicMock()

    mock_onedir_path = MagicMock()
    mock_onedir_path.__truediv__.return_value = "extras"

    with patch(
        "salt.scripts._get_onedir_env_path", return_value=mock_onedir_path
    ), patch("salt.config.minion_config", mock_minion_config), patch(
        "salt.utils.user.get_user", mock_get_user
    ), patch(
        "salt.utils.verify.check_user", mock_check_user
    ), patch(
        "subprocess.run"
    ) as mock_run, patch(
        "sys.exit"
    ):

        salt.scripts.salt_pip()

        # Verify check_user was NOT called
        mock_check_user.assert_not_called()


def test_salt_pip_network_lockdown_opts_flow_to_subprocess_env():
    """
    saltpip_no_deps/saltpip_no_index/saltpip_disable_pip_version_check/
    saltpip_use_pythonpath, when set in minion config, actually reach the
    pip subprocess's environment end-to-end through salt_pip().
    """
    mock_minion_config = MagicMock(
        return_value={
            "user": "root",
            "saltpip_use_pythonpath": True,
            "saltpip_no_deps": True,
            "saltpip_no_index": True,
            "saltpip_disable_pip_version_check": True,
        }
    )
    mock_get_user = MagicMock(return_value="root")

    mock_onedir_path = MagicMock()
    mock_onedir_path.__truediv__.return_value = "extras"

    with patch(
        "salt.scripts._get_onedir_env_path", return_value=mock_onedir_path
    ), patch("salt.config.minion_config", mock_minion_config), patch(
        "salt.utils.user.get_user", mock_get_user
    ), patch(
        "os.environ.copy", return_value={"PYTHONPATH": "/leaked/system/path"}
    ), patch(
        "subprocess.run"
    ) as mock_run, patch(
        "sys.exit"
    ):

        salt.scripts.salt_pip()

        called_env = mock_run.call_args.kwargs["env"]
        assert called_env["PYTHONPATH"] == f"extras{os.pathsep}/leaked/system/path"
        assert called_env["PIP_NO_DEPS"] == "1"
        assert called_env["PIP_NO_INDEX"] == "1"
        assert called_env["PIP_DISABLE_PIP_VERSION_CHECK"] == "1"


def test_salt_pip_network_lockdown_opts_default_off():
    """
    Without any saltpip_* options set, the PIP_* lockdown env vars are not
    injected at all -- current behavior is unchanged.

    Uses a controlled, empty base environment (rather than the real
    ambient one) since CI runners commonly set vars like
    PIP_DISABLE_PIP_VERSION_CHECK themselves for unrelated reasons, which
    would otherwise leak through and make this assertion flaky/host
    dependent -- salt-pip correctly leaves pre-existing env vars alone
    when the corresponding option is off, it's the test's job to control
    what's "pre-existing" here.
    """
    mock_minion_config = MagicMock(return_value={"user": "root"})
    mock_get_user = MagicMock(return_value="root")

    mock_onedir_path = MagicMock()
    mock_onedir_path.__truediv__.return_value = "extras"

    with patch(
        "salt.scripts._get_onedir_env_path", return_value=mock_onedir_path
    ), patch("salt.config.minion_config", mock_minion_config), patch(
        "salt.utils.user.get_user", mock_get_user
    ), patch(
        "os.environ.copy", return_value={}
    ), patch(
        "subprocess.run"
    ) as mock_run, patch(
        "sys.exit"
    ):

        salt.scripts.salt_pip()

        called_env = mock_run.call_args.kwargs["env"]
        assert called_env["PYTHONPATH"] == "extras"
        assert "PIP_NO_DEPS" not in called_env
        assert "PIP_NO_INDEX" not in called_env
        assert "PIP_DISABLE_PIP_VERSION_CHECK" not in called_env
