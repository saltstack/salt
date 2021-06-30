"""
    tests.unit.utils.beacons
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~

    Test the salt beacon utils
"""

import logging

import salt.utils.beacons as beacons

log = logging.getLogger(__name__)


def test_list_to_dict():
    """
    Make sure you can instantiate etc.
    """
    ret = beacons.list_to_dict([])
    assert isinstance(ret, dict)

    config = [{"a": "b"}, {"c": "d"}, {"_e": "f"}]
    ret = beacons.list_to_dict(config)
    assert isinstance(ret, dict)


def test_remove_hidden_options():
    """
    Make sure you can instantiate etc.
    """
    config = [{"a": "b"}, {"c": "d"}, {"_e": "f"}]
    expected = [{"a": "b"}, {"c": "d"}]
    ret = beacons.remove_hidden_options(config, [])
    assert ret == expected

    config = [{"a": "b"}, {"c": "d"}, {"_e": "f"}]
    expected = [{"a": "b"}, {"c": "d"}, {"_e": "f"}]
    ret = beacons.remove_hidden_options(config, ["_e"])
    assert ret == expected
