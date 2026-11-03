import multiprocessing
import os
import pathlib
import subprocess
import sys
import textwrap

import pytest

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


def test_pip_environment_pypath_isolated():
    """
    salt-pip must not leak an inherited PYTHONPATH into the pip subprocess
    it spawns. PYTHONPATH is always set to just salt's own extras
    directory, regardless of what the parent process's environment already
    had set. See https://github.com/saltstack/salt/issues/70151 -- a
    PYTHONPATH inherited from an unrelated Python installation combined
    with ``--force-reinstall`` could otherwise cause salt-pip to uninstall
    packages belonging to that unrelated environment.
    """
    extras = "/tmp/footest"
    env = {
        "HOME": "/home/dwoz",
        "PYTHONPATH": "/usr/local/lib/python3.10/site-packages",
    }
    pipenv = _pip_environment(env, extras)
    # The original environment mapping is left untouched...
    assert env["PYTHONPATH"] == "/usr/local/lib/python3.10/site-packages"
    # ...but the inherited PYTHONPATH is not carried over to the subprocess.
    assert pipenv["PYTHONPATH"] == "/tmp/footest"


def test_pip_environment_use_pythonpath_opt_in():
    """
    The saltpip_use_pythonpath minion config option restores the old
    prepend-onto-inherited-PYTHONPATH behavior, opt-in only.
    """
    extras = "/tmp/footest"
    env = {
        "HOME": "/home/dwoz",
        "PYTHONPATH": "/usr/local/lib/python3.10/site-packages",
    }
    pipenv = _pip_environment(env, extras, use_pythonpath=True)
    assert (
        pipenv["PYTHONPATH"]
        == f"/tmp/footest{os.pathsep}/usr/local/lib/python3.10/site-packages"
    )


def test_pip_environment_use_pythonpath_opt_in_no_inherited_value():
    """
    saltpip_use_pythonpath with nothing inherited just falls back to the
    isolated (extras-only) behavior -- there's nothing to prepend.
    """
    extras = "/tmp/footest"
    env = {"HOME": "/home/dwoz"}
    pipenv = _pip_environment(env, extras, use_pythonpath=True)
    assert pipenv["PYTHONPATH"] == "/tmp/footest"


@pytest.mark.parametrize(
    "env_var",
    ["PIP_NO_DEPS", "PIP_NO_INDEX", "PIP_DISABLE_PIP_VERSION_CHECK"],
)
def test_pip_environment_network_lockdown_opts_default_off(env_var):
    """
    saltpip_no_deps/saltpip_no_index/saltpip_disable_pip_version_check
    default to False, matching current (unchanged) behavior: the
    corresponding PIP_* env var isn't set at all.
    """
    extras = "/tmp/footest"
    env = {"HOME": "/home/dwoz"}
    pipenv = _pip_environment(env, extras)
    assert env_var not in pipenv


@pytest.mark.parametrize(
    "kwarg,env_var",
    [
        ("no_deps", "PIP_NO_DEPS"),
        ("no_index", "PIP_NO_INDEX"),
        ("disable_version_check", "PIP_DISABLE_PIP_VERSION_CHECK"),
    ],
)
def test_pip_environment_network_lockdown_opts_enabled(kwarg, env_var):
    """
    When enabled, each network-lockdown option sets its corresponding
    PIP_* env var, forcing it regardless of anything already inherited
    from the parent environment.
    """
    extras = "/tmp/footest"
    env = {"HOME": "/home/dwoz", env_var: "0"}
    pipenv = _pip_environment(env, extras, **{kwarg: True})
    assert pipenv[env_var] == "1"


def test_pip_environment_find_links_passthrough_by_default():
    """
    saltpip_allow_find_links defaults to True: an inherited PIP_FIND_LINKS
    passes through unchanged, matching current (unchanged) behavior.
    """
    extras = "/tmp/footest"
    env = {"HOME": "/home/dwoz", "PIP_FIND_LINKS": "https://example.com/links"}
    pipenv = _pip_environment(env, extras)
    assert pipenv["PIP_FIND_LINKS"] == "https://example.com/links"


@pytest.mark.parametrize("no_index", [True, False])
def test_pip_environment_find_links_stripped_when_disallowed(no_index):
    """
    saltpip_allow_find_links=False strips an inherited PIP_FIND_LINKS
    unconditionally -- independent of saltpip_no_index, since
    --find-links remains meaningful (and is pip's own documented
    air-gapped-install pattern) even when the index itself is disabled.
    """
    extras = "/tmp/footest"
    env = {"HOME": "/home/dwoz", "PIP_FIND_LINKS": "https://example.com/links"}
    pipenv = _pip_environment(env, extras, allow_find_links=False, no_index=no_index)
    assert "PIP_FIND_LINKS" not in pipenv


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
# multiprocessing start-method pin (Python 3.14+ on Linux)
#
# PEP 741 changed the default start method from ``fork`` to ``forkserver``,
# which makes Salt daemon startup ~5× slower (every subprocess re-imports
# Salt) and leaks worker processes that hold ports across restarts.
# ``salt.scripts`` pins the start method back to ``fork`` at import time so
# every Salt CLI entry point gets the same behaviour as on 3.13.  The two
# tests below pin that contract.
# ---------------------------------------------------------------------------


@pytest.mark.skip_on_windows(reason="Linux-only multiprocessing default change")
@pytest.mark.skipif(
    sys.version_info < (3, 14),
    reason="Pre-3.14 already defaulted to fork on Linux",
)
def test_salt_scripts_pins_fork_start_method():
    """
    On Linux + Python 3.14+, importing ``salt.scripts`` (which the CLI
    entry-point scripts do before creating any Process) pins the
    multiprocessing start method to ``fork``.
    """
    # ``import salt.scripts`` already happened at module load.
    assert multiprocessing.get_start_method(allow_none=False) == "fork"


@pytest.mark.skip_on_windows(reason="Linux-only multiprocessing default change")
@pytest.mark.skipif(
    sys.version_info < (3, 14),
    reason="Pre-3.14 already defaulted to fork on Linux",
)
def test_salt_scripts_pin_survives_fresh_interpreter():
    """
    Spawn a fresh interpreter, import ``salt.scripts`` first thing, then
    print the multiprocessing start method.  Verifies the pin runs at
    import time (not as a side-effect of some test-only fixture).
    """
    code = textwrap.dedent(
        """
        import multiprocessing
        import salt.scripts
        print(multiprocessing.get_start_method(allow_none=False))
        """
    )
    proc = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        check=True,
        text=True,
        timeout=60,
    )
    assert proc.stdout.strip() == "fork"


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
