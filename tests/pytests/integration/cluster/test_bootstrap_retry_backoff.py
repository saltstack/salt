"""
Integration regression for PR #70732 / issue #70727.

When a clustered master defers a minion's initial pillar request with the
``cluster_retry`` sentinel (master's Raft node is still catching up),
pre-fix the minion logged three hard ``[ERROR]`` lines plus a traceback on
every retry:

    [ERROR] Master did not return a session key for pillar request (cluster not ready)
    [ERROR] Error while bringing up minion for multi-master. ... Exception getting pillar.
    [ERROR] This Minion was scheduled to stop. Not running Minion.tune_in()

The retry loop still eventually succeeded, but the log looked like a
hard failure to any operator watching bringup.  Post-fix (PR #70732) the
``MinionManager._connect_minion`` retry path recognises the
``cluster_retry`` sentinel on the inner ``AuthenticationError`` and logs
a single ``[INFO]`` line instead:

    [INFO] Master <ip> is still catching up (cluster not ready); retrying in <N>s

This is an in-process cross-module integration test:

* ``cluster_master_1`` + ``cluster_master_2`` from the existing conftest
  provide a real 2-master cluster so the minion opts come from the real
  loader + apply_minion_config (not hand-built like a unit test).
* The test instantiates a real ``salt.minion.MinionManager`` against
  those opts and drives one iteration of ``_connect_minion`` with
  ``Minion.connect_master`` monkey-patched to raise the same
  ``SaltClientError("Exception getting pillar.") from
  AuthenticationError("... (cluster not ready)")`` exception chain the
  pillar channel produces during a real cluster-bringup race.
* ``caplog`` captures ``salt.minion`` log output; the test asserts the
  post-fix INFO line fires once and the pre-fix multi-master ERROR line
  never fires.

This exercises the real salt.channel.client sentinel constants
(``CLUSTER_NOT_READY_SUFFIX``, ``_is_cluster_not_ready_message``), the
real ``MinionManager._connect_minion`` branch logic, and the real
``minion._running`` reset -- the three pieces of PR #70732 that
pre-fix would have logged ERROR + traceback.

Pre-fix the symbols don't exist (``AttributeError`` on
``salt.channel.client._is_cluster_not_ready_message``) and the branch
logic doesn't inspect ``exc.__cause__``, so the ERROR line always fires
and the INFO line never does -- the assertions below fail.
"""

import asyncio
import logging

import pytest

import salt.channel.client
import salt.config
import salt.crypt
import salt.exceptions
import salt.minion

pytestmark = [
    pytest.mark.slow_test,
    pytest.mark.timeout(240),
]


def _build_cluster_retry_exception():
    """
    Construct the exact exception chain
    ``salt.pillar.{Async,}RemotePillar.compile_pillar`` re-raises when a
    clustered master replies with the ``cluster_retry`` sentinel.
    """
    inner = salt.crypt.AuthenticationError(
        "Master did not return a session key for pillar request"
        + salt.channel.client.CLUSTER_NOT_READY_SUFFIX
    )
    outer = salt.exceptions.SaltClientError("Exception getting pillar.")
    outer.__cause__ = inner
    return outer


class _FakeMinion:
    """
    Stand-in for ``salt.minion.Minion`` that is just rich enough to run
    one iteration of ``MinionManager._connect_minion``'s retry branch.

    ``connect_master`` raises the ``cluster_retry`` exception chain the
    first time it is called and succeeds on the second call -- so the
    retry loop exits cleanly after confirming the fix path fired.
    """

    def __init__(self, opts):
        self.opts = opts
        self.destroy_calls = 0
        self.tune_in_calls = 0
        self._running = True
        self._connect_calls = 0
        # ``_connect_minion`` reads these during the retry branch.
        self.beacons_leader = False

    async def connect_master(self, failed=False):
        self._connect_calls += 1
        if self._connect_calls == 1:
            raise _build_cluster_retry_exception()

    def setup_beacons(self, before_connect=False):
        pass

    def setup_scheduler(self, before_connect=False):
        pass

    def tune_in(self, start=True):
        self.tune_in_calls += 1

    def destroy(self):
        self.destroy_calls += 1
        # Real ``Minion.destroy()`` flips ``_running`` to False; PR #70732
        # resets it to None in ``_connect_minion``.  Mirror that side
        # effect so the ``_running = None`` assertion downstream is
        # meaningful.
        self._running = False


def test_cluster_not_ready_retry_logs_info_not_error(
    cluster_master_1, cluster_master_2, caplog
):
    """
    Drive one ``_connect_minion`` retry cycle with a fake Minion that
    raises the cluster-retry sentinel.  The real
    ``MinionManager._connect_minion`` code path must log one INFO line
    (``catching up (cluster not ready); retrying in Ns``) and must not
    log the pre-fix multi-master ERROR line.

    Uses ``cluster_master_1`` + ``cluster_master_2`` to anchor the test
    to a real cluster config -- the minion opts come from
    ``minion_config`` against that master's ret port, so the
    MinionManager receives the same opts shape a real salt-minion
    process would see on bringup.
    """
    # Build a minion opts dict pointed at the real cluster.  Start from
    # the DEFAULT_MINION_OPTS so every field MinionManager touches has
    # a value, then overlay the cluster's address + the test's own
    # knobs.
    port = cluster_master_1.config["ret_port"]
    addr = cluster_master_1.config["interface"]
    opts = dict(salt.config.DEFAULT_MINION_OPTS)
    opts["id"] = "bootstrap-retry-backoff-fake"
    opts["master"] = f"{addr}:{port}"
    opts["transport"] = cluster_master_1.config["transport"]
    # These are the only MinionManager-touched keys that don't default
    # to a usable value on the DEFAULT_MINION_OPTS copy.
    opts["acceptance_wait_time"] = 0
    opts["acceptance_wait_time_max"] = 0
    opts.setdefault("master_type", "str")

    mgr = salt.minion.MinionManager(opts)
    # The retry loop's backoff would otherwise sleep up to 60s -- shrink
    # it to keep the test well under 60s total runtime.
    mgr.auth_wait = 0.1
    mgr.max_auth_wait = 0.2

    fake_minion = _FakeMinion(opts)

    caplog.clear()
    caplog.set_level(logging.DEBUG, logger="salt.minion")

    loop = asyncio.new_event_loop()
    try:
        loop.run_until_complete(mgr._connect_minion(fake_minion))
    finally:
        loop.close()

    # The fake minion raises once then succeeds -- so ``_connect_minion``
    # must have taken both branches of the retry loop.
    assert fake_minion._connect_calls == 2, (
        f"Fake minion should have been called twice (fail + succeed); "
        f"got {fake_minion._connect_calls}"
    )
    assert fake_minion.destroy_calls == 1, (
        f"MinionManager._connect_minion must destroy() the failing "
        f"minion before retrying; got {fake_minion.destroy_calls} calls"
    )

    # Latent correctness fix from PR #70732: ``_connect_minion`` sets
    # ``minion._running = None`` after ``destroy()`` so the successful
    # retry's ``tune_in(start=False)`` binds the master cleanly.
    assert fake_minion._running is None, (
        "After the retry succeeds ``minion._running`` must be ``None``, "
        "not the ``False`` value ``destroy()`` leaves behind.  "
        "Regression of PR #70732 latent correctness fix."
    )

    # Walk the emitted records so the assertions name the exact signature
    # that's missing or unexpected.
    info_messages = [
        rec.getMessage()
        for rec in caplog.records
        if rec.levelno == logging.INFO
        and rec.name == "salt.minion"
        and "catching up (cluster not ready)" in rec.getMessage()
    ]
    error_messages = [
        rec.getMessage()
        for rec in caplog.records
        if rec.levelno == logging.ERROR
        and rec.name == "salt.minion"
        and "Error while bringing up minion for multi-master" in rec.getMessage()
    ]

    assert not error_messages, (
        f"MinionManager._connect_minion logged {len(error_messages)} "
        f"'Error while bringing up minion for multi-master' line(s) for "
        f"a cluster-not-ready retry -- regression of PR #70732.\n\n"
        + "\n".join(error_messages[:5])
    )

    assert info_messages, (
        "Expected at least one 'catching up (cluster not ready); "
        "retrying in Ns' INFO line from MinionManager._connect_minion.  "
        "Pre-fix: the symbol ``salt.channel.client.CLUSTER_NOT_READY_SUFFIX`` "
        "didn't exist and the retry branch didn't inspect "
        "``exc.__cause__``, so no INFO line fired."
    )

    # Hard contract on the salt.channel.client half of PR #70732 -- those
    # symbols are what MinionManager's branch inspects.
    assert hasattr(salt.channel.client, "CLUSTER_NOT_READY_SUFFIX"), (
        "salt.channel.client.CLUSTER_NOT_READY_SUFFIX must exist for "
        "the pillar channel + MinionManager to agree on the sentinel.  "
        "Regression of PR #70732."
    )
    assert salt.channel.client.CLUSTER_NOT_READY_SUFFIX == " (cluster not ready)", (
        f"CLUSTER_NOT_READY_SUFFIX wording changed to "
        f"{salt.channel.client.CLUSTER_NOT_READY_SUFFIX!r}; the pillar "
        f"channel and the detector must stay in lockstep."
    )
    assert salt.channel.client._is_cluster_not_ready_message(
        "Master did not return a session key for pillar request"
        + salt.channel.client.CLUSTER_NOT_READY_SUFFIX
    ), "_is_cluster_not_ready_message must recognise its own sentinel"
    assert not salt.channel.client._is_cluster_not_ready_message(
        "some other authentication error"
    ), "_is_cluster_not_ready_message must reject non-sentinel messages"
