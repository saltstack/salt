"""
    :codeauthor: :email:`Anthony Shaw <anthonyshaw@apache.org>`
"""

import pytest

import salt.modules.napalm_route as napalm_route
import tests.support.napalm as napalm_test_support
from tests.support.mock import MagicMock, patch


def mock_net_load(template, *args, **kwargs):
    raise ValueError(f"incorrect template {template}")


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
            "net.load_template": mock_net_load,
        }
    }

    return {napalm_route: module_globals}


def test_show():
    with patch(
        "salt.utils.napalm.get_device",
        MagicMock(return_value=napalm_test_support.MockNapalmDevice()),
    ):
        ret = napalm_route.show("1.2.3.4")
        assert ret["out"] == napalm_test_support.TEST_ROUTE.copy()
