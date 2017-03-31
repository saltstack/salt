# -*- coding: utf-8 -*-
'''
Module for managing PowerShell through PowerShellGet (PSGet)

:depends:
    - PowerShell 5.0
    - PSGet

Support for PowerShell
'''
from __future__ import absolute_import, unicode_literals

# Import python libs
import copy
import logging
import json

# Import salt libs
import salt.utils
from salt.exceptions import CommandExecutionError
from salt.utils.versions import StrictVersion as _StrictVersion

# Set up logging
log = logging.getLogger(__name__)

# Define the module's virtual name
__virtualname__ = 'psget'


def __virtual__():
    '''
    Set the system module of the kernel is Windows
    '''
    # Verify Windows
    if not salt.utils.is_windows():
        log.debug('Module PSGet: Only available on Windows systems')
        return False, 'Module PSGet: Only available on Windows systems'

    # Verify PowerShell
    powershell_info = __salt__['cmd.shell_info']('powershell')
    if not powershell_info['installed']:
        log.debug('Module PSGet: Requires PowerShell')
        return False, 'Module PSGet: Requires PowerShell'

    # Verify PowerShell 5.0 or greater
    if salt.utils.compare_versions(powershell_info['version'], '<', '5.0'):
        log.debug('Module PSGet: Requires PowerShell 5 or newer')
        return False, 'Module PSGet: Requires PowerShell 5 or newer.'

    return __virtualname__


def _pshell(cmd, cwd=None, json_depth=2):
    '''
    Execute the desired powershell command and ensure that it returns data
    in json format and load that into python
    '''
    if 'convertto-json' not in cmd.lower():
        cmd = '{0} | ConvertTo-Json -Depth {1}'.format(cmd, json_depth)
    log.debug('DSC: {0}'.format(cmd))
    results = __salt__['cmd.run_all'](cmd, shell='powershell', cwd=cwd, python_shell=True)

    if 'pid' in results:
        del results['pid']

    if 'retcode' not in results or results['retcode'] != 0:
        # run_all logs an error to log.error, fail hard back to the user
        raise CommandExecutionError('Issue executing powershell {0}'.format(cmd), info=results)

    try:
        ret = json.loads(results['stdout'], strict=False)
    except ValueError:
        raise CommandExecutionError('No JSON results from powershell', info=results)

    return ret


def psversion():
    '''
    Returns the Powershell version

    This has been deprecated and has been replaced by ``cmd.shell_info`` Note
    the minimum version return is 5 as ``dsc`` is not available for version
    less than 5.  This function will be removed in 'Oxygen' release.

    CLI Example:

    .. code-block:: bash

        salt 'win01' dsc.psversion
    '''
    salt.utils.warn_until('Oxygen',
        'The \'psversion\' has been deprecated and has been '
        'replaced by \'cmd.shell_info\'.'
    )
    powershell_info = __salt__['cmd.shell_info']('powershell')
    if powershell_info['installed']:
        try:
            return int(powershell_info['version'].split('.')[0])
        except ValueError:
            pass
    return 0


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
