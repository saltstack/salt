.. _resources-configuration:

=============
Configuration
=============

.. versionadded:: 3008.0

Configuration options that control the resource subsystem. All
options are read from the standard master/minion config files; the
side column indicates which daemon honours each one.


Minion options
==============

.. conf_minion:: resource_pillar_key

``resource_pillar_key``
-----------------------

Default: ``resources``

The pillar key under which the managing minion looks for resource
declarations. The minion's pillar must contain this key (a dict) for
any resource type to be discovered.

.. code-block:: yaml

    # /etc/salt/minion.d/resources.conf
    resource_pillar_key: salt_resources

When set, the matching pillar key on each minion must use the same
name — the master assumes one canonical key when reading resource
declarations across minions.

Setting this to an empty string logs a warning and falls back to the
default.

See :ref:`resources-authoring-pillar` for the pillar layout under this
key.


Master options
==============

.. conf_master:: resource_index_primary_capacity

``resource_index_primary_capacity``
------------------------------------

Default: ``2097152`` (``1 << 21``)

The number of slots in the master's mmap-backed primary resource
index. Each slot holds one ``SRN → managing-minion`` mapping; the
index uses linear probing, so reserved capacity is also the upper
bound on resources the master can register before compaction is
required.

Sizing rule of thumb: pick a capacity at least 4× your expected
peak resource count, round up to a power of two. The default
(2 097 152) fits ~500 K resources comfortably with room for the
hash-table fill factor to stay under 25 %.

Increasing this option requires recreating the on-disk index file —
delete ``<cachedir>/resources/resource_index.by_id.mmap`` on the
master before restarting if you raise the capacity.

.. conf_master:: resource_index_primary_slot_size

``resource_index_primary_slot_size``
-------------------------------------

Default: ``128``

Per-slot byte budget in the primary resource index. Each slot stores
the SRN key, the JSON payload (``{"m": ..., "t": ...}``), and a small
header. 128 bytes accommodates ~80-character SRNs comfortably.

Raise this only if your environment uses very long resource ids or
type names. Like ``resource_index_primary_capacity``, changing this
option requires recreating the on-disk index file.


``resource_pillar_key`` on the master
-------------------------------------

The master reads :conf_minion:`resource_pillar_key` from its **own**
config to know how to read minion pillar caches when expanding
targets (the master compiles minion pillar on its side too — see
``_resource_ids_from_minion_pillar_cache``). Keep the value
consistent across master and all minions.


Pillar
======

Resource declarations live under :conf_minion:`resource_pillar_key`
on each minion's pillar. See :ref:`resources-authoring-pillar` for the
full shape; the relevant configuration aspect is that **every minion
managing resources of the same type must agree on the type's pillar
shape**. The connection module is the contract.


Inspection
==========

To verify the master's view of registered resources:

.. code-block:: bash

    salt-run resource.list_grains
    salt-run resource.show_grains type=ssh id=web-01

To force a re-registration after a config change:

.. code-block:: bash

    # On the managing minion
    salt-call saltutil.refresh_pillar

    # Or from the master, targeted at one minion
    salt-run resource.refresh minion=<minion-id>

See :ref:`resources-operations` for more.


Sizing guidance
===============

Worked example: a master fleet of 1 000 minions, each managing
100 resources on average, with peak bursts up to 200 per minion.

* Peak total = 200 × 1 000 = 200 000 resources.
* Capacity = 200 000 × 4 = 800 000 → round up to 1 048 576 (``1 << 20``).
* Default capacity (2 097 152) is already 2× that — leave it.

Sizing the on-disk file:
``capacity × slot_size`` = 2 097 152 × 128 = 256 MiB at the default.
File grows as needed, but plan for it.
