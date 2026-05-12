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
