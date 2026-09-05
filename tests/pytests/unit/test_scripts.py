import pathlib
import sys

import pytest

import salt.defaults.exitcodes
import salt.scripts
from salt.scripts import _pip_args, _pip_environment, _resolve_extras_dir
from tests.support.mock import MagicMock, patch


def test_pip_environment_no_pypath():
    """
    We add PYTHONPATH to environemnt when it doesn't already exist.
    """
    extras = "/tmp/footest"
    env = {"HOME": "/home/dwoz"}
    pipenv = _pip_environment(env, extras)
    assert "PYTHONPATH" not in env
    assert "PYTHONPATH" in pipenv
    assert pipenv["PYTHONPATH"] == "/tmp/footest"


@pytest.mark.skip_on_windows(reason="Specific to *nix systems")
def test_pip_environment_pypath_nix():
    """
    We update PYTHONPATH in environemnt when it's already set.
    """
    extras = "/tmp/footest"
    env = {
        "HOME": "/home/dwoz",
        "PYTHONPATH": "/usr/local/lib/python3.10/site-packages",
    }
    assert "PYTHONPATH" in env
    pipenv = _pip_environment(env, extras)
    assert env["PYTHONPATH"] == "/usr/local/lib/python3.10/site-packages"
    assert "PYTHONPATH" in pipenv
    assert (
        pipenv["PYTHONPATH"] == "/tmp/footest:/usr/local/lib/python3.10/site-packages"
    )


@pytest.mark.skip_unless_on_windows(reason="Specific to win32 systems")
def test_pip_environment_pypath_win():
    """
    We update PYTHONPATH in environemnt when it's already set.
    """
    extras = "/tmp/footest"
    env = {
        "HOME": "/home/dwoz",
        "PYTHONPATH": "/usr/local/lib/python3.10/site-packages",
    }
    assert "PYTHONPATH" in env
    pipenv = _pip_environment(env, extras)
    assert env["PYTHONPATH"] == "/usr/local/lib/python3.10/site-packages"
    assert "PYTHONPATH" in pipenv
    assert (
        pipenv["PYTHONPATH"] == "/tmp/footest;/usr/local/lib/python3.10/site-packages"
    )


def test_pip_environment_disables_version_check():
    """
    Regression test for #70024.

    ``salt-pip`` shells out to ``python -m pip`` under a packager-pinned
    onedir pip; pip's periodic "A new release of pip is available" check
    is pure noise and a proxy-config gotcha (cf. #69910). ``_pip_environment``
    must inject ``PIP_DISABLE_PIP_VERSION_CHECK=1`` into the child's env.
    """
    extras = "/tmp/footest"
    env = {"HOME": "/home/dwoz"}
    pipenv = _pip_environment(env, extras)
    assert "PIP_DISABLE_PIP_VERSION_CHECK" not in env
    assert pipenv["PIP_DISABLE_PIP_VERSION_CHECK"] == "1"


def test_pip_environment_respects_operator_override():
    """
    Regression test for #70024.

    Operators must be able to re-enable pip's periodic version check by
    exporting ``PIP_DISABLE_PIP_VERSION_CHECK=0`` before invoking
    ``salt-pip``. ``_pip_environment`` uses ``setdefault`` so a caller's
    explicit setting wins over the salt-pip default.
    """
    extras = "/tmp/footest"
    env = {"HOME": "/home/dwoz", "PIP_DISABLE_PIP_VERSION_CHECK": "0"}
    pipenv = _pip_environment(env, extras)
    assert pipenv["PIP_DISABLE_PIP_VERSION_CHECK"] == "0"


def test_pip_args_not_installing():
    extras = "/tmp/footest"
    args = ["list"]
    pargs = _pip_args(args, extras)
    assert pargs is not args
    assert args == ["list"]
    assert pargs == ["list"]


def test_pip_args_installing_without_target():
    extras = "/tmp/footest"
    args = ["install"]
    pargs = _pip_args(args, extras)
    assert pargs is not args
    assert args == ["install"]
    assert pargs == ["install", "--target=/tmp/footest"]


def test_pip_args_installing_with_target():
    extras = "/tmp/footest"
    args = ["install", "--target=/tmp/bartest"]
    pargs = _pip_args(args, extras)
    assert pargs is not args
    assert args == ["install", "--target=/tmp/bartest"]
    assert pargs == ["install", "--target=/tmp/bartest"]


# ---------------------------------------------------------------------------
# SALT_EXTRAS_DIR honoring (issue #70198)
#
# When the packaging scriptlets relocate the extras tree outside the
# onedir under SALT_ONEDIR_HARDEN=1, they export SALT_EXTRAS_DIR pointing
# at /var/lib/salt/<daemon>/extras-<py>. ``salt-pip`` and the onedir .pth
# helper both need to honor that so packages installed via ``salt-pip``
# land where the daemon's Python actually imports from.
# ---------------------------------------------------------------------------


def test_resolve_extras_dir_falls_back_to_relenv_extras(monkeypatch):
    """
    Without SALT_EXTRAS_DIR set, the extras dir is the historical
    <relenv_root>/extras-<py-major>.<py-minor> path.
    """
    monkeypatch.delenv("SALT_EXTRAS_DIR", raising=False)
    relenv_root = pathlib.Path("/opt/saltstack/salt")
    resolved = _resolve_extras_dir(relenv_root)
    assert resolved == str(relenv_root / "extras-{}.{}".format(*sys.version_info))


def test_resolve_extras_dir_honors_env_override(monkeypatch):
    """
    When SALT_EXTRAS_DIR is set (packaging hardened layout), the extras
    dir override wins over the relenv-derived path.
    """
    monkeypatch.setenv("SALT_EXTRAS_DIR", "/var/lib/salt/minion/extras-3.11")
    relenv_root = pathlib.Path("/opt/saltstack/salt")
    resolved = _resolve_extras_dir(relenv_root)
    assert resolved == "/var/lib/salt/minion/extras-3.11"


def test_resolve_extras_dir_empty_env_falls_back(monkeypatch):
    """
    Empty-string SALT_EXTRAS_DIR is treated as unset (avoid targeting
    "/", which would happen if the packaging layer wrote an empty
    variable).
    """
    monkeypatch.setenv("SALT_EXTRAS_DIR", "")
    relenv_root = pathlib.Path("/opt/saltstack/salt")
    resolved = _resolve_extras_dir(relenv_root)
    assert resolved == str(relenv_root / "extras-{}.{}".format(*sys.version_info))


@pytest.mark.skip_on_windows(
    reason="The keepalive supervisor only exists on non-Windows minions"
)
def test_salt_minion_supervisor_drops_privileges(monkeypatch):
    """
    Regression test for #68115.

    ``salt_minion()`` forks a ``MinionKeepAlive`` child process that
    eventually drops privileges to the configured ``user`` inside
    ``Minion._real_start``. The parent supervisor process, however, used
    to retain its original (root) uid forever, leaving an unprivileged
    minion with a privileged parent visible in the process table. The
    parent must drop privileges itself once the keepalive child has been
    spawned.
    """
    monkeypatch.setattr(sys, "argv", ["salt-minion"])

    fake_process = MagicMock()
    fake_process.pid = 4321
    fake_process.exitcode = 0

    fake_multiprocessing = MagicMock()
    fake_multiprocessing.Process.return_value = fake_process

    fake_opts = {"user": "saltuser"}

    with patch("salt.utils.platform.is_windows", return_value=False), patch(
        "salt.utils.debug.enable_sigusr1_handler"
    ), patch("salt.utils.process.notify_systemd"), patch(
        "salt.config.minion_config", return_value=fake_opts
    ), patch(
        "salt.utils.user.get_user", return_value="root"
    ), patch(
        "salt.utils.verify.check_user", return_value=True
    ) as check_user, patch.dict(
        sys.modules, {"multiprocessing": fake_multiprocessing}
    ):
        with pytest.raises(SystemExit):
            salt.scripts.salt_minion()

    fake_multiprocessing.Process.assert_called_once()
    fake_process.start.assert_called_once()
    # The supervisor parent must drop privileges after spawning the child.
    check_user.assert_called_once_with("saltuser")


@pytest.mark.skip_on_windows(
    reason="The keepalive supervisor only exists on non-Windows minions"
)
def test_salt_minion_supervisor_skips_drop_when_already_user(monkeypatch):
    """
    If the supervisor is already running as the configured user (or as a
    non-root user without ``user`` set), no privilege drop is attempted.
    """
    monkeypatch.setattr(sys, "argv", ["salt-minion"])

    fake_process = MagicMock()
    fake_process.pid = 4321
    fake_process.exitcode = 0

    fake_multiprocessing = MagicMock()
    fake_multiprocessing.Process.return_value = fake_process

    fake_opts = {"user": "saltuser"}

    with patch("salt.utils.platform.is_windows", return_value=False), patch(
        "salt.utils.debug.enable_sigusr1_handler"
    ), patch("salt.utils.process.notify_systemd"), patch(
        "salt.config.minion_config", return_value=fake_opts
    ), patch(
        "salt.utils.user.get_user", return_value="saltuser"
    ), patch(
        "salt.utils.verify.check_user", return_value=True
    ) as check_user, patch.dict(
        sys.modules, {"multiprocessing": fake_multiprocessing}
    ):
        with pytest.raises(SystemExit):
            salt.scripts.salt_minion()

    check_user.assert_not_called()


@pytest.mark.skip_on_windows(
    reason="The keepalive supervisor only exists on non-Windows proxies"
)
def test_salt_proxy_supervisor_drops_privileges(monkeypatch):
    """
    Regression test for #68115. The ``salt-proxy`` supervisor has the
    same keepalive shape as ``salt-minion`` and must likewise drop
    privileges after forking the child.
    """
    monkeypatch.setattr(sys, "argv", ["salt-proxy"])

    fake_process = MagicMock()
    fake_process.pid = 4321
    fake_process.exitcode = 0

    fake_queue = MagicMock()
    fake_queue.get.return_value = 0

    fake_multiprocessing = MagicMock()
    fake_multiprocessing.Process.return_value = fake_process
    fake_multiprocessing.Queue.return_value = fake_queue

    fake_opts = {"user": "saltuser"}

    with patch("salt.utils.platform.is_windows", return_value=False), patch(
        "salt.config.proxy_config", return_value=fake_opts
    ), patch("salt.utils.user.get_user", return_value="root"), patch(
        "salt.utils.verify.check_user", return_value=True
    ) as check_user, patch.dict(
        sys.modules, {"multiprocessing": fake_multiprocessing}
    ):
        with pytest.raises(SystemExit):
            salt.scripts.salt_proxy()

    fake_multiprocessing.Process.assert_called_once()
    fake_process.start.assert_called_once()
    check_user.assert_called_once_with("saltuser")
