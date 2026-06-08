import multiprocessing
import subprocess
import sys
import textwrap

import pytest

from salt.scripts import _pip_args, _pip_environment


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
