import shutil

import pytest

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


def test_ssh_mine_get(salt_ssh_cli):
    """
    test salt-ssh with mine
    """
    ret = salt_ssh_cli.run("mine.get", "localhost", "test.arg")
    assert ret.returncode == 0
    assert ret.data
    assert "localhost" in ret.data
    assert "args" in ret.data["localhost"]
    assert ret.data["localhost"]["args"] == ["itworked"]
