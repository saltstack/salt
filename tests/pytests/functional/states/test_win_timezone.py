"""
Functional tests for the timezone state on Windows.

Verifies that ``timezone.system`` succeeds on Windows even when ``utc=True``
(the default), which previously produced a false-positive failure because
Windows hardware clock is always localtime and cannot be changed.
"""

import pytest

pytestmark = [
    pytest.mark.windows_whitelisted,
    pytest.mark.skip_unless_on_windows,
    pytest.mark.slow_test,
    pytest.mark.destructive_test,
]


@pytest.fixture(scope="module")
def timezone_state(states):
    return states.timezone


@pytest.fixture(scope="module")
def timezone_mod(modules):
    return modules.timezone


@pytest.fixture
def _reset_zone(timezone_mod):
    original = timezone_mod.get_zone()
    try:
        yield
    finally:
        timezone_mod.set_zone(original)


@pytest.mark.usefixtures("_reset_zone")
def test_system_utc_true(timezone_state):
    """
    timezone.system with utc=True (the default) must succeed on Windows.

    Previously the state returned result=False with "Failed to set UTC to True"
    because win_timezone.set_hwclock always returns False. The fix skips the
    hwclock block entirely on Windows.
    """
    ret = timezone_state.system("America/New_York", utc=True)
    assert ret.result is True, ret.comment


@pytest.mark.usefixtures("_reset_zone")
def test_system_utc_false(timezone_state):
    """
    timezone.system with utc=False must also succeed on Windows.
    """
    ret = timezone_state.system("America/New_York", utc=False)
    assert ret.result is True, ret.comment


@pytest.mark.usefixtures("_reset_zone")
def test_system_already_set(timezone_state, timezone_mod):
    """
    Calling timezone.system a second time when the timezone is already correct
    must return result=True (idempotent).
    """
    timezone_mod.set_zone("America/Denver")
    ret = timezone_state.system("America/Denver", utc=True)
    assert ret.result is True, ret.comment
    assert ret.changes == {}
