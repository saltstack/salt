"""
salt-ssh testing
"""

import pathlib
import shutil

import pytest

import salt.utils.files
import salt.utils.yaml

pytestmark = [
    pytest.mark.slow_test,
    pytest.mark.skip_on_windows(reason="salt-ssh not available on Windows"),
]


@pytest.fixture(autouse=True)
def thin_dir(salt_ssh_cli):
    try:
        yield
    finally:
        ret = salt_ssh_cli.run("config.get", "thin_dir")
        assert ret.returncode == 0
        thin_dir_path = ret.data
        shutil.rmtree(thin_dir_path, ignore_errors=True)


def test_ping(salt_ssh_cli):
    """
    Test a simple ping
    """
    ret = salt_ssh_cli.run("test.ping")
    assert ret.returncode == 0
    assert ret.data is True


def test_thin_dir(salt_ssh_cli):
    """
    test to make sure thin_dir is created
    and salt-call file is included
    """
    ret = salt_ssh_cli.run("config.get", "thin_dir")
    assert ret.returncode == 0
    thin_dir = pathlib.Path(ret.data)
    assert thin_dir.is_dir()
    assert thin_dir.joinpath("salt-call").exists()
    assert thin_dir.joinpath("running_data").exists()


def test_wipe(salt_ssh_cli):
    """
    Ensure --wipe is respected by the state module wrapper
    issue #61083
    """
    ret = salt_ssh_cli.run("config.get", "thin_dir")
    assert ret.returncode == 0
    thin_dir = pathlib.Path(ret.data)
    assert thin_dir.exists()
    # only few modules (state and cp) will actually respect --wipe
    # (see commit #8a414d53284ec04940540ebd823306ab5119e105)
    salt_ssh_cli.run("--wipe", "state.apply")
    assert not thin_dir.exists()


def test_set_path(salt_ssh_cli, tmp_path, salt_ssh_roster_file):
    """
    test setting the path env variable
    """
    path = "/pathdoesnotexist/"
    roster_file = tmp_path / "roster-set-path"
    with salt.utils.files.fopen(salt_ssh_roster_file) as rfh:
        roster_data = salt.utils.yaml.safe_load(rfh)
        roster_data["localhost"].update(
            {
                "set_path": "$PATH:/usr/local/bin/:{}".format(path),
            }
        )
    with salt.utils.files.fopen(roster_file, "w") as wfh:
        salt.utils.yaml.safe_dump(roster_data, wfh)

    ret = salt_ssh_cli.run(
        "--roster-file={}".format(roster_file), "environ.get", "PATH"
    )
    assert ret.returncode == 0
    assert path in ret.data


def test_tty(salt_ssh_cli, tmp_path, salt_ssh_roster_file):
    """
    test using tty
    """
    roster_file = tmp_path / "roster-tty"
    with salt.utils.files.fopen(salt_ssh_roster_file) as rfh:
        roster_data = salt.utils.yaml.safe_load(rfh)
        roster_data["localhost"].update({"tty": True})
    with salt.utils.files.fopen(roster_file, "w") as wfh:
        salt.utils.yaml.safe_dump(roster_data, wfh)
    ret = salt_ssh_cli.run("--roster-file={}".format(roster_file), "test.ping")
    assert ret.returncode == 0
    assert ret.data is True
