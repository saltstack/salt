import time

import pytest


@pytest.fixture(scope="module")
def event_listener(salt_factories):
    return salt_factories.event_listener


def test_minion_hangs_on_master_failure_50814(
    event_listener,
    salt_mm_master_1,
    salt_mm_master_2,
    salt_mm_minion_1,
    mm_master_2_salt_cli,
):
    """
    Check minion handling events for the alive master when another master is dead.
    The case being checked here is described in details in issue #50814.
    """
    # Let's make sure everything works with both masters online
    event_count = 3
    while event_count:
        check_event_start_time = time.time()
        stop_time = check_event_start_time + 30
        event_tag = "myco/foo/bar/{}".format(event_count)
        ret = mm_master_2_salt_cli.run(
            "event.send", event_tag, minion_tgt=salt_mm_minion_1.id
        )
        assert ret.exitcode == 0
        assert ret.json is True
        # Let's make sure we get the event back
        mm_master_1_event_match = mm_master_2_event_match = None
        while True:
            if time.time() > stop_time:
                pytest.fail(
                    "Minion is not responding to the second master after the first "
                    "one has gone. Check #50814 for details."
                )
            if (
                mm_master_1_event_match is not None
                and mm_master_2_event_match is not None
            ):
                # We got the right event back!
                break

            time.sleep(0.5)

            if mm_master_1_event_match is None:
                events = event_listener.get_events(
                    [(salt_mm_master_1.id, event_tag)],
                    after_time=check_event_start_time,
                )
                for event in events:
                    # We got the event back!
                    if event.tag == event_tag:
                        mm_master_1_event_match = True
                        break
            if mm_master_2_event_match is None:
                events = event_listener.get_events(
                    [(salt_mm_master_2.id, event_tag)],
                    after_time=check_event_start_time,
                )
                for event in events:
                    # We got the event back!
                    if event.tag == event_tag:
                        mm_master_2_event_match = True
                        break
        event_count -= 1
        time.sleep(0.5)

    # Now, let's try this one of the masters offline
    with salt_mm_master_1.stopped():
        assert salt_mm_master_1.is_running() is False

        # Sending one event would be okay. It would hang after the second with one of the masters offline
        event_count = 1
        while event_count <= 3:
            check_event_start_time = time.time()
            stop_time = check_event_start_time + 30
            event_tag = "myco/foo/bar/{}".format(event_count)
            ret = mm_master_2_salt_cli.run(
                "event.send", event_tag, minion_tgt=salt_mm_minion_1.id
            )
            assert ret.exitcode == 0
            assert ret.json is True

            # Let's make sure we get the event back
            event_match = None
            while True:
                if time.time() > stop_time:
                    pytest.fail(
                        "Minion is not responding to the second master(events sent: %s) after the first "
                        "has gone offline. Check #50814 for details.",
                        event_count,
                    )
                if event_match is not None:
                    # We got the right event back!
                    break

                time.sleep(0.5)
                events = event_listener.get_events(
                    [(salt_mm_master_2.id, event_tag)],
                    after_time=check_event_start_time,
                )
                for event in events:
                    # We got the event back!
                    if event.tag == event_tag:
                        event_match = True
                        break
            event_count += 1
            time.sleep(0.5)
