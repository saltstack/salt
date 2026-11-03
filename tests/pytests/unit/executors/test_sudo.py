import salt.executors.sudo
from tests.support.mock import MagicMock, patch


def _make_run_all_mock():
    return MagicMock(
        return_value={
            "retcode": 0,
            "stdout": '{"local": {"return": true, "retcode": 0}}',
        }
    )


def _run_execute(opts, fun="test.ping", args=None, kwargs=None):
    """Helper: run sudo.execute with mocked cmd.run_all and return call args."""
    data = {"fun": fun}
    func = MagicMock()
    args = args or []
    kwargs = kwargs or {}

    mock_run_all = _make_run_all_mock()
    context_dict = {}

    if not hasattr(salt.executors.sudo, "__salt__"):
        salt.executors.sudo.__salt__ = {}
    if not hasattr(salt.executors.sudo, "__context__"):
        salt.executors.sudo.__context__ = {}

    with patch.dict(
        salt.executors.sudo.__salt__, {"cmd.run_all": mock_run_all}
    ), patch.dict(salt.executors.sudo.__context__, context_dict):
        salt.executors.sudo.execute(opts, data, func, args, kwargs)
        return mock_run_all.call_args[0][0]


def test_sudo_execute_uses_sudo_by_default():
    """When sudo_cmd is absent, execute() uses 'sudo'."""
    opts = {"sudo_user": "saltdev", "config_dir": "/etc/salt"}
    call_args = _run_execute(opts)
    assert call_args[0] == "sudo"
    assert "-u" in call_args
    assert "saltdev" in call_args
    assert "salt-call" in call_args


def test_sudo_execute_adds_priv_arg():
    """execute() passes --priv <sudo_user> to salt-call."""
    opts = {"sudo_user": "saltdev", "config_dir": "/etc/salt"}
    call_args = _run_execute(opts)

    assert "--priv" in call_args
    salt_call_idx = call_args.index("salt-call")
    priv_idx = call_args.index("--priv")
    assert priv_idx > salt_call_idx
    assert call_args[priv_idx + 1] == "saltdev"


def test_sudo_execute_uses_sudo_cmd_when_set():
    """When sudo_cmd is set, execute() uses it instead of 'sudo'."""
    opts = {"sudo_user": "saltdev", "config_dir": "/etc/salt", "sudo_cmd": "doas"}
    call_args = _run_execute(opts)
    assert call_args[0] == "doas"
    assert "sudo" not in call_args


def test_sudo_execute_uses_sudo_when_sudo_cmd_empty():
    """When sudo_cmd is an empty string (default config value), execute() uses 'sudo'."""
    opts = {"sudo_user": "saltdev", "config_dir": "/etc/salt", "sudo_cmd": ""}
    call_args = _run_execute(opts)
    assert call_args[0] == "sudo"


def _with_opts(opts):
    """Return a context manager that patches __opts__ on the sudo executor."""
    if not hasattr(salt.executors.sudo, "__opts__"):
        salt.executors.sudo.__opts__ = {}
    return patch.dict(salt.executors.sudo.__opts__, opts)


def test_sudo_virtual_loads_with_sudo_present(tmp_path):
    """__virtual__ returns the virtualname when sudo is found and sudo_user is set."""
    fake_sudo = tmp_path / "sudo"
    fake_sudo.touch()
    fake_sudo.chmod(0o755)

    opts = {"sudo_user": "saltdev", "sudo_cmd": ""}
    with _with_opts(opts), patch(
        "salt.utils.path.which",
        side_effect=lambda x: str(fake_sudo) if x == "sudo" else None,
    ):
        result = salt.executors.sudo.__virtual__()
    assert result == "sudo"


def test_sudo_virtual_loads_with_sudo_cmd(tmp_path):
    """__virtual__ returns the virtualname when sudo_cmd binary is found."""
    fake_doas = tmp_path / "doas"
    fake_doas.touch()
    fake_doas.chmod(0o755)

    opts = {"sudo_user": "saltdev", "sudo_cmd": "doas"}
    with _with_opts(opts), patch(
        "salt.utils.path.which",
        side_effect=lambda x: str(fake_doas) if x == "doas" else None,
    ):
        result = salt.executors.sudo.__virtual__()
    assert result == "sudo"


def test_sudo_virtual_false_without_sudo_user(tmp_path):
    """__virtual__ returns False when sudo_user is not configured."""
    fake_sudo = tmp_path / "sudo"
    fake_sudo.touch()
    fake_sudo.chmod(0o755)

    opts = {"sudo_user": "", "sudo_cmd": ""}
    with _with_opts(opts), patch(
        "salt.utils.path.which",
        side_effect=lambda x: str(fake_sudo) if x == "sudo" else None,
    ):
        result = salt.executors.sudo.__virtual__()
    assert result is False


def test_sudo_virtual_false_when_neither_sudo_nor_sudo_cmd_found():
    """__virtual__ returns False when the escalation binary is not on PATH."""
    opts = {"sudo_user": "saltdev", "sudo_cmd": "doas"}
    with _with_opts(opts), patch("salt.utils.path.which", return_value=None):
        result = salt.executors.sudo.__virtual__()
    assert result is False
