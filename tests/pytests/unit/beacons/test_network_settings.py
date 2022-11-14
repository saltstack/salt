# Python libs

import logging

import pytest

# Salt libs
import salt.beacons.network_settings as network_settings
from tests.support.mock import MagicMock, patch

try:
    # ipdb_interfaces_view requires pyroute2 >= 0.7.1
    from pyroute2 import NDB
    from pyroute2.ndb.compat import ipdb_interfaces_view

    HAS_NDB = True
except ImportError:
    HAS_NDB = False

try:
    # IPDB support may be dropped in future pyroute2 releases
    from pyroute2 import IPDB

    HAS_IPDB = True
except ImportError:
    HAS_IPDB = False


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


@pytest.mark.skipif(HAS_IPDB is False, reason="pyroute2.IPDB not available, skipping")
def test_interface_dict_fields_old():
    with IPDB() as ipdb:
        for attr in network_settings.ATTRS:
            # ipdb.interfaces is a dict-like object, that
            # contains interface definitions. Interfaces can
            # be referenced both with indices and names.
            #
            # ipdb.interfaces[1] is an interface with index 1,
            # that is the loopback interface.
            assert attr in ipdb.interfaces[1]


@pytest.mark.skipif(
    HAS_NDB is False, reason="pyroute2.ndb.compat not yet available, skipping"
)
def test_interface_dict_fields_new():
    with NDB() as ndb:
        # ndb provides dict-like objects for all the RTNL entities
        # upon requests, like:
        #
        #   ndb.interfaces["lo"]
        #   ndb.interfaces[{"target": "netns01", "ifname": "lo"}]
        #   ndb.addresses["127.0.0.1/8"]
        #
        # but for our case is important that NDB provides listings of
        # RTNL entities as sets of named tuples:
        #
        #   for record in ndb.interfaces:
        #       print(record.index, record.ifname)
        #
        # pyroute2.ndb.compat.ipdb_interfaces_view() translates
        # this view into a dict tree that resembles IPDB layout.
        #
        # beacon might use this translation to read the NDB info and at
        # the same time not to saturate memory with multiple objects.
        view = ipdb_interfaces_view(ndb)
        for attr in network_settings.ATTRS:
            assert attr in view["lo"]
