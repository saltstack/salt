"""
MWorker-only stress-test fixture.

Spawns exactly one :class:`salt.master.MWorker` subprocess wired to a
private ``ReqServerChannel`` on a dynamically-allocated TCP port, and
gives tests a hand-rolled DEALER socket that impersonates
``MWorkerQueue``.  No full salt-master daemon is started — everything
below the MWorker (ext-transport, PubServer, EventReturn, Maintenance,
etc.) is absent.

Design notes
------------
* We bind the DEALER **after** ``worker.start()`` returns so the child
  does not inherit a live parent-side zmq socket file descriptor.
  libzmq is not fork-safe; inheriting an open ZMQ socket into the child
  causes silent drops.
* The DEALER's URI is computed via
  ``req_channel.transport.get_worker_uri(pool_name="default")`` so it
  matches the URI the child MWorker resolves.  ``MWorker.__init__``
  defaults ``pool_name`` to ``"default"``, and
  :func:`RequestServer.get_worker_uri` applies an ``adler32`` port
  offset for named pools — using the bare ``tcp_master_workers`` port
  puts the DEALER on the wrong socket and the round-trip silently
  hangs.
* ``opts["minimum_auth_version"] = 0`` is set so cleartext ``ping``
  payloads (used by throughput tests) are not rejected at the
  ReqServerChannel layer before they reach ``MWorker._handle_payload``.
* ``opts["worker_pools_enabled"] = False`` picks the plain
  :class:`~salt.channel.server.ReqServerChannel` path (no
  PoolRoutingChannel), which is the only one MWorker sees in practice.
"""

import ctypes
import logging
import multiprocessing
import socket
import time

import pytest
import zmq
import zmq.utils.monitor

import salt.channel.server
import salt.config
import salt.crypt
import salt.master
import salt.payload
import salt.utils.files
import salt.utils.stringutils

log = logging.getLogger(__name__)


def _pick_free_port() -> int:
    """
    Pick a free localhost port.  Uses SO_REUSEADDR + close to release
    it immediately; the caller (a zmq bind) will re-take it.
    """
    with socket.socket() as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture
def _mworker_secrets():
    """
    Seed ``SMaster.secrets["aes"]`` for the duration of the test.

    MWorker (and the ReqServerChannel it wraps) require this to be
    present before their in-child post_fork runs.
    """
    prev = salt.master.SMaster.secrets.get("aes")
    salt.master.SMaster.secrets["aes"] = {
        "secret": multiprocessing.Array(
            ctypes.c_char,
            salt.utils.stringutils.to_bytes(salt.crypt.Crypticle.generate_key_string()),
        ),
        "serial": multiprocessing.Value(ctypes.c_longlong, lock=False),
        "reload": salt.crypt.Crypticle.generate_key_string,
    }
    try:
        yield
    finally:
        if prev is None:
            salt.master.SMaster.secrets.pop("aes", None)
        else:
            salt.master.SMaster.secrets["aes"] = prev


@pytest.fixture
def mworker_opts(tmp_path):
    """
    Minimal master opts sufficient to instantiate an MWorker with a
    plain non-pooled ReqServerChannel.
    """
    root = tmp_path / "master"
    opts = salt.config.master_config(None)
    opts["__role"] = "master"
    opts["root_dir"] = str(root)
    for name in ("cachedir", "pki_dir", "sock_dir", "conf_dir"):
        d = root / name
        d.mkdir(parents=True, exist_ok=True)
        opts[name] = str(d)
    opts["log_file"] = str(root / "master.log")
    # Non-pooled path — MWorker + a plain ReqServerChannel over zmq TCP.
    opts["worker_pools_enabled"] = False
    opts["worker_threads"] = 1
    opts["transport"] = "zeromq"
    # TCP for the worker/queue socket so per-test parallelism does not
    # collide on filesystem IPC paths, and to sidestep fork-inheritance
    # oddities that IPC-on-tmpfs exhibits under repeated test runs.
    opts["ipc_mode"] = "tcp"
    opts["tcp_master_workers"] = _pick_free_port()
    opts["auto_accept"] = True
    opts["cluster_id"] = None
    opts["fips_mode"] = False
    # Cleartext ping traffic used by these tests is not "auth" and
    # would otherwise be rejected by ReqServerChannel.handle_message
    # before reaching the worker.
    opts["minimum_auth_version"] = 0
    # These niceness settings default to non-zero; running as non-root
    # in CI those would emit log warnings we don't care about.
    opts["req_server_niceness"] = None
    opts["mworker_niceness"] = None
    opts["pub_server_niceness"] = None
    opts["zmq_monitor"] = False
    opts["master_stats"] = False
    return opts


class MWorkerHandle:
    """
    Encapsulates a spawned MWorker subprocess and a client-side zmq
    DEALER that lets tests push request payloads and read replies.
    """

    def __init__(self, opts):
        self.opts = opts
        self.req_channel = salt.channel.server.ReqServerChannel.factory(opts)
        # Use the transport's own URI resolver so we bind exactly where
        # the child MWorker's REP will connect.
        self.w_uri = self.req_channel.transport.get_worker_uri(pool_name="default")
        self.mkey = salt.crypt.MasterKeys(opts)
        self._ctx = None
        self._dealer = None
        self._monitor = None
        self.process = salt.master.MWorker(
            opts,
            self.mkey,
            {},  # ClearFuncs.key: unused by ping/etc.
            [self.req_channel],
            name=f"stress-mworker-{opts['tcp_master_workers']}",
        )

    # -- lifecycle -------------------------------------------------------

    def start(self, ready_timeout: float = 10.0) -> None:
        """
        Fork the MWorker subprocess and wait for its REP to complete a
        handshake with our DEALER.
        """
        self.process.start()
        # Bind the DEALER *after* the child fork so the child does not
        # inherit our socket fd.  We create a per-handle Context (not
        # ``Context.instance()``) so state does not leak between tests.
        self._ctx = zmq.Context()
        self._dealer = self._ctx.socket(zmq.DEALER)
        self._dealer.setsockopt(zmq.LINGER, 0)
        # Ports we picked via ``_pick_free_port`` can briefly linger in
        # TIME_WAIT after the previous test's DEALER closes.  Retry
        # briefly so back-to-back test runs don't flake on
        # "Address already in use".
        bind_deadline = time.monotonic() + 5.0
        while True:
            try:
                self._dealer.bind(self.w_uri)
                break
            except zmq.error.ZMQError:
                if time.monotonic() >= bind_deadline:
                    raise
                time.sleep(0.1)
        # A monitor socket gives us a deterministic "connected" signal
        # instead of arbitrary time.sleep.
        self._monitor = self._dealer.get_monitor_socket()
        deadline = time.monotonic() + ready_timeout
        handshake = False
        while time.monotonic() < deadline:
            if self._monitor.poll(200):
                while self._monitor.poll(0):
                    try:
                        ev = zmq.utils.monitor.recv_monitor_message(self._monitor)
                    except zmq.error.Again:
                        break
                    if ev.get("event") == zmq.Event.HANDSHAKE_SUCCEEDED:
                        handshake = True
                        break
            if handshake:
                break
        if not handshake:
            raise TimeoutError(
                f"MWorker child (pid={self.process.pid}) never completed a REP "
                f"handshake at {self.w_uri} within {ready_timeout}s"
            )

    def stop(self, join_timeout: float = 5.0) -> None:
        try:
            if self._monitor is not None:
                self._monitor.close(linger=0)
                self._monitor = None
            if self._dealer is not None:
                self._dealer.close(linger=0)
                self._dealer = None
        finally:
            try:
                if self.process.is_alive():
                    self.process.terminate()
                self.process.join(timeout=join_timeout)
                if self.process.is_alive():
                    self.process.kill()
                    self.process.join(timeout=join_timeout)
            finally:
                try:
                    self.req_channel.close()
                except Exception:  # pylint: disable=broad-except
                    pass
                if self._ctx is not None:
                    try:
                        self._ctx.term()
                    except Exception:  # pylint: disable=broad-except
                        pass
                    self._ctx = None

    # -- request / reply -------------------------------------------------

    def send(self, payload: dict) -> None:
        """Enqueue one raw request payload on the DEALER."""
        raw = salt.payload.dumps(payload)
        self._dealer.send_multipart([b"", raw])

    def recv(self, timeout: float = 5.0):
        """
        Receive one reply from the DEALER, returning the decoded
        payload.  Raises ``TimeoutError`` when no reply arrives within
        ``timeout`` seconds.
        """
        if not self._dealer.poll(int(timeout * 1000)):
            raise TimeoutError(f"no reply within {timeout}s")
        parts = self._dealer.recv_multipart()
        # DEALER-to-REP framing: [empty-delimiter, payload]
        raw = parts[-1]
        try:
            return salt.payload.loads(raw)
        except Exception:  # pylint: disable=broad-except
            return raw

    def send_recv(self, payload: dict, timeout: float = 5.0):
        """One-shot send-and-wait-for-reply helper."""
        self.send(payload)
        return self.recv(timeout=timeout)

    def send_raw(self, raw: bytes) -> None:
        """Send arbitrary bytes (used for fault-injection tests)."""
        self._dealer.send_multipart([b"", raw])

    # -- introspection ---------------------------------------------------

    @property
    def pid(self) -> int:
        return self.process.pid

    def is_alive(self) -> bool:
        return self.process.is_alive()

    def rss_kb(self) -> int:
        """Read the child's resident set size in kilobytes from /proc."""
        with salt.utils.files.fopen(f"/proc/{self.pid}/status", "r") as f:
            for line in f:
                if line.startswith("VmRSS:"):
                    # "VmRSS:   12345 kB"
                    return int(line.split()[1])
        raise RuntimeError(f"no VmRSS in /proc/{self.pid}/status")


@pytest.fixture
def mworker(_mworker_secrets, mworker_opts):
    """
    Fully-wired MWorker subprocess + client DEALER.  Blocks until the
    REP↔DEALER handshake completes, so tests can immediately drive
    traffic.
    """
    handle = MWorkerHandle(mworker_opts)
    handle.start(ready_timeout=15.0)
    try:
        yield handle
    finally:
        handle.stop()
