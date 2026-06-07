"""
Regression tests for win_task duration handling.

These tests are platform-agnostic on purpose: they exercise pure-Python
control flow inside ``add_trigger`` and don't require the Windows COM
bindings. Kept in their own module so they aren't gated by the
``skip_unless_on_windows`` / ``destructive_test`` markers used by the live
Task Scheduler tests in ``test_win_task.py``.
"""

from types import SimpleNamespace

import salt.modules.win_task as win_task
from tests.support.mock import MagicMock, patch


class _RepetitionRecorder:
    """
    Stand-in for a COM ``IRepetitionPattern``. Records exactly which
    properties the caller assigns, so the regression test can assert that
    ``Duration`` is NOT set when ``repeat_duration="Indefinitely"``.
    """

    def __init__(self):
        object.__setattr__(self, "assigned", {})

    def __setattr__(self, name, value):
        self.assigned[name] = value

    def __getattr__(self, name):
        # Reads (used by reverse_lookup paths) return empty string by
        # default — irrelevant for these tests but keeps Mock-like access
        # safe.
        return ""


class _TriggerRecorder:
    def __init__(self):
        object.__setattr__(self, "Repetition", _RepetitionRecorder())
        object.__setattr__(self, "assigned", {})

    def __setattr__(self, name, value):
        if name in ("Repetition", "assigned"):
            object.__setattr__(self, name, value)
        else:
            self.assigned[name] = value


def _make_task_definition():
    trigger = _TriggerRecorder()
    triggers = SimpleNamespace(Create=MagicMock(return_value=trigger))
    task_definition = SimpleNamespace(Triggers=triggers)
    return task_definition, trigger


def test_indefinitely_does_not_set_duration_property():
    """
    Regression test for #68420.

    When ``add_trigger`` is called with ``repeat_duration="Indefinitely"``
    it must leave ``trigger.Repetition.Duration`` unset. The Windows Task
    Scheduler treats an explicitly-assigned empty Duration as "0 seconds"
    and silently disables repetition; the documented way to get an
    indefinite repetition pattern is to leave the property at its null
    default. The COM API also rejects ``"PT0S"`` outright because
    ``Duration`` must be greater than ``Interval``, so the fix is
    structural — don't touch the property at all for the "Indefinitely"
    case.
    """
    task_definition, trigger = _make_task_definition()

    # Patch the COM context manager so we can call add_trigger on Linux
    # without pywin32.
    with patch.object(win_task.salt.utils.winapi, "Com", MagicMock()):
        win_task.add_trigger(
            name="anything",
            trigger_type="Daily",
            trigger_enabled=True,
            repeat_duration="Indefinitely",
            repeat_interval="30 minutes",
            task_definition=task_definition,
        )

    assert "Duration" not in trigger.Repetition.assigned, (
        "Repetition.Duration must not be assigned when "
        'repeat_duration="Indefinitely" — see #68420'
    )
    # And Interval must be assigned, otherwise we're not exercising the
    # right code path.
    assert trigger.Repetition.assigned.get("Interval") == "PT30M"


def test_finite_repeat_duration_still_sets_property():
    """
    Sanity check that the fix only special-cases "Indefinitely": finite
    values must still be assigned to ``Repetition.Duration``.
    """
    task_definition, trigger = _make_task_definition()

    with patch.object(win_task.salt.utils.winapi, "Com", MagicMock()):
        win_task.add_trigger(
            name="anything",
            trigger_type="Daily",
            trigger_enabled=True,
            repeat_duration="1 hour",
            repeat_interval="30 minutes",
            task_definition=task_definition,
        )

    assert trigger.Repetition.assigned.get("Duration") == "PT1H"
    assert trigger.Repetition.assigned.get("Interval") == "PT30M"
