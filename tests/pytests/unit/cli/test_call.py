import salt.cli.call
import salt.defaults.exitcodes
from tests.support.mock import MagicMock, patch


def test_check_user_called_even_with_sudo_user():
    with patch("salt.utils.parsers.SaltCallOptionParser.parse_args"), patch(
        "salt.cli.caller.Caller"
    ), patch("salt.utils.verify.verify_env"), patch(
        "salt.utils.verify.check_user", return_value=True
    ) as mock_check_user, patch(
        "salt.utils.user.get_user", return_value="root"
    ):

        salt_call = salt.cli.call.SaltCall()

        # Setup mock config with sudo_user set
        salt_call.config = {
            "verify_env": True,
            "pki_dir": "/etc/salt/pki",
            "cachedir": "/var/cache/salt",
            "extension_modules": "/var/cache/salt/extmods",
            "user": "salt",
            "sudo_user": "salt",  # sudo_user is set
            "permissive_pki_access": False,
        }
        salt_call.options = MagicMock()
        salt_call.options.user = None
        salt_call.options.master = None
        salt_call.options.doc = False
        salt_call.options.grains_run = False
        salt_call.options.local = False
        salt_call.options.file_root = None
        salt_call.options.pillar_root = None
        salt_call.options.states_dir = None

        salt_call.run()

        # check_user SHOULD be called even if sudo_user is set
        # because we no longer implicitly skip check_user based on sudo_user presence
        mock_check_user.assert_called_with("salt")


def test_check_user_called_without_sudo_user():
    with patch("salt.utils.parsers.SaltCallOptionParser.parse_args"), patch(
        "salt.cli.caller.Caller"
    ), patch("salt.utils.verify.verify_env"), patch(
        "salt.utils.verify.check_user", return_value=True
    ) as mock_check_user, patch(
        "salt.utils.user.get_user", return_value="root"
    ):

        salt_call = salt.cli.call.SaltCall()

        # Setup mock config WITHOUT sudo_user
        salt_call.config = {
            "verify_env": True,
            "pki_dir": "/etc/salt/pki",
            "cachedir": "/var/cache/salt",
            "extension_modules": "/var/cache/salt/extmods",
            "user": "salt",
            "sudo_user": None,
            "permissive_pki_access": False,
        }
        salt_call.options = MagicMock()
        salt_call.options.user = None
        salt_call.options.master = None
        salt_call.options.doc = False
        salt_call.options.grains_run = False
        salt_call.options.local = False
        salt_call.options.file_root = None
        salt_call.options.pillar_root = None
        salt_call.options.states_dir = None

        salt_call.run()

        # check_user SHOULD be called
        mock_check_user.assert_called_with("salt")


def test_check_user_skipped_when_already_correct_user():
    with patch("salt.utils.parsers.SaltCallOptionParser.parse_args"), patch(
        "salt.cli.caller.Caller"
    ), patch("salt.utils.verify.verify_env"), patch(
        "salt.utils.verify.check_user"
    ) as mock_check_user, patch(
        "salt.utils.user.get_user", return_value="salt"
    ):

        salt_call = salt.cli.call.SaltCall()

        # Setup mock config where user matches current user
        salt_call.config = {
            "verify_env": True,
            "pki_dir": "/etc/salt/pki",
            "cachedir": "/var/cache/salt",
            "extension_modules": "/var/cache/salt/extmods",
            "user": "salt",
            "sudo_user": None,
            "permissive_pki_access": False,
        }
        salt_call.options = MagicMock()
        salt_call.options.user = None
        salt_call.options.master = None
        salt_call.options.doc = False
        salt_call.options.grains_run = False
        salt_call.options.local = False
        salt_call.options.file_root = None
        salt_call.options.pillar_root = None
        salt_call.options.states_dir = None

        salt_call.run()

        # check_user should NOT be called as we are already the correct user
        mock_check_user.assert_not_called()


def test_check_user_called_with_cli_override():
    with patch("salt.utils.parsers.SaltCallOptionParser.parse_args"), patch(
        "salt.cli.caller.Caller"
    ), patch("salt.utils.verify.verify_env"), patch(
        "salt.utils.verify.check_user", return_value=True
    ) as mock_check_user, patch(
        "salt.utils.user.get_user", return_value="root"
    ):

        salt_call = salt.cli.call.SaltCall()

        # Setup mock config
        salt_call.config = {
            "verify_env": True,
            "pki_dir": "/etc/salt/pki",
            "cachedir": "/var/cache/salt",
            "extension_modules": "/var/cache/salt/extmods",
            "user": "salt",
            "sudo_user": None,
            "permissive_pki_access": False,
        }
        # Override user via options
        salt_call.options = MagicMock()
        salt_call.options.user = "custom_user"
        salt_call.options.master = None
        salt_call.options.doc = False
        salt_call.options.grains_run = False
        salt_call.options.local = False
        salt_call.options.file_root = None
        salt_call.options.pillar_root = None
        salt_call.options.states_dir = None

        salt_call.run()

        # verify config was updated
        assert salt_call.config["user"] == "custom_user"
        # check_user called with override value
        mock_check_user.assert_called_with("custom_user")
