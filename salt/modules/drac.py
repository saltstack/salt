# -*- coding: utf-8 -*-
'''
Manage Dell DRAC
'''

import salt.utils

import logging

log = logging.getLogger(__name__)


def __virtual__():
    '''

    '''
    if salt.utils.which('racadm'):
        return True

    return False


def __parse_drac(output):
    '''
    Parse Dell DRAC output
    '''
    drac = {}
    section = ''

    for i in output.splitlines():
        if len(i.rstrip()) > 0 and '=' in i:
            if section in drac:
                drac[section].update(dict(
                    [[prop.strip() for prop in i.split('=')]]
                ))
        else:
            section = i.strip()[:-1]
            if section not in drac and section:
                drac[section] = {}

    return drac


def getsysinfo():
    '''
    Return System information

    CLI Example:

    .. code-block:: bash

        salt dell drac.getsysinfo
    '''
    drac = {}
    section = ''

    cmd = __salt__['cmd.run_all']('racadm getsysinfo')

    if cmd['retcode'] != 0:
        log.warn('racadm return an exit code \'{0}\'.'.format(cmd['retcode']))

    return __parse_drac(cmd['stdout'])


def getniccfg():
    '''
    Return Network Configuration

    CLI Example:

    .. code-block:: bash

        salt salt drac.getniccfg
    '''

    cmd = __salt__['cmd.run_all']('racadm getniccfg')

    if cmd['retcode'] != 0:
        log.warn('racadm return an exit code \'{0}\'.'.format(cmd['retcode']))

    return __parse_drac(cmd['stdout'])
