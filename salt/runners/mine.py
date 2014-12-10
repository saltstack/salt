# -*- coding: utf-8 -*-
'''
A runner to access data from the salt mine
'''
from __future__ import absolute_import

# Import Python Libs
import logging

# Import salt libs
import salt.utils
import salt.utils.minions

log = logging.getLevelName(__name__)


def get(tgt, fun, tgt_type='glob', output=None):
    '''
    Gathers the data from the specified minions' mine, pass in the target,
    function to look up and the target type

    CLI Example:

    .. code-block:: bash

        salt-run mine.get '*' network.interfaces
    '''
    if output is not None:
        # Remove this logging warning in Beryllium
        salt.utils.warn_until(
                'Beryllium',
                'Runners now supports --out. Please use --out instead.')
    ret = salt.utils.minions.mine_get(tgt, fun, tgt_type, __opts__)
    return ret
