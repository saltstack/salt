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
