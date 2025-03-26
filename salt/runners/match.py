"""
Run matchers from the master context.

.. versionadded:: 3007.0
"""

import logging

import salt.utils.minions
import salt.utils.verify
from salt.defaults import DEFAULT_TARGET_DELIM

log = logging.getLogger(__name__)


def compound_matches(expr, minion_id):
    """
    Check whether a minion is matched by a given compound match expression.
    On success, this function will return the minion ID, otherwise False.

    .. note::

        Pillar values will be matched literally only since this function is intended
        for remote calling. This also applies to node groups defined on the master.
        Custom matchers are not respected.

    .. note::

        If a module calls this runner from a minion, you will need to explicitly
        allow the remote call. See :conf_master:`peer_run`.

    CLI Example:

    .. code-block:: bash

        salt-run match.compound_matches 'I@foo:bar and G@os:Deb* and not db*' myminion

    expr
        The :term:`Compound Matcher` expression to validate against.

    minion_id
        The minion ID of the minion to check the match for.

    """
    try:
        # Ensure that if the minion data cache is disabled, we always return
        # False. This is because the matcher will return a list of all minions
        # in that case (assumption is greedy).
        if not __opts__.get("minion_data_cache", True):
            log.warning(
                "Minion data cache is disabled. Cannot evaluate compound matcher expression."
            )
            return {"res": False}
        # Ensure the passed minion ID is valid.
        if not salt.utils.verify.valid_id(__opts__, minion_id):
            log.warning("Got invalid minion ID.")
            return {"res": False}
        log.debug("Evaluating if minion '%s' is matched by '%s'.", minion_id, expr)
        ckminions = salt.utils.minions.CkMinions(__opts__)
        # Compound expressions are usually evaluated in greedy mode since you
        # want to make sure the executing user has privileges to run a command on
        # any possibly matching minion, including those with uncached data.
        # This function has the opposite requirements, we want to make absolutely
        # sure the minion is matched by the expression.
        # Thus we do not include minions whose data has not been cached (greedy=False).
        # Also, allow exact pillar matches only to make enumeration attacks harder.
        minions = ckminions._check_compound_pillar_exact_minions(
            expr, DEFAULT_TARGET_DELIM, greedy=False
        )
        if minion_id in minions["minions"]:
            return {"res": minion_id}
    except Exception:  # pylint: disable=broad-except
        pass
    return {"res": False}
