"""
Salt runner for PKI key management utilities.

.. versionadded:: 3009.0
"""

import logging

log = logging.getLogger(__name__)


def migrate_to_mmap(dry_run=False):
    """
    Migrate PKI keys from the legacy filesystem layout into the mmap_key backend.

    Scans ``pki_dir`` for existing accepted/pending/rejected/denied keys and
    loads them into the mmap_key index+heap files.  Safe to run repeatedly —
    already-present keys are overwritten in-place.

    With ``dry_run=True``, counts the keys that *would* be migrated without
    writing anything.

    CLI Examples:

    .. code-block:: bash

        # Preview what would be migrated
        salt-run pki.migrate_to_mmap dry_run=True

        # Perform the migration
        salt-run pki.migrate_to_mmap
    """
    import os  # pylint: disable=import-outside-toplevel

    pki_dir = __opts__.get("pki_dir", "")

    state_dirs = {
        "minions": "accepted",
        "minions_pre": "pending",
        "minions_rejected": "rejected",
    }

    counts = {"accepted": 0, "pending": 0, "rejected": 0, "denied": 0}

    for dir_name, state in state_dirs.items():
        dir_path = os.path.join(pki_dir, dir_name)
        if not os.path.isdir(dir_path):
            continue
        try:
            with os.scandir(dir_path) as it:
                for entry in it:
                    if not entry.is_file() or entry.is_symlink():
                        continue
                    if not entry.name.startswith("."):
                        counts[state] += 1
        except OSError as exc:
            log.error("pki.migrate_to_mmap: cannot scan %s: %s", dir_path, exc)

    denied_path = os.path.join(pki_dir, "minions_denied")
    if os.path.isdir(denied_path):
        try:
            with os.scandir(denied_path) as it:
                for entry in it:
                    if entry.is_file() and not entry.is_symlink():
                        counts["denied"] += 1
        except OSError as exc:
            log.error("pki.migrate_to_mmap: cannot scan %s: %s", denied_path, exc)

    total = sum(counts.values())

    if dry_run:
        return (
            f"PKI migration dry-run (no changes written):\n"
            f"  Accepted: {counts['accepted']:,}\n"
            f"  Pending:  {counts['pending']:,}\n"
            f"  Rejected: {counts['rejected']:,}\n"
            f"  Denied:   {counts['denied']:,}\n"
            f"  Total:    {total:,}"
        )

    from salt.cache import mmap_key  # pylint: disable=import-outside-toplevel

    mmap_key.__opts__ = __opts__
    result = mmap_key.rebuild_from_localfs(__opts__)

    return (
        f"PKI keys migrated to mmap_key backend successfully.\n"
        f"  Accepted: {result['accepted']:,}\n"
        f"  Pending:  {result['pending']:,}\n"
        f"  Rejected: {result['rejected']:,}\n"
        f"  Denied:   {result['denied']:,}\n"
        f"  Total:    {sum(result.values()):,}"
    )


def status():
    """
    Show PKI key counts from the filesystem layout.

    CLI Example:

    .. code-block:: bash

        salt-run pki.status
    """
    return migrate_to_mmap(dry_run=True)
