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
        salt_call.options.cachedir = None

        salt_call.run()

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
        salt_call.options.cachedir = None

        salt_call.run()

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
        salt_call.options.cachedir = None

        salt_call.run()

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
        salt_call.options.cachedir = None

        salt_call.run()

        assert salt_call.config["user"] == "custom_user"
        mock_check_user.assert_called_with("custom_user")


def _make_salt_call_for_roots_check(file_root, pillar_root, states_dir, local):
    """
    Build a SaltCall instance wired up to skip everything except the
    --file-root / --pillar-root / --states-dir handling in ``run()``.
    """
    salt_call = salt.cli.call.SaltCall()
    salt_call.config = {
        "verify_env": False,
        "pki_dir": "/etc/salt/pki",
        "cachedir": "/var/cache/salt",
        "extension_modules": "/var/cache/salt/extmods",
        "user": "root",
        "sudo_user": None,
        "permissive_pki_access": False,
    }
    salt_call.options = MagicMock()
    salt_call.options.user = None
    salt_call.options.master = None
    salt_call.options.doc = False
    salt_call.options.grains_run = False
    salt_call.options.local = local
    salt_call.options.file_root = file_root
    salt_call.options.pillar_root = pillar_root
    salt_call.options.states_dir = states_dir
    salt_call.options.cachedir = None
    return salt_call


def test_file_root_without_local_warns(capsys):
    """
    Regression test for #68137: using --file-root without --local should not
    silently do nothing — the user must be told that the remote file client
    will ignore the override.
    """
    with patch("salt.utils.parsers.SaltCallOptionParser.parse_args"), patch(
        "salt.cli.caller.Caller"
    ), patch("salt.utils.verify.verify_env"), patch(
        "salt.utils.verify.check_user", return_value=True
    ), patch(
        "salt.utils.user.get_user", return_value="root"
    ):
        salt_call = _make_salt_call_for_roots_check(
            file_root="/tmp/myroot",
            pillar_root=None,
            states_dir=None,
            local=False,
        )
        salt_call.run()

    captured = capsys.readouterr()
    combined = captured.err + captured.out
    assert "--file-root" in combined
    assert "--local" in combined


def test_pillar_root_without_local_warns(capsys):
    """
    Regression test for #68137: --pillar-root without --local must warn.
    """
    with patch("salt.utils.parsers.SaltCallOptionParser.parse_args"), patch(
        "salt.cli.caller.Caller"
    ), patch("salt.utils.verify.verify_env"), patch(
        "salt.utils.verify.check_user", return_value=True
    ), patch(
        "salt.utils.user.get_user", return_value="root"
    ):
        salt_call = _make_salt_call_for_roots_check(
            file_root=None,
            pillar_root="/tmp/mypillar",
            states_dir=None,
            local=False,
        )
        salt_call.run()

    captured = capsys.readouterr()
    combined = captured.err + captured.out
    assert "--pillar-root" in combined
    assert "--local" in combined


def test_states_dir_without_local_warns(capsys):
    """
    Regression test for #68137: --states-dir without --local must warn.
    """
    with patch("salt.utils.parsers.SaltCallOptionParser.parse_args"), patch(
        "salt.cli.caller.Caller"
    ), patch("salt.utils.verify.verify_env"), patch(
        "salt.utils.verify.check_user", return_value=True
    ), patch(
        "salt.utils.user.get_user", return_value="root"
    ):
        salt_call = _make_salt_call_for_roots_check(
            file_root=None,
            pillar_root=None,
            states_dir="/tmp/mystates",
            local=False,
        )
        salt_call.run()

    captured = capsys.readouterr()
    combined = captured.err + captured.out
    assert "--states-dir" in combined
    assert "--local" in combined


def test_file_root_with_local_does_not_warn(capsys):
    """
    Regression test for #68137: when --local is set, --file-root works as
    intended and no warning should be emitted.
    """
    with patch("salt.utils.parsers.SaltCallOptionParser.parse_args"), patch(
        "salt.cli.caller.Caller"
    ), patch("salt.utils.verify.verify_env"), patch(
        "salt.utils.verify.check_user", return_value=True
    ), patch(
        "salt.utils.user.get_user", return_value="root"
    ):
        salt_call = _make_salt_call_for_roots_check(
            file_root="/tmp/myroot",
            pillar_root="/tmp/mypillar",
            states_dir="/tmp/mystates",
            local=True,
        )
        salt_call.run()

    captured = capsys.readouterr()
    combined = captured.err + captured.out
    assert "--local" not in combined
    assert "ignored" not in combined.lower()


def test_no_root_options_does_not_warn(capsys):
    """
    Regression test for #68137: when none of --file-root, --pillar-root,
    --states-dir are passed, no warning should be emitted regardless of
    --local.
    """
    with patch("salt.utils.parsers.SaltCallOptionParser.parse_args"), patch(
        "salt.cli.caller.Caller"
    ), patch("salt.utils.verify.verify_env"), patch(
        "salt.utils.verify.check_user", return_value=True
    ), patch(
        "salt.utils.user.get_user", return_value="root"
    ):
        salt_call = _make_salt_call_for_roots_check(
            file_root=None,
            pillar_root=None,
            states_dir=None,
            local=False,
        )
        salt_call.run()

    captured = capsys.readouterr()
    combined = captured.err + captured.out
    assert "--file-root" not in combined
    assert "--pillar-root" not in combined
    assert "--states-dir" not in combined
