"""
Integration tests for the mac_desktop execution module.
"""

import pytest

from salt.exceptions import CommandExecutionError

pytestmark = [
    pytest.mark.slow_test,
    pytest.mark.destructive_test,
    pytest.mark.skip_if_not_root,
    pytest.mark.skip_unless_on_darwin,
]


@pytest.fixture(scope="module")
def desktop(modules):
    return modules.desktop


def test_get_output_volume(desktop):
    """
    Tests the return of get_output_volume.
    """
    ret = desktop.get_output_volume()
    assert ret is not None


def test_set_output_volume(desktop):
    """
    Tests the return of set_output_volume.
    """
    current_vol = desktop.get_output_volume()
    if current_vol == "missing value":
        current_vol = 0
    try:
        to_set = 10
        if current_vol == str(to_set):
            to_set += 2
        new_vol = desktop.set_output_volume(str(to_set))
        check_vol = desktop.get_output_volume()
        assert new_vol == check_vol
    finally:
        # Set volume back to what it was before
        desktop.set_output_volume(current_vol)


def test_screensaver(desktop):
    """
    Tests the return of the screensaver function.
    """
    try:
        ret = desktop.screensaver()
    except CommandExecutionError as exc:
        pytest.skip("Skipping. Screensaver unavailable.")
    assert ret


def test_lock(desktop):
    """
    Tests the return of the lock function.
    """
    try:
        ret = desktop.lock()
    except CommandExecutionError as exc:
        pytest.skip("Skipping. Unable to lock screen.")
    assert ret


@pytest.mark.skipif(True, reason="Test is flaky. Is this really needed?")
def test_say(desktop):
    """
    Tests the return of the say function.
    """
    ret = desktop.say("hello", "world")
    assert ret
