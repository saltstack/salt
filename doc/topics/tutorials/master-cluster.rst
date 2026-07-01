.. _tutorial-master-cluster:


==============
Master Cluster
==============

A clustered Salt Master has several advantages over Salt's traditional High
Availability options. First, a master cluster is meant to be served behind a
load balancer. Minions only need to know about the load balancer's IP address.
Therefore, masters can be added and removed from a cluster without the need to
re-configure minions. Another major benefit of master clusters over Salt's
older HA implimentations is that Masters in a cluster share the load of all
jobs. This allows Salt administrators to more easily scale their environments
to handle larger numbers of minions and larger jobs.

Minimum Requirements
====================

A master cluster needs a tcp load balancer in front of each master's publish
and request server ports (typically 4505 / 4506) and a reliable local area
network between peers.  Beyond that, each peer needs access to the same
identity material: ``cluster_pki_dir`` (the shared cluster public/private key
and minion keys), ``cachedir`` (job and grain cache), and the
:conf_master:`file_roots` / :conf_master:`pillar_roots` trees that the
cluster serves.

That identity material can be provided in one of two ways:

* **Shared filesystem (default).**  Mount the same NFS/Gluster/etc. share at
  ``cluster_pki_dir``, ``cachedir``, ``file_roots``, and ``pillar_roots`` on
  every peer.  This is the original master-cluster mode and the topology the
  rest of this tutorial demonstrates with Gluster + HAProxy.

* **Isolated filesystem (3008.0 and later).**  Set
  :conf_master:`cluster_isolated_filesystem` to ``True`` on each peer.  Each
  master keeps its own local ``cluster_pki_dir`` / ``cachedir`` /
  ``file_roots`` / ``pillar_roots``; a joining master pulls keys, denied
  keys, ``file_roots``, and ``pillar_roots`` from an existing peer in-band
  over the cluster transport before being promoted to a Raft voter, and
  job/cache state moves between masters via the Raft+HashRing layer.  See
  the :ref:`Topology section <master-cluster-topology>` for a side-by-side
  comparison.

Each master in a cluster maintains its own public and private key, and an in
memory aes key. Each cluster peer also has access to the ``cluster_pki_dir``
where a cluster-wide public and private key are stored. In addition, the
cluster-wide aes key is generated and stored in the ``cluster_pki_dir``.
Further, when operating as a cluster, minion keys are stored in the
``cluster_pki_dir`` instead of the master's ``pki_dir``.

.. _master-cluster-topology:

Topology: shared filesystem vs. isolated filesystem
===================================================

.. versionadded:: 3008.0
    Isolated-filesystem mode (:conf_master:`cluster_isolated_filesystem`).

The two topologies differ only in how the *content* a master needs is
provisioned to it; the wire protocol between cluster peers, the
:conf_master:`cluster_pool_port` Raft RPC, and the load-balancer setup are
identical.

.. list-table::
    :header-rows: 1
    :widths: 30 35 35

    * - What
      - Shared filesystem
      - Isolated filesystem
    * - ``cluster_pki_dir`` contents
      - Same path on every peer
      - Local on every peer
    * - ``cachedir`` contents
      - Same path on every peer
      - Local on every peer
    * - ``file_roots`` / ``pillar_roots``
      - Same path on every peer
      - Local on every peer; pushed in-band on join and via
        ``salt-run cluster.sync_roots``
    * - Job / grain cache routing
      - Through the shared cachedir
      - Through Raft + HashRing
    * - Recommended :conf_master:`keys.cache_driver`
      - ``localfs_key`` (default)
      - ``mmap_key`` (see :ref:`mmap-cache`)
    * - Adding a master
      - Mount the share, start it
      - Dynamic Join -- state-sync runs automatically

When to pick which:

* **Shared filesystem** is the right answer when you already operate a
  reliable cluster filesystem and want a single place to edit
  ``file_roots`` / ``pillar_roots``.  Failures in the shared filesystem
  fail the whole cluster.

* **Isolated filesystem** removes the shared-storage dependency, so a
  master can join a cluster from a vanilla box with only Salt installed.
  The cost is that ``file_roots`` and ``pillar_roots`` edits made on one
  master must be propagated explicitly (``salt-run cluster.sync_roots``)
  rather than appearing instantly on every peer.

Regardless of topology, ``cluster_pool_port`` carries Raft RPC between
peers, ``4505``/``4506`` carry minion publish and return traffic through
the load balancer, and ``cluster_secret`` authenticates new masters that
want to join.

Reference Implementation
========================

Gluster: https://docs.gluster.org/en/main/Quick-Start-Guide/Quickstart/

HAProxy:

.. code-block:: text

        frontend salt-master-pub
            mode tcp
            bind 10.27.5.116:4505
            option tcplog
            # This timeout is equal to the publish_session setting of the
            # masters.
            timeout client 86400s
            default_backend salt-master-pub-backend

        backend salt-master-pub-backend
            mode tcp
            #option log-health-checks
            log global
            balance roundrobin
            timeout connect 10s
            # This timeout is equal to the publish_session setting of the
            # masters.
            timeout server 86400s
            server rserve1 10.27.12.13:4505 check
            server rserve2 10.27.7.126:4505 check
            server rserve3 10.27.3.73:4505 check

        frontend salt-master-req
            mode tcp
            bind 10.27.5.116:4506
            option tcplog
            timeout client  1m
            default_backend salt-master-req-backend

        backend salt-master-req-backend
            mode tcp
            log global
            balance roundrobin
            timeout connect 10s
            timeout server 1m
            server rserve1 10.27.12.13:4506 check
            server rserve2 10.27.7.126:4506 check
            server rserve3 10.27.3.73:4506 check

Master Config:

.. code-block:: yaml

        id: 10.27.12.13
        cluster_id: master_cluster
        cluster_peers:
          - 10.27.7.126
          - 10.27.3.73
        cluster_pki_dir: /my/gluster/share/pki
        cachedir: /my/gluster/share/cache
        file_roots:
          base:
            - /my/gluster/share/srv/salt
        pillar_roots:
          base:
            - /my/gluster/share/srv/pillar


.. _master-cluster-dynamic-join:

Dynamic Join
============

.. versionadded:: 3008.0

A new master can join a running cluster without reconfiguring the existing
peers. The joining master needs the same ``cluster_id``,
``cluster_pki_dir``, and ``cluster_secret`` as the cluster, plus at least
one reachable peer in its ``cluster_peers`` -- it does not need the full
peer list. On startup it runs a discover/join handshake against those
peers, and on success it receives the shared cluster public key and the
current in-memory AES session key and is added to every peer's
``cluster_peers``.

Joining master config:

.. code-block:: yaml

        id: 10.27.9.42
        cluster_id: master_cluster
        cluster_peers:
          - 10.27.12.13
        cluster_pki_dir: /my/gluster/share/pki
        cluster_secret: "d8b4c2e1f07a4c3e8a1b5d0a9c7f3e42b6d9a1c4f8e2b7d0a3c6e9f1b4d7a0c3"
        cachedir: /my/gluster/share/cache

Add the new master to the load balancer's backend pools so publish/return
traffic starts reaching it.

Security notes:

* ``cluster_secret`` is what authenticates the join. Always set a
  high-entropy value in production; an empty/unset secret matches an empty
  secret on the peer and provides no authentication.
* Discover and join payloads are signed per-master, and ``cluster_secret``,
  the AES session key, and the cluster key are encrypted to the
  recipient's public key. Restrict the cluster transport to a trusted
  network -- an attacker with ``cluster_secret`` and transport access can
  still join.
* The joining master normally reads the cluster public key from the
  shared ``cluster_pki_dir``. If that is not available, pin it with
  :conf_master:`cluster_pub_fingerprint` on the joining master.

To remove a peer, drop it from the load balancer, stop the master, delete
its ``cluster_pki_dir/peers/<peer_id>.pub``, and restart the remaining
masters. Rotate ``cluster_secret`` if you want to prevent the removed
peer from re-joining.


Migrating from a shared-filesystem cluster
==========================================

.. versionadded:: 3008.0
    :conf_master:`cluster_isolated_filesystem`,
    :py:func:`pki.migrate_to_mmap <salt.runners.pki.migrate_to_mmap>`, and
    the cluster runners used below.

These steps convert a running shared-filesystem cluster to isolated-FS mode
without minion-visible downtime, provided the load balancer keeps draining
one master at a time.

1.  **Switch the key-cache driver to mmap_key.**  On a single master, while
    the cluster is still on the shared filesystem, run:

    .. code-block:: bash

        salt-run pki.migrate_to_mmap

    This converts every accepted, pending, denied, and rejected minion key
    from the on-disk ``localfs_key`` layout to the ``mmap_key`` layout
    described in :ref:`mmap-cache`.  The shared filesystem now contains
    mmap blobs that every peer can read.

2.  **Update each peer's master config.**  On every master, add:

    .. code-block:: yaml

        cluster_isolated_filesystem: True
        keys.cache_driver: mmap_key

    Leave ``cluster_pki_dir``, ``cachedir``, ``file_roots``, and
    ``pillar_roots`` pointing at the shared paths for now -- the next two
    steps move them to local paths.

3.  **Roll the cluster one master at a time.**  For each peer:

    a.  Drain it from the load balancer (so minions stop sending it
        traffic).
    b.  Stop ``salt-master``.
    c.  Copy ``cluster_pki_dir`` and ``cachedir`` from the shared mount to
        local paths, and update the master config to point at the local
        copies.  Optionally also copy ``file_roots`` and ``pillar_roots``
        and switch them to local paths.
    d.  Start ``salt-master``.  The master rejoins as a learner, runs the
        in-band state-sync from a peer (keys, denied keys, ``file_roots``,
        ``pillar_roots``), then gets promoted back to a voter.
    e.  Add it back to the load balancer.

    Repeat until every peer has been moved off the shared filesystem.

4.  **Verify the new topology.**  On any master, run:

    .. code-block:: bash

        salt-run cluster.members
        salt-run cluster.ring_info

    ``cluster.members`` shows every Raft voter (and any learners that
    haven't caught up yet).  ``cluster.ring_info`` shows the HashRing
    state that routes job and grain cache to specific peers.  Both should
    list every peer with no stuck learners.

5.  **Drop the shared filesystem mount.**  Once every peer is fully on
    local paths and the cluster is healthy, you can unmount the shared
    filesystem.  Do this last so that step 3 can fall back to it on any
    peer that hits trouble.

After migration:

* When you edit ``file_roots`` or ``pillar_roots`` on one master, push the
  changes to peers explicitly:

  .. code-block:: bash

      salt-run cluster.sync_roots

  The runner fan-outs over the same encrypted cluster transport as the
  join-time state-sync.  Tail each peer's master log for the
  ``state-sync ... installed N items`` lines to confirm delivery.

* When you add a new master, the :ref:`Dynamic Join
  <master-cluster-dynamic-join>` flow handles the in-band state-sync
  automatically -- no extra runner is required.
