salt.cache.mmap_cache
=====================

A memory-mapped cache backend, drop-in for ``localfs``.  On large fleets
``mmap_cache`` runs orders of magnitude faster than the default
file-per-entry layout — see :ref:`mmap-cache` for benchmark numbers,
sizing guidance, and the migration path.

.. automodule:: salt.cache.mmap_cache
    :members:
