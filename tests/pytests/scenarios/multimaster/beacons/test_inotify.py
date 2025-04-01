import logging
import shutil
import time

import pytest

import salt.config
import salt.version

try:
    import pyinotify  # pylint: disable=unused-import

    HAS_PYINOTIFY = True
except ImportError:
    HAS_PYINOTIFY = False


log = logging.getLogger(__name__)

pytestmark = [
    pytest.mark.slow_test,
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
def setup_beacons(mm_master_1_salt_cli, salt_mm_minion_1, inotify_test_path):
    start_time = time.time()
    try:
        # Add a status beacon to use for interval checks
        ret = mm_master_1_salt_cli.run(
            "beacons.add",
            "inotify",
            beacon_data=[{"files": {str(inotify_test_path): {"mask": ["create"]}}}],
            minion_tgt=salt_mm_minion_1.id,
            timeout=60,
        )
        assert ret.returncode == 0
        log.debug("Inotify beacon add returned: %s", ret.data or ret.stdout)
        assert ret.data
        assert ret.data["result"] is True
        ret = mm_master_1_salt_cli.run(
            "beacons.add",
            "status",
            beacon_data=[{"time": ["all"]}],
            minion_tgt=salt_mm_minion_1.id,
        )
        assert ret.returncode == 0
        log.debug("Status beacon add returned: %s", ret.data or ret.stdout)
        assert ret.data
        assert ret.data["result"] is True
        ret = mm_master_1_salt_cli.run(
            "beacons.list", return_yaml=False, minion_tgt=salt_mm_minion_1.id
        )
        assert ret.returncode == 0
        log.debug("Beacons list: %s", ret.data or ret.stdout)
        assert ret.data
        assert "inotify" in ret.data
        assert ret.data["inotify"] == [
            {"files": {str(inotify_test_path): {"mask": ["create"]}}}
        ]
        assert "status" in ret.data
        assert ret.data["status"] == [{"time": ["all"]}]
        yield start_time
    finally:
        # Remove the added beacons
        for beacon in ("inotify", "status"):
            mm_master_1_salt_cli.run(
                "beacons.delete", beacon, minion_tgt=salt_mm_minion_1.id
            )


@pytest.mark.slow_test
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
    expected_tag = f"salt/beacon/{salt_mm_minion_1.id}/status/*"
    expected_patterns = [
        (salt_mm_master_1.id, expected_tag),
        (salt_mm_master_2.id, expected_tag),
    ]
    matched_events = event_listener.wait_for_events(
        expected_patterns,
        after_time=start_time,
        timeout=salt_mm_minion_1.config["loop_interval"] * 2 + 60,
    )
    assert matched_events.found_all_events
    log.debug("Status events received: %s", matched_events.matches)

    # Let's trigger an inotify event
    start_time = time.time()
    file_path = inotify_test_path / "tmpfile"
    file_path.write_text("")
    log.warning(
        "Test file to trigger the inotify event has been written to: %s", file_path
    )
    expected_tag = "salt/beacon/{}/inotify/{}".format(
        salt_mm_minion_1.id, inotify_test_path
    )
    expected_patterns = [
        (salt_mm_master_1.id, expected_tag),
        (salt_mm_master_2.id, expected_tag),
    ]
    matched_events = event_listener.wait_for_events(
        expected_patterns,
        after_time=start_time,
        # Now in successful case this test will get results at most in 3 loop intervals.
        # Waiting for 3 loops intervals + some seconds to the hardware stupidity.
        timeout=salt_mm_minion_1.config["loop_interval"] * 3 + 60,
    )
    assert matched_events.found_all_events
    log.debug("Inotify events received: %s", matched_events.matches)

    expected_data = {
        "path": str(file_path),
        "change": "IN_CREATE",
        "id": salt_mm_minion_1.id,
    }

    assert [(expected_tag, expected_data), (expected_tag, expected_data)] == [
        (event.tag, event.data) for event in matched_events
    ]
