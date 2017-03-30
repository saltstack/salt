# -*- coding: utf-8 -*-
'''
Module for working with DSC (Alpha)

:depends:
    - PowerShell 5.0
'''
from __future__ import absolute_import, unicode_literals

# Import python libs
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
    # Verify Windows
    if not salt.utils.is_windows():
        log.debug('Module DSC: Only available on Windows systems')
        return False, 'Module DSC: Only available on Windows systems'

    # Verify PowerShell
    powershell_info = __salt__['cmd.shell_info']('powershell')
    if not powershell_info['installed']:
        log.debug('Module DSC: Requires PowerShell')
        return False, 'Module DSC: Requires PowerShell'

    # Verify PowerShell 5.0 or greater
    if salt.utils.compare_versions(powershell_info['version'], '<', '5.0'):
        log.debug('Module DSC: Requires PowerShell 5 or later')
        return False, 'Module DSC: Requires PowerShell 5 or later'

    return __virtualname__


def _pshell(cmd, cwd=None, json_depth=2):
    '''
    Execute the desired powershell command and ensure that it returns data
    in json format and load that into python
    '''
    if 'convertto-json' not in cmd.lower():
        cmd = '{0} | ConvertTo-Json -Depth {1}'.format(cmd, json_depth)
    log.debug('DSC: {0}'.format(cmd))
    results = __salt__['cmd.run_all'](
        cmd, shell='powershell', cwd=cwd, python_shell=True)

    if 'pid' in results:
        del results['pid']

    if 'retcode' not in results or results['retcode'] != 0:
        # run_all logs an error to log.error, fail hard back to the user
        raise CommandExecutionError(
            'Issue executing powershell {0}'.format(cmd), info=results)

    try:
        ret = json.loads(results['stdout'], strict=False)
    except ValueError:
        raise CommandExecutionError(
            'No JSON results from powershell', info=results)

    return ret


def run_config(path, source=None, config=None, salt_env='base'):
    r'''
    Compile a DSC Configuration in the form of a powershell script (.ps1) and
    apply it. The powershell script can be cached from the master using the
    ``source`` option. If there is more than one config within the powershell
    script, the desired configuration can be applied by passing the name in the
    ``config`` option.

    This command would be the equivalent of running ``dsc.compile_config`` and
    ``dsc.apply_config`` separately.

    :param str path: The local path to the powershell script that contains the
    DSC Configuration.
    Required.

    :param str source: The path to the script on ``file_roots`` to cache at the
    location specified by ``path``. The source file will be cached locally and
    then executed. If source is not passed, the config script located at
    ``path`` will be compiled.
    Optional.

    :param str config: The name of the Configuration within the script to apply.
    If the script contains multiple configurations within the file a config
    must be specified. If the config is not specified, the name of the file will
    be used as the config to run.
    Optional.

    :param str salt_env: The salt environment to use when copying the source.
    Default is 'base'

    :return: True if successfully compiled and applied, False if not
    :rtype: bool

    CLI Example:

    To compile a config from a script that already exists on the system:

    .. code-block:: bash

        salt '*' dsc.compile_apply_config C:\\DSC\\WebsiteConfig.ps1

    To cache a config script to the system from the master and compile it:

    .. code-block:: bash

        salt '*' dsc.compile_apply_config C:\\DSC\\WebsiteConfig.ps1 salt://dsc/configs/WebsiteConfig.ps1
    '''
    ret = compile_config(path, source, config, salt_env)

    if ret.get('Exists'):
        config_path = os.path.dirname(ret['FullName'])
        return apply_config(config_path)
    else:
        return False


def compile_config(path, source=None, config=None, salt_env='base'):
    r'''
    Compile a config from a powershell script (``.ps1``)

    :param str path: Path (local) to the script that will create the ``.mof``
    configuration file. If no source is passed, the file must exist locally.
    Required.

    :param str source: Path to the script on ``file_roots`` to cache at the
    location specified by ``path``. The source file will be cached locally and
    then executed. If source is not passed, the config script located at
    ``path`` will be compiled.
    Optional.

    :param str config: The name of the Configuration within the script to apply.
    If the script contains multiple configurations within the file a config
    must be specified. If the config is not specified, the name of the file will
    be used as the config to run.
    Optional.

    :param str salt_env: The salt environment to use when copying the source.
    Default is 'base'

    :return: A dictionary containing the results of the compilation
    :rtype: dict

    CLI Example:

    To compile a config from a script that already exists on the system:

    .. code-block:: bash

        salt '*' dsc.compile_config C:\\DSC\\WebsiteConfig.ps1

    To cache a config script to the system from the master and compile it:

    .. code-block:: bash

        salt '*' dsc.compile_config C:\\DSC\\WebsiteConfig.ps1 salt://dsc/configs/WebsiteConfig.ps1
    '''
    if source:
        log.info('Caching {0}'.format(source))
        cached_files = __salt__['cp.get_file'](path=source,
                                               dest=path,
                                               saltenv=salt_env,
                                               makedirs=True)
        if not cached_files:
            error = 'Failed to cache {0}'.format(source)
            log.error(error)
            raise CommandExecutionError(error)

    # Make sure the path exists
    if not os.path.exists(path):
        error = '"{0} not found.'.format(path)
        log.error(error)
        raise CommandExecutionError(error)

    if config is None:
        # If the name of the config isn't passed, make it the name of the .ps1
        config = os.path.splitext(os.path.basename(path))[0]

    cwd = os.path.dirname(path)

    # Run the script and see if the compile command is in the script
    cmd = '{0} '.format(path)
    cmd += '| Select-Object -Property FullName, Extension, Exists, ' \
           '@{Name="LastWriteTime";Expression={Get-Date ($_.LastWriteTime) ' \
           '-Format g}}'

    ret = _pshell(cmd, cwd)

    if ret:
        # Script compiled, return results
        if ret.get('Exists'):
            log.info('DSC Compile Config: {0}'.format(ret))
            return ret

    # Run the script and run the compile command
    cmd = '. {0} ; {1} '.format(path, config)
    cmd += '| Select-Object -Property FullName, Extension, Exists, ' \
           '@{Name="LastWriteTime";Expression={Get-Date ($_.LastWriteTime) ' \
           '-Format g}}'

    ret = _pshell(cmd, cwd)

    if ret:
        # Script compiled, return results
        if ret.get('Exists'):
            log.info('DSC Compile Config: {0}'.format(ret))
            return ret

    error = 'Failed to compile config: {0}'.format(path)
    error += '\nReturned: {0}'.format(ret)
    log.error('DSC Compile Config: {0}'.format(error))
    raise CommandExecutionError(error)


def apply_config(path, source=None, salt_env='base'):
    r'''
    Run an compiled DSC configuration (a folder containing a .mof file). The
    folder can be cached from the salt master using the ``source`` option.

    :param str path: Local path to the directory that contains the .mof
    configuration file to apply.
    Required.

    :param str source: Path to the directory that contains the .mof file on the
    ``file_roots``. The source directory will be copied to the path directory
    and then executed. If the path and source directories differ, the source
    directory will be applied. If source is not passed, the config located at
    ``path`` will be applied.
    Optional.

    :param str salt_env: The salt environment to use when copying your source.
    Default is 'base'

    :return: True if successful, otherwise False
    :rtype: bool

    CLI Example:

    To apply a config that already exists on the the system

    .. code-block:: bash

        salt '*' dsc.run_config C:\\DSC\\WebSiteConfiguration

    To cache a configuration from the master and apply it:

    .. code-block:: bash

        salt '*' dsc.run_config C:\\DSC\\WebSiteConfiguration salt://dsc/configs/WebSiteConfiguration

    '''
    # If you're getting an error along the lines of "The client cannot connect
    # to the destination specified in the request.", try the following:
    # Enable-PSRemoting -SkipNetworkProfileCheck
    config = path
    if source:
        # Make sure the folder names match
        path_name = os.path.basename(os.path.normpath(path))
        source_name = os.path.basename(os.path.normpath(source))
        if path_name.lower() != source_name.lower():
            # Append the Source name to the Path
            path = '{0}\\{1}'.format(path, source_name)
            log.debug('{0} appended to the path.'.format(source_name))

        # Destination path minus the basename
        dest_path = os.path.dirname(os.path.normpath(path))
        log.info('Caching {0}'.format(source))
        cached_files = __salt__['cp.get_dir'](source, dest_path, salt_env)
        if not cached_files:
            error = 'Failed to copy {0}'.format(source)
            log.error(error)
            raise CommandExecutionError(error)
        else:
            config = os.path.dirname(cached_files[0])

    # Make sure the path exists
    if not os.path.exists(config):
        error = '{0} not found.'.format(config)
        log.error(error)
        raise CommandExecutionError(error)

    # Run the DSC Configuration
    # Putting quotes around the parameter protects against command injection
    cmd = 'Start-DscConfiguration -Path "{0}" -Wait -Force'.format(config)
    ret = _pshell(cmd)

    if ret is False:
        raise CommandExecutionError('Apply Config Failed: {0}'.format(path))

    cmd = '$status = Get-DscConfigurationStatus; $status.Status'
    ret = _pshell(cmd)
    log.info('DSC Apply Config: {0}'.format(ret))

    return ret == 'Success'


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
    return ret == 'True'


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
          'Select-Object -Property HostName, Status, MetaData, ' \
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

    Returns (bool): True if successful, otherwise False

    CLI Example:

    .. code-block:: bash

        salt '*' dsc.set_lcm_config ApplyOnly
    '''
    temp_dir = os.getenv('TEMP', '{0}\\temp'.format(os.getenv('WINDIR')))
    cmd = 'Configuration SaltConfig {'
    cmd += '    Node localhost {'
    cmd += '        LocalConfigurationManager {'
    if config_mode:
        if config_mode not in ('ApplyOnly', 'ApplyAndMonitor',
                               'ApplyAndAutoCorrect'):
            error = 'config_mode must be one of ApplyOnly, ApplyAndMonitor, ' \
                    'or ApplyAndAutoCorrect. Passed {0}'.format(config_mode)
            SaltInvocationError(error)
            return error
        cmd += '            ConfigurationMode = "{0}";'.format(config_mode)
    if config_mode_freq:
        if not isinstance(config_mode_freq, int):
            SaltInvocationError('config_mode_freq must be an integer')
            return 'config_mode_freq must be an integer. Passed {0}'.\
                format(config_mode_freq)
        cmd += '            ConfigurationModeFrequencyMins = {0};'.format(config_mode_freq)
    if refresh_mode:
        if refresh_mode not in ('Disabled', 'Push', 'Pull'):
            SaltInvocationError('refresh_mode must be one of Disabled, Push, '
                                'or Pull')
        cmd += '            RefreshMode = "{0}";'.format(refresh_mode)
    if refresh_freq:
        if not isinstance(refresh_freq, int):
            SaltInvocationError('refresh_freq must be an integer')
        cmd += '            RefreshFrequencyMins = {0};'.format(refresh_freq)
    if reboot_if_needed is not None:
        if not isinstance(reboot_if_needed, bool):
            SaltInvocationError('reboot_if_needed must be a boolean value')
        if reboot_if_needed:
            reboot_if_needed = '$true'
        else:
            reboot_if_needed = '$false'
        cmd += '            RebootNodeIfNeeded = {0};'.format(reboot_if_needed)
    if action_after_reboot:
        if action_after_reboot not in ('ContinueConfiguration',
                                       'StopConfiguration'):
            SaltInvocationError('action_after_reboot must be one of '
                                'ContinueConfiguration or StopConfiguration')
        cmd += '            ActionAfterReboot = "{0}"'.format(action_after_reboot)
    if certificate_id is not None:
        if certificate_id == '':
            certificate_id = None
        cmd += '            CertificateID = "{0}";'.format(certificate_id)
    if configuration_id is not None:
        if configuration_id == '':
            configuration_id = None
        cmd += '            ConfigurationID = "{0}";'.format(configuration_id)
    if allow_module_overwrite is not None:
        if not isinstance(allow_module_overwrite, bool):
            SaltInvocationError('allow_module_overwrite must be a boolean value')
        if allow_module_overwrite:
            allow_module_overwrite = '$true'
        else:
            allow_module_overwrite = '$false'
        cmd += '            AllowModuleOverwrite = {0};'.format(allow_module_overwrite)
    if debug_mode is not False:
        if debug_mode is None:
            debug_mode = 'None'
        if debug_mode not in ('None', 'ForceModuleImport', 'All'):
            SaltInvocationError('debug_mode must be one of None, '
                                'ForceModuleImport, ResourceScriptBreakAll, or '
                                'All')
        cmd += '            DebugMode = "{0}";'.format(debug_mode)
    if status_retention_days:
        if not isinstance(status_retention_days, int):
            SaltInvocationError('status_retention_days must be an integer')
        cmd += '            StatusRetentionTimeInDays = {0};'.format(status_retention_days)
    cmd += '        }}};'
    cmd += r'SaltConfig -OutputPath "{0}\SaltConfig"'.format(temp_dir)

    # Execute Config to create the .mof
    _pshell(cmd)

    # Apply the config
    cmd = r'Set-DscLocalConfigurationManager -Path "{0}\SaltConfig"' \
          r''.format(temp_dir)
    ret = __salt__['cmd.run_all'](cmd, shell='powershell', python_shell=True)
    __salt__['file.remove'](r'{0}\SaltConfig'.format(temp_dir))
    if not ret['retcode']:
        log.info('LCM config applied successfully')
        return True
    else:
        log.error('Failed to apply LCM config. Error {0}'.format(ret))
        return False
