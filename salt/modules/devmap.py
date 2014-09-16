# -*- coding: utf-8 -*-
import logging
log = logging.getLogger(__name__)


def multipath_list():
    '''
    Device-Mapper Multipath module
    CLI Example:
    .. code-block:: bash
    salt '*' devmap.multipath_list
    salt '*' devmap.multipath flush mpath1
    '''
    cmd = 'multipath -l'
    return __salt__['cmd.run'](cmd).splitlines()


def multipath_flush(args=None):
    '''
    Device-Mapper Multipath module
    CLI Example:
    .. code-block:: bash
    salt '*' devmap.multipath_flush mpath1
    '''
    ret={}
    try:
        cmd = 'multipath -f {0}'.format(ret[0])
    except ValueError:
        return 'Error: No device to flush has been provided!'