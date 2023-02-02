import subprocess

import pytest

pytestmark = [
    pytest.mark.skip_on_windows(reason="Linux test only"),
]


def test_system_config(salt_cli, salt_minion):
    """
    Test system config
    """
    get_family = salt_cli.run("grains.get", "os_family", minion_tgt=salt_minion.id)
    assert get_family.returncode == 0
    get_finger = salt_cli.run("grains.get", "osfinger", minion_tgt=salt_minion.id)
    assert get_finger.returncode == 0

    if get_family.data == "RedHat":
        if get_finger.data in (
            "CentOS Stream-8",
            "CentOS Linux-8",
            "CentOS Stream-9",
            "Fedora Linux-36",
        ):
            ret = subprocess.call(
                "systemctl show -p ${config} salt-minion.service", shell=True
            )
            assert ret == 0
        else:
            ret = subprocess.call(
                "systemctl show -p ${config} salt-minion.service", shell=True
            )
            assert ret == 1

    elif "Debian" in get_family.stdout:
        if "Debian-9" in get_finger.stdout:
            ret = subprocess.call(
                "systemctl show -p ${config} salt-minion.service", shell=True
            )
            assert ret == 1
        else:
            ret = subprocess.call(
                "systemctl show -p ${config} salt-minion.service", shell=True
            )
            assert ret == 0
