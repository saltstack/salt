"""Advanced netem + layer-2/3 fault battery -- pytest port of
``scenarios/netem_advanced.sh``.

Each phase applies a transport-layer pathology inside the choke
container on the choke interface, holds it for the configured tier
duration, clears it, then calls :meth:`Topology.assert_reconnect` with
the exact phase label from the bash scenario (preserved verbatim so
``results.jsonl`` stays analyzer-compatible).

Phase -> test mapping (same labels as the bash scenario, passed as the
first arg to ``assert_reconnect``):

    netem_reorder_30                 test_netem_reorder_30
    netem_duplicate_20               test_netem_duplicate_20
    netem_corrupt_5                  test_netem_corrupt_5
    netem_mtu_drop                   test_netem_mtu_drop
    netem_rate_limit_1mbit           test_netem_rate_limit_1mbit
    netem_asymmetric_outbound        test_netem_asymmetric_outbound
    netem_asymmetric_outbound_deep   test_netem_asymmetric_outbound_deep
    netem_asymmetric_inbound         test_netem_asymmetric_inbound
    netem_asymmetric_inbound_deep    test_netem_asymmetric_inbound_deep
    netem_syn_flood_simulation       test_netem_syn_flood_simulation
    netem_split_horizon_cluster      test_netem_split_horizon_cluster
        (gated by @pytest.mark.topology("cluster3"))
"""

# pylint: disable=broad-exception-caught  # Resiliency: test cleanup catches Exception deliberately to avoid masking the real verdict

from __future__ import annotations

import logging
import subprocess
import time

import pytest

from tests.resiliency.durations import (
    RECOVER_STANDARD_SEC,
    TIER_DEEPREC_SEC,
    TIER_STANDARD_SEC,
)
from tests.resiliency.lib.injectors import (
    drop_interface_mtu,
    inject_ingress_netem,
    inject_netem,
    inject_tbf,
)

log = logging.getLogger("resiliency.netem_advanced")


MASTER_RET_PORT = 44506


# ---------------------------------------------------------------------------
# Plain netem phases (symmetric root qdisc)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "label, netem_args",
    [
        ("netem_reorder_30", "delay 10ms reorder 30% 50%"),
        ("netem_duplicate_20", "duplicate 20%"),
        ("netem_corrupt_5", "corrupt 5%"),
    ],
    ids=["reorder_30", "duplicate_20", "corrupt_5"],
)
def test_netem_symmetric(topology, request, label, netem_args):
    """netem_reorder_30 / netem_duplicate_20 / netem_corrupt_5 --
    straightforward root-qdisc netem for TIER_STANDARD_SEC.
    """
    before = topology.sample_minions()
    with inject_netem(topology, netem_args):
        time.sleep(TIER_STANDARD_SEC)
    topology.assert_reconnect(
        label,
        fault_sec=TIER_STANDARD_SEC,
        before=before,
        notes=f"netem {netem_args}",
        item=request.node,
    )


# ---------------------------------------------------------------------------
# MTU drop (raw link, not netem)
# ---------------------------------------------------------------------------


def test_netem_mtu_drop(topology, request):
    """netem_mtu_drop -- shrink $CHOKE_IFACE MTU to 576 (IPv4 minimum)
    for TIER_STANDARD_SEC, then restore to 1500.
    """
    label = "netem_mtu_drop"
    before = topology.sample_minions()
    with drop_interface_mtu(topology, 576):
        time.sleep(TIER_STANDARD_SEC)
    topology.assert_reconnect(
        label,
        fault_sec=TIER_STANDARD_SEC,
        before=before,
        notes=f"link mtu dropped to 576 on {topology.spec.choke_container}",
        item=request.node,
    )


# ---------------------------------------------------------------------------
# Rate-limit via tbf
# ---------------------------------------------------------------------------


def test_netem_rate_limit_1mbit(topology, request):
    """netem_rate_limit_1mbit -- tbf rate 1mbit burst 32kbit latency 400ms
    for TIER_STANDARD_SEC.
    """
    label = "netem_rate_limit_1mbit"
    before = topology.sample_minions()
    with inject_tbf(topology, rate="1mbit", burst="32kbit", latency="400ms"):
        time.sleep(TIER_STANDARD_SEC)
    topology.assert_reconnect(
        label,
        fault_sec=TIER_STANDARD_SEC,
        before=before,
        notes="tbf rate 1mbit burst 32kbit latency 400ms",
        item=request.node,
    )


# ---------------------------------------------------------------------------
# Asymmetric outbound (egress-only) -- standard + deep variants
# ---------------------------------------------------------------------------


def test_netem_asymmetric_outbound(topology, request):
    """netem_asymmetric_outbound -- root netem loss 100%, egress only,
    held for TIER_STANDARD_SEC.
    """
    label = "netem_asymmetric_outbound"
    before = topology.sample_minions()
    with inject_netem(topology, "loss 100%"):
        time.sleep(TIER_STANDARD_SEC)
    topology.assert_reconnect(
        label,
        fault_sec=TIER_STANDARD_SEC,
        before=before,
        notes="egress-only loss 100% via root netem",
        item=request.node,
    )


def test_netem_asymmetric_outbound_deep(topology, request):
    """netem_asymmetric_outbound_deep -- same fault held across
    TIER_DEEPREC_SEC; reconnect window widened to RECOVER_STANDARD_SEC.
    """
    label = "netem_asymmetric_outbound_deep"
    before = topology.sample_minions()
    with inject_netem(topology, "loss 100%"):
        time.sleep(TIER_DEEPREC_SEC)
    topology.assert_reconnect(
        label,
        fault_sec=TIER_DEEPREC_SEC,
        before=before,
        window_sec=RECOVER_STANDARD_SEC,
        notes="egress-only loss 100% via root netem (deep)",
        item=request.node,
    )


# ---------------------------------------------------------------------------
# Asymmetric inbound (ifb + mirred ingress redirect) -- standard + deep
# ---------------------------------------------------------------------------


def test_netem_asymmetric_inbound(topology, request):
    """netem_asymmetric_inbound -- ifb0 + mirred ingress redirect +
    netem loss 100% on ifb0 egress; drops ingress only.  Held for
    TIER_STANDARD_SEC.
    """
    label = "netem_asymmetric_inbound"
    before = topology.sample_minions()
    with inject_ingress_netem(topology, "loss 100%"):
        time.sleep(TIER_STANDARD_SEC)
    topology.assert_reconnect(
        label,
        fault_sec=TIER_STANDARD_SEC,
        before=before,
        notes="ingress-only loss 100% via ifb0 mirred redirect",
        item=request.node,
    )


def test_netem_asymmetric_inbound_deep(topology, request):
    """netem_asymmetric_inbound_deep -- same ifb/mirred ingress drop
    held across TIER_DEEPREC_SEC; reconnect window widened to
    RECOVER_STANDARD_SEC.
    """
    label = "netem_asymmetric_inbound_deep"
    before = topology.sample_minions()
    with inject_ingress_netem(topology, "loss 100%"):
        time.sleep(TIER_DEEPREC_SEC)
    topology.assert_reconnect(
        label,
        fault_sec=TIER_DEEPREC_SEC,
        before=before,
        window_sec=RECOVER_STANDARD_SEC,
        notes="ingress-only loss 100% via ifb0 mirred redirect (deep)",
        item=request.node,
    )


# ---------------------------------------------------------------------------
# SYN flood (hping3)
# ---------------------------------------------------------------------------


def _container_ipv4(container: str) -> str:
    """Return the first IPv4 address on any attached docker network,
    or "" on failure.  Mirrors ``container_ip()`` in the bash scenario.
    """
    try:
        out = subprocess.run(
            [
                "docker",
                "inspect",
                "-f",
                "{{range .NetworkSettings.Networks}}{{.IPAddress}} {{end}}",
                container,
            ],
            check=True,
            capture_output=True,
            text=True,
        ).stdout
    except subprocess.CalledProcessError:
        return ""
    for tok in out.split():
        tok = tok.strip()
        if tok:
            return tok
    return ""


def _install_hping3(topology, container: str) -> bool:
    """Best-effort apt/apk/dnf/yum install of hping3 inside ``container``.
    Returns True iff ``hping3`` is on PATH afterwards.
    """
    check_cmd = "command -v hping3 >/dev/null 2>&1"
    try:
        topology.exec(container, "sh", "-c", check_cmd, check=True)
        return True
    except subprocess.CalledProcessError:
        pass
    except Exception:  # noqa: BLE001
        pass

    install_sh = (
        "(command -v apt-get >/dev/null 2>&1 "
        "&& apt-get update -qq >/dev/null 2>&1 "
        "&& apt-get install -y --no-install-recommends hping3 "
        ">/dev/null 2>&1) "
        "|| (command -v apk >/dev/null 2>&1 "
        "&& apk add --no-cache hping3 >/dev/null 2>&1) "
        "|| (command -v dnf >/dev/null 2>&1 "
        "&& dnf install -y hping3 >/dev/null 2>&1) "
        "|| (command -v yum >/dev/null 2>&1 "
        "&& yum install -y hping3 >/dev/null 2>&1) "
        "|| true"
    )
    try:
        topology.exec(container, "sh", "-c", install_sh, check=False)
    except Exception:  # noqa: BLE001
        return False
    try:
        topology.exec(container, "sh", "-c", check_cmd, check=True)
        return True
    except Exception:  # noqa: BLE001
        return False


def test_netem_syn_flood_simulation(topology, request):
    """netem_syn_flood_simulation -- spawn ``hping3 --flood --syn`` from
    the choke container against the primary master's return port
    (44506) for TIER_STANDARD_SEC, then kill the flood and assert
    reconnect.

    Skipped if hping3 can't be installed in the choke container.
    """
    label = "netem_syn_flood_simulation"
    choke = topology.spec.choke_container
    target_ip = _container_ipv4(topology.spec.primary_master)
    if not target_ip:
        pytest.skip(f"could not resolve IP for {topology.spec.primary_master}")

    if not _install_hping3(topology, choke):
        pytest.skip(f"hping3 unavailable in {choke}: install failed")

    before = topology.sample_minions()

    # ``docker exec -d`` detaches from the daemon side; we recover the
    # PID via pgrep afterwards.  Same pattern the bash port uses.
    log.info(
        "netem_syn_flood_simulation: launching hping3 --flood --syn -p %d %s in %s",
        MASTER_RET_PORT,
        target_ip,
        choke,
    )
    try:
        subprocess.run(
            [
                "docker",
                "exec",
                "-d",
                choke,
                "sh",
                "-c",
                f"hping3 --flood --syn -p {MASTER_RET_PORT} {target_ip} "
                ">/dev/null 2>&1 &",
            ],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"docker exec -d hping3 failed in {choke}: {exc}")

    # Give the daemon a moment to fork hping3; then look it up.
    time.sleep(1)
    try:
        pgrep = topology.exec(
            choke,
            "sh",
            "-c",
            "pgrep -f 'hping3 --flood' | head -1",
            check=False,
        )
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"pgrep failed in {choke}: {exc}")
    hping_pid = (pgrep.stdout or "").strip()

    try:
        if not hping_pid:
            pytest.skip(f"hping3 did not start in {choke}")
        log.info(
            "netem_syn_flood_simulation: hping3 running pid=%s",
            hping_pid,
        )
        time.sleep(TIER_STANDARD_SEC)
    finally:
        # Belt + suspenders kill: explicit PID then pkill by name.
        if hping_pid:
            try:
                topology.exec(
                    choke,
                    "sh",
                    "-c",
                    f"kill -9 {hping_pid} 2>/dev/null || true",
                    check=False,
                )
            except Exception:  # noqa: BLE001
                pass
        try:
            topology.exec(
                choke,
                "sh",
                "-c",
                "pkill -9 -f hping3 2>/dev/null || true",
                check=False,
            )
        except Exception:  # noqa: BLE001
            pass

    topology.assert_reconnect(
        label,
        fault_sec=TIER_STANDARD_SEC,
        before=before,
        notes=(f"hping3 --flood --syn -p {MASTER_RET_PORT} {target_ip}"),
        item=request.node,
    )


# ---------------------------------------------------------------------------
# Split horizon -- cluster3-only
# ---------------------------------------------------------------------------


@pytest.mark.topology("cluster3")
def test_netem_split_horizon_cluster(topology, request):
    """netem_split_horizon_cluster -- tc u32 drop filter on the haproxy's
    egress targeting one specific backend master's IP; the other two
    backends and the VIP stay healthy.

    The "sick" backend is the LAST entry in ``spec.masters`` so the
    primary (first entry, which the salt CLI runs on) stays reachable
    for ``assert_reconnect``.  Held for TIER_DEEPREC_SEC with the
    reconnect window widened to RECOVER_STANDARD_SEC.
    """
    label = "netem_split_horizon_cluster"
    choke = topology.spec.choke_container
    iface = topology.spec.choke_iface

    masters = tuple(topology.spec.masters)
    if len(masters) < 2:
        pytest.skip(f"split_horizon needs multiple backends, got {len(masters)}")
    sick_master = masters[-1]
    sick_ip = _container_ipv4(sick_master)
    if not sick_ip:
        pytest.skip(f"could not resolve IP for {sick_master}")

    # Probe tc first so we skip (not fail) on unprivileged choke images.
    try:
        topology.exec(
            choke,
            "sh",
            "-c",
            "command -v tc >/dev/null 2>&1",
            check=True,
        )
    except subprocess.CalledProcessError:
        pytest.skip(f"tc unavailable in {choke}: cannot split-horizon")

    log.info(
        "netem_split_horizon_cluster: tc u32 drop to %s (%s) via %s",
        sick_master,
        sick_ip,
        choke,
    )

    setup_sh = (
        "set -e; "
        f"tc qdisc replace dev {iface} root handle 1: prio; "
        f"tc filter add dev {iface} parent 1: protocol ip prio 1 u32 "
        f"match ip dst {sick_ip}/32 action drop"
    )
    try:
        topology.exec(choke, "sh", "-c", setup_sh, check=True)
    except subprocess.CalledProcessError as exc:
        # Best-effort cleanup then skip.
        try:
            topology.exec(
                choke,
                "sh",
                "-c",
                f"tc qdisc del dev {iface} root 2>/dev/null || true",
                check=False,
            )
        except Exception:  # noqa: BLE001
            pass
        pytest.skip(f"tc u32 drop setup failed in {choke}: {exc}")

    before = topology.sample_minions()
    try:
        time.sleep(TIER_DEEPREC_SEC)
    finally:
        try:
            topology.exec(
                choke,
                "sh",
                "-c",
                f"tc qdisc del dev {iface} root 2>/dev/null || true",
                check=False,
            )
        except Exception:  # noqa: BLE001
            pass

    topology.assert_reconnect(
        label,
        fault_sec=TIER_DEEPREC_SEC,
        before=before,
        window_sec=RECOVER_STANDARD_SEC,
        notes=(f"tc u32 drop to {sick_master} {sick_ip} via {choke} (deep)"),
        item=request.node,
    )
