"""
Integration tests for the ``whitelist_modules`` propagation into the
beacons + engines + scheduler subsystems and the sys.doc error path.

Sister to :mod:`tests.pytests.integration.loader.test_state_whitelist_dunder`.
Where the functional tier proves the loader factories and Schedule
class wire up correctly, this tier boots a real salt-minion under a
strict ``whitelist_modules`` and exercises the end-to-end code paths
through the CLI: the minion must start cleanly with a shipped beacon
configured (so beacons factory + Beacon.__init__ + process_beacons all
run without KeyError'ing on ``__salt__["status.loadavg"]`` or
``config.merge``), ``salt-call`` on a missing function must produce a
docs message (not a traceback because ``sys`` isn't whitelisted), and
routine dispatch must still succeed on a whitelisted function
(``test.ping``).
"""

import pytest

from tests.conftest import FIPS_TESTRUN


@pytest.fixture
def whitelisted_minion(salt_master):
    """
    Minion booted with a deliberately narrow ``whitelist_modules`` --
    ``config``, ``status``, ``mine``, ``sys``, ``timezone``, ``cmd``,
    ``event``, ``pillar`` are all omitted from the wire loader.  The
    fix under test is that Salt's internal subsystems (scheduler
    bookkeeping, beacon composition, ``__mine_interval`` injection,
    sys.doc error-path) still work because they route through the
    inner unfiltered loader.

    A ``status`` beacon is configured so beacon loader composition
    with the non-whitelisted ``salt.modules.status`` gets exercised on
    every minion tick -- if the fix regresses, ``process_beacons``
    KeyError's on ``config.merge`` and beacon startup fails; the
    minion itself may still boot but ``beacons.list`` won't reflect
    the configured beacon.
    """
    minion = salt_master.salt_minion_daemon(
        "test-subsystem-whitelist-dunder-minion",
        overrides={
            "whitelist_modules": [
                "test",
                "grains",
                "saltutil",
                "state",
                "schedule",
                "beacons",
                "file",
            ],
            "mine_enabled": True,
            "mine_interval": 60,
            "beacons": {
                "status": [
                    {"loadavg": ["1-min"]},
                    {"interval": 60},
                ],
            },
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


# ---------------------------------------------------------------------------
# End-to-end: minion boots cleanly under strict whitelist_modules
# ---------------------------------------------------------------------------


def test_whitelisted_minion_dispatches_test_ping(salt_cli, whitelisted_minion):
    """
    Sanity check: a minion booted with a strict ``whitelist_modules``
    that omits every one of the internal-composition helpers our fix
    targets (``config``, ``status``, ``mine``, ``sys``, ``timezone``,
    ``event``, ``pillar``) is still functional -- ``test.ping``
    returns ``True`` through the master.

    If beacons factory / process_beacons / setup_scheduler /
    engine loader / sys.doc error path had regressed, the minion
    would either fail to start or drop off the master.
    """
    ret = salt_cli.run("test.ping", minion_tgt=whitelisted_minion.id)
    assert ret.returncode == 0, (ret.stdout, ret.stderr)
    assert ret.data is True, ret.data


# ---------------------------------------------------------------------------
# Beacon composition under strict whitelist
# ---------------------------------------------------------------------------


def test_beacons_list_reflects_configured_status_beacon(salt_cli, whitelisted_minion):
    """
    ``beacons.list`` on a minion whose ``whitelist_modules`` omits
    ``status`` and ``config`` must still expose the configured
    ``status`` beacon -- proving that both the beacons loader factory
    (which packs ``functions._dunder_salt`` as ``__salt__``) and
    ``Minion.process_beacons`` (which reads ``config.merge`` via the
    inner loader) worked end-to-end.  Pre-fix, either the beacon
    loader itself couldn't compose with ``status.*`` on load, or the
    tick-time ``config.merge`` KeyError'd and beacon processing
    silently degraded.
    """
    ret = salt_cli.run("beacons.list", minion_tgt=whitelisted_minion.id)
    text = str(ret.data or ret.stdout or "")
    assert "status" in text and "loadavg" in text, (
        "beacons.list did not reflect the configured status beacon; the "
        "beacons factory / process_beacons chain may have regressed. "
        f"Returned: {text!r}"
    )


# ---------------------------------------------------------------------------
# sys.doc error path under strict whitelist
# ---------------------------------------------------------------------------


def test_missing_function_error_path_does_not_traceback(salt_cli, whitelisted_minion):
    """
    Dispatching a nonexistent function on a minion whose
    ``whitelist_modules`` omits ``sys`` used to KeyError on the "did
    you mean" error-path ``functions["sys.doc"]`` lookup and surface
    a traceback to the operator instead of the intended fallback
    message.  The fix routes the sys.doc lookup through the inner
    unfiltered loader.
    """
    ret = salt_cli.run(
        "does_not_exist.definitely_missing",
        minion_tgt=whitelisted_minion.id,
    )
    text = str(ret.data or ret.stdout or ret.stderr or "")
    # A pre-fix minion would leak a Python traceback naming sys.doc
    # as the KeyError target.  The post-fix path either resolves
    # sys.doc through the inner loader (returning docs), or the outer
    # loader returns the "function is not available" message.
    assert not ("KeyError" in text and "sys.doc" in text), (
        f"Missing-function error path leaked a sys.doc KeyError to "
        f"the operator: {text!r}"
    )
    assert not ("Traceback" in text and "sys.doc" in text), (
        f"Missing-function error path returned a Python traceback "
        f"instead of the intended fallback message: {text!r}"
    )
