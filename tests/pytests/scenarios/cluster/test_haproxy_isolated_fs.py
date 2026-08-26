"""
Scenario: minion authenticates through a load-balancer (HAProxy-style)
in front of a cluster of masters running with
``cluster_isolated_filesystem: True``.

Reproduces https://github.com/saltstack/salt/issues/70090.

Under isolated-filesystem mode each cluster master keeps its own
``cluster_pki_dir``.  The founder generates ``cluster.pem`` /
``cluster.pub`` locally; joiners receive the founder's PEM over the
wire in ``cluster/peer/join-reply`` and overwrite their pre-join
placeholders on disk.

Before the fix in salt/channel/server.py, the joiner overwrote the
files on disk but never refreshed the master-keys cache the running
process (and every fresh worker) reads from via
``MasterKeys.get_pub_str``.  So each backend served a different
``cluster.pub`` to minions, and any minion reaching the cluster
through a round-robin load balancer would fail its second sign-in
with ``SaltClientError: Invalid master key``.

The test uses a small in-process asyncio TCP proxy that alternates
between the two backend masters per accepted connection, avoiding a
docker/HAProxy dependency in CI while exercising the exact
cross-backend key-mismatch code path the reporter hit.
"""

import asyncio
import contextlib
import logging
import pathlib
import socket
import threading
import time

import pytest
from pytestshellutils.utils import ports

import salt.utils.files
from tests.conftest import FIPS_TESTRUN

log = logging.getLogger(__name__)


pytestmark = [
    pytest.mark.slow_test,
    pytest.mark.no_subprocess_coverage,
]


class RoundRobinTCPProxy:
    """
    Minimal round-robin TCP proxy used as an in-process HAProxy stand-in.

    Each accepted client connection is bridged to the next backend in the
    list (``(host, port)`` tuples), advancing a shared cursor so successive
    connections land on different backends.  Traffic is proxied byte-for-byte
    in both directions.

    Runs its own event loop in a daemon thread; :meth:`start` blocks until
    the listen socket is bound so tests can advertise the port to minions
    right away.
    """

    def __init__(self, listen_host, listen_port, backends):
        self.listen_host = listen_host
        self.listen_port = listen_port
        # Copy so external mutation can't shift the round-robin cursor.
        self.backends = list(backends)
        self._cursor = 0
        self._cursor_lock = threading.Lock()
        self._loop = None
        self._server = None
        self._thread = None
        self._started_event = threading.Event()
        self._stop_event = None
        self.dispatch_log = []  # list[(backend_host, backend_port)]

    def _next_backend(self):
        with self._cursor_lock:
            backend = self.backends[self._cursor % len(self.backends)]
            self._cursor += 1
        return backend

    async def _pipe(self, reader, writer):
        try:
            while True:
                chunk = await reader.read(65536)
                if not chunk:
                    break
                writer.write(chunk)
                await writer.drain()
        except (ConnectionResetError, BrokenPipeError, OSError):
            pass
        finally:
            with contextlib.suppress(Exception):
                writer.close()

    async def _handle_client(self, client_reader, client_writer):
        backend_host, backend_port = self._next_backend()
        self.dispatch_log.append((backend_host, backend_port))
        try:
            backend_reader, backend_writer = await asyncio.open_connection(
                backend_host, backend_port
            )
        except OSError as exc:
            log.warning(
                "proxy: backend %s:%d unreachable: %s", backend_host, backend_port, exc
            )
            with contextlib.suppress(Exception):
                client_writer.close()
            return
        await asyncio.gather(
            self._pipe(client_reader, backend_writer),
            self._pipe(backend_reader, client_writer),
        )

    async def _serve(self):
        self._server = await asyncio.start_server(
            self._handle_client, self.listen_host, self.listen_port
        )
        self._started_event.set()
        try:
            await self._stop_event.wait()
        finally:
            self._server.close()
            with contextlib.suppress(Exception):
                await self._server.wait_closed()

    def _run(self):
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        self._stop_event = asyncio.Event()
        try:
            self._loop.run_until_complete(self._serve())
        finally:
            self._loop.close()

    def start(self, timeout=10):
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        if not self._started_event.wait(timeout):
            raise RuntimeError(
                f"RoundRobinTCPProxy did not bind {self.listen_host}:"
                f"{self.listen_port} within {timeout}s"
            )

    def stop(self, timeout=5):
        if self._loop is None or self._stop_event is None:
            return
        self._loop.call_soon_threadsafe(self._stop_event.set)
        if self._thread is not None:
            self._thread.join(timeout=timeout)


def _wait_for_port(host, port, timeout):
    """Wait until *host:port* accepts TCP connections."""
    deadline = time.monotonic() + timeout
    last_exc = None
    while time.monotonic() < deadline:
        try:
            with socket.create_connection((host, port), timeout=1.0):
                return True
        except OSError as exc:
            last_exc = exc
            time.sleep(0.5)
    raise TimeoutError(
        f"{host}:{port} did not accept connections within {timeout}s ({last_exc})"
    )


def _read_pub(path):
    p = pathlib.Path(path)
    if not p.is_file():
        return None
    with salt.utils.files.fopen(p, "rb") as fp:
        return fp.read()


def _wait_for_cluster_pub_convergence(masters, timeout=60):
    """
    Poll every master's on-disk ``cluster.pub`` until they all match.

    The join-reply handler installs the founder's ``cluster.pub`` on joiners
    after the discover/join handshake completes; the fixtures only wait for
    ``ret_port`` to bind, not for cluster convergence.
    """
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        pubs = [
            _read_pub(pathlib.Path(m.config["cluster_pki_dir"]) / "cluster.pub")
            for m in masters
        ]
        if all(p is not None for p in pubs) and len(set(pubs)) == 1:
            return pubs[0]
        time.sleep(0.5)
    pytest.fail(
        "Cluster masters never converged on a shared cluster.pub within "
        f"{timeout}s — join-reply key-distribution regressed. Contents: "
        + ", ".join(
            f"{m.config['interface']}={'<none>' if p is None else p[:32] + b'...'}"
            for m, p in zip(masters, pubs)
        )
    )


@pytest.fixture
def haproxy_vip_ports():
    """
    Allocate loopback VIP ports for the proxy (one for publish, one for req).

    The minion will point at these; the proxy round-robins each accepted
    connection between the two backend masters.
    """
    return {
        "publish_port": ports.get_unused_localhost_port(),
        "ret_port": ports.get_unused_localhost_port(),
    }


@pytest.fixture
def haproxy_proxy(
    cluster_master_1_isolated,
    cluster_master_2_isolated,
    haproxy_vip_ports,
):
    """
    Run two in-process TCP proxies (one for publish, one for req) that
    alternate between the two isolated-FS cluster masters.  Yields the
    proxies so tests can inspect ``dispatch_log`` and stops them on
    teardown.

    Before yielding, waits for the cluster to converge on a shared
    ``cluster.pub`` so the test's minion sees the same key regardless of
    which backend the proxy routes it to.
    """
    masters = [cluster_master_1_isolated, cluster_master_2_isolated]
    # Wait for the join-reply-driven cluster.pub convergence before letting
    # the minion connect.  Absent the fix this poll times out and the test
    # fails with a clear message pointing at the join-reply path.
    _wait_for_cluster_pub_convergence(masters)

    backends_pub = [(m.config["interface"], m.config["publish_port"]) for m in masters]
    backends_ret = [(m.config["interface"], m.config["ret_port"]) for m in masters]

    pub_proxy = RoundRobinTCPProxy(
        "127.0.0.10", haproxy_vip_ports["publish_port"], backends_pub
    )
    ret_proxy = RoundRobinTCPProxy(
        "127.0.0.10", haproxy_vip_ports["ret_port"], backends_ret
    )
    try:
        pub_proxy.start()
        ret_proxy.start()
    except OSError:
        # The 127.0.0.10 alias isn't present on this host (macOS/BSD
        # need `ifconfig lo0 alias 127.0.0.10 up`).  Fall back to
        # 127.0.0.1 with the allocated ports — same code path,
        # different VIP address.
        pub_proxy = RoundRobinTCPProxy(
            "127.0.0.1", haproxy_vip_ports["publish_port"], backends_pub
        )
        ret_proxy = RoundRobinTCPProxy(
            "127.0.0.1", haproxy_vip_ports["ret_port"], backends_ret
        )
        pub_proxy.start()
        ret_proxy.start()

    try:
        yield {
            "pub": pub_proxy,
            "ret": ret_proxy,
            "publish_port": haproxy_vip_ports["publish_port"],
            "ret_port": haproxy_vip_ports["ret_port"],
            "host": pub_proxy.listen_host,
        }
    finally:
        pub_proxy.stop()
        ret_proxy.stop()


@pytest.fixture
def haproxy_fronted_minion(
    salt_factories,
    cluster_master_1_isolated,
    cluster_master_2_isolated,
    haproxy_proxy,
):
    """
    A minion whose ``master`` address is the proxy VIP.  Each auth /
    request will be routed to one of the two backend masters
    round-robin.
    """
    _wait_for_port(haproxy_proxy["host"], haproxy_proxy["ret_port"], timeout=10)

    config_overrides = {
        "master": f"{haproxy_proxy['host']}:{haproxy_proxy['ret_port']}",
        "publish_port": haproxy_proxy["publish_port"],
        "log_granular_levels": {
            "salt": "info",
            "salt.transport": "debug",
            "salt.channel": "debug",
        },
        "fips_mode": FIPS_TESTRUN,
        "encryption_algorithm": ("OAEP-SHA224" if FIPS_TESTRUN else "OAEP-SHA1"),
        "signing_algorithm": ("PKCS1v15-SHA224" if FIPS_TESTRUN else "PKCS1v15-SHA1"),
    }
    factory = cluster_master_1_isolated.salt_minion_daemon(
        "haproxy-fronted-minion",
        defaults={"transport": cluster_master_1_isolated.config["transport"]},
        overrides=config_overrides,
        extra_cli_arguments_after_first_start_failure=["--log-level=info"],
    )
    with factory.started(start_timeout=120):
        yield factory


def test_minion_auth_via_haproxy_isolated_cluster(
    cluster_master_1_isolated,
    cluster_master_2_isolated,
    haproxy_proxy,
    haproxy_fronted_minion,
):
    """
    A minion configured to talk to a round-robin proxy in front of two
    isolated-FS cluster masters must be able to complete repeated
    sign-in / request cycles even though successive connections land on
    different backend masters.

    Pre-fix: the joiner served its pre-join placeholder ``cluster.pub``
    from the master-keys cache, so the minion cached one key on its
    first request and hit ``SaltClientError: Invalid master key`` on
    the second (which landed on the other backend).

    Post-fix: the join-reply handler refreshes the cache with the
    wire-delivered ``cluster.pub``, so every backend serves the same
    key.
    """
    # Issue enough test.ping calls that the round-robin proxy is
    # guaranteed to dispatch to both backends.  Each ``salt-call``
    # opens fresh connections, so 6 rounds -> at least ~3 dispatches
    # per backend.
    cli = haproxy_fronted_minion.salt_call_cli(timeout=30)
    for attempt in range(6):
        ret = cli.run("test.ping")
        assert ret.returncode == 0, (
            f"salt-call test.ping via HAProxy proxy failed on attempt "
            f"{attempt + 1}/6: rc={ret.returncode}, stderr={ret.stderr!r}"
        )
        assert ret.data is True, (
            f"salt-call test.ping returned unexpected data on attempt "
            f"{attempt + 1}/6: {ret.data!r}"
        )

    # Confirm the proxy actually round-robined across both backends;
    # otherwise the test is a no-op that would pass even with the bug
    # present.
    dispatched = set(haproxy_proxy["ret"].dispatch_log)
    assert len(dispatched) >= 2, (
        f"HAProxy proxy did not fan out across backends "
        f"(dispatched to {dispatched}); test cannot exercise the "
        f"cross-backend cluster.pub mismatch path."
    )
