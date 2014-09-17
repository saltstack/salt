# -*- coding: utf-8 -*-
"""
Device-Mapper module
"""
import logging
log = logging.getLogger(__name__)


def multipath_list():
    '''
    Device-Mapper Multipath list
    CLI Example:
    .. code-block:: bash
    salt '*' devmap.multipath_list
    '''
    cmd = 'multipath -l'
    return __salt__['cmd.run'](cmd).splitlines()


def multipath_flush(args=None):
    '''
    Device-Mapper Multipath flush
    CLI Example:
    .. code-block:: bash
    salt '*' devmap.multipath_flush mpath1
    '''
    ret = {}
    try:
        cmd = 'multipath -f {0}'.format(ret[0])
    except ValueError:
        return 'Error: No device to flush has been provided!'
    return __salt__['cmd.run'](cmd).splitlines()
    