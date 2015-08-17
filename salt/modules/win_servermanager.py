# -*- coding: utf-8 -*-
'''
Manage Windows features via the ServerManager powershell module
'''
from __future__ import absolute_import
import logging

# Import python libs
try:
    from shlex import quote as _cmd_quote  # pylint: disable=E0611
except ImportError:
    from pipes import quote as _cmd_quote

# Import salt libs
import salt.utils

log = logging.getLogger(__name__)


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
    return __salt__['cmd.run'](
            'Import-Module ServerManager ; {0}'.format(func),
            shell='powershell',
            python_shell=True)


def _parse_powershell_list(lst):
    '''
    Parse command output when piped to format-list
    Need to look at splitting with ':' so you can get the full value
    Need to check for error codes and return false if it's trying to parse
    '''
    ret = {}
    for line in lst.splitlines():
        if line:
            splt = line.split()
            # Ensure it's not a malformed line, e.g.:
            #   FeatureResult : {foo, bar,
            #                    baz}
            if len(splt) > 2:
                ret[splt[0]] = splt[2]
    ret['message'] = lst
    return ret


def list_available():
    '''
    List available features to install

    CLI Example:

    .. code-block:: bash

        salt '*' win_servermanager.list_available
    '''
    return _srvmgr('Get-WindowsFeature -erroraction silentlycontinue -warningaction silentlycontinue')


def list_installed():
    '''
    List installed features. Supported on Windows Server 2008 and Windows 8 and
    newer.

    CLI Example:

    .. code-block:: bash

        salt '*' win_servermanager.list_installed
    '''
    ret = {}
    names = _srvmgr('Get-WindowsFeature -erroraction silentlycontinue -warningaction silentlycontinue | Select DisplayName,Name')
    for line in names.splitlines()[2:]:
        splt = line.split()
        name = splt.pop(-1)
        display_name = ' '.join(splt)
        ret[name] = display_name
    state = _srvmgr('Get-WindowsFeature -erroraction silentlycontinue -warningaction silentlycontinue | Select Installed,Name')
    for line in state.splitlines()[2:]:
        splt = line.split()
        if splt[0] == 'False' and splt[1] in ret:
            del ret[splt[1]]
        if '----' in splt[0]:
            del ret[splt[1]]
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
        salt '*' win_servermanager.install SNMP-Service True
    '''
    sub = ''
    if recurse:
        sub = '-IncludeAllSubFeature'
    out = _srvmgr('Add-WindowsFeature -Name {0} {1} -erroraction silentlycontinue -warningaction silentlycontinue | format-list'.format(
                  _cmd_quote(feature), sub))
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
    out = _srvmgr('Remove-WindowsFeature -Name {0} -erroraction silentlycontinue -warningaction silentlycontinue | format-list'.format(
                  _cmd_quote(feature)))
    return _parse_powershell_list(out)
