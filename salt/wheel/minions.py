# -*- coding: utf-8 -*-
'''
Wheel system wrapper for connected minions
'''

# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals

# Import Salt libs
from salt.utils.cache import CacheCli
import salt.tgt
import salt.config


def connected():
    '''
    List all connected minions on a salt-master
    '''
    opts = salt.config.master_config(__opts__['conf_file'])

    if opts.get('con_cache'):
        cache_cli = CacheCli(opts)
        minions = cache_cli.get_cached()
    else:
        minions = list(salt.tgt.connected_ids(opts))
    return minions
