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


Reference Implimentation
========================

Gluster: https://docs.gluster.org/en/main/Quick-Start-Guide/Quickstart/

HAProxy:

.. code-block:: text

        frontend salt-master-pub
            mode tcp
            bind 10.27.5.116:4505
            option tcplog
            timeout client  1m
            default_backend salt-master-pub-backend

        backend salt-master-pub-backend
            mode tcp
            option tcplog
            #option log-health-checks
            log global
            #balance source
            balance roundrobin
            timeout connect 10s
            timeout server 1m
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
            option tcplog
            #option log-health-checks
            log global
            balance roundrobin
            #balance source
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
