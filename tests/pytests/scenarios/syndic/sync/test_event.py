import time

from saltfactories.utils import random_string


def test_event(event_listener, salt_cli, minion, master):
    event_tag = random_string("salt/test/event/")
    event_data = {"event.fire_master": random_string("syndic test event: ")}
    start_time = time.time()

    ret = salt_cli.run(
        "event.fire_master",
        tag=event_tag,
        data=event_data,
        minion_tgt="syndic",
        _timeout=15,
    )
    assert ret.data is True

    event_pattern = (master.id, event_tag)
    matched_events = event_listener.wait_for_events(
        [event_pattern], after_time=start_time, timeout=30
    )
    assert matched_events.found_all_events
    for event in matched_events:
        assert event.data["id"] == "syndic"
        assert event.data["cmd"] == "_minion_event"
        assert event.data["data"] == event_data
