"""
Unit tests for :meth:`salt.topology.link.PeerMasterLink.quiesce` drain
semantics (RFC implementation-follow-up item 3).

The RFC spec:

* duration = ``opts["topology_detach_quiesce"]`` (default:
  ``opts["publish_timeout"]``)
* drain exit = (no active breadcrumbs reference this link) OR timer
  elapsed, whichever comes first
* after exit, link transitions to DISCONNECTED
* in-flight returns still mid-send when the timer fires: the current
  ``send_return`` completes before the transition
* operator-visible WARNING log on the timer-elapsed path listing any
  undelivered jids

These tests drive ``quiesce`` directly without a running peer by
pre-populating ``_health`` / ``_inflight_returns`` and passing in a
small in-memory fake breadcrumb cache that mirrors the
:class:`salt.utils.mmap_cache.MmapCache` surface
:func:`salt.topology.breadcrumbs.jids_for_link` consumes.
"""

import asyncio
import logging
import time

import pytest

import salt.utils.msgpack
from salt.config.topology import PeerRef
from salt.topology.link import LinkHealth, PeerMasterLink

pytestmark = [
    pytest.mark.skip_on_windows,
]


# ---------------------------------------------------------------------------
# Fakes: in-memory breadcrumb cache that satisfies ``jids_for_link``.
# ---------------------------------------------------------------------------


class _FakeBreadcrumbCache:
    """Minimal shim exposing just ``list_items`` for ``jids_for_link``."""

    def __init__(self):
        self._entries = {}  # key -> msgpack bytes

    def add(self, jid, link_cluster_id, ttl=60.0):
        self._entries[jid] = salt.utils.msgpack.packb(
            {
                "link_cluster_id": link_cluster_id,
                "expiry_at": time.time() + ttl,
            },
            use_bin_type=True,
        )

    def remove(self, jid):
        self._entries.pop(jid, None)

    def list_items(self):
        return list(self._entries.items())


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def io_loop():
    loop = asyncio.new_event_loop()
    try:
        yield loop
    finally:
        loop.close()


def _make_link(io_loop, opts_override=None):
    opts = {
        "cluster_id": "west",
        "topology_link_port": 4521,
        "pki_dir": "/tmp/not-used",
        "publish_timeout": 5,
    }
    if opts_override:
        opts.update(opts_override)
    seed = PeerRef(host="peer-east", port=4521, finger=None)
    link = PeerMasterLink(opts, seed, io_loop)
    link._peer_cluster_id = "east"
    link._health = LinkHealth.CONNECTED
    return link


# ---------------------------------------------------------------------------
# Already-DISCONNECTED is a no-op
# ---------------------------------------------------------------------------


def test_quiesce_already_disconnected_is_noop(io_loop):
    """A DISCONNECTED link short-circuits quiesce (no state change)."""
    link = _make_link(io_loop)
    link._health = LinkHealth.DISCONNECTED
    io_loop.run_until_complete(link.quiesce())
    # Still DISCONNECTED; was never promoted to QUIESCING.
    assert link._health == LinkHealth.DISCONNECTED


# ---------------------------------------------------------------------------
# Clean exit when no breadcrumbs reference the link
# ---------------------------------------------------------------------------


def test_quiesce_exits_immediately_with_empty_breadcrumbs(io_loop):
    """With no breadcrumbs referencing the link, drain exits before the timer."""
    link = _make_link(io_loop, {"topology_detach_quiesce": 60})
    cache = _FakeBreadcrumbCache()  # empty
    start = time.monotonic()
    io_loop.run_until_complete(link.quiesce(breadcrumb_cache=cache))
    elapsed = time.monotonic() - start
    assert link._health == LinkHealth.DISCONNECTED
    # Must not have slept for the full 60s window.
    assert elapsed < 5.0, f"quiesce took {elapsed:.2f}s with empty breadcrumbs"


def test_quiesce_exits_when_last_breadcrumb_clears(io_loop):
    """Drain exits as soon as the breadcrumb set referencing the link empties."""
    link = _make_link(io_loop, {"topology_detach_quiesce": 10})
    cache = _FakeBreadcrumbCache()
    cache.add("east:20250101000000000001", "east", ttl=30.0)

    async def _drive():
        task = asyncio.ensure_future(link.quiesce(breadcrumb_cache=cache))
        # Let one poll tick observe the live breadcrumb, then clear it.
        await asyncio.sleep(0.4)
        cache.remove("east:20250101000000000001")
        await task

    start = time.monotonic()
    io_loop.run_until_complete(_drive())
    elapsed = time.monotonic() - start
    assert link._health == LinkHealth.DISCONNECTED
    # Exited early (well under the 10s timer).
    assert elapsed < 5.0


def test_quiesce_ignores_breadcrumbs_for_other_links(io_loop):
    """Breadcrumbs pointing at a different link_cluster_id don't delay exit."""
    link = _make_link(io_loop, {"topology_detach_quiesce": 30})
    cache = _FakeBreadcrumbCache()
    cache.add("south:20250101000000000002", "south", ttl=30.0)
    start = time.monotonic()
    io_loop.run_until_complete(link.quiesce(breadcrumb_cache=cache))
    elapsed = time.monotonic() - start
    assert link._health == LinkHealth.DISCONNECTED
    assert elapsed < 5.0


# ---------------------------------------------------------------------------
# Timer-elapsed path logs WARNING with pending jids
# ---------------------------------------------------------------------------


def test_quiesce_timer_elapsed_logs_warning_with_pending_jids(io_loop, caplog):
    """When the drain timer runs out, the WARNING names each stuck jid."""
    link = _make_link(io_loop, {"topology_detach_quiesce": 0.5})
    cache = _FakeBreadcrumbCache()
    cache.add("east:20250101000000000003", "east", ttl=30.0)
    cache.add("east:20250101000000000004", "east", ttl=30.0)
    with caplog.at_level(logging.WARNING, logger="salt.topology.link"):
        io_loop.run_until_complete(link.quiesce(breadcrumb_cache=cache))
    assert link._health == LinkHealth.DISCONNECTED
    warning_records = [rec for rec in caplog.records if rec.levelno == logging.WARNING]
    assert warning_records, "quiesce timer-elapsed path must log WARNING"
    text = "\n".join(rec.getMessage() for rec in warning_records)
    assert "quiesce drain timer elapsed" in text
    assert "east:20250101000000000003" in text
    assert "east:20250101000000000004" in text


def test_quiesce_timer_elapsed_without_cache_still_disconnects(io_loop):
    """Without a breadcrumb cache the drain just waits the timer; no raise."""
    link = _make_link(io_loop, {"topology_detach_quiesce": 0.2})
    start = time.monotonic()
    io_loop.run_until_complete(link.quiesce())
    elapsed = time.monotonic() - start
    assert link._health == LinkHealth.DISCONNECTED
    # Slept for roughly the drain window.
    assert elapsed >= 0.15


# ---------------------------------------------------------------------------
# publish_timeout fallback when topology_detach_quiesce unset
# ---------------------------------------------------------------------------


def test_quiesce_falls_back_to_publish_timeout(io_loop):
    """When ``topology_detach_quiesce`` is absent, ``publish_timeout`` is used."""
    link = _make_link(io_loop, {"publish_timeout": 0.3})
    # Explicitly drop the detach knob so the fallback engages.
    link.opts.pop("topology_detach_quiesce", None)
    start = time.monotonic()
    io_loop.run_until_complete(link.quiesce())
    elapsed = time.monotonic() - start
    assert link._health == LinkHealth.DISCONNECTED
    # Timer fired roughly at publish_timeout.
    assert 0.2 <= elapsed < 2.0


# ---------------------------------------------------------------------------
# Mid-send send_return completes before transition
# ---------------------------------------------------------------------------


def test_quiesce_waits_for_inflight_send_return_at_timer(io_loop):
    """When the drain timer fires with an in-flight send_return, the transition
    waits until the inflight counter drops to zero."""
    link = _make_link(io_loop, {"topology_detach_quiesce": 0.2})
    cache = _FakeBreadcrumbCache()
    cache.add("east:20250101000000000005", "east", ttl=30.0)

    async def _drive():
        # Simulate send_return mid-send: counter non-zero across the timer.
        link._inflight_returns = 1
        task = asyncio.ensure_future(link.quiesce(breadcrumb_cache=cache))
        # Let the drain timer run out.
        await asyncio.sleep(0.4)
        # At this point the drain is waiting for the inflight counter to
        # drop; link must NOT be DISCONNECTED yet.
        assert link._health == LinkHealth.QUIESCING
        # Simulate the mid-send send_return finishing.
        link._inflight_returns = 0
        await task

    io_loop.run_until_complete(_drive())
    assert link._health == LinkHealth.DISCONNECTED


# ---------------------------------------------------------------------------
# send_return tracks inflight counter on normal completion
# ---------------------------------------------------------------------------


def test_send_return_increments_and_decrements_inflight(io_loop):
    """A completed ``send_return`` leaves ``_inflight_returns`` back at 0."""
    link = _make_link(io_loop)
    link._rotate_session(b"\x00" * 32)

    class _FakeReq:
        def __init__(self, link):
            self._link = link

        async def send(self, payload, **kwargs):
            # Observe the counter mid-send.
            assert self._link._inflight_returns == 1
            return {"ok": True}

    link._req_channel = _FakeReq(link)
    io_loop.run_until_complete(link.send_return([{"id": "m1"}], path=["west"]))
    assert link._inflight_returns == 0


def test_send_return_decrements_on_exception(io_loop):
    """A ``send_return`` whose underlying send raises still releases the gate."""
    link = _make_link(io_loop)
    link._rotate_session(b"\x00" * 32)

    class _FakeReq:
        async def send(self, payload, **kwargs):
            raise RuntimeError("transport down")

    link._req_channel = _FakeReq()
    with pytest.raises(RuntimeError):
        io_loop.run_until_complete(link.send_return([{"id": "m1"}], path=["west"]))
    assert link._inflight_returns == 0
