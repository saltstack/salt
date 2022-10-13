import pytest

import salt.runners.net as net
from tests.support.mock import MagicMock

pytestmark = [
    pytest.mark.skipif(
        not net.HAS_NAPALM, reason="napalm module required for this test"
    )
]


@pytest.fixture
def configure_loader_modules(tmp_path):
    mock_get = MagicMock(return_value={})
    return {
        net: {
            "__opts__": {
                "optimization_order": [0, 1, 2],
                "renderer": "yaml",
                "renderer_blacklist": [],
                "renderer_whitelist": [],
                "extension_modules": str(tmp_path),
            },
            "__salt__": {"mine.get": mock_get},
        }
    }


def test_interfaces():
    ret = net.interfaces()
    assert ret is None


def test_findarp():
    ret = net.findarp()
    assert ret is None


def test_findmac():
    ret = net.findmac()
    assert ret is None


def test_lldp():
    ret = net.lldp()
    assert ret is None


def test_find():
    ret = net.find("")
    assert {} == ret


def test_multi_find():
    ret = net.multi_find()
    assert ret is None
