"""
Helpers for Salt resource minions: configurable pillar key and lookups.
"""

import logging

log = logging.getLogger(__name__)


def resource_pillar_key(opts):
    """
    Return the top-level pillar key used for per-type resource configuration.

    Configured by minion option ``resource_pillar_key`` (default ``resources``).
    Empty values are rejected with a warning and treated as ``"resources"``.
    """
    key = opts.get("resource_pillar_key", "resources")
    if not key:
        log.warning(
            "resource_pillar_key is empty; using default 'resources'. "
            "Set resource_pillar_key to a non-empty string in the minion config."
        )
        key = "resources"
    return key


def pillar_resources_tree(opts):
    """
    Return the merged pillar mapping under the configured resource pillar key.

    If the key is absent, returns ``{}`` (same as an empty declaration).
    Non-dict values are treated as empty.
    """
    key = resource_pillar_key(opts)
    pillar = opts.get("pillar", {})
    if key not in pillar:
        return {}
    pr = pillar.get(key)
    return pr if isinstance(pr, dict) else {}


def bare_resource_ids_from_decl(decl):
    """
    Flatten ``salt_resources`` / pillar ``resources`` subtree mappings to bare IDs.

    Supports ``{rtype: [id, ...]}`` (post-discovery) and
    ``{rtype: {"resource_ids": [...]}}`` (pillar-shaped) layouts.
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
    Return ``True`` if ``resource_id`` appears in any cached minion pillar /
    grains snapshot on the master.

    Used when the mmap resource registry has not yet recorded the ID (or was
    cleared) but :conf_master:`minion_data_cache` still holds pillar/grains
    from the last sync — so ``salt m2-dummy2 state.apply`` / ``test.ping``
    style targeting can still resolve.

    :param cache:
        Optional :class:`salt.cache.Cache` from the caller (e.g. ``CkMinions``
        already constructs one). Pillar entries may live under a separate
        backend when :conf_master:`pillar.cache_driver` is set; that driver is
        always used for ``bank="pillar"`` reads. Grains use ``cache`` (or a
        newly created default cache handle when ``cache`` is omitted).
    """
    if not opts.get("minion_data_cache") or not resource_id:
        return False
    try:
        import salt.cache

        grains_cache = cache if cache is not None else salt.cache.factory(opts)
        pillar_driver = opts.get("pillar.cache_driver")
        pillar_cache = (
            salt.cache.factory(opts, driver=pillar_driver)
            if pillar_driver
            else grains_cache
        )
        rk = resource_pillar_key(opts)
        try:
            p_keys = pillar_cache.list("pillar")
        except Exception:  # pylint: disable=broad-except
            p_keys = []
        for mid in p_keys:
            try:
                data = pillar_cache.fetch("pillar", mid) or {}
            except Exception:  # pylint: disable=broad-except
                continue
            if not isinstance(data, dict):
                continue
            subtree = data.get(rk)
            ids = bare_resource_ids_from_decl(subtree)
            if resource_id in ids:
                return True

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
