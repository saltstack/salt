"""
Peer helpers for pubchannel stress tests.

These wrap the low-level details of pushing payloads into the publisher's
pull socket and pulling payloads out of its pub socket, for each transport
supported by ``PublishServer``.

Everything here is synchronous or lightweight-async so tests stay
deterministic (no time.sleep-and-hope on real socket state).
"""

from __future__ import annotations

import selectors
import socket
import struct
import threading
import time

import zmq

import salt.utils.msgpack

# ---------------------------------------------------------------------------
# TCP pusher and subscriber
# ---------------------------------------------------------------------------


def tcp_frame(body: bytes) -> bytes:
    """Frame a body the way ``salt.transport.frame.frame_msg_ipc`` does."""
    packed = salt.utils.msgpack.packb({"head": {}, "body": body}, use_bin_type=True)
    return struct.pack(">I", len(packed)) + packed


class TCPPusher:
    """
    Push framed payloads into the publisher's pull socket.
    Blocks on ``send`` — the test is expected to drive load explicitly.
    """

    def __init__(self, host: str, port: int, timeout: float = 5.0):
        self.host = host
        self.port = port
        self.timeout = timeout
        self._sock: socket.socket | None = None

    def connect(self) -> None:
        self._sock = socket.create_connection(
            (self.host, self.port), timeout=self.timeout
        )
        self._sock.settimeout(self.timeout)

    def send(self, body: bytes) -> None:
        assert self._sock is not None, "call connect() first"
        self._sock.sendall(tcp_frame(body))

    def close(self) -> None:
        if self._sock is not None:
            try:
                self._sock.close()
            finally:
                self._sock = None

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


class TCPSubscriber:
    """
    Fake TCP SUB.  Connects to the publisher's pub socket, reads at most
    ``max_recv_bytes`` per drain cycle, and unpacks msgpack frames the
    publisher wrote via ``PubServer.publish_payload``.

    Setting ``read_delay`` > 0 introduces a per-read pause so the socket
    receive buffer fills and the publisher-side write buffer grows,
    triggering the slow-subscriber drop path.

    Setting ``read_delay = None`` (or calling ``stop_reading``) keeps the
    peer connected without ever reading, which is the worst-case slow SUB.
    """

    def __init__(
        self,
        host: str,
        port: int,
        *,
        read_delay: float = 0.0,
        connect_timeout: float = 5.0,
        recv_buf: int = 8192,
        so_rcvbuf: int | None = None,
    ):
        self.host = host
        self.port = port
        self.read_delay = read_delay
        self.connect_timeout = connect_timeout
        self.recv_buf = recv_buf
        self.so_rcvbuf = so_rcvbuf
        self._sock: socket.socket | None = None
        self._unpacker = salt.utils.msgpack.Unpacker(raw=False)
        self._reader_thread: threading.Thread | None = None
        self._stop = threading.Event()
        self._reading = False
        self.frames: list[dict] = []
        self.recv_error: BaseException | None = None
        self.raw_bytes_received: int = 0
        self.closed_by_peer: bool = False

    # ------------------------------------------------------------------
    # lifecycle
    # ------------------------------------------------------------------

    def connect(self) -> None:
        self._sock = socket.create_connection(
            (self.host, self.port), timeout=self.connect_timeout
        )
        if self.so_rcvbuf is not None:
            self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, self.so_rcvbuf)
        self._sock.setblocking(False)

    def start_reader(self) -> None:
        assert self._sock is not None, "call connect() first"
        self._reading = True
        self._reader_thread = threading.Thread(
            target=self._reader_loop, name=f"tcp-sub-{self.port}", daemon=True
        )
        self._reader_thread.start()

    def stop_reading(self) -> None:
        """Stop draining but keep the socket open."""
        self._reading = False
        if self._reader_thread is not None:
            self._stop.set()
            self._reader_thread.join(timeout=2.0)
            self._reader_thread = None
            self._stop.clear()

    def close(self) -> None:
        self._reading = False
        self._stop.set()
        if self._reader_thread is not None:
            self._reader_thread.join(timeout=2.0)
            self._reader_thread = None
        if self._sock is not None:
            try:
                self._sock.close()
            finally:
                self._sock = None

    def __enter__(self):
        self.connect()
        self.start_reader()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    # ------------------------------------------------------------------
    # reader loop
    # ------------------------------------------------------------------

    def _reader_loop(self) -> None:
        sel = selectors.DefaultSelector()
        sock = self._sock
        assert sock is not None
        sel.register(sock, selectors.EVENT_READ)
        try:
            while not self._stop.is_set():
                events = sel.select(timeout=0.1)
                if not events:
                    continue
                try:
                    chunk = sock.recv(self.recv_buf)
                except BlockingIOError:
                    continue
                except OSError as exc:
                    self.recv_error = exc
                    self.closed_by_peer = True
                    break
                if not chunk:
                    # Peer half-closed the connection.
                    self.closed_by_peer = True
                    break
                self.raw_bytes_received += len(chunk)
                self._unpacker.feed(chunk)
                for frame in self._unpacker:
                    self.frames.append(frame)
                if self.read_delay:
                    time.sleep(self.read_delay)
        finally:
            try:
                sel.unregister(sock)
            except Exception:  # pylint: disable=broad-except
                pass

    # ------------------------------------------------------------------
    # probes tests use
    # ------------------------------------------------------------------

    def wait_for_frames(self, n: int, timeout: float = 5.0) -> bool:
        """Return True when we have >= ``n`` frames or timeout."""
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if len(self.frames) >= n:
                return True
            time.sleep(0.02)
        return len(self.frames) >= n

    def socket_thinks_connected(self) -> bool:
        """
        Best-effort check: from the SUB side, does the socket look alive?

        This is the crucial "is the subscriber told it was dropped?" probe.
        In the production bug, the master drops the SUB but the OS-level
        socket state observable from the subscriber is often unchanged
        for an extended window (no FIN if the master half of the socket
        was silently reused / write-side stalled).
        """
        if self._sock is None:
            return False
        try:
            self._sock.getpeername()
        except OSError:
            return False
        return not self.closed_by_peer


# ---------------------------------------------------------------------------
# ZMQ pusher and subscriber
# ---------------------------------------------------------------------------


class ZMQPusher:
    """PUSH client into the publisher's PULL socket."""

    def __init__(self, host: str, port: int):
        self.host = host
        self.port = port
        self._ctx: zmq.Context | None = None
        self._sock: zmq.Socket | None = None

    def connect(self) -> None:
        self._ctx = zmq.Context()
        self._sock = self._ctx.socket(zmq.PUSH)
        # LINGER long enough that a burst-and-close sequence still
        # actually delivers.  ``close(0)`` drops un-flushed messages,
        # which caused tests to see 0/N frames on ephemeral pushers.
        self._sock.setsockopt(zmq.LINGER, 2000)
        # Give PUSH a moment to detect a not-yet-attached PULL as
        # unavailable and try again after connect completes.
        self._sock.setsockopt(zmq.SNDTIMEO, 5000)
        self._sock.connect(f"tcp://{self.host}:{self.port}")

    def send(self, body: bytes) -> None:
        assert self._sock is not None, "call connect() first"
        self._sock.send(body)

    def close(self) -> None:
        if self._sock is not None:
            # LINGER (set at connect time) governs the actual close.
            self._sock.close()
            self._sock = None
        if self._ctx is not None:
            self._ctx.destroy()
            self._ctx = None

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


class ZMQSubscriber:
    """SUB client from the publisher's PUB socket."""

    def __init__(
        self,
        host: str,
        port: int,
        *,
        read_delay: float = 0.0,
        rcvhwm: int | None = None,
        so_rcvbuf: int | None = None,
    ):
        self.host = host
        self.port = port
        self.read_delay = read_delay
        self.rcvhwm = rcvhwm
        self.so_rcvbuf = so_rcvbuf
        self._ctx: zmq.Context | None = None
        self._sock: zmq.Socket | None = None
        self._monitor_sock: zmq.Socket | None = None
        self._reader_thread: threading.Thread | None = None
        self._monitor_thread: threading.Thread | None = None
        self._stop = threading.Event()
        self._reading = False
        self.frames: list[bytes] = []
        self.disconnected_by_peer = False

    def connect(self) -> None:
        self._ctx = zmq.Context()
        self._sock = self._ctx.socket(zmq.SUB)
        self._sock.setsockopt(zmq.LINGER, 1)
        if self.rcvhwm is not None:
            self._sock.setsockopt(zmq.RCVHWM, self.rcvhwm)
        if self.so_rcvbuf is not None:
            self._sock.setsockopt(zmq.RCVBUF, self.so_rcvbuf)
        self._sock.setsockopt(zmq.SUBSCRIBE, b"")
        # Wire up socket monitor so the test can observe whether the
        # SUB ever sees a disconnect notification from the master.
        try:
            monitor_endpoint = f"inproc://monitor-sub-{id(self)}"
            self._sock.monitor(monitor_endpoint, zmq.EVENT_DISCONNECTED)
            self._monitor_sock = self._ctx.socket(zmq.PAIR)
            self._monitor_sock.connect(monitor_endpoint)
            self._monitor_thread = threading.Thread(
                target=self._monitor_loop,
                name=f"zmq-sub-monitor-{self.port}",
                daemon=True,
            )
            self._monitor_thread.start()
        except zmq.ZMQError:
            # monitor() may fail on old libzmq — non-fatal for tests.
            self._monitor_sock = None
        self._sock.connect(f"tcp://{self.host}:{self.port}")

    def start_reader(self) -> None:
        assert self._sock is not None, "call connect() first"
        self._reading = True
        self._reader_thread = threading.Thread(
            target=self._reader_loop, name=f"zmq-sub-{self.port}", daemon=True
        )
        self._reader_thread.start()

    def stop_reading(self) -> None:
        self._reading = False
        if self._reader_thread is not None:
            self._stop.set()
            self._reader_thread.join(timeout=2.0)
            self._reader_thread = None
            self._stop.clear()

    def _reader_loop(self) -> None:
        assert self._sock is not None
        poller = zmq.Poller()
        poller.register(self._sock, zmq.POLLIN)
        try:
            while not self._stop.is_set():
                events = dict(poller.poll(timeout=100))
                if self._sock in events:
                    try:
                        msg = self._sock.recv(zmq.NOBLOCK)
                    except zmq.Again:
                        continue
                    except zmq.ZMQError:
                        break
                    self.frames.append(msg)
                    if self.read_delay:
                        time.sleep(self.read_delay)
        finally:
            poller.unregister(self._sock)

    def _monitor_loop(self) -> None:
        assert self._monitor_sock is not None
        poller = zmq.Poller()
        poller.register(self._monitor_sock, zmq.POLLIN)
        try:
            while not self._stop.is_set():
                events = dict(poller.poll(timeout=100))
                if self._monitor_sock in events:
                    try:
                        # event msgpart 1: event_number + value
                        # event msgpart 2: endpoint
                        parts = self._monitor_sock.recv_multipart(zmq.NOBLOCK)
                    except zmq.Again:
                        continue
                    except zmq.ZMQError:
                        break
                    # Any DISCONNECTED event fires this flag.
                    if parts:
                        self.disconnected_by_peer = True
        finally:
            try:
                poller.unregister(self._monitor_sock)
            except Exception:  # pylint: disable=broad-except
                pass

    def socket_thinks_connected(self) -> bool:
        """
        Best-effort: has the SUB seen a DISCONNECTED event from libzmq?

        This is the SUB's ONLY signal that the master has dropped it —
        and in the HWM-drop path, no such event fires (the connection
        stays open; only application-layer messages are silently
        discarded).
        """
        return not self.disconnected_by_peer and self._sock is not None

    def close(self) -> None:
        self._reading = False
        self._stop.set()
        if self._reader_thread is not None:
            self._reader_thread.join(timeout=2.0)
            self._reader_thread = None
        if self._monitor_thread is not None:
            self._monitor_thread.join(timeout=2.0)
            self._monitor_thread = None
        if self._monitor_sock is not None:
            self._monitor_sock.close(0)
            self._monitor_sock = None
        if self._sock is not None:
            self._sock.close(0)
            self._sock = None
        if self._ctx is not None:
            self._ctx.destroy(0)
            self._ctx = None

    def __enter__(self):
        self.connect()
        self.start_reader()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def wait_for_frames(self, n: int, timeout: float = 5.0) -> bool:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if len(self.frames) >= n:
                return True
            time.sleep(0.02)
        return len(self.frames) >= n


# ---------------------------------------------------------------------------
# Transport-agnostic helpers
# ---------------------------------------------------------------------------


def make_pusher(publisher):
    if publisher.transport == "tcp":
        return TCPPusher(publisher.pull_host, publisher.pull_port)
    return ZMQPusher(publisher.pull_host, publisher.pull_port)


def make_subscriber(publisher, *, read_delay: float = 0.0, **kwargs):
    if publisher.transport == "tcp":
        return TCPSubscriber(
            publisher.pub_host, publisher.pub_port, read_delay=read_delay, **kwargs
        )
    return ZMQSubscriber(
        publisher.pub_host, publisher.pub_port, read_delay=read_delay, **kwargs
    )


def subscriber_frame_count(sub) -> int:
    return len(sub.frames)


def extract_body(frame) -> bytes:
    """
    Normalize a received frame to its ``body`` bytes.

    * TCP subscribers see ``{"head": {}, "body": <bytes>}`` msgpack dicts.
    * ZMQ subscribers see the raw body bytes.
    """
    if isinstance(frame, dict):
        return frame[b"body"] if b"body" in frame else frame["body"]
    return frame
