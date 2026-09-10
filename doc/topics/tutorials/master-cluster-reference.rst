.. _tutorial-master-cluster-reference:

==============================================
Master Cluster Reference Topologies
==============================================

.. versionadded:: 3008.0

This page is a worked, copy-pasteable companion to
:ref:`tutorial-master-cluster`.  It covers two concrete topologies that
together address most production deployments:

* :ref:`master-cluster-2node-ref` -- the minimum HA pair behind a single
  load balancer.
* :ref:`master-cluster-3node-ref` -- the recommended starting point for
  production: a three-node cluster with a Raft majority that survives a
  single-master outage.

Both reference implementations use the 3008.0 *isolated-filesystem*
cluster mode (:conf_master:`cluster_isolated_filesystem`) so they can be
stood up on stock hosts with only ``salt-master`` installed -- no
NFS/Gluster/CephFS to operate.  The HAProxy section that follows is the
same for either topology.

For a side-by-side comparison of shared-filesystem vs. isolated-filesystem
mode, the migration runbook between the two, and the :ref:`Dynamic Join
<master-cluster-dynamic-join>` flow used when a master joins a running
cluster, see :ref:`tutorial-master-cluster`.

.. _master-cluster-ports:

Ports used by a master cluster
==============================

A single master cluster uses three TCP ports per peer:

* ``4505/tcp`` -- minion publish (master to minion).  Fronted by the
  load balancer.
* ``4506/tcp`` -- minion request / return (minion to master).  Fronted
  by the load balancer.
* :conf_master:`cluster_pool_port` (``4520/tcp`` by default) -- cluster
  Raft + state-sync RPC between peers.  Peer-to-peer only; **must not**
  be exposed through the minion-facing load balancer.

The minion-facing load balancer terminates ``4505`` and ``4506`` and
fans out to every peer.  ``cluster_pool_port`` is a direct peer-to-peer
mesh; it should be reachable on the cluster's private network only.

.. _master-cluster-2node-ref:

Reference topology A: 2-node HA pair
====================================

A 2-node cluster is the smallest deployment that survives the loss of
one master.  Use this when you have exactly two hosts available, accept
that a *network partition* between the two masters cannot be resolved
automatically (Raft has no majority on two nodes), and want minimum
operational overhead.

Hosts in this example:

* ``master-a`` -- ``10.27.12.13``
* ``master-b`` -- ``10.27.7.126``
* Load balancer VIP -- ``10.27.5.116`` (the address minions are
  configured with)

Master config -- ``master-a`` (``/etc/salt/master``):

.. code-block:: yaml

    id: master-a
    cluster_id: prod_cluster

    # cluster_peers lists every OTHER peer -- not the local node.
    cluster_peers:
      - 10.27.7.126

    # 3008.0+ isolated-filesystem mode: each peer keeps its own local
    # cluster_pki_dir / cachedir / file_roots / pillar_roots.  Content
    # is sync'd in-band over the cluster transport.
    cluster_isolated_filesystem: True
    keys.cache_driver: mmap_key

    cluster_pki_dir: /etc/salt/pki/cluster
    cachedir: /var/cache/salt/master

    # Pre-shared secret authenticating cluster joins.  Generate with
    # `openssl rand -hex 32` and set the SAME value on every peer.
    cluster_secret: "d8b4c2e1f07a4c3e8a1b5d0a9c7f3e42b6d9a1c4f8e2b7d0a3c6e9f1b4d7a0c3"

    file_roots:
      base:
        - /srv/salt
    pillar_roots:
      base:
        - /srv/pillar

Master config -- ``master-b`` (``/etc/salt/master``):

.. code-block:: yaml

    id: master-b
    cluster_id: prod_cluster
    cluster_peers:
      - 10.27.12.13

    cluster_isolated_filesystem: True
    keys.cache_driver: mmap_key

    cluster_pki_dir: /etc/salt/pki/cluster
    cachedir: /var/cache/salt/master

    cluster_secret: "d8b4c2e1f07a4c3e8a1b5d0a9c7f3e42b6d9a1c4f8e2b7d0a3c6e9f1b4d7a0c3"

    file_roots:
      base:
        - /srv/salt
    pillar_roots:
      base:
        - /srv/pillar

Notes specific to two nodes:

* **Quorum / split-brain.**  Two voters cannot form a Raft majority on
  their own; if the two masters can reach minions but not each other,
  neither side will accept writes.  This is the safe failure mode.  If
  you want the cluster to keep serving in that scenario, run a third
  master (see :ref:`master-cluster-3node-ref`).
* **Identical file_roots / pillar_roots content.**  In isolated-FS mode
  the *initial* content is pushed during the join handshake; afterwards,
  run ``salt-run cluster.sync_roots`` from whichever master you edit on
  to fan changes out to peers.
* **One LB, no LB HA.**  A 2-node cluster behind a single load balancer
  has a load-balancer SPOF.  For real HA pair the LB itself with
  keepalived/VRRP, ECMP, or a managed cloud LB.

.. _master-cluster-3node-ref:

Reference topology B: 3-node production cluster
===============================================

Three nodes is the smallest topology that gives you a Raft majority
that can survive the loss of any single peer with no manual
intervention.  This is the recommended starting point for production.

Hosts in this example:

* ``master-a`` -- ``10.27.12.13``
* ``master-b`` -- ``10.27.7.126``
* ``master-c`` -- ``10.27.3.73``
* Load balancer VIP -- ``10.27.5.116``

Master config -- ``master-a`` (``/etc/salt/master``):

.. code-block:: yaml

    id: master-a
    cluster_id: prod_cluster

    cluster_peers:
      - 10.27.7.126
      - 10.27.3.73

    cluster_isolated_filesystem: True
    keys.cache_driver: mmap_key

    cluster_pki_dir: /etc/salt/pki/cluster
    cachedir: /var/cache/salt/master

    cluster_secret: "d8b4c2e1f07a4c3e8a1b5d0a9c7f3e42b6d9a1c4f8e2b7d0a3c6e9f1b4d7a0c3"

    file_roots:
      base:
        - /srv/salt
    pillar_roots:
      base:
        - /srv/pillar

Master config -- ``master-b``:

.. code-block:: yaml

    id: master-b
    cluster_id: prod_cluster
    cluster_peers:
      - 10.27.12.13
      - 10.27.3.73

    cluster_isolated_filesystem: True
    keys.cache_driver: mmap_key

    cluster_pki_dir: /etc/salt/pki/cluster
    cachedir: /var/cache/salt/master

    cluster_secret: "d8b4c2e1f07a4c3e8a1b5d0a9c7f3e42b6d9a1c4f8e2b7d0a3c6e9f1b4d7a0c3"

    file_roots:
      base:
        - /srv/salt
    pillar_roots:
      base:
        - /srv/pillar

Master config -- ``master-c``:

.. code-block:: yaml

    id: master-c
    cluster_id: prod_cluster
    cluster_peers:
      - 10.27.12.13
      - 10.27.7.126

    cluster_isolated_filesystem: True
    keys.cache_driver: mmap_key

    cluster_pki_dir: /etc/salt/pki/cluster
    cachedir: /var/cache/salt/master

    cluster_secret: "d8b4c2e1f07a4c3e8a1b5d0a9c7f3e42b6d9a1c4f8e2b7d0a3c6e9f1b4d7a0c3"

    file_roots:
      base:
        - /srv/salt
    pillar_roots:
      base:
        - /srv/pillar

After all three masters are running, verify the cluster from any peer:

.. code-block:: bash

    salt-run cluster.members
    salt-run cluster.ring_info

``cluster.members`` should list all three masters as voters; if a peer
shows up as a learner that hasn't caught up, give it another few
seconds and re-run.  ``cluster.ring_info`` shows the HashRing entries
used to route job and grain cache to specific peers.

Scaling beyond three:

* Add a fourth or fifth master via the :ref:`Dynamic Join
  <master-cluster-dynamic-join>` flow.  The joining master only needs
  ``cluster_id``, ``cluster_secret``, and *one* reachable peer in its
  ``cluster_peers`` list; the existing peers learn about it through
  the join handshake.
* Raft majorities tolerate ``(N-1)/2`` failures, so 5 masters survive
  2 simultaneous outages.  Even numbers of voters give no extra
  fault-tolerance for the cost.

.. _master-cluster-haproxy-ref:

HAProxy reference configuration
===============================

This is a complete HAProxy configuration that fronts the three masters
from :ref:`master-cluster-3node-ref`.  For the 2-node topology, drop
``server master-c ...`` from each backend.

.. code-block:: text

    global
        log /dev/log local0
        maxconn 16384
        user haproxy
        group haproxy
        daemon

    defaults
        mode tcp
        log global
        option dontlognull
        timeout connect 10s
        # timeout client/server are deliberately overridden per-frontend
        # below; the publish frontend in particular needs a very long
        # timeout because publish_session is 24h by default.
        timeout client 1m
        timeout server 1m
        retries 3

    # --------- publish (master -> minion) ---------
    frontend salt-master-pub
        mode tcp
        bind 10.27.5.116:4505
        option tcplog
        # publish_session default is 86400s; keep the LB timeout >= that
        # or the LB will tear down idle minion-subscriber sockets.
        timeout client 86400s
        default_backend salt-master-pub-backend

    backend salt-master-pub-backend
        mode tcp
        log global
        # roundrobin is correct here: each minion holds ONE long-lived
        # publish subscription, so the distribution happens at connect
        # time across newly-connecting minions, not per request.
        balance roundrobin
        timeout connect 10s
        timeout server 86400s
        server master-a 10.27.12.13:4505 check
        server master-b 10.27.7.126:4505 check
        server master-c 10.27.3.73:4505 check

    # --------- request / return (minion -> master) ---------
    frontend salt-master-req
        mode tcp
        bind 10.27.5.116:4506
        option tcplog
        timeout client 1m
        default_backend salt-master-req-backend

    backend salt-master-req-backend
        mode tcp
        log global
        # roundrobin again -- a request is a short-lived TCP connection
        # carrying a single AES-wrapped payload; any master in the
        # cluster can answer it because all peers share the cluster
        # AES key and route through the cluster cache layer.
        balance roundrobin
        timeout connect 10s
        timeout server 1m
        server master-a 10.27.12.13:4506 check
        server master-b 10.27.7.126:4506 check
        server master-c 10.27.3.73:4506 check

.. important::

    **Do not** add ``cluster_pool_port`` (``4520`` by default) to the
    minion-facing HAProxy.  That port carries cluster-internal Raft RPC
    and must reach every peer directly.  Exposing it through the
    minion LB will break the Raft majority calculation.

Minion configuration is unchanged from a single-master deployment --
the minion only needs the load-balancer VIP:

.. code-block:: yaml

    # /etc/salt/minion
    master: 10.27.5.116
    # master_alive_interval lets the minion notice a transport-level
    # outage faster than the kernel's keepalive timer.
    master_alive_interval: 30

.. _master-cluster-lb-tradeoffs:

Load balancer choices: sticky sessions vs. round-robin, transport
=================================================================

A clustered Salt deployment is one of the few cases where **round-robin
LB is correct and sticky sessions are wrong**.  The reasoning:

* **Publish (4505) is one long-lived subscription per minion.**  Once
  the minion connects, it stays connected.  Distribution happens at
  connection time; per-request balancing is not in play.  Round-robin
  spreads new minion connections evenly across peers.
* **Request (4506) is a short-lived per-call connection.**  Any master
  can answer it because all peers share the cluster AES key and the
  cluster cache layer routes job / grain reads to the correct peer
  internally.  Pinning a minion to one master via sticky sessions only
  defeats horizontal scaling and concentrates load on whichever peer
  the minion was first hashed to.

The transport choice (``transport: zeromq`` vs. ``transport: tcp``) is
independent of the LB choice, but has implications:

* ``zeromq`` (the default) speaks ZMTP over TCP.  HAProxy in ``mode
  tcp`` passes it through transparently; ZeroMQ's per-connection
  framing is preserved.
* ``transport: tcp`` is the native Salt TCP transport.  It is also
  passed through by HAProxy ``mode tcp`` unchanged.  If you use it,
  the load balancer config is identical -- only the timeouts and
  ``check`` intervals matter.

In both cases:

* Use ``mode tcp``, **not** ``mode http``.  Neither ZeroMQ nor Salt's
  TCP transport speak HTTP and ``mode http`` will reject the
  connection.
* Health checks default to TCP ``connect`` checks (the ``check``
  keyword on each ``server`` line).  That is enough to drop a dead
  peer; deeper health-checking (running ``salt-run
  cluster.ring_info`` from a sidecar) is optional and out of scope
  here.

.. _master-cluster-decisions:

Topology decisions that need maintainer sign-off
================================================

This section lists the decisions baked into the reference topologies
above so reviewers can confirm them against the implementation:

#. **Defaulting the reference topologies to
   ``cluster_isolated_filesystem: True``.**  Isolated-FS mode is newer
   (3008.0) but removes the shared-storage dependency from the
   reference implementation.  Shared-FS is still documented in
   :ref:`tutorial-master-cluster` for sites that already operate a
   reliable cluster filesystem.
#. **Round-robin LB on both 4505 and 4506 with no session
   stickiness.**  See :ref:`master-cluster-lb-tradeoffs` above for the
   reasoning.  Some operators have asked about source-IP hashing to
   "pin" a minion to a master for log locality; doing that is *not*
   recommended because it concentrates load on whichever peer a minion
   first hashed to.
#. **Two-node cluster: prefer split-brain refuse-writes over manual
   tiebreaker.**  A 2-node Raft cluster has no majority; the safe
   failure mode is to refuse writes from both sides during a
   partition.  We do not document a manual ``cluster.force_voter``
   workaround on purpose.
#. **No syndic / no multimaster failover combined with cluster.**
   Master cluster, syndic, and ``master_type: failover`` are three
   different HA models.  Combining cluster with syndic is possible but
   out of scope of this reference; mixing cluster with
   ``master_type: failover`` on the minion side is *not* supported and
   should not be documented as such.

.. seealso::

    * :ref:`tutorial-master-cluster` -- the shared-vs-isolated-FS
      comparison, the dynamic-join handshake, and the migration
      runbook between the two modes.
    * :ref:`mmap-cache` -- the recommended ``keys.cache_driver`` for
      isolated-filesystem clusters.
    * :ref:`tutorial-multi-master` -- the older "hot" multi-master
      pattern without a cluster.  Use this only when you cannot
      deploy a 3007+ cluster.
