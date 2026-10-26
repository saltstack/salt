"""
Reusable ``TopologyCluster`` wrapper for the master-topology
functional test harness.

A :class:`TopologyCluster` represents one logical master in the
topology graph.  It is either:

* a single standalone master (``peer_count=1``), or
* an N-member 3008.x master cluster (``peer_count>=2``).

Either way, the wrapper exposes the semantic operations topology
tests reach for: ``accept_peer``, ``revoke_peer``, ``config_peer``,
``inspect_registry``, ``inspect_breadcrumbs``, and ``terminate``.

The wrapper is deliberately thin:

* It writes a per-master ``topology.conf`` at a known path and
  sets ``topology_enabled`` / ``topology_link_port`` /
  ``topology_config_file`` in each master's opts.
* It generates (and keeps on disk) a per-cluster ``master_identity.pub``
  stand-in so ``accept_peer`` has something to copy.  Per-file
  implementation teams will swap this out for a real
  :func:`salt.topology.registry.set_identity_pub` once that lands.
* ``inspect_registry`` and ``inspect_breadcrumbs`` read from the
  on-disk harness state (the ``masters/`` dir and
  ``topology_registry.mmap`` if it exists).  Teams who later wire
  the real mmap caches may replace these methods, but tests built
  against this shape keep working.

See the sibling ``tests/pytests/integration/cluster/conftest.py``
for the 3008.x master-cluster primitives this harness builds on.
"""

import logging
import os
import pathlib
import shutil
import subprocess

import yaml
from pytestshellutils.utils import ports

import salt.utils.files
import salt.utils.platform

log = logging.getLogger(__name__)


# Harness-generated identity-key placeholder.  Each cluster gets its
# own ``master_identity.pub`` byte string so ``accept_peer`` copies
# are distinguishable.  Keep this far away from a real crypto path:
# behavior tests that need a real identity key will materialize one
# via ``salt.crypt`` once the implementation lands.
_HARNESS_IDENTITY_PREFIX = b"-----BEGIN HARNESS IDENTITY PLACEHOLDER-----\n"
_HARNESS_IDENTITY_SUFFIX = b"\n-----END HARNESS IDENTITY PLACEHOLDER-----\n"


def _make_harness_identity(cluster_id):
    """Return deterministic placeholder public-key bytes for *cluster_id*."""
    return (
        _HARNESS_IDENTITY_PREFIX + cluster_id.encode("utf-8") + _HARNESS_IDENTITY_SUFFIX
    )


def _ensure_lo_alias(addr):
    """
    On BSDs the loopback aliases above 127.0.0.1 aren't automatic.
    Mirrors the pattern used in
    ``tests/pytests/integration/cluster/conftest.py``.
    """
    if salt.utils.platform.is_darwin() or salt.utils.platform.is_freebsd():
        subprocess.check_output(["ifconfig", "lo0", "alias", addr, "up"])


class TopologyCluster:
    """
    Harness wrapper around one logical master in a topology graph.

    :param cluster_id: Topology cluster_id (``east``, ``west``, ...).
    :param masters: List of started
        :class:`saltfactories.daemons.master.SaltMaster` instances
        belonging to this logical master.  List has length 1 for a
        standalone master, >1 for a 3008.x cluster.
    :param pki_root: Path containing the per-master pki_dir(s).  The
        ``masters/`` directory inside this path is where
        :meth:`accept_peer` drops peer identity keys.
    :param identity_pub: This cluster's placeholder identity public
        key bytes.  Copied into peers' ``masters/`` dirs by
        :meth:`accept_peer`.
    """

    def __init__(self, cluster_id, masters, pki_root, identity_pub):
        self.cluster_id = cluster_id
        self.masters = list(masters)
        self.pki_root = pathlib.Path(pki_root)
        self.identity_pub = identity_pub
        self._contexts = []
        self._terminated = False

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    @property
    def masters_pki_dir(self):
        """
        Return the ``<pki_dir>/masters/`` directory where
        :meth:`accept_peer` drops accepted peer identity keys.

        For a 3008.x cluster this reads from the shared
        ``cluster_pki_dir``; for a solo master, from the master's
        own ``pki_dir``.
        """
        # Each cluster has one shared masters/ directory because key
        # acceptance is a cluster-wide fact.  For a solo master it's
        # just the master's pki_dir/master/masters path.
        master = self.masters[0]
        pki_dir = pathlib.Path(master.config["pki_dir"])
        masters_dir = pki_dir / "masters"
        masters_dir.mkdir(parents=True, exist_ok=True)
        return masters_dir

    def is_running(self):
        """True if every underlying salt-master factory reports running."""
        if self._terminated:
            return False
        return all(m.is_running() for m in self.masters)

    def terminate(self):
        """
        Stop every underlying salt-master.  Idempotent.

        The fixtures also run their own exit-stack cleanup via
        ``factory.started()`` --- :meth:`terminate` is for tests that
        need to assert "cluster is down" without exiting the fixture.
        """
        if self._terminated:
            return
        for master in self.masters:
            try:
                master.terminate()
            except (OSError, RuntimeError) as exc:  # pragma: no cover
                log.warning("terminate(%s): %s", master.id, exc)
        self._terminated = True

    # ------------------------------------------------------------------
    # Peer acceptance (``salt-key -a --master`` simulation)
    # ------------------------------------------------------------------

    def accept_peer(self, other):
        """
        Place *other*'s identity pub in this cluster's ``masters/``
        directory --- simulates ``salt-key -a <other.cluster_id> --master``.

        :param other: Another :class:`TopologyCluster`.
        """
        if not isinstance(other, TopologyCluster):
            raise TypeError(f"accept_peer expects TopologyCluster, got {type(other)!r}")
        target = self.masters_pki_dir / f"{other.cluster_id}.pub"
        target.write_bytes(other.identity_pub)
        os.chmod(target, 0o644)

    def revoke_peer(self, other):
        """
        Remove *other*'s identity pub from this cluster's ``masters/``
        directory.  Idempotent.
        """
        if not isinstance(other, TopologyCluster):
            raise TypeError(f"revoke_peer expects TopologyCluster, got {type(other)!r}")
        target = self.masters_pki_dir / f"{other.cluster_id}.pub"
        if target.exists():
            target.unlink()

    # ------------------------------------------------------------------
    # Config-time peering (``topology.peers:`` in topology.conf)
    # ------------------------------------------------------------------

    def config_peer(self, other, host=None, port=None):
        """
        Add *other* to this cluster's ``topology.peers:`` list in
        ``topology.conf``.

        The implementation (not this harness) is responsible for
        reloading the config.  Behavior tests that need the running
        master to pick up a new peer will typically restart the
        master or trigger whatever reload mechanism lands.

        :param host: Override the peer host.  Defaults to the peer's
            own ``interface`` opt.
        :param port: Override the peer port.  Defaults to the peer's
            own ``topology_link_port``.
        """
        if not isinstance(other, TopologyCluster):
            raise TypeError(f"config_peer expects TopologyCluster, got {type(other)!r}")
        master = self.masters[0]
        conf_path = pathlib.Path(master.config["topology_config_file"])
        host = host or other.masters[0].config.get("interface", "127.0.0.1")
        port = port or other.masters[0].config["topology_link_port"]

        if conf_path.exists():
            with salt.utils.files.fopen(conf_path, encoding="utf-8") as fh:
                data = yaml.safe_load(fh) or {}
        else:
            data = {}
        data.setdefault("cluster_id", self.cluster_id)
        peers = list(data.get("peers") or [])
        entry = {"host": host, "port": int(port)}
        if entry not in peers:
            peers.append(entry)
        data["peers"] = peers
        with salt.utils.files.fopen(conf_path, "w", encoding="utf-8") as fh:
            yaml.safe_dump(data, fh, default_flow_style=False, sort_keys=False)

        # Mirror on every peer in the 3008.x cluster so they see the
        # same topology.conf (same semantics as cluster_pki_dir shared
        # state).
        for other_master in self.masters[1:]:
            other_conf = pathlib.Path(other_master.config["topology_config_file"])
            shutil.copy(str(conf_path), str(other_conf))

    # ------------------------------------------------------------------
    # Inspection (harness-level, swap for real-cache reads later)
    # ------------------------------------------------------------------

    def inspect_registry(self):
        """
        Return a snapshot of this cluster's registry state.

        Harness-level reading from disk --- the ``masters/`` dir for
        accepted peers, and ``master_identity.pub`` for the identity
        half.  Per-file implementation teams who land the real
        :mod:`salt.topology.registry` MmapCache may extend this to
        read the mmap instead; existing callers see the same keys
        (``identity``, ``peers``).
        """
        peers = []
        masters_dir = self.masters_pki_dir
        if masters_dir.is_dir():
            for entry in sorted(masters_dir.iterdir()):
                if entry.suffix == ".pub":
                    peers.append(entry.stem)
        return {
            "identity": self.identity_pub,
            "cluster_id": self.cluster_id,
            "peers": peers,
        }

    def inspect_breadcrumbs(self):
        """
        Return the list of breadcrumb entries visible on disk.

        Reads the real :mod:`salt.topology.breadcrumbs` MmapCache
        when it exists and returns a list of
        ``{"jid": str, "link_cluster_id": str, "expiry_at": float}``
        dicts for every non-expired entry.  Returns ``[]`` when the
        file has not yet been materialised (either the publish
        daemon hasn't started or no publishes have been forwarded).
        """
        crumbs = []
        master = self.masters[0]
        pki_dir = pathlib.Path(master.config["pki_dir"])
        mmap_path = pki_dir / "master" / "topology_breadcrumbs.mmap"
        if not mmap_path.exists():
            return crumbs
        # Open a reader against the real breadcrumbs cache and
        # decode each live entry's msgpack payload.
        import salt.topology.breadcrumbs as breadcrumbs_mod

        opts = {
            "pki_dir": str(pki_dir),
            "topology_breadcrumb_cache_size": master.config.get(
                "topology_breadcrumb_cache_size", 1_000_000
            ),
            "topology_breadcrumb_cache_key_size": master.config.get(
                "topology_breadcrumb_cache_key_size", 64
            ),
        }
        reader = breadcrumbs_mod.open_reader(opts)
        try:
            for key, raw in reader.list_items():
                decoded = breadcrumbs_mod._decode(  # pylint: disable=protected-access
                    raw
                )
                if decoded is None:
                    continue
                crumbs.append(
                    {
                        "jid": key,
                        "link_cluster_id": decoded.get("link_cluster_id"),
                        "expiry_at": decoded.get("expiry_at"),
                    }
                )
        finally:
            reader.close()
        return crumbs

    def breadcrumb_mmap_paths(self):
        """
        Return the on-disk paths of the breadcrumbs MmapCache files
        as a dict with keys ``index``, ``heap``, ``roster``,
        ``lock``.

        Lets scenario tests assert "the cache file persists on disk"
        across a publish-daemon restart --- the file is written
        before :meth:`terminate` and still exists afterward because
        MmapCache lifetime is tied to on-disk files, not the
        process.
        """
        master = self.masters[0]
        pki_dir = pathlib.Path(master.config["pki_dir"])
        base = pki_dir / "master" / "topology_breadcrumbs.mmap"
        return {
            "index": base,
            "heap": pathlib.Path(str(base) + ".heap"),
            "roster": pathlib.Path(str(base) + ".roster"),
            "lock": pathlib.Path(str(base) + ".lock"),
        }

    def master_opts(self):
        """
        Return the opts dict needed to drive
        :mod:`salt.topology.link_manager` /
        :mod:`salt.topology.registry` /
        :mod:`salt.topology.breadcrumbs` against this cluster's
        on-disk state.

        Pulls values from the first master's running config so an
        in-process link_manager.start uses the same pki_dir /
        topology_link_port / topology.conf as the harness-managed
        daemon.  Scenario tests that drive topology lifecycle
        in-process (publish daemon restart, startup ordering) use
        this to point module-level writers at the right disk.
        """
        master = self.masters[0]
        # Mirror the running master's config sizing so the writer we
        # open here lines up byte-for-byte with any MmapCache files
        # the salt-master's own ``pre_fork`` already materialised.
        # A size mismatch between pre-created files and the writer
        # produces a cache that silently drops writes to the
        # out-of-range slots.
        return {
            "pki_dir": master.config["pki_dir"],
            "cluster_id": self.cluster_id,
            "interface": master.config.get("interface", "127.0.0.1"),
            "topology_enabled": True,
            "topology_link_port": master.config["topology_link_port"],
            "topology_config_file": master.config["topology_config_file"],
            "topology_registry_cache_size": master.config.get(
                "topology_registry_cache_size", 10_000
            ),
            "topology_registry_cache_key_size": master.config.get(
                "topology_registry_cache_key_size", 64
            ),
            "topology_breadcrumb_cache_size": master.config.get(
                "topology_breadcrumb_cache_size", 1_000_000
            ),
            "topology_breadcrumb_cache_key_size": master.config.get(
                "topology_breadcrumb_cache_key_size", 64
            ),
            "topology_breadcrumb_grace": master.config.get(
                "topology_breadcrumb_grace", 2
            ),
            "topology_breadcrumb_max_age": master.config.get(
                "topology_breadcrumb_max_age", 60
            ),
            "topology_detach_quiesce": master.config.get("topology_detach_quiesce", 1),
        }

    def start_publish_daemon(self, raft_service=None):
        """
        Drive :func:`salt.topology.link_manager.start` in-process
        against this cluster's pki_dir.

        Simulates the publish-daemon post-fork hook that will wire
        the topology subsystem once Phase 5 integration lands in
        :class:`salt.channel.server.MasterPubServerChannel`.
        Returns the ``(loop, opts)`` pair so the caller can drive
        follow-on operations (``_handle_master_auth``, forced
        ``stop``, etc.) on the same loop.

        The caller is responsible for calling :meth:`stop_publish_daemon`
        (or driving ``link_manager.stop`` on the returned loop) at
        the end of the scenario.  Idempotent-ish: if ``link_manager``
        is already started, a WARNING is logged and the existing
        state is reused.
        """
        import asyncio

        import salt.topology.link_manager as link_manager

        opts = self.master_opts()
        loop = asyncio.new_event_loop()
        loop.run_until_complete(link_manager.start(opts, loop, raft_service))
        return loop, opts

    def stop_publish_daemon(self, loop):
        """
        Drive :func:`salt.topology.link_manager.stop` on *loop*.

        Mirrors :meth:`start_publish_daemon`.  Idempotent: a second
        ``stop_publish_daemon`` with the same loop is a no-op after
        the first because ``link_manager.stop`` resets module state
        to its post-import defaults.
        """
        import salt.topology.link_manager as link_manager

        try:
            loop.run_until_complete(link_manager.stop())
        finally:
            loop.close()


def _write_topology_conf(path, cluster_id):
    """Write a minimal valid topology.conf with just a cluster_id."""
    path = pathlib.Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with salt.utils.files.fopen(path, "w", encoding="utf-8") as fh:
        yaml.safe_dump({"cluster_id": cluster_id, "peers": []}, fh, sort_keys=False)
    return path


def make_single_master(
    salt_factories,
    tmp_path,
    cluster_id,
    opts_overrides=None,
    transport="zeromq",
):
    """
    Spin up one standalone master configured for topology (opts +
    topology.conf written; stub code remains inert).

    :returns: A started :class:`TopologyCluster` with ``len(masters)==1``.
    """
    opts_overrides = dict(opts_overrides or {})
    link_port = ports.get_unused_localhost_port()
    pki_root = pathlib.Path(tmp_path) / f"{cluster_id}-pki"
    pki_root.mkdir(parents=True, exist_ok=True)
    topology_conf = pathlib.Path(tmp_path) / f"{cluster_id}-topology.conf"
    _write_topology_conf(topology_conf, cluster_id)

    base_overrides = {
        "open_mode": True,
        "pki_dir": str(pki_root),
        "topology_enabled": True,
        "topology_link_port": link_port,
        "topology_config_file": str(topology_conf),
        "topology_breadcrumb_grace": 2,
        "topology_breadcrumb_max_age": 60,
        "topology_detach_quiesce": 1,
        "log_granular_levels": {
            "salt": "info",
        },
    }
    base_overrides.update(opts_overrides)

    factory = salt_factories.salt_master_daemon(
        f"topology-{cluster_id}",
        defaults={"open_mode": True, "transport": transport},
        overrides=base_overrides,
        extra_cli_arguments_after_first_start_failure=["--log-level=info"],
    )
    identity_pub = _make_harness_identity(cluster_id)
    # The caller is responsible for driving ``factory.started()``.
    return factory, pki_root, identity_pub, topology_conf


def make_cluster(
    salt_factories,
    tmp_path,
    cluster_id,
    peer_count,
    opts_overrides=None,
    transport="zeromq",
):
    """
    Spin up an N-member 3008.x master cluster configured for
    topology.  Each cluster peer gets the same ``topology.conf`` on
    disk (writes mirrored by :meth:`TopologyCluster.config_peer`).

    :returns: ``(factories, pki_root, identity_pub, topology_confs,
        addrs)`` --- caller drives ``factory.started()`` for each.
    """
    if peer_count < 1:
        raise ValueError("peer_count must be >= 1")
    if peer_count == 1:
        factory, pki_root, identity_pub, topology_conf = make_single_master(
            salt_factories, tmp_path, cluster_id, opts_overrides, transport
        )
        return [factory], pki_root, identity_pub, [topology_conf]

    # Multi-peer: use the loopback-alias pattern from the existing
    # cluster conftest.
    opts_overrides = dict(opts_overrides or {})
    link_port = ports.get_unused_localhost_port()
    ret_port = ports.get_unused_localhost_port()
    pub_port = ports.get_unused_localhost_port()
    cluster_shared = pathlib.Path(tmp_path) / f"{cluster_id}-shared"
    cluster_shared.mkdir(parents=True, exist_ok=True)
    cluster_pki = cluster_shared / "pki"
    cluster_pki.mkdir(parents=True, exist_ok=True)
    (cluster_pki / "peers").mkdir(exist_ok=True)
    cluster_cache = cluster_shared / "cache"
    cluster_cache.mkdir(parents=True, exist_ok=True)

    # Pick N distinct loopback addrs: 127.0.0.1..127.0.0.N.
    addrs = [f"127.0.0.{i + 1}" for i in range(peer_count)]

    factories = []
    topology_confs = []
    salt_cluster_id = f"master_cluster_{cluster_id}"
    identity_pub = _make_harness_identity(cluster_id)
    for addr in addrs:
        _ensure_lo_alias(addr)
        own_pki = pathlib.Path(tmp_path) / f"{cluster_id}-{addr}-pki"
        own_pki.mkdir(parents=True, exist_ok=True)
        topology_conf = pathlib.Path(tmp_path) / f"{cluster_id}-{addr}-topology.conf"
        _write_topology_conf(topology_conf, cluster_id)
        topology_confs.append(topology_conf)

        peers = [a for a in addrs if a != addr]
        overrides = {
            "open_mode": True,
            "interface": addr,
            "pki_dir": str(own_pki),
            "cluster_id": salt_cluster_id,
            "cluster_peers": peers,
            "cluster_pki_dir": str(cluster_pki),
            "cache_dir": str(cluster_cache),
            "ret_port": ret_port,
            "publish_port": pub_port,
            "topology_enabled": True,
            "topology_link_port": link_port,
            "topology_config_file": str(topology_conf),
            "topology_breadcrumb_grace": 2,
            "topology_breadcrumb_max_age": 60,
            "topology_detach_quiesce": 1,
            "log_granular_levels": {
                "salt": "info",
            },
        }
        overrides.update(opts_overrides)
        factory = salt_factories.salt_master_daemon(
            addr,
            defaults={"open_mode": True, "transport": transport},
            overrides=overrides,
            extra_cli_arguments_after_first_start_failure=["--log-level=info"],
        )
        factories.append(factory)

    return factories, cluster_pki, identity_pub, topology_confs
