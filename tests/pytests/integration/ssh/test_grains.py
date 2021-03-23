import pytest
import salt.utils.platform

pytestmark = [
    pytest.mark.slow_test,
    pytest.mark.skip_on_windows(reason="salt-ssh not available on Windows"),
]


def test_grains_id(salt_ssh_cli):
    """
    Test salt-ssh grains id work for localhost.
    """
    ret = salt_ssh_cli.run("grains.get", "id")
    assert ret.exitcode == 0
    assert ret.json == "localhost"


def test_grains_items(salt_ssh_cli):
    """
    test grains.items with salt-ssh
    """
    ret = salt_ssh_cli.run("grains.items")
    assert ret.exitcode == 0
    assert ret.json
    assert isinstance(ret.json, dict)
    if salt.utils.platform.is_darwin():
        grain = "Darwin"
    elif salt.utils.platform.is_aix():
        grain = "AIX"
    elif salt.utils.platform.is_freebsd():
        grain = "FreeBSD"
    else:
        grain = "Linux"
    assert ret.json["kernel"] == grain
