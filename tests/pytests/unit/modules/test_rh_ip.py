import pytest

import salt.modules.rh_ip as rh_ip
from tests.support.mock import MagicMock, patch


@pytest.fixture
def configure_loader_modules():
    return {rh_ip: {"__grains__": {"os": "CentOS"}}}


def test_virtual_claims_ip_on_legacy_box():
    # network-scripts present (ifup/ifdown on PATH) -> rh_ip still owns "ip".
    with patch.dict(rh_ip.__grains__, {"os_family": "RedHat", "os": "CentOS"}):
        with patch.object(rh_ip, "_nm_managed", MagicMock(return_value=False)):
            assert rh_ip.__virtual__() == "ip"


def test_virtual_defers_to_nm_ip_on_networkmanager():
    # NetworkManager-managed, no ifup/ifdown -> defer so nm_ip claims "ip".
    with patch.dict(rh_ip.__grains__, {"os_family": "RedHat", "os": "CentOS"}):
        with patch.object(rh_ip, "_nm_managed", MagicMock(return_value=True)):
            ret = rh_ip.__virtual__()
    assert ret[0] is False
    assert "nm_ip" in ret[1]


def test_virtual_amazon1_still_declines():
    grains = {"os_family": "RedHat", "os": "Amazon", "osmajorrelease": 1}
    with patch.dict(rh_ip.__grains__, grains):
        with patch("salt.utils.path.which", MagicMock(return_value="/usr/sbin/ifup")):
            ret = rh_ip.__virtual__()
    assert ret[0] is False
