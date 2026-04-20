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

The static configuration above requires every master to list every other peer
in ``cluster_peers`` up front. When you want to grow a running cluster --
for example to auto-scale behind a load balancer, or to replace a failed
peer -- the existing masters do not need to be reconfigured. A new master
can bootstrap itself into the cluster as long as it:

* Shares the ``cluster_pki_dir`` (and ``cachedir``, ``file_roots``,
  ``pillar_roots``) with the existing peers, typically via the same shared
  filesystem described above.
* Is configured with the same ``cluster_id`` as the existing cluster.
* Lists **at least one** reachable existing peer in ``cluster_peers``. It
  does not need to know about every peer; the cluster will tell the joining
  master about the others.
* Is configured with the same ``cluster_secret`` as the existing peers.

On startup the joining master waits a short grace period and then runs a
discover/join handshake against each address in its ``cluster_peers`` list.


Joining Master Config
---------------------

A minimal configuration for a fourth master joining the three-node cluster
shown above looks like this:

.. code-block:: yaml

        id: 10.27.9.42
        cluster_id: master_cluster
        cluster_peers:
          - 10.27.12.13
        cluster_pki_dir: /my/gluster/share/pki
        cluster_secret: "d8b4c2e1f07a4c3e8a1b5d0a9c7f3e42b6d9a1c4f8e2b7d0a3c6e9f1b4d7a0c3"
        cachedir: /my/gluster/share/cache
        file_roots:
          base:
            - /my/gluster/share/srv/salt
        pillar_roots:
          base:
            - /my/gluster/share/srv/pillar

Only the joining master needs a list of peers that is smaller than the final
cluster topology. The existing masters keep their original configuration;
they do not need to have ``10.27.9.42`` added to their ``cluster_peers``
before it comes up. Once the join completes they learn about the new peer
from the handshake and from the ``cluster/peer/join-notify`` event that the
contacted peer forwards to the rest of the cluster.

After the join succeeds the new master is routed to by the load balancer
like any other peer. Remember to add it to the HAProxy backend pools (or
equivalent) so that minion publish/return traffic starts reaching it.


Handshake Overview
------------------

The join handshake runs over the existing cluster event bus. At a high
level:

#. **discover** -- the joining master signs a payload containing its
   ``peer_id``, its master public key, and a random token with its own
   private key and fires it to each configured peer on the
   ``cluster/peer/discover`` tag.
#. **discover-reply** -- each peer that receives the discover event
   verifies the signature, then replies on ``cluster/peer/discover-reply``
   with its own master public key, the shared ``cluster_pki_dir`` public
   key, and a fresh token, signed with its own private key. The joining
   master verifies the signature against the public key the peer just
   provided.
#. **join** -- the joining master encrypts
   ``token + cluster_secret`` and ``token + <its-aes-session-key>`` with
   the peer's public key, signs the whole payload with its own private
   key, and fires it on ``cluster/peer/join``.
#. **join-reply** / **join-notify** -- the receiving peer decrypts the
   payload, rejects the join if ``cluster_secret`` does not match its own,
   and otherwise (a) writes the joining master's public key into
   ``cluster_pki_dir/peers/<peer_id>.pub``, (b) adds the new peer to its
   in-memory ``cluster_peers`` list, (c) replies to the joiner with the
   shared cluster public key and the current in-memory AES session key,
   each encrypted with the joiner's public key and signed with the peer's
   private key, and (d) emits a ``cluster/peer/join-notify`` so the rest
   of the cluster learns about the new peer and converges on the same AES
   session key.

Once the handshake is complete the new master holds the same in-memory
AES session key as every other peer, so minions behind the load balancer
can transparently fail between old and new peers.


Security Considerations
-----------------------

* ``cluster_secret`` is the authentication token that prevents an attacker
  who can reach a peer on the cluster transport from joining the cluster.
  Treat it like a long-lived shared credential: generate a high-entropy
  value, distribute it over a secure channel (configuration management
  with encrypted pillars, a secret manager, etc.), and rotate it by
  updating it on every peer and restarting them in a rolling fashion. An
  unset or empty ``cluster_secret`` is accepted only if both sides have
  the same empty value, which is not a meaningful check; always set one
  in production.
* The discover/join payloads are signed with per-master private keys and
  sensitive fields (the secret, the AES session key, the cluster key) are
  encrypted with the recipient's public key, so passive observers on the
  cluster network cannot recover them. An attacker who has obtained a
  copy of ``cluster_secret`` **and** can reach the cluster transport can
  still join, which is why restricting the cluster transport to a
  trusted local network -- as called out in "Minimum Requirements" --
  remains important.
* The joining master learns the shared cluster public key from the
  discover-reply. In the shared-filesystem topology described above the
  joining master already has access to ``cluster_pki_dir`` on disk, so it
  is reading the cluster public key from a trusted source. If you cannot
  rely on a shared filesystem -- for example when bootstrapping a master
  from a provisioning system that does not yet have the cluster
  filesystem mounted -- set ``cluster_pub_fingerprint`` on the joining
  master to the SHA-256 hex digest of the PEM-encoded cluster public key.
  Any discover-reply whose advertised key does not hash to that value
  will be rejected. See :conf_master:`cluster_pub_fingerprint` for
  details. ``cluster_secret`` remains required in either mode: it is what
  prevents a master that does not know the shared secret from completing
  a join, regardless of whether the fingerprint is pinned.


Removing a Peer
---------------

There is no on-the-wire leave protocol; a peer that is shut down simply
stops responding to cluster events and load-balancer health checks. To
permanently decommission a peer:

#. Remove it from the load-balancer backend pools so no new traffic is
   routed to it.
#. Stop the master process on that host.
#. Remove its public key from ``cluster_pki_dir/peers/<peer_id>.pub`` on
   the shared filesystem.
#. Restart the remaining masters (rolling is fine) so they drop the
   removed peer from their in-memory ``cluster_peers`` lists.

If you also want to invalidate the decommissioned peer's ability to
re-join, rotate ``cluster_secret`` across the remaining peers at the same
time.
