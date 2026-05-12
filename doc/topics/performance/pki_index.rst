.. _pki_index:

====================
PKI Index Operations
====================

The PKI index is an optional, high-performance optimization designed for Salt
environments with a large number of minions.

Overview
========

By default, the Salt Master performs linear directory scans to find minion
public keys during authentication and job publication. As the number of minions
grows into the thousands, these disk I/O operations can become a significant
bottleneck.

The PKI index replaces these linear scans with a constant-time O(1) lookup
using a memory-mapped hash table. This substantially reduces disk I/O and
improves Master responsiveness.

Enabling the Index
==================

To enable the PKI index, add the following to your Master configuration file:

.. code-block:: yaml

    pki_index_enabled: True

Configuration
=============

While the default settings work for most environments, you can tune the index
using these options:

* :conf_master:`pki_index_size`: The number of slots in the hash table (default: 1,000,000).
* :conf_master:`pki_index_slot_size`: The size of each slot in bytes (default: 128).

Monitoring and Management
=========================

You can check the status of your PKI index or force a manual rebuild using the
:ref:`PKI runner <all-salt.runners.pki>`:

.. code-block:: bash

    # Check index status and load factor
    salt-run pki.status

    # Manually rebuild the index from the filesystem
    salt-run pki.rebuild_index
