"""
Minion-side matcher for the ``M@`` managing-minion targeting engine.

A ``M@`` expression targets a minion directly by its ID, as the entity
*responsible for* a set of resources — rather than targeting the resources
themselves.  It is most useful in compound expressions where you want to
constrain a resource target to those owned by a specific minion:

.. code-block:: text

    salt -C 'M@vcenter-1 and T@vcf_host'

That expression matches all ``vcf_host`` resources managed by the minion
whose ID is ``vcenter-1``.  On its own ``M@vcenter-1`` is equivalent to
``L@vcenter-1``, but pairing it with ``T@`` is its primary use-case.
"""

import logging

log = logging.getLogger(__name__)


def match(tgt, opts=None, minion_id=None):
    """
    Return ``True`` if this minion's ID equals ``tgt``.

    ``tgt`` is the minion ID given after the ``M@`` prefix.  The match is
    always an exact equality check — no globbing or regex.

    :param str tgt: The minion ID to match against.
    :param dict opts: Salt opts dict; defaults to ``__opts__``.
    :param str minion_id: The minion ID to evaluate; defaults to ``opts["id"]``.
    :rtype: bool
    """
    if opts is None:
        opts = __opts__  # pylint: disable=undefined-variable
    if minion_id is None:
        minion_id = opts.get("id", "")
    result = minion_id == tgt
    log.debug("managing_minion_match: M@%s => %s (id=%s)", tgt, result, minion_id)
    return result
