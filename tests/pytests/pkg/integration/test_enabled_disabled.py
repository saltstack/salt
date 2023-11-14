import pytest
from pytestskipmarkers.utils import platform


@pytest.mark.skip_on_windows(reason="Linux test only")
def test_services(install_salt, salt_cli, salt_minion):
    """
    Check if Services are enabled/disabled
    """
    if install_salt.distro_id in ("ubuntu", "debian"):
        services_enabled = ["salt-master", "salt-minion", "salt-syndic", "salt-api"]
        services_disabled = []
    elif install_salt.distro_id in ("centos", "redhat", "amzn", "fedora"):
        services_enabled = []
        services_disabled = ["salt-master", "salt-minion", "salt-syndic", "salt-api"]
    elif install_salt.distro_id == "photon":
        if float(install_salt.distro_version) < 5:
            services_enabled = []
            services_disabled = [
                "salt-master",
                "salt-minion",
                "salt-syndic",
                "salt-api",
            ]
        else:
            services_enabled = ["salt-master", "salt-minion", "salt-syndic", "salt-api"]
            services_disabled = []
    elif platform.is_darwin():
        services_enabled = ["salt-minion"]
        services_disabled = []
    else:
        pytest.fail(f"Don't know how to handle os_family={install_salt.distro_id}")

    for service in services_enabled:
        ret = salt_cli.run("service.enabled", service, minion_tgt=salt_minion.id)
        assert "true" in ret.stdout

    for service in services_disabled:
        ret = salt_cli.run("service.disabled", service, minion_tgt=salt_minion.id)
        assert "true" in ret.stdout
