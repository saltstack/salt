# Python libs

import pytest

# Salt libs
import salt.beacons.service as service_beacon
from tests.support.mock import MagicMock, patch


@pytest.fixture
def configure_loader_modules():
    return {service_beacon: {"__context__": {}, "__salt__": {}}}


def test_non_list_config():
    config = {}

    ret = service_beacon.validate(config)

    assert ret == (False, "Configuration for service beacon must be a list.")


def test_empty_config():
    config = [{}]

    ret = service_beacon.validate(config)

    assert ret == (False, "Configuration for service beacon requires services.")


def test_validate_config_services_none():
    config = [{"services": None}]

    ret = service_beacon.validate(config)

    assert ret == (
        False,
        "Services configuration item for service beacon must be a dictionary.",
    )


def test_validate_config_services_list():
    config = [{"services": [{"sshd": {}}]}]

    ret = service_beacon.validate(config)

    assert ret == (
        False,
        "Services configuration item for service beacon must be a dictionary.",
    )


def test_validate_config_services_valid():
    config = [{"services": {"sshd": {}}}]

    ret = service_beacon.validate(config)

    assert ret == (True, "Valid beacon configuration")


def test_service_running():
    with patch.dict(
        service_beacon.__salt__, {"service.status": MagicMock(return_value=True)}
    ):
        config = [{"services": {"salt-master": {}}}]

        ret = service_beacon.validate(config)

        assert ret == (True, "Valid beacon configuration")

        ret = service_beacon.beacon(config)
        assert ret == [
            {
                "service_name": "salt-master",
                "tag": "salt-master",
                "salt-master": {"running": True},
            }
        ]


def test_service_not_running():
    with patch.dict(
        service_beacon.__salt__, {"service.status": MagicMock(return_value=False)}
    ):
        config = [{"services": {"salt-master": {}}}]

        ret = service_beacon.validate(config)

        assert ret == (True, "Valid beacon configuration")

        ret = service_beacon.beacon(config)
        assert ret == [
            {
                "service_name": "salt-master",
                "tag": "salt-master",
                "salt-master": {"running": False},
            }
        ]
