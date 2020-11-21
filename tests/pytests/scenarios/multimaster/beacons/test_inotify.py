import logging
import shutil
import time

import pytest
import salt.config
import salt.version
from tests.support.helpers import slowTest

try:
    import pyinotify  # pylint: disable=unused-import

    HAS_PYINOTIFY = True
except ImportError:
    HAS_PYINOTIFY = False


log = logging.getLogger(__name__)

pytestmark = [
    pytest.mark.skipif(HAS_PYINOTIFY is False, reason="pyinotify is not available"),
    pytest.mark.skipif(
        salt.utils.platform.is_freebsd(),
        reason="Skip on FreeBSD, IN_CREATE event is not supported",
    ),
]


@pytest.fixture(scope="module")
def inotify_test_path(tmp_path_factory):
    test_path = tmp_path_factory.mktemp("inotify-tests")
    try:
        yield test_path
    finally:
        shutil.rmtree(str(test_path), ignore_errors=True)


@pytest.fixture(scope="module")
def event_listener(salt_factories):
    return salt_factories.event_listener


@pytest.fixture(scope="module")
def setup_beacons(mm_master_1_salt_cli, salt_mm_minion_1, inotify_test_path):
    start_time = time.time()
    try:
        # Add a status beacon to use for interval checks
        ret = mm_master_1_salt_cli.run(
            "beacons.add",
            "inotify",
            beacon_data=[{"files": {str(inotify_test_path): {"mask": ["create"]}}}],
            minion_tgt=salt_mm_minion_1.id,
        )
        assert ret.exitcode == 0
        log.debug("Inotify beacon add returned: %s", ret.json or ret.stdout)
        assert ret.json
        assert ret.json["result"] is True
        ret = mm_master_1_salt_cli.run(
            "beacons.add",
            "status",
            beacon_data=[{"time": ["all"]}],
            minion_tgt=salt_mm_minion_1.id,
        )
        assert ret.exitcode == 0
        log.debug("Status beacon add returned: %s", ret.json or ret.stdout)
        assert ret.json
        assert ret.json["result"] is True
        ret = mm_master_1_salt_cli.run(
            "beacons.list", return_yaml=False, minion_tgt=salt_mm_minion_1.id
        )
        assert ret.exitcode == 0
        log.debug("Beacons list: %s", ret.json or ret.stdout)
        assert ret.json
        assert "inotify" in ret.json
        assert ret.json["inotify"] == [
            {"files": {str(inotify_test_path): {"mask": ["create"]}}}
        ]
        assert "status" in ret.json
        assert ret.json["status"] == [{"time": ["all"]}]
        yield start_time
    finally:
        # Remove the added beacons
        for beacon in ("inotify", "status"):
            mm_master_1_salt_cli.run(
                "beacons.delete", beacon, minion_tgt=salt_mm_minion_1.id
            )


@slowTest
def test_beacons_duplicate_53344(
    event_listener,
    inotify_test_path,
    salt_mm_minion_1,
    salt_mm_master_1,
    salt_mm_master_2,
    setup_beacons,
):
    # We have to wait beacon first execution that would configure the inotify watch.
    # Since beacons will be executed both together, we wait for the status beacon event
    # which means that, the inotify becacon was executed too
    start_time = setup_beacons
    stop_time = start_time + salt_mm_minion_1.config["loop_interval"] * 2 + 60
    mm_master_1_event = mm_master_2_event = None
    expected_tag = "salt/beacon/{}/status/*".format(salt_mm_minion_1.id)
    mm_master_1_event_pattern = (salt_mm_master_1.id, expected_tag)
    mm_master_2_event_pattern = (salt_mm_master_2.id, expected_tag)
    while True:
        if time.time() > stop_time:
            pytest.fail(
                "Failed to receive at least one of the status events. "
                "Master 1 Event: {}; Master 2 Event: {}".format(
                    mm_master_1_event, mm_master_2_event
                )
            )

        if not mm_master_1_event:
            events = event_listener.get_events(
                [mm_master_1_event_pattern], after_time=start_time
            )
            for event in events:
                mm_master_1_event = event
                break
        if not mm_master_2_event:
            events = event_listener.get_events(
                [mm_master_2_event_pattern], after_time=start_time
            )
            for event in events:
                mm_master_2_event = event
                break

        if mm_master_1_event and mm_master_2_event:
            # We got all events back
            break

        time.sleep(0.5)

    log.debug("Status events received: %s, %s", mm_master_1_event, mm_master_2_event)

    # Let's trigger an inotify event
    start_time = time.time()
    file_path = inotify_test_path / "tmpfile"
    file_path.write_text("")
    log.warning(
        "Test file to trigger the inotify event has been written to: %s", file_path
    )
    stop_time = start_time + salt_mm_minion_1.config["loop_interval"] * 3 + 60
    # Now in successful case this test will get results at most in 3 loop intervals.
    # Waiting for 3 loops intervals + some seconds to the hardware stupidity.
    mm_master_1_event = mm_master_2_event = None
    expected_tag = "salt/beacon/{}/inotify/{}".format(
        salt_mm_minion_1.id, inotify_test_path
    )
    mm_master_1_event_pattern = (salt_mm_master_1.id, expected_tag)
    mm_master_2_event_pattern = (salt_mm_master_2.id, expected_tag)
    while True:
        if time.time() > stop_time:
            pytest.fail(
                "Failed to receive at least one of the inotify events. "
                "Master 1 Event: {}; Master 2 Event: {}".format(
                    mm_master_1_event, mm_master_2_event
                )
            )

        if not mm_master_1_event:
            events = event_listener.get_events(
                [mm_master_1_event_pattern], after_time=start_time
            )
            for event in events:
                mm_master_1_event = event
                break
        if not mm_master_2_event:
            events = event_listener.get_events(
                [mm_master_2_event_pattern], after_time=start_time
            )
            for event in events:
                mm_master_2_event = event
                break

        if mm_master_1_event and mm_master_2_event:
            # We got all events back
            break

        time.sleep(0.5)

    log.debug("Inotify events received: %s, %s", mm_master_1_event, mm_master_2_event)

    # We can't determine the timestamp so remove it from results
    for event in (mm_master_1_event, mm_master_2_event):
        del event.data["_stamp"]

    expected_data = {
        "path": str(file_path),
        "change": "IN_CREATE",
        "id": salt_mm_minion_1.id,
    }

    # It's better to compare both at once to see both responses in the error log.
    assert ((expected_tag, expected_data), (expected_tag, expected_data)) == (
        (mm_master_1_event.tag, mm_master_1_event.data),
        (mm_master_2_event.tag, mm_master_2_event.data),
    )
