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

Running a cluster master requires all nodes in the cluster to have a shared
filesystem. The `cluster_pki_dir`, `cache_dir`, `file_roots` and `pillar_roots`
must all be on a shared filesystem. Most implementations will also serve the
masters publish and request server ports via a tcp load balancer. All of the
masters in a cluster are assumed to be running on a reliable local area
network.

Each master in a cluster maintains its own public and private key, and an in
memory aes key. Each cluster peer also has access to the `cluster_pki_dir`
where a cluster wide public and private key are stored. In addition, the cluster
wide aes key is generated and stored in the `cluster_pki_dir`. Further,
when operating as a cluster, minion keys are stored in the `cluster_pki_dir`
instead of the master's `pki_dir`.


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
