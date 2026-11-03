"""
Regression test for saltstack/salt issue #70401.

On a cluster with ``cluster_isolated_filesystem: True`` (each master has
its own ``cluster_pki_dir`` / ``cache_dir``), running
``salt-key -a <minion_id>`` on master_1 accepts the key locally but does
NOT propagate the acceptance to the other cluster peers.  Deletions
(``salt-key -d``) and auto-accept (``open_mode: True``) both work; the
CLI-driven ``accept`` path is the only one broken.

Root cause (see https://github.com/saltstack/salt/issues/70401):

  * ``salt.key.Key.change_state`` fires ``salt/key`` with
    ``act=self.DIR_MAP[to_state]``, which produces the long-form string
    (``"accepted"`` / ``"rejected"`` / ``"pending"``).
  * ``salt.master.EventMonitor._PEER_KEY_STATE`` keys off the short-form
    (``"accept"`` / ``"reject"`` / ``"pend"``), so
    ``_apply_peer_key_change`` falls through to the ``state is None``
    guard and silently drops the event on every peer.

The auto-accept path in ``AESFuncs._auth`` fires ``act="accept"``
directly, which is why the existing ``test_isolated_cluster.py``
coverage (which uses ``open_mode=True``) does not catch this.

This test MUST fail on current master; it is the executable spec for
the fix.  Do not xfail — a silent xfail hides the bug from the next
person running the suite.
"""

import time

import pytest

import salt.cache
from tests.conftest import FIPS_TESTRUN

pytestmark = [
    pytest.mark.slow_test,
    pytest.mark.no_subprocess_coverage,
]


def _fetch_minion_key(master, minion_id):
    cache = salt.cache.Cache(master.config, driver=master.config["keys.cache_driver"])
    return cache.fetch("keys", minion_id)


def _wait_for_state(master, minion_id, state, timeout=30):
    deadline = time.monotonic() + timeout
    entry = None
    while time.monotonic() < deadline:
        entry = _fetch_minion_key(master, minion_id)
        if entry and entry.get("state") == state:
            return entry
        time.sleep(0.5)
    return entry


@pytest.fixture
def pending_minion_on_master_1(cluster_master_1_isolated_closed):
    config_defaults = {
        "transport": cluster_master_1_isolated_closed.config["transport"],
    }
    port = cluster_master_1_isolated_closed.config["ret_port"]
    addr = cluster_master_1_isolated_closed.config["interface"]
    config_overrides = {
        "master": f"{addr}:{port}",
        "test.foo": "baz",
        # Short per-attempt timeout so the minion keeps retrying auth
        # instead of blocking the whole test behind a long first attempt.
        "auth_timeout": 5,
        "auth_tries": 240,
        "log_granular_levels": {
            "salt": "info",
            "salt.transport": "debug",
            "salt.channel": "debug",
            "salt.utils.event": "debug",
        },
        "fips_mode": FIPS_TESTRUN,
        "encryption_algorithm": "OAEP-SHA224" if FIPS_TESTRUN else "OAEP-SHA1",
        "signing_algorithm": "PKCS1v15-SHA224" if FIPS_TESTRUN else "PKCS1v15-SHA1",
    }
    factory = cluster_master_1_isolated_closed.salt_minion_daemon(
        "cluster-minion-pending-iso",
        defaults=config_defaults,
        overrides=config_overrides,
        extra_cli_arguments_after_first_start_failure=["--log-level=info"],
    )
    # The default start check waits for ``salt/minion/<id>/start``, which
    # never fires until the key is accepted — the whole point of this
    # test is to accept it *after* the minion is up and pending.  Drop
    # the start-event check so ``start()`` returns as soon as the
    # subprocess is alive; the test polls master_1's pending bucket to
    # confirm readiness.
    factory._start_checks_callbacks = []  # pylint: disable=protected-access
    factory.start(start_timeout=15, max_start_attempts=1)
    try:
        yield factory
    finally:
        factory.terminate()


def test_salt_key_accept_replicates_to_isolated_peers(
    cluster_master_1_isolated_closed,
    cluster_master_2_isolated_closed,
    cluster_master_3_isolated_closed,
    pending_minion_on_master_1,
):
    """
    ``salt-key -a <minion_id> -y`` on master_1 must replicate the
    accepted-state entry to masters 2 and 3 under
    ``cluster_isolated_filesystem: True``.  Currently fails because
    ``EventMonitor._PEER_KEY_STATE`` keys on short-form ``"accept"``
    but ``Key.change_state`` fires long-form ``"accepted"``.
    See https://github.com/saltstack/salt/issues/70401.
    """
    minion_id = pending_minion_on_master_1.id
    masters = [
        cluster_master_1_isolated_closed,
        cluster_master_2_isolated_closed,
        cluster_master_3_isolated_closed,
    ]

    pending = _wait_for_state(
        cluster_master_1_isolated_closed, minion_id, "pending", timeout=60
    )
    assert pending and pending.get("state") == "pending", (
        f"Minion {minion_id!r} never reached pending on master_1 "
        f"(last entry={pending!r})"
    )

    salt_key = cluster_master_1_isolated_closed.salt_key_cli(timeout=30)
    ret = salt_key.run("-y", "-a", minion_id)
    assert ret.returncode == 0, (
        f"salt-key -a exited {ret.returncode}; stdout={ret.stdout!r} "
        f"stderr={ret.stderr!r}"
    )

    master_1_entry = _wait_for_state(
        cluster_master_1_isolated_closed, minion_id, "accepted", timeout=15
    )
    assert master_1_entry and master_1_entry.get("state") == "accepted", (
        f"salt-key -a didn't persist the accepted state locally on "
        f"master_1 (entry={master_1_entry!r})"
    )

    deadline = time.monotonic() + 30
    peer_entries = {}
    while time.monotonic() < deadline:
        peer_entries = {
            m.config["interface"]: _fetch_minion_key(m, minion_id) for m in masters[1:]
        }
        if all(e and e.get("state") == "accepted" for e in peer_entries.values()):
            break
        time.sleep(0.5)

    missing = [
        addr
        for addr, entry in peer_entries.items()
        if not entry or entry.get("state") != "accepted"
    ]
    assert not missing, (
        f"salt-key -a on master_1 did not replicate accepted-state entry "
        f"for {minion_id!r} to peers {missing}; got {peer_entries!r}. "
        f"This is saltstack/salt#70401 — Key.change_state fires "
        f"act='accepted' (long form) but EventMonitor._PEER_KEY_STATE "
        f"keys on 'accept' (short form), so _apply_peer_key_change "
        f"drops the event."
    )

    pubs = {master_1_entry["pub"]} | {e["pub"] for e in peer_entries.values()}
    assert len(pubs) == 1, (
        f"Minion pub key body differs across cluster peers after "
        f"salt-key -a: {len(pubs)} distinct values"
    )
