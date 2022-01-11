import logging
import time

import pytest
from saltfactories.exceptions import FactoryNotStarted

log = logging.getLogger(__name__)

ECHO_STR = "The FitnessGram Pacer Test is a multistage aerobic capacity test"

pytestmark = [
    pytest.mark.slow_test,
    pytest.mark.windows_whitelisted,
]


def _get_all_ret_events_after_time(masters, minions, event_listener, start_time):
    """
    Get all the ret events that happened after `start_time`
    """
    minion_pattern = "salt/job/*/ret/{}"
    events = []

    for minion in minions:
        tag = minion_pattern.format(minion.id)
        matchers = [(master.id, tag) for master in masters]
        ret_events = event_listener.get_events(matchers, after_time=start_time)
        events.append(
            [
                event
                for event in ret_events
                if event.data["fun"] == "test.ping" and event.data["return"]
            ]
        )

    return tuple(events)


def test_basic_command_return(
    event_listener,
    salt_mm_master_1,
    salt_mm_master_2,
    salt_mm_minion_1,
    salt_mm_minion_2,
    mm_master_1_salt_cli,
    mm_master_2_salt_cli,
    run_salt_cmds,
):
    """
    Make sure minions return to both masters
    """
    start_time = time.time()

    run_salt_cmds(
        [mm_master_1_salt_cli, mm_master_2_salt_cli],
        [salt_mm_minion_1, salt_mm_minion_2],
    )

    # pylint: disable=unbalanced-tuple-unpacking
    minion_1_ret_events, minion_2_ret_events = _get_all_ret_events_after_time(
        [salt_mm_master_1, salt_mm_master_2],
        [salt_mm_minion_1, salt_mm_minion_2],
        event_listener,
        start_time,
    )

    assert len(minion_1_ret_events) == 2
    assert len(minion_2_ret_events) == 2


def test_stopped_first_master(
    event_listener,
    salt_mm_master_1,
    salt_mm_master_2,
    salt_mm_minion_1,
    salt_mm_minion_2,
    mm_master_2_salt_cli,
    run_salt_cmds,
):
    """
    Make sure minions return only to the second master when the first is stopped
    """
    with salt_mm_master_1.stopped():
        start_time = time.time()

        run_salt_cmds([mm_master_2_salt_cli], [salt_mm_minion_1, salt_mm_minion_2])

        # pylint: disable=unbalanced-tuple-unpacking
        minion_1_ret_events, minion_2_ret_events = _get_all_ret_events_after_time(
            [salt_mm_master_1, salt_mm_master_2],
            [salt_mm_minion_1, salt_mm_minion_2],
            event_listener,
            start_time,
        )

        # Each minion should only return to the second master
        assert len(minion_1_ret_events) == 1
        assert len(minion_2_ret_events) == 1
        assert minion_1_ret_events.pop().daemon_id == salt_mm_master_2.id
        assert minion_2_ret_events.pop().daemon_id == salt_mm_master_2.id


def test_stopped_second_master(
    event_listener,
    salt_mm_master_1,
    salt_mm_master_2,
    salt_mm_minion_1,
    salt_mm_minion_2,
    mm_master_1_salt_cli,
    run_salt_cmds,
):
    """
    Make sure minions return only to the first master when the second is stopped
    """
    with salt_mm_master_2.stopped():
        start_time = time.time()

        run_salt_cmds([mm_master_1_salt_cli], [salt_mm_minion_1, salt_mm_minion_2])

        # pylint: disable=unbalanced-tuple-unpacking
        minion_1_ret_events, minion_2_ret_events = _get_all_ret_events_after_time(
            [salt_mm_master_1, salt_mm_master_2],
            [salt_mm_minion_1, salt_mm_minion_2],
            event_listener,
            start_time,
        )

        # Each minion should only return to the first master
        assert len(minion_1_ret_events) == 1
        assert len(minion_2_ret_events) == 1
        assert minion_1_ret_events.pop().daemon_id == salt_mm_master_1.id
        assert minion_2_ret_events.pop().daemon_id == salt_mm_master_1.id


def test_minion_reconnection_attempts(
    event_listener,
    salt_mm_master_1,
    salt_mm_master_2,
    salt_mm_minion_1,
    salt_mm_minion_2,
    mm_master_1_salt_cli,
    mm_master_2_salt_cli,
    run_salt_cmds,
    ensure_connections,
):
    """
    Test that minions stay alive and reauth when masters go down and back up, even after restart
    """
    with salt_mm_master_2.stopped():
        with salt_mm_master_1.stopped():
            # Force the minion to restart
            salt_mm_minion_1.terminate()
            # This should make sure the minion stays alive with no masters
            with pytest.raises(FactoryNotStarted):
                with salt_mm_minion_1.started(start_timeout=30):
                    pass

        assert not salt_mm_minion_1.is_running()

        start_time = time.time()
        salt_mm_minion_1.start()

        assert salt_mm_minion_1.is_running()
        assert salt_mm_minion_2.is_running()

        start_events = event_listener.wait_for_events(
            [(salt_mm_master_1.id, "salt/minion/{}/start".format(salt_mm_minion_1.id))],
            timeout=60,
            after_time=start_time,
        )

        assert not start_events.missed
        assert len(start_events.matches) == 1

        ensure_connections([mm_master_1_salt_cli], [salt_mm_minion_1, salt_mm_minion_2])

        start_time = time.time()
        run_salt_cmds([mm_master_1_salt_cli], [salt_mm_minion_1, salt_mm_minion_2])

        # pylint: disable=unbalanced-tuple-unpacking
        minion_1_ret_events, minion_2_ret_events = _get_all_ret_events_after_time(
            [salt_mm_master_1, salt_mm_master_2],
            [salt_mm_minion_1, salt_mm_minion_2],
            event_listener,
            start_time,
        )

        # Each minion should only return to the first master
        assert len(minion_1_ret_events) == 1
        assert len(minion_2_ret_events) == 1
        assert minion_1_ret_events.pop().daemon_id == salt_mm_master_1.id
        assert minion_2_ret_events.pop().daemon_id == salt_mm_master_1.id
        start_time = time.time()

    start_events = event_listener.wait_for_events(
        [(salt_mm_master_2.id, "salt/minion/{}/start".format(salt_mm_minion_1.id))],
        timeout=60,
        after_time=start_time,
    )
    assert not start_events.missed
    assert len(start_events.matches) == 1

    ensure_connections(
        [mm_master_1_salt_cli, mm_master_2_salt_cli],
        [salt_mm_minion_1, salt_mm_minion_2],
    )

    with salt_mm_master_1.stopped():
        start_time = time.time()
        run_salt_cmds([mm_master_2_salt_cli], [salt_mm_minion_1, salt_mm_minion_2])

        # pylint: disable=unbalanced-tuple-unpacking
        minion_1_ret_events, minion_2_ret_events = _get_all_ret_events_after_time(
            [salt_mm_master_1, salt_mm_master_2],
            [salt_mm_minion_1, salt_mm_minion_2],
            event_listener,
            start_time,
        )

        # Each minion should only return to the second master
        assert len(minion_1_ret_events) == 1
        assert len(minion_2_ret_events) == 1
        assert minion_1_ret_events.pop().daemon_id == salt_mm_master_2.id
        assert minion_2_ret_events.pop().daemon_id == salt_mm_master_2.id

    # This will make sure the minions are working
    ensure_connections(
        [mm_master_1_salt_cli, mm_master_2_salt_cli],
        [salt_mm_minion_1, salt_mm_minion_2],
    )
