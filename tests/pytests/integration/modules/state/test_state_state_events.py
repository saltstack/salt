"""
tests.pytests.integration.modules.state.test_state_state_events
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
"""

import logging
import time

import pytest

log = logging.getLogger(__name__)


@pytest.fixture(scope="module")
def configure_state_tree(salt_master, salt_minion):
    top_file = """
    base:
      '{}':
        - state-event
    """.format(
        salt_minion.id
    )

    state_event_sls = """
    show_notification:
        test.show_notification:
            - text: Notification
    """

    with salt_master.state_tree.base.temp_file(
        "top.sls", top_file
    ), salt_master.state_tree.base.temp_file("state-event.sls", state_event_sls):
        yield


@pytest.fixture(scope="module")
def state_event_tag():
    """
    State event tag to match
    """
    return "salt/job/*/prog/{}/0"


def test_highstate_state_events(
    event_listener,
    salt_master,
    salt_minion,
    salt_call_cli,
    configure_state_tree,
    state_event_tag,
):
    """
    Test state.highstate with state_events=True
    """

    start_time = time.time()
    ret = salt_call_cli.run("state.highstate", state_events=True)
    assert ret.returncode == 0
    assert ret.data

    event_pattern = (salt_master.id, state_event_tag.format(salt_minion.id))
    matched_events = event_listener.wait_for_events(
        [event_pattern], after_time=start_time, timeout=30
    )
    assert matched_events.found_all_events


def test_sls_state_events(
    event_listener,
    salt_master,
    salt_minion,
    salt_call_cli,
    configure_state_tree,
    state_event_tag,
):
    """
    Test state.sls with state_events=True
    """

    start_time = time.time()
    ret = salt_call_cli.run("state.sls", "state-event", state_events=True)
    assert ret.returncode == 0
    assert ret.data

    event_pattern = (salt_master.id, state_event_tag.format(salt_minion.id))
    matched_events = event_listener.wait_for_events(
        [event_pattern], after_time=start_time, timeout=30
    )
    assert matched_events.found_all_events


def test_sls_id_state_events(
    event_listener,
    salt_master,
    salt_minion,
    salt_call_cli,
    configure_state_tree,
    state_event_tag,
):
    """
    Test state.sls_id with state_events=True
    """

    start_time = time.time()
    ret = salt_call_cli.run(
        "state.sls_id", "show_notification", "state-event", state_events=True
    )
    assert ret.returncode == 0
    assert ret.data

    event_pattern = (salt_master.id, state_event_tag.format(salt_minion.id))
    matched_events = event_listener.wait_for_events(
        [event_pattern], after_time=start_time, timeout=30
    )
    assert matched_events.found_all_events
