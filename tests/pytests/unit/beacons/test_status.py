"""
    tests.pytests.unit.beacons.test_status
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    Status beacon test cases
"""

import pytest
import salt.modules.status as status_module
from salt.beacons import status


@pytest.fixture
def configure_loader_modules():
    return {
        status: {
            "__salt__": pytest.helpers.salt_loader_module_functions(status_module)
        },
        status_module: {"__grains__": {"kernel": "Linux"}, "__salt__": {}},
    }


def test_empty_config():
    config = []

    ret = status.validate(config)
    assert ret == (True, "Valid beacon configuration")

    ret = status.beacon(config)
    expected = sorted(["loadavg", "meminfo", "cpustats", "vmstats", "time"])

    assert sorted(list(ret[0]["data"])) == expected


def test_deprecated_dict_config():
    config = {"time": ["all"]}

    ret = status.validate(config)
    assert ret == (False, "Configuration for status beacon must be a list.")


def test_list_config():
    config = [{"time": ["all"]}]

    ret = status.validate(config)
    assert ret == (True, "Valid beacon configuration")

    ret = status.beacon(config)
    expected = ["time"]

    assert list(ret[0]["data"]) == expected
