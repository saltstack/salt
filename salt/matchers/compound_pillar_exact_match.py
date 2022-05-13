"""
This is the default pillar exact matcher for compound matches.

There is no minion-side equivalent for this, so consequently there is no ``match()``
function below, only an ``mmatch()``
"""

import logging

import salt.utils.minions

log = logging.getLogger(__name__)


def mmatch(expr, delimiter, greedy, opts=None):
    """
    Return the minions found by looking via pillar
    """
    if not opts:
        opts = __opts__

    ckminions = salt.utils.minions.CkMinions(opts)
    return ckminions._check_compound_minions(expr, delimiter, greedy, pillar_exact=True)
