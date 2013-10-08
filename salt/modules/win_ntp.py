# -*- coding: utf-8 -*-
'''
Management of NTP servers on Windows
'''

# Import python libs
import logging

# Import salt libs
import salt.utils

log = logging.getLogger(__name__)


def __virtual__():
    '''
    This only supports Windows
    '''
    if not salt.utils.is_windows():
        return False
    return 'ntp'


def set_servers(*servers):
    '''
    Set Windows to use a list of NTP servers

    CLI Example:

    .. code-block:: bash

        salt '*' ntp.set_servers 'pool.ntp.org' 'us.pool.ntp.org'
    '''
    cmd = ('W32tm /config /syncfromflags:manual /manualpeerlist:"{0}" &&'
          'W32tm /config /reliable:yes &&'
          'W32tm /config /update &&'
          'Net stop w32time && Net start w32time'
          ).format(' '.join(servers))
    ret = __salt__['cmd.run'](cmd)
    return 'command completed successfully' in ret


def get_servers():
    '''
    Get list of configured NTP servers

    CLI Example:

    .. code-block:: bash

        salt '*' ntp.get_servers
    '''
    cmd = 'w32tm /query /configuration'
    lines = __salt__['cmd.run'](cmd).splitlines()
    for line in lines:
        if 'NtpServer' in line:
            _, ntpsvrs = line.rstrip(' (Local)').split(':', 1)
            return sorted(ntpsvrs.split())
    return False
