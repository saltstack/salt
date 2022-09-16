import attr
import pytest

import salt.defaults.events


@attr.s(kw_only=True, frozen=True, slots=True)
class PillarRefreshComplete:
    event_listener = attr.ib()
    minion_id = attr.ib()

    def __call__(self, start_time):
        expected_tag = salt.defaults.events.MINION_PILLAR_REFRESH_COMPLETE
        event_pattern = (self.minion_id, expected_tag)
        matched_events = self.event_listener.wait_for_events(
            [event_pattern], after_time=start_time, timeout=120
        )
        assert matched_events.found_all_events


@pytest.fixture(scope="module")
def wait_for_pillar_refresh_complete(event_listener, salt_minion):
    return PillarRefreshComplete(
        event_listener=event_listener, minion_id=salt_minion.id
    )
