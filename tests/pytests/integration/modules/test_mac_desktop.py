"""
Integration tests for the mac_desktop execution module.
"""

import pytest

pytestmark = [
    pytest.mark.slow_test,
    pytest.mark.destructive_test,
    pytest.mark.skip_if_not_root,
    pytest.mark.skip_unless_on_darwin,
]


def test_get_output_volume(salt_call_cli):
    """
    Tests the return of get_output_volume.
    """
    ret = salt_call_cli.run("desktop.get_output_volume")
    assert ret.data is not None


def test_set_output_volume(salt_call_cli):
    """
    Tests the return of set_output_volume.
    """
    ret = salt_call_cli.run("desktop.get_output_volume")
    current_vol = ret.data
    to_set = 10
    if current_vol == str(to_set):
        to_set += 2
    ret = salt_call_cli.run("desktop.set_output_volume", str(to_set))
    new_vol = ret.data
    ret = salt_call_cli.run("desktop.get_output_volume")
    check_vol = ret.data
    assert new_vol == check_vol

    # Set volume back to what it was before
    salt_call_cli.run("desktop.set_output_volume", current_vol)


def test_screensaver(salt_call_cli):
    """
    Tests the return of the screensaver function.
    """
    ret = salt_call_cli.run("desktop.screensaver")
    assert ret.data


def test_lock(salt_call_cli):
    """
    Tests the return of the lock function.
    """
    ret = salt_call_cli.run("desktop.lock")
    assert ret.data


def test_say(salt_call_cli):
    """
    Tests the return of the say function.
    """
    ret = salt_call_cli.run("desktop.say", "hello", "world")
    assert ret.data
