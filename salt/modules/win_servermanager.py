# -*- coding: utf-8 -*-
'''
Manage Windows features via the ServerManager powershell module
'''
from __future__ import absolute_import
import logging
import json

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
        return False, 'Failed to load win_servermanager module: ' \
                      'Only available on Windows systems.'

    if salt.utils.version_cmp(__grains__['osversion'], '6.1.7600') == -1:
        return False, 'Failed to load win_servermanager module: ' \
                      'Requires Remote Server Administration Tools which ' \
                      'is only available on Windows 2008 R2 and later.'

    if not _check_server_manager():
        return False, 'Failed to load win_servermanager module: ' \
                      'ServerManager module not available. ' \
                      'May need to install Remote Server Administration Tools.'

    return __virtualname__


def _check_server_manager():
    '''
    See if ServerManager module will import

    Returns: True if import is successful, otherwise returns False
    '''
    return not __salt__['cmd.retcode']('Import-Module ServerManager',
                                       shell='powershell',
                                       python_shell=True)


def _pshell_json(cmd, cwd=None):
    '''
    Execute the desired powershell command and ensure that it returns data
    in json format and load that into python
    '''
    cmd = 'Import-Module ServerManager; {0}'.format(cmd)
    if 'convertto-json' not in cmd.lower():
        cmd = '{0} | ConvertTo-Json'.format(cmd)
    log.debug('PowerShell: {0}'.format(cmd))
    ret = __salt__['cmd.shell'](cmd, shell='powershell', cwd=cwd)
    try:
        ret = json.loads(ret, strict=False)
    except ValueError:
        log.debug('Json not returned')
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
    cmd = 'Import-Module ServerManager; ' \
          'Get-WindowsFeature -erroraction silentlycontinue ' \
          '-warningaction silentlycontinue'
    return __salt__['cmd.shell'](cmd, shell='powershell')


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
    cmd = 'Get-WindowsFeature -erroraction silentlycontinue ' \
          '-warningaction silentlycontinue | ' \
          'Select DisplayName,Name,Installed'
    features = _pshell_json(cmd)

    ret = {}
    for entry in features:
        if entry['Installed']:
            ret[entry['Name']] = entry['DisplayName']

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

    cmd = 'Add-WindowsFeature -Name {0} {1} ' \
          '-ErrorAction SilentlyContinue ' \
          '-WarningAction SilentlyContinue'.format(_cmd_quote(feature), sub)
    out = _pshell_json(cmd)

    ret = {'ExitCode': out['ExitCode'],
           'DisplayName': out['FeatureResult'][0]['DisplayName'],
           'RestartNeeded': out['FeatureResult'][0]['RestartNeeded'],
           'Success': out['Success']}

    return ret


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
    cmd = 'Remove-WindowsFeature -Name {0} ' \
          '-ErrorAction SilentlyContinue ' \
          '-WarningAction SilentlyContinue'.format(_cmd_quote(feature))
    out = _pshell_json(cmd)

    ret = {'ExitCode': out['ExitCode'],
           'DisplayName': out['FeatureResult'][0]['DisplayName'],
           'RestartNeeded': out['FeatureResult'][0]['RestartNeeded'],
           'Success': out['Success']}

    return ret
