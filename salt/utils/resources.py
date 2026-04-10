"""
Helpers for Salt resource minions: configurable pillar key and lookups.
"""


def resource_pillar_key(opts):
    """
    Return the top-level pillar key used for per-type resource configuration.

    Configured by minion option ``resource_pillar_key`` (default ``resources``).
    """
    return opts.get("resource_pillar_key", "resources")


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
