# Python libs

import logging

import pytest

# Salt libs
import salt.beacons.network_settings as network_settings
from tests.support.mock import MagicMock, patch

try:
    from pyroute2 import IPDB

    HAS_PYROUTE2 = True
except ImportError:
    HAS_PYROUTE2 = False


log = logging.getLogger(__name__)


class MockIPClass:
    def __init__(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs

    def by_name(self):
        return {}


@pytest.fixture
def configure_loader_modules():
    return {network_settings: {"__context__": {}, "__salt__": {}}}


def test_non_list_config():
    config = {}

    ret = network_settings.validate(config)

    assert ret == (False, "Configuration for network_settings beacon must be a list.")


def test_empty_config():
    config = [{}]

    ret = network_settings.validate(config)

    assert ret == (True, "Valid beacon configuration")


def test_interface():
    config = [{"interfaces": {"enp14s0u1u2": {"promiscuity": None}}}]
    LAST_STATS = network_settings._copy_interfaces_info(
        {"enp14s0u1u2": {"family": "0", "promiscuity": "0", "group": "0"}}
    )

    NEW_STATS = network_settings._copy_interfaces_info(
        {"enp14s0u1u2": {"family": "0", "promiscuity": "1", "group": "0"}}
    )

    ret = network_settings.validate(config)
    assert ret == (True, "Valid beacon configuration")

    with patch.object(network_settings, "LAST_STATS", {}), patch.object(
        network_settings, "IP", MockIPClass
    ), patch(
        "salt.beacons.network_settings._copy_interfaces_info",
        MagicMock(side_effect=[LAST_STATS, NEW_STATS]),
    ):
        ret = network_settings.beacon(config)
        assert ret == []

        ret = network_settings.beacon(config)
        _expected = [
            {
                "interface": "enp14s0u1u2",
                "tag": "enp14s0u1u2",
                "change": {"promiscuity": "1"},
            }
        ]
        assert ret == _expected


def test_interface_no_change():
    config = [{"interfaces": {"enp14s0u1u2": {"promiscuity": None}}}]
    LAST_STATS = network_settings._copy_interfaces_info(
        {"enp14s0u1u2": {"family": "0", "promiscuity": "0", "group": "0"}}
    )

    NEW_STATS = network_settings._copy_interfaces_info(
        {"enp14s0u1u2": {"family": "0", "promiscuity": "0", "group": "0"}}
    )

    ret = network_settings.validate(config)
    assert ret == (True, "Valid beacon configuration")

    with patch.object(network_settings, "LAST_STATS", {}), patch.object(
        network_settings, "IP", MockIPClass
    ), patch(
        "salt.beacons.network_settings._copy_interfaces_info",
        MagicMock(side_effect=[LAST_STATS, NEW_STATS]),
    ):
        ret = network_settings.beacon(config)
        assert ret == []

        ret = network_settings.beacon(config)
        assert ret == []


def test_wildcard_interface():
    config = [{"interfaces": {"en*": {"promiscuity": None}}}]
    LAST_STATS = network_settings._copy_interfaces_info(
        {"enp14s0u1u2": {"family": "0", "promiscuity": "0", "group": "0"}}
    )

    NEW_STATS = network_settings._copy_interfaces_info(
        {"enp14s0u1u2": {"family": "0", "promiscuity": "1", "group": "0"}}
    )

    ret = network_settings.validate(config)
    assert ret == (True, "Valid beacon configuration")

    with patch.object(network_settings, "LAST_STATS", {}), patch.object(
        network_settings, "IP", MockIPClass
    ), patch(
        "salt.beacons.network_settings._copy_interfaces_info",
        MagicMock(side_effect=[LAST_STATS, NEW_STATS]),
    ):
        ret = network_settings.beacon(config)
        assert ret == []

        ret = network_settings.beacon(config)
        _expected = [
            {
                "interface": "enp14s0u1u2",
                "tag": "enp14s0u1u2",
                "change": {"promiscuity": "1"},
            }
        ]
        assert ret == _expected


@pytest.mark.skipif(HAS_PYROUTE2 is False, reason="no pyroute2 installed, skipping")
def test_interface_dict_fields():
    with IPDB() as ipdb:
        for attr in network_settings.ATTRS:
            # ipdb.interfaces is a dict-like object, that
            # contains interface definitions. Interfaces can
            # be referenced both with indices and names.
            #
            # ipdb.interfaces[1] is an interface with index 1,
            # that is the loopback interface.
            assert attr in ipdb.interfaces[1]
