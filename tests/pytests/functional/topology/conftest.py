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
  / ``topology.start``.  Setting ``topology_enabled: True`` plus
  ``cluster_id`` / ``topology_peers`` in the master opts is
  sufficient to let the master come up today, and sufficient to
  let tomorrow's wired implementation behave correctly without
  touching this harness.
* One ``cluster_id`` serves both features: it is the Raft master
  cluster identity AND the topology-graph node identity.  For
  solo masters this is the only identity; for multi-peer clusters
  the same string names the Raft cluster.  Harness uses
  ``topology-{cluster_id}`` as the salt-factories master-id for
  single-master fixtures and the loopback addr as the master-id
  for cluster peers.
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
        factory, pki_root, identity_pub = make_single_master(
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
        factories, pki_root, identity_pub = make_cluster(
            salt_factories,
            topology_tmp_path,
            cluster_id,
            peer_count,
            opts_overrides=opts_overrides,
            transport=transport,
        )
        started = []
        if len(factories) == 1:
            # Solo masters have no quorum dependency; keep the
            # original sequential path for the simpler trace.
            _topology_exit_stack.enter_context(factories[0].started(start_timeout=240))
            started.append(factories[0])
        else:
            # Multi-peer cluster: peers need each other online to
            # commit the founding CONFIG (voters = {all peers}, so
            # the first peer cannot bootstrap alone --- it needs
            # majority quorum).  Each thread calls ``factory.start()``
            # on its own factory and blocks until that one factory is
            # ready; the shared ``ExitStack`` is only touched from the
            # main thread AFTER the threads join (ExitStack is not
            # documented as thread-safe).  On Linux the old sequential
            # path happened to work by timing (start-event fires before
            # Raft matters); on Windows the EventPublisher's
            # aes-key-event send blocks for 30s when Raft can't form,
            # long enough that the per-peer 240s start_timeout trips
            # and the whole cluster-start times out.
            import threading as _threading

            errors = [None] * len(factories)
            # Per-attempt start budget.  Saltfactories retries up to
            # ``max_start_attempts`` (default 3) on FactoryNotStarted,
            # so the worst-case wall-clock for one peer is
            # ``start_timeout * max_start_attempts``.  Keep that
            # under the pytest-timeout budget on the test (300s) so a
            # genuine failure surfaces as a FactoryNotStarted traceback
            # rather than a pytest-timeout on ``Thread.join``.
            _PEER_START_TIMEOUT = 60

            def _start_one(idx):
                try:
                    factories[idx].start(start_timeout=_PEER_START_TIMEOUT)
                except BaseException as exc:  # pylint: disable=broad-except
                    errors[idx] = exc

            threads = [
                _threading.Thread(target=_start_one, args=(i,), daemon=True)
                for i in range(len(factories))
            ]
            for t in threads:
                t.start()
            # Hard wall clock on ``Thread.join`` so the test cannot
            # block forever if a peer's ``factory.start`` itself
            # deadlocks (observed on slower Linux CI runners where
            # one peer never signalled ``started`` and saltfactories
            # swallowed the retry traceback).  The bound is comfortably
            # larger than ``_PEER_START_TIMEOUT * max_start_attempts``
            # so a normal failure path raises below instead of here.
            _JOIN_TIMEOUT = 240
            for t in threads:
                t.join(timeout=_JOIN_TIMEOUT)
            stuck = [i for i, t in enumerate(threads) if t.is_alive()]
            if stuck:
                for i, other_factory in enumerate(factories):
                    try:
                        other_factory.terminate()
                    except Exception:  # pylint: disable=broad-except
                        pass
                raise RuntimeError(
                    f"multi-peer cluster start stuck: peer threads "
                    f"{stuck} still running after {_JOIN_TIMEOUT}s"
                )
            for idx, exc in enumerate(errors):
                if exc is not None:
                    # Tear down any peers that DID come up before
                    # re-raising, so the test's cleanup doesn't
                    # inherit a stray process.
                    for i, other_factory in enumerate(factories):
                        if i != idx:
                            try:
                                other_factory.terminate()
                            except Exception:  # pylint: disable=broad-except
                                pass
                    raise exc
            # All three are up; now register teardown on the shared
            # exit stack so fixture scope-exit terminates each one.
            for factory in factories:
                _topology_exit_stack.callback(factory.terminate)
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
