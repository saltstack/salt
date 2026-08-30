"""
Fixtures for isolated ``PubServerChannel._publish_daemon`` stress tests.

We spawn ONLY the transport's ``PublishServer.publish_daemon`` in a fresh
subprocess (no salt-master, no auth, no crypto).  The daemon binds:

* one **pub** endpoint that fan-outs to attached subscribers (TCP or
  zmq PUB); tests attach fake subscribers here to observe / stress the
  fan-out behavior.
* one **pull** endpoint that ingests payloads (TCP IPC or zmq PULL);
  tests push payloads here.

The fixture is parametrized by transport (``tcp``, ``zeromq``) via
``pytest.fixture(params=...)``.

The ``publish_payload`` handler in production wraps its input with the
master's crypto material (``PubServerChannel.publish_payload`` at
``salt/channel/server.py:1454``).  For these stress tests we skip that
wrap and use each transport's own ``publish_payload`` directly, which is
what the daemon actually spins on in ``publisher()``.  This is the
faithful shape of the ``PubServerChannel._publish_daemon`` subprocess
minus the crypto-transform step, and the fan-out / backpressure / drop
mechanisms under test live entirely below the crypto step.
"""

from __future__ import annotations

import multiprocessing
import os
import socket
import time

import pytest


def _find_free_port() -> int:
    """Bind to port 0, return the port, then close."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


# ---------------------------------------------------------------------------
# Subprocess entrypoints (top-level so they are picklable on spawn platforms)
# ---------------------------------------------------------------------------


def _run_tcp_publish_daemon(opts, pub_host, pub_port, pull_host, pull_port, started):
    """Entrypoint for the TCP publisher subprocess."""
    # Avoid inheriting the parent process' asyncio state.
    import salt.transport.tcp  # noqa: F401 pylint: disable=import-outside-toplevel

    server = salt.transport.tcp.PublishServer(
        opts,
        pub_host=pub_host,
        pub_port=pub_port,
        pull_host=pull_host,
        pull_port=pull_port,
        started=started,
    )
    # ``PublishServer.publish_payload`` forwards to ``pub_server.publish_payload``.
    # This is the identity forwarder path used by production
    # ``PubServerChannel._publish_daemon`` once the crypto wrap has run.
    server.publish_daemon(server.publish_payload, started=started)


def _run_zmq_publish_daemon(opts, pub_host, pub_port, pull_host, pull_port, started):
    """Entrypoint for the ZeroMQ publisher subprocess."""
    import salt.transport.zeromq  # noqa: F401 pylint: disable=import-outside-toplevel

    server = salt.transport.zeromq.PublishServer(
        opts,
        pub_host=pub_host,
        pub_port=pub_port,
        pull_host=pull_host,
        pull_port=pull_port,
        started=started,
    )
    server.publish_daemon(server.publish_payload, started=started)


# ---------------------------------------------------------------------------
# Handle returned by the fixture
# ---------------------------------------------------------------------------


class PublisherHandle:
    """
    Bundle of endpoints and process controls for a spawned publisher daemon.
    """

    def __init__(
        self,
        transport,
        process,
        pub_host,
        pub_port,
        pull_host,
        pull_port,
        opts,
    ):
        self.transport = transport
        self.process = process
        self.pub_host = pub_host
        self.pub_port = pub_port
        self.pull_host = pull_host
        self.pull_port = pull_port
        self.opts = opts

    @property
    def pid(self):
        return self.process.pid

    def is_alive(self) -> bool:
        return self.process.is_alive()

    def stop(self, timeout: float = 5.0) -> None:
        if not self.process.is_alive():
            return
        self.process.terminate()
        self.process.join(timeout=timeout)
        if self.process.is_alive():
            self.process.kill()
            self.process.join(timeout=timeout)


# ---------------------------------------------------------------------------
# Fixture
# ---------------------------------------------------------------------------


_DEFAULT_OPTS = {
    "ipv6": False,
    "zmq_filtering": False,
    "zmq_backlog": 1000,
    "pub_hwm": 1000,
    "tcp_keepalive": True,
    "tcp_keepalive_idle": 300,
    "tcp_keepalive_cnt": -1,
    "tcp_keepalive_intvl": -1,
    "tcp_master_publish_pull": None,
    "pub_server_niceness": 0,
    "order_masters": False,
}


@pytest.fixture(params=["tcp", "zeromq"])
def transport(request):
    return request.param


@pytest.fixture
def publisher_opts_overrides(request):
    """
    Tests can override this to tweak the opts passed to the publisher
    subprocess (e.g. set ``pub_hwm`` low for HWM tests).

    Populate via ``@pytest.mark.parametrize("publisher_opts_overrides",
    [{"pub_hwm": 10}], indirect=True)``.
    """
    return getattr(request, "param", {})


@pytest.fixture
def publisher(transport, publisher_opts_overrides):
    """
    Spawn a fresh ``PublishServer.publish_daemon`` subprocess for the
    parametrized transport and yield a :class:`PublisherHandle`.
    """
    pub_port = _find_free_port()
    pull_port = _find_free_port()
    pub_host = "127.0.0.1"
    pull_host = "127.0.0.1"

    opts = dict(_DEFAULT_OPTS)
    opts["transport"] = transport
    opts["publish_port"] = pub_port
    opts["ret_port"] = pull_port
    opts["interface"] = pub_host
    opts["id"] = "stress-master"
    opts["__role"] = "master"
    opts.update(publisher_opts_overrides)

    started = multiprocessing.Event()
    ctx = multiprocessing.get_context("fork")

    if transport == "tcp":
        target = _run_tcp_publish_daemon
    else:
        target = _run_zmq_publish_daemon

    proc = ctx.Process(
        target=target,
        args=(opts, pub_host, pub_port, pull_host, pull_port, started),
        name=f"PubServerChannel._publish_daemon[{transport}]",
    )
    proc.start()

    # Wait for the daemon to signal ready.
    if not started.wait(timeout=15.0):
        proc.terminate()
        proc.join(timeout=5.0)
        pytest.fail(f"publisher subprocess ({transport}) did not signal ready")

    handle = PublisherHandle(
        transport=transport,
        process=proc,
        pub_host=pub_host,
        pub_port=pub_port,
        pull_host=pull_host,
        pull_port=pull_port,
        opts=opts,
    )
    # Extra breathing room for pub socket to accept connections.
    time.sleep(0.2)
    try:
        yield handle
    finally:
        handle.stop()


# ---------------------------------------------------------------------------
# Convenience: peer-connection helpers exposed to test modules
# ---------------------------------------------------------------------------


def rss_kb(pid: int) -> int:
    """Return RSS in KiB for ``pid``; 0 if the process is gone."""
    import salt.utils.files  # pylint: disable=import-outside-toplevel

    try:
        with salt.utils.files.fopen(f"/proc/{pid}/status", encoding="utf-8") as f:
            for line in f:
                if line.startswith("VmRSS:"):
                    return int(line.split()[1])
    except FileNotFoundError:
        return 0
    return 0


def fd_count(pid: int) -> int:
    """Return count of open file descriptors for ``pid``; 0 if gone."""
    try:
        return len(os.listdir(f"/proc/{pid}/fd"))
    except FileNotFoundError:
        return 0
