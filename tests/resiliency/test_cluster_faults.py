"""Cluster-specific fault battery -- pytest port of ``scenarios/cluster_faults.sh``.

Each test exercises a fault that only makes sense when more than one
master is in play.  Every phase carries a ``@pytest.mark.topology(...)``
marker so conftest's ``pytest_collection_modifyitems`` records a
``skipped_for_topology`` row on topologies that don't match -- the
scenarios do not short-circuit each other and no per-phase runtime guard
is required.

Phase -> test mapping (phase labels are passed verbatim to
``assert_reconnect`` so ``results.jsonl`` rows stay compatible with the
analyzer):

    cluster_peer_sigstop_standard                 test_cluster_peer_sigstop_standard
    cluster_peer_sigstop_backoff                  test_cluster_peer_sigstop_backoff
    cluster_peer_unreachable                      test_cluster_peer_unreachable
    cluster_aes_rotation_under_load               test_cluster_aes_rotation_under_load
    cluster_haproxy_backend_flap                  test_cluster_haproxy_backend_flap
    cluster_split_brain_simulate                  test_cluster_split_brain_simulate
    cluster_rolling_restart_with_traffic_<m>      test_cluster_rolling_restart_with_traffic[<m>]
    multimaster_primary_unreachable               test_multimaster_primary_unreachable
    multimaster_hothot_one_master_tc_partition    test_multimaster_hothot_one_master_tc_partition
    multimaster_both_masters_restart_staggered    test_multimaster_both_masters_restart_staggered

Correctness notes (see the audit at
``agents/reports/cluster-faults-correctness-audit.md``): the existing
reconnect-only signals are preserved as-is.  A future wave will enrich
them with raft ``match_index`` / data-consistency checks.  Nothing in
this port touches ``/etc/salt/cluster-pki``, raft state, or minion
keys.  The AES-rotation phase writes + removes a single ``.dfn``
dropfile at ``/var/cache/salt/master/.dfn`` and nothing else.
"""

# pylint: disable=broad-exception-caught  # Resiliency: test cleanup catches Exception deliberately to avoid masking the real verdict

from __future__ import annotations

import os
import subprocess
import time

import pytest

from tests.resiliency.durations import (
    PACING_ROLLING_SEC,
    PING_TIMEOUT_SEC,
    RECOVER_STANDARD_SEC,
    TIER_BACKOFF_SEC,
    TIER_DEEPREC_SEC,
    TIER_STANDARD_SEC,
)
from tests.resiliency.lib.injectors import (
    disconnected_from_network,
    inject_netem,
    sigstopped_container,
)
from tests.resiliency.lib.topology import load_topology

# ---------------------------------------------------------------------------
# Env knobs (preserve bash defaults from cluster_faults.sh)
# ---------------------------------------------------------------------------


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


PEER_SIGSTOP_SEC = _env_int("PEER_SIGSTOP_SEC", TIER_STANDARD_SEC)
PEER_SIGSTOP_BACKOFF_SEC = _env_int("PEER_SIGSTOP_BACKOFF_SEC", TIER_BACKOFF_SEC)
PEER_UNREACHABLE_SEC = _env_int("PEER_UNREACHABLE_SEC", TIER_BACKOFF_SEC)
AES_PROPAGATION_WAIT_SEC = _env_int("AES_PROPAGATION_WAIT_SEC", 30)
HAPROXY_FLAP_SEC = _env_int("HAPROXY_FLAP_SEC", TIER_STANDARD_SEC)
SPLIT_BRAIN_SEC = _env_int("SPLIT_BRAIN_SEC", TIER_DEEPREC_SEC)
ROLLING_WORKLOAD_BURST_SEC = _env_int("ROLLING_WORKLOAD_BURST_SEC", 15)
MM_PRIMARY_UNREACH_SEC = _env_int("MM_PRIMARY_UNREACH_SEC", 90)
MM_HOTHOT_PARTITION_SEC = _env_int("MM_HOTHOT_PARTITION_SEC", TIER_STANDARD_SEC)
MM_STAGGERED_GAP_SEC = _env_int("MM_STAGGERED_GAP_SEC", 10)
INTER_MASTER_WAIT_SEC = _env_int("INTER_MASTER_WAIT_SEC", PACING_ROLLING_SEC)


HAPROXY_CONTAINER = "c3-salt-haproxy"


# ---------------------------------------------------------------------------
# Collection-time parametrize for the rolling-restart test
# ---------------------------------------------------------------------------


def pytest_generate_tests(metafunc):
    """Expand ``master`` parametrize from the active --topology.

    ``load_topology`` is pure data (no docker side effects), so it's safe
    to call at collection time to size the rolling parametrize.  On
    topologies that don't match the test's ``@pytest.mark.topology``
    marker the conftest still adds the skip marker; we still produce one
    parametrize id so a ``skipped_for_topology`` row lands in
    ``results.jsonl``.
    """
    if "rolling_master" in metafunc.fixturenames:
        topo_name = metafunc.config.getoption("--topology")
        spec = load_topology(topo_name)
        if spec.master_count <= 1:
            metafunc.parametrize(
                "rolling_master",
                [pytest.param(spec.primary_master, id=spec.primary_master)],
            )
        else:
            metafunc.parametrize(
                "rolling_master",
                [pytest.param(m, id=m) for m in spec.masters],
            )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _pick_non_primary_peer(topology) -> str | None:
    """Return the first master in ``spec.masters`` that is not primary."""
    for m in topology.spec.masters:
        if m != topology.spec.primary_master:
            return m
    return None


def _wait_container_running(container: str, timeout: int = 120) -> bool:
    """Poll ``docker inspect`` until ``.State.Running`` is "true"."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        proc = subprocess.run(
            ["docker", "inspect", "-f", "{{.State.Running}}", container],
            check=False,
            capture_output=True,
            text=True,
        )
        if proc.returncode == 0 and proc.stdout.strip().lower() == "true":
            return True
        time.sleep(1)
    return False


# ---------------------------------------------------------------------------
# Phase 1: SIGSTOP a non-primary peer master (STANDARD tier)
# ---------------------------------------------------------------------------


@pytest.mark.topology("cluster3")
def test_cluster_peer_sigstop_standard(topology, workload, request):
    """cluster_peer_sigstop_standard -- SIGSTOP a non-primary peer for
    ``PEER_SIGSTOP_SEC`` (TIER_STANDARD_SEC), then SIGCONT.  3x keepalive
    window: the reconnect SM is fully engaged but PRIMARY still answers
    minion traffic.
    """
    label = "cluster_peer_sigstop_standard"
    peer = _pick_non_primary_peer(topology)
    if peer is None:
        pytest.fail(
            f"{label}: no non-primary peer in masters={topology.spec.masters!r}"
        )

    before = topology.sample_minions()
    fault_start = time.monotonic()
    with sigstopped_container(topology, peer):
        time.sleep(PEER_SIGSTOP_SEC)
    fault_sec = int(time.monotonic() - fault_start)

    topology.assert_reconnect(
        label,
        fault_sec=fault_sec,
        before=before,
        notes=f"paused_peer={peer}",
        item=request.node,
    )


# ---------------------------------------------------------------------------
# Phase 1b: SIGSTOP a non-primary peer (BACKOFF tier, wider window)
# ---------------------------------------------------------------------------


@pytest.mark.topology("cluster3")
def test_cluster_peer_sigstop_backoff(topology, workload, request):
    """cluster_peer_sigstop_backoff -- SIGSTOP a non-primary peer for
    ``PEER_SIGSTOP_BACKOFF_SEC`` (TIER_BACKOFF_SEC).  Uses a wider
    ``RECOVER_STANDARD_SEC`` reconnect window because a minion
    mid-backoff may land in a long sleep when the peer resumes.
    """
    label = "cluster_peer_sigstop_backoff"
    peer = _pick_non_primary_peer(topology)
    if peer is None:
        pytest.fail(
            f"{label}: no non-primary peer in masters={topology.spec.masters!r}"
        )

    before = topology.sample_minions()
    fault_start = time.monotonic()
    with sigstopped_container(topology, peer):
        time.sleep(PEER_SIGSTOP_BACKOFF_SEC)
    fault_sec = int(time.monotonic() - fault_start)

    topology.assert_reconnect(
        label,
        fault_sec=fault_sec,
        before=before,
        window_sec=RECOVER_STANDARD_SEC,
        notes=f"paused_peer={peer} tier=backoff",
        item=request.node,
    )


# ---------------------------------------------------------------------------
# Phase 2: network-disconnect a non-primary peer
# ---------------------------------------------------------------------------


@pytest.mark.topology("cluster3")
def test_cluster_peer_unreachable(topology, workload, request):
    """cluster_peer_unreachable -- docker-network-disconnect a non-primary
    peer for ``PEER_UNREACHABLE_SEC`` (TIER_BACKOFF_SEC), then reconnect.
    """
    label = "cluster_peer_unreachable"
    peer = _pick_non_primary_peer(topology)
    if peer is None:
        pytest.fail(
            f"{label}: no non-primary peer in masters={topology.spec.masters!r}"
        )

    before = topology.sample_minions()
    fault_start = time.monotonic()
    with disconnected_from_network(topology, peer):
        time.sleep(PEER_UNREACHABLE_SEC)
    fault_sec = int(time.monotonic() - fault_start)

    topology.assert_reconnect(
        label,
        fault_sec=fault_sec,
        before=before,
        window_sec=RECOVER_STANDARD_SEC,
        notes=f"disconnected_peer={peer}",
        item=request.node,
    )


# ---------------------------------------------------------------------------
# Phase 3: cluster AES key rotation while workload is active
# ---------------------------------------------------------------------------


@pytest.mark.topology("cluster3")
def test_cluster_aes_rotation_under_load(topology, workload, request):
    """cluster_aes_rotation_under_load -- trigger an AES rotation on the
    primary master by writing a ``.dfn`` dropfile and wait for the
    Maintenance thread to pick it up.

    Entry point: there is NO ``salt-run cluster.rotate_cluster_secret``
    runner on 3008.x; ``rotate_cluster_secret`` is a classmethod on
    ``salt.master.SMaster`` invoked internally by
    ``Maintenance.handle_key_rotate`` when a ``.dfn`` dropfile matches
    the master's id (see ``salt/master.py:570-700`` and
    ``salt/master.py:1443`` for the ``rotate_cluster_aes_key`` dispatch).

    The dropfile MUST be mode exactly ``0400``: ``master.py:580`` gates
    on ``stats.st_mode == 0o100400``; anything else is logged as
    "Found dropfile with incorrect permissions, ignoring..." and the
    rotation never fires.  We write via ``umask 0277`` + explicit
    ``chmod 0400`` + atomic ``mv``.

    Nothing under ``/etc/salt/cluster-pki`` is touched.  The ``workload``
    fixture supplies continuous traffic for the "under load" dimension.
    The dropfile is removed in ``finally`` even if the maintenance tick
    consumed it (``rm -f`` is idempotent).
    """
    label = "cluster_aes_rotation_under_load"
    primary = topology.spec.primary_master

    # Read the master's id from /etc/salt/master -- for cluster3 that's
    # "salt-master-1".
    proc = topology.exec(
        primary,
        "sh",
        "-c",
        "awk '/^id:/ {print $2}' /etc/salt/master",
        check=False,
    )
    master_id = (proc.stdout or "").strip()
    if not master_id:
        pytest.fail(
            f"{label}: could not resolve master id from /etc/salt/master in {primary}"
        )

    before = topology.sample_minions()
    fault_start = time.monotonic()

    dfn_path = "/var/cache/salt/master/.dfn"
    try:
        # Atomic write with exact mode 0400:
        #   umask 0277 ensures the file starts out mode 0400 on creation,
        #   belt-and-braces chmod 0400 forces it even if umask is overridden,
        #   mv is atomic relative to the Maintenance thread's os.stat().
        write_sh = (
            "umask 0277; "
            f"printf '%s' '{master_id}' > {dfn_path}.next && "
            f"chmod 0400 {dfn_path}.next && "
            f"mv {dfn_path}.next {dfn_path}"
        )
        try:
            topology.exec(primary, "sh", "-c", write_sh, check=True)
        except subprocess.CalledProcessError as exc:
            pytest.fail(f"{label}: could not write {dfn_path} on {primary}: {exc}")

        # Wait for the Maintenance thread to pick it up.  loop_interval
        # defaults to 60s, so a single wait can miss the tick; but
        # assert_reconnect runs for another RECOVER_STANDARD_SEC below
        # so the total deadline covers worst-case.
        time.sleep(AES_PROPAGATION_WAIT_SEC)
        fault_sec = int(time.monotonic() - fault_start)

        topology.assert_reconnect(
            label,
            fault_sec=fault_sec,
            before=before,
            notes=f"aes_rotation_via_dropfile master_id={master_id}",
            item=request.node,
        )
    finally:
        # Idempotent cleanup: if Maintenance consumed the dropfile this
        # is a no-op (master.py:587 removes it after a successful
        # rotation); if the phase bailed before the tick, we remove it
        # ourselves so the next test starts with a clean slate.
        topology.exec(
            primary,
            "sh",
            "-c",
            f"rm -f {dfn_path} {dfn_path}.next",
            check=False,
        )


# ---------------------------------------------------------------------------
# Phase 4: haproxy backend flap
# ---------------------------------------------------------------------------


def _haproxy_socat_available(topology) -> bool:
    """Probe whether haproxy has socat + /var/run/haproxy.sock."""
    try:
        topology.exec(
            HAPROXY_CONTAINER,
            "sh",
            "-c",
            "command -v socat >/dev/null 2>&1 && [ -S /var/run/haproxy.sock ]",
            check=True,
        )
        return True
    except Exception:  # noqa: BLE001
        return False


@pytest.mark.topology("cluster3")
def test_cluster_haproxy_backend_flap(topology, workload, request):
    """cluster_haproxy_backend_flap -- flap one backend in haproxy.

    Preferred path: ``disable server masters-ret/<short>`` via the
    haproxy stats socket (requires socat + ``/var/run/haproxy.sock``;
    the stock haproxy.cfg does NOT expose the socket so this almost
    always falls through).

    Fallback: SIGSTOP the backing master container.  haproxy's
    health-check (``check inter 2000 rise 2 fall 3``) marks the backend
    down in ~6s; ``HAPROXY_FLAP_SEC`` (TIER_STANDARD_SEC) is much more
    than enough.
    """
    label = "cluster_haproxy_backend_flap"
    peer = _pick_non_primary_peer(topology)
    if peer is None:
        pytest.fail(
            f"{label}: no non-primary peer in masters={topology.spec.masters!r}"
        )

    # Backend/server name in haproxy.cfg uses the short service name,
    # stripped of the "c3-" compose-project prefix.
    server_short = peer[len("c3-") :] if peer.startswith("c3-") else peer

    before = topology.sample_minions()
    fault_start = time.monotonic()
    use_socat = _haproxy_socat_available(topology)

    if use_socat:
        # Try the control-plane path first; on any exception, fall back.
        disable_sh = (
            f"echo 'disable server masters-ret/{server_short}' "
            f"| socat stdio /var/run/haproxy.sock"
        )
        enable_sh = (
            f"echo 'enable server masters-ret/{server_short}' "
            f"| socat stdio /var/run/haproxy.sock"
        )
        try:
            topology.exec(HAPROXY_CONTAINER, "sh", "-c", disable_sh, check=True)
            try:
                time.sleep(HAPROXY_FLAP_SEC)
            finally:
                topology.exec(
                    HAPROXY_CONTAINER,
                    "sh",
                    "-c",
                    enable_sh,
                    check=False,
                )
            mode = "socat"
        except subprocess.CalledProcessError:
            use_socat = False

    if not use_socat:
        # Fallback: SIGSTOP the backing master; haproxy marks it DOWN.
        with sigstopped_container(topology, peer):
            time.sleep(HAPROXY_FLAP_SEC)
        mode = "sigstop"

    fault_sec = int(time.monotonic() - fault_start)
    topology.assert_reconnect(
        label,
        fault_sec=fault_sec,
        before=before,
        notes=f"haproxy_backend_flap mode={mode} target={peer}",
        item=request.node,
    )


# ---------------------------------------------------------------------------
# Phase 5: split-brain simulation (3-master quorum required)
# ---------------------------------------------------------------------------


@pytest.mark.topology("cluster3")
def test_cluster_split_brain_simulate(topology, workload, request):
    """cluster_split_brain_simulate -- disconnect PRIMARY_MASTER so the
    remaining 2 masters form a 2-of-3 quorum; haproxy steers minion
    traffic to the still-healthy backends.  Hold for ``SPLIT_BRAIN_SEC``
    (TIER_DEEPREC_SEC), reconnect primary, assert 3-of-3 recovery.

    Correctness: raft quorum math at ``raft/node.py:796`` is
    ``quorum = (len(voters) + 1) // 2 + 1``; for a 3-node cluster
    len(voters)=2 -> quorum=2, so a majority of 3 holds while master-1
    is partitioned out.  On reconnect, master-1 rejoins as follower
    (its term is <= leader's); it does NOT try to become leader
    unprompted.
    """
    label = "cluster_split_brain_simulate"
    if topology.spec.master_count < 3:
        pytest.skip(f"{label}: requires >=3 masters (got {topology.spec.master_count})")

    primary = topology.spec.primary_master
    before = topology.sample_minions()
    fault_start = time.monotonic()
    with disconnected_from_network(topology, primary):
        time.sleep(SPLIT_BRAIN_SEC)
    fault_sec = int(time.monotonic() - fault_start)

    topology.assert_reconnect(
        label,
        fault_sec=fault_sec,
        before=before,
        window_sec=RECOVER_STANDARD_SEC,
        notes=f"isolated={primary}",
        item=request.node,
    )


# ---------------------------------------------------------------------------
# Phase 6: rolling restart with traffic (parametrized over masters)
# ---------------------------------------------------------------------------


@pytest.mark.topology("cluster3")
def test_cluster_rolling_restart_with_traffic(
    topology,
    workload,
    request,
    rolling_master,
):
    """cluster_rolling_restart_with_traffic_<master> -- restart one
    master at a time (parametrized), pause ``ROLLING_WORKLOAD_BURST_SEC``
    with the ``workload`` fixture driving continuous traffic from
    PRIMARY_MASTER, then assert recovery before moving to the next
    master.

    Pacing: ``INTER_MASTER_WAIT_SEC`` (PACING_ROLLING_SEC) sleep at end
    of each iteration so a slow reconnect for master N doesn't bleed
    into the baseline for master N+1.  Bash scenario did this inside
    its for-loop; pytest spreads it across the parametrize boundary so
    each master still records its own ``results.jsonl`` row.
    """
    if topology.spec.master_count <= 1:
        pytest.skip("single-master topology")

    label = f"cluster_rolling_restart_with_traffic_{rolling_master}"
    before = topology.sample_minions()
    fault_start = time.monotonic()

    topology.restart(rolling_master)
    if not _wait_container_running(rolling_master):
        pytest.fail(f"{label}: {rolling_master} did not reach Running=true within 120s")

    # The ``workload`` fixture already supplies continuous test.ping
    # traffic from topology.spec.primary_master.  We just need to wait
    # out the burst window so the assertion fires after a representative
    # amount of mid-restart traffic has flowed.
    time.sleep(ROLLING_WORKLOAD_BURST_SEC)
    fault_sec = int(time.monotonic() - fault_start)

    # Pick the source container for the notes string: same pattern as
    # the bash scenario -- if we're restarting the primary, name a peer
    # as the burst-source; otherwise the primary.
    if rolling_master == topology.spec.primary_master:
        burst_source = _pick_non_primary_peer(topology) or topology.spec.primary_master
    else:
        burst_source = topology.spec.primary_master

    topology.assert_reconnect(
        label,
        fault_sec=fault_sec,
        before=before,
        notes=f"rolling burst_from={burst_source}",
        item=request.node,
    )

    # Pace between rolling steps so a slow reconnect for master N
    # doesn't bleed into the baseline for master N+1.
    time.sleep(INTER_MASTER_WAIT_SEC)


# ---------------------------------------------------------------------------
# Phase 7: multimaster-failover primary unreachable
# ---------------------------------------------------------------------------


@pytest.mark.topology("multimaster-failover")
def test_multimaster_primary_unreachable(topology, workload, request):
    """multimaster_primary_unreachable -- disconnect the failover-primary
    (``mm-salt-master-a``) for ``MM_PRIMARY_UNREACH_SEC`` (90s), then
    reconnect.  The minion must fail over to master-b during the hold
    (``master_alive_interval: 15`` + ``master_tries: -1`` from
    ``minion-failover.conf``) and the whole fleet must be reachable
    again once master-a returns.
    """
    label = "multimaster_primary_unreachable"
    primary = "mm-salt-master-a"
    before = topology.sample_minions()
    fault_start = time.monotonic()
    with disconnected_from_network(topology, primary):
        time.sleep(MM_PRIMARY_UNREACH_SEC)
    fault_sec = int(time.monotonic() - fault_start)

    topology.assert_reconnect(
        label,
        fault_sec=fault_sec,
        before=before,
        window_sec=RECOVER_STANDARD_SEC,
        notes=f"disconnected={primary}",
        item=request.node,
    )


# ---------------------------------------------------------------------------
# Phase 8: multimaster-hothot one-master tc partition
# ---------------------------------------------------------------------------


@pytest.mark.topology("multimaster-hothot")
def test_multimaster_hothot_one_master_tc_partition(topology, workload, request):
    """multimaster_hothot_one_master_tc_partition -- apply ``netem loss
    100%`` on the first master only (NOT both).  The second leg
    (master-b) must keep answering throughout.  Mid-fault we probe
    master-b to confirm the second leg is live.
    """
    label = "multimaster_hothot_one_master_tc_partition"
    masters = tuple(topology.spec.masters)
    if not masters:
        pytest.fail(f"{label}: no masters in spec.masters")

    first_master = masters[0]
    # Second master to probe mid-fault.
    probe_master = masters[1] if len(masters) > 1 else None

    before = topology.sample_minions()
    fault_start = time.monotonic()

    inflight_ok = True
    with inject_netem(
        topology,
        "loss 100%",
        container=first_master,
        iface=topology.spec.choke_iface,
    ):
        # Probe the second leg once; a hothot minion must answer there
        # even while the first master is black-holed.
        if probe_master is not None:
            try:
                topology.exec(
                    probe_master,
                    "salt",
                    f"--timeout={PING_TIMEOUT_SEC}",
                    "--out=json",
                    "*",
                    "test.ping",
                    check=True,
                    timeout=PING_TIMEOUT_SEC + 15,
                )
            except Exception:  # noqa: BLE001 -- probe failure is a WARN
                inflight_ok = False

        time.sleep(MM_HOTHOT_PARTITION_SEC)

    fault_sec = int(time.monotonic() - fault_start)
    topology.assert_reconnect(
        label,
        fault_sec=fault_sec,
        before=before,
        notes=(f"partition={first_master} " f"second_leg_ok={int(inflight_ok)}"),
        item=request.node,
    )


# ---------------------------------------------------------------------------
# Phase 9: multimaster staggered restart (both masters)
# ---------------------------------------------------------------------------


@pytest.mark.topology("multimaster-failover", "multimaster-hothot")
def test_multimaster_both_masters_restart_staggered(topology, workload, request):
    """multimaster_both_masters_restart_staggered -- ``docker restart``
    the first master, wait ``MM_STAGGERED_GAP_SEC`` (10s, NOT for
    recovery), then restart the second master before the first is back.
    Creates a brief overlap window where neither master is fully live;
    minion's ``master_tries: -1`` prevents give-up, so recovery is
    deterministic once at least one master returns.
    """
    label = "multimaster_both_masters_restart_staggered"
    if topology.spec.master_count < 2:
        pytest.skip(f"{label}: requires >=2 masters (got {topology.spec.master_count})")

    first_master = topology.spec.masters[0]
    second_master = topology.spec.masters[1]

    before = topology.sample_minions()
    fault_start = time.monotonic()

    topology.restart(first_master)
    time.sleep(MM_STAGGERED_GAP_SEC)
    topology.restart(second_master)

    if not _wait_container_running(first_master):
        pytest.fail(f"{label}: {first_master} did not reach Running=true within 120s")
    if not _wait_container_running(second_master):
        pytest.fail(f"{label}: {second_master} did not reach Running=true within 120s")

    fault_sec = int(time.monotonic() - fault_start)
    topology.assert_reconnect(
        label,
        fault_sec=fault_sec,
        before=before,
        window_sec=RECOVER_STANDARD_SEC,
        notes=f"staggered gap={MM_STAGGERED_GAP_SEC}s",
        item=request.node,
    )
