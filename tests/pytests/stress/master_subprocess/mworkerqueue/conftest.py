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
    """
    # Import inside the child so the parent doesn't pull half the master
    # stack (and its C extensions) until it has to.
    import salt.transport.zeromq as _z  # noqa: WPS433

    server = _z.RequestServer(opts)
    try:
        server.zmq_device()
    except SystemExit:
        pass
    except KeyboardInterrupt:
        pass


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

    def worker(self, linger: int = 500) -> zmq.Socket:
        """Open a fake-worker REP socket connected to the DEALER port."""
        s = self.ctx.socket(zmq.REP)
        s.setsockopt(zmq.LINGER, linger)
        s.setsockopt(zmq.RCVTIMEO, 5000)
        s.setsockopt(zmq.SNDTIMEO, 5000)
        s.connect(self.dealer_uri)
        self._sockets.append(s)
        return s

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

    handle = MWorkerQueueHandle(
        process=proc,
        router_uri=f"tcp://127.0.0.1:{ret_port}",
        dealer_uri=f"tcp://127.0.0.1:{worker_port}",
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
