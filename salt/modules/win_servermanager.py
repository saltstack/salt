# -*- coding: utf-8 -*-
'''
Manage Windows features via the ServerManager powershell module
'''
from __future__ import absolute_import
import ast
import json
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
    def _module_present():
        '''
        Check for the presence of the ServerManager module.
        '''
        cmd = r"[Bool] (Get-Module -ListAvailable | Where-Object { $_.Name -eq 'ServerManager' })"
        cmd_ret = __salt__['cmd.run_all'](cmd, shell='powershell', python_shell=True)

        if cmd_ret['retcode'] == 0:
            return ast.literal_eval(cmd_ret['stdout'])
        return False

    if not salt.utils.is_windows():
        return False, 'Failed to load win_servermanager module: ' \
                      'Only available on Windows systems.'

    if salt.utils.version_cmp(__grains__['osversion'], '6.1.7600') == -1:
        return False, 'Failed to load win_servermanager module: ' \
                      'Requires Remote Server Administration Tools which ' \
                      'is only available on Windows 2008 R2 and later.'

    if not _module_present():
        return False, 'Failed to load win_servermanager module: ' \
                      'ServerManager module not available. ' \
                      'May need to install Remote Server Administration Tools.'

    return __virtualname__


def _check_server_manager():
    '''
    See if ServerManager module will import

    Returns: True if import is successful, otherwise returns False
    '''
    if 'Server' not in __grains__['osrelease']:
        return False

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
          'Get-WindowsFeature ' \
          '-ErrorAction SilentlyContinue ' \
          '-WarningAction SilentlyContinue'
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
    cmd = 'Get-WindowsFeature ' \
          '-ErrorAction SilentlyContinue ' \
          '-WarningAction SilentlyContinue ' \
          '| Select DisplayName,Name,Installed'
    features = _pshell_json(cmd)

    ret = {}
    for entry in features:
        if entry['Installed']:
            ret[entry['Name']] = entry['DisplayName']

    return ret


def install(feature, recurse=False, source=None, restart=False, exclude=None):
    '''
    Install a feature

    .. note::
        Some features require reboot after un/installation, if so until the
        server is restarted other features can not be installed!

    .. note::
        Some features take a long time to complete un/installation, set -t with
        a long timeout

    :param str feature: The name of the feature to install

    :param bool recurse: Install all sub-features. Default is False

    :param str source: Path to the source files if missing from the target
        system. None means that the system will use windows update services to
        find the required files. Default is None

    :param bool restart: Restarts the computer when installation is complete, if
        required by the role/feature installed. Default is False

    :param str exclude: The name of the feature to exclude when installing the
        named feature.

        .. note::
            As there is no exclude option for the ``Add-WindowsFeature``
            command, the feature will be installed with other sub-features and
            will then be removed.

    :return: A dictionary containing the results of the install
    :rtype: dict

    CLI Example:

    .. code-block:: bash

        salt '*' win_servermanager.install Telnet-Client
        salt '*' win_servermanager.install SNMP-Service True
        salt '*' win_servermanager.install TFTP-Client source=d:\\side-by-side
    '''
    mgmt_tools = ''
    if salt.utils.version_cmp(__grains__['osversion'], '6.2') >= 0:
        mgmt_tools = '-IncludeManagementTools'

    sub = ''
    if recurse:
        sub = '-IncludeAllSubFeature'

    rst = ''
    if restart:
        rst = '-Restart'

    src = ''
    if source is not None:
        src = '-Source {0}'.format(source)

    cmd = 'Add-WindowsFeature -Name {0} {1} {2} {3} {4} ' \
          '-ErrorAction SilentlyContinue ' \
          '-WarningAction SilentlyContinue'\
          .format(_cmd_quote(feature), mgmt_tools, sub, src, rst)
    out = _pshell_json(cmd)

    if exclude is not None:
        remove(exclude, restart=restart)

    if out['FeatureResult']:
        return {'ExitCode': out['ExitCode'],
                'DisplayName': out['FeatureResult'][0]['DisplayName'],
                'RestartNeeded': out['FeatureResult'][0]['RestartNeeded'],
                'Success': out['Success']}
    else:
        return {'ExitCode': out['ExitCode'],
                'DisplayName': '{0} (already installed)'.format(feature),
                'RestartNeeded': False,
                'Success': out['Success']}


def remove(feature, remove_payload=False, restart=False):
    r'''
    Remove an installed feature

    .. note::
        Some features require a reboot after installation/uninstallation. If
        one of these features are modified, then other features cannot be
        installed until the server is restarted. Additionally, some features
        take a while to complete installation/uninstallation, so it is a good
        idea to use the ``-t`` option to set a longer timeout.

    :param str feature: The name of the feature to remove

    :param bool remove_payload: True will cause the feature to be removed from
        the side-by-side store (``%SystemDrive%:\Windows\WinSxS``). Default is
        False

    :param bool restart: Restarts the computer when uninstall is complete, if
        required by the role/feature removed. Default is False

    :return: A dictionary containing the results of the uninstall
    :rtype: dict

    CLI Example:

    .. code-block:: bash

        salt -t 600 '*' win_servermanager.remove Telnet-Client
    '''
    mgmt_tools = ''
    if salt.utils.version_cmp(__grains__['osversion'], '6.2') >= 0:
        mgmt_tools = '-IncludeManagementTools'

    rmv = ''
    if remove_payload:
        rmv = '-Remove'

    rst = ''
    if restart:
        rst = '-Restart'

    cmd = 'Remove-WindowsFeature -Name {0} {1} {2} {3} ' \
          '-ErrorAction SilentlyContinue ' \
          '-WarningAction SilentlyContinue'\
          .format(_cmd_quote(feature), mgmt_tools, rmv, rst)
    out = _pshell_json(cmd)

    if out['FeatureResult']:
        return {'ExitCode': out['ExitCode'],
                'DisplayName': out['FeatureResult'][0]['DisplayName'],
                'RestartNeeded': out['FeatureResult'][0]['RestartNeeded'],
                'Success': out['Success']}
    else:
        return {'ExitCode': out['ExitCode'],
                'DisplayName': '{0} (not installed)'.format(feature),
                'RestartNeeded': False,
                'Success': out['Success']}
