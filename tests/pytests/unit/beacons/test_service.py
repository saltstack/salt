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

        with patch.dict(service_beacon.LAST_STATUS, {}):
            ret = service_beacon.beacon(config)
            assert ret == [
                {
                    "service_name": "salt-master",
                    "tag": "salt-master",
                    "salt-master": {"running": True},
                }
            ]

        # When onchangeonly is True and emitatstartup is False ,
        # we should not see a return when the beacon is run.
        config = [
            {
                "services": {
                    "salt-master": {"emitatstartup": False, "onchangeonly": True}
                }
            }
        ]

        ret = service_beacon.validate(config)

        assert ret == (True, "Valid beacon configuration")

        # The return is empty because the beacon did not run
        # but the LAST_STATUS should contain the last status
        # for the service.
        with patch.dict(service_beacon.LAST_STATUS, {}):
            ret = service_beacon.beacon(config)
            assert "salt-master" in service_beacon.LAST_STATUS
            assert ret == []

        # When onchangeonly is True and emitatstartup is
        # the default value True, we should see a return
        # when the beacon is run.
        config = [{"services": {"salt-master": {"onchangeonly": True}}}]

        ret = service_beacon.validate(config)

        assert ret == (True, "Valid beacon configuration")

        with patch.dict(service_beacon.LAST_STATUS, {}):
            ret = service_beacon.beacon(config)
            assert ret == [
                {
                    "service_name": "salt-master",
                    "tag": "salt-master",
                    "salt-master": {"running": True},
                }
            ]

        # LAST_STATUS has service name and status has not changed
        config = [{"services": {"salt-master": {"onchangeonly": True}}}]

        ret = service_beacon.validate(config)

        assert ret == (True, "Valid beacon configuration")

        mock_ret_dict = {}
        mock_ret_dict["salt-master"] = {"running": True}

        with patch.dict(service_beacon.LAST_STATUS, mock_ret_dict):
            ret = service_beacon.beacon(config)
            assert ret == []

        # LAST_STATUS has service name and status has changed
        config = [{"services": {"salt-master": {"onchangeonly": True}}}]

        ret = service_beacon.validate(config)

        assert ret == (True, "Valid beacon configuration")

        mock_ret_dict = {}
        mock_ret_dict["salt-master"] = {"running": False}

        with patch.dict(service_beacon.LAST_STATUS, mock_ret_dict):
            ret = service_beacon.beacon(config)
            assert ret == [
                {
                    "service_name": "salt-master",
                    "tag": "salt-master",
                    "salt-master": {"running": True},
                }
            ]

        # When onchangeonly is True and emitatstartup is True,
        # we should see a return when the beacon is run.
        config = [
            {"services": {"salt-master": {"emitatstartup": True, "onchangeonly": True}}}
        ]

        ret = service_beacon.validate(config)

        assert ret == (True, "Valid beacon configuration")

        with patch.dict(service_beacon.LAST_STATUS, {}):
            ret = service_beacon.beacon(config)
            assert ret == [
                {
                    "salt-master": {"running": True},
                    "service_name": "salt-master",
                    "tag": "salt-master",
                }
            ]

            ret = service_beacon.beacon(config)
            assert ret == []


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
