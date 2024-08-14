import pytest
from pytestskipmarkers.utils import platform


@pytest.mark.skip_unless_on_linux(reason="Linux test only")
def test_services(install_salt, salt_call_cli):
    """
    Check if Services are enabled/disabled
    """
    services_disabled = []
    services_enabled = []
    if install_salt.distro_id in ("ubuntu", "debian"):
        services_enabled = ["salt-master", "salt-minion", "salt-syndic", "salt-api"]
    elif install_salt.distro_id in (
        "almalinux",
        "rocky",
        "centos",
        "redhat",
        "amzn",
        "fedora",
    ):
        services_disabled = ["salt-master", "salt-minion", "salt-syndic", "salt-api"]
    elif install_salt.distro_id == "photon":
        services_enabled = ["salt-master", "salt-minion", "salt-syndic", "salt-api"]
    elif platform.is_darwin():
        services_enabled = ["salt-minion"]
        services_disabled = []
    else:
        pytest.fail(f"Don't know how to handle os_family={install_salt.distro_id}")

    for service in services_enabled:
        test_cmd = f"systemctl show -p UnitFileState {service}"
        ret = salt_call_cli.run("--local", "cmd.run", test_cmd)
        test_enabled = ret.stdout.strip().split("=")[1].split('"')[0].strip()
        assert ret.returncode == 0
        assert test_enabled == "enabled"

    for service in services_disabled:
        test_cmd = f"systemctl show -p UnitFileState {service}"
        ret = salt_call_cli.run("--local", "cmd.run", test_cmd)
        test_enabled = ret.stdout.strip().split("=")[1].split('"')[0].strip()
        assert ret.returncode == 0
        assert test_enabled == "disabled"
