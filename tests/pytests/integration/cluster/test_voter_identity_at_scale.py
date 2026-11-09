"""
Integration regression for PR #70568 / issue #70567.

The Raft service's local ``node_id`` used to come from ``opts["interface"]``
while the join-handshake ``peer_id`` sent by non-founding masters came
from ``opts["id"]`` (via :func:`salt.cluster.node_id`).  When these two
names disagreed -- which they do in any deployment where masters have
dedicated hostnames separate from their bind address -- each non-founder
got registered in the committed voter set twice: once under its interface
and once under its id.

The PR's own unit tests and the existing three-master integration tests
on this conftest all run with ``id == interface`` (saltfactories' default
on loopback aliases).  The bug only manifests when the two names are
distinct AND the cluster has non-founding joiners.  A 5-master cluster
with explicit hostname ids is the scale at which the regression bites
hardest: ``opts["interface"] + opts["id"]`` for every master = 10 names,
and the pre-fix membership state machine winds up with 9 entries (the
4 non-founders double-count).

This test provisions 5 masters where each has a hostname-style id
different from its interface, waits for Raft to converge, and asserts
``salt-run cluster.members`` on every master returns exactly 5 voters --
the five ids, no interface aliases, and no duplicates.
"""

import contextlib
import json
import subprocess
import time

import pytest

import salt.utils.platform
from tests.conftest import FIPS_TESTRUN

pytestmark = [
    pytest.mark.slow_test,
    pytest.mark.timeout(360),
    # Coverage-init in every master subprocess adds enough per-fork cost
    # to push Raft election timing over its budget on shared runners.
    # The symbols under test are Raft membership, not election liveness,
    # so skipping subprocess coverage keeps the signal clean.
    pytest.mark.no_subprocess_coverage,
]


# Five masters on five distinct loopback addresses; each has an id that
# does NOT equal its interface so the pre-fix duplicate-voter bug has
# somewhere to land.
_MASTERS = [
    ("salt-master-1", "127.0.0.1"),
    ("salt-master-2", "127.0.0.2"),
    ("salt-master-3", "127.0.0.3"),
    ("salt-master-4", "127.0.0.4"),
    ("salt-master-5", "127.0.0.5"),
]


def _overrides(idx, pki_dir, cache_dir, pool_port):
    """Build cluster_* overrides for the ``idx``-th master."""
    my_id, my_addr = _MASTERS[idx]
    peers = [addr for i, (_id, addr) in enumerate(_MASTERS) if i != idx]
    return {
        # Explicit ``id`` so ``apply_master_config`` does not fall back to
        # the hostname and the id ends up distinct from the interface.
        "id": my_id,
        "interface": my_addr,
        "cluster_id": "voter_identity_cluster",
        "cluster_peers": peers,
        "cluster_pki_dir": str(pki_dir),
        "cache_dir": str(cache_dir),
        "cluster_pool_port": pool_port,
        "log_granular_levels": {
            "salt": "info",
            "salt.cluster": "debug",
            "salt.transport": "debug",
            "salt.channel": "debug",
        },
        "fips_mode": FIPS_TESTRUN,
        "publish_signing_algorithm": (
            "PKCS1v15-SHA224" if FIPS_TESTRUN else "PKCS1v15-SHA1"
        ),
        "cluster_encryption_algorithm": (
            "OAEP-SHA224" if FIPS_TESTRUN else "OAEP-SHA1"
        ),
    }


@pytest.fixture
def _loopback_aliases():
    """Bring up 127.0.0.4 and 127.0.0.5 on platforms that need it."""
    if salt.utils.platform.is_darwin() or salt.utils.platform.is_freebsd():
        for addr in ("127.0.0.4", "127.0.0.5"):
            subprocess.check_output(["ifconfig", "lo0", "alias", addr, "up"])


@pytest.fixture
def five_master_cluster(request, salt_factories, tmp_path, _loopback_aliases):
    """
    Bring up a 5-master cluster where each master has an id distinct
    from its interface.  Shared cluster_pki_dir + cache_dir so founders
    and non-founders agree on cluster keys.
    """
    pki = tmp_path / "pki"
    pki.mkdir()
    (pki / "peers").mkdir()
    cache = tmp_path / "cache"
    cache.mkdir()

    # Pick a single cluster_pool_port used by all five masters
    # (saltfactories' auto-selection assigns a different port per master
    # which would stop them from forming a Raft ring).
    from pytestskipmarkers.utils import ports  # pylint: disable=import-outside-toplevel

    pool_port = ports.get_unused_localhost_port()

    first_defaults = {
        "open_mode": True,
        "transport": request.config.getoption("--transport"),
    }
    masters = []
    # ``ExitStack`` guarantees LIFO teardown and avoids direct __enter__
    # /__exit__ calls (pylint C2801) while still letting us launch
    # masters one at a time inside a loop.
    with contextlib.ExitStack() as stack:
        for idx, (my_id, _addr) in enumerate(_MASTERS):
            config_overrides = _overrides(idx, pki, cache, pool_port)
            if idx > 0:
                # Match the first master's ret_port / publish_port so the
                # cluster conftest-style port alignment carries over.
                for key in ("ret_port", "publish_port"):
                    config_overrides[key] = masters[0].config[key]
            factory = salt_factories.salt_master_daemon(
                my_id,
                defaults=(
                    first_defaults
                    if idx == 0
                    else {
                        "open_mode": True,
                        "transport": masters[0].config["transport"],
                    }
                ),
                overrides=config_overrides,
                extra_cli_arguments_after_first_start_failure=["--log-level=info"],
            )
            stack.enter_context(factory.started(start_timeout=240))
            masters.append(factory)
        yield masters


def _members(master, timeout=60):
    """Return parsed ``salt-run cluster.members`` output for *master*."""
    cli = master.salt_run_cli(timeout=timeout)
    ret = cli.run("--output=json", "cluster.members")
    assert ret.returncode == 0, (
        f"cluster.members failed on {master.id}: "
        f"stdout={ret.stdout!r}, stderr={ret.stderr!r}"
    )
    return json.loads(ret.stdout)


def _wait_for_full_voter_set(masters, expected_count=5, timeout=120):
    """
    Poll each master's ``cluster.members`` output until every master
    reports ``voter_count >= expected_count`` (converged) or timeout.
    Returns the last-seen ``members`` dict from each master.
    """
    deadline = time.monotonic() + timeout
    latest = {}
    while time.monotonic() < deadline:
        latest = {}
        all_converged = True
        for m in masters:
            try:
                info = _members(m, timeout=30)
            except Exception as exc:  # pylint: disable=broad-except
                all_converged = False
                latest[m.id] = {"error": str(exc)}
                continue
            latest[m.id] = info
            if info.get("voter_count", 0) < expected_count:
                all_converged = False
        if all_converged:
            return latest
        time.sleep(2)
    return latest


def test_five_master_cluster_has_exactly_five_voters(five_master_cluster):
    """
    All five masters must converge on a voter set of exactly five
    entries -- the five configured ids, no interface aliases.

    Pre-fix (3008.x without PR #70568): the four non-founders register
    under both their id and their interface, producing a 9-entry voter
    set.  Assert ``voter_count == 5`` and ``set(voters) == set(ids)``
    on every master.
    """
    expected_ids = {my_id for my_id, _addr in _MASTERS}
    expected_addrs = {addr for _id, addr in _MASTERS}

    members_by_master = _wait_for_full_voter_set(
        five_master_cluster, expected_count=5, timeout=180
    )

    # First surface a diagnostic snapshot on any failure.
    snapshot = {
        mid: {
            "voter_count": info.get("voter_count"),
            "voters": sorted(info.get("voters") or []),
        }
        for mid, info in members_by_master.items()
    }

    for master_id, info in members_by_master.items():
        voter_count = info.get("voter_count")
        voters = set(info.get("voters") or [])

        assert voter_count == 5, (
            f"{master_id} reports voter_count={voter_count} "
            f"(expected 5). Full voters={sorted(voters)!r}.  "
            f"Regression of PR #70568: non-founding masters are being "
            f"registered under both their id and their interface in the "
            f"committed voter set.\n\nCluster snapshot:\n{snapshot!r}"
        )

        # Voters must be the hostname-style ids, not the loopback
        # addresses.  The pre-fix mixed set would show interface
        # addresses alongside (or instead of) ids.
        assert voters == expected_ids, (
            f"{master_id} voter set {sorted(voters)!r} != expected ids "
            f"{sorted(expected_ids)!r}.  Pre-fix PR #70568 would include "
            f"interface addresses {sorted(expected_addrs)!r} as extra "
            f"voter entries.\n\nCluster snapshot:\n{snapshot!r}"
        )

        # Defence in depth: assert there are no interface strings in the
        # voter set.  Even if ``voter_count == 5`` hit by coincidence,
        # a mix of ids + addresses would fail here.
        interface_leaks = voters & expected_addrs
        assert not interface_leaks, (
            f"{master_id} voter set leaked interface addresses "
            f"{sorted(interface_leaks)!r} -- the Raft service is keying "
            f"the local Node off opts['interface'] instead of "
            f"salt.cluster.node_id(opts).  Regression of PR #70568."
        )
