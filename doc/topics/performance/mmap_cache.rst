.. _mmap-cache:

===========================
Memory-Mapped Cache Backend
===========================

.. versionadded:: 3009.0

Salt's default cache backend (``localfs``) stores every entry as a file under
``cachedir``.  On large fleets that turns into millions of inodes, slow
directory scans (``salt-key -L``, target matching by grain or pillar) and
high syscall overhead on every store/fetch.

The ``mmap_cache`` family of backends replaces that file-per-entry layout
with a single memory-mapped hash-table file per bank, plus a segmented heap
for variable-size values.  Reads become memory-bandwidth-bound; writes become
one ``mmap`` index store plus one heap append.

Two backends ship together:

* :py:mod:`~salt.cache.mmap_cache` — generic key/value store, drop-in for
  ``localfs`` via the master :conf_master:`cache` setting.
* :py:mod:`~salt.cache.mmap_key` — specialised for the master's minion-key
  store (``keys`` and ``denied_keys`` banks), wired through the
  ``keys.cache_driver`` master setting.

Both share the same ``salt.utils.mmap_cache.MmapCache`` index/heap/roster
implementation, so the performance and durability properties below apply to
either.


When to switch
==============

Switch to ``mmap_cache`` when one or more of these is true on the master:

* ``salt-key -L`` takes seconds (or longer) to enumerate accepted keys.
* Targeting by grain or pillar (``salt -G``, ``salt -I``) noticeably stalls
  before publishes go out.
* The cache directory holds tens of thousands of files and ``ls`` /
  ``find`` against it is painful.
* Backups, antivirus scanners or container snapshotters spend disproportionate
  time iterating ``cachedir``.

Switch to ``mmap_key`` (independently of the generic backend) when ``salt-key``
operations or the master's authentication path are the bottleneck.

Conversely, ``localfs`` is fine — and stays the default — for small
deployments (a few hundred minions), for environments that explicitly need
the directory-tree shape (audit tooling, third-party scrapers), or for any
backend whose data lifecycle isn't a hot path.


Performance characteristics
===========================

All numbers below are for a 10 000-minion fleet on a single master with
warm page cache; treat them as relative shape, not absolutes.

.. list-table::
   :header-rows: 1
   :widths: 30 30 30

   * - Operation
     - ``localfs``
     - ``mmap_cache``
   * - ``store`` small
     - ~25 µs
     - ~8 µs
   * - ``store`` large (10 KB)
     - ~35 µs
     - ~10 µs
   * - ``fetch`` warm
     - ~20 µs
     - ~6 µs
   * - ``fetch`` large
     - ~25 µs
     - ~10 µs
   * - ``updated`` (mtime probe)
     - ~7 µs
     - ~2 µs
   * - ``list`` whole bank
     - O(N) ``listdir`` + N stat
     - O(occupied) roster pass
   * - ``salt-key -L`` (10 k keys)
     - ~10 s
     - ~5–10 ms
   * - Grain target match (10 k)
     - ~10 s
     - ~250 ms

Scaling shape:

* ``get`` / ``contains`` / ``updated`` are O(1) average — open-addressing hash
  probe in mmap'd memory.
* ``list`` and ``list_all`` are O(occupied) regardless of total table size,
  because they iterate a packed roster file rather than scanning every slot.
* ``store`` and ``delete`` are O(1) average plus one append/rewrite of the
  roster entry.
* The on-disk index is a fixed-size file (``size × slot_size`` bytes); the
  heap is segmented and rolls a new segment at ``max_segment_bytes`` (1 GiB
  default), so individual segments stay below filesystem-friendly limits.


Configuration
=============

Generic cache backend
---------------------

Set the master ``cache`` option to ``mmap_cache``:

.. code-block:: yaml

    cache: mmap_cache

That's the only required change.  Optional tunables (defaults shown) live
alongside the standard cache options:

.. code-block:: yaml

    # Number of slots in each bank's index file.  Pick ~2× the maximum
    # number of keys you expect in any bank.
    mmap_cache_size: 1000000

    # Bytes per index slot.  Must be at least 1 + key_size + 20.
    mmap_cache_slot_size: 96

    # Maximum bytes per heap segment before a new segment rolls.
    mmap_cache_max_segment_bytes: 1073741824  # 1 GiB

    # Verify CRC on every heap read.  Default True; set False to trade a
    # small CRC check for ~1–2 % per-op throughput in trusted environments.
    mmap_cache_verify_checksums: true

Minion-key backend
------------------

The minion-key store has its own driver setting:

.. code-block:: yaml

    keys.cache_driver: mmap_key

Set this independently of ``cache``.  The two backends share an
implementation but live in different bank trees, so you can switch one
without the other.

``mmap_key`` is the recommended driver for isolated-filesystem master
clusters (:conf_master:`cluster_isolated_filesystem`).  Its deterministic
per-bank layout makes the key files safe to push between peers as opaque
blobs over the cluster transport, which is what the cluster state-sync
relies on.  See :ref:`tutorial-master-cluster` for the migration
walkthrough.

Migrating an existing master
============================

Both backends ship migration runners that walk the existing on-disk store
and load it into the new format.  Run them before flipping the relevant opt
in ``/etc/salt/master``; both are idempotent and safe to re-run.

Generic cache (``localfs`` → ``mmap_cache``)
--------------------------------------------

.. code-block:: bash

    # Preview — counts entries that would be migrated, writes nothing.
    salt-run cache.migrate dry_run=True

    # Migrate every bank.
    salt-run cache.migrate

    # Restrict to a single bank tree.
    salt-run cache.migrate bank=minions

After the migration completes, edit ``/etc/salt/master`` to set
``cache: mmap_cache`` and restart the master.

Minion keys (``localfs_key`` → ``mmap_key``)
--------------------------------------------

.. code-block:: bash

    # Preview — file-system count of accepted/pending/rejected/denied keys.
    salt-run pki.migrate_to_mmap dry_run=True

    # Load the existing PKI tree into the mmap_key index.
    salt-run pki.migrate_to_mmap

Then set ``keys.cache_driver: mmap_key`` and restart the master.  The
on-disk PKI files remain in place as the durable record; the mmap index is
the lookup accelerator.


Durability and concurrency
==========================

Writes are durable.  Every ``store`` / ``delete`` / ``atomic_rebuild`` call:

#. Writes the heap record, ``flush()`` + ``fsync`` on the heap fd.
#. Updates the index slot, ``msync`` + ``fsync`` on the index fd.
#. Updates the roster, ``flush()`` + ``fsync`` on the roster fd.

A crash between steps is recoverable: the index header tracks
``occupied_count``, the roster is rebuilt from the index on the next
``open(write=True)`` if their entry counts diverge.

Multiple master worker processes can read and write the same bank
concurrently.  Writers serialise through ``fcntl.flock`` on a per-bank
``.lock`` file; readers do not lock and use shared mmaps so they see
writes immediately through the page cache.  Cross-process consistency was
hardened in 3009.0 — see the test suite under
``tests/pytests/functional/utils/test_mmap_cache.py::TestMultiProcess``.


Sizing the index
================

The index file is preallocated to ``size × slot_size`` bytes.  Defaults
(``size=1_000_000``, ``slot_size=96``) reserve **96 MiB of virtual address
space per bank** — not resident RAM, the kernel pages it on demand.  Pick
``size`` to be roughly twice the maximum number of keys you expect in any
bank: a 60 % load factor keeps probe chains short under linear probing.

For very large fleets, raise ``mmap_cache_size`` rather than running multiple
caches.  The heap-segment cap (``mmap_cache_max_segment_bytes``) applies
independently and rolls a new segment file when the active one fills, so the
total store can exceed any single segment's size.


Compaction
==========

Deletes mark slots as DELETED and leave heap bytes as garbage.  Over time
that grows the on-disk footprint without changing live data.

The index header tracks live and deleted counts, so ``cache.get_stats(bank)``
reports the fragmentation ratio.  Run ``MmapCache.atomic_rebuild`` to
defragment — it writes a fresh index, heap, and roster, then atomically
swaps all three.  A runner-level entry point for this is on the roadmap.

For Raft and other consensus uses, log compaction maps directly to
``atomic_rebuild`` after a snapshot — the unused log-entry heap regions are
reclaimed in the same pass.


See also
========

* :py:mod:`salt.cache.mmap_cache` — generic backend module reference.
* :py:mod:`salt.cache.mmap_key` — minion-key backend module reference.
* :py:mod:`salt.utils.mmap_cache` — underlying ``MmapCache`` index/heap/roster
  implementation.
* :conf_master:`cache` — master option to select the cache backend.
* :conf_master:`keys.cache_driver` — master option to select the keys backend.
* :ref:`tutorial-master-cluster` — isolated-filesystem master clusters use
  ``mmap_key`` for the minion-key store.
