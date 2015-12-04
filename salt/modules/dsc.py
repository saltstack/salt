# -*- coding: utf-8 -*-
'''
Module for managing PowerShell modules

:depends:
    - PowerShell 5.0

Support for PowerShell
'''
from __future__ import absolute_import

# Import python libs
import copy
import logging
import json
import os

# Import salt libs
import salt.utils
from salt.exceptions import CommandExecutionError, SaltInvocationError

# Set up logging
log = logging.getLogger(__name__)

# Define the module's virtual name
__virtualname__ = 'dsc'


def __virtual__():
    '''
    Set the system module of the kernel is Windows
    '''
    if salt.utils.is_windows() and psversion() >= 5:
        return __virtualname__
    return False


def _pshell(cmd):
    '''
    Execute the desired powershell command and ensure that it returns data
    in json format and load that into python
    '''
    if 'convertto-json' not in cmd.lower():
        cmd = ' '.join([cmd, '| ConvertTo-Json -Depth 10'])
    log.debug('DSC: {0}'.format(cmd))
    ret = __salt__['cmd.shell'](cmd, shell='powershell')
    try:
        ret = json.loads(ret, strict=False)
    except ValueError:
        log.debug('Json not returned')
    return ret


def bootstrap():
    '''
    Make sure that nuget-anycpu.exe is installed.
    This will download the official nuget-anycpu.exe from the internet.

    CLI Example:

    .. code-block:: bash

        salt 'win01' dsc.bootstrap
    '''
    cmd = 'Get-PackageProvider -Name NuGet -ForceBootstrap'
    ret = _pshell(cmd)
    return ret


def enable_scripts():
    '''
    Enable Powershell Scripts

    Allows all Powershell scripts to be run.
    Executes "Set-ExecutionPolicy Unrestricted" on the system.

    CLI Example:

    .. code-block:: bash

        salt 'win01' dsc.enable_scripts
    '''
    cmd = 'Set-ExecutionPolicy Unrestricted'
    return _pshell(cmd)


def psversion():
    '''
    Returns the Powershell version

    CLI Example:

    .. code-block:: bash

        salt 'win01' dsc.psversion
    '''
    cmd = '$PSVersionTable.PSVersion.Major'
    ret = _pshell(cmd)
    return ret


def avail_modules(desc=False):
    '''
    List available modules in registered Powershell module repositories.

    desc : False
         If ``True``, the verbose description will be returned.

    CLI Example:

    .. code-block:: bash

        salt 'win01' dsc.avail_modules
        salt 'win01' dsc.avail_modules desc=True
    '''
    cmd = 'Find-Module'
    modules = _pshell(cmd)
    names = []
    if desc:
        names = {}
    for module in modules:
        if desc:
            names[module['Name']] = module['Description']
            continue
        names.append(module['Name'])
    return names


def list_modules(desc=False):
    '''
    List currently installed DSC Modules on the system.

    desc : False
         If ``True``, the verbose description will be returned.

    CLI Example:

    .. code-block:: bash

        salt 'win01' dsc.list_modules
        salt 'win01' dsc.list_modules desc=True
    '''
    cmd = 'Get-InstalledModule'
    modules = _pshell(cmd)
    if isinstance(modules, dict):
        ret = []
        if desc:
            modules_ret = {}
            modules_ret[modules['Name']] = copy.deepcopy(modules)
            modules = modules_ret
            return modules
        ret.append(modules['Name'])
        return ret
    names = []
    if desc:
        names = {}
    for module in modules:
        if desc:
            names[module['Name']] = module
            continue
        names.append(module['Name'])
    return names


def install(name):
    '''
    Install a Powershell DSC module on the system.

    name
        Name of a Powershell DSC module

    CLI Example:

    .. code-block:: bash

        salt 'win01' dsc.install PowerPlan
    '''
    # Putting quotes around the parameter protects against command injection
    cmd = 'Install-Module -name "{0}" -Force'.format(name)
    no_ret = _pshell(cmd)
    return name in list_modules()


def remove(name):
    '''
    Remove a Powershell DSC module from the system.

    name
        Name of a Powershell DSC module

    CLI Example:

    .. code-block:: bash

        salt 'win01' dsc.remove PowerPlan
    '''
    # Putting quotes around the parameter protects against command injection
    cmd = 'Uninstall-Module "{0}"'.format(name)
    no_ret = _pshell(cmd)
    return name not in list_modules()


def run_config(path, source=None, saltenv='base'):
    '''
    Run an existing DSC configuration

    :param str path: Path to the directory that contains the .mof configuration
    file to apply. Required.

    :param str source: Path to the directory that contains the .mof file on the
    ``file_roots``. The directory source and path directories must be the same.
    The source directory will be copied to the path directory and then executed.
    If source is not passed, the config located at 'path' will be applied.
    Optional.

    :param str saltenv: The salt environment to use when copying your source.
    Default is 'base'

    :return: True if successful, otherwise False
    :rtype: bool

    CLI Example:

    To apply a config that already exists on the the system

    .. code-block:: bash

        salt '*' dsc.run_config C:\DSC\WebSiteConfiguration

    To cache a configuration for the master and apply it:

    .. code-block:: bash

        salt '*' dsc.run_config C:\DSC\WebSiteConfiguration salt://dsc/configs/WebSiteConfiguration
    '''
    if source:
        # Make sure the folder names match
        pathname = os.path.basename(os.path.normpath(path))
        sourcename = os.path.basename(os.path.normpath(source))
        if pathname.lower() != sourcename.lower():
            error = 'Path and Source folder names must match.'
            log.error(error)
            raise CommandExecutionError(error)

        # Destination path minus the basename
        dest_path = os.path.dirname(os.path.normpath(path))
        log.info('Caching {0}'.format(source))
        cached_files = __salt__['cp.get_dir'](source, dest_path, saltenv)
        if not cached_files:
            error = 'Failed to copy {0}'.format(source)
            log.error(error)
            raise CommandExecutionError(error)

    # Make sure the path exists
    if not os.path.exists(path):
        error = '"{0} not found.'
        log.error(error)
        raise CommandExecutionError(error)

    # Run the DSC Configuration
    # Putting quotes around the parameter protects against command injection
    cmd = '$job = Start-DscConfiguration -Path "{0}";'.format(path)
    cmd += 'Do{ } While ($job.State -notin \'Completed\', \'Failed\'); ' \
           'return $job.State'
    ret = _pshell(cmd)
    if ret == 'Completed':
        log.info('DSC Run Config: {0}'.format(ret))
        return True
    else:
        log.info('DSC Run Config: {0}'.format(ret))
        return False


def get_config():
    '''
    Get the current DSC Configuration

    :return: A dictionary representing the DSC Configuration on the machine
    :rtype: dict

    CLI Example:

    .. code-block:: bash

        salt '*' dsc.get_config
    '''
    cmd = 'Get-DscConfiguration | ' \
          'Select-Object * -ExcludeProperty Cim*'
    return _pshell(cmd)


def test_config():
    '''
    Tests the current applied DSC Configuration

    :return: True if successfully applied, otherwise False
    :rtype: bool

    CLI Example:

    .. code-block:: bash

        salt '*' dsc.test_config
    '''
    cmd = 'Test-DscConfiguration *>&1'
    ret = _pshell(cmd)
    if ret == 'True':
        return True
    else:
        return False


def get_config_status():
    '''
    Get the status of the current DSC Configuration

    :return: A dictionary representing the status of the current DSC
    Configuration on the machine
    :rtype: dict

    CLI Example:

    .. code-block:: bash

        salt '*' dsc.get_config_status
    '''
    cmd = 'Get-DscConfigurationStatus | ' \
          'Select-Object -Property HostName, Status, ' \
          '@{Name="StartDate";Expression={Get-Date ($_.StartDate) -Format g}}, ' \
          'Type, Mode, RebootRequested, NumberofResources'
    return _pshell(cmd)


def get_lcm_config():
    '''
    Get the current Local Configuration Manager settings

    :return: A dictionary representing the Local Configuration Manager settings
     on the machine
    :rtype: dict

    CLI Example:

    .. code-block:: bash

        salt '*' dsc.get_lcm_config
    '''
    cmd = 'Get-DscLocalConfigurationManager | ' \
          'Select-Object -Property ConfigurationModeFrequencyMins, LCMState, ' \
          'RebootNodeIfNeeded, ConfigurationMode, ActionAfterReboot, ' \
          'RefreshMode, CertificateID, ConfigurationID, RefreshFrequencyMins, ' \
          'AllowModuleOverwrite, DebugMode, StatusRetentionTimeInDays '
    return _pshell(cmd)


def set_lcm_config(config_mode=None,
                   config_mode_freq=None,
                   refresh_freq=None,
                   reboot_if_needed=None,
                   action_after_reboot=None,
                   refresh_mode=None,
                   certificate_id=None,
                   configuration_id=None,
                   allow_module_overwrite=None,
                   debug_mode=False,
                   status_retention_days=None):
    '''

    For detailed descriptions of the parameters see:
    https://msdn.microsoft.com/en-us/PowerShell/DSC/metaConfig

    :param str config_mode: How the LCM applies the configuration. Valid values
    are:
    - ApplyOnly
    - ApplyAndMonitor
    - ApplyAndAutoCorrect

    :param int config_mode_freq: How often, in minutes, the current
    configuration is checked and applied. Ignored if config_mode is set to
    ApplyOnly. Default is 15.

    :param str refresh_mode: How the LCM gets configurations. Valid values are:
    - Disabled
    - Push
    - Pull

    :param int refresh_freq: How often, in minutes, the LCM checks for updated
    configurations. (pull mode only) Default is 30.

    .. note:: Either `config_mode_freq` or `refresh_freq` needs to be a multiple
    of the other. See documentation on MSDN for more details.

    :param bool reboot_if_needed: Reboot the machine if needed after a
    configuration is applied. Default is False.

    :param str action_after_reboot: Action to take after reboot. Valid values
    are:
    - ContinueConfiguration
    - StopConfiguration

    :param guid certificate_id: A GUID that specifies a certificate used to
    access the configuration: (pull mode)

    :param guid configuration_id: A GUID that identifies the config file to get
    from a pull server. (pull mode)

    :param bool allow_module_overwrite: New configs are allowed to overwrite old
    ones on the target node.

    :param str debug_mode: Sets the debug level. Valid values are:
    - None
    - ForceModuleImport
    - All

    :param int status_retention_days: Number of days to keep status of the
    current config.

    Returns:

    '''
    cmd = 'Configuration SaltConfig {'
    cmd += '    Node localhost {'
    cmd += '        LocalConfigurationManager {'
    if config_mode:
        if config_mode not in ('ApplyOnly', 'ApplyAndMonitor', 'ApplyAndAutoCorrect'):
            error = 'config_mode must be one of ApplyOnly, ApplyAndMonitor, ' \
                    'or ApplyAndAutoCorrect. Passed {0}'.format(config_mode)
            SaltInvocationError(error)
            return error
        cmd += '            ConfigurationMode = "{0}"'.format(config_mode)
    if config_mode_freq:
        if isinstance(config_mode_freq, int):
            SaltInvocationError('config_mode_freq must be an integer')
            return 'config_mode_freq must be an integer. Passed {0}'.\
                format(config_mode_freq)
        cmd += '            ConfigurationModeFrequencyMins = {0}'.format(config_mode_freq)
    if refresh_mode:
        if refresh_mode not in ('Disabled', 'Push', 'Pull'):
            SaltInvocationError('refresh_mode must be one of Disabled, Push, '
                                'or Pull')
        cmd += '            RefreshMode = "{0}"'.format(refresh_mode)
    if refresh_freq:
        if isinstance(refresh_freq, int):
            SaltInvocationError('refresh_freq must be an integer')
        cmd += '            RefreshFrequencyMins = {0}'.format(refresh_freq)
    if reboot_if_needed is not None:
        if not isinstance(reboot_if_needed, bool):
            SaltInvocationError('reboot_if_needed must be a boolean value')
        if reboot_if_needed:
            reboot_if_needed = '$true'
        else:
            reboot_if_needed = '$false'
        cmd += '            RebootNodeIfNeeded = {0}'.format(reboot_if_needed)
    if action_after_reboot:
        if action_after_reboot not in ('ContinueConfiguration, StopConfiguration'):
            SaltInvocationError('action_after_reboot must be one of '
                                'ContinueConfiguration or StopConfiguration')
        cmd += '            ActionAfterReboot = "{0}"'.format(action_after_reboot)
    if certificate_id is not None:
        if certificate_id == '':
            certificate_id = None
        cmd += '            CertificateID = "{0}"'.format(certificate_id)
    if configuration_id is not None:
        if configuration_id == '':
            configuration_id = None
        cmd += '            ConfigurationID = "{0}"'.format(configuration_id)
    if allow_module_overwrite is not None:
        if not isinstance(allow_module_overwrite, bool):
            SaltInvocationError('allow_module_overwrite must be a boolean value')
        if allow_module_overwrite:
            allow_module_overwrite = '$true'
        else:
            allow_module_overwrite = '$false'
        cmd += '            AllowModuleOverwrite = {0}'.format(allow_module_overwrite)
    if debug_mode is not False:
        if debug_mode is None:
            debug_mode = 'None'
        if debug_mode not in ('None', 'ForceModuleImport', 'All'):
            SaltInvocationError('debug_mode must be one of None, ForceModuleImport, '
                                'ResourceScriptBreakAll, or All')
        cmd += '            DebugMode = "{0}"'.format(debug_mode)
    if status_retention_days:
        if isinstance(status_retention_days, int):
            SaltInvocationError('status_retention_days must be an integer')
        cmd += '            StatusRetentionTimeInDays = {0}'.format(status_retention_days)
    cmd += '        }}};'
    cmd += 'SaltConfig -OutputPath "C:\DSC\SaltConfig"'

    # Execute Config to create the .mof
    __salt__['cmd.shell'](cmd, shell='powershell')

    # Apply the config
    cmd = 'Set-DscLocalConfigurationManager -Path "C:\DSC\SaltConfig"'
    ret = _pshell(cmd)
    if not ret:
        log.info('LCM config applied successfully')
        return True
    else:
        log.error('Failed to apply LCM config. Error {0}'.format(ret))
        return False
