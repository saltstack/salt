"""
Tests written specifically for the grains.append function.
"""

import logging
import time

import attr
import pytest

log = logging.getLogger(__name__)

pytestmark = [
    pytest.mark.slow_test,
    pytest.mark.windows_whitelisted,
]


@attr.s(frozen=True, slots=True)
class AppendGrain:
    key = attr.ib(default="append-grains-test-key")
    value = attr.ib(default="my-grain-value")


@pytest.fixture(scope="module")
def append_grain_module(salt_call_cli, wait_for_pillar_refresh_complete):
    grain = AppendGrain()
    try:
        # Start off with an empty list
        start_time = time.time()
        ret = salt_call_cli.run("grains.setval", grain.key, val=[])
        assert ret.exitcode == 0
        assert ret.json
        assert ret.json == {grain.key: []}

        # Let's wait for the pillar refresh, at which stage we know grains are also refreshed
        wait_for_pillar_refresh_complete(start_time)
        yield grain
    finally:
        start_time = time.time()
        ret = salt_call_cli.run("grains.delkey", grain.key, force=True)
        assert ret.exitcode == 0
        assert ret.json

        # Let's wait for the pillar refresh, at which stage we know grains are also refreshed
        wait_for_pillar_refresh_complete(start_time)


@pytest.fixture
def append_grain(append_grain_module, salt_call_cli, wait_for_pillar_refresh_complete):
    try:
        yield append_grain_module
    finally:
        start_time = time.time()
        ret = salt_call_cli.run("grains.setval", append_grain_module.key, val=[])
        assert ret.exitcode == 0
        assert ret.json
        assert ret.json == {append_grain_module.key: []}

        # Let's wait for the pillar refresh, at which stage we know grains are also refreshed
        wait_for_pillar_refresh_complete(start_time)


def test_grains_append(salt_call_cli, append_grain):
    """
    Tests the return of a simple grains.append call.
    """
    ret = salt_call_cli.run("grains.append", append_grain.key, append_grain.value)
    assert ret.exitcode == 0
    assert ret.json
    assert ret.json == {append_grain.key: [append_grain.value]}


def test_grains_append_val_already_present(salt_call_cli, append_grain):
    """
    Tests the return of a grains.append call when the value is already
    present in the grains list.
    """
    msg = "The val {} was already in the list {}".format(
        append_grain.value, append_grain.key
    )

    # First, make sure the test grain is present
    ret = salt_call_cli.run("grains.append", append_grain.key, append_grain.value)
    assert ret.exitcode == 0
    assert ret.json
    assert ret.json == {append_grain.key: [append_grain.value]}

    # Now try to append again
    ret = salt_call_cli.run("grains.append", append_grain.key, append_grain.value)
    assert ret.exitcode == 0
    assert ret.json
    assert ret.json == msg


def test_grains_append_val_is_list(salt_call_cli, append_grain):
    """
    Tests the return of a grains.append call when val is passed in as a list.
    """
    second_grain = append_grain.value + "-2"
    ret = salt_call_cli.run(
        "grains.append", append_grain.key, val=[append_grain.value, second_grain]
    )
    assert ret.exitcode == 0
    assert ret.json
    assert ret.json == {append_grain.key: [append_grain.value, second_grain]}


def test_grains_remove_add(
    salt_call_cli, append_grain, wait_for_pillar_refresh_complete
):
    second_grain = append_grain.value + "-2"
    ret = salt_call_cli.run("grains.get", append_grain.key)
    assert ret.exitcode == 0
    assert ret.json == []

    # The range was previously set to 10. Honestly, I don't know why testing 2 iterations
    # would be any different than 10. Maybe because we're making salt work harder...
    # Anyway, setting at 3 since it sounds more reasonable.
    for _ in range(3):
        start_time = time.time()
        ret = salt_call_cli.run("grains.setval", append_grain.key, val=[])
        assert ret.exitcode == 0
        assert ret.json
        assert ret.json == {append_grain.key: []}
        wait_for_pillar_refresh_complete(start_time)
        ret = salt_call_cli.run("grains.get", append_grain.key)
        assert ret.exitcode == 0
        assert ret.json == []

        start_time = time.time()
        ret = salt_call_cli.run("grains.append", append_grain.key, append_grain.value)
        assert ret.exitcode == 0
        assert ret.json
        assert ret.json == {append_grain.key: [append_grain.value]}
        wait_for_pillar_refresh_complete(start_time)
        ret = salt_call_cli.run("grains.get", append_grain.key)
        assert ret.exitcode == 0
        assert ret.json == [append_grain.value]

        start_time = time.time()
        ret = salt_call_cli.run("grains.setval", append_grain.key, val=[])
        assert ret.exitcode == 0
        assert ret.json
        assert ret.json == {append_grain.key: []}
        wait_for_pillar_refresh_complete(start_time)
        ret = salt_call_cli.run("grains.get", append_grain.key)
        assert ret.exitcode == 0
        assert ret.json == []

        start_time = time.time()
        ret = salt_call_cli.run(
            "grains.append", append_grain.key, val=[append_grain.value, second_grain]
        )
        assert ret.exitcode == 0
        assert ret.json
        assert ret.json == {append_grain.key: [append_grain.value, second_grain]}
        wait_for_pillar_refresh_complete(start_time)
        ret = salt_call_cli.run("grains.get", append_grain.key)
        assert ret.exitcode == 0
        assert ret.json == [append_grain.value, second_grain]
