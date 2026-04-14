"""
Salt runner for PKI index management.

.. versionadded:: 3009.0
"""

import logging

log = logging.getLogger(__name__)


def rebuild_index(dry_run=False):
    """
    Rebuild the PKI mmap index from filesystem.

    With dry_run=True, shows what would be rebuilt without making changes.

    CLI Examples:

    .. code-block:: bash

        # Rebuild the index
        salt-run pki.rebuild_index

        # Check status without rebuilding (dry-run)
        salt-run pki.rebuild_index dry_run=True
    """
    from salt.cache import localfs_key  # pylint: disable=import-outside-toplevel

    stats_before = localfs_key.get_index_stats(__opts__)

    if dry_run:
        if not stats_before:
            return "PKI index does not exist or is not accessible."

        pct_tombstones = (
            (
                stats_before["deleted"]
                / (stats_before["occupied"] + stats_before["deleted"])
                * 100
            )
            if (stats_before["occupied"] + stats_before["deleted"]) > 0
            else 0
        )

        return (
            f"PKI Index Status:\n"
            f"  Total slots: {stats_before['total']:,}\n"
            f"  Occupied: {stats_before['occupied']:,}\n"
            f"  Deleted (tombstones): {stats_before['deleted']:,}\n"
            f"  Empty: {stats_before['empty']:,}\n"
            f"  Load factor: {stats_before['load_factor']:.1%}\n"
            f"  Tombstone ratio: {pct_tombstones:.1f}%\n"
            f"\n"
            f"Rebuild recommended: {'Yes' if pct_tombstones > 25 else 'No'}"
        )

    # Perform rebuild
    log.info("Starting PKI index rebuild")
    result = localfs_key.rebuild_index(__opts__)

    if not result:
        return "PKI index rebuild failed. Check logs for details."

    stats_after = localfs_key.get_index_stats(__opts__)

    if stats_before and stats_after:
        tombstones_removed = stats_before["deleted"]
        return (
            f"PKI index rebuilt successfully.\n"
            f"  Keys: {stats_after['occupied']:,}\n"
            f"  Tombstones removed: {tombstones_removed:,}\n"
            f"  Load factor: {stats_after['load_factor']:.1%}"
        )
    else:
        return "PKI index rebuilt successfully."


def status():
    """
    Show PKI index statistics.

    CLI Example:

    .. code-block:: bash

        salt-run pki.status
    """
    # Just call rebuild_index with dry_run=True
    return rebuild_index(dry_run=True)
