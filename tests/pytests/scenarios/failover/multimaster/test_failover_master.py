import logging
import time
from contextlib import contextmanager

import pytest
from salt.utils.files import fopen
from saltfactories.exceptions import FactoryTimeout

pytestmark = [pytest.mark.slow_test]

log = logging.getLogger(__name__)


def _run_echo_for_all_possibilities(cli_list, minion_list):
    """
    Run test.echo from each cli to each minion.

    Returns a list of minions that echoed back.
    """
    returned_minions = []

    for cli in cli_list:
        for minion in minion_list:
            # Attempt to run test.echo from cli to the minion.
            # If it the master has a key of an unconnected minion,  it will error out, so we handle it.
            try:
                ret = cli.run(
                    "test.echo", "salt is cool!", minion_tgt=minion.id, _timeout=5
                )
                if ret and ret.json:
                    assert ret.json == "salt is cool!"
                    assert ret.exitcode == 0
                    returned_minions.append(minion)
            except FactoryTimeout as exc:
                log.debug(
                    "Failed to execute test.echo from %s to %s.",
                    cli.get_display_name(),
                    minion.id,
                )

    return returned_minions


@contextmanager
def _stop_with_grains_swap(
    master_to_stop, master_to_stop_cli, disconnected_minions, alive_master
):
    """
    Context manager to deal with failover quirks.

    Since we are running on the same interface, we have to keep track of the publish port.
    In fact, the previous statement is true if we ran on two separate interfaces, because we are not using default ports.
    To see why, take a look at the master function in the status execution module.  It caused much pain :(
    We are running on the same interface to allow FreeBSD tests to pass, as salt-factories has trouble stopping masters properly otherwise.
    This adjustment should not impact the integrity of the tests.
    """
    for minion in disconnected_minions:
        master_to_stop_cli.run(
            "grains.setval",
            "publish_port",
            alive_master.config["publish_port"],
            minion_tgt=minion.id,
        )
    with master_to_stop.stopped():
        yield


def test_pki(salt_mm_failover_minion_1):
    """
    Verify https://docs.saltproject.io/en/latest/topics/tutorials/multimaster_pki.html

    We should keep this as the first test to minimize the size of the log file.
    """
    with fopen(salt_mm_failover_minion_1.config["log_file"]) as fp:
        while True:
            line = fp.readline()
            if not line:
                # We have reached the end of the file
                assert False
            if (
                "Successfully verified signature of master public key with verification public key master_sign.pub"
                in line
            ):
                break


def test_return_to_assigned_master(
    event_listener,
    salt_mm_failover_master_1,
    salt_mm_failover_master_2,
    mm_failover_master_1_salt_cli,
    mm_failover_master_2_salt_cli,
    salt_mm_failover_minion_1,
    salt_mm_failover_minion_2,
):
    """
    Test that values are being returned to only the master the minion is currently connected to.
    """
    start_time = time.time()

    _run_echo_for_all_possibilities(
        [mm_failover_master_1_salt_cli, mm_failover_master_2_salt_cli],
        [salt_mm_failover_minion_1, salt_mm_failover_minion_2],
    )

    # We are getting the return events associated with each minion
    minion_1_pattern = "salt/job/*/ret/{}".format(salt_mm_failover_minion_1.id)
    minion_2_pattern = "salt/job/*/ret/{}".format(salt_mm_failover_minion_2.id)
    minion_1_ret_events = event_listener.get_events(
        [
            (salt_mm_failover_master_1.id, minion_1_pattern),
            (salt_mm_failover_master_2.id, minion_1_pattern),
        ],
        after_time=start_time,
    )
    minion_2_ret_events = event_listener.get_events(
        [
            (salt_mm_failover_master_1.id, minion_2_pattern),
            (salt_mm_failover_master_2.id, minion_2_pattern),
        ],
        after_time=start_time,
    )

    # Each minion should only return to one master
    assert len(minion_1_ret_events) == 1
    assert len(minion_2_ret_events) == 1


def test_failover_to_second_master(
    event_listener,
    salt_mm_failover_master_1,
    salt_mm_failover_master_2,
    salt_mm_failover_minion_1,
    salt_mm_failover_minion_2,
    mm_failover_master_1_salt_cli,
    mm_failover_master_2_salt_cli,
):
    """
    Test then when the first master is stopped, connected minions failover to the second master.
    """
    # Get all the minions connected to salt_mm_failover_master_1
    master_1_minions = _run_echo_for_all_possibilities(
        [mm_failover_master_1_salt_cli],
        [salt_mm_failover_minion_1, salt_mm_failover_minion_2],
    )
    event_patterns = [
        (minion.id, "salt/minion/{}/start".format(minion.id))
        for minion in master_1_minions
    ]

    # breakpoint()
    with _stop_with_grains_swap(
        salt_mm_failover_master_1,
        mm_failover_master_1_salt_cli,
        master_1_minions,
        salt_mm_failover_master_2,
    ):
        start_time = time.time()
        # We need to wait for them to realize that the master is not alive
        # At this point, only the first minion will need to change masters
        if event_patterns:
            event_listener.wait_for_events(
                event_patterns,
                timeout=salt_mm_failover_minion_1.config["master_alive_interval"] * 2,
                after_time=start_time,
            )

        _run_echo_for_all_possibilities(
            [mm_failover_master_1_salt_cli, mm_failover_master_2_salt_cli],
            [salt_mm_failover_minion_1, salt_mm_failover_minion_2],
        )

        # We are getting the return events associated with each minion
        minion_1_pattern = "salt/job/*/ret/{}".format(salt_mm_failover_minion_1.id)
        minion_2_pattern = "salt/job/*/ret/{}".format(salt_mm_failover_minion_2.id)

        # Make sure nothing returned to the first (stopped) master
        assert not event_listener.get_events(
            [(salt_mm_failover_master_1.id, minion_1_pattern)], after_time=start_time
        )
        assert not event_listener.get_events(
            [(salt_mm_failover_master_1.id, minion_2_pattern)], after_time=start_time
        )

        minion_1_ret_events = event_listener.get_events(
            [(salt_mm_failover_master_2.id, minion_1_pattern)], after_time=start_time
        )
        minion_2_ret_events = event_listener.get_events(
            [(salt_mm_failover_master_2.id, minion_2_pattern)], after_time=start_time
        )

        # Each minion should only return to one master
        assert len(minion_1_ret_events) == 1
        assert len(minion_2_ret_events) == 1


def test_minion_reconnection_against_one_live_master(
    event_listener,
    salt_mm_failover_master_1,
    salt_mm_failover_master_2,
    salt_mm_failover_minion_1,
    salt_mm_failover_minion_2,
    mm_failover_master_1_salt_cli,
    mm_failover_master_2_salt_cli,
):
    """
    Test that mininons reconnect to a live master.

    To work well with salt factories, the minions will reconnect to the master the were connected to in conftest.py.
    We should keep this test directly after `test_failover_to_second_master`, to ensure all minions are initially
    connected to the second master.  A more thorough test.
    """
    start_time = time.time()

    with salt_mm_failover_minion_1.stopped(), salt_mm_failover_minion_2.stopped():
        pass

    event_patterns = [
        (minion.id, "salt/minion/{}/start".format(minion.id))
        for minion in (salt_mm_failover_minion_1, salt_mm_failover_minion_2)
    ]
    event_listener.wait_for_events(
        event_patterns,
        timeout=salt_mm_failover_minion_1.config["master_alive_interval"] * 2,
        after_time=start_time,
    )

    _run_echo_for_all_possibilities(
        [mm_failover_master_1_salt_cli, mm_failover_master_2_salt_cli],
        [salt_mm_failover_minion_1, salt_mm_failover_minion_2],
    )

    # We are getting the return events associated with each minion
    minion_1_pattern = "salt/job/*/ret/{}".format(salt_mm_failover_minion_1.id)
    minion_2_pattern = "salt/job/*/ret/{}".format(salt_mm_failover_minion_2.id)
    minion_1_ret_events = event_listener.get_events(
        [
            (salt_mm_failover_master_1.id, minion_1_pattern),
            (salt_mm_failover_master_2.id, minion_1_pattern),
        ],
        after_time=start_time,
    )
    minion_2_ret_events = event_listener.get_events(
        [
            (salt_mm_failover_master_1.id, minion_2_pattern),
            (salt_mm_failover_master_2.id, minion_2_pattern),
        ],
        after_time=start_time,
    )

    # Each minion should only return to one master
    assert len(minion_1_ret_events) == 1
    assert len(minion_2_ret_events) == 1


def test_minions_alive_with_no_master(
    event_listener,
    salt_mm_failover_master_1,
    salt_mm_failover_master_2,
    salt_mm_failover_minion_1,
    salt_mm_failover_minion_2,
    mm_failover_master_1_salt_cli,
    mm_failover_master_2_salt_cli,
):
    """
    Make sure the minions stay alive after all masters have stopped.
    """
    start_time = time.time()
    with salt_mm_failover_master_1.stopped():
        with salt_mm_failover_master_2.stopped():
            # Make sure they had at least one chance to re-auth to both masters
            event_listener.wait_for_events(
                [
                    (salt_mm_failover_minion_1.id, "__master_disconnected"),
                    (salt_mm_failover_minion_2.id, "__master_disconnected"),
                ],
                timeout=salt_mm_failover_minion_1.config["master_alive_interval"] * 2,
                after_time=time.time(),
            )
            event_listener.wait_for_events(
                [
                    (salt_mm_failover_minion_1.id, "__master_disconnected"),
                    (salt_mm_failover_minion_2.id, "__master_disconnected"),
                ],
                timeout=salt_mm_failover_minion_1.config["master_alive_interval"] * 2,
                after_time=time.time(),
            )

            assert salt_mm_failover_minion_1.is_running()
            assert salt_mm_failover_minion_2.is_running()

    event_patterns = [
        (minion.id, "salt/minion/{}/start".format(minion.id))
        for minion in (salt_mm_failover_minion_1, salt_mm_failover_minion_2)
    ]
    event_listener.wait_for_events(
        event_patterns,
        timeout=salt_mm_failover_minion_1.config["master_alive_interval"] * 2,
        after_time=start_time,
    )

    start_time = time.time()

    _run_echo_for_all_possibilities(
        [mm_failover_master_1_salt_cli, mm_failover_master_2_salt_cli],
        [salt_mm_failover_minion_1, salt_mm_failover_minion_2],
    )

    # We are getting the return events associated with each minion
    minion_1_pattern = "salt/job/*/ret/{}".format(salt_mm_failover_minion_1.id)
    minion_2_pattern = "salt/job/*/ret/{}".format(salt_mm_failover_minion_2.id)
    minion_1_ret_events = event_listener.get_events(
        [
            (salt_mm_failover_master_1.id, minion_1_pattern),
            (salt_mm_failover_master_2.id, minion_1_pattern),
        ],
        after_time=start_time,
    )
    minion_2_ret_events = event_listener.get_events(
        [
            (salt_mm_failover_master_1.id, minion_2_pattern),
            (salt_mm_failover_master_2.id, minion_2_pattern),
        ],
        after_time=start_time,
    )

    # Each minion should only return to one master
    assert len(minion_1_ret_events) == 1
    assert len(minion_2_ret_events) == 1
