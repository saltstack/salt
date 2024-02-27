import time

import pytest

pytestmark = [
    pytest.mark.core_test,
]


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
    while True:
        check_event_start_time = time.time()
        event_tag = f"myco/foo/bar/{event_count}"
        ret = mm_master_2_salt_cli.run(
            "event.send", event_tag, minion_tgt=salt_mm_minion_1.id
        )
        assert ret.returncode == 0
        assert ret.data is True
        # Let's make sure we get the event back
        expected_patterns = [
            (salt_mm_master_1.id, event_tag),
            (salt_mm_master_2.id, event_tag),
        ]
        matched_events = event_listener.wait_for_events(
            expected_patterns, after_time=check_event_start_time, timeout=30
        )
        assert matched_events.found_all_events, (
            "Minion is not responding to the second master after the first one has"
            " gone. Check #50814 for details."
        )
        event_count -= 1
        if event_count <= 0:
            break
        time.sleep(0.5)

    def wait_for_minion(salt_cli, tgt, timeout=30):
        start = time.time()
        while True:
            ret = salt_cli.run(
                "test.ping", "--timeout=5", minion_tgt=tgt, _timeout=timeout
            )
            if ret.returncode == 0 and ret.data is True:
                break
            if time.time() - start > timeout:
                raise TimeoutError("Minion failed to respond top ping after timeout")

    # Wait for the minion to re-connect so this test will not affect any
    # others.
    salt_mm_master_1.after_start(
        wait_for_minion, salt_mm_master_1.salt_cli(), salt_mm_minion_1.id
    )

    # Now, let's try this one of the masters offline
    with salt_mm_master_1.stopped():
        assert salt_mm_master_1.is_running() is False
        # Sending one event would be okay. It would hang after the second with one of the masters offline
        event_count = 1
        while True:
            check_event_start_time = time.time()
            event_tag = f"myco/foo/bar/{event_count}"
            ret = mm_master_2_salt_cli.run(
                "event.send", event_tag, minion_tgt=salt_mm_minion_1.id
            )
            assert ret.returncode == 0
            assert ret.data is True

            # Let's make sure we get the event back
            expected_patterns = [
                (salt_mm_master_2.id, event_tag),
            ]
            matched_events = event_listener.wait_for_events(
                expected_patterns, after_time=check_event_start_time, timeout=30
            )
            assert matched_events.found_all_events, (
                "Minion is not responding to the second master(events sent: {}) after"
                " the first has gone offline. Check #50814 for details.".format(
                    event_count
                )
            )
            event_count += 1
            if event_count > 3:
                break
            time.sleep(0.5)
