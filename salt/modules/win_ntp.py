# -*- coding: utf-8 -*-
'''
Management of Windows Time Service's upstream time servers

.. versionadded:: 2014.1.0 (Hydrogen)
'''

# Import python libs
import logging

# Import salt libs
import salt.utils

log = logging.getLogger(__name__)

# Define the module's virtual name
__virtualname__ = 'win_ntp'


def __virtual__():
    '''
    This only supports Windows
    '''
    if not salt.utils.is_windows():
        return False
    return __virtualname__


def set_servers(*servers):
    '''
    Set Windows Time Service to use a list of NTP servers

    CLI Example:

    .. code-block:: bash

        salt '*' win_ntp.set_servers 'pool.ntp.org' 'us.pool.ntp.org'
    '''
    service_name = 'w32time'
    if not __salt__['service.status'](service_name):
        if not __salt__['service.start'](service_name):
            return False
    ret = __salt__['cmd.run'](
        'W32tm /config /syncfromflags:manual /manualpeerlist:"{0}" &&'
        'W32tm /config /reliable:yes && W32tm /config /update'
        .format(' '.join(servers))
    )
    __salt__['service.restart'](service_name)
    return 'command completed successfully' in ret


def get_servers():
    '''
    Get list of NTP servers configured in Windows Time Service

    CLI Example:

    .. code-block:: bash

        salt '*' win_ntp.get_servers
    '''
    cmd = 'w32tm /query /configuration'
    lines = __salt__['cmd.run'](cmd).splitlines()
    for line in lines:
        if 'NtpServer' in line:
            _, ntpsvrs = line.rstrip(' (Local)').split(':', 1)
            return sorted(ntpsvrs.split())
    return False
