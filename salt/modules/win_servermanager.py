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

__virtualname__ = 'win_servermanager'


def __virtual__():
    '''
    Load only on windows with servermanager module
    '''
    if not salt.utils.is_windows():
        return (False, 'Failed to load win_servermanager module:\n'
                       'Only available on Windows systems.')

    if not _check_server_manager():
        return (False, 'Failed to load win_servermanager module:\n'
                       'ServerManager module not available.\n'
                       'May need to install Remote Server Administration Tools.')

    return __virtualname__


def _check_server_manager():
    '''
    See if ServerManager module will import

    Returns: True if import is successful, otherwise returns False
    '''
    return not __salt__['cmd.retcode']('Import-Module ServerManager',
                                       shell='powershell',
                                       python_shell=True)


def _pshell(func):
    '''
    Execute a powershell command and return the STDOUT
    '''
    return __salt__['cmd.run']('{0}'.format(func),
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

    :return: A list of available features
    :rtype: list

    CLI Example:

    .. code-block:: bash

        salt '*' win_servermanager.list_available
    '''
    return _pshell('Get-WindowsFeature -erroraction silentlycontinue '
                   '-warningaction silentlycontinue')


def list_installed():
    '''
    List installed features. Supported on Windows Server 2008 and Windows 8 and
    newer.

    :return: A list of installed features
    :rtype: list

    CLI Example:

    .. code-block:: bash

        salt '*' win_servermanager.list_installed
    '''
    ret = {}
    names = _pshell('Get-WindowsFeature -erroraction silentlycontinue '
                    '-warningaction silentlycontinue | Select DisplayName,Name')
    for line in names.splitlines()[2:]:
        splt = line.split()
        name = splt.pop(-1)
        display_name = ' '.join(splt)
        ret[name] = display_name
    state = _pshell('Get-WindowsFeature -erroraction silentlycontinue '
                    '-warningaction silentlycontinue | Select Installed,Name')
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

    .. note::
        Some features require reboot after un/installation, if so until the
        server is restarted other features can not be installed!

    .. note::
        Some features take a long time to complete un/installation, set -t with
        a long timeout

    :param str feature: The name of the feature to install

    :param bool recurse: Install all sub-features

    :return: A dictionary containing the results of the install
    :rtype: dict

    CLI Example:

    .. code-block:: bash

        salt '*' win_servermanager.install Telnet-Client
        salt '*' win_servermanager.install SNMP-Service True
    '''
    sub = ''
    if recurse:
        sub = '-IncludeAllSubFeature'
    out = _pshell('Add-WindowsFeature -Name {0} {1} '
                  '-erroraction silentlycontinue '
                  '-warningaction silentlycontinue '
                  '| format-list'.format(_cmd_quote(feature), sub))
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

    :param str feature: The name of the feature to remove

    :return: A dictionary containing the results of the uninstall
    :rtype: dict

    CLI Example:

    .. code-block:: bash

        salt -t 600 '*' win_servermanager.remove Telnet-Client
    '''
    out = _pshell('Remove-WindowsFeature -Name {0} '
                  '-erroraction silentlycontinue '
                  '-warningaction silentlycontinue '
                  '| format-list'.format(_cmd_quote(feature)))
    return _parse_powershell_list(out)
