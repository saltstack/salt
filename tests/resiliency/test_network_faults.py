"""Pytest port of ``tests/resiliency/scenarios/network_faults.sh``.

Walks the minion-side network layer through a battery of transient
faults (latency, loss, jitter+loss, full partition at four hold tiers,
TCP RST injection, container pause, DNS flap).  After each phase the
fault is cleared and ``Topology.assert_reconnect`` verifies every
minion in ``spec.minion_ids`` answers ``test.ping`` within the
scenario's recovery window AND that per-minute RSS slope stays under
``RSS_LEAK_KB_PER_MIN``.

Phase labels (preserved verbatim from the bash scenario so the
``results.jsonl`` schema stays stable for the analyzer):

    network_latency                  netem delay 200ms 50ms distribution normal
    network_loss_10                  netem loss 10%
    network_jitter_loss              netem delay 100ms 40ms distribution normal loss 5%
    network_partition_full           netem loss 100%, STANDARD / RECOVER_FAST
    network_partition_sub_keepalive  netem loss 100%, SUBKEEPALIVE / RECOVER_FAST
    network_partition_first_miss     netem loss 100%, FIRSTMISS / RECOVER_FAST
    network_partition_deep           netem loss 100%, DEEPREC / RECOVER_STANDARD
    network_tcp_reset                iptables REJECT --reject-with tcp-reset
    network_pause_master             docker pause $PRIMARY_MASTER
    network_dns_flap                 /etc/hosts poison (skipped on single)

The DNS-flap case is excluded on topology ``single`` via
``@pytest.mark.topology`` because the minion resolves ``salt-master``
through docker's embedded DNS, not ``/etc/hosts`` -- rewriting it
doesn't flap resolution there.  conftest's
``pytest_collection_modifyitems`` turns that marker into a
``skipped_for_topology`` row in ``results.jsonl``.
"""

from __future__ import annotations

import contextlib
import time

import pytest

from tests.resiliency.durations import (
    RECOVER_FAST_SEC,
    RECOVER_STANDARD_SEC,
    TIER_DEEPREC_SEC,
    TIER_FIRSTMISS_SEC,
    TIER_STANDARD_SEC,
    TIER_SUBKEEPALIVE_SEC,
)
from tests.resiliency.lib.injectors import (
    dns_hosts_poisoned,
    inject_netem,
    paused_container,
    tcp_reset_from_minions,
)

# pylint: disable=broad-exception-caught
# Resiliency tests catch broad Exception in cleanup paths deliberately;
# a test-cleanup failure must never mask the real test verdict.


# ---------------------------------------------------------------------------
# netem phases (latency / loss / jitter+loss)
# ---------------------------------------------------------------------------


def test_network_latency(topology, workload, request):
    before = topology.sample_minions()
    with inject_netem(topology, "delay 200ms 50ms distribution normal"):
        time.sleep(TIER_STANDARD_SEC)
    topology.assert_reconnect(
        "network_latency",
        fault_sec=TIER_STANDARD_SEC,
        before=before,
        window_sec=RECOVER_FAST_SEC,
        notes="netem delay 200ms 50ms distribution normal",
        item=request.node,
    )


def test_network_loss_10(topology, workload, request):
    before = topology.sample_minions()
    with inject_netem(topology, "loss 10%"):
        time.sleep(TIER_STANDARD_SEC)
    topology.assert_reconnect(
        "network_loss_10",
        fault_sec=TIER_STANDARD_SEC,
        before=before,
        window_sec=RECOVER_FAST_SEC,
        notes="netem loss 10%",
        item=request.node,
    )


def test_network_jitter_loss(topology, workload, request):
    before = topology.sample_minions()
    with inject_netem(topology, "delay 100ms 40ms distribution normal loss 5%"):
        time.sleep(TIER_STANDARD_SEC)
    topology.assert_reconnect(
        "network_jitter_loss",
        fault_sec=TIER_STANDARD_SEC,
        before=before,
        window_sec=RECOVER_FAST_SEC,
        notes="netem delay 100ms 40ms distribution normal loss 5%",
        item=request.node,
    )


# ---------------------------------------------------------------------------
# Full-partition (loss 100%) at four hold tiers
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "label,hold_sec,recovery_sec",
    [
        ("network_partition_sub_keepalive", TIER_SUBKEEPALIVE_SEC, RECOVER_FAST_SEC),
        ("network_partition_first_miss", TIER_FIRSTMISS_SEC, RECOVER_FAST_SEC),
        ("network_partition_full", TIER_STANDARD_SEC, RECOVER_FAST_SEC),
        ("network_partition_deep", TIER_DEEPREC_SEC, RECOVER_STANDARD_SEC),
    ],
    ids=[
        "network_partition_sub_keepalive",
        "network_partition_first_miss",
        "network_partition_full",
        "network_partition_deep",
    ],
)
def test_network_partition(topology, workload, label, hold_sec, recovery_sec, request):
    before = topology.sample_minions()
    with inject_netem(topology, "loss 100%"):
        time.sleep(hold_sec)
    # Use the explicit label from the parametrize tuple; the pytest
    # nodeid id is only for human-readable collection output.
    topology.assert_reconnect(
        label,
        fault_sec=hold_sec,
        before=before,
        window_sec=recovery_sec,
        notes="netem loss 100%",
        item=request.node,
    )


# ---------------------------------------------------------------------------
# TCP RST injection
# ---------------------------------------------------------------------------


def test_network_tcp_reset(topology, workload, request):
    before = topology.sample_minions()
    with tcp_reset_from_minions(topology, dport=44506):
        time.sleep(TIER_STANDARD_SEC)
    topology.assert_reconnect(
        "network_tcp_reset",
        fault_sec=TIER_STANDARD_SEC,
        before=before,
        window_sec=RECOVER_FAST_SEC,
        notes="iptables REJECT tcp-reset dport 44506",
        item=request.node,
    )


# ---------------------------------------------------------------------------
# Container pause (full blackhole on $PRIMARY_MASTER)
# ---------------------------------------------------------------------------


def test_network_pause_master(topology, workload, request):
    before = topology.sample_minions()
    primary = topology.spec.primary_master
    with paused_container(topology, primary):
        time.sleep(TIER_STANDARD_SEC)
    topology.assert_reconnect(
        "network_pause_master",
        fault_sec=TIER_STANDARD_SEC,
        before=before,
        window_sec=RECOVER_FAST_SEC,
        notes=f"docker pause {primary}",
        item=request.node,
    )


# ---------------------------------------------------------------------------
# DNS flap via /etc/hosts poisoning (skipped on single)
# ---------------------------------------------------------------------------


def _dns_poison_names(topology) -> list[str]:
    """Build the list of hostnames to poison inside each minion.

    Mirrors the bash phase 7 logic: for every master container name
    include both the full name and the "short" form with the ``c3-``
    or ``mm-`` compose-project prefix stripped.  On cluster3 also
    poison the haproxy VIP (both full and short).
    """
    names: list[str] = []
    for master in topology.spec.masters:
        short = master
        if short.startswith("c3-"):
            short = short[len("c3-") :]
        elif short.startswith("mm-"):
            short = short[len("mm-") :]
        elif short.startswith("c5-"):
            # cluster5 has no haproxy VIP and uses the same strip
            # convention; the bash script didn't handle c5- explicitly
            # but the compose-service shortname applies equivalently.
            short = short[len("c5-") :]
        elif short.startswith("rs-"):
            short = short[len("rs-") :]
        names.append(master)
        if short != master:
            names.append(short)

    if topology.spec.name == "cluster3":
        names.extend(["c3-salt-haproxy", "salt-haproxy"])

    # Deduplicate while preserving order.
    seen: set[str] = set()
    out: list[str] = []
    for n in names:
        if n not in seen:
            seen.add(n)
            out.append(n)
    return out


@pytest.mark.topology(
    "cluster3",
    "cluster5",
    "multimaster-failover",
    "multimaster-hothot",
    "syndic",
)
def test_network_dns_flap(topology, workload, request):
    poison_names = _dns_poison_names(topology)
    before = topology.sample_minions()
    with contextlib.ExitStack() as stack:
        for minion in topology.spec.minion_containers:
            stack.enter_context(dns_hosts_poisoned(topology, minion, poison_names))
        time.sleep(TIER_STANDARD_SEC)
    topology.assert_reconnect(
        "network_dns_flap",
        fault_sec=TIER_STANDARD_SEC,
        before=before,
        window_sec=RECOVER_FAST_SEC,
        notes="/etc/hosts poisoned with 127.0.0.1 for master hostnames",
        item=request.node,
    )
