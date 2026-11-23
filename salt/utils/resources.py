"""
Helpers for Salt resource minions.

Resource inventory is declared on the minion via a top-level minion opt
``resource_types`` (list of type names) plus whatever per-type opts each
module needs (e.g. ``dummy_resource_count`` for the dummy module).  Pillar
is **not** the source of resource inventory -- holding a 200K-resource
grain dict in ``opts["pillar"]["resources"]`` violates the minion memory
ceiling (see ``feedback-no-resource-data-in-pillar`` and
``feedback-minion-never-holds-full-resource-set``).

Resource module ``discover(opts)`` contract::

    discover(opts) -> Iterable[str]

        Yield bare resource IDs this minion manages for a given type.
        MAY be a generator; the register loop consumes it exactly once.
        Implementations SHOULD NOT buffer the full set in memory when
        the source is sequential/countable.

        The caller (minion ``_register_resources_with_master``) is
        responsible for chunking.  A single call to ``discover()``
        returns one iterable for the full inventory; chunking happens
        at the register-loop level.
"""

import logging

log = logging.getLogger(__name__)


def enabled_resource_types(opts):
    """
    Return the list of resource types this minion is configured to load.

    Configured by the minion option ``resource_types`` -- a list of
    strings.  Empty / missing / wrong-shape values yield an empty list
    (minion manages no resources).
    """
    types = opts.get("resource_types") or []
    if not isinstance(types, list):
        log.warning(
            "resource_types must be a list; got %r -- treating as empty",
            type(types).__name__,
        )
        return []
    return [t for t in types if isinstance(t, str) and t]


def bare_resource_ids_from_decl(decl):
    """
    Flatten ``salt_resources`` grains-subtree mappings to bare IDs.

    Supports ``{rtype: [id, ...]}`` (post-discovery) and
    ``{rtype: {"resource_ids": [...]}}`` (legacy-shaped) layouts.
    Used by the grains-cache fallback in
    :func:`bare_resource_id_in_minion_data_cache`.
    """
    if not isinstance(decl, dict):
        return []
    out = []
    for val in decl.values():
        if isinstance(val, list):
            out.extend(val)
        elif isinstance(val, dict):
            ids = val.get("resource_ids")
            if isinstance(ids, list):
                out.extend(ids)
    return out


def bare_resource_id_in_minion_data_cache(opts, resource_id, cache=None):
    """
    Return ``True`` if ``resource_id`` appears in any cached minion
    grains snapshot on the master.

    Used when the mmap resource registry has not yet recorded the ID (or
    was cleared) but :conf_master:`minion_data_cache` still holds grains
    from the last sync -- so ``salt m2-dummy2 state.apply`` /
    ``test.ping`` style targeting can still resolve for offline minions.

    The pillar-reading branch of this helper was removed when pillar
    stopped being the source of resource inventory; the grains-cache
    branch (``salt_resources`` grain) remains as the only fallback.

    :param cache:
        Optional :class:`salt.cache.Cache` from the caller (e.g.
        :class:`salt.utils.minions.CkMinions` already constructs one).
        A new default cache is created when ``cache`` is omitted.
    """
    if not opts.get("minion_data_cache") or not resource_id:
        return False
    try:
        import salt.cache  # noqa: PLC0415

        grains_cache = cache if cache is not None else salt.cache.factory(opts)
        try:
            g_keys = grains_cache.list("grains")
        except Exception:  # pylint: disable=broad-except
            g_keys = []
        for mid in g_keys:
            try:
                data = grains_cache.fetch("grains", mid) or {}
            except Exception:  # pylint: disable=broad-except
                continue
            if not isinstance(data, dict):
                continue
            ids = bare_resource_ids_from_decl(data.get("salt_resources"))
            if resource_id in ids:
                return True
    except Exception as exc:  # pylint: disable=broad-except
        log.debug(
            "bare_resource_id_in_minion_data_cache(%r) failed: %s",
            resource_id,
            exc,
            exc_info=True,
        )
    return False
