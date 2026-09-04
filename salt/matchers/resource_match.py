"""
Minion-side matcher for the ``T@`` resource targeting engine.

A ``T@`` expression targets Salt Resources managed by this minion.  The
pattern is either a bare resource type or a full Salt Resource Name (SRN):

.. code-block:: text

    T@vcf_host               # any resource of this type
    T@vcf_host:esxi-01       # one specific resource by SRN

This matcher is evaluated on the minion.  It reads from ``opts["resources"]``,
which is populated when the minion loads its resource modules — analogous to
how ``grain_match`` reads from ``opts["grains"]``.  No cache or registry
lookup is performed.
"""

import logging

log = logging.getLogger(__name__)


def match(tgt, opts=None, minion_id=None):
    """
    Return ``True`` if this minion manages at least one resource that matches
    the ``T@`` pattern ``tgt``.

    ``tgt`` is the portion of the ``T@`` expression after the ``@``.  It is
    either a bare resource type (``vcf_host``) or a full SRN
    (``vcf_host:esxi-01``).  When a bare type is given, every resource of that
    type in ``opts["resources"]`` satisfies the match.  When a full SRN is
    given, only an exact match against a resource ID in ``opts["resources"]``
    satisfies it.

    The structure of ``opts["resources"]`` is populated by the resource module
    loader at minion startup, analogous to ``opts["grains"]``.

    :param str tgt: The T@ pattern — a resource type or a full SRN.
    :param dict opts: Salt opts dict; defaults to ``__opts__``.
    :param str minion_id: The minion ID to evaluate; defaults to ``opts["id"]``.
    :rtype: bool
    """
    if opts is None:
        opts = __opts__  # pylint: disable=undefined-variable
    resources = opts.get("resources", {})
    if not resources:
        return False

    if ":" in tgt:
        resource_type, resource_id = tgt.split(":", 1)
        result = resource_id in resources.get(resource_type, [])
    else:
        result = bool(resources.get(tgt))

    log.debug("resource_match: T@%s => %s (resources=%s)", tgt, result, list(resources))
    return result
