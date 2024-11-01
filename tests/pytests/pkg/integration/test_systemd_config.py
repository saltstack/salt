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
            "Rocky Linux-8",
            "Rocky Linux-9",
            "CentOS Stream-8",
            "CentOS Linux-8",
            "CentOS Stream-9",
            "Fedora Linux-40",
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


@pytest.mark.usefixtures("salt_minion")
def test_systemd_selinux_config(grains):
    """
    Test systemd selinux config
    """
    if grains["init"] == "systemd":
        ret = subprocess.run(
            "systemctl show -p SELinuxContext salt-minion.service",
            shell=True,
            check=False,
            capture_output=True,
        )
        assert "system_u:system_r:unconfined_t:s0" in ret.stdout.decode()
