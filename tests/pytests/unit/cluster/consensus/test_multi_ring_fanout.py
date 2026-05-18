"""
Unit tests for the multi-ring runner fan-out path in
:class:`salt.channel.server.MasterPubServerChannel`.

The fan-out wraps a ``cluster/runner/ring_*`` / ``route_*`` /
``ring_set`` event payload in a cluster_aes-encrypted
``cluster/peer/multi-ring-request`` envelope and pushes it to every
peer pusher.  Each peer that receives the envelope re-dispatches via
``_handle_multi_ring_runner_event``; only the master that is the
Raft leader of the relevant group actually appends an entry.

These tests pin the wire shape — encryption, tagify, payload
round-trip — so a future refactor doesn't drift the fan-out away
from what the peer-side handler expects to decrypt.
"""

import asyncio
import collections

import pytest

import salt.crypt
import salt.master
import salt.utils.event
from salt.channel.server import MasterPubServerChannel


class _FakePusher:
    """Captures the bytes published to a peer."""

    def __init__(self, pull_host):
        self.pull_host = pull_host
        self.pull_port = 4506
        self.sent = collections.deque()

    async def publish(self, raw):
        self.sent.append(raw)


@pytest.fixture
def _seeded_cluster_aes():
    """
    Install a ``cluster_aes`` secret on ``SMaster.secrets`` so the
    fan-out can build a Crypticle, and restore the prior state after.
    """
    orig = salt.master.SMaster.secrets.copy()
    secret = salt.crypt.Crypticle.generate_key_string()

    class _Sec:
        def __init__(self, val):
            self.value = val

    salt.master.SMaster.secrets["cluster_aes"] = {"secret": _Sec(secret)}
    yield secret
    salt.master.SMaster.secrets.clear()
    salt.master.SMaster.secrets.update(orig)


def _make_channel(opts=None):
    ch = MasterPubServerChannel.__new__(MasterPubServerChannel)
    ch.opts = opts or {"id": "test-master"}
    ch.pushers = []
    return ch


def test_fanout_publishes_to_every_pusher(_seeded_cluster_aes):
    """One publish per pusher, each carrying the encrypted envelope."""
    ch = _make_channel()
    ch.pushers = [_FakePusher("127.0.0.2"), _FakePusher("127.0.0.3")]

    asyncio.run(
        ch._fanout_multi_ring_request(
            "cluster/runner/ring_create",
            {"ring_id": "jobs", "founding_voters": ["m1", "m2", "m3"]},
        )
    )

    for pusher in ch.pushers:
        assert len(pusher.sent) == 1, f"{pusher.pull_host} got {len(pusher.sent)} pubs"


def test_fanout_payload_round_trips_through_cluster_aes(_seeded_cluster_aes):
    """
    The peer-side handler decrypts with ``cluster_aes`` and reads
    ``runner_tag`` + ``data`` back out — pin that contract here.
    """
    ch = _make_channel()
    ch.pushers = [_FakePusher("127.0.0.2")]
    data = {"ring_id": "jobs", "founding_voters": ["m1", "m2", "m3"]}

    asyncio.run(ch._fanout_multi_ring_request("cluster/runner/ring_create", data))

    raw = ch.pushers[0].sent.pop()
    tag, encrypted = salt.utils.event.SaltEvent.unpack(raw)
    assert tag.endswith("cluster/peer/multi-ring-request")

    crypticle = salt.crypt.Crypticle(ch.opts, _seeded_cluster_aes)
    decoded = crypticle.loads(encrypted)
    assert decoded == {
        "runner_tag": "cluster/runner/ring_create",
        "data": data,
    }


def test_fanout_with_no_pushers_is_noop(_seeded_cluster_aes):
    """A solo master (no peers) fan-out is a clean no-op, not an error."""
    ch = _make_channel()
    ch.pushers = []

    # Should not raise.
    asyncio.run(ch._fanout_multi_ring_request("cluster/runner/route_set", {}))


def test_fanout_skips_silently_when_cluster_aes_missing():
    """
    Before the join handshake completes there's no cluster_aes secret;
    the fan-out logs and returns rather than crashing the publish loop.
    """
    orig = salt.master.SMaster.secrets.copy()
    salt.master.SMaster.secrets.pop("cluster_aes", None)
    try:
        ch = _make_channel()
        ch.pushers = [_FakePusher("127.0.0.2")]
        asyncio.run(
            ch._fanout_multi_ring_request(
                "cluster/runner/ring_create", {"ring_id": "jobs"}
            )
        )
        assert len(ch.pushers[0].sent) == 0
    finally:
        salt.master.SMaster.secrets.clear()
        salt.master.SMaster.secrets.update(orig)


def test_fanout_swallows_per_pusher_publish_errors(_seeded_cluster_aes):
    """
    A broken pusher (transport dropped) must not abort delivery to the
    other peers — they're independent links.
    """
    good = _FakePusher("127.0.0.3")

    class _BrokenPusher(_FakePusher):
        async def publish(self, raw):
            raise OSError("transport closed")

    broken = _BrokenPusher("127.0.0.2")
    ch = _make_channel()
    ch.pushers = [broken, good]

    asyncio.run(
        ch._fanout_multi_ring_request(
            "cluster/runner/route_clear", {"data_type": "jobs"}
        )
    )

    assert len(good.sent) == 1
    assert len(broken.sent) == 0
