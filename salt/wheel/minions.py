# -*- coding: utf-8 -*-
'''
Wheel system wrapper for connected minions
'''

# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals

# Import Salt libs
from salt.utils.cache import CacheCli
import salt.config
import salt.utils.minions


def connected():
    '''
    List all connected minions on a salt-master
    '''
    opts = salt.config.master_config(__opts__['conf_file'])

    if opts.get('con_cache'):
        cache_cli = CacheCli(opts)
        minions = cache_cli.get_cached()
    else:
        minions = list(salt.utils.minions.CkMinions(opts).connected_ids())
    return minions
