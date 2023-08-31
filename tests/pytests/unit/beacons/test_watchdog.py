import os
import time

import pytest

import salt.utils.files
import salt.utils.platform
from salt.beacons import watchdog

pytestmark = [
    pytest.mark.skipif(
        watchdog.HAS_WATCHDOG is False, reason="watchdog is not available"
    ),
    pytest.mark.skipif(
        salt.utils.platform.is_darwin(),
        reason="Tests were being skipped pre macos under nox. Keep it like that for now.",
    ),
]


def check_events(config):
    total_delay = 1
    delay_per_loop = 20e-3

    for _ in range(int(total_delay / delay_per_loop)):
        events = watchdog.beacon(config)

        if events:
            return events

        time.sleep(delay_per_loop)

    return []


def create(path, content=None):
    with salt.utils.files.fopen(path, "w") as f:
        if content:
            f.write(content)
        os.fsync(f)


@pytest.fixture
def configure_loader_modules():
    return {watchdog: {}}


@pytest.fixture(autouse=True)
def _close_watchdog(configure_loader_modules):
    try:
        yield
    finally:
        watchdog.close({})


def assertValid(config):
    ret = watchdog.validate(config)
    assert ret == (True, "Valid beacon configuration")


def test_empty_config():
    config = [{}]
    ret = watchdog.beacon(config)
    assert ret == []


@pytest.mark.skip_on_freebsd(
    reason="Skip on FreeBSD - does not yet have full inotify/watchdog support",
)
def test_file_create(tmp_path):
    path = str(tmp_path / "tmpfile")

    config = [{"directories": {str(tmp_path): {"mask": ["create"]}}}]
    assertValid(config)
    assert watchdog.beacon(config) == []

    create(path)

    ret = check_events(config)
    assert len(ret) == 1
    assert ret[0]["path"] == path
    assert ret[0]["change"] == "created"


def test_file_modified(tmp_path):
    path = str(tmp_path / "tmpfile")
    # Create triggers a modify event along with the create event in Py3
    # So, let's do this before configuring the beacon
    create(path)

    config = [{"directories": {str(tmp_path): {"mask": ["modify"]}}}]
    assertValid(config)
    assert watchdog.beacon(config) == []

    create(path, "some content")

    ret = check_events(config)

    modified = False
    for event in ret:
        # "modified" requires special handling
        # A modification sometimes triggers 2 modified events depending on
        # the OS and the python version
        # When the "modified" event triggers on modify, it will have the
        # path to the temp file (path), other modified events will contain
        # the path minus "tmpfile" and will not match. That's how we'll
        # distinguish the two
        if event["change"] == "modified":
            if event["path"] == path:
                modified = True

    # Check results of the for loop to validate modified
    assert modified


def test_file_deleted(tmp_path):
    path = str(tmp_path / "tmpfile")
    create(path)

    config = [{"directories": {str(tmp_path): {"mask": ["delete"]}}}]
    assertValid(config)
    assert watchdog.beacon(config) == []

    os.remove(path)

    ret = check_events(config)
    assert len(ret) == 1
    assert ret[0]["path"] == path
    assert ret[0]["change"] == "deleted"


@pytest.mark.skip_on_freebsd(
    reason="Skip on FreeBSD - does not yet have full inotify/watchdog support",
)
def test_file_moved(tmp_path):
    path = str(tmp_path / "tmpfile")
    create(path)

    config = [{"directories": {str(tmp_path): {"mask": ["move"]}}}]
    assertValid(config)
    assert watchdog.beacon(config) == []

    os.rename(path, path + "_moved")

    ret = check_events(config)
    assert len(ret) == 1
    assert ret[0]["path"] == path
    assert ret[0]["change"] == "moved"


@pytest.mark.skip_on_freebsd(
    reason="Skip on FreeBSD - does not yet have full inotify/watchdog support",
)
def test_file_create_in_directory(tmp_path):
    config = [{"directories": {str(tmp_path): {"mask": ["create"]}}}]
    assertValid(config)
    assert watchdog.beacon(config) == []

    path = str(tmp_path / "tmpfile")
    create(path)

    ret = check_events(config)
    assert len(ret) == 1
    assert ret[0]["path"] == path
    assert ret[0]["change"] == "created"


@pytest.mark.skip_on_freebsd(
    reason="Skip on FreeBSD - does not yet have full inotify/watchdog support",
)
@pytest.mark.slow_test
def test_trigger_all_possible_events(tmp_path):
    path = str(tmp_path / "tmpfile")
    moved = path + "_moved"

    config = [{"directories": {str(tmp_path): {}}}]
    assertValid(config)
    assert watchdog.beacon(config) == []

    # create
    create(path)
    # modify
    create(path, "modified content")
    # move
    os.rename(path, moved)
    # delete
    os.remove(moved)

    # Give the events time to load into the queue
    time.sleep(1)

    ret = check_events(config)

    events = {"created": "", "deleted": "", "moved": ""}
    modified = False
    for event in ret:
        if event["change"] == "created":
            assert event["path"] == path
            events.pop("created", "")
        if event["change"] == "moved":
            assert event["path"] == path
            events.pop("moved", "")
        if event["change"] == "deleted":
            assert event["path"] == moved
            events.pop("deleted", "")
        # "modified" requires special handling
        # All events [created, moved, deleted] also trigger a "modified"
        # event on Linux
        # Only the "created" event triggers a modified event on Py3 Windows
        # When the "modified" event triggers on modify, it will have the
        # path to the temp file (path), other modified events will contain
        # the path minus "tmpfile" and will not match. That's how we'll
        # distinguish the two
        if event["change"] == "modified":
            if event["path"] == path:
                modified = True

    # Check results of the for loop to validate modified
    assert modified

    # Make sure all events were checked
    assert events == {}
