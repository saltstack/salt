salt.cache.mmap_key
===================

A memory-mapped backend specialised for the master's minion-key store
(``keys`` and ``denied_keys`` banks).  Replaces the ``localfs_key``
directory layout with an O(1) hash table; ``salt-key -L`` and
authentication probes drop from seconds to milliseconds at fleet scale.
See :ref:`mmap-cache` for the full performance picture and migration
runner.

.. automodule:: salt.cache.mmap_key
    :members:
