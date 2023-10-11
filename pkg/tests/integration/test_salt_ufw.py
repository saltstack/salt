import logging
import os.path
import pathlib
import subprocess

import pytest
from pytestskipmarkers.utils import platform

log = logging.getLogger(__name__)


@pytest.mark.skip_on_windows()
def test_salt_ufw(salt_master, salt_call_cli, install_salt):
    """
    Test salt.ufw for Debian/Ubuntu salt-master
    """
    if install_salt.distro_id not in ("debian", "ubuntu"):
        pytest.skip("Only tests Debian / Ubuntu packages")

    # check that the salt_master is running
    assert salt_master.is_running()

    ## ufw_master_path = pathlib.Path("/etc/ufw/applications.d/salt-master")
    ufw_master_path = pathlib.Path("/etc/ufw/applications.d/salt.ufw")
    assert ufw_master_path.exists()
    assert ufw_master_path.is_file()

    ls_cmd = "ls -alhrt /etc/ufw/applications.d/"
    ret = salt_call_cli.run("--local", "cmd.run", ls_cmd)
    log.warning(f"DGM test_salt_ufw  ls cmd ret '{ret}'")

    cat_cmd = "cat /etc/ufw/applications.d/salt-master"
    ret = salt_call_cli.run("--local", "cmd.run", cat_cmd)
    log.warning(f"DGM test_salt_ufw  cat cmd ret '{ret}'")

    ufw_list_cmd = "/usr/sbin/ufw app list"
    ret = salt_call_cli.run("--local", "cmd.run", ufw_list_cmd)
    log.warning(f"DGM test_salt_ufw  list ret '{ret}'")

    ufw_upd_cmd = "/usr/sbin/ufw app update Salt"
    ret = salt_call_cli.run("--local", "cmd.run", ufw_upd_cmd)
    log.warning(f"DGM test_salt_ufw  update ret '{ret}'")

    ufw_info_cmd = "/usr/sbin/ufw app info Salt"
    ret = salt_call_cli.run("--local", "cmd.run", ufw_info_cmd)
