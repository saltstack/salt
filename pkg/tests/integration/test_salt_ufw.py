import logging
import os.path
import pathlib
import subprocess

import pytest
from pytestskipmarkers.utils import platform

log = logging.getLogger(__name__)


@pytest.mark.skip_on_windows()
def test_salt_ufw(salt_master, install_salt):
    """
    Test salt.ufw for Debian/Ubuntu salt-master
    """
    log.warning(f"DGM test_salt_ufw install_salt '{install_salt}'")

    if install_salt.distro_id not in ("debian", "ubuntu"):
        pytest.skip("Only tests Debian / Ubuntu packages")

    pkg = [x for x in install_salt.pkgs if "deb" in x]
    if not pkg:
        pytest.skip("Not testing deb packages")
    pkg = pkg[0].split("/")[-1]
    if "rc" not in pkg:
        pytest.skip("Not testing an RC package")

    ufw_master_path = Path("/etc/ufw/applications.d/salt-master")
    assert ufw_master_path.is_file()
