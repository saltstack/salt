import io

import pytest

import salt.proxy.junos as junos
from tests.support.mock import ANY, patch

try:
    import jxmlease  # pylint: disable=unused-import
    from jnpr.junos.device import Device  # pylint: disable=unused-import
    from jnpr.junos.exception import ConnectError

    HAS_JUNOS = True
except ImportError:
    HAS_JUNOS = False


pytestmark = [
    pytest.mark.skipif(
        not HAS_JUNOS, reason="The junos-eznc and jxmlease modules are required"
    ),
]


@pytest.fixture
def opts():
    return {
        "proxy": {
            "username": "xxxx",
            "password]": "xxx",
            "host": "junos",
            "port": "960",
        }
    }


@pytest.fixture
def configure_loader_modules():
    return {junos: {"__pillar__": {}}}


def test_init(opts):
    with patch("ncclient.manager.connect") as mock_connect:
        junos.init(opts)
        assert junos.thisproxy.get("initialized")
        mock_connect.assert_called_with(
            allow_agent=True,
            device_params={"name": "junos", "local": False, "use_filter": False},
            host="junos",
            hostkey_verify=False,
            key_filename=None,
            password=None,
            port="960",
            sock_fd=None,
            ssh_config=ANY,
            username="xxxx",
        )


def test_init_err(opts):
    with patch("ncclient.manager.connect") as mock_connect:
        mock_connect.side_effect = ConnectError
        junos.init(opts)
        assert not junos.thisproxy.get("initialized")


def test_alive(opts):
    with patch("ncclient.manager.connect") as mock_connect:
        junos.init(opts)
        junos.thisproxy["conn"]._conn._session._buffer = io.BytesIO()
        assert junos.alive(opts)
        assert junos.thisproxy.get("initialized")
