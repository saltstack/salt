"""
Reusable fixtures for master-topology functional tests.

Exposes:

* ``single_master(opts_overrides=None, cluster_id="solo")`` --- a
  factory for one standalone master wrapped in a
  :class:`tests.support.topology.cluster.TopologyCluster`.
* ``single_cluster(cluster_id, peer_count=1)`` --- a factory for a
  3008.x master cluster of N peers wrapped in a
  :class:`TopologyCluster`.  ``peer_count=1`` falls through to
  ``single_master`` so the same test can parametrize over cluster
  size.
* ``two_cluster_fixture`` --- a pair of standalone-master clusters
  (``east`` and ``west``), unpeered.  Tests opt in to peering by
  calling ``.accept_peer`` / ``.config_peer``.
* ``three_cluster_fixture`` --- three unpeered standalone-master
  clusters (``a``, ``b``, ``c``) for routing experiments.
* ``attach_minion(cluster)`` --- factory that spins up a minion
  attached to ``cluster.masters[0]``.

Teardown is handled by an ``ExitStack`` per fixture: every
``factory.started()`` is pushed onto the stack, and the stack
unwinds in reverse order at fixture scope exit.  No explicit
``.terminate()`` is required in tests.

Design decisions worth calling out
----------------------------------
* The harness does **not** import ``salt.topology`` at any point.
  Stubs are empty; importing them from a master process would be
  the implementation teams' job as they wire ``topology.pre_fork``
  / ``topology.start``.  Writing ``topology_enabled: True`` + a
  ``topology.conf`` to disk is sufficient to let the master come
  up today, and sufficient to let tomorrow's wired implementation
  behave correctly without touching this harness.
* The topology ``cluster_id`` lives in ``topology.conf``;
  salt-factories' master opts also carry a 3008.x ``cluster_id``
  for the master-cluster primitive.  To avoid collision, the
  harness uses ``topology-{cluster_id}`` as the master-id and
  ``master_cluster_{cluster_id}`` as the 3008.x cluster_id for
  multi-peer clusters.
"""

import contextlib
import logging

import pytest

from tests.support.topology.cluster import (
    TopologyCluster,
    make_cluster,
    make_single_master,
)

log = logging.getLogger(__name__)


@pytest.fixture
def topology_tmp_path(tmp_path):
    """Alias; distinct name keeps the harness fixtures easy to grep."""
    return tmp_path


@pytest.fixture
def _topology_exit_stack():
    """Shared context stack for fixture-managed daemon teardown."""
    with contextlib.ExitStack() as stack:
        yield stack


@pytest.fixture
def single_master(request, salt_factories, topology_tmp_path, _topology_exit_stack):
    """
    Factory fixture: ``single_master(opts_overrides=None,
    cluster_id="solo")`` -> :class:`TopologyCluster`.

    Each call reserves fresh ports and a fresh pki_dir; the fixture
    guarantees cleanup at scope exit regardless of how many times
    it is called within a single test.
    """
    transport = request.config.getoption("--transport", default="zeromq")
    counter = {"n": 0}

    def _factory(opts_overrides=None, cluster_id=None):
        counter["n"] += 1
        resolved_id = cluster_id or f"solo{counter['n']}"
        factory, pki_root, identity_pub, _topology_conf = make_single_master(
            salt_factories,
            topology_tmp_path,
            resolved_id,
            opts_overrides=opts_overrides,
            transport=transport,
        )
        _topology_exit_stack.enter_context(factory.started(start_timeout=120))
        return TopologyCluster(
            cluster_id=resolved_id,
            masters=[factory],
            pki_root=pki_root,
            identity_pub=identity_pub,
        )

    return _factory


@pytest.fixture
def single_cluster(request, salt_factories, topology_tmp_path, _topology_exit_stack):
    """
    Factory fixture: ``single_cluster(cluster_id, peer_count=1)`` ->
    :class:`TopologyCluster`.

    For ``peer_count=1`` this is semantically identical to
    ``single_master(cluster_id=cluster_id)``.  For ``peer_count>=2``,
    a 3008.x master cluster is spun up.
    """
    transport = request.config.getoption("--transport", default="zeromq")

    def _factory(cluster_id, peer_count=1, opts_overrides=None):
        factories, pki_root, identity_pub, _confs = make_cluster(
            salt_factories,
            topology_tmp_path,
            cluster_id,
            peer_count,
            opts_overrides=opts_overrides,
            transport=transport,
        )
        started = []
        for factory in factories:
            _topology_exit_stack.enter_context(factory.started(start_timeout=240))
            started.append(factory)
        return TopologyCluster(
            cluster_id=cluster_id,
            masters=started,
            pki_root=pki_root,
            identity_pub=identity_pub,
        )

    return _factory


@pytest.fixture
def two_cluster_fixture(single_master):
    """
    Pair of unpeered standalone-master clusters: ``east``, ``west``.

    Behavior tests opt in to peering with ``.accept_peer`` and/or
    ``.config_peer``.
    """
    east = single_master(cluster_id="east")
    west = single_master(cluster_id="west")
    return east, west


@pytest.fixture
def three_cluster_fixture(single_master):
    """
    Three unpeered standalone-master clusters: ``a``, ``b``, ``c``.

    Used by routing/transit experiments.
    """
    a = single_master(cluster_id="a")
    b = single_master(cluster_id="b")
    c = single_master(cluster_id="c")
    return a, b, c


@pytest.fixture
def attach_minion(_topology_exit_stack):
    """
    Factory fixture: ``attach_minion(cluster) -> SaltMinion``.

    The minion's ``master`` opt is set to ``cluster.masters[0]``'s
    ``interface:ret_port``.  Caller holds no cleanup burden; the
    exit stack tears the minion down at fixture scope exit.
    """

    def _factory(cluster, minion_id=None, overrides=None):
        if not isinstance(cluster, TopologyCluster):
            raise TypeError(
                f"attach_minion expects TopologyCluster, got {type(cluster)!r}"
            )
        master = cluster.masters[0]
        host = master.config.get("interface", "127.0.0.1")
        port = master.config["ret_port"]
        resolved_id = minion_id or f"topology-minion-{cluster.cluster_id}"
        config_overrides = {
            "master": f"{host}:{port}",
            "log_granular_levels": {
                "salt": "info",
            },
        }
        if overrides:
            config_overrides.update(overrides)
        factory = master.salt_minion_daemon(
            resolved_id,
            defaults={"transport": master.config["transport"]},
            overrides=config_overrides,
            extra_cli_arguments_after_first_start_failure=["--log-level=info"],
        )
        _topology_exit_stack.enter_context(factory.started(start_timeout=240))
        return factory

    return _factory
