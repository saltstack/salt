"""
Stress + regression tests for the salt-master ``EventPublisher`` (EP)
subprocess in isolation.

See ``conftest.py`` for the design rationale (spawn EP as a real
multiprocessing subprocess through ``ProcessManager.add_process`` so the
production fork path is exercised, and RSS / FD probes see a distinct
PID).

Every test:

* Talks to EP over its real UNIX-domain-socket ``pull`` / ``pub``
  channels — the fake senders / subscribers do **not** stub the wire
  protocol.
* Avoids ``time.sleep(N)``.  Instead we deadline-poll for the event we
  care about, or we monkeypatch a config knob (``publish_drain_timeout``)
  down to the smallest number of ms that still hits the code we want to
  exercise.
* Terminates the EP subprocess on teardown.  If a test wedges EP the
  fixture will still recover by ``SIGKILL``-ing the child.

Categories covered:

1. Throughput floor.
2. Multi-subscriber fan-out.
3. Backpressure — slow subscriber gets discarded, others keep flowing.
4. Fault injection — subscriber RST, malformed pull frame, subscriber
   writes to pub socket.
5. Peer-churn FD / RSS stability.
"""

from __future__ import annotations

import errno
import socket
import struct
import time

import pytest

import salt.transport.frame
import salt.transport.tcp
import salt.utils.msgpack
import salt.utils.platform

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _pack_pull_frame(body) -> bytes:
    """
    Frame a payload the way ``salt.transport.frame.frame_msg_ipc`` does
    for the pull socket.  The receiver (``TCPPuller.handle_stream``)
    reads the 4-byte big-endian length prefix, then that many bytes of
    msgpack.
    """
    return salt.transport.frame.frame_msg_ipc(body, raw_body=True)


def _make_event(tag: str, payload: dict) -> bytes:
    """
    Build an event payload shaped like production traffic: ``tag`` +
    ``TAGEND`` sentinel + msgpack of ``payload``.  ``MasterPubServerChannel.publish_payload``
    ``SaltEvent.unpack``s this on the way in.
    """
    import salt.utils.event

    return salt.utils.event.SaltEvent.pack(tag, payload)


class _SyncPuller:
    """
    Minimal synchronous UNIX-socket client for the pull side.  We use
    plain blocking sockets so a test running in a thread can bang out
    events at kernel speed without an ioloop.
    """

    def __init__(self, path: str):
        self.path = path
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        # Larger send buffer helps burst throughput on tests that push
        # thousands of frames; not required for correctness.
        try:
            self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 1 << 20)
        except OSError:
            pass
        self.sock.connect(path)

    def send(self, body) -> None:
        self.sock.sendall(_pack_pull_frame(body))

    def send_raw(self, blob: bytes) -> None:
        self.sock.sendall(blob)

    def close(self) -> None:
        try:
            self.sock.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass
        try:
            self.sock.close()
        except OSError:
            pass


class _SyncSubscriber:
    """
    Blocking UNIX-socket subscriber for the pub side.  Reads
    length-prefixed msgpack frames as they arrive from
    ``PubServer._stream_read`` — actually no, wait: ``PubServer`` writes
    frames via ``salt.transport.frame.frame_msg`` which is a *plain*
    msgpack blob, no length prefix.  So we feed the raw bytes through a
    streaming ``msgpack.Unpacker``.
    """

    def __init__(self, path: str, rcvbuf: int | None = None):
        self.path = path
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        if rcvbuf is not None:
            try:
                self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, rcvbuf)
            except OSError:
                pass
        self.sock.connect(path)
        self.unpacker = salt.utils.msgpack.Unpacker(raw=False)

    def recv_one(self, timeout: float = 5.0):
        """
        Return the next framed message body, or raise ``TimeoutError``.
        """
        deadline = time.monotonic() + timeout
        # Fast path: something already buffered.
        for msg in self.unpacker:
            return msg["body"]
        while time.monotonic() < deadline:
            remaining = deadline - time.monotonic()
            self.sock.settimeout(max(0.05, remaining))
            try:
                chunk = self.sock.recv(65536)
            except TimeoutError:
                continue
            except OSError as exc:
                if exc.errno in (errno.EBADF, errno.ECONNRESET):
                    raise
                continue
            if not chunk:
                raise ConnectionResetError("EP pub socket closed")
            self.unpacker.feed(chunk)
            for msg in self.unpacker:
                return msg["body"]
        raise TimeoutError(f"no message on {self.path} within {timeout}s")

    def drain(self, n: int, timeout: float = 30.0) -> list:
        """
        Read exactly *n* frames.  Raises TimeoutError if EP delivered
        fewer within the deadline.
        """
        out = []
        deadline = time.monotonic() + timeout
        while len(out) < n:
            remaining = max(0.0, deadline - time.monotonic())
            if remaining == 0:
                raise TimeoutError(
                    f"only received {len(out)}/{n} messages within {timeout}s"
                )
            out.append(self.recv_one(timeout=remaining))
        return out

    def close(self) -> None:
        try:
            self.sock.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass
        try:
            self.sock.close()
        except OSError:
            pass


def _connect_subscriber(path: str, timeout: float = 5.0, **kwargs) -> _SyncSubscriber:
    """
    Retry-connect until EP accepts.  Handles the race where EP's
    ``PubServer.add_socket`` hasn't fired ``handle_stream`` yet.
    """
    deadline = time.monotonic() + timeout
    last_exc = None
    while time.monotonic() < deadline:
        try:
            return _SyncSubscriber(path, **kwargs)
        except OSError as exc:
            last_exc = exc
            time.sleep(0.02)
    raise RuntimeError(f"could not connect subscriber to {path}: {last_exc!r}")


def _wait_for(condition, timeout: float = 10.0, interval: float = 0.02) -> bool:
    """
    Poll *condition* (zero-arg callable returning truthy) until true or
    timeout.  Returns whether it went true.
    """
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if condition():
            return True
        time.sleep(interval)
    return False


# ---------------------------------------------------------------------------
# 1. Throughput floor
# ---------------------------------------------------------------------------


@pytest.mark.timeout(60)
def test_throughput_floor_single_subscriber(ep):
    """
    Fire N events at EP as fast as a single blocking sender can push
    frames; a single subscriber must receive every event with no
    duplication and no reordering, and the effective rate must clear a
    conservative floor.

    The floor is intentionally low (500 events / sec) — the point is to
    catch a regression that pins EP throughput at, say, 10 evt/s (the
    kind of pathological drop the 3006.x → 3008.x
    ``create_task``-per-frame bug caused), not to benchmark.
    """
    n = 5000
    tag_prefix = "stress/ep/throughput/"

    sub = _connect_subscriber(ep.pub_path)
    # Slight settle so EP has definitely registered the subscriber.
    assert _wait_for(ep.is_alive, timeout=2.0)

    puller = _SyncPuller(ep.pull_path)
    t0 = time.monotonic()
    for i in range(n):
        puller.send(_make_event(f"{tag_prefix}{i}", {"idx": i}))
    send_elapsed = time.monotonic() - t0

    received = sub.drain(n, timeout=45.0)
    total_elapsed = time.monotonic() - t0
    rate = n / total_elapsed

    puller.close()
    sub.close()

    assert ep.is_alive(), "EP died under throughput load"

    # Correctness — same count, in order, no gaps.  Payloads are the
    # raw ``load`` bytes: ``tag TAGEND msgpack(payload)``.
    idxs = []
    for msg in received:
        # ``msg`` is the ``body`` value; ``publish_payload`` on the pull
        # side receives what the sender sent, which is a ``bytes``
        # ``SaltEvent.pack(...)``.
        assert isinstance(msg, (bytes, bytearray, str))
        raw = msg.encode() if isinstance(msg, str) else bytes(msg)
        _tag_bytes, _sep, mdata = raw.partition(b"\n\n")
        payload = salt.utils.msgpack.unpackb(mdata, raw=False)
        idxs.append(payload["idx"])
    assert idxs == list(range(n)), "events out of order or gaps present"

    assert rate >= 500, (
        f"EP throughput {rate:.1f} evt/s below floor 500 evt/s "
        f"(send={send_elapsed:.2f}s total={total_elapsed:.2f}s)"
    )


# ---------------------------------------------------------------------------
# 2. Multiple subscribers — every subscriber gets every event in order
# ---------------------------------------------------------------------------


@pytest.mark.timeout(60)
def test_multi_subscriber_fanout(ep):
    """
    Attach K subscribers, fire N events, assert each subscriber received
    exactly N events in order.
    """
    k = 5
    n = 1000
    subs = [_connect_subscriber(ep.pub_path) for _ in range(k)]

    puller = _SyncPuller(ep.pull_path)
    for i in range(n):
        puller.send(_make_event(f"stress/ep/fanout/{i}", {"idx": i}))

    # Read all subs in parallel-ish (serial is fine because each recv is
    # bounded by the deadline).
    per_sub_idxs: list[list[int]] = []
    for sub in subs:
        got = sub.drain(n, timeout=30.0)
        idxs = []
        for msg in got:
            raw = msg.encode() if isinstance(msg, str) else bytes(msg)
            _tag_bytes, _sep, mdata = raw.partition(b"\n\n")
            payload = salt.utils.msgpack.unpackb(mdata, raw=False)
            idxs.append(payload["idx"])
        per_sub_idxs.append(idxs)

    puller.close()
    for sub in subs:
        sub.close()

    assert ep.is_alive()
    for i, idxs in enumerate(per_sub_idxs):
        assert idxs == list(range(n)), f"subscriber {i} out of order / missing"


# ---------------------------------------------------------------------------
# 3. Backpressure — slow subscriber
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "ep_opts_overrides",
    # Bring the drain timeout way down so the test finishes fast, and
    # cap the per-stream write buffer so the "slow" subscriber actually
    # blocks EP's write future (the code path we're validating).
    [
        {
            "publish_drain_timeout": 0.5,
            "ipc_write_buffer": 64 * 1024,
        }
    ],
    indirect=True,
)
@pytest.mark.timeout(120)
def test_slow_subscriber_does_not_block_fast_subscriber(ep):
    """
    Regression for the pre-#66282 / pre-fire-and-forget-drain wedge:
    with the OLD serial-await ``publish_payload`` loop, a single slow
    subscriber blocks the entire broadcast loop -- every subsequent
    ``await stream.write(...)`` for the fast subscriber serialises
    behind the slow one's stuck write, so the fast subscriber sees
    events only after each drain_timeout expires (per event).  With
    the fix, drains fire-and-forget: the fast subscriber gets events
    immediately regardless of the slow subscriber's state.

    We can't reliably observe EP's client set from outside (short of
    log parsing in the subprocess), and Linux UNIX-loopback socket
    buffers auto-tune large enough that forcing the kernel buffer to
    fill within a test's runtime is fragile.  The behaviour we CAN
    pin here is the one that would regress the production wedge:
    fast subscriber must receive N events in bounded wall time even
    with a peer subscriber that never reads a byte.
    """
    n = 500
    filler = b"x" * 4096  # keep the burst modest so the test is fast

    # Slow subscriber: connect but never recv.  Its recv-buffer + EP's
    # per-stream write buffer will eventually saturate; the write
    # future to it will stop resolving; the drain task will time out
    # after 0.5s and (in prod) close the client.  Whether EP actually
    # closes it or not is not this test's concern.
    slow = _connect_subscriber(ep.pub_path, rcvbuf=4096)
    fast = _connect_subscriber(ep.pub_path)

    puller = _SyncPuller(ep.pull_path)
    t0 = time.monotonic()
    for i in range(n):
        puller.send(_make_event(f"stress/ep/slow/{i}", {"idx": i, "pad": filler}))
    send_elapsed = time.monotonic() - t0

    # Fast subscriber must drain within ~ (n / floor_rate) — well
    # under the "n * drain_timeout" ceiling a serial-await bug would
    # produce (which would be 500 * 0.5 = 250 s here).
    got = fast.drain(n, timeout=30.0)
    fan_elapsed = time.monotonic() - t0

    puller.close()
    slow.close()
    fast.close()

    assert len(got) == n
    assert ep.is_alive(), "EP crashed under slow-subscriber load"
    # If we ever spend > ~10s draining n=500 events, something's very
    # wrong — production runs at ~1000+ evt/s on this size.
    assert fan_elapsed < 10.0, (
        f"fast subscriber took {fan_elapsed:.1f}s for {n} events "
        f"(send phase alone was {send_elapsed:.2f}s); slow subscriber "
        "appears to be blocking the fast one — publish_payload serial "
        "await regression?"
    )


# ---------------------------------------------------------------------------
# 4. Fault injection
# ---------------------------------------------------------------------------


@pytest.mark.timeout(30)
def test_subscriber_rst_mid_stream_does_not_hang_ep(ep):
    """
    A subscriber connects, receives a few events, then hard-closes
    (RST via SO_LINGER=0).  EP must:

    * not hang on the next publish (drain future to the dead socket
      resolves via ``StreamClosedError`` / socket error);
    * remove the client from ``self.clients``;
    * keep serving other subscribers.
    """
    stable = _connect_subscriber(ep.pub_path)

    # Killer subscriber: SO_LINGER=0 forces RST on close.
    killer_sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    killer_sock.setsockopt(socket.SOL_SOCKET, socket.SO_LINGER, struct.pack("ii", 1, 0))
    killer_sock.connect(ep.pub_path)

    puller = _SyncPuller(ep.pull_path)
    # Warm-up burst — everyone gets some events.
    for i in range(50):
        puller.send(_make_event(f"stress/ep/rst/warmup/{i}", {"idx": i}))

    # Kill.
    try:
        killer_sock.close()
    except OSError:
        pass

    # Post-kill burst.  ``stable`` must receive all 50 of these.
    for i in range(50, 100):
        puller.send(_make_event(f"stress/ep/rst/post/{i}", {"idx": i}))

    got = stable.drain(100, timeout=20.0)
    assert len(got) == 100

    puller.close()
    stable.close()
    assert ep.is_alive(), "EP died after subscriber RST"


@pytest.mark.timeout(30)
def test_malformed_pull_frame_does_not_kill_ep(ep):
    """
    Push a garbage frame at the pull socket.  ``TCPPuller.handle_stream``
    catches per-stream exceptions but a bad length prefix that claims,
    say, 4 GiB is a hazard — EP must not OOM or crash.  A valid frame
    that follows the bad one on a fresh connection must still be
    delivered.
    """
    sub = _connect_subscriber(ep.pub_path)

    # Bad frame: 4-byte length prefix of ~1 GiB followed by nothing.
    # ``handle_stream`` will do ``read_bytes(length)`` and block; when
    # the socket closes, ``StreamClosedError`` breaks out of the loop.
    # EP itself must remain alive.
    bad = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    bad.connect(ep.pull_path)
    bad.sendall(struct.pack(">I", 1 << 30))  # claim 1 GiB
    bad.sendall(b"\x00" * 16)  # then send nothing meaningful
    bad.close()

    # Second bad frame: valid length prefix, garbage msgpack.  This
    # exercises the ``payload_handler`` exception path.
    bad2 = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    bad2.connect(ep.pull_path)
    junk = b"\xff\xff\xff\xff\xff\xff"  # not valid msgpack
    bad2.sendall(struct.pack(">I", len(junk)) + junk)
    bad2.close()

    # Good frame on a fresh connection — must be delivered.
    good = _SyncPuller(ep.pull_path)
    good.send(_make_event("stress/ep/after_bad", {"idx": 42}))
    msg = sub.recv_one(timeout=10.0)

    raw = msg.encode() if isinstance(msg, str) else bytes(msg)
    _tag, _sep, mdata = raw.partition(b"\n\n")
    payload = salt.utils.msgpack.unpackb(mdata, raw=False)
    assert payload["idx"] == 42

    good.close()
    sub.close()
    assert ep.is_alive(), "EP died on malformed pull frame"


@pytest.mark.timeout(30)
def test_subscriber_writes_to_pub_socket_do_not_kill_ep(ep):
    """
    The pub socket is a fan-out; a well-behaved subscriber only reads.
    A misbehaved subscriber that sends bytes exercises
    ``PubServer._stream_read`` — which *does* feed the bytes into a
    ``msgpack.Unpacker`` and invoke ``presence_callback`` per parsed
    frame.  With the default presence callback (identity) this should be
    a no-op.  Send garbage and then valid msgpack; EP must survive and
    continue delivering to a well-behaved subscriber.
    """
    good_sub = _connect_subscriber(ep.pub_path)

    misbehaved = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    misbehaved.connect(ep.pub_path)
    # 1) unstructured garbage.
    misbehaved.sendall(b"\xff\xfe\xfd\xfc" * 8)
    # 2) valid framed msgpack that isn't shaped like an event.  This is
    # a dict-shaped frame with only a ``body`` key so ``framed_msg["body"]``
    # in ``_stream_read`` succeeds.
    frame = salt.utils.msgpack.dumps({"body": {"hello": "world"}}, use_bin_type=True)
    misbehaved.sendall(frame)
    misbehaved.close()

    # EP must still be able to publish.
    puller = _SyncPuller(ep.pull_path)
    puller.send(_make_event("stress/ep/after_misbehaved", {"idx": 7}))
    msg = good_sub.recv_one(timeout=5.0)
    raw = msg.encode() if isinstance(msg, str) else bytes(msg)
    _tag, _sep, mdata = raw.partition(b"\n\n")
    payload = salt.utils.msgpack.unpackb(mdata, raw=False)
    assert payload["idx"] == 7

    puller.close()
    good_sub.close()
    assert ep.is_alive()


# ---------------------------------------------------------------------------
# 5. Peer churn — FD / RSS stability
# ---------------------------------------------------------------------------


@pytest.mark.timeout(60)
def test_subscriber_churn_no_fd_leak(ep):
    """
    Churn N subscribers through connect + disconnect.  EP's FD count
    must return to (approximately) baseline afterwards — no leak.

    Regression target: the 3008.x accumulator described in
    ``PubServer._discard_on_close`` docstring.  Without the close
    callback, each closed subscriber sits in ``self.clients`` and pins
    its ``IOStream`` + FD until the next publish tries to write to it.
    """
    # Warm-up publish so all machinery is fully wired.
    warmup_sub = _connect_subscriber(ep.pub_path)
    puller = _SyncPuller(ep.pull_path)
    puller.send(_make_event("stress/ep/warmup", {"i": 0}))
    warmup_sub.recv_one(timeout=5.0)
    warmup_sub.close()
    puller.close()

    # Give EP a beat to fully release the warmup client.  This is a
    # brief, bounded wait -- not a "sleep and hope".
    time.sleep(0.1)

    baseline_fds = ep.fd_count()
    baseline_rss = ep.rss_bytes()
    assert baseline_fds > 0, "could not read /proc — Linux-only test"

    churn_n = 100
    for _ in range(churn_n):
        s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        s.connect(ep.pub_path)
        # Send one tiny publish through so EP's ``handle_stream`` fires
        # + ``set_close_callback`` runs on close.
        s.close()

    # Trigger a publish so EP walks its client list — this used to be
    # the only chance stale entries had to be discovered pre-fix.
    puller = _SyncPuller(ep.pull_path)
    for i in range(5):
        puller.send(_make_event(f"stress/ep/post_churn/{i}", {"i": i}))
    puller.close()

    # Wait for FD count to settle.  ``_discard_on_close`` runs via the
    # IOLoop; give it up to 5s.
    def _stable():
        return ep.fd_count() <= baseline_fds + 3

    ok = _wait_for(_stable, timeout=10.0)
    fds_after = ep.fd_count()
    rss_after = ep.rss_bytes()

    assert ep.is_alive()
    assert ok, (
        f"EP FDs did not settle after churn: "
        f"baseline={baseline_fds}, after={fds_after} "
        f"(expected <= baseline+3)"
    )
    # RSS: allow generous growth (Python's allocator doesn't return heap
    # to the OS aggressively).  Just guard against a runaway leak.
    #
    # aarch64 note: glibc's per-thread malloc arenas on aarch64 default
    # to 64 MiB each, and tornado's IOLoop / accept threads plus msgpack
    # temporaries can pin one or two extra arenas after churn.  We've
    # observed 88-102 MiB one-shot expansion on Photon OS 5 Arm64 that
    # does not compound across repeat churn rounds (i.e. it is cached
    # allocator state, not a real leak).  x86_64 glibc has different
    # arena sizing and stays flat.  Widen the ceiling on aarch64 so this
    # canary catches actual runaway leaks without flagging arena caching.
    rss_growth = rss_after - baseline_rss
    max_growth = (
        200 * 1024 * 1024 if salt.utils.platform.is_aarch64() else 50 * 1024 * 1024
    )
    assert rss_growth < max_growth, (
        f"EP RSS grew {rss_growth / 1024 / 1024:.1f} MiB after {churn_n}-sub "
        f"churn — possible leak (ceiling {max_growth / 1024 / 1024:.0f} MiB)"
    )
