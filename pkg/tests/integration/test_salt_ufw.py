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

    ufw_master_path = pathlib.Path("/etc/ufw/applications.d/salt-master")
    assert ufw_master_path.exists()
