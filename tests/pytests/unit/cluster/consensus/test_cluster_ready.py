"""
Unit tests for the cluster-readiness gate.

Covers:
- ``_cluster_is_ready`` helper function
- ``ReqServerChannel.handle_message`` defers non-_auth when not ready
- ``PoolRoutingChannel.handle_and_route_message`` defers non-_auth when not ready
"""

import asyncio
import multiprocessing

from tests.support.mock import MagicMock, patch


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

    def test_cluster_not_ready_when_entry_missing(self):
        from salt.channel.server import _cluster_is_ready

        with patch("salt.master.SMaster") as mock_smaster:
            mock_smaster.secrets = {}
            assert _cluster_is_ready({"cluster_id": "test"}) is False

    def test_cluster_not_ready_when_event_not_set(self):
        from salt.channel.server import _cluster_is_ready

        event = multiprocessing.Event()
        with patch("salt.master.SMaster") as mock_smaster:
            mock_smaster.secrets = {"cluster_ready": {"event": event}}
            assert _cluster_is_ready({"cluster_id": "test"}) is False

    def test_cluster_ready_when_event_set(self):
        from salt.channel.server import _cluster_is_ready

        event = multiprocessing.Event()
        event.set()
        with patch("salt.master.SMaster") as mock_smaster:
            mock_smaster.secrets = {"cluster_ready": {"event": event}}
            assert _cluster_is_ready({"cluster_id": "test"}) is True


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
        ch._auth = MagicMock(return_value={"publish": True})

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
