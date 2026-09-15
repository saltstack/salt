"""
Integration tests for the scheduler two-loader model.

Sister to :mod:`tests.pytests.functional.utils.test_scheduler_whitelist_dunder`
which exercises the scheduler internals with real loaders but no
salt-master.  This tier boots a full salt-master + salt-minion pair
and verifies scheduler behavior over the wire under a strict
``whitelist_modules``.
"""

import pytest

from tests.conftest import FIPS_TESTRUN


@pytest.fixture
def whitelisted_scheduler_minion(salt_master):
    """
    Minion with a narrow ``whitelist_modules`` that excludes ``config``
    and ``timezone`` -- the two execution modules the scheduler reads
    internally in ``__singleton_init__`` and ``option``.  With the
    fix, the minion boots + the scheduler works normally.  Pre-fix,
    ``Schedule.__singleton_init__`` still runs (the KeyError is caught
    by the ``try/except`` that defaults ``time_offset`` to ``"0000"``),
    but ``option()`` silently loses pillar-merged semantics.
    """
    minion = salt_master.salt_minion_daemon(
        "test-scheduler-whitelist-dunder-minion",
        overrides={
            "whitelist_modules": [
                "test",
                "grains",
                "saltutil",
                "state",
                "schedule",
                "beacons",
            ],
            "mine_enabled": True,
            "mine_interval": 60,
            "fips_mode": FIPS_TESTRUN,
            "encryption_algorithm": "OAEP-SHA224" if FIPS_TESTRUN else "OAEP-SHA1",
            "signing_algorithm": (
                "PKCS1v15-SHA224" if FIPS_TESTRUN else "PKCS1v15-SHA1"
            ),
        },
    )
    minion.after_terminate(
        pytest.helpers.remove_stale_minion_key, salt_master, minion.id
    )
    with minion.started():
        yield minion


def test_schedule_list_succeeds_under_narrow_whitelist(
    salt_cli, whitelisted_scheduler_minion
):
    """
    ``schedule.list`` fires a ``manage_schedule`` event that the
    scheduler event loop processes via ``Schedule.eval`` /
    ``handle_func``.  Under a strict whitelist that omits ``config``,
    the pre-fix ``Schedule.option()`` KeyError'd on ``config.merge``
    at every scheduler tick, degrading persistent-schedule reads and
    the operator-visible ``schedule.list`` output.

    Post-fix, ``option()`` routes through the inner unfiltered loader,
    so ``schedule.list`` returns cleanly without errors.
    """
    ret = salt_cli.run("schedule.list", minion_tgt=whitelisted_scheduler_minion.id)
    assert ret.returncode == 0, (ret.stdout, ret.stderr)
    text = str(ret.data or ret.stdout or "")
    # Pre-fix KeyError would surface as a traceback in stderr / stdout;
    # post-fix schedule.list returns YAML (possibly ``schedule: {}``
    # when nothing is scheduled yet, but no traceback).
    assert "Traceback" not in text, (
        f"schedule.list emitted a traceback -- Schedule.option / "
        f"config.merge routing may have regressed: {text!r}"
    )
    assert "KeyError" not in text, (
        f"schedule.list surfaced a KeyError to the operator -- "
        f"Schedule.option / config.merge routing may have regressed: "
        f"{text!r}"
    )


def test_saltutil_running_succeeds_under_narrow_whitelist(
    salt_cli, whitelisted_scheduler_minion
):
    """
    ``saltutil.running`` reads the minion's active-job cache, which is
    exercised on every scheduler tick.  If ``Schedule.handle_func``
    KeyError'd on a Salt-internal ``__``-prefixed scheduled job (e.g.
    ``__mine_interval``), those failures would surface as tracebacks
    in the minion log.  This test verifies the CLI call itself
    succeeds cleanly, which is the operator-visible symptom of a
    well-functioning scheduler dispatch path.
    """
    ret = salt_cli.run("saltutil.running", minion_tgt=whitelisted_scheduler_minion.id)
    assert ret.returncode == 0, (ret.stdout, ret.stderr)
    text = str(ret.data or ret.stdout or "")
    assert "Traceback" not in text, f"saltutil.running emitted a traceback: {text!r}"
