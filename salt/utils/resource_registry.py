"""
Resource Registry — the system of record for Salt Resources.

The registry tracks which minions manage each resource and is the backing
store that the targeting layer queries when resolving ``T@`` and ``M@``
expressions.

**Minions are resources.**  A traditional Salt minion is a resource of type
``minion`` with SRN ``minion:<minion_id>``.  All resources are stored and
queried uniformly through this registry.

Cache layout
------------
Resources are stored across three banks in Salt's pluggable cache
(``salt.cache.factory(opts)``).  All banks use the **bare resource ID** as the
key.  IDs are globally unique across all types and all minions, so the type is
never part of the cache key::

    bank: "grains",    key: "<id>"  →  {grain_dict}
    bank: "pillar",    key: "<id>"  →  {pillar_dict}
    bank: "resources", key: "<id>"  →  {"type": "...", "managing_minions": [...]}

The ``grains`` and ``pillar`` banks are unchanged from today — existing minion
entries require no migration.

The ``resources`` bank is new.  It is the topology store: it records the
resource type and which minions manage each resource.  This data is externally
defined (by RAAS or the operator) and is never self-reported by the resource.

A resource may be managed by more than one minion.  ``managing_minions`` is
always a list.  For a minion-type resource it contains the minion's own ID.

Resources enter the registry in two ways:

* **Defined in RAAS** — created directly in the enterprise control plane.
* **Reported by minions** — minions discover resources and push them to the
  Master via ``saltutil.refresh_resources``, analogous to grain reporting.

This module provides the interface consumed by the targeting layer.
Registry population (registration and discovery) is handled elsewhere.
"""

import logging

# import salt.cache  # TODO(resources): uncomment when ResourceRegistry is implemented

log = logging.getLogger(__name__)

RESOURCE_BANK = "resources"


def parse_srn(expression):
    """
    Parse a ``T@`` pattern into its ``type`` and ``id`` components.

    A full Salt Resource Name (SRN) has the form ``<type>:<id>``.  A bare
    expression contains only a type with no colon.  The cache never sees the
    full SRN — this function is used only by the targeting layer when parsing
    user-supplied expressions.

    Returns a dict with keys:

    * ``type`` — the resource type string (e.g. ``"vcf_host"``).
    * ``id``   — the bare resource ID string, or ``None`` for a bare type.

    Examples::

        parse_srn("vcf_host")           # {"type": "vcf_host", "id": None}
        parse_srn("vcf_host:esxi-01")   # {"type": "vcf_host", "id": "esxi-01"}

    :param str expression: A bare resource type or a full SRN.
    :rtype: dict
    """


class ResourceRegistry:
    """
    Master-side interface to the Salt Resource Registry backed by ``salt.cache``.

    Instantiate with the Salt opts dict; the class opens its own cache handle
    via ``salt.cache.factory(opts)`` so callers do not manage the cache
    directly.  The cache backend (localfs, redis, etc.) is determined by
    ``opts["cache"]``, exactly as it is for grains and pillar caching in
    ``CkMinions``::

        registry = ResourceRegistry(opts)
        registry.get_managing_minions_by_type("vcf_host")

    This class is a master-side construct.  Minions do not query the registry
    cache — they read resource information from ``opts["resources"]``, which is
    populated by the resource module loader at startup, analogous to how
    ``opts["grains"]`` is populated by the grain loader.
    """

    def __init__(self, opts):
        """
        Initialise the registry and open a handle to the Salt cache.

        :param dict opts: The Salt opts dict.
        """

    # ------------------------------------------------------------------
    # Read interface — used by the targeting layer
    # ------------------------------------------------------------------

    def get_resource(self, resource_id):
        """
        Return the topology blob for a single resource from the ``resources``
        bank, or ``None`` if the resource is not registered::

            cache.fetch("resources", resource_id)

        The blob contains at minimum ``type`` and ``managing_minions`` keys.

        :param str resource_id: The bare resource ID (e.g. ``"esxi-01"``).
        :rtype: dict or None
        """

    def get_managing_minions_by_type(self, resource_type):
        """
        Return the set of minion IDs that manage at least one resource of
        ``resource_type``.

        Used by ``CkMinions._check_resource_minions`` to resolve ``T@<type>``
        expressions.  Iterates all entries in the ``resources`` bank, filters
        by type, and returns the union of all ``managing_minions`` lists.

        The return value mirrors the ``{"minions": [...], "missing": []}``
        shape used throughout ``CkMinions``.

        :param str resource_type: The resource type to query (e.g.
            ``"vcf_host"``).
        :rtype: dict
        """

    def get_managing_minions_for_id(self, resource_id):
        """
        Return the list of minion IDs that manage the resource identified by
        ``resource_id``, or an empty list if the resource is not registered.

        Used by ``CkMinions._check_resource_minions`` to resolve
        ``T@<type>:<id>`` expressions.

        :param str resource_id: The bare resource ID (e.g. ``"esxi-01"``).
        :rtype: list[str]
        """

    def get_resources_for_minion(self, minion_id):
        """
        Return the list of resource IDs managed by ``minion_id``.

        Used by ``CkMinions._check_resource_minions`` and
        ``CkMinions._check_managing_minion_minions`` to enumerate the resources
        a given minion owns when resolving compound expressions on the master.

        :param str minion_id: The minion whose resources are requested.
        :rtype: list[str]
        """

    def has_resource_type(self, minion_id, resource_type):
        """
        Return ``True`` if ``minion_id`` manages at least one resource of
        ``resource_type``.

        Used by master-side compound expression evaluation to verify ownership
        when intersecting ``M@`` and ``T@`` expressions.

        :param str minion_id: The minion to check.
        :param str resource_type: The resource type to test for.
        :rtype: bool
        """

    def has_resource(self, minion_id, resource_id):
        """
        Return ``True`` if ``minion_id`` manages the resource identified by
        ``resource_id``.

        Used by master-side compound expression evaluation to verify ownership
        when intersecting ``M@`` and ``T@`` expressions.

        :param str minion_id: The minion to check.
        :param str resource_id: The bare resource ID (e.g. ``"esxi-01"``).
        :rtype: bool
        """
