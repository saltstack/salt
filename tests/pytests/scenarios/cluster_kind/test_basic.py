"""
Basic Salt cluster scenario on a real (in-Docker) Kubernetes cluster.

These tests are the minimum smoke that proves the
``cluster_kind`` fixture set is wired up end-to-end:

1. kind cluster comes up
2. three salt-master Pods become Ready
3. inter-master DNS works (each master can resolve its peers)
4. ``salt-key -L`` runs inline inside a master Pod
5. one master logs ``BECOMING LEADER`` for some Raft term within
   the election timeout

Heavy multi-minion / late-joiner scenarios stay in the existing
``tests/pytests/integration/cluster/`` and ``scenarios/cluster/``
suites for now — they're cheaper there.  This file is the scaffold to
grow real network-partition / multi-IP tests on top of.
"""

import re
import time

import pytest

from tests.pytests.scenarios.cluster_kind.conftest import (
    CLUSTER_SUBDOMAIN,
    MASTER_NAMES,
)

pytestmark = [pytest.mark.slow_test]


def test_kind_masters_become_ready(cluster_masters):
    """All three master Pods report Ready (the fixture itself enforces
    this; this test is the explicit assertion that documents the
    contract)."""
    assert set(cluster_masters) == set(MASTER_NAMES)


def test_inter_master_dns_resolves(kind_cluster, cluster_masters, salt_in_pod):
    """Each master can resolve its two peers via the headless service."""
    for src in MASTER_NAMES:
        for dst in MASTER_NAMES:
            if dst == src:
                continue
            target = f"{dst}.{CLUSTER_SUBDOMAIN}.{kind_cluster.namespace}"
            proc = salt_in_pod(src, "getent", "hosts", target, timeout=15)
            assert (
                proc.returncode == 0
            ), f"{src} could not resolve peer {target}: {proc.stderr or proc.stdout}"


def test_salt_key_list_runs_inside_pod(cluster_masters, salt_in_pod):
    """``salt-key -L`` runs successfully inside a master Pod and lists
    the four key buckets the cluster master sets up."""
    proc = salt_in_pod(MASTER_NAMES[0], "salt-key", "-L", timeout=30)
    assert proc.returncode == 0, proc.stderr or proc.stdout
    out = proc.stdout
    for bucket in ("Accepted Keys", "Denied Keys", "Unaccepted Keys", "Rejected Keys"):
        assert bucket in out, f"Missing {bucket} in salt-key output:\n{out}"


_BECOMING_LEADER_RE = re.compile(r"Node \S+ BECOMING LEADER for term \d+")


def test_a_leader_is_elected(kind_cluster, cluster_masters):
    """
    Within 60 s of all three masters reaching Ready, exactly one of
    them must log ``BECOMING LEADER for term N``.  Election timing in
    a real-network kind cluster is more variable than on loopback, so
    this is a generous deadline.
    """
    deadline = time.monotonic() + 60
    while time.monotonic() < deadline:
        leaders = []
        for name in MASTER_NAMES:
            proc = kind_cluster.kubectl(
                "logs",
                "-n",
                kind_cluster.namespace,
                name,
                "--tail=2000",
                check=False,
                timeout=15,
            )
            if proc.returncode != 0:
                continue
            if _BECOMING_LEADER_RE.search(proc.stdout):
                leaders.append(name)
        if leaders:
            assert (
                len(leaders) == 1
            ), f"Expected one leader, found {len(leaders)}: {leaders}"
            return
        time.sleep(2)
    # Diagnostic: dump the last 80 lines from each master so failures
    # show *why* no election ever fired (network reachability, salt
    # config error, missing peer key, etc.).
    diagnostic = []
    for name in MASTER_NAMES:
        proc = kind_cluster.kubectl(
            "logs",
            "-n",
            kind_cluster.namespace,
            name,
            "--tail=80",
            check=False,
            timeout=15,
        )
        diagnostic.append(f"--- {name} (rc={proc.returncode}) ---")
        diagnostic.append(proc.stdout or "<empty stdout>")
        if proc.stderr:
            diagnostic.append(f"--- {name} stderr ---")
            diagnostic.append(proc.stderr)
    pytest.fail(
        "No master logged 'BECOMING LEADER' within the election deadline.\n"
        + "\n".join(diagnostic)
    )
