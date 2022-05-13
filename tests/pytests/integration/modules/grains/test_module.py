"""
Test the grains module
"""


import logging
import time

import pytest

log = logging.getLogger(__name__)

pytestmark = [
    pytest.mark.slow_test,
    pytest.mark.windows_whitelisted,
]


@pytest.fixture(scope="module")
def minion_test_grain(salt_minion):
    return salt_minion.config["grains"]["test_grain"]


def test_items(salt_call_cli, minion_test_grain):
    """
    grains.items
    """
    ret = salt_call_cli.run("grains.items")
    assert ret.exitcode == 0
    assert ret.json
    assert isinstance(ret.json, dict)
    assert ret.json["test_grain"] == minion_test_grain


def test_item(salt_call_cli, minion_test_grain):
    """
    grains.item
    """
    ret = salt_call_cli.run("grains.item", "test_grain")
    assert ret.exitcode == 0
    assert ret.json
    assert isinstance(ret.json, dict)
    assert ret.json["test_grain"] == minion_test_grain


def test_ls(salt_call_cli, grains):
    """
    grains.ls
    """
    check_for = (
        "cpu_flags",
        "cpu_model",
        "cpuarch",
        "domain",
        "fqdn",
        "fqdns",
        "gid",
        "groupname",
        "host",
        "kernel",
        "kernelrelease",
        "kernelversion",
        "localhost",
        "mem_total",
        "num_cpus",
        "os",
        "os_family",
        "path",
        "pid",
        "ps",
        "pythonpath",
        "pythonversion",
        "saltpath",
        "saltversion",
        "uid",
        "username",
        "virtual",
    )
    ret = salt_call_cli.run("grains.ls")
    assert ret.exitcode == 0
    assert ret.json
    for grain in check_for:
        if grains["os"] == "Windows" and grain in (
            "cpu_flags",
            "gid",
            "groupname",
            "uid",
        ):
            continue
        assert grain in ret.json


def test_set_val(salt_call_cli, wait_for_pillar_refresh_complete):
    """
    test grains.set_val
    """
    start_time = time.time()
    ret = salt_call_cli.run("grains.setval", "setgrain", "grainval")
    assert ret.exitcode == 0
    assert ret.json
    assert ret.json == {"setgrain": "grainval"}

    # Let's wait for the pillar refresh, at which stage we know grains are also refreshed
    wait_for_pillar_refresh_complete(start_time)

    ret = salt_call_cli.run("grains.item", "setgrain")
    assert ret.exitcode == 0
    assert ret.json == {"setgrain": "grainval"}


def test_get(salt_call_cli):
    """
    test grains.get
    """
    ret = salt_call_cli.run("grains.get", "level1:level2")
    assert ret.exitcode == 0
    assert ret.json
    assert ret.json == "foo"


@pytest.mark.parametrize(
    "grain", ("os", "os_family", "osmajorrelease", "osrelease", "osfullname", "id")
)
def test_get_core_grains(salt_call_cli, grains, grain):
    """
    test to ensure some core grains are returned
    """
    ret = salt_call_cli.run("grains.get", grain)
    assert ret.exitcode == 0
    log.debug("Value of '%s' grain: '%s'", grain, ret.json)
    if grains["os"] in ("Arch", "Windows") and grain in ["osmajorrelease"]:
        assert ret.json == ""
    else:
        assert ret.json


@pytest.mark.parametrize("grain", ("num_cpus", "mem_total", "num_gpus", "uid"))
def test_get_grains_int(salt_call_cli, grains, grain):
    """
    test to ensure int grains
    are returned as integers
    """
    ret = salt_call_cli.run("grains.get", grain)
    assert ret.exitcode == 0
    log.debug("Value of '%s' grain: %r", grain, ret.json)
    if grains["os"] == "Windows" and grain in ["uid"]:
        assert ret.json == ""
    else:
        assert isinstance(ret.json, int), "grain: {} is not an int or empty".format(
            grain
        )
