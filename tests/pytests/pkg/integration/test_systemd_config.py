import subprocess

import pytest

pytestmark = [
    pytest.mark.skip_on_windows(reason="Linux test only"),
]


@pytest.mark.usefixtures("salt_minion")
def test_system_config(grains):
    """
    Test system config
    """
    if grains["os_family"] == "RedHat":
        if grains["osfinger"] in (
            "AlmaLinux-8",
            "AlmaLinux-9",
            "CentOS Stream-8",
            "CentOS Linux-8",
            "CentOS Stream-9",
            "Fedora Linux-36",
            "VMware Photon OS-3",
            "VMware Photon OS-4",
            "VMware Photon OS-5",
            "Amazon Linux-2023",
        ):
            expected_retcode = 0
        else:
            expected_retcode = 1
        ret = subprocess.call(
            "systemctl show -p ${config} salt-minion.service", shell=True
        )
        assert ret == expected_retcode

    elif grains["os_family"] == "Debian":
        if grains["osfinger"] == "Debian-9":
            expected_retcode = 1
        else:
            expected_retcode = 0
        ret = subprocess.call(
            "systemctl show -p ${config} salt-minion.service", shell=True
        )
        assert ret == expected_retcode
