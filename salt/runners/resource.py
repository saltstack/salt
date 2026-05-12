"""
Operator-facing helpers for inspecting Salt Resources state on the master.

.. versionadded:: 3008.0

The mmap-backed registry (``salt.utils.resource_registry``) is the master's
authority for *which* minions manage which resources. The
``resource_grains`` cache bank (populated by the master's
``_register_resources`` handler from each minion's
:meth:`salt.minion.Minion._collect_resource_grains` payload) is the source
of truth for the per-resource grain dicts that drive ``salt -G`` /
``salt -P`` / ``salt -C 'G@…'`` matching.

This runner exposes thin read-only views over both so operators can debug
"why didn't ``salt -G '<key>:<value>' test.ping`` match my resource?"
without spelunking through pickled cache files by hand.

CLI examples::

    salt-run resource.show_grains type=dummy id=dummy-01
    salt-run resource.list_grains
    salt-run resource.refresh minion=resources-minion
"""

import logging

import salt.utils.event
import salt.utils.resource_registry

log = logging.getLogger(__name__)


def _resource_grains_cache(opts):
    """Return the ``salt.cache`` handle for the ``resource_grains`` bank."""
    import salt.cache  # pylint: disable=import-outside-toplevel

    return salt.cache.factory(opts)


def show_grains(type, id):  # noqa: A002 — keep CLI-friendly param names
    """
    Return the per-resource grain dict the master has cached for one
    resource, or ``None`` if no entry exists.

    The resource is addressed by the same composite SRN the registry
    uses internally: ``"<type>:<id>"``.

    CLI Example:

    .. code-block:: bash

        salt-run resource.show_grains type=dummy id=dummy-01

    :param str type: The resource type (e.g. ``"dummy"``, ``"ssh"``).
    :param str id: The bare resource id (e.g. ``"dummy-01"``).
    :rtype: dict or None
    """
    if not type or not id:
        return None
    cache = _resource_grains_cache(__opts__)  # pylint: disable=undefined-variable
    bank = salt.utils.resource_registry.RESOURCE_GRAINS_BANK
    try:
        return cache.fetch(bank, f"{type}:{id}")
    except Exception as exc:  # pylint: disable=broad-except
        log.warning("resource.show_grains(%s:%s) failed: %s", type, id, exc)
        return None


def list_grains():
    """
    Return every SRN currently in the master's ``resource_grains`` cache
    bank along with a short summary (top-level grain keys, count).

    Useful for sanity-checking that a minion's last
    ``_register_resources`` actually landed.

    CLI Example:

    .. code-block:: bash

        salt-run resource.list_grains
    """
    cache = _resource_grains_cache(__opts__)  # pylint: disable=undefined-variable
    bank = salt.utils.resource_registry.RESOURCE_GRAINS_BANK
    try:
        srns = list(cache.list(bank) or [])
    except Exception as exc:  # pylint: disable=broad-except
        log.warning("resource.list_grains: cannot list bank: %s", exc)
        return {}
    summary = {}
    for srn in srns:
        try:
            gdict = cache.fetch(bank, srn) or {}
        except Exception:  # pylint: disable=broad-except
            continue
        if not isinstance(gdict, dict):
            continue
        summary[srn] = {
            "grain_keys": sorted(gdict.keys()),
            "grain_count": len(gdict),
        }
    return summary


def refresh(minion):
    """
    Ask one minion to re-render its per-resource grains and re-publish
    them to the master's ``resource_grains`` bank.

    Fires the ``resource_refresh`` event at the minion via the master
    event bus; the minion's event handler re-runs
    ``_discover_resources`` + ``_register_resources_with_master``.

    Use this when a resource's underlying state changed out-of-band
    (e.g. the operator updated metadata via the resource's connection
    module) and you need the master's grain bank to reflect it without
    waiting for the next pillar refresh.

    CLI Example:

    .. code-block:: bash

        salt-run resource.refresh minion=resources-minion

    :param str minion: Minion ID to send the event to.
    :rtype: bool
    """
    if not minion:
        return False
    with salt.utils.event.get_event(
        "master",
        sock_dir=__opts__["sock_dir"],  # pylint: disable=undefined-variable
        opts=__opts__,  # pylint: disable=undefined-variable
        listen=False,
    ) as evt:
        try:
            evt.fire_event(
                {"minion": minion},
                f"minion/{minion}/resource_refresh",
            )
            return True
        except Exception as exc:  # pylint: disable=broad-except
            log.warning("resource.refresh(%s) failed: %s", minion, exc)
            return False
