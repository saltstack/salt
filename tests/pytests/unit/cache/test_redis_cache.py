"""
Unit tests for ``salt.cache.redis_cache`` hierarchical-bank fixes.

Three closely-related bugs are covered here:

1. ``_build_bank_hier`` registers child bank names in both
   ``$BANK_<parent>`` (used by the flush tree-traversal) and
   ``$BANKEYS_<parent>`` (used by ``list_``). Without this,
   ``cache.list("minions")`` returns empty and ``salt-run
   manage.present`` reports no minions even when their data is in
   Redis.
2. ``_get_banks_to_remove`` decodes the ``bytes`` returned by
   ``smembers`` and skips the ``"."`` placeholder, so recursive flush
   can actually descend into sub-banks.
3. ``flush(bank, key=None)`` removes the flushed bank's reference
   from its parent's index sets, so ``list_(parent)`` no longer
   reports the freshly-flushed bank as still present.
"""

import pytest

import salt.cache.redis_cache as redis_cache
from tests.support.mock import MagicMock, patch


@pytest.fixture
def configure_loader_modules():
    return {redis_cache: {"__opts__": {}}}


def _saddargs(pipe):
    """Return the list of (set_name, value) tuples from ``pipe.sadd`` calls."""
    return [tuple(call.args) for call in pipe.sadd.call_args_list]


def _sremargs(pipe):
    """Return the list of (set_name, value) tuples from ``pipe.srem`` calls."""
    return [tuple(call.args) for call in pipe.srem.call_args_list]


# ---------------------------------------------------------------------------
# _build_bank_hier: parent-index population
# ---------------------------------------------------------------------------


class TestBuildBankHier:
    """
    Each ``store(bank, key, ...)`` call eventually calls
    ``_build_bank_hier(bank, pipe)`` to make sure every level of the
    bank path is recorded. Before the fix this only wrote a ``.``
    placeholder at each level; after the fix every non-root level also
    appears as a member of its parent's ``$BANK_`` and ``$BANKEYS_``
    sets.
    """

    def test_single_level_only_writes_placeholder(self):
        pipe = MagicMock()
        redis_cache._build_bank_hier("minions", pipe)
        calls = _saddargs(pipe)
        assert ("$BANK_minions", ".") in calls
        # Nothing else should be written for a top-level bank: there is
        # no parent above ``minions`` to register under.
        assert len(calls) == 1

    def test_two_levels_register_child_in_parent_bank_set(self):
        """``$BANK_minions`` must contain ``foo`` (used by flush)."""
        pipe = MagicMock()
        redis_cache._build_bank_hier("minions/foo", pipe)
        calls = _saddargs(pipe)
        assert ("$BANK_minions", "foo") in calls

    def test_two_levels_register_child_in_parent_bankkeys_set(self):
        """``$BANKEYS_minions`` must contain ``foo`` (used by list_)."""
        pipe = MagicMock()
        redis_cache._build_bank_hier("minions/foo", pipe)
        calls = _saddargs(pipe)
        assert ("$BANKEYS_minions", "foo") in calls

    def test_two_levels_placeholder_at_each_level(self):
        pipe = MagicMock()
        redis_cache._build_bank_hier("minions/foo", pipe)
        calls = _saddargs(pipe)
        assert ("$BANK_minions", ".") in calls
        assert ("$BANK_minions/foo", ".") in calls

    def test_three_levels_full_chain_registered(self):
        pipe = MagicMock()
        redis_cache._build_bank_hier("minions/host01.example.com/data", pipe)
        calls = _saddargs(pipe)

        # Placeholder at every level.
        assert ("$BANK_minions", ".") in calls
        assert ("$BANK_minions/host01.example.com", ".") in calls
        assert ("$BANK_minions/host01.example.com/data", ".") in calls

        # Each parent->child step recorded in BOTH parent indices.
        assert ("$BANK_minions", "host01.example.com") in calls
        assert ("$BANKEYS_minions", "host01.example.com") in calls
        assert ("$BANK_minions/host01.example.com", "data") in calls
        assert ("$BANKEYS_minions/host01.example.com", "data") in calls


# ---------------------------------------------------------------------------
# _get_banks_to_remove: bytes decoding and "." placeholder skipping
# ---------------------------------------------------------------------------


class TestGetBanksToRemove:
    def test_decodes_bytes_smembers_result(self):
        """
        ``redis_cache`` is not configured with ``decode_responses=True``,
        so ``smembers`` returns bytes. The recursion must decode them
        before concatenating into the path -- otherwise the next
        ``smembers`` lookup hits a corrupted key like
        ``$BANK_minions/b'foo'``.
        """
        # First call: $BANK_minions returns {b"foo"}.
        # Second call: $BANK_minions/foo returns {b"."} (only placeholder).
        smembers_results = {
            "$BANK_minions": {b"foo"},
            "$BANK_minions/foo": {b"."},
        }
        server = MagicMock()
        server.smembers.side_effect = lambda key: smembers_results.get(key, set())

        result = redis_cache._get_banks_to_remove(server, "minions")
        # Must contain the cleanly-formed path, not the bytes-corrupted
        # variant.
        assert "minions/foo" in result
        assert "minions/b'foo'" not in result

    def test_skips_dot_placeholder(self):
        """
        ``$BANK_<bank>`` always contains a ``"."`` placeholder
        (written by ``_build_bank_hier`` to mark the bank's existence).
        Recursion must not treat it as a real sub-bank, otherwise
        ``bank_paths_to_remove`` ends up polluted with phantom paths
        like ``minions/foo/.``.
        """
        smembers_results = {
            "$BANK_minions/foo": {b".", b"data"},
            "$BANK_minions/foo/data": {b"."},
        }
        server = MagicMock()
        server.smembers.side_effect = lambda key: smembers_results.get(key, set())

        result = redis_cache._get_banks_to_remove(server, "minions/foo")
        assert "minions/foo" in result
        assert "minions/foo/data" in result
        # No phantom path with a "." segment.
        assert all("/." not in path for path in result)

    def test_handles_no_children(self):
        """A leaf bank with empty smembers returns just itself."""
        server = MagicMock()
        server.smembers.return_value = set()
        result = redis_cache._get_banks_to_remove(server, "minions/foo")
        assert result == ["minions/foo"]


# ---------------------------------------------------------------------------
# flush(): remove the flushed bank's reference from its parent's indices
# ---------------------------------------------------------------------------


class TestFlushOrphanCleanup:
    """
    After ``flush("minions/foo")`` returns, ``cache.list("minions")``
    must no longer report ``foo``. Without the parent-index cleanup,
    the patched ``_build_bank_hier`` populates the parent set but
    ``flush`` never empties it again, leaving an orphan reference.
    """

    def test_flush_subbank_srems_self_from_parent_bank_set(self):
        pipe = MagicMock()
        server = MagicMock()
        server.pipeline.return_value = pipe
        # ``smembers`` returns no children; we only care about the
        # final ``srem`` calls.
        server.smembers.return_value = set()
        # ``redis_pipe.execute()`` is invoked twice in the ``key is None``
        # branch: once after the smembers gathers (returns the list of
        # subtree key-sets) and once at the very end (returns the
        # delete results). Both must yield iterables.
        pipe.execute.side_effect = [[set()], None]

        with patch.object(redis_cache, "_get_redis_server", return_value=server):
            redis_cache.flush("minions/foo")

        srem_calls = _sremargs(pipe)
        assert ("$BANK_minions", "foo") in srem_calls

    def test_flush_subbank_srems_self_from_parent_bankkeys_set(self):
        pipe = MagicMock()
        server = MagicMock()
        server.pipeline.return_value = pipe
        server.smembers.return_value = set()
        pipe.execute.side_effect = [[set()], None]

        with patch.object(redis_cache, "_get_redis_server", return_value=server):
            redis_cache.flush("minions/foo")

        srem_calls = _sremargs(pipe)
        assert ("$BANKEYS_minions", "foo") in srem_calls

    def test_flush_top_level_bank_no_parent_srems(self):
        """A top-level bank has no parent; no SREM is issued for one."""
        pipe = MagicMock()
        server = MagicMock()
        server.pipeline.return_value = pipe
        server.smembers.return_value = set()
        pipe.execute.side_effect = [[set()], None]

        with patch.object(redis_cache, "_get_redis_server", return_value=server):
            redis_cache.flush("minions")

        srem_calls = _sremargs(pipe)
        assert all(
            not call_args[0].endswith("_") for call_args in srem_calls
        ), f"unexpected parent-set SREM for a top-level bank: {srem_calls}"


# ---------------------------------------------------------------------------
# Integration: store -> list -> flush(child) -> list round-trip
# ---------------------------------------------------------------------------


class TestStoreListFlushIntegration:
    """
    Drive ``store`` and ``list_`` against a small in-memory stub of
    Redis SET semantics to prove the three fixes compose correctly:
    after two stores ``list_`` returns both children; after flushing
    one child it disappears from the parent listing.
    """

    @staticmethod
    def _make_stub_redis():
        """
        Build a small stub of Redis SET semantics that distinguishes
        between direct server operations (``server.smembers``) and
        pipelined ones (``pipe.smembers`` + ``pipe.execute``). The
        ``flush`` path in particular queues several ``smembers`` calls
        on the pipeline and reads them back from ``execute()``; a
        single shared mock would conflate the two.
        """
        sets = {}
        pipe_smembers_queue = []

        def fake_sadd(name, *values):
            sets.setdefault(name, set()).update(values)

        def fake_srem(name, *values):
            if name in sets:
                sets[name].difference_update(values)

        def fake_smembers(name):
            return {
                v.encode() if isinstance(v, str) else v for v in sets.get(name, set())
            }

        def fake_pipe_smembers(name):
            pipe_smembers_queue.append(fake_smembers(name))

        def fake_pipe_delete(*names):
            for n in names:
                sets.pop(n, None)

        def fake_pipe_execute():
            result = list(pipe_smembers_queue)
            pipe_smembers_queue.clear()
            return result

        server = MagicMock()
        pipe = MagicMock()
        server.pipeline.return_value = pipe

        # Direct (non-pipelined) ops on the server itself.
        server.sadd.side_effect = fake_sadd
        server.srem.side_effect = fake_srem
        server.smembers.side_effect = fake_smembers

        # Pipelined ops: SET writes (sadd, srem, delete, set) take
        # effect immediately on our in-memory dict; smembers is queued
        # so that ``execute()`` can return the captured results.
        pipe.sadd.side_effect = fake_sadd
        pipe.srem.side_effect = fake_srem
        pipe.smembers.side_effect = fake_pipe_smembers
        pipe.delete.side_effect = fake_pipe_delete
        pipe.set.side_effect = lambda *args, **kwargs: None
        pipe.execute.side_effect = fake_pipe_execute

        return server, pipe, sets

    def test_store_two_then_list_returns_both(self):
        server, _pipe, _sets = self._make_stub_redis()
        with patch.object(redis_cache, "_get_redis_server", return_value=server):
            redis_cache.store("minions/foo", "data", {"some": "grain"})
            redis_cache.store("minions/bar", "data", {"some": "grain"})
            result = sorted(redis_cache.list_("minions"))
        assert result == ["bar", "foo"]

    def test_store_then_flush_child_removes_from_list(self):
        """
        Headline of the parent-index orphan check: after flushing
        ``minions/foo``, ``list_("minions")`` must return only
        ``bar``, not both.
        """
        server, _pipe, _sets = self._make_stub_redis()
        with patch.object(redis_cache, "_get_redis_server", return_value=server):
            redis_cache.store("minions/foo", "data", {"some": "grain"})
            redis_cache.store("minions/bar", "data", {"some": "grain"})
            redis_cache.flush("minions/foo")
            result = sorted(redis_cache.list_("minions"))
        assert result == ["bar"], (
            f"expected only ['bar'] after flushing minions/foo; "
            f"got {result} -- parent-index orphan was not cleaned up"
        )
