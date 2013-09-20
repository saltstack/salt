# -*- coding: utf-8 -*-
'''
Manage RDP Service on Windows servers
'''

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


def enable():
    '''
    Enable RDP the service on the server

    CLI Example:

    .. code-block:: bash

        salt '*' rdp.enable
    '''
    cmd = 'powershell -InputFormat None -Command "& { $RDP = Get-WmiObject -Class Win32_TerminalServiceSetting -Namespace root\\CIMV2\\TerminalServices -Computer . -Authentication 6 -ErrorAction Stop ; $RDP.SetAllowTsConnections(1,1) }"'
    return _parse_return_code_powershell(__salt__['cmd.run'](cmd)) == 0


def disable():
    '''
    Disable RDP the service on the server

    CLI Example:

    .. code-block:: bash

        salt '*' rdp.disable
    '''
    cmd = 'powershell -InputFormat None -Command "& { $RDP = Get-WmiObject -Class Win32_TerminalServiceSetting -Namespace root\\CIMV2\\TerminalServices -Computer . -Authentication 6 -ErrorAction Stop ; $RDP.SetAllowTsConnections(0,1) }"'
    return _parse_return_code_powershell(__salt__['cmd.run'](cmd)) == 0


def status():
    '''
    Show if rdp is enabled on the server

    CLI Example:

    .. code-block:: bash

        salt '*' rdp.status
    '''
    cmd = 'powershell -InputFormat None -Command "& { $RDP = Get-WmiObject -Class Win32_TerminalServiceSetting -Namespace root\\CIMV2\\TerminalServices -Computer . -Authentication 6 -ErrorAction Stop ; echo $RDP.AllowTSConnections }"'
    out = int(__salt__['cmd.run'](cmd).strip())
    return out != 0
