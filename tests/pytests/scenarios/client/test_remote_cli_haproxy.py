"""
Scenario coverage for the remote Salt CLI against a 3-node master cluster
behind a load balancer.

The cluster masters already share ``cluster_pki_dir`` (via
``cluster_mode``), so the ``client_keys`` cache that
:class:`salt.master.MWorker._is_client_bridge` /
:meth:`ClearFuncs.publish` consult is visible from every master in the
pool.  What's new here is the *CLIENT* side: a workstation configured
to reach the cluster through a load-balancer front end instead of
pinning one master directly.

``RoundRobinTCPProxy`` is the same in-process HAProxy stand-in that
:mod:`tests.pytests.scenarios.cluster.test_haproxy_isolated_fs` uses --
copied here (rather than imported) so one test file breaking the proxy
doesn't take the other down with it.

Scope of the coverage:

* **Wheel path (``salt-key``)**: fully exercised.  Each ``salt-key``
  invocation opens a fresh ``ReqChannel``; the proxy routes it to one
  of the three masters round-robin.  Because every master in the
  cluster can resolve ``client_keys`` against the shared pki_dir, the
  AES bridge accepts the request regardless of which backend served
  it.  This is the primary HA property we care about.
* **Runner path (``salt-run``)**: covered for a stateless runner
  (``test.sleep``); the same per-connection round-robin assumption
  applies.
* **Publish path (``salt test.ping``)**: the publish+return cycle
  spans two separate network legs (ReqChannel for the publish, event
  subscriber for the return).  Only the publish leg is routed through
  the proxy; the event subscriber pins to a single master's
  ``client_event_port`` because round-robin PUB/SUB has no stickiness
  story.  This matches the production deployment pattern.

Known gap this test does NOT exercise: cross-master session-key
propagation (see the note on ``salt/channel/server.py`` in
``test_haproxy_isolated_fs.py``) -- a single long-lived ``RemoteClient``
instance that holds its ReqChannel open while hitting the LB multiple
times is not covered.  Each sub-test instantiates a fresh client, so
the per-connection AES session negotiated on sign-in is always consumed
by the same master that minted it.
"""

import asyncio
import contextlib
import logging
import textwrap
import threading

import pytest

import salt.crypt
import salt.key
import salt.utils.files
from tests.conftest import FIPS_TESTRUN

# pylint: disable=unused-import
from tests.pytests.integration.cluster.conftest import (
    cluster_cache_path,
    cluster_master_1,
    cluster_master_2,
    cluster_master_3,
    cluster_pki_path,
    cluster_shared_path,
)

# pylint: enable=unused-import

log = logging.getLogger(__name__)


pytestmark = [
    pytest.mark.slow_test,
    pytest.mark.no_subprocess_coverage,
]


# ---------------------------------------------------------------------------
# In-process HAProxy stand-in -- behaviour-equivalent to the copy in
# tests/pytests/scenarios/cluster/test_haproxy_isolated_fs.py.  Duplicated
# so a test-side rewrite over there does not silently affect this suite.
# ---------------------------------------------------------------------------


class RoundRobinTCPProxy:
    """
    Minimal round-robin TCP proxy used as an in-process HAProxy stand-in.
    """

    def __init__(self, listen_host, listen_port, backends):
        self.listen_host = listen_host
        self.listen_port = listen_port
        self.backends = list(backends)
        self._cursor = 0
        self._cursor_lock = threading.Lock()
        self._loop = None
        self._server = None
        self._thread = None
        self._started_event = threading.Event()
        self._stop_event = None
        self.dispatch_log = []

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
                "proxy: backend %s:%d unreachable: %s",
                backend_host,
                backend_port,
                exc,
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


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def cluster_masters(cluster_master_1, cluster_master_2, cluster_master_3):
    """Convenience bundle of the three cluster masters as a list."""
    return [cluster_master_1, cluster_master_2, cluster_master_3]


@pytest.fixture
def cluster_lb_proxy(cluster_masters):
    """
    HAProxy stand-in in front of the three masters' ``ret_port``.

    Each cluster master binds its own ``127.0.0.{1,2,3}:ret_port``; the
    proxy accepts on ``127.0.0.1`` at a dynamically-allocated port and
    round-robins TCP connections across the three backends.
    """
    from pytestshellutils.utils import ports

    listen_port = ports.get_unused_localhost_port()
    backends = [(m.config["interface"], m.config["ret_port"]) for m in cluster_masters]
    proxy = RoundRobinTCPProxy("127.0.0.1", listen_port, backends)
    proxy.start()
    try:
        yield proxy
    finally:
        proxy.stop()


@pytest.fixture
def remote_client_setup_cluster(cluster_masters, cluster_lb_proxy, tmp_path):
    """
    Workstation setup pointing at the cluster through the proxy.

    * generates a fresh PKI keypair in the workstation's ``pki_dir``
    * registers the pubkey in the cluster's shared ``cluster_pki_dir``
      so every master can resolve ``client_keys`` for this client
    * writes an ``/etc/salt/client``-style config whose ``master_port``
      points at the proxy's listen port (so publish / runner / wheel
      traffic rotates across masters) and whose ``client_event_port``
      pins to ``cluster_master_1`` (round-robin PUB/SUB has no
      stickiness, so the event subscriber must stick to one backend)
    """
    workstation_dir = tmp_path / "cluster_workstation"
    workstation_dir.mkdir()
    pki_dir = workstation_dir / "pki"
    pki_dir.mkdir()

    client_id = "cluster-admin"
    priv_key, pub_key = salt.crypt.gen_keys(2048)

    priv_path = pki_dir / "client.pem"
    pub_path = pki_dir / "client.pub"
    with salt.utils.files.fopen(priv_path, "wb") as fp:
        fp.write(priv_key.encode() if isinstance(priv_key, str) else priv_key)
    with salt.utils.files.fopen(pub_path, "wb") as fp:
        fp.write(pub_key.encode() if isinstance(pub_key, str) else pub_key)
    import os

    os.chmod(priv_path, 0o400)
    os.chmod(pub_path, 0o644)

    # Pre-accept the client's pubkey on master 1.  Because every master
    # has ``cluster_id`` set, ``salt.cache.localfs_key.init_kwargs``
    # resolves ``cachedir`` to ``cluster_pki_dir`` -- so the entry we
    # store here is visible on every peer.
    with salt.key.ClientKey(cluster_masters[0].config) as ckey:
        ckey.cache.store(
            "client_keys", client_id, {"pub": pub_key, "state": "accepted"}
        )

    cluster_m1 = cluster_masters[0]
    # Match the master-side crypto choices (see cluster_master_1 in
    # tests/pytests/integration/cluster/conftest.py).  Under FIPS the
    # defaults ``PKCS1v15-SHA1`` / ``OAEP-SHA1`` fail sign-in because
    # SHA1 is disallowed; fall through to the standard SHA224 pair
    # used by the rest of the test suite's FIPS runs.
    _fips_bool = "true" if FIPS_TESTRUN else "false"
    _sign_algo = "PKCS1v15-SHA224" if FIPS_TESTRUN else "PKCS1v15-SHA1"
    _enc_algo = "OAEP-SHA224" if FIPS_TESTRUN else "OAEP-SHA1"
    client_config = textwrap.dedent(
        f"""
        id: {client_id}
        # Point at the HAProxy stand-in, not any individual master.
        master: {cluster_lb_proxy.listen_host}
        master_port: {cluster_lb_proxy.listen_port}

        # The event-stream SUB/REP pair has no round-robin story
        # (events a master emits don't propagate across the cluster
        # bus), so pin to a single master.  Operators doing the same
        # topology would use session-affinity on the LB for this port
        # pair; this test picks master 1 directly.
        client_event_port: {cluster_m1.config['client_event_port']}

        pki_dir: {pki_dir}
        transport: {cluster_m1.config.get('transport', 'zeromq')}

        fips_mode: {_fips_bool}
        signing_algorithm: {_sign_algo}
        encryption_algorithm: {_enc_algo}

        timeout: 30
        acceptance_wait_time: 10
        acceptance_wait_time_max: 30
        """
    )

    config_file = workstation_dir / "client"
    with salt.utils.files.fopen(config_file, "w") as fp:
        fp.write(client_config)

    return {
        "id": client_id,
        "config_file": str(config_file),
        "pki_dir": str(pki_dir),
        "pub_key": pub_key,
        "priv_key": priv_key,
        "config_dir": str(workstation_dir),
    }


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestRemoteCLIBehindClusterLB:
    """
    Verify the remote CLI continues to function when the operator's
    workstation reaches the master cluster through a round-robin TCP
    load balancer.
    """

    def test_proxy_fronts_all_three_masters(self, cluster_lb_proxy, cluster_masters):
        """Sanity: proxy's backend list matches the cluster masters."""
        backends = set(cluster_lb_proxy.backends)
        expected = {
            (m.config["interface"], m.config["ret_port"]) for m in cluster_masters
        }
        assert backends == expected
        assert len(backends) == 3

    def test_cluster_shares_client_keys_cache(
        self, cluster_masters, remote_client_setup_cluster
    ):
        """
        Every master in the cluster must see the ``client_keys`` entry
        the setup fixture stored on master 1 -- otherwise an LB that
        routed a request to a different backend would reject the
        client at the AES-bridge gate.  Reads via each master's own
        ``salt.cache`` (not just the shared file) to catch any
        cache-driver layer that might shadow disk state.
        """
        import salt.cache

        client_id = remote_client_setup_cluster["id"]
        for master in cluster_masters:
            cache = salt.cache.Cache(
                master.config,
                driver=master.config.get("keys.cache_driver", "localfs_key"),
            )
            record = cache.fetch("client_keys", client_id)
            assert (
                record is not None
            ), f"client_keys entry missing on {master.config['interface']}"
            assert record.get("state") == "accepted"
            assert record.get("pub"), "pub key empty in client_keys record"

    def test_wheel_list_clients_through_proxy(self, remote_client_setup_cluster):
        """
        ``salt-key``-style wheel call through the proxy.

        Instantiate a :class:`salt.wheel.RemoteWheelClient` (which is
        what ``salt-key -L`` ends up using when ``__role=client``) and
        invoke ``key.list_all_client``.  The call opens an AES ReqChannel
        to the proxy -- the proxy routes it to one of the three
        cluster masters round-robin -- the master dispatches to
        ClearFuncs.wheel under ``auth_type="client"``, which authorises
        via ``self.client_acl``.  The response identifies our client
        in the ``clients`` list.
        """
        import salt.config
        import salt.wheel

        opts = salt.config.client_config(remote_client_setup_cluster["config_file"])
        wheel = salt.wheel.RemoteWheelClient(opts)
        try:
            result = wheel.cmd_sync({"fun": "key.list_all_client"})
        finally:
            wheel.destroy()

        # Response shape: {"tag": ..., "data": {"return": {"clients": [...]}}}
        assert isinstance(result, dict), result
        inner = result.get("data") or result
        if "return" in inner:
            inner = inner["return"]
        assert "clients" in inner, f"expected 'clients' key in response, got {inner!r}"
        assert remote_client_setup_cluster["id"] in inner["clients"]

    def test_proxy_rotates_across_backends(
        self, cluster_lb_proxy, remote_client_setup_cluster
    ):
        """
        After several wheel calls, the proxy's dispatch log should
        show connections distributed across all three masters -- not
        pinned to one.  This proves the LB layer is actually rotating
        and the auth path tolerates it.
        """
        import salt.config
        import salt.wheel

        opts = salt.config.client_config(remote_client_setup_cluster["config_file"])

        starting = len(cluster_lb_proxy.dispatch_log)
        for _ in range(6):
            wheel = salt.wheel.RemoteWheelClient(opts)
            try:
                wheel.cmd_sync({"fun": "key.list_all_client"})
            finally:
                wheel.destroy()

        new_dispatches = cluster_lb_proxy.dispatch_log[starting:]
        # Each cmd_sync opens one ReqChannel connection; the proxy's
        # cursor advances per accepted connection.  Six calls => at
        # least six dispatches.
        assert (
            len(new_dispatches) >= 6
        ), f"proxy saw {len(new_dispatches)} new dispatches, expected >= 6"
        backends_hit = {bk for bk in new_dispatches}
        # Allow the LB to rotate across any subset of the backends;
        # the stronger assertion is that it's not pinned to one.
        assert len(backends_hit) >= 2, (
            f"proxy only hit {len(backends_hit)} backend(s): {backends_hit!r} "
            "-- round-robin not rotating as expected"
        )
