import subprocess

import pytest
from pytestskipmarkers.utils import platform

pytestmark = [
    pytest.mark.skip_on_windows,
]


@pytest.fixture
def salt_systemd_setup(
    salt_call_cli,
    install_salt,
):
    """
    Fixture to set systemd for salt packages to enabled and active
    Note: assumes Salt packages already installed
    """
    install_salt.install()

    # ensure known state, enabled and active
    test_list = ["salt-api", "salt-minion", "salt-master"]
    for test_item in test_list:
        test_cmd = f"systemctl enable {test_item}"
        ret = salt_call_cli.run("--local", "cmd.run", test_cmd)
        assert ret.returncode == 0

        test_cmd = f"systemctl restart {test_item}"
        ret = salt_call_cli.run("--local", "cmd.run", test_cmd)
        assert ret.returncode == 0


@pytest.fixture
def pillar_name(salt_master):
    name = "info"
    top_file_contents = """
    base:
      '*':
        - test
    """
    test_file_contents = f"""
    {name}: test
    """
    with salt_master.pillar_tree.base.temp_file(
        "top.sls", top_file_contents
    ), salt_master.pillar_tree.base.temp_file("test.sls", test_file_contents):
        if not platform.is_windows() and not platform.is_darwin():
            subprocess.run(
                [
                    "chown",
                    "-R",
                    "salt:salt",
                    str(salt_master.pillar_tree.base.write_path),
                ],
                check=False,
            )
        yield name


def test_salt_pillar(salt_systemd_setup, salt_cli, salt_minion, pillar_name):
    """
    Test pillar.items
    """
    # setup systemd to enabled and active for Salt packages
    # pylint: disable=pointless-statement
    salt_systemd_setup

    ret = salt_cli.run("pillar.items", minion_tgt=salt_minion.id)
    assert ret.returncode == 0
    assert pillar_name in ret.data
