"""
Fixtures for isolated stress tests of the salt-master MWorkerQueue subprocess.

The MWorkerQueue is the zmq QUEUE proxy defined by
``salt.transport.zeromq.RequestServer.zmq_device`` and started by
``salt.master`` under the name ``MWorkerQueue``.  It sits between:

* a ROUTER socket bound to ``tcp://{interface}:{ret_port}`` where minions
  (REQ) send authenticated request payloads, and
* a DEALER socket bound to ``tcp://127.0.0.1:{tcp_master_workers}`` (or
  an IPC path) where MWorker workers (REP) connect and pull work.

The fixture below spawns *only* that proxy in its own OS process against
fake peers so tests can exercise starvation, backpressure, malformed
input, and requester churn without paying for a full master.

Isolation rules
---------------
* The proxy is spawned with ``multiprocessing`` using the ``spawn`` start
  method so the parent test process is not tainted by libzmq context
  reuse.
* Every socket the tests open (fake minion / fake worker) uses a
  test-local ``zmq.Context`` created inside the fixture and torn down at
  the end.
* ``ret_port`` and ``tcp_master_workers`` are dynamically allocated free
  TCP ports so the fixture is safe to parametrise and to run in parallel.
* ``sock_dir`` is a per-test tempdir (only used because the proxy code
  references it during setup; we run ``ipc_mode='tcp'`` so nothing
  actually binds inside it).
"""

from __future__ import annotations

import multiprocessing
import os
import secrets
import socket
import sys
import time
from dataclasses import dataclass, field

import pytest
import zmq

import salt.utils.files

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _free_tcp_port() -> int:
    """Return a currently-free TCP port on 127.0.0.1."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _port_open(host: str, port: int, timeout: float = 0.2) -> bool:
    """Return True if a TCP connection to ``host:port`` succeeds."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(timeout)
        try:
            return s.connect_ex((host, port)) == 0
        except OSError:
            return False


def _build_opts(sock_dir: str, ret_port: int, worker_port: int) -> dict:
    """Minimal opts dict accepted by ``RequestServer.zmq_device``."""
    return {
        "interface": "127.0.0.1",
        "ret_port": ret_port,
        "ipv6": False,
        "mworker_queue_niceness": None,
        "sock_dir": sock_dir,
        "ipc_mode": "tcp",
        "tcp_master_workers": worker_port,
        "zmq_backlog": 1000,
        "zmq_monitor": False,
        # RequestRouter (built unconditionally inside zmq_device) reads this.
        # A single catch-all pool keeps its validation happy without turning
        # on the pooled code path.
        "worker_pools": {
            "default": {"worker_count": 1, "commands": ["*"]},
        },
        "worker_pools_enabled": False,
        # RequestRouter references opts.get("id", "") for its stats key.
        "id": "stress-mworkerqueue",
        # Never referenced by zmq_device but touched by imports elsewhere.
        "extension_modules": os.path.join(sock_dir, "extmods"),
    }


def _run_mworkerqueue(opts: dict) -> None:
    """
    Subprocess entrypoint: spin up a RequestServer and run its zmq_device.

    Readiness is signalled implicitly by both TCP ports being connectable
    (the parent polls with ``socket.connect_ex``).  We avoid pipe-based
    signalling because ``multiprocessing`` with ``spawn`` does not
    guarantee that a raw fd passed via ``args`` remains valid in the
    child (the fd number is not re-inherited across the exec that
    ``spawn`` performs on some platforms).

    Port-open is necessary but not sufficient: ``zmq_device()`` binds its
    ROUTER/DEALER sockets early, then imports ``salt.master`` and builds a
    ``RequestRouter`` before entering the ``zmq.device(QUEUE, ...)``
    forwarding loop.  Pre-import ``salt.master`` here so the heavy import
    happens before bind -- that minimises the window where ports are open
    but the device loop is not yet forwarding.  Tests that race the first
    message through the pipeline (the ``test_requester_churn_fd_bounded``
    family) hit that window on busy CI runners even with handshake-level
    waits in place.  The parent additionally calls ``_wait_pipeline_ready``
    to confirm an end-to-end round-trip before yielding.
    """
    # Pre-import inside the child so the parent doesn't pull half the master
    # stack (and its C extensions) until it has to -- but also so that by
    # the time ``zmq_device()`` binds its sockets, the slow salt.master
    # import it does mid-flight is already cached.
    import salt.master  # noqa: WPS433 pylint: disable=unused-import,import-outside-toplevel
    import salt.transport.zeromq as _z  # noqa: WPS433 pylint: disable=import-outside-toplevel

    server = _z.RequestServer(opts)
    try:
        server.zmq_device()
    except SystemExit:
        pass
    except KeyboardInterrupt:
        pass


def _wait_pipeline_ready(
    ctx: zmq.Context,
    router_uri: str,
    dealer_uri: str,
    timeout: float = 30.0,
) -> None:
    """
    Block until a REQ -> ROUTER -> device -> DEALER -> REP -> ack
    round-trip completes end-to-end.

    Port-open means the proxy's sockets are bound, not that the
    ``zmq.device(QUEUE, ROUTER, DEALER)`` forwarding loop has been entered
    (bind happens before ``salt.master`` import and ``RequestRouter``
    construction).  Also, HANDSHAKE_SUCCEEDED on the REP side only
    reflects the REP's view of the ZMTP handshake with the DEALER; it
    does not guarantee the DEALER has processed the REP's greeting and
    added it to its dispatch set.  The only reliable readiness signal is
    an actual round-trip.

    Each iteration uses a fresh unique token so a stale message from a
    previous aborted iteration (routed by the DEALER's internal queue
    once a peer appears) can't masquerade as a successful probe.  Both
    sockets are closed with ``LINGER=0`` between iterations so the
    ROUTER's identity binding for the dead REQ is reaped and dropped
    acks never confuse the next pass.
    """
    deadline = time.monotonic() + timeout
    last_err = ""
    while time.monotonic() < deadline:
        token = b"__probe__" + secrets.token_bytes(8)
        req = ctx.socket(zmq.REQ)
        req.setsockopt(zmq.LINGER, 0)
        req.setsockopt(zmq.RCVTIMEO, 500)
        req.setsockopt(zmq.SNDTIMEO, 500)
        rep = ctx.socket(zmq.REP)
        rep.setsockopt(zmq.LINGER, 0)
        rep.setsockopt(zmq.RCVTIMEO, 500)
        rep.setsockopt(zmq.SNDTIMEO, 500)
        try:
            rep.connect(dealer_uri)
            req.connect(router_uri)
            try:
                req.send(token)
            except zmq.error.ZMQError as exc:  # pragma: no cover - diagnostic
                last_err = f"req.send: {exc}"
                continue

            # Drain anything already queued on REP until we see our token
            # or exhaust 3 s of inner budget.  Stale messages (from an
            # earlier iteration's REQ that we've since closed) share the
            # ``__probe__`` prefix but not this iteration's random suffix.
            poller = zmq.Poller()
            poller.register(rep, zmq.POLLIN)
            inner_deadline = time.monotonic() + 3.0
            got_token = False
            while time.monotonic() < inner_deadline:
                events = dict(poller.poll(500))
                if rep not in events or not events[rep] & zmq.POLLIN:
                    continue
                msg = rep.recv()
                if msg == token:
                    got_token = True
                    break
                # Stale -- send a throwaway ack back so the REP FSM leaves
                # the ``must send`` state and we can poll again next pass.
                try:
                    rep.send(b"__stale_ack__")
                except zmq.error.ZMQError:
                    pass
            if not got_token:
                last_err = "no probe seen on REP within 3 s"
                continue

            try:
                rep.send(token)
            except zmq.error.ZMQError as exc:  # pragma: no cover - diagnostic
                last_err = f"rep.send: {exc}"
                continue

            poller2 = zmq.Poller()
            poller2.register(req, zmq.POLLIN)
            inner2 = time.monotonic() + 3.0
            while time.monotonic() < inner2:
                events = dict(poller2.poll(500))
                if req not in events or not events[req] & zmq.POLLIN:
                    continue
                reply = req.recv()
                if reply == token:
                    return  # end-to-end round-trip confirmed
                # Stale ack from an earlier aborted iteration -- discard
                # and keep waiting for our own.
            last_err = "no matching ack on REQ within 3 s"
        finally:
            try:
                req.close(linger=0)
            except Exception:  # pylint: disable=broad-except
                pass
            try:
                rep.close(linger=0)
            except Exception:  # pylint: disable=broad-except
                pass
    raise RuntimeError(
        f"MWorkerQueue subprocess pipeline did not become live within "
        f"{timeout}s (last iteration: {last_err})"
    )


# ---------------------------------------------------------------------------
# Handle exposed to tests
# ---------------------------------------------------------------------------


@dataclass
class MWorkerQueueHandle:
    """Lightweight process handle returned by the fixture."""

    process: multiprocessing.Process
    router_uri: str  # minion (REQ) connects here
    dealer_uri: str  # worker (REP) connects here
    ctx: zmq.Context
    opts: dict
    _sockets: list = field(default_factory=list)

    # ---- peer helpers -------------------------------------------------

    def minion(self, identity: bytes | None = None, linger: int = 500) -> zmq.Socket:
        """Open a fake-minion REQ socket connected to the ROUTER port."""
        s = self.ctx.socket(zmq.REQ)
        if identity is not None:
            s.setsockopt(zmq.IDENTITY, identity)
        s.setsockopt(zmq.LINGER, linger)
        s.setsockopt(zmq.RCVTIMEO, 5000)
        s.setsockopt(zmq.SNDTIMEO, 5000)
        s.connect(self.router_uri)
        self._sockets.append(s)
        return s

    def worker(self, linger: int = 500, wait_ready: bool = False) -> zmq.Socket:
        """Open a fake-worker REP socket connected to the DEALER port.

        ``wait_ready=True`` runs an end-to-end REQ -> worker -> ack probe
        before returning so the caller knows the proxy's inner DEALER has
        registered this REP as a routable peer.  Tests that race the
        first message through the pipeline on a freshly attached worker
        (e.g. ``test_requester_churn_fd_bounded``) need this; tests that
        attach several workers and tolerate first-few-message loss
        (e.g. ``test_passthrough_throughput``) do not.
        """
        s = self.ctx.socket(zmq.REP)
        s.setsockopt(zmq.LINGER, linger)
        s.setsockopt(zmq.RCVTIMEO, 5000)
        s.setsockopt(zmq.SNDTIMEO, 5000)
        s.connect(self.dealer_uri)
        self._sockets.append(s)
        if wait_ready:
            self._wait_worker_ready(s)
        return s

    def _wait_worker_ready(self, worker: zmq.Socket, timeout: float = 15.0) -> None:
        """Confirm this worker is in the proxy's inner DEALER dispatch set.

        HANDSHAKE_SUCCEEDED on the worker's REP monitor only reflects the
        REP's view of the ZMTP handshake; the DEALER-side peer-list
        update lags by hundreds of ms on busy CI runners, so a REQ sent
        in that window is routed to no peer and the worker never
        receives.  The only reliable readiness signal is an actual
        REQ -> worker -> ack round-trip.  Each iteration uses a unique
        token so stale messages from an aborted earlier iteration (that
        the DEALER drained once a peer appeared) can't masquerade as a
        successful probe.
        """
        deadline = time.monotonic() + timeout
        last_err = ""
        while time.monotonic() < deadline:
            token = b"__probe__" + secrets.token_bytes(8)
            probe = self.ctx.socket(zmq.REQ)
            probe.setsockopt(zmq.LINGER, 0)
            probe.setsockopt(zmq.RCVTIMEO, 500)
            probe.setsockopt(zmq.SNDTIMEO, 500)
            probe.connect(self.router_uri)
            try:
                try:
                    probe.send(token)
                except zmq.error.ZMQError as exc:  # pragma: no cover
                    last_err = f"probe.send: {exc}"
                    continue

                poller = zmq.Poller()
                poller.register(worker, zmq.POLLIN)
                inner = time.monotonic() + 3.0
                got_token = False
                while time.monotonic() < inner:
                    events = dict(poller.poll(500))
                    if worker not in events or not events[worker] & zmq.POLLIN:
                        continue
                    msg = worker.recv()
                    if msg == token:
                        got_token = True
                        break
                    # Stale -- a leftover from an earlier aborted
                    # iteration's REQ.  Send a throwaway ack so the REP
                    # FSM leaves "must send" state and we can keep
                    # polling.  The ack is routed to an identity bound
                    # to a now-closed probe, so the ROUTER silently
                    # drops it.
                    try:
                        worker.send(b"__stale_ack__")
                    except zmq.error.ZMQError:
                        pass
                if not got_token:
                    last_err = "no probe seen on worker within 3 s"
                    continue

                try:
                    worker.send(token)
                except zmq.error.ZMQError as exc:  # pragma: no cover
                    last_err = f"worker.send: {exc}"
                    continue

                poller2 = zmq.Poller()
                poller2.register(probe, zmq.POLLIN)
                inner2 = time.monotonic() + 3.0
                while time.monotonic() < inner2:
                    events = dict(poller2.poll(500))
                    if probe not in events or not events[probe] & zmq.POLLIN:
                        continue
                    reply = probe.recv()
                    if reply == token:
                        return
                last_err = "no matching ack on probe within 3 s"
            finally:
                try:
                    probe.close(linger=0)
                except Exception:  # pylint: disable=broad-except
                    pass
        raise RuntimeError(
            f"worker never confirmed routable within {timeout}s "
            f"(last iteration: {last_err})"
        )

    # ---- lifecycle ----------------------------------------------------

    def stop(self, timeout: float = 5.0) -> None:
        for s in list(self._sockets):
            try:
                s.close(linger=0)
            except Exception:  # pylint: disable=broad-except
                pass
        self._sockets.clear()
        if self.process.is_alive():
            self.process.terminate()
            self.process.join(timeout)
            if self.process.is_alive():
                self.process.kill()
                self.process.join(timeout)
        # Context terminated by fixture teardown.


# ---------------------------------------------------------------------------
# Pytest fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mwq_ctx():
    """Per-test zmq.Context — never share across tests."""
    ctx = zmq.Context()
    try:
        yield ctx
    finally:
        ctx.destroy(linger=0)


@pytest.fixture
def mworkerqueue(mwq_ctx, tmp_path):
    """
    Spawn a single MWorkerQueue subprocess and return an
    :class:`MWorkerQueueHandle` connected to it.
    """
    ret_port = _free_tcp_port()
    worker_port = _free_tcp_port()
    while worker_port == ret_port:
        worker_port = _free_tcp_port()

    sock_dir = str(tmp_path)
    os.makedirs(os.path.join(sock_dir, "extmods"), exist_ok=True)

    opts = _build_opts(sock_dir, ret_port, worker_port)

    # ``spawn`` gives us a clean interpreter — no inherited zmq contexts.
    ctx_mp = multiprocessing.get_context("spawn")
    proc = ctx_mp.Process(
        target=_run_mworkerqueue,
        args=(opts,),
        name="MWorkerQueue-stress",
        daemon=True,
    )
    proc.start()

    # Wait until both ports accept TCP connections (up to 15s).
    deadline = time.monotonic() + 15.0
    ready = False
    while time.monotonic() < deadline:
        if not proc.is_alive():
            break
        if _port_open("127.0.0.1", ret_port) and _port_open("127.0.0.1", worker_port):
            ready = True
            break
        time.sleep(0.05)

    if not ready:
        if proc.is_alive():
            proc.terminate()
            proc.join(2.0)
        raise RuntimeError(
            f"MWorkerQueue subprocess did not become ready "
            f"(alive={proc.is_alive()}, exitcode={proc.exitcode})"
        )

    router_uri = f"tcp://127.0.0.1:{ret_port}"
    dealer_uri = f"tcp://127.0.0.1:{worker_port}"

    # Ports accepting connections only means the sockets are bound -- it
    # does not mean the ``zmq.device(QUEUE, ROUTER, DEALER)`` forwarding
    # loop has been entered yet.  Confirm the full pipeline is live
    # before yielding so individual tests (notably the churn and
    # malformed-input ones) don't race the device-loop entry with their
    # first message.
    try:
        _wait_pipeline_ready(mwq_ctx, router_uri, dealer_uri)
    except RuntimeError:
        if proc.is_alive():
            proc.terminate()
            proc.join(2.0)
        raise

    handle = MWorkerQueueHandle(
        process=proc,
        router_uri=router_uri,
        dealer_uri=dealer_uri,
        ctx=mwq_ctx,
        opts=opts,
    )
    try:
        yield handle
    finally:
        handle.stop()


# ---------------------------------------------------------------------------
# Utility fixtures for tests that snapshot the child's resources.
# ---------------------------------------------------------------------------


def _proc_fd_count(pid: int) -> int:
    """Number of open file descriptors held by ``pid`` (Linux only)."""
    try:
        return len(os.listdir(f"/proc/{pid}/fd"))
    except (FileNotFoundError, PermissionError):
        return -1


def _proc_rss_kb(pid: int) -> int:
    """RSS of ``pid`` in kilobytes (Linux only)."""
    try:
        with salt.utils.files.fopen(f"/proc/{pid}/status", encoding="utf-8") as fh:
            for line in fh:
                if line.startswith("VmRSS:"):
                    return int(line.split()[1])
    except (FileNotFoundError, PermissionError):
        return -1
    return -1


@pytest.fixture
def proc_stats():
    """
    Return ``(fd_count, rss_kb)`` snapshot helpers.  Skip the test on
    non-Linux platforms where /proc is unavailable.
    """
    if not sys.platform.startswith("linux"):
        pytest.skip("proc stats require /proc (Linux only)")

    def _snapshot(pid: int) -> tuple[int, int]:
        return _proc_fd_count(pid), _proc_rss_kb(pid)

    return _snapshot
