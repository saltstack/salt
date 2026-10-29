"""
Pin the master-cluster documentation to source-of-truth semantics.

The reference tutorial in
``doc/topics/tutorials/master-cluster-reference.rst`` makes several
claims that depend on:

* Config-option **defaults** in ``salt.config`` (``cluster_pool_port``
  == 4520, ``cluster_isolated_filesystem`` default False, etc.).
* The **existence and signature** of cluster runners
  (``cluster.members``, ``cluster.ring_info``, ``cluster.sync_roots``).
* Defaults of adjacent options the docs reference for tuning HAProxy
  timeouts / minion recovery (``publish_session`` == 86400s;
  ``master_alive_interval`` default 0).

If any of these change and the doc isn't updated in the same PR, that
PR should turn one of these assertions red -- keeping the doc honest.
"""

import inspect

import salt.config
import salt.runners.cluster

# ---------------------------------------------------------------------------
# Config-option defaults referenced by the reference tutorial
# ---------------------------------------------------------------------------


def test_cluster_pool_port_default_is_4520():
    """Doc claims ``cluster_pool_port`` defaults to 4520 (L41)."""
    assert salt.config.DEFAULT_MASTER_OPTS["cluster_pool_port"] == 4520


def test_cluster_isolated_filesystem_default_false():
    """
    Doc claims the default is shared-FS mode and isolated-FS is opt-in
    (L7, L19-23, decision #1 at L394-399).
    """
    assert salt.config.DEFAULT_MASTER_OPTS["cluster_isolated_filesystem"] is False


def test_cluster_isolated_filesystem_accepts_true(tmp_path):
    """
    Doc L81/L107/L164/L189/L214 all set ``cluster_isolated_filesystem:
    True`` -- and the option loads without raising through
    ``master_config`` (redundant with the topology test but keeps the
    invariant visible from the config layer alone).
    """
    cfg = tmp_path / "master"
    cfg.write_text(
        "id: master-a\n"
        "cluster_id: prod_cluster\n"
        "cluster_peers:\n"
        "  - 10.27.7.126\n"
        "cluster_isolated_filesystem: True\n"
        "cluster_pki_dir: /etc/salt/pki/cluster\n"
        "cluster_secret: abc\n"
    )
    opts = salt.config.master_config(str(cfg))
    assert opts["cluster_isolated_filesystem"] is True


def test_cluster_secret_survives_load(tmp_path):
    """
    Doc L87-89 -- ``cluster_secret`` is a shared pre-shared string that
    must survive config load unchanged so every peer sees the same
    value.
    """
    secret = "d8b4c2e1f07a4c3e8a1b5d0a9c7f3e42b6d9a1c4f8e2b7d0a3c6e9f1b4d7a0c3"
    cfg = tmp_path / "master"
    cfg.write_text(
        "id: master-a\n"
        "cluster_id: prod_cluster\n"
        "cluster_peers:\n"
        "  - 10.27.7.126\n"
        f"cluster_secret: {secret!r}\n"
    )
    opts = salt.config.master_config(str(cfg))
    assert opts["cluster_secret"] == secret


def test_cluster_min_voters_default_is_three():
    """
    Doc L124-128 + decision #3 (L406-410) -- the safe failure mode on a
    2-node partition is refuse-writes because Raft needs a majority.
    That correctness guarantee is Raft's; but the *floor* below which
    the voter-health watchdog refuses to demote is controlled by
    ``cluster_min_voters``, and its default (3) is what makes even a
    healthy 2-node cluster refuse to auto-demote a peer -- important
    reader-facing invariant.
    """
    assert salt.config.DEFAULT_MASTER_OPTS["cluster_min_voters"] == 3


def test_publish_session_default_is_86400():
    """
    Doc L277, L287 -- the publish-session default is 86400s (24h),
    which is why the LB's ``timeout client`` on the publish frontend
    must be >= 86400s.
    """
    assert salt.config.DEFAULT_MASTER_OPTS["publish_session"] == 86400


def test_master_alive_interval_default_zero():
    """
    Doc L340-343 -- the minion sample sets ``master_alive_interval:
    30``; the reason it needs to be set explicitly is that the default
    is 0 (feature off).  If the default flips, the doc's guidance
    changes.
    """
    from salt.config import DEFAULT_MINION_OPTS

    assert DEFAULT_MINION_OPTS["master_alive_interval"] == 0


# ---------------------------------------------------------------------------
# Cluster-runner surface referenced by the reference tutorial
# ---------------------------------------------------------------------------


def test_keys_cache_driver_mmap_key_accepted(tmp_path):
    """
    Doc L82/L108/L165/L190/L215 -- the reference topologies set
    ``keys.cache_driver: mmap_key`` alongside
    ``cluster_isolated_filesystem: True``.  Make sure that key/value
    round-trips through master_config.
    """
    cfg = tmp_path / "master"
    cfg.write_text(
        "id: master-a\n"
        "cluster_id: prod_cluster\n"
        "cluster_peers:\n"
        "  - 10.27.7.126\n"
        "cluster_isolated_filesystem: True\n"
        "keys.cache_driver: mmap_key\n"
        "cluster_pki_dir: /etc/salt/pki/cluster\n"
        "cluster_secret: abc\n"
    )
    opts = salt.config.master_config(str(cfg))
    assert opts["keys.cache_driver"] == "mmap_key"


def test_cluster_members_runner_exists_with_signature():
    """
    Doc L229-239 tells the reader to run ``salt-run cluster.members``
    after starting the cluster.  Guard against the runner being
    renamed or dropped.
    """
    assert callable(salt.runners.cluster.members)
    sig = inspect.signature(salt.runners.cluster.members)
    # No positional arguments -- the doc example calls it bare.
    assert not any(
        p.default is inspect.Parameter.empty
        and p.kind
        in (inspect.Parameter.POSITIONAL_ONLY, inspect.Parameter.POSITIONAL_OR_KEYWORD)
        for p in sig.parameters.values()
    ), f"cluster.members must be callable with no args (got {sig})"


def test_cluster_ring_info_runner_exists_with_signature():
    """
    Doc L229-239 pairs ``cluster.ring_info`` with ``cluster.members``.
    Same guard.
    """
    assert callable(salt.runners.cluster.ring_info)
    sig = inspect.signature(salt.runners.cluster.ring_info)
    assert not any(
        p.default is inspect.Parameter.empty
        and p.kind
        in (inspect.Parameter.POSITIONAL_ONLY, inspect.Parameter.POSITIONAL_OR_KEYWORD)
        for p in sig.parameters.values()
    ), f"cluster.ring_info must be callable with no args (got {sig})"


def test_cluster_sync_roots_runner_exists_with_signature():
    """
    Doc L131-132 -- ``salt-run cluster.sync_roots`` is the operator-
    driven counterpart of the join-time state-sync.  Signature must
    remain ``(roots='both')`` because the reference page shows the
    bare-args form.
    """
    assert callable(salt.runners.cluster.sync_roots)
    sig = inspect.signature(salt.runners.cluster.sync_roots)
    params = list(sig.parameters.values())
    assert len(params) == 1, f"cluster.sync_roots signature drift: {sig}"
    assert params[0].name == "roots"
    assert params[0].default == "both"
