"""
Unit tests for ``salt.cluster.state_sync`` — the four-stream paged bulk
state-sync used by ``cluster_isolated_filesystem`` joiners.

Pins:

* the chunk wire shape (item lists + per-channel eof flag);
* the chunking knobs (count for keys/denied, byte budget for roots);
* :class:`StateSyncSession` — fires ``on_complete`` exactly once when
  every channel eofs, and only that once even on duplicate eofs;
* :meth:`StateSyncSession.force_complete` — fires the watchdog path.
"""

import pytest

from salt.cluster.state_sync import (
    ALL_CHANNELS,
    DEFAULT_KEY_CHUNK_COUNT,
    DEFAULT_ROOTS_CHUNK_BYTES,
    DENIED_CHANNEL,
    FILE_ROOTS_CHANNEL,
    KEYS_CHANNEL,
    PILLAR_ROOTS_CHANNEL,
    StateSyncSession,
    install_keys_chunk,
    install_root_chunk,
    iter_keys_chunks,
    iter_root_chunks,
    new_session_id,
)

# ---------------------------------------------------------------------------
# Channel inventory + session id
# ---------------------------------------------------------------------------


def test_all_channels_inventory():
    """The four channels are exactly the ones we ship over the wire."""
    assert set(ALL_CHANNELS) == {
        KEYS_CHANNEL,
        DENIED_CHANNEL,
        FILE_ROOTS_CHANNEL,
        PILLAR_ROOTS_CHANNEL,
    }


def test_new_session_id_is_unique():
    ids = {new_session_id() for _ in range(50)}
    assert len(ids) == 50


# ---------------------------------------------------------------------------
# iter_keys_chunks (sender, count-based)
# ---------------------------------------------------------------------------


def _keys_opts(monkeypatch, fake_dump):
    """Force ``salt.cache.Cache.list_all`` to return *fake_dump*."""
    import salt.cache

    class _FakeCache:
        def __init__(self, *args, **kwargs):
            pass

        def list_all(self, channel, include_data=False):  # noqa: ARG002
            return dict(fake_dump.get(channel, {}))

    monkeypatch.setattr(salt.cache, "Cache", _FakeCache)
    return {"keys.cache_driver": "localfs_key"}


def test_iter_keys_chunks_empty_yields_one_empty_chunk(monkeypatch):
    """An empty bank still yields exactly one chunk so the eof flag fires."""
    opts = _keys_opts(monkeypatch, {KEYS_CHANNEL: {}})
    chunks = list(iter_keys_chunks(opts, KEYS_CHANNEL))
    assert chunks == [[]]


def test_iter_keys_chunks_count_based_split(monkeypatch):
    """A 250-entry bank with default 200-count chunks → 2 chunks (200 + 50)."""
    bank = {f"m{i:03d}": {"state": "accepted", "pub": "p"} for i in range(250)}
    opts = _keys_opts(monkeypatch, {KEYS_CHANNEL: bank})
    chunks = list(iter_keys_chunks(opts, KEYS_CHANNEL))
    assert [len(c) for c in chunks] == [DEFAULT_KEY_CHUNK_COUNT, 50]
    # Each item is the wire-shape dict.
    assert chunks[0][0] == {
        "id": "m000",
        "value": {"state": "accepted", "pub": "p"},
    }


def test_iter_keys_chunks_custom_count(monkeypatch):
    """``count`` override controls chunk size."""
    bank = {f"m{i}": {"state": "accepted", "pub": "p"} for i in range(7)}
    opts = _keys_opts(monkeypatch, {KEYS_CHANNEL: bank})
    chunks = list(iter_keys_chunks(opts, KEYS_CHANNEL, count=3))
    assert [len(c) for c in chunks] == [3, 3, 1]


def test_iter_keys_chunks_unknown_channel_raises(monkeypatch):
    opts = _keys_opts(monkeypatch, {})
    with pytest.raises(ValueError):
        list(iter_keys_chunks(opts, "wat"))


# ---------------------------------------------------------------------------
# iter_root_chunks (sender, byte-budget-based)
# ---------------------------------------------------------------------------


def test_iter_root_chunks_empty_yields_one_empty_chunk():
    """No roots → single empty chunk so the eof flag still fires."""
    assert list(iter_root_chunks(None)) == [[]]
    assert list(iter_root_chunks({})) == [[]]


def test_iter_root_chunks_single_file_under_budget(tmp_path):
    """A small tree fits in one chunk."""
    base = tmp_path / "base"
    base.mkdir()
    f = base / "init.sls"
    f.write_text("ok\n")
    f.chmod(0o644)

    chunks = list(iter_root_chunks({"base": [str(base)]}))

    assert len(chunks) == 1
    assert chunks[0] == [
        {"env": "base", "path": "init.sls", "mode": 0o644, "data": b"ok\n"}
    ]


def test_iter_root_chunks_byte_budget_splits(tmp_path):
    """When cumulative bytes exceed the budget, a new chunk starts."""
    base = tmp_path / "base"
    base.mkdir()
    (base / "a.sls").write_bytes(b"x" * 600)
    (base / "b.sls").write_bytes(b"y" * 600)
    (base / "c.sls").write_bytes(b"z" * 600)

    chunks = list(iter_root_chunks({"base": [str(base)]}, byte_budget=1000))

    # First chunk holds one file (600 ≤ 1000), adding a second (600+600=1200)
    # crosses the budget so the second file starts a new chunk; same for
    # the third.  Result: 3 chunks of one file each, in directory order.
    assert len(chunks) == 3
    paths = [chunks[i][0]["path"] for i in range(3)]
    assert sorted(paths) == ["a.sls", "b.sls", "c.sls"]


def test_iter_root_chunks_oversized_file_gets_own_chunk(tmp_path):
    """A single file larger than the budget gets its own chunk."""
    base = tmp_path / "base"
    base.mkdir()
    (base / "small.sls").write_bytes(b"x" * 100)
    (base / "huge.sls").write_bytes(b"y" * 5000)

    chunks = list(iter_root_chunks({"base": [str(base)]}, byte_budget=1000))

    # Two chunks: small first, then huge alone.
    assert len(chunks) == 2
    files_by_chunk = [[e["path"] for e in c] for c in chunks]
    assert sorted(files_by_chunk[0] + files_by_chunk[1]) == ["huge.sls", "small.sls"]


def test_iter_root_chunks_default_byte_budget_constant():
    """Constant has to be > 0 and a whole number; pinning so a refactor
    does not silently drop chunking."""
    assert isinstance(DEFAULT_ROOTS_CHUNK_BYTES, int)
    assert DEFAULT_ROOTS_CHUNK_BYTES > 0


# ---------------------------------------------------------------------------
# install_keys_chunk / install_root_chunk (receiver)
# ---------------------------------------------------------------------------


def test_install_keys_chunk_writes_via_cache(monkeypatch):
    """``install_keys_chunk`` calls ``cache.store`` once per valid item."""
    stored = []

    class _FakeCache:
        def __init__(self, *args, **kwargs):
            pass

        def store(self, bank, key, value):
            stored.append((bank, key, value))

    import salt.cache

    monkeypatch.setattr(salt.cache, "Cache", _FakeCache)

    items = [
        {"id": "m1", "value": {"state": "accepted", "pub": "p1"}},
        {"id": "m2", "value": {"state": "pending", "pub": "p2"}},
        {"id": "m3"},  # missing value, skipped
        {"value": {"state": "accepted"}},  # missing id, skipped
        {},  # empty, skipped
    ]
    written = install_keys_chunk(
        {"keys.cache_driver": "localfs_key"}, KEYS_CHANNEL, items
    )

    assert written == 2
    assert stored == [
        ("keys", "m1", {"state": "accepted", "pub": "p1"}),
        ("keys", "m2", {"state": "pending", "pub": "p2"}),
    ]


def test_install_keys_chunk_unknown_channel_raises():
    with pytest.raises(ValueError):
        install_keys_chunk({"keys.cache_driver": "localfs_key"}, "wat", [])


def test_install_root_chunk_groups_by_env_and_writes(tmp_path):
    """Receiver re-groups flat ``items`` back to ``{env: [entries]}``."""
    base = tmp_path / "base"
    base.mkdir()
    prod = tmp_path / "prod"
    prod.mkdir()
    items = [
        {"env": "base", "path": "a.sls", "mode": 0o644, "data": b"a\n"},
        {"env": "prod", "path": "b.sls", "mode": 0o600, "data": b"b\n"},
        {"env": "base", "path": "deep/c.sls", "mode": 0o644, "data": b"c\n"},
        # invalid entries — silently skipped
        {"env": "base", "data": b"no-path\n"},
        {"path": "no-env.sls", "data": b"x\n"},
    ]
    written = install_root_chunk({"base": [str(base)], "prod": [str(prod)]}, items)
    assert written == 3
    assert (base / "a.sls").read_bytes() == b"a\n"
    assert (base / "deep" / "c.sls").read_bytes() == b"c\n"
    assert (prod / "b.sls").read_bytes() == b"b\n"


# ---------------------------------------------------------------------------
# StateSyncSession state machine
# ---------------------------------------------------------------------------


def test_session_fires_on_complete_after_all_channels_eof():
    """``on_complete`` fires exactly when the last outstanding eof lands."""
    fired = []
    s = StateSyncSession("sess-1", lambda: fired.append("done"))

    # Three channels eof — still one outstanding.
    s.record_chunk(KEYS_CHANNEL, 0, eof=True, items_installed=10)
    s.record_chunk(DENIED_CHANNEL, 0, eof=True, items_installed=0)
    s.record_chunk(FILE_ROOTS_CHANNEL, 0, eof=True, items_installed=5)
    assert fired == []
    assert not s.completed

    # Last channel eof — fires once.
    s.record_chunk(PILLAR_ROOTS_CHANNEL, 0, eof=True, items_installed=2)
    assert fired == ["done"]
    assert s.completed


def test_session_handles_intermediate_chunks_then_eof():
    """A multi-chunk channel only flips eof on the final chunk."""
    fired = []
    s = StateSyncSession("sess-2", lambda: fired.append("done"))
    s.record_chunk(KEYS_CHANNEL, 0, eof=False, items_installed=200)
    s.record_chunk(KEYS_CHANNEL, 1, eof=False, items_installed=200)
    s.record_chunk(KEYS_CHANNEL, 2, eof=True, items_installed=50)
    s.record_chunk(DENIED_CHANNEL, 0, eof=True, items_installed=0)
    s.record_chunk(FILE_ROOTS_CHANNEL, 0, eof=True, items_installed=0)
    s.record_chunk(PILLAR_ROOTS_CHANNEL, 0, eof=True, items_installed=0)
    assert fired == ["done"]


def test_session_on_complete_fires_only_once_even_on_duplicate_eofs():
    """A second eof on an already-eof'd channel does not re-fire."""
    fired = []
    s = StateSyncSession("sess-3", lambda: fired.append("done"))
    for ch in ALL_CHANNELS:
        s.record_chunk(ch, 0, eof=True, items_installed=0)
    assert fired == ["done"]

    # Duplicate eof — must not fire again.
    s.record_chunk(KEYS_CHANNEL, 1, eof=True, items_installed=0)
    assert fired == ["done"]


def test_session_force_complete_fires_with_partial_state():
    """Watchdog path: ``force_complete`` runs the callback even if some
    channels never eof'd."""
    fired = []
    s = StateSyncSession("sess-4", lambda: fired.append("done"))
    s.record_chunk(KEYS_CHANNEL, 0, eof=True, items_installed=3)
    # denied / file_roots / pillar_roots never eof
    s.force_complete()
    assert fired == ["done"]
    assert s.completed


def test_session_force_complete_after_natural_complete_is_noop():
    """``force_complete`` after the natural completion does not re-fire."""
    fired = []
    s = StateSyncSession("sess-5", lambda: fired.append("done"))
    for ch in ALL_CHANNELS:
        s.record_chunk(ch, 0, eof=True, items_installed=0)
    s.force_complete()
    assert fired == ["done"]


def test_session_unknown_channel_logs_and_skips():
    """A chunk for a channel not in the session's expected set is ignored."""
    fired = []
    s = StateSyncSession("sess-6", lambda: fired.append("done"))
    s.record_chunk("unknown-channel", 0, eof=True, items_installed=99)
    # Must not advance toward completion.
    assert fired == []
    for ch in ALL_CHANNELS:
        s.record_chunk(ch, 0, eof=True, items_installed=0)
    assert fired == ["done"]


def test_session_status_snapshot():
    """``status()`` exposes per-channel chunks/items/eof for log output."""
    s = StateSyncSession("sess-7", lambda: None)
    s.record_chunk(KEYS_CHANNEL, 0, eof=False, items_installed=10)
    s.record_chunk(KEYS_CHANNEL, 1, eof=True, items_installed=5)
    snap = s.status()
    assert snap[KEYS_CHANNEL] == {"eof": True, "chunks": 2, "items": 15}
    assert snap[DENIED_CHANNEL] == {"eof": False, "chunks": 0, "items": 0}


# ---------------------------------------------------------------------------
# Wire-level chunk-drop simulation (asyncio watchdog wiring)
# ---------------------------------------------------------------------------
#
# Mirrors the join-reply receiver wiring in
# ``MasterPubServerChannel._begin_state_sync_session`` — a session is
# created, ``loop.call_later(deadline, session.force_complete)`` schedules
# a watchdog, then chunks arrive.  The tests below prove that under a
# chunk-drop scenario (some seq numbers never arrive) the watchdog fires
# ``on_complete`` with the partial state rather than leaving the joiner
# stuck, and that a complete delivery cancels the watchdog cleanly.


def test_watchdog_fires_on_complete_when_chunks_dropped():
    """
    Asyncio-driven failure-mode rehearsal: schedule a real ``call_later``
    watchdog (matching production), feed only some channels' chunks,
    advance the loop, and verify ``on_complete`` ran with the partial
    state.
    """
    import asyncio  # pylint: disable=import-outside-toplevel

    loop = asyncio.new_event_loop()
    try:
        fired = []
        session = StateSyncSession("drop-test-1", lambda: fired.append("complete"))
        # Pretend the cluster_aes / cluster.pem channels arrived; the
        # roots channels were dropped on the wire.
        session.record_chunk(KEYS_CHANNEL, 0, eof=True, items_installed=12)
        session.record_chunk(DENIED_CHANNEL, 0, eof=True, items_installed=0)
        # No FILE_ROOTS_CHANNEL or PILLAR_ROOTS_CHANNEL chunks — drop.
        assert not session.completed
        assert fired == []

        # Schedule the watchdog the same way ``_begin_state_sync_session``
        # does in production.  Use a tight deadline so the test runs fast.
        loop.call_later(0.05, session.force_complete)

        # Drive the loop until the watchdog fires.  Cap the wait so a
        # broken implementation cannot hang the suite.
        async def _wait():
            deadline = loop.time() + 1.0
            while loop.time() < deadline and not session.completed:
                await asyncio.sleep(0.01)

        loop.run_until_complete(_wait())
        assert session.completed, (
            "Watchdog did not force-complete the session within 1s of the "
            "scheduled deadline; production joiners would hang here"
        )
        assert fired == ["complete"]
        # Status must still reflect the partial delivery so the join-reply
        # logger / debug runners can describe what was missing.
        snap = session.status()
        assert snap[KEYS_CHANNEL]["eof"] is True
        assert snap[FILE_ROOTS_CHANNEL]["eof"] is False
        assert snap[PILLAR_ROOTS_CHANNEL]["eof"] is False
    finally:
        loop.close()


def test_watchdog_cancelled_when_all_channels_complete_in_time():
    """
    The complementary case: all chunks arrive before the deadline.  The
    natural ``on_complete`` runs once; the watchdog handle, if cancelled
    by the caller (matching ``_begin_state_sync_session`` behaviour),
    must not re-fire ``on_complete``.
    """
    import asyncio  # pylint: disable=import-outside-toplevel

    loop = asyncio.new_event_loop()
    try:
        fired = []
        session = StateSyncSession("drop-test-2", lambda: fired.append("complete"))
        handle = loop.call_later(0.05, session.force_complete)

        # All chunks arrive before the deadline.
        for ch in ALL_CHANNELS:
            session.record_chunk(ch, 0, eof=True, items_installed=1)
        assert session.completed
        assert fired == ["complete"]

        # Cancel the watchdog (production code does this in the
        # ``_on_complete`` callback) and let the loop spin past the
        # original deadline.  ``on_complete`` must remain at one call.
        handle.cancel()

        async def _settle():
            await asyncio.sleep(0.1)

        loop.run_until_complete(_settle())
        assert fired == ["complete"], (
            f"Watchdog must not double-fire on_complete after natural "
            f"completion, got {fired!r}"
        )
    finally:
        loop.close()
