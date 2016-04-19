# -*- coding: utf-8 -*-
'''
Manage Windows features via the ServerManager powershell module
'''
from __future__ import absolute_import
import logging
import json

# Import python libs
from distutils.version import LooseVersion
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
        return False, 'Failed to load win_servermanager module:\n' \
                      'Only available on Windows systems.'

    if not _check_server_manager():
        return False, 'Failed to load win_servermanager module:\n' \
                      'ServerManager module not available.\n' \
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
    if 'convertto-json' not in cmd.lower():
        cmd = ' '.join([cmd, '| ConvertTo-Json'])
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
    cmd = 'Get-WindowsFeature -erroraction silentlycontinue ' \
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


def install(feature, recurse=False, restart=False):
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

    :param bool restart: Restarts the computer when installation is complete, if required by the role feature installed.

    :return: A dictionary containing the results of the install
    :rtype: dict

    CLI Example:

    .. code-block:: bash

        salt '*' win_servermanager.install Telnet-Client
        salt '*' win_servermanager.install SNMP-Service True
    '''

    # Use Install-WindowsFeature on Windows 8 (osversion 6.2) and later minions. Includes Windows 2012+.
    # Default to Add-WindowsFeature for earlier releases of Windows.
    # The newer command makes management tools optional so add them for partity with old behavior.
    command = 'Add-WindowsFeature'
    management_tools = ''
    if LooseVersion(__grains__['osversion']) >= LooseVersion('6.2'):
        command = 'Install-WindowsFeature'
        management_tools = '-IncludeManagementTools'

    sub = ''
    if recurse:
        sub = '-IncludeAllSubFeature'

    rst = ''
    if restart:
        rst = '-Restart'

    cmd = '{0} -Name {1} {2} {3} {4} ' \
          '-ErrorAction SilentlyContinue ' \
          '-WarningAction SilentlyContinue'.format(command,
                                                   _cmd_quote(feature),
                                                   sub,
                                                   rst,
                                                   management_tools)
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
