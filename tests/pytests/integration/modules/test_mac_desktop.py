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
    assert ret is not None


def test_set_output_volume(salt_call_cli):
    """
    Tests the return of set_output_volume.
    """
    current_vol = salt_call_cli.run("desktop.get_output_volume")
    to_set = 10
    if current_vol == str(to_set):
        to_set += 2
    new_vol = salt_call_cli.run("desktop.set_output_volume", str(to_set))
    check_vol = salt_call_cli.run("desktop.get_output_volume")
    assert new_vol == check_vol

    # Set volume back to what it was before
    salt_call_cli.run("desktop.set_output_volume", [current_vol])


def test_screensaver(salt_call_cli):
    """
    Tests the return of the screensaver function.
    """
    assert salt_call_cli.run("desktop.screensaver")


def test_lock(salt_call_cli):
    """
    Tests the return of the lock function.
    """
    assert salt_call_cli.run("desktop.lock")


def test_say(salt_call_cli):
    """
    Tests the return of the say function.
    """
    assert salt_call_cli.run("desktop.say", "hello", "world")
