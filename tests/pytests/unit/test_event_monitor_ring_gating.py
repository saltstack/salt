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
        "sock_dir": "/tmp",
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


def _pick_owned_and_other_jid(members, ring_name="jobs_ring"):
    """
    Return ``(owned_jid, other_jid)`` where ``owned_jid`` hashes to
    ``members[0]`` and ``other_jid`` hashes to a different member.

    Multi-ring shape: the rebuild targets a named ring (``jobs_ring``
    by default), and the caller is expected to install a routing
    entry ``"jobs" -> ring_name`` so the gate site's
    ``owns_for(opts, "jobs", jid)`` defers to this ring.
    """
    ring_membership.rebuild(ring_name, members)
    ring = ring_membership.get_ring(ring_name)
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
    With the "jobs" data type routed to a ring and the jid hashed to
    a different member, the /new branch must NOT call
    ``store_minions``.  Direct evidence that the gate sites in
    master.py drop writes once a route + ring policy are in place.
    """
    members = ["m1", "m2", "m3"]
    owned_jid, other_jid = _pick_owned_and_other_jid(members)
    # Route "jobs" to the populated ring so ``owns_for`` defers to it.
    ring_membership.set_route("jobs", "jobs_ring")
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
    ring_membership.set_route("jobs", "jobs_ring")
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


# ---------------------------------------------------------------------------
# Multi-ring routing semantics at the gate site
# ---------------------------------------------------------------------------


def test_job_new_drops_when_routed_to_unknown_ring():
    """
    The "jobs" data type routed to a ring this master does NOT host
    locally (no Node, no ring contents) is a non-member situation:
    the gate site no-ops the write to avoid mirroring data that the
    actual ring members will reject.
    """
    # Route exists, but no rebuild has populated "jobs_ring" — the
    # ring is empty / unknown to this master.
    ring_membership.set_route("jobs", "jobs_ring")
    monitor = _make_monitor(_opts(interface="m1"))
    with patch("salt.utils.job.store_minions") as mock_store:
        _fire(
            monitor,
            "salt/job/20260508/new",
            {"__peer_id": "m2", "jid": "anything", "minions": ["x"]},
        )
    mock_store.assert_not_called()


def test_job_new_drop_fires_delegate_when_owner_known():
    """
    When the gate drops a routed job event AND the ring has a known
    owner, the EventMonitor fires a ``cluster/runner/delegate_write``
    event so the publish daemon can forward the write to the owner.
    Pin the delegate-on-miss safety net: a routed deployment with an
    asymmetric topology doesn't silently lose data.
    """
    ring_membership.rebuild("jobs_ring", ["other-master", "another-one"])
    ring_membership.set_route("jobs", "jobs_ring")
    monitor = _make_monitor(_opts(interface="m1"))

    fired = []

    class _FakeEvent:
        def __init__(self, *a, **kw):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def fire_event(self, data, tag):
            fired.append((tag, data))

    import salt.utils.event

    with (
        patch("salt.utils.job.store_minions") as mock_store,
        patch.object(salt.utils.event, "get_event", lambda *a, **kw: _FakeEvent()),
    ):
        _fire(
            monitor,
            "salt/job/20260517/new",
            {"__peer_id": "m2", "jid": "test-jid", "minions": ["m"]},
        )

    mock_store.assert_not_called()
    delegates = [e for e in fired if e[0] == "cluster/runner/delegate_write"]
    assert len(delegates) == 1
    _, data = delegates[0]
    assert data["data_type"] == "jobs"
    assert data["ring_id"] == "jobs_ring"
    assert data["write_kind"] == "store_minions"
    assert data["payload"] == {"jid": "test-jid", "minions": ["m"]}
    # Owner is one of the two ring members (consistent-hash answers
    # one or the other depending on the jid's hash).
    assert data["owner"] in {"other-master", "another-one"}


def test_job_ret_drop_fires_delegate_for_returns():
    """
    Same delegate-on-miss path for the ``/ret/`` branch — pins that
    minion-return writes also get forwarded to the ring owner when
    this master isn't a member.
    """
    ring_membership.rebuild("jobs_ring", ["owner-a", "owner-b"])
    ring_membership.set_route("jobs", "jobs_ring")
    monitor = _make_monitor(_opts(interface="m1"))

    fired = []

    class _FakeEvent:
        def __init__(self, *a, **kw):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def fire_event(self, data, tag):
            fired.append((tag, data))

    import salt.utils.event

    with (
        patch("salt.utils.job.store_job") as mock_store,
        patch.object(salt.utils.event, "get_event", lambda *a, **kw: _FakeEvent()),
    ):
        _fire(
            monitor,
            "salt/job/20260517/ret/minion-x",
            {
                "__peer_id": "m2",
                "jid": "test-jid",
                "id": "minion-x",
                "return": "ok",
            },
        )

    mock_store.assert_not_called()
    delegates = [e for e in fired if e[0] == "cluster/runner/delegate_write"]
    assert len(delegates) == 1
    _, data = delegates[0]
    assert data["write_kind"] == "store_job"
    assert data["payload"]["jid"] == "test-jid"
    assert data["payload"]["id"] == "minion-x"


def test_delegate_skip_when_this_master_is_the_owner():
    """
    Defensive: if ``ring_membership.get_owner`` somehow returns this
    master's address (it shouldn't, since owns_for would have
    returned True), the delegate path skips silently rather than
    looping the event back to itself.
    """
    ring_membership.rebuild("jobs_ring", ["m1", "m2", "m3"])
    ring_membership.set_route("jobs", "jobs_ring")
    monitor = _make_monitor(_opts(interface="m1"))

    fired = []

    class _FakeEvent:
        def __init__(self, *a, **kw):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def fire_event(self, data, tag):
            fired.append((tag, data))

    import salt.utils.event
    from salt.cluster.ring import HashRing

    real_ring = HashRing()
    real_ring.rebuild(["m1", "m2", "m3"])
    # Pick a JID that DOES hash to m1 so owns_for returns True and
    # the delegate path is never reached.
    owned_jid = None
    for i in range(2000):
        jid = f"jid-{i:04d}"
        if real_ring.get_owner(jid) == "m1":
            owned_jid = jid
            break
    assert owned_jid is not None

    with (
        patch("salt.utils.job.store_minions") as mock_store,
        patch.object(salt.utils.event, "get_event", lambda *a, **kw: _FakeEvent()),
    ):
        _fire(
            monitor,
            "salt/job/20260517/new",
            {"__peer_id": "m2", "jid": owned_jid, "minions": ["m"]},
        )

    # We DID own it; store_minions ran and no delegate fired.
    mock_store.assert_called_once()
    assert not fired


def test_job_new_writes_when_route_cleared():
    """
    Clearing the route returns "jobs" to broadcast — every master
    writes regardless of the ring's contents.  Pins the reversibility
    contract that operator runners depend on.
    """
    ring_membership.rebuild("jobs_ring", ["m1", "m2", "m3"])
    ring_membership.set_route("jobs", "jobs_ring")
    ring_membership.set_route("jobs", None)  # back to broadcast
    monitor = _make_monitor(_opts(interface="m1"))
    with patch("salt.utils.job.store_minions") as mock_store:
        _fire(
            monitor,
            "salt/job/20260508/new",
            {"__peer_id": "m2", "jid": "anything", "minions": ["x"]},
        )
    mock_store.assert_called_once()
