"""
tests.pytests.integration.modules.test_event
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
"""
import time

import pytest
from saltfactories.utils import random_string

pytestmark = [
    pytest.mark.slow_test,
    pytest.mark.windows_whitelisted,
]


def test_fire_master(event_listener, salt_master, salt_minion, salt_call_cli):
    """
    Test firing an event on the master event bus
    """
    event_tag = random_string("salt/test/event/")
    start_time = time.time()
    ret = salt_call_cli.run(
        "event.fire_master", "event.fire_master: just test it!!!!", event_tag
    )
    assert ret.returncode == 0
    assert ret.data
    assert ret.data is True

    event_pattern = (salt_master.id, event_tag)
    matched_events = event_listener.wait_for_events(
        [event_pattern], after_time=start_time, timeout=30
    )
    assert matched_events.found_all_events
    for event in matched_events:
        assert event.data["id"] == salt_minion.id
        assert event.data["cmd"] == "_minion_event"
        assert "event.fire_master: just test it!!!!" in event.data["data"]


def test_event_fire(event_listener, salt_minion, salt_sub_minion, salt_cli):
    """
    Test firing an even on both test minions local event bus
    """
    event_tag = random_string("salt/test/event/")
    data = {"event.fire": "just test it!!!!"}
    for minion_tgt in (salt_minion.id, salt_sub_minion.id):
        start_time = time.time()
        ret = salt_cli.run(
            "event.fire", data=data, tag=event_tag, minion_tgt=minion_tgt
        )
        assert ret.returncode == 0
        assert ret.data
        assert ret.data is True

        event_pattern = (minion_tgt, event_tag)
        matched_events = event_listener.wait_for_events(
            [event_pattern], after_time=start_time, timeout=30
        )
        assert matched_events.found_all_events
        for event in matched_events:
            assert event.data == data


def test_send(event_listener, salt_master, salt_minion, salt_call_cli):
    """
    Test sending an event to the master event bus
    """
    event_tag = random_string("salt/test/event/")
    data = {"event.fire": "just test it!!!!"}
    start_time = time.time()
    ret = salt_call_cli.run(
        "event.send",
        event_tag,
        data=data,
        with_grains=True,
        with_pillar=True,
        preload={"foo": "bar"},
    )
    assert ret.returncode == 0
    assert ret.data
    assert ret.data is True

    event_pattern = (salt_master.id, event_tag)
    matched_events = event_listener.wait_for_events(
        [event_pattern], after_time=start_time, timeout=30
    )
    assert matched_events.found_all_events
    for event in matched_events:
        assert event.data["id"] == salt_minion.id
        assert event.data["cmd"] == "_minion_event"
        assert "event.fire" in event.data["data"]
        assert event.data["foo"] == "bar"
        assert event.data["data"]["grains"]["test_grain"] == "cheese"
        assert event.data["data"]["pillar"]["ext_spam"] == "eggs"
