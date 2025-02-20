"""
salt-ssh testing
"""

import pathlib

import pytest

pytestmark = [
    pytest.mark.slow_test,
    pytest.mark.skip_on_windows(reason="salt-ssh not available on Windows"),
]


def test_relenv_dir(salt_ssh_cli):
    """
    test to make sure thin_dir is created
    and salt-call file is included
    """
    ret = salt_ssh_cli.run("--relenv", "config.get", "thin_dir")
    assert ret.returncode == 0
    thin_dir = pathlib.Path(ret.data)
    assert thin_dir.is_dir()
    assert thin_dir
    assert thin_dir.joinpath("salt-call").exists()


def test_relenv_ping(salt_ssh_cli):
    """
    Test a simple ping
    """
    ret = salt_ssh_cli.run("--relenv", "test.ping")
    assert ret.returncode == 0
    assert ret.data is True
