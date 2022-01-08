import logging
import os
import shutil
import time

import pytest
import salt.utils.platform

pytestmark = [
    pytest.mark.slow_test,
    pytest.mark.windows_whitelisted,
    pytest.mark.skipif(
        salt.utils.platform.is_freebsd(),
        reason="Processes are not properly killed on FreeBSD",
    ),
]

log = logging.getLogger(__name__)


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


def test_pki(salt_mm_failover_master_1, salt_mm_failover_master_2, caplog):
    """
    Verify https://docs.saltproject.io/en/latest/topics/tutorials/multimaster_pki.html
    """
    # At first we spin up a simple minion in order to capture its logging output.
    config_defaults = {
        "transport": salt_mm_failover_master_1.config["transport"],
    }

    mm_master_1_port = salt_mm_failover_master_1.config["ret_port"]
    mm_master_1_addr = salt_mm_failover_master_1.config["interface"]
    mm_master_2_port = salt_mm_failover_master_2.config["ret_port"]
    mm_master_2_addr = salt_mm_failover_master_2.config["interface"]
    config_overrides = {
        "master": [
            "{}:{}".format(mm_master_1_addr, mm_master_1_port),
            "{}:{}".format(mm_master_2_addr, mm_master_2_port),
        ],
        "publish_port": salt_mm_failover_master_1.config["publish_port"],
        "master_type": "failover",
        "master_alive_interval": 15,
        "master_tries": -1,
        "verify_master_pubkey_sign": True,
    }
    factory = salt_mm_failover_master_1.salt_minion_daemon(
        "mm-failover-pki-minion-1",
        defaults=config_defaults,
        overrides=config_overrides,
        extra_cli_arguments_after_first_start_failure=["--log-level=debug"],
    )
    # Need to grab the public signing key from the master, either will do
    shutil.copyfile(
        os.path.join(salt_mm_failover_master_1.config["pki_dir"], "master_sign.pub"),
        os.path.join(factory.config["pki_dir"], "master_sign.pub"),
    )
    with caplog.at_level(logging.DEBUG):
        with factory.started(start_timeout=120):
            pass

    assert (
        "Successfully verified signature of master public key with verification public key master_sign.pub"
        in caplog.text
    )


def test_return_to_assigned_master(
    event_listener,
    salt_mm_failover_master_1,
    salt_mm_failover_master_2,
    mm_failover_master_1_salt_cli,
    mm_failover_master_2_salt_cli,
    salt_mm_failover_minion_1,
    salt_mm_failover_minion_2,
    run_salt_cmds,
):
    """
    Test that values are being returned to only the master the minion is currently connected to.
    """
    start_time = time.time()

    run_salt_cmds(
        [mm_failover_master_1_salt_cli, mm_failover_master_2_salt_cli],
        [salt_mm_failover_minion_1, salt_mm_failover_minion_2],
    )

    # pylint: disable=unbalanced-tuple-unpacking
    minion_1_ret_events, minion_2_ret_events = _get_all_ret_events_after_time(
        [salt_mm_failover_master_1, salt_mm_failover_master_2],
        [salt_mm_failover_minion_1, salt_mm_failover_minion_2],
        event_listener,
        start_time,
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
    run_salt_cmds,
    request,
):
    """
    Test then when the first master is stopped, connected minions failover to the second master.
    """
    if request.config.getoption("--transport") == "tcp":
        pytest.skip("Failover process under the TPC transport is not working.")

    event_patterns = [
        (
            salt_mm_failover_master_2.id,
            "salt/minion/{}/start".format(salt_mm_failover_minion_1.id),
        )
    ]

    start_time = time.time()
    with salt_mm_failover_master_1.stopped():
        assert salt_mm_failover_master_2.is_running()
        # We need to wait for them to realize that the master is not alive
        # At this point, only the first minion will need to change masters
        events = event_listener.wait_for_events(
            event_patterns,
            timeout=salt_mm_failover_minion_1.config["master_alive_interval"] * 2,
            after_time=start_time,
        )

        assert salt_mm_failover_minion_1.is_running()
        assert not events.missed

        start_time = time.time()
        run_salt_cmds(
            [mm_failover_master_1_salt_cli, mm_failover_master_2_salt_cli],
            [salt_mm_failover_minion_1, salt_mm_failover_minion_2],
        )

        # pylint: disable=unbalanced-tuple-unpacking
        minion_1_ret_events, minion_2_ret_events = _get_all_ret_events_after_time(
            [salt_mm_failover_master_1, salt_mm_failover_master_2],
            [salt_mm_failover_minion_1, salt_mm_failover_minion_2],
            event_listener,
            start_time,
        )

        # Each minion should only return to one master
        assert len(minion_1_ret_events) == 1
        assert len(minion_2_ret_events) == 1


def test_minion_reconnection(
    event_listener,
    salt_mm_failover_master_1,
    salt_mm_failover_master_2,
    salt_mm_failover_minion_1,
    salt_mm_failover_minion_2,
    mm_failover_master_1_salt_cli,
    mm_failover_master_2_salt_cli,
    run_salt_cmds,
):
    """
    Test that mininons reconnect to a live master.

    To work well with salt factories, the minions will reconnect to the master they were connected to in conftest.py.
    """
    start_time = time.time()

    with salt_mm_failover_minion_1.stopped(), salt_mm_failover_minion_2.stopped():
        pass

    event_patterns = [
        (
            salt_mm_failover_master_1.id,
            "salt/minion/{}/start".format(salt_mm_failover_minion_1.id),
        ),
        (
            salt_mm_failover_master_2.id,
            "salt/minion/{}/start".format(salt_mm_failover_minion_2.id),
        ),
    ]
    events = event_listener.wait_for_events(
        event_patterns,
        timeout=salt_mm_failover_minion_1.config["master_alive_interval"] * 2,
        after_time=start_time,
    )
    assert not events.missed

    run_salt_cmds(
        [mm_failover_master_1_salt_cli, mm_failover_master_2_salt_cli],
        [salt_mm_failover_minion_1, salt_mm_failover_minion_2],
    )

    # pylint: disable=unbalanced-tuple-unpacking
    minion_1_ret_events, minion_2_ret_events = _get_all_ret_events_after_time(
        [salt_mm_failover_master_1, salt_mm_failover_master_2],
        [salt_mm_failover_minion_1, salt_mm_failover_minion_2],
        event_listener,
        start_time,
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
):
    """
    Make sure the minions stay alive after all masters have stopped.
    """
    start_time = time.time()
    with salt_mm_failover_master_1.stopped():
        with salt_mm_failover_master_2.stopped():
            # Make sure they had at least one chance to re-auth
            events = event_listener.wait_for_events(
                [
                    (salt_mm_failover_minion_1.id, "__master_disconnected"),
                    (salt_mm_failover_minion_2.id, "__master_disconnected"),
                ],
                timeout=salt_mm_failover_minion_1.config["master_alive_interval"] * 2,
                after_time=start_time,
            )
            assert not events.missed
            assert salt_mm_failover_minion_1.is_running()
            assert salt_mm_failover_minion_2.is_running()

            start_time = time.time()

    event_patterns = [
        (
            salt_mm_failover_master_1.id,
            "salt/minion/{}/start".format(salt_mm_failover_minion_1.id),
        ),
        (
            salt_mm_failover_master_1.id,
            "salt/minion/{}/start".format(salt_mm_failover_minion_2.id),
        ),
        (
            salt_mm_failover_master_2.id,
            "salt/minion/{}/start".format(salt_mm_failover_minion_1.id),
        ),
        (
            salt_mm_failover_master_2.id,
            "salt/minion/{}/start".format(salt_mm_failover_minion_2.id),
        ),
    ]
    events = event_listener.wait_for_events(
        event_patterns,
        timeout=salt_mm_failover_minion_1.config["master_alive_interval"] * 4,
        after_time=start_time,
    )

    assert len(events.matches) >= 2

    expected_tags = {
        "salt/minion/{}/start".format(salt_mm_failover_minion_1.id),
        "salt/minion/{}/start".format(salt_mm_failover_minion_2.id),
    }
    assert {event.tag for event in events} == expected_tags
