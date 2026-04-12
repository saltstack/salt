"""
Expose the resource IDs managed by this minion as a grain.

The grain ``salt_resources`` mirrors the ``resources:`` section of the minion
configuration so that the master's grains cache records which resources each
minion manages.  This enables grain-based targeting (``G@salt_resources``) and
gives operators a human-readable view of resource topology via ``grains.items``.

Example output::

    salt_resources:
      dummy:
        - dummy-01
        - dummy-02
        - dummy-03
"""

import logging

log = logging.getLogger(__name__)


def resources():
    """Return the resource IDs managed by this minion, keyed by resource type."""
    managed = __opts__.get("resources", {})
    if not managed:
        return {}
    return {"salt_resources": managed}
