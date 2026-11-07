"""
3-master isolated-FS cluster tests for chunked resource registration.

This is the Tier 3 of the scale-register test matrix described on
``dwoz/fix/minion-register-scale``: five minions × 200K resources each
routed through an in-process haproxy stand-in (RoundRobinTCPProxy) land
atomically on one of three cluster masters, and the registry's visible
state converges.

Scale cases are ``slow_test`` gated — the 1M-resource run is the gate
for the production bug but is impractical for every-commit CI (several
GB of pillar files on disk, several minutes of bring-up). Smaller
sanity cases run by default.

The RoundRobinTCPProxy class is re-used from
``test_haproxy_isolated_fs.py`` for the haproxy stand-in.

RUNTIME NOTE: these tests need 127.0.0.1-127.0.0.4 free. The dev-time
manual cluster sandbox at ``etc/salt/cluster_test/`` binds
``cluster_pool_port=55003`` on all three interfaces, which collides
with the saltfactories cluster bring-up's Raft peer channel and causes
master 3 to start without peering. Stop the sandbox before running
these on a developer host.
"""

import asyncio
import contextlib
import logging
import pathlib
import socket
import threading
import time

import pytest

import salt.utils.files
from tests.conftest import FIPS_TESTRUN

# pylint: disable=unused-import
from tests.pytests.integration.cluster.conftest import (
    _isolated_master_overrides,
    cluster_cache_path,
    cluster_cache_path_isolated,
    cluster_file_roots_path_isolated,
    cluster_master_1_isolated,
    cluster_master_2_isolated,
    cluster_master_3_isolated,
    cluster_pillar_roots_path_isolated,
    cluster_pki_path,
    cluster_pki_path_isolated,
    cluster_shared_path,
)

# pylint: enable=unused-import

log = logging.getLogger(__name__)


pytestmark = [
    pytest.mark.slow_test,
    pytest.mark.no_subprocess_coverage,
]


# ---------------------------------------------------------------------------
# RoundRobinTCPProxy — pure-Python haproxy stand-in
#
# Copied from tests/pytests/scenarios/cluster/test_haproxy_isolated_fs.py
# with no behavioural changes. Running it in-process lets us hit the
# chunked register path through a real load balancer without pulling
# haproxy into the test dependency set.
# ---------------------------------------------------------------------------


class RoundRobinTCPProxy:
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
                await writer.wait_closed()

    async def _handle_client(self, client_reader, client_writer):
        backend = self._next_backend()
        self.dispatch_log.append(backend)
        try:
            backend_reader, backend_writer = await asyncio.open_connection(*backend)
        except OSError:
            with contextlib.suppress(Exception):
                client_writer.close()
                await client_writer.wait_closed()
            return
        await asyncio.gather(
            self._pipe(client_reader, backend_writer),
            self._pipe(backend_reader, client_writer),
            return_exceptions=True,
        )

    async def _serve(self):
        self._stop_event = asyncio.Event()
        self._server = await asyncio.start_server(
            self._handle_client, self.listen_host, self.listen_port
        )
        self._started_event.set()
        async with self._server:
            await self._stop_event.wait()

    def _run(self):
        self._loop = asyncio.new_event_loop()
        try:
            self._loop.run_until_complete(self._serve())
        finally:
            with contextlib.suppress(Exception):
                self._loop.close()

    def start(self, timeout=10):
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        if not self._started_event.wait(timeout=timeout):
            raise RuntimeError("RoundRobinTCPProxy failed to bind within timeout")

    def stop(self, timeout=5):
        if self._loop and self._stop_event:
            self._loop.call_soon_threadsafe(self._stop_event.set)
        if self._thread:
            self._thread.join(timeout=timeout)


def _wait_for_port(host, port, timeout):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with socket.create_connection((host, port), timeout=1):
                return True
        except OSError:
            time.sleep(0.2)
    return False


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _pick_free_port(host):
    """Reserve and return a free TCP port on ``host`` by binding briefly."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind((host, 0))
        return s.getsockname()[1]


@pytest.fixture
def haproxy_pub_ret(
    cluster_master_1_isolated,
    cluster_master_2_isolated,
    cluster_master_3_isolated,
):
    """
    Round-robin TCP proxies for the three masters' publish + return ports,
    bound on 127.0.0.4. Yields ``(pub_port, ret_port)`` — minions are
    configured to talk to 127.0.0.4:ret_port and subscribe on
    127.0.0.4:pub_port. Ports are picked dynamically so a parallel
    sandbox at the sandbox-conventional 55007/55008 doesn't collide.
    """
    masters = [
        cluster_master_1_isolated,
        cluster_master_2_isolated,
        cluster_master_3_isolated,
    ]
    pub_backends = [(m.config["interface"], m.config["publish_port"]) for m in masters]
    ret_backends = [(m.config["interface"], m.config["ret_port"]) for m in masters]
    listen = "127.0.0.4"
    pub_port = _pick_free_port(listen)
    ret_port = _pick_free_port(listen)
    pub_proxy = RoundRobinTCPProxy(listen, pub_port, pub_backends)
    ret_proxy = RoundRobinTCPProxy(listen, ret_port, ret_backends)
    pub_proxy.start()
    ret_proxy.start()
    try:
        assert _wait_for_port(listen, pub_port, 5), "haproxy pub frontend did not bind"
        assert _wait_for_port(listen, ret_port, 5), "haproxy ret frontend did not bind"
        yield pub_port, ret_port
    finally:
        pub_proxy.stop()
        ret_proxy.stop()


def _write_pillar_tree(cluster_master_1_isolated, minion_ids, n_per_minion):
    """
    Install top.sls + per-minion pillar SLSes carrying ``n_per_minion``
    resources each. Returns the list of temp_file context managers —
    the caller must enter + exit them to control lifetime.
    """
    top_lines = ["base:"]
    for mid in minion_ids:
        top_lines.append(f"  '{mid}':")
        top_lines.append(f"    - {mid}_resources")
    top = "\n".join(top_lines) + "\n"
    ctxs = [cluster_master_1_isolated.pillar_tree.base.temp_file("top.sls", top)]
    for i, mid in enumerate(minion_ids):
        # Use distinct id ranges per minion so the master registry's
        # cross-minion uniqueness is also tested.
        start = i * n_per_minion
        lines = [
            "resources:",
            "  dummy:",
            "    resource_ids:",
        ]
        for j in range(n_per_minion):
            lines.append(f"      - dummy-{start + j:08d}")
        sls = "\n".join(lines) + "\n"
        ctxs.append(
            cluster_master_1_isolated.pillar_tree.base.temp_file(
                f"{mid}_resources.sls", sls
            )
        )
    return ctxs


def _make_haproxy_minion(
    cluster_master_1_isolated,
    pub_port,
    ret_port,
    minion_id,
    chunk_size=None,
):
    """
    Build a minion whose master address is the haproxy so pub/ret traffic
    is round-robined across the three cluster masters. If ``chunk_size``
    is non-None, inject it into the minion config so the test can force
    the chunked path at small inventories.
    """
    defaults = {"transport": cluster_master_1_isolated.config["transport"]}
    overrides = {
        "master": "127.0.0.4",
        "master_port": ret_port,
        "publish_port": pub_port,
        # open_mode=True so this minion's connection doesn't hinge on
        # cluster-wide key distribution (the subject under test here is
        # chunked register, not key sync).
        "open_mode": True,
        "multiprocessing": False,
        "fips_mode": FIPS_TESTRUN,
        "encryption_algorithm": "OAEP-SHA224" if FIPS_TESTRUN else "OAEP-SHA1",
        "signing_algorithm": "PKCS1v15-SHA224" if FIPS_TESTRUN else "PKCS1v15-SHA1",
        "log_granular_levels": {
            "salt": "info",
            "salt.channel": "debug",
            "salt.transport": "debug",
        },
    }
    if chunk_size is not None:
        overrides["resource_register_chunk_size"] = chunk_size
    factory = cluster_master_1_isolated.salt_minion_daemon(
        minion_id,
        defaults=defaults,
        overrides=overrides,
        extra_cli_arguments_after_first_start_failure=["--log-level=info"],
    )
    factory.after_terminate(
        pytest.helpers.remove_stale_minion_key,
        cluster_master_1_isolated,
        factory.id,
    )
    return factory


def _assert_no_truncation(masters):
    """
    Fail if any master log contains 'is truncated' — the mmap heap fix
    (#70717) means these should not appear under chunked register. If a
    master isn't observable (e.g. shut down for restart tests), it is
    skipped.
    """
    offenders = []
    for m in masters:
        log_path = m.config.get("log_file")
        if not log_path:
            continue
        p = pathlib.Path(log_path)
        if not p.is_file():
            continue
        try:
            with salt.utils.files.fopen(
                str(p), encoding="utf-8", errors="replace"
            ) as fh:
                for line in fh:
                    if "is truncated" in line:
                        offenders.append(f"{m.id}: {line.strip()}")
        except OSError:
            continue
    assert (
        not offenders
    ), "cluster master log(s) contain 'is truncated' warnings:\n" + "\n".join(
        offenders[:10]
    )


def _total_registered(cluster_master, type_name="dummy"):
    """
    Return the number of SRNs of ``type_name`` the master's
    ``resource_grains`` bank currently holds. Uses ``resource.list_grains``.
    """
    salt_run = cluster_master.salt_run_cli(timeout=120)
    ret = salt_run.run("resource.list_grains", _timeout=120)
    if ret.returncode != 0 or not isinstance(ret.data, dict):
        return 0
    return sum(1 for srn in ret.data if srn.startswith(f"{type_name}:"))


def _wait_total_registered(master, expected, timeout, type_name="dummy"):
    """Poll ``_total_registered`` until it reaches ``expected`` or times out."""
    deadline = time.monotonic() + timeout
    count = 0
    while time.monotonic() < deadline:
        count = _total_registered(master, type_name=type_name)
        if count >= expected:
            return count
        time.sleep(2)
    return count


# ---------------------------------------------------------------------------
# Baseline sanity: haproxy + one minion + small chunked register
# ---------------------------------------------------------------------------


def test_single_minion_small_pillar_through_haproxy(
    cluster_master_1_isolated,
    cluster_master_2_isolated,
    cluster_master_3_isolated,
    haproxy_pub_ret,
):
    """
    One minion sends 25 resources (forced chunk_size=10 -> 3 chunks)
    through the haproxy. All chunks must land on whichever master the
    round-robin dispatched them to, and ``resource.list_grains`` on that
    master must show 25 entries. Baseline sanity before the heavyweight
    scale cases.
    """
    pub_port, ret_port = haproxy_pub_ret
    minion_id = "scale-mini-1"
    ctxs = _write_pillar_tree(cluster_master_1_isolated, [minion_id], 25)
    with contextlib.ExitStack() as es:
        for ctx in ctxs:
            es.enter_context(ctx)
        minion_factory = _make_haproxy_minion(
            cluster_master_1_isolated,
            pub_port,
            ret_port,
            minion_id,
            chunk_size=10,
        )
        with minion_factory.started(start_timeout=240):
            salt_call = minion_factory.salt_call_cli(timeout=120)
            ret = salt_call.run("saltutil.refresh_pillar", wait=True, _timeout=120)
            assert ret.returncode == 0, ret
            ret = salt_call.run("saltutil.sync_all", _timeout=120)
            assert ret.returncode == 0, ret
            # Poll each master in turn — which one got the register depends
            # on which the round-robin was pointing at.
            total = 0
            for master in (
                cluster_master_1_isolated,
                cluster_master_2_isolated,
                cluster_master_3_isolated,
            ):
                total = max(total, _wait_total_registered(master, 25, timeout=60))
                if total >= 25:
                    break
            assert total >= 25, (
                f"single-minion 25-resource register through haproxy "
                f"did not reach any master (best observed {total})"
            )
    _assert_no_truncation(
        [
            cluster_master_1_isolated,
            cluster_master_2_isolated,
            cluster_master_3_isolated,
        ]
    )


# ---------------------------------------------------------------------------
# Scale: 200K via haproxy to the cluster
# ---------------------------------------------------------------------------


@pytest.mark.slow_test
@pytest.mark.timeout(900)
def test_single_minion_200k_through_haproxy(
    cluster_master_1_isolated,
    cluster_master_2_isolated,
    cluster_master_3_isolated,
    haproxy_pub_ret,
):
    """
    One minion × 200K resources via the haproxy -> one of three masters.
    Regression gate for the production scale target. Also fails if any
    master log emits the 'is truncated' warning that reappeared in the
    pre-#70717 mmap heap bug under heavy chunked writes.
    """
    pub_port, ret_port = haproxy_pub_ret
    minion_id = "scale-mini-200k"
    ctxs = _write_pillar_tree(cluster_master_1_isolated, [minion_id], 200_000)
    with contextlib.ExitStack() as es:
        for ctx in ctxs:
            es.enter_context(ctx)
        minion_factory = _make_haproxy_minion(
            cluster_master_1_isolated, pub_port, ret_port, minion_id
        )
        with minion_factory.started(start_timeout=300):
            salt_call = minion_factory.salt_call_cli(timeout=300)
            ret = salt_call.run("saltutil.refresh_pillar", wait=True, _timeout=600)
            assert ret.returncode == 0, ret
            ret = salt_call.run("saltutil.sync_all", _timeout=600)
            assert ret.returncode == 0, ret
            total = 0
            for master in (
                cluster_master_1_isolated,
                cluster_master_2_isolated,
                cluster_master_3_isolated,
            ):
                observed = _wait_total_registered(master, 200_000, timeout=600)
                log.info("master %s observed %d items", master.id, observed)
                total = max(total, observed)
                if total >= 200_000:
                    break
            assert total >= 200_000, (
                f"200K register through haproxy must land on some master; "
                f"best observed {total}"
            )
    _assert_no_truncation(
        [
            cluster_master_1_isolated,
            cluster_master_2_isolated,
            cluster_master_3_isolated,
        ]
    )


@pytest.mark.slow_test
@pytest.mark.timeout(1800)
def test_five_minions_1m_total_through_haproxy(
    cluster_master_1_isolated,
    cluster_master_2_isolated,
    cluster_master_3_isolated,
    haproxy_pub_ret,
):
    """
    THE SCALE TARGET: five minions × 200K resources each routed via the
    haproxy to the 3-master cluster. Each minion's inventory is a
    disjoint id range (dummy-00000000..dummy-00999999) so the master
    cluster's aggregate registry must contain 1 000 000 unique SRNs.

    Wall-clock bound: 30 min. The pre-chunking register path saw 4 of 5
    minions land only 100-150K items; this test fails hard on any
    partial-landing.

    Under ``cluster_isolated_filesystem: True`` each master owns its own
    registry file and the cluster sync replicates between them
    asynchronously — but the per-minion register lands on a single
    master and that master's registry sees the full inventory for that
    minion. The assertion sums the per-master union (dedup by SRN) and
    requires the total to equal 1 000 000.
    """
    pub_port, ret_port = haproxy_pub_ret
    minion_ids = [f"scale-mini-{i}" for i in range(5)]
    ctxs = _write_pillar_tree(cluster_master_1_isolated, minion_ids, 200_000)
    with contextlib.ExitStack() as es:
        for ctx in ctxs:
            es.enter_context(ctx)
        minion_factories = [
            _make_haproxy_minion(cluster_master_1_isolated, pub_port, ret_port, mid)
            for mid in minion_ids
        ]
        # Enter all minion contexts so they start in parallel.
        for mf in minion_factories:
            es.enter_context(mf.started(start_timeout=300))
        # Trigger a pillar refresh on each minion so it discovers its
        # resources and runs _register_resources_with_master.
        start = time.monotonic()
        for mf in minion_factories:
            salt_call = mf.salt_call_cli(timeout=600)
            ret = salt_call.run("saltutil.refresh_pillar", wait=True, _timeout=600)
            assert ret.returncode == 0, (mf.id, ret)
            ret = salt_call.run("saltutil.sync_all", _timeout=600)
            assert ret.returncode == 0, (mf.id, ret)
        # Poll the aggregate registry across all three masters.
        deadline = time.monotonic() + 1500
        aggregate = set()
        while time.monotonic() < deadline:
            aggregate = set()
            for master in (
                cluster_master_1_isolated,
                cluster_master_2_isolated,
                cluster_master_3_isolated,
            ):
                salt_run = master.salt_run_cli(timeout=120)
                ret = salt_run.run("resource.list_grains", _timeout=120)
                if ret.returncode == 0 and isinstance(ret.data, dict):
                    aggregate.update(
                        srn for srn in ret.data if srn.startswith("dummy:")
                    )
            if len(aggregate) >= 1_000_000:
                break
            time.sleep(5)
        elapsed = time.monotonic() - start
        log.info(
            "5x200K register observed %d unique SRNs after %.1fs",
            len(aggregate),
            elapsed,
        )
        assert len(aggregate) >= 1_000_000, (
            f"1M-SRN aggregate must be reached across cluster; "
            f"saw {len(aggregate)} after {elapsed:.1f}s"
        )
    _assert_no_truncation(
        [
            cluster_master_1_isolated,
            cluster_master_2_isolated,
            cluster_master_3_isolated,
        ]
    )
