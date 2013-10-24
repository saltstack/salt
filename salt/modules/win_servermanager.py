# -*- coding: utf-8 -*-
'''
Manage Windows features via the ServerManager powershell module
'''


# Import salt libs
import salt.utils


def __virtual__():
    '''
    Load only on windows
    '''
    if salt.utils.is_windows():
        return 'win_servermanager'
    return False


def _srvmgr(func):
    '''
    Execute a function from the ServerManager PS module and return the STDOUT
    '''
    return __salt__['cmd.run']('Import-Module ServerManager ; {0}'.format(func), shell='powershell')


def _parse_powershell_list(lst):
    '''
    Parse command output when piped to format-list
    '''
    ret = {}
    for line in lst.splitlines():
        if line:
            splt = line.split()
            ret[splt[0]] = splt[2]

    return ret


def list_available():
    '''
    List available features to install

    CLI Example:

    .. code-block:: bash

        salt '*' win_servermanager.list_available
    '''
    return _srvmgr('Get-WindowsFeature -erroraction silentlycontinue')


def list_installed():
    '''
    List installed features

    CLI Example:

    .. code-block:: bash

        salt '*' win_servermanager.list_installed
    '''
    ret = {}
    for line in list_available().splitlines()[2:]:
        splt = line.split()
        if splt[0] == '[X]':
            name = splt.pop(-1)
            splt.pop(0)
            display_name = ' '.join(splt)
            ret[name] = display_name

    return ret


def install(feature, recurse=False):
    '''
    Install a feature

    Note:
    Some features requires reboot after un/installation, if so until the server is restarted
    Other features can not be installed !

    Note:
    Some features takes a long time to complete un/installation, set -t with a long timeout

    CLI Example:

    .. code-block:: bash

        salt '*' win_servermanager.install Telnet-Client
        salt '*' win_servermanager.install SNMP-Services True
    '''
    sub = ''
    if recurse:
        sub = '-IncludeAllSubFeature'
    out = _srvmgr('"Add-WindowsFeature -Name {0} {1} -erroraction silentlycontinue | format-list"'.format(feature, sub))
    return _parse_powershell_list(out)


def remove(feature):
    '''
    Remove an installed feature

    .. note::
        Some features require a reboot after installation/uninstallation. If
        one of these features are modified, then other features cannot be
        installed until the server is restarted. Additionally, some features
        take a while to complete installation/uninstallation, so it is a good
        idea to use the ``-t`` option to set a longer timeout.

    CLI Example:

    .. code-block:: bash

        salt -t 600 '*' win_servermanager.remove Telnet-Client
    '''
    out = _srvmgr('"Remove-WindowsFeature -Name {0} -erroraction silentlycontinue | format-list"'.format(feature))
    return _parse_powershell_list(out)
