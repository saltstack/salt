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
    log.warning(f"DGM test_salt_ufw install_salt '{install_salt}'")

    if install_salt.distro_id not in ("debian", "ubuntu"):
        pytest.skip("Only tests Debian / Ubuntu packages")

    pkg = [x for x in install_salt.pkgs if "deb" in x and "master" in x]
    if not pkg:
        pytest.skip("Not testing deb packages")
    pkg_master = pkg[0]

    pkg = [x for x in install_salt.pkgs if "deb" in x and "common" in x]
    if not pkg:
        pytest.skip("Not testing deb packages")
    pkg_common = pkg[0]
    log.warning(f"DGM test_salt_ufw pkg_common '{pkg_common}'")

    pkg_mngr = install_salt.pkg_mngr
    log.warning(
        f"DGM test_salt_ufw pkg_mngr '{pkg_mngr}', pkg_common '{pkg_common}', pkg_master '{pkg_master}'"
    )

    install_common_cmd = f"{pkg_mngr} -y install {pkg_common}"
    install_master_cmd = f"{pkg_mngr} -y install {pkg_master}"
    ## ret = salt_call_cli.run("--local", "cmd.run", pkg_mngr, "-y", "install", pkg_to_install)
    ret = salt_call_cli.run("--local", "cmd.run", install_common_cmd)
    log.warning(f"DGM test_salt_ufw salt_common post install '{ret}'")
    assert ret.returncode == 0

    ret = salt_call_cli.run("--local", "cmd.run", install_master_cmd)
    log.warning(f"DGM test_salt_ufw salt_master post install '{ret}'")
    assert ret.returncode == 0

    ufw_master_path = pathlib.Path("/etc/ufw/applications.d/salt-master")
    assert ufw_master_path.exists()

    # cleanup
    remove_cmd = f"{pkg_mngr} -y remove salt-common"
    ret = salt_call_cli.run("--local", "cmd.run", remove_cmd)
    log.warning(f"DGM test_salt_ufw salt_master post remove '{ret}'")
    assert ret.returncode == 0
