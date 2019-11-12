.. _tutorial-multi-master:

=====================
Multi Master Tutorial
=====================

As of Salt 0.16.0, the ability to connect minions to multiple masters has been
made available. The multi-master system allows for redundancy of Salt
masters and facilitates multiple points of communication out to minions. When
using a multi-master setup, all masters are running hot, and any active master
can be used to send commands out to the minions.

.. note::
    If you need failover capabilities with multiple masters, there is also a
    MultiMaster-PKI setup available, that uses a different topology
    `MultiMaster-PKI with Failover Tutorial <http://docs.saltstack.com/en/latest/topics/tutorials/multimaster_pki.html>`_

In 0.16.0, the masters do not share any information, keys need to be accepted
on both masters, and shared files need to be shared manually or use tools like
the git fileserver backend to ensure that the :conf_master:`file_roots` are
kept consistent.

Beginning with Salt 2016.11.0, the :ref:`Pluggable Minion Data Cache <pluggable-data-cache>`
was introduced. The minion data cache contains the Salt Mine data, minion grains, and minion
pillar information cached on the Salt Master. By default, Salt uses the ``localfs`` cache
module, but other external data stores can be used instead.

Using a pluggable minion cache modules allows for the data stored on a Salt Master about
Salt Minions to be replicated on other Salt Masters the Minion is connected to. Please see
the :ref:`Minion Data Cache <cache>` documentation for more information and configuration
examples.

Summary of Steps
----------------

1. Create a redundant master server
2. Copy primary master key to redundant master
3. Start redundant master
4. Configure minions to connect to redundant master
5. Restart minions
6. Accept keys on redundant master

Prepping a Redundant Master
---------------------------

The first task is to prepare the redundant master. If the redundant master is
already running, stop it. There is only one requirement when preparing a
redundant master, which is that masters share the same private key. When the
first master was created, the master's identifying key pair was generated and
placed in the master's ``pki_dir``. The default location of the master's key
pair is ``/etc/salt/pki/master/``. Take the private key, ``master.pem``, and
copy it to the same location on the redundant master. Do the same for the
master's public key, ``master.pub``. Assuming that no minions have yet been
connected to the new redundant master, it is safe to delete any existing key
in this location and replace it.

.. note::
    There is no logical limit to the number of redundant masters that can be
    used.

Once the new key is in place, the redundant master can be safely started.

Configure Minions
-----------------

Since minions need to be master-aware, the new master needs to be added to the
minion configurations. Simply update the minion configurations to list all
connected masters:

.. code-block:: yaml

    master:
      - saltmaster1.example.com
      - saltmaster2.example.com

Now the minion can be safely restarted.

.. note::

    If the ipc_mode for the minion is set to TCP (default in Windows), then
    each minion in the multi-minion setup (one per master) needs its own
    tcp_pub_port and tcp_pull_port.

    If these settings are left as the default 4510/4511, each minion object
    will receive a port 2 higher than the previous. Thus the first minion will
    get 4510/4511, the second will get 4512/4513, and so on. If these port
    decisions are unacceptable, you must configure tcp_pub_port and
    tcp_pull_port with lists of ports for each master. The length of these
    lists should match the number of masters, and there should not be overlap
    in the lists.

Now the minions will check into the original master and also check into the new
redundant master. Both masters are first-class and have rights to the minions.

.. note::

    Minions can automatically detect failed masters and attempt to reconnect
    to them quickly. To enable this functionality, set
    `master_alive_interval` in the minion config and specify a number of
    seconds to poll the masters for connection status.

    If this option is not set, minions will still reconnect to failed masters
    but the first command sent after a master comes back up may be lost while
    the minion authenticates.

Sharing Files Between Masters
-----------------------------

Salt does not automatically share files between multiple masters. A number of
files should be shared or sharing of these files should be strongly considered.

Minion Keys
```````````

Minion keys can be accepted the normal way using :strong:`salt-key` on both
masters.  Keys accepted, deleted, or rejected on one master will NOT be
automatically managed on redundant masters; this needs to be taken care of by
running salt-key on both masters or sharing the
``/etc/salt/pki/master/{minions,minions_pre,minions_rejected}`` directories
between masters.

.. note::

    While sharing the :strong:`/etc/salt/pki/master` directory will work, it is
    strongly discouraged, since allowing access to the :strong:`master.pem` key
    outside of Salt creates a *SERIOUS* security risk.

File_Roots
``````````

The :conf_master:`file_roots` contents should be kept consistent between
masters. Otherwise state runs will not always be consistent on minions since
instructions managed by one master will not agree with other masters.

The recommended way to sync these is to use a fileserver backend like gitfs or
to keep these files on shared storage.

.. important::
   If using gitfs/git_pillar with the cachedir shared between masters using
   `GlusterFS`_, nfs, or another network filesystem, and the masters are
   running Salt 2015.5.9 or later, it is strongly recommended not to turn off
   :conf_master:`gitfs_global_lock`/:conf_master:`git_pillar_global_lock` as
   doing so will cause lock files to be removed if they were created by a
   different master.

.. _GlusterFS: http://www.gluster.org/

Pillar_Roots
````````````

Pillar roots should be given the same considerations as
:conf_master:`file_roots`.

Master Configurations
`````````````````````

While reasons may exist to maintain separate master configurations, it is wise
to remember that each master maintains independent control over minions.
Therefore, access controls should be in sync between masters unless a valid
reason otherwise exists to keep them inconsistent.

These access control options include but are not limited to:

- external_auth
- publisher_acl
- peer
- peer_run
