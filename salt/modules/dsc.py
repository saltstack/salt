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
from salt.exceptions import CommandExecutionError

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
            raise CommandExecutionError('Path and Source folder names don\'t '
                                        'match')

        # Destination path minus the basename
        dest_path = os.path.dirname(os.path.normpath(path))
        log.info('Caching {0}'.format(source))
        cached_files = __salt__['cp.get_dir'](source, dest_path, saltenv)
        if not cached_files:
            raise CommandExecutionError('Failed to copy {0}'.format(source))

    # Make sure the path exists
    if not os.path.exists(path):
        raise CommandExecutionError('Must pass a valid path')

    # Run the DSC Configuration
    # Putting quotes around the parameter protects against command injection
    cmd = '$job = Start-DscConfiguration -Path "{0}";'.format(path)
    cmd += 'Do{ } While ($job.State -notin \'Completed\', \'Failed\'); ' \
           'return $job.State'
    ret = _pshell(cmd)
    if ret == 'Completed':
        return True
    else:
        return False


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
          'Select-Object * -ExcludeProperty Cim*'
    return _pshell(cmd)


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


def set_config_status():
    cmd = 'Configuration SaltConfig {'
    cmd += '    Node "SAVDALHV01 {'
    cmd += '        LocalConfigurationManager {'
    cmd += '            ConfigurationMode = "ApplyAndAutoCorrect"'
    cmd += '            ConfigurationModeFrequencyMins = 30 #must be a multiple of the RefreshFrequency and how often configuration is checked'
    cmd += '            RefreshFrequencyMins = 15  #15 is minimum and this is how often configuration is pulled from pull server'
    cmd += '        }}};'
    cmd += 'SaltConfig -OutputPath "C:\DSC\SaltConfig"'
    # Execute

    # Apply
    Set-DscLocalConfigurationManager -Path "C:\Users\administrator\dsc" -Verbose


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
