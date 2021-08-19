# Python libs

import pytest

# Salt libs
import salt.beacons.salt_proxy as salt_proxy
from tests.support.mock import MagicMock, patch


@pytest.fixture
def configure_loader_modules():
    return {salt_proxy: {"__context__": {}, "__salt__": {}}}


def test_non_list_config():
    config = {}

    ret = salt_proxy.validate(config)

    assert ret == (False, "Configuration for salt_proxy beacon must be a list.")


def test_empty_config():
    config = [{}]

    ret = salt_proxy.validate(config)

    assert ret == (False, "Configuration for salt_proxy beacon requires proxies.")


def test_salt_proxy_running():
    mock = MagicMock(return_value={"result": True})
    with patch.dict(salt_proxy.__salt__, {"salt_proxy.is_running": mock}):
        config = [{"proxies": {"p8000": ""}}]

        ret = salt_proxy.validate(config)
        assert ret == (True, "Valid beacon configuration")

        ret = salt_proxy.beacon(config)
        assert ret == [{"p8000": "Proxy p8000 is already running"}]


def test_salt_proxy_not_running():
    is_running_mock = MagicMock(return_value={"result": False})
    configure_mock = MagicMock(
        return_value={
            "result": True,
            "changes": {
                "new": "Salt Proxy: Started proxy process for p8000",
                "old": [],
            },
        }
    )
    cmd_run_mock = MagicMock(
        return_value={"pid": 1000, "retcode": 0, "stderr": "", "stdout": ""}
    )
    with patch.dict(
        salt_proxy.__salt__, {"salt_proxy.is_running": is_running_mock}
    ), patch.dict(
        salt_proxy.__salt__, {"salt_proxy.configure_proxy": configure_mock}
    ), patch.dict(
        salt_proxy.__salt__, {"cmd.run_all": cmd_run_mock}
    ):
        config = [{"proxies": {"p8000": ""}}]

        ret = salt_proxy.validate(config)
        assert ret == (True, "Valid beacon configuration")

        ret = salt_proxy.beacon(config)
        assert ret == [{"p8000": "Proxy p8000 was started"}]
