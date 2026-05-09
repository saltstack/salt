"""
Coverage for the ring gating in ``EventMonitor.handle_event``.

The gate sites at ``salt/master.py`` 1149-1197 wrap
``store_minions`` / ``store_job`` / ``_apply_peer_key_change`` in
``ring_membership.owns(opts, jid)``.  In stage 0 with a self-only
ring the gate is always-True and behaviour is unchanged from
pre-ring.  Stage 1 onwards the gate actually drops writes for
non-owned keys; these tests pin both ends of that contract so a
future regression to "always broadcast" or "always shard" surfaces.

Async note
----------
``EventMonitor.handle_event`` is ``async def``; without pytest-asyncio
installed in the salt repo we drive each call ourselves with
``asyncio.run`` instead of the ``@pytest.mark.asyncio`` decorator.
That decorator is silently ignored when the plugin is missing — async
test bodies never execute and every test "passes" trivially, which is
worse than not gating at all.
"""

import asyncio

import pytest

import salt.utils.event
from salt.cluster import ring_membership
from salt.master import EventMonitor
from tests.support.mock import patch


@pytest.fixture(autouse=True)
def _isolate_ring():
    """Per-test ring reset; cleanup runs even if a test raises."""
    ring_membership.reset()
    yield
    ring_membership.reset()


def _opts(interface="m1"):
    """Minimal opts the gate sites consult."""
    return {
        "interface": interface,
        "id": f"{interface}-host",
        "cluster_id": "test-cluster",
    }


def _make_monitor(opts):
    """Build an EventMonitor without actually starting the subprocess."""
    return EventMonitor(opts, ipc_publisher=None, channels=[])


def _fire(monitor, tag, payload):
    """Drive ``handle_event`` synchronously via ``asyncio.run``."""
    package = salt.utils.event.SaltEvent.pack(tag, payload)
    asyncio.run(monitor.handle_event(package))


# ---------------------------------------------------------------------------
# Stage 0 (self-only / empty ring): gate is always True, behaviour unchanged
# ---------------------------------------------------------------------------


def test_job_new_event_writes_when_ring_empty():
    """
    With an empty ring, ``ring_membership.owns`` returns True for every
    key, so the /new branch calls ``store_minions``.  Default
    behaviour pre-stage-1 — must remain identical until an operator
    flips ring policy.
    """
    monitor = _make_monitor(_opts())
    with patch("salt.utils.job.store_minions") as mock_store:
        _fire(
            monitor,
            "salt/job/20260508/new",
            {
                "__peer_id": "m2",
                "jid": "20260508-A",
                "minions": ["minion-a", "minion-b"],
            },
        )
    mock_store.assert_called_once()


def test_job_ret_event_writes_when_ring_empty():
    """
    Same as the /new test but for the /ret branch — empty ring gates
    every key as locally-owned, so ``store_job`` runs.
    """
    monitor = _make_monitor(_opts())
    with patch("salt.utils.job.store_job") as mock_store:
        _fire(
            monitor,
            "salt/job/20260508/ret/minion-a",
            {
                "__peer_id": "m2",
                "jid": "20260508-A",
                "id": "minion-a",
                "return": True,
            },
        )
    mock_store.assert_called_once()


# ---------------------------------------------------------------------------
# Stage 1 (voters policy): gate drops writes for non-owned keys
# ---------------------------------------------------------------------------


def _pick_owned_and_other_jid(members):
    """
    Return ``(owned_jid, other_jid)`` where ``owned_jid`` hashes to
    ``members[0]`` and ``other_jid`` hashes to a different member.

    Owners are determined by ``HashRing.get_owner`` on the rebuilt
    ring.  Iterating jid candidates is fast.
    """
    ring_membership.rebuild(members)
    ring = ring_membership.get_ring()
    owner_target = members[0]
    owned = None
    other = None
    for i in range(2000):
        jid = f"jid-search-{i:04d}"
        owner = ring.get_owner(jid)
        if owned is None and owner == owner_target:
            owned = jid
        elif other is None and owner != owner_target:
            other = jid
        if owned and other:
            break
    if not owned or not other:
        raise AssertionError(
            f"Could not synthesize owned/other jids for members={members!r}"
        )
    return owned, other


def test_job_new_event_drops_when_key_not_owned():
    """
    With ring populated and the jid hashed to a different member,
    the /new branch must NOT call ``store_minions``.  Direct evidence
    that the gate sites in master.py drop writes once policy flips.
    """
    members = ["m1", "m2", "m3"]
    owned_jid, other_jid = _pick_owned_and_other_jid(members)
    monitor = _make_monitor(_opts(interface="m1"))

    with patch("salt.utils.job.store_minions") as mock_store:
        # Owned by m1: store_minions runs.
        _fire(
            monitor,
            "salt/job/owned/new",
            {"__peer_id": "m2", "jid": owned_jid, "minions": ["x"]},
        )
        # Owned by m2 or m3: store_minions skipped.
        _fire(
            monitor,
            "salt/job/other/new",
            {"__peer_id": "m2", "jid": other_jid, "minions": ["y"]},
        )

    assert mock_store.call_count == 1, (
        f"Expected exactly one call (owned jid {owned_jid!r}); "
        f"got {mock_store.call_count}"
    )


def test_job_ret_event_drops_when_key_not_owned():
    """Mirror of the /new test for the /ret branch."""
    members = ["m1", "m2", "m3"]
    owned_jid, other_jid = _pick_owned_and_other_jid(members)
    monitor = _make_monitor(_opts(interface="m1"))

    with patch("salt.utils.job.store_job") as mock_store:
        _fire(
            monitor,
            "salt/job/owned/ret/minion-x",
            {
                "__peer_id": "m2",
                "jid": owned_jid,
                "id": "minion-x",
                "return": True,
            },
        )
        _fire(
            monitor,
            "salt/job/other/ret/minion-y",
            {
                "__peer_id": "m2",
                "jid": other_jid,
                "id": "minion-y",
                "return": False,
            },
        )

    assert mock_store.call_count == 1


def test_event_without_peer_id_is_ignored():
    """
    Events that don't carry ``__peer_id`` are not cluster-forwarded
    events — the gate sites short-circuit before consulting the ring.
    Pins the contract that local-origin events bypass the gate.
    """
    monitor = _make_monitor(_opts())
    with (
        patch("salt.utils.job.store_minions") as mock_minions,
        patch("salt.utils.job.store_job") as mock_job,
    ):
        _fire(
            monitor,
            "salt/job/20260508/new",
            {"jid": "x", "minions": ["a"]},  # no __peer_id
        )
        _fire(
            monitor,
            "salt/job/20260508/ret/minion-a",
            {"jid": "x", "id": "minion-a", "return": True},  # no __peer_id
        )
    mock_minions.assert_not_called()
    mock_job.assert_not_called()


def test_event_without_cluster_id_is_ignored():
    """A non-cluster master ignores forwarded job events entirely."""
    opts = _opts()
    opts.pop("cluster_id")
    monitor = _make_monitor(opts)
    with patch("salt.utils.job.store_minions") as mock_store:
        _fire(
            monitor,
            "salt/job/20260508/new",
            {"__peer_id": "m2", "jid": "x", "minions": ["a"]},
        )
    mock_store.assert_not_called()
