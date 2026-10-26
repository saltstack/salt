"""
Match a minion based on which master cluster it belongs to.

Compound target syntax: ``C@cluster_id`` or ``C@a,b,c`` (union).

Routing-time behavior: the
:class:`salt.topology.router.TopologyRouter` extracts ``C@`` clauses
*before* a publish reaches the compound matcher, uses them to
decide which peer links to dispatch down, and strips the clauses
before publishing to local minions. By the time this matcher runs
on local minions, the ``C@`` clause is only relevant for correctness
when the compound expression contains a mix of ``C@`` and other
matchers that the router preserved intact across the wire --- the
full compound reaches the receiving cluster and is re-evaluated
per-minion there.

Match semantics: ``True`` when this master's ``opts["cluster_id"]``
is one of the names in the comma-separated target. On a minion
process (unlikely path, as the router strips ``C@`` before publish-
to-minions), ``opts["master_cluster_id"]`` is consulted instead.
"""

import logging

log = logging.getLogger(__name__)


def match(tgt, opts=None, minion_id=None):
    """
    Standard compound-matcher plugin signature.

    :param tgt: Comma-separated list of ``cluster_id`` values, e.g.
        ``"east"`` or ``"east,west"``.
    :param opts: Master or minion opts. On a master, expected to
        contain ``cluster_id``. On a minion, expected to contain
        ``master_cluster_id`` (populated from the auth response
        when :data:`topology_push_cluster_grain` is True on the
        master).
    :param minion_id: Unused by this matcher; present for signature
        conformance with other matcher plugins.
    :returns: ``True`` iff this cluster is named in the target set.
        ``False`` otherwise, including when ``opts`` has no cluster
        identifier (non-topology deployment, pre-handshake minion,
        etc.) --- a non-matching failure is always safer than a
        false positive.
    """
    if opts is None:
        try:
            opts = __opts__  # noqa: F821 (loader-injected dunder)
        except NameError:
            opts = {}
    if not isinstance(tgt, str):
        log.error("cluster_match target must be a string, got %r", type(tgt))
        return False
    local = opts.get("cluster_id") or opts.get("master_cluster_id")
    if not local:
        return False
    wanted = {token.strip() for token in tgt.split(",") if token.strip()}
    if not wanted:
        return False
    return local in wanted
