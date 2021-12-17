"""
Wheel system wrapper for connected minions
"""


import salt.config
import salt.utils.minions
from salt.utils.cache import CacheCli


def connected():
    """
    List all connected minions on a salt-master
    """
    opts = salt.config.master_config(__opts__["conf_file"])

    if opts.get("con_cache"):
        cache_cli = CacheCli(opts)
        minions = cache_cli.get_cached()
    else:
        minions = list(salt.utils.minions.CkMinions(opts).connected_ids())
    return minions
