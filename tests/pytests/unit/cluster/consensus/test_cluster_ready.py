"""
Unit tests for the cluster-readiness gate.

Covers:
- ``_cluster_is_ready`` helper function
- ``ReqServerChannel.handle_message`` defers non-_auth when not ready
- ``PoolRoutingChannel.handle_and_route_message`` defers non-_auth when not ready
"""

import asyncio
import multiprocessing

from tests.support.mock import AsyncMock, MagicMock, patch


def _run(coro):
    return asyncio.run(coro)


# ---------------------------------------------------------------------------
# _cluster_is_ready
# ---------------------------------------------------------------------------


class TestClusterIsReady:
    def test_non_cluster_always_ready(self):
        from salt.channel.server import _cluster_is_ready

        assert _cluster_is_ready({}) is True
        assert _cluster_is_ready({"cluster_id": None}) is True
        assert _cluster_is_ready({"cluster_id": ""}) is True

    def test_topology_only_master_is_ready(self):
        """
        A topology-only master sets ``cluster_id`` but no
        ``cluster_peers``.  There is no Raft readiness to wait on,
        so the gate must pass through.
        """
        from salt.channel.server import _cluster_is_ready

        assert _cluster_is_ready({"cluster_id": "east"}) is True
        assert _cluster_is_ready({"cluster_id": "east", "cluster_peers": []}) is True

    def test_cluster_not_ready_when_entry_missing(self):
        from salt.channel.server import _cluster_is_ready

        with patch("salt.master.SMaster") as mock_smaster:
            mock_smaster.secrets = {}
            opts = {"cluster_id": "test", "cluster_peers": ["127.0.0.2"]}
            assert _cluster_is_ready(opts) is False

    def test_cluster_not_ready_when_event_not_set(self):
        from salt.channel.server import _cluster_is_ready

        event = multiprocessing.Event()
        with patch("salt.master.SMaster") as mock_smaster:
            mock_smaster.secrets = {"cluster_ready": {"event": event}}
            opts = {"cluster_id": "test", "cluster_peers": ["127.0.0.2"]}
            assert _cluster_is_ready(opts) is False

    def test_cluster_ready_when_event_set(self):
        from salt.channel.server import _cluster_is_ready

        event = multiprocessing.Event()
        event.set()
        with patch("salt.master.SMaster") as mock_smaster:
            mock_smaster.secrets = {"cluster_ready": {"event": event}}
            opts = {"cluster_id": "test", "cluster_peers": ["127.0.0.2"]}
            assert _cluster_is_ready(opts) is True


# ---------------------------------------------------------------------------
# ReqServerChannel gate
# ---------------------------------------------------------------------------


def _make_req_channel(cluster_id="test-cluster", ready=False):
    """Build a minimal ReqServerChannel with mocked internals."""
    from salt.channel.server import ReqServerChannel

    opts = {
        "cluster_id": cluster_id,
        "sock_dir": "/tmp/salt",
        "cachedir": "/tmp/salt",
        "pub_server_niceness": None,
        "minimum_auth_version": 0,
        "con_cache": False,
        "master_stats": False,
        "request_server_ttl": 0,
    }
    transport = MagicMock()
    ch = ReqServerChannel.__new__(ReqServerChannel)
    ch.opts = opts
    ch.transport = transport
    ch.payload_handler = MagicMock()
    ch.sessions = {}
    ch._ready = ready
    return ch


class TestReqServerChannelGate:
    def _patched_ready(self, ready):
        return patch("salt.channel.server._cluster_is_ready", return_value=ready)

    def test_auth_passes_when_not_ready(self):
        """_auth requests are always allowed through regardless of readiness."""
        ch = _make_req_channel()
        auth_payload = {
            "enc": "clear",
            "load": {"cmd": "_auth", "id": "minion1"},
        }
        ch._decode_payload = MagicMock(return_value=auth_payload)
        # ``_auth`` is now ``async def`` (PR #70129); use AsyncMock so
        # ``await self._auth(...)`` in handle_message resolves to the
        # return value instead of raising ``TypeError: 'dict' object
        # can't be awaited``.
        ch._auth = AsyncMock(return_value={"publish": True})

        with self._patched_ready(False):
            result = _run(ch.handle_message(auth_payload))

        ch._auth.assert_called_once()
        assert result == {"publish": True}

    def test_non_auth_deferred_when_not_ready(self):
        """Non-_auth requests get a cluster_retry response when not ready."""
        ch = _make_req_channel()
        payload = {
            "enc": "aes",
            "load": b"encrypted-stuff",
            "id": "minion1",
        }
        decoded = {"enc": "aes", "load": {"cmd": "publish", "id": "minion1"}}
        ch._decode_payload = MagicMock(return_value=decoded)

        with self._patched_ready(False):
            result = _run(ch.handle_message(payload))

        assert result == {
            "enc": "clear",
            "load": {"ret": False, "cluster_retry": True},
        }
        ch.payload_handler.assert_not_called()

    def test_non_auth_passes_when_ready(self):
        """Non-_auth requests are forwarded to payload_handler when ready."""
        ch = _make_req_channel()
        payload = {
            "enc": "aes",
            "load": b"encrypted-stuff",
            "id": "minion1",
        }
        decoded = {"enc": "aes", "load": {"cmd": "publish", "id": "minion1"}}
        ch._decode_payload = MagicMock(return_value=decoded)

        async def fake_handler(p):
            return {"ret": True}, {}

        ch.payload_handler = fake_handler

        with self._patched_ready(True):
            result = _run(ch.handle_message(payload))

        assert result is not None

    def test_non_cluster_always_passes(self):
        """Masters with no cluster_id never gate traffic."""
        ch = _make_req_channel(cluster_id=None)
        payload = {
            "enc": "aes",
            "load": b"encrypted-stuff",
            "id": "minion1",
        }
        decoded = {"enc": "aes", "load": {"cmd": "publish", "id": "minion1"}}
        ch._decode_payload = MagicMock(return_value=decoded)

        async def fake_handler(p):
            return {"ret": True}, {}

        ch.payload_handler = fake_handler

        # _cluster_is_ready returns True for non-cluster masters, no patch needed
        result = _run(ch.handle_message(payload))
        assert result is not None


# ---------------------------------------------------------------------------
# PoolRoutingChannel gate
# ---------------------------------------------------------------------------


class TestPoolRoutingChannelGate:
    def _patched_ready(self, ready):
        return patch("salt.channel.server._cluster_is_ready", return_value=ready)

    def _make_pool_channel(self, cluster_id="test-cluster"):
        from salt.channel.server import PoolRoutingChannel

        opts = {
            "cluster_id": cluster_id,
            "sock_dir": "/tmp/salt",
            "cachedir": "/tmp/salt",
            "minimum_auth_version": 0,
            "con_cache": False,
        }
        transport = MagicMock()
        ch = PoolRoutingChannel.__new__(PoolRoutingChannel)
        ch.opts = opts
        ch.transport = transport
        ch.worker_pools = {"default": {}}
        ch.pool_clients = {}
        ch.pool_servers = {}
        ch.command_to_pool = {}
        ch.default_pool = "default"
        ch.sessions = {}
        ch.crypticle = None
        ch.master_key = None
        ch.auto_key = None
        ch.io_loop = None
        ch.event = None
        ch.router = None
        return ch

    def test_auth_passes_when_not_ready(self):
        """_auth bypasses the cluster-ready gate in PoolRoutingChannel."""
        ch = self._make_pool_channel()
        auth_payload = {
            "enc": "clear",
            "load": {"cmd": "_auth", "id": "minion1"},
        }

        async def fake_auth(payload, version):
            return {"publish": True}

        ch._handle_clear_auth_local = fake_auth

        with self._patched_ready(False):
            result = _run(ch.handle_and_route_message(auth_payload))

        assert result == {"publish": True}

    def test_non_auth_deferred_when_not_ready(self):
        """Non-_auth commands get cluster_retry when the gate is closed."""
        ch = self._make_pool_channel()
        payload = {
            "enc": "clear",
            "load": {"cmd": "publish", "id": "minion1"},
        }

        with self._patched_ready(False):
            result = _run(ch.handle_and_route_message(payload))

        assert result == {
            "enc": "clear",
            "load": {"ret": False, "cluster_retry": True},
        }

    def test_non_cluster_not_gated(self):
        """PoolRoutingChannel with no cluster_id is never gated."""
        ch = self._make_pool_channel(cluster_id=None)
        payload = {
            "enc": "clear",
            "load": {"cmd": "publish", "id": "minion1"},
        }
        # No pool_clients, so it falls to "No client" error — but NOT cluster_retry
        with self._patched_ready(True):
            result = _run(ch.handle_and_route_message(payload))

        # Should get the "no client" error, not cluster_retry
        assert result != {"enc": "clear", "load": {"ret": False, "cluster_retry": True}}


# ---------------------------------------------------------------------------
# RaftService readiness persistence across restarts (BUG-024 regression)
# ---------------------------------------------------------------------------


class TestRaftServiceReadinessSticky:
    """
    Regression: after a RaftService restart (master process restart, not a
    simple re-election), the readiness gate must re-open from the on-disk
    Raft log even if no new CONFIG entry commits in the new leader's term.

    Raft §5.4 forbids a new leader from committing entries written in prior
    terms via ``advance_commit_index``; without seeding ``membership_sm``
    from the persisted log, ``_on_membership_change`` never fires and the
    ``cluster_ready`` Event stays unset forever, latching every publish
    through the ``cluster_retry`` sentinel.
    """

    def _build_opts(self, tmp_path, my_addr="192.168.0.1"):
        import salt.config

        opts = salt.config.master_config("/dev/null")
        opts["interface"] = my_addr
        opts["cluster_id"] = "west"
        opts["cluster_peers"] = ["192.168.0.2", "192.168.0.3"]
        opts["cluster_pool_port"] = 55596
        opts["cachedir"] = str(tmp_path)
        return opts

    def test_on_ready_fires_from_persisted_config_entry(self, tmp_path):
        """
        Pre-seed the on-disk Raft log with a CONFIG entry listing this
        node as a voter, then construct a fresh RaftService.  The
        ``on_ready`` callback must fire without any AppendEntries
        arriving — the gate re-opens from disk.
        """
        import asyncio

        from salt.cluster.consensus.raft.log import LogEntry, LogEntryType
        from salt.cluster.consensus.service import RaftService
        from salt.cluster.consensus.storage import SaltStorage

        opts = self._build_opts(tmp_path)
        my_addr = opts["interface"]

        # Pre-seed storage with a committed-shape CONFIG entry.
        storage = SaltStorage(my_addr, opts)
        config_entry = LogEntry(
            term=1,
            index=0,
            cmd={
                "voters": [my_addr, "192.168.0.2", "192.168.0.3"],
                "learners": [],
                "protocol_versions": {},
            },
            node_id=None,
            type=LogEntryType.CONFIG,
        )
        storage.append_log(config_entry)

        on_ready = MagicMock()
        loop = asyncio.new_event_loop()
        try:
            peer_pushers = {
                "192.168.0.2": MagicMock(),
                "192.168.0.3": MagicMock(),
            }
            svc = RaftService(opts, loop, peer_pushers, on_ready=on_ready)
            assert svc is not None
        finally:
            loop.close()

        on_ready.assert_called_once()

    def test_no_fire_when_not_in_voter_set(self, tmp_path):
        """
        A CONFIG entry that does NOT list this node must not fire
        ``on_ready`` — the master is still pre-join.
        """
        import asyncio

        from salt.cluster.consensus.raft.log import LogEntry, LogEntryType
        from salt.cluster.consensus.service import RaftService
        from salt.cluster.consensus.storage import SaltStorage

        opts = self._build_opts(tmp_path)
        my_addr = opts["interface"]

        storage = SaltStorage(my_addr, opts)
        config_entry = LogEntry(
            term=1,
            index=0,
            cmd={
                "voters": ["192.168.0.2", "192.168.0.3"],
                "learners": [],
                "protocol_versions": {},
            },
            node_id=None,
            type=LogEntryType.CONFIG,
        )
        storage.append_log(config_entry)

        on_ready = MagicMock()
        loop = asyncio.new_event_loop()
        try:
            peer_pushers = {
                "192.168.0.2": MagicMock(),
                "192.168.0.3": MagicMock(),
            }
            RaftService(opts, loop, peer_pushers, on_ready=on_ready)
        finally:
            loop.close()

        on_ready.assert_not_called()

    def test_fresh_node_no_log_does_not_fire(self, tmp_path):
        """
        A fresh RaftService with no log entries must not fire
        ``on_ready`` — the gate only opens after real consensus.
        """
        import asyncio

        from salt.cluster.consensus.service import RaftService

        opts = self._build_opts(tmp_path)

        on_ready = MagicMock()
        loop = asyncio.new_event_loop()
        try:
            peer_pushers = {
                "192.168.0.2": MagicMock(),
                "192.168.0.3": MagicMock(),
            }
            RaftService(opts, loop, peer_pushers, on_ready=on_ready)
        finally:
            loop.close()

        on_ready.assert_not_called()

    def test_latest_config_wins_when_multiple_in_log(self, tmp_path):
        """
        If the log contains several CONFIG entries (membership churn),
        the seed must apply the LAST one — dropping a node that has
        since left the voter set should not re-fire readiness for it.
        """
        import asyncio

        from salt.cluster.consensus.raft.log import LogEntry, LogEntryType
        from salt.cluster.consensus.service import RaftService
        from salt.cluster.consensus.storage import SaltStorage

        opts = self._build_opts(tmp_path)
        my_addr = opts["interface"]

        storage = SaltStorage(my_addr, opts)
        # Earlier entry: we WERE a voter.
        storage.append_log(
            LogEntry(
                term=1,
                index=0,
                cmd={
                    "voters": [my_addr, "192.168.0.2", "192.168.0.3"],
                    "learners": [],
                    "protocol_versions": {},
                },
                node_id=None,
                type=LogEntryType.CONFIG,
            )
        )
        # Later entry: we were DEMOTED / removed.
        storage.append_log(
            LogEntry(
                term=2,
                index=1,
                cmd={
                    "voters": ["192.168.0.2", "192.168.0.3"],
                    "learners": [],
                    "protocol_versions": {},
                },
                node_id=None,
                type=LogEntryType.CONFIG,
            )
        )

        on_ready = MagicMock()
        loop = asyncio.new_event_loop()
        try:
            peer_pushers = {
                "192.168.0.2": MagicMock(),
                "192.168.0.3": MagicMock(),
            }
            RaftService(opts, loop, peer_pushers, on_ready=on_ready)
        finally:
            loop.close()

        on_ready.assert_not_called()
