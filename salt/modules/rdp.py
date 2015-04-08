# -*- coding: utf-8 -*-
'''
Manage RDP Service on Windows servers
'''
from __future__ import absolute_import

# Import python libs
import re

# Import salt libs
import salt.utils


def __virtual__():
    '''
    Only works on Windows systems
    '''
    if salt.utils.is_windows():
        return 'rdp'
    return False


def _parse_return_code_powershell(string):
    '''
    return from the input string the return code of the powershell command
    '''

    regex = re.search(r'ReturnValue\s*: (\d*)', string)
    if not regex:
        return False
    else:
        return int(regex.group(1))


def _psrdp(cmd):
    '''
    Create a Win32_TerminalServiceSetting WMI Object as $RDP and execute the
    command cmd returns the STDOUT of the command
    '''
    rdp = ('$RDP = Get-WmiObject -Class Win32_TerminalServiceSetting '
           '-Namespace root\\CIMV2\\TerminalServices -Computer . '
           '-Authentication 6 -ErrorAction Stop')
    return __salt__['cmd.run']('{0} ; {1}'.format(rdp, cmd),
                               shell='powershell', python_shell=True)


def enable():
    '''
    Enable RDP the service on the server

    CLI Example:

    .. code-block:: bash

        salt '*' rdp.enable
    '''

    return _parse_return_code_powershell(
        _psrdp('$RDP.SetAllowTsConnections(1,1)')) == 0


def disable():
    '''
    Disable RDP the service on the server

    CLI Example:

    .. code-block:: bash

        salt '*' rdp.disable
    '''

    return _parse_return_code_powershell(
        _psrdp('$RDP.SetAllowTsConnections(0,1)')) == 0


def status():
    '''
    Show if rdp is enabled on the server

    CLI Example:

    .. code-block:: bash

        salt '*' rdp.status
    '''

    out = int(_psrdp('echo $RDP.AllowTSConnections').strip())
    return out != 0
