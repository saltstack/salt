"""
Tests for the win_task module's ``duration`` lookup table.

These tests are platform-agnostic on purpose: the ``duration`` dictionary is
defined at module import time and does not require the Windows COM bindings
that the rest of ``win_task`` needs to load. Placing them in a separate
module from ``test_win_task.py`` keeps them out of the ``skip_unless_on_windows``
/ ``destructive_test`` markers that gate the live Task Scheduler tests.
"""

import salt.modules.win_task as win_task


def test_indefinitely_maps_to_pt0s():
    """
    Regression test for #68420.

    The Windows Task Scheduler ``RepetitionPattern.Duration`` property is an
    ISO 8601 duration string. The documented value for "repeat indefinitely"
    is ``PT0S``; an empty string is interpreted as "no duration set" and
    silently causes the task to not repeat at all when paired with a non-zero
    ``Interval``. The ``duration`` lookup table must therefore map the
    human-readable key ``"Indefinitely"`` to ``"PT0S"``, not ``""``.
    """
    assert win_task.duration["Indefinitely"] == "PT0S"
