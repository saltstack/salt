import logging
import time

import pytest
from pytestshellutils.exceptions import FactoryNotStarted

log = logging.getLogger(__name__)

ECHO_STR = "The FitnessGram Pacer Test is a multistage aerobic capacity test"

pytestmark = [
    pytest.mark.core_test,
]


def test_basic_command_return(
    salt_mm_minion_1,
    salt_mm_minion_2,
    mm_master_1_salt_cli,
    mm_master_2_salt_cli,
    run_salt_cmds,
):
    """
    Make sure minions return to both masters
    """
    returns = run_salt_cmds(
        [mm_master_1_salt_cli, mm_master_2_salt_cli],
        [salt_mm_minion_1, salt_mm_minion_2],
    )

    assert len(returns) == 4
    assert (mm_master_1_salt_cli, salt_mm_minion_1) in returns
    assert (mm_master_2_salt_cli, salt_mm_minion_1) in returns
    assert (mm_master_1_salt_cli, salt_mm_minion_2) in returns
    assert (mm_master_2_salt_cli, salt_mm_minion_2) in returns


def test_stopped_first_master(
    salt_mm_master_1,
    salt_mm_minion_1,
    salt_mm_minion_2,
    mm_master_1_salt_cli,
    mm_master_2_salt_cli,
    run_salt_cmds,
):
    """
    Make sure minions return only to the second master when the first is stopped
    """
    with salt_mm_master_1.stopped():
        returns = run_salt_cmds(
            [mm_master_1_salt_cli, mm_master_2_salt_cli],
            [salt_mm_minion_1, salt_mm_minion_2],
        )

        assert len(returns) == 2
        assert (mm_master_2_salt_cli, salt_mm_minion_1) in returns
        assert (mm_master_2_salt_cli, salt_mm_minion_2) in returns


def test_stopped_second_master(
    salt_mm_master_2,
    salt_mm_minion_1,
    salt_mm_minion_2,
    mm_master_1_salt_cli,
    mm_master_2_salt_cli,
    run_salt_cmds,
):
    """
    Make sure minions return only to the first master when the second is stopped
    """
    with salt_mm_master_2.stopped():
        returns = run_salt_cmds(
            [mm_master_1_salt_cli, mm_master_2_salt_cli],
            [salt_mm_minion_1, salt_mm_minion_2],
        )

        assert len(returns) == 2
        assert (mm_master_1_salt_cli, salt_mm_minion_1) in returns
        assert (mm_master_1_salt_cli, salt_mm_minion_2) in returns


def test_minion_reconnection_attempts(
    event_listener,
    salt_mm_master_1,
    salt_mm_master_2,
    salt_mm_minion_1,
    salt_mm_minion_2,
    mm_master_1_salt_cli,
    mm_master_2_salt_cli,
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
            [(salt_mm_master_1.id, f"salt/minion/{salt_mm_minion_1.id}/start")],
            timeout=60,
            after_time=start_time,
        )

        assert not start_events.missed
        assert len(start_events.matches) == 1

        ensure_connections([mm_master_1_salt_cli], [salt_mm_minion_1, salt_mm_minion_2])

        start_time = time.time()

    start_events = event_listener.wait_for_events(
        [(salt_mm_master_2.id, f"salt/minion/{salt_mm_minion_1.id}/start")],
        timeout=60,
        after_time=start_time,
    )
    assert not start_events.missed
    assert len(start_events.matches) == 1

    ensure_connections(
        [mm_master_1_salt_cli, mm_master_2_salt_cli],
        [salt_mm_minion_1, salt_mm_minion_2],
    )
