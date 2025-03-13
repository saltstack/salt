import time

import pytest


@pytest.fixture
def start():
    return time.time()


def test_minion_start_event(
    start, event_listener, salt_master_1, salt_master_2, salt_minion_1
):
    start_events = event_listener.wait_for_events(
        [
            (salt_master_1.id, f"salt/minion/{salt_minion_1.id}/start"),
            (salt_master_2.id, f"salt/minion/{salt_minion_1.id}/start"),
        ],
        timeout=60,
        after_time=start,
    )
    assert not start_events.missed
    assert len(start_events.matches) == 2
