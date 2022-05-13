"""
    tests.pytests.unit.beacons.test_haproxy
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    HAProxy beacon test cases
"""
import pytest
import salt.beacons.haproxy as haproxy
from tests.support.mock import MagicMock, patch


@pytest.fixture
def configure_loader_modules():
    return {haproxy: {"__context__": {}, "__salt__": {}}}


def test_non_list_config():
    config = {}

    ret = haproxy.validate(config)
    assert ret == (False, "Configuration for haproxy beacon must be a list.")


def test_empty_config():
    config = [{}]

    ret = haproxy.validate(config)
    assert ret == (False, "Configuration for haproxy beacon requires backends.")


def test_no_servers():
    config = [{"backends": {"www-backend": {"threshold": 45}}}]

    ret = haproxy.validate(config)
    assert ret == (False, "Backends for haproxy beacon require servers.")


def test_threshold_reached():
    config = [{"backends": {"www-backend": {"threshold": 45, "servers": ["web1"]}}}]

    ret = haproxy.validate(config)
    assert ret == (True, "Valid beacon configuration")

    mock = MagicMock(return_value=46)
    with patch.dict(haproxy.__salt__, {"haproxy.get_sessions": mock}):
        ret = haproxy.beacon(config)
        assert ret == [{"threshold": 45, "scur": 46, "server": "web1"}]


def test_threshold_not_reached():
    config = [{"backends": {"www-backend": {"threshold": 100, "servers": ["web1"]}}}]

    ret = haproxy.validate(config)
    assert ret == (True, "Valid beacon configuration")

    mock = MagicMock(return_value=50)
    with patch.dict(haproxy.__salt__, {"haproxy.get_sessions": mock}):
        ret = haproxy.beacon(config)
        assert ret == []
