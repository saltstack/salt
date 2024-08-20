import pathlib

import pytest


@pytest.mark.skip_on_windows
@pytest.mark.skip_if_binaries_missing("ufw")
def test_salt_ufw(salt_master, salt_call_cli, install_salt):
    """
    Test salt.ufw for Debian/Ubuntu salt-master
    """
    if install_salt.distro_id not in ("debian", "ubuntu"):
        pytest.skip("Only tests Debian / Ubuntu packages")

    # check that the salt_master is running
    assert salt_master.is_running()

    ufw_master_path = pathlib.Path("/etc/ufw/applications.d/salt.ufw")
    assert ufw_master_path.exists()
    assert ufw_master_path.is_file()

    ufw_list_cmd = "/usr/sbin/ufw app list"
    ret = salt_call_cli.run("--local", "cmd.run", ufw_list_cmd)
    assert "Available applications" in ret.stdout
    assert "Salt" in ret.stdout
    ufw_upd_cmd = "/usr/sbin/ufw app update Salt"
    ret = salt_call_cli.run("--local", "cmd.run", ufw_upd_cmd)
    assert ret.returncode == 0
    expected_info = """Profile: Salt
Title: salt
Description: fast and powerful configuration management and remote
execution

Ports:
  4505,4506/tcp"""
    ufw_info_cmd = "/usr/sbin/ufw app info Salt"
    ret = salt_call_cli.run("--local", "cmd.run", ufw_info_cmd)
    assert expected_info in ret.data
