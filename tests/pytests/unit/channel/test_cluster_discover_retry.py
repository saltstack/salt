"""
Unit tests for the periodic ``cluster/peer/discover`` retry scheduled by
``MasterPubServerChannel._schedule_discover_retry``.

The initial ``discover_peers`` call in ``salt.master.Master.start`` is
fire-and-forget: if the peer's pool-puller TCP listener is not yet bound
when the discover event is forwarded, the push raises ``StreamClosedError``
and the discover is lost.  Without a retry the joining master waits
forever on ``_discover_event`` and the cluster bootstrap stalls.  These
tests lock in that the retry:

* re-sends discover on the configured interval when no peer has replied,
* stops immediately once every configured peer has registered its AES key,
* stops after ``cluster_join_discover_retry_timeout`` seconds have elapsed.
"""

import tornado.ioloop

import salt.channel.server
from tests.support.mock import MagicMock, patch


def _opts(**overrides):
    opts = {
        "cluster_id": "test-cluster",
        "cluster_peers": ["peer-a", "peer-b"],
        "cluster_pool_port": 4520,
        "sock_dir": "/tmp/does-not-matter",
        "interface": "127.0.0.1",
        "publish_port": 4505,
        "cluster_join_discover_retry_interval": 2,
        "cluster_join_discover_retry_timeout": 60,
    }
    opts.update(overrides)
    return opts


class _FakeLoop:
    """Minimal io_loop stand-in that exposes ``time()``."""

    def __init__(self, start=0.0):
        self._t = start

    def time(self):
        return self._t

    def advance(self, seconds):
        self._t += seconds


def _make_channel(opts):
    """Instantiate the channel without touching disk or crypto."""
    chan = salt.channel.server.MasterPubServerChannel.__new__(
        salt.channel.server.MasterPubServerChannel
    )
    chan.opts = opts
    chan.cluster_peers = list(opts["cluster_peers"])
    chan.peer_keys = {}
    chan._discover_event = None
    chan._discover_token = None
    chan._discover_candidates = {}
    chan._discover_replies = set()
    chan._discover_retry_pc = None
    chan.io_loop = _FakeLoop()
    return chan


def test_pending_discover_peers_excludes_peers_that_replied():
    chan = _make_channel(_opts(cluster_peers=["peer-a", "peer-b", "peer-c"]))
    chan._discover_replies = {"peer-a"}
    pending = chan._pending_discover_peers()
    assert "peer-a" not in pending
    assert set(pending) == {"peer-b", "peer-c"}


def test_pending_discover_peers_is_not_cancelled_by_aes_key_arrival():
    """
    AES-key broadcast populates ``peer_keys`` independently of the
    discover protocol.  A peer that has merely sent us its AES key has
    *not* answered discover, and the retry must keep firing.
    """
    chan = _make_channel(_opts(cluster_peers=["peer-a", "peer-b"]))
    chan.peer_keys = {"peer-a": b"key-a", "peer-b": b"key-b"}
    chan._discover_replies = set()
    assert chan._pending_discover_peers() == ["peer-a", "peer-b"]


def test_pending_discover_peers_strips_port_suffix_when_matching():
    chan = _make_channel(_opts(cluster_peers=["peer-a:4520", "peer-b"]))
    # Discover-reply handler keys ``_discover_replies`` by the bare host
    # (``payload["peer_id"]``); match that against the ``host:port`` form
    # an operator may have used in ``cluster_peers``.
    chan._discover_replies = {"peer-a"}
    assert chan._pending_discover_peers() == ["peer-b"]


def test_schedule_discover_retry_resends_until_reply():
    chan = _make_channel(_opts())
    captured = []

    def _fake_discover(peers=None):
        # Grab a snapshot so later retries don't mutate the recorded list.
        captured.append(list(peers) if peers is not None else None)

    chan.discover_peers = _fake_discover

    pc = MagicMock()
    with patch.object(tornado.ioloop, "PeriodicCallback", return_value=pc) as pc_cls:
        chan._schedule_discover_retry()

    # PeriodicCallback was constructed with the configured interval.
    pc_cls.assert_called_once()
    callback = pc_cls.call_args.args[0]
    assert pc_cls.call_args.args[1] == 2000  # 2 seconds in ms
    pc.start.assert_called_once()
    assert chan._discover_retry_pc is pc

    # Fire two retry ticks with no peer having replied.
    callback()
    callback()

    assert captured == [["peer-a", "peer-b"], ["peer-a", "peer-b"]]
    pc.stop.assert_not_called()

    # Peer A replies; the next tick should only retry peer B.
    chan._discover_replies.add("peer-a")
    callback()
    assert captured[-1] == ["peer-b"]
    pc.stop.assert_not_called()

    # Peer B replies; the next tick must cancel the retry.
    chan._discover_replies.add("peer-b")
    callback()
    pc.stop.assert_called_once()
    assert chan._discover_retry_pc is None


def test_schedule_discover_retry_stops_on_timeout():
    chan = _make_channel(
        _opts(
            cluster_join_discover_retry_interval=1,
            cluster_join_discover_retry_timeout=10,
        )
    )
    chan.discover_peers = MagicMock()
    pc = MagicMock()
    with patch.object(tornado.ioloop, "PeriodicCallback", return_value=pc) as pc_cls:
        chan._schedule_discover_retry()
        callback = pc_cls.call_args.args[0]

    # No peer replies; advance beyond the timeout and tick.
    chan.io_loop.advance(11)
    callback()

    # Discover is NOT re-sent after the deadline; the retry is cancelled.
    assert chan.discover_peers.call_count == 0
    pc.stop.assert_called()
    assert chan._discover_retry_pc is None


def test_schedule_discover_retry_no_peers_is_noop():
    chan = _make_channel(_opts(cluster_peers=[]))
    with patch.object(tornado.ioloop, "PeriodicCallback") as pc_cls:
        chan._schedule_discover_retry()
    pc_cls.assert_not_called()
    assert chan._discover_retry_pc is None


def test_schedule_discover_retry_cancels_prior_instance():
    chan = _make_channel(_opts())
    prior = MagicMock()
    chan._discover_retry_pc = prior
    with patch.object(tornado.ioloop, "PeriodicCallback") as pc_cls:
        chan._schedule_discover_retry()
    prior.stop.assert_called_once()
    pc_cls.assert_called_once()
