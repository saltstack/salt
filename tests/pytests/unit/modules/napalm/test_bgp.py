"""
    :codeauthor: :email:`Anthony Shaw <anthonyshaw@apache.org>`
"""


import pytest

import salt.modules.napalm_bgp as napalm_bgp
import tests.support.napalm as napalm_test_support
from tests.support.mock import MagicMock, patch


@pytest.fixture
def configure_loader_modules():
    module_globals = {
        "__salt__": {
            "config.get": MagicMock(
                return_value={"test": {"driver": "test", "key": "2orgk34kgk34g"}}
            ),
            "file.file_exists": napalm_test_support.true,
            "file.join": napalm_test_support.join,
            "file.get_managed": napalm_test_support.get_managed_file,
            "random.hash": napalm_test_support.random_hash,
        },
    }

    return {napalm_bgp: module_globals}


def test_config():
    with patch(
        "salt.utils.napalm.get_device",
        MagicMock(return_value=napalm_test_support.MockNapalmDevice()),
    ):
        ret = napalm_bgp.config("test_group")
        assert ret["out"] == napalm_test_support.TEST_BGP_CONFIG.copy()


def test_neighbors():
    with patch(
        "salt.utils.napalm.get_device",
        MagicMock(return_value=napalm_test_support.MockNapalmDevice()),
    ):
        ret = napalm_bgp.neighbors("test_address")
        assert ret["out"] == napalm_test_support.TEST_BGP_NEIGHBORS.copy()
