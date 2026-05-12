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
