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


def get(tgt, fun, tgt_type='glob'):
    '''
    Gathers the data from the specified minions' mine, pass in the target,
    function to look up and the target type

    CLI Example:

    .. code-block:: bash

        salt-run mine.get '*' network.interfaces
    '''
    ret = salt.utils.minions.mine_get(tgt, fun, tgt_type, __opts__)
    return ret
