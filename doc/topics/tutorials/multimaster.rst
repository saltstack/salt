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

Now the minions will check into the original master and also check into the new
redundant master. Both masters are first-class and have rights to the minions.

.. note::

    Minions can automatically detect failed masters and attempt to reconnect
    to reconnect to them quickly. To enable this functionality, set
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
- client_acl
- peer
- peer_run
