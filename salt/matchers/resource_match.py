"""
Minion-side matcher for the ``T@`` resource targeting engine.

A ``T@`` expression targets Salt Resources managed by this minion.  The
pattern is either a bare resource type or a full Salt Resource Name (SRN):

.. code-block:: text

    T@vcf_host               # any resource of this type
    T@vcf_host:esxi-01       # one specific resource by SRN

This matcher is evaluated on the minion.  It consults the configured
``resource_types`` opt (via :func:`salt.utils.resources.enabled_resource_types`)
and, when a specific SRN is being matched, iterates that type's
``discover(opts)`` generator to check membership.  No inventory dict is
materialized on the minion -- the memory-ceiling invariant from
``feedback_minion_never_holds_full_resource_set.md`` is preserved.

The pre-refactor shape read from ``opts["resources"]``, which was
populated at minion startup by the module loader.  That accumulator
was removed when pillar/grain-driven resource inventory was dropped
(a 200K-resource dict on the minion blew the memory ceiling); the
matcher was never ported to the new generator-based API.  This module
is that port.
"""

import logging

log = logging.getLogger(__name__)


def _iter_resource_ids(opts, resource_type):
    """
    Yield bare resource IDs for ``resource_type`` by calling the
    module's ``discover(opts)`` generator.

    Returns an empty iterator when the loader is unavailable or the
    type has no ``discover`` entry -- matcher callers treat that as
    "no managed resources of this type", which is the correct
    answer for an un-configured type.
    """
    try:
        import salt.loader  # noqa: PLC0415
    except Exception as exc:  # pylint: disable=broad-except
        log.debug("resource_match: salt.loader unavailable (%s)", exc)
        return
    try:
        funcs = salt.loader.resource(opts)
    except Exception as exc:  # pylint: disable=broad-except
        log.debug(
            "resource_match: resource loader failed for '%s' (%s)",
            resource_type,
            exc,
        )
        return
    discover_fn = f"{resource_type}.discover"
    if discover_fn not in funcs:
        log.debug(
            "resource_match: no discover function for type '%s'",
            resource_type,
        )
        return
    try:
        ids = funcs[discover_fn](opts)
    except Exception as exc:  # pylint: disable=broad-except
        log.debug("resource_match: discover(%s) failed: %s", resource_type, exc)
        return
    if ids is None:
        return
    yield from ids


def match(tgt, opts=None, minion_id=None):
    """
    Return ``True`` if this minion manages at least one resource that matches
    the ``T@`` pattern ``tgt``.

    ``tgt`` is the portion of the ``T@`` expression after the ``@``.  It is
    either a bare resource type (``vcf_host``) or a full SRN
    (``vcf_host:esxi-01``).  When a bare type is given, the match succeeds iff
    the type is in ``resource_types`` and its ``discover`` generator yields at
    least one ID.  When a full SRN is given, the match iterates the type's
    ``discover`` generator and short-circuits on the first match (so
    matching does not materialize the full inventory).

    :param str tgt: The T@ pattern -- a resource type or a full SRN.
    :param dict opts: Salt opts dict; defaults to ``__opts__``.
    :param str minion_id: The minion ID to evaluate; defaults to ``opts["id"]``.
    :rtype: bool
    """
    if opts is None:
        opts = __opts__  # pylint: disable=undefined-variable

    import salt.utils.resources  # noqa: PLC0415

    enabled = set(salt.utils.resources.enabled_resource_types(opts))

    if ":" in tgt:
        resource_type, resource_id = tgt.split(":", 1)
        if resource_type not in enabled:
            result = False
        else:
            result = False
            for rid in _iter_resource_ids(opts, resource_type):
                if rid == resource_id:
                    result = True
                    break
    else:
        if tgt not in enabled:
            result = False
        else:
            # Bare-type match: True iff the generator yields at least one ID.
            result = False
            for _rid in _iter_resource_ids(opts, tgt):
                result = True
                break

    log.debug("resource_match: T@%s => %s (enabled=%s)", tgt, result, sorted(enabled))
    return result
