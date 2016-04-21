# -*- coding: utf-8 -*-
'''
Module for managing PowerShell through PowerShellGet (PSGet)

:depends:
    - PowerShell 5.0
    - PSGet

Support for PowerShell
'''
from __future__ import absolute_import

# Import python libs
import copy
import logging
import json

# Import salt libs
import salt.utils

# Set up logging
log = logging.getLogger(__name__)

# Define the module's virtual name
__virtualname__ = 'psget'


def __virtual__():
    '''
    Set the system module of the kernel is Windows
    '''
    if not salt.utils.is_windows():
        return (False, 'Module PSGet: Module only works on Windows systems ')

    if psversion() < 5:
        return (False, 'Module PSGet: Module only works with PowerShell 5 or later.')

    return __virtualname__


def _pshell(cmd, cwd=None):
    '''
    Execute the desired powershell command and ensure that it returns data
    in json format and load that into python
    '''
    if 'convertto-json' not in cmd.lower():
        cmd = ' '.join([cmd, '| ConvertTo-Json'])
    log.debug('PSGET: {0}'.format(cmd))
    ret = __salt__['cmd.shell'](cmd, shell='powershell', cwd=cwd)
    try:
        ret = json.loads(ret, strict=False)
    except ValueError:
        log.debug('Json not returned')
    return ret


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


def bootstrap():
    '''
    Make sure that nuget-anycpu.exe is installed.
    This will download the official nuget-anycpu.exe from the internet.

    CLI Example:

    .. code-block:: bash

        salt 'win01' psget.bootstrap
    '''
    cmd = 'Get-PackageProvider -Name NuGet -ForceBootstrap'
    ret = _pshell(cmd)
    return ret


def avail_modules(desc=False):
    '''
    List available modules in registered Powershell module repositories.

    :param desc: If ``True``, the verbose description will be returned.
    :type  desc: ``bool``

    CLI Example:

    .. code-block:: bash

        salt 'win01' psget.avail_modules
        salt 'win01' psget.avail_modules desc=True
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
    List currently installed PSGet Modules on the system.

    :param desc: If ``True``, the verbose description will be returned.
    :type  desc: ``bool``

    CLI Example:

    .. code-block:: bash

        salt 'win01' psget.list_modules
        salt 'win01' psget.list_modules desc=True
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


def install(name, minimum_version=None, required_version=None, scope=None,
            repository=None):
    '''
    Install a Powershell module from powershell gallery on the system.

    :param name: Name of a Powershell module
    :type  name: ``str``

    :param minimum_version: The maximum version to install, e.g. 1.23.2
    :type  minimum_version: ``str``

    :param required_version: Install a specific version
    :type  required_version: ``str``

    :param scope: The scope to install the module to, e.g. CurrentUser, Computer
    :type  scope: ``str``

    :param repository: The friendly name of a private repository, e.g. MyREpo
    :type  repository: ``str``

    CLI Example:

    .. code-block:: bash

        salt 'win01' psget.install PowerPlan
    '''
    # Putting quotes around the parameter protects against command injection
    flags = [('Name', name)]

    if minimum_version is not None:
        flags.append(('MinimumVersion', minimum_version))
    if required_version is not None:
        flags.append(('RequiredVersion', required_version))
    if scope is not None:
        flags.append(('Scope', scope))
    if repository is not None:
        flags.append(('Repository', repository))
    params = ''
    for flag, value in flags:
        params += '-{0} {1} '.format(flag, value)
    cmd = 'Install-Module {0} -Force'.format(params)
    _pshell(cmd)
    return name in list_modules()


def update(name, maximum_version=None, required_version=None):
    '''
    Update a PowerShell module to a specific version, or the newest

    :param name: Name of a Powershell module
    :type  name: ``str``

    :param maximum_version: The maximum version to install, e.g. 1.23.2
    :type  maximum_version: ``str``

    :param required_version: Install a specific version
    :type  required_version: ``str``

    CLI Example:

    .. code-block:: bash

        salt 'win01' psget.update PowerPlan
    '''
    # Putting quotes around the parameter protects against command injection
    flags = [('Name', name)]

    if maximum_version is not None:
        flags.append(('MaximumVersion', maximum_version))
    if required_version is not None:
        flags.append(('RequiredVersion', required_version))

    params = ''
    for flag, value in flags:
        params += '-{0} {1} '.format(flag, value)
    cmd = 'Update-Module {0} -Force'.format(params)
    _pshell(cmd)
    return name in list_modules()


def remove(name):
    '''
    Remove a Powershell DSC module from the system.

    :param  name: Name of a Powershell DSC module
    :type   name: ``str``

    CLI Example:

    .. code-block:: bash

        salt 'win01' psget.remove PowerPlan
    '''
    # Putting quotes around the parameter protects against command injection
    cmd = 'Uninstall-Module "{0}"'.format(name)
    no_ret = _pshell(cmd)
    return name not in list_modules()


def register_repository(name, location, installation_policy=None):
    '''
    Register a PSGet repository on the local machine

    :param name: The name for the repository
    :type  name: ``str``

    :param location: The URI for the repository
    :type  location: ``str``

    :param installation_policy: The installation policy
        for packages, e.g. Trusted, Untrusted
    :type  installation_policy: ``str``

    CLI Example:

    .. code-block:: bash

        salt 'win01' psget.register_repository MyRepo https://myrepo.mycompany.com/packages
    '''
    # Putting quotes around the parameter protects against command injection
    flags = [('Name', name)]

    flags.append(('SourceLocation', location))
    if installation_policy is not None:
        flags.append(('InstallationPolicy', installation_policy))

    params = ''
    for flag, value in flags:
        params += '-{0} {1} '.format(flag, value)
    cmd = 'Register-PSRepository {0}'.format(params)
    no_ret = _pshell(cmd)
    return name not in list_modules()


def get_repository(name):
    '''
    Get the details of a local PSGet repository

    :param  name: Name of the repository
    :type   name: ``str``

    CLI Example:

    .. code-block:: bash

        salt 'win01' psget.get_repository MyRepo
    '''
    # Putting quotes around the parameter protects against command injection
    cmd = 'Get-PSRepository "{0}"'.format(name)
    no_ret = _pshell(cmd)
    return name not in list_modules()
