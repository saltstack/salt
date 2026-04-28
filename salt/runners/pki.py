"""
Salt runner for PKI index management.

.. deprecated:: 3009.0
    Use :mod:`salt.runners.index` instead, e.g.
    ``salt-run index.compact name=pki`` and ``salt-run index.status name=pki``.
"""

import salt.utils.versions as versions


def rebuild_index(dry_run=False):
    """
    Rebuild the PKI mmap index from filesystem.

    .. deprecated:: 3009.0
        Use :py:func:`salt.runners.index.compact` with ``name='pki'``.

    With dry_run=True, shows what would be rebuilt without making changes.

    CLI Examples:

    .. code-block:: bash

        salt-run pki.rebuild_index
        salt-run pki.rebuild_index dry_run=True
    """
    versions.warn_until(
        "Potassium",
        "The 'pki' runner is deprecated and will be removed in Salt {version}. "
        "Use 'salt-run index.compact name=pki' (or index.status name=pki) instead.",
    )
    from salt.runners import (
        index as index_runner,  # pylint: disable=import-outside-toplevel
    )

    # Runner loader injects ``__opts__`` per module; tests may only patch ``pki``.
    index_runner.__opts__ = __opts__
    return index_runner.compact("pki", dry_run=dry_run)


def status():
    """
    Show PKI index statistics.

    .. deprecated:: 3009.0
        Use :py:func:`salt.runners.index.status` with ``name='pki'``.

    CLI Example:

    .. code-block:: bash

        salt-run pki.status
    """
    versions.warn_until(
        "Potassium",
        "The 'pki' runner is deprecated and will be removed in Salt {version}. "
        "Use 'salt-run index.status name=pki' instead.",
    )
    from salt.runners import (
        index as index_runner,  # pylint: disable=import-outside-toplevel
    )

    index_runner.__opts__ = __opts__
    return index_runner.status("pki")
