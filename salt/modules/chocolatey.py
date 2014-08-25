# -*- coding: utf-8 -*-
'''
A dead simple module wrapping calls to the Chocolatey package manager
(http://chocolatey.org)

.. versionadded:: 2014.1.0
'''

# Import python libs
import logging
import os.path
import re
import tempfile
from distutils.version import LooseVersion as _LooseVersion

# Import salt libs
import salt.utils
from salt.exceptions import CommandExecutionError, CommandNotFoundError


log = logging.getLogger(__name__)

__func_alias__ = {
    'list_': 'list'
}


def __virtual__():
    '''
    Confirm this module is on a Windows system running Vista or later.

    While it is possible to make Chocolatey run under XP and Server 2003 with
    an awful lot of hassle (e.g. SSL is completely broken), the PowerShell shim
    for simulating UAC forces a GUI prompt, and is not compatible with
    salt-minion running as SYSTEM.
    '''
    if __grains__['os_family'] != 'Windows':
        return False
    elif __grains__['osrelease'] in ('XP', '2003Server'):
        return False
    return 'chocolatey'


def _find_chocolatey():
    '''
    Returns the full path to chocolatey.bat on the host.
    '''
    try:
        return __context__['chocolatey._path']
    except KeyError:
        choc_defaults = ['C:\\Chocolatey\\bin\\chocolatey.bat',
                         'C:\\ProgramData\\Chocolatey\\bin\\chocolatey.exe', ]

        choc_path = __salt__['cmd.which']('chocolatey.exe')
        if not choc_path:
            for choc_dir in choc_defaults:
                if __salt__['cmd.has_exec'](choc_dir):
                    choc_path = choc_dir
        if not choc_path:
            err = ('Chocolatey not installed. Use chocolatey.bootstrap to '
                   'install the Chocolatey package manager.')
            log.error(err)
            raise CommandExecutionError(err)
        __context__['chocolatey._path'] = choc_path
        return choc_path


def chocolatey_version():
    '''
    .. versionadded:: 2014.7.0

    Returns the version of Chocolatey installed on the minion.

    CLI Example:

    .. code-block:: bash

        salt '*' chocolatey.chocolatey_version
    '''
    try:
        return __context__['chocolatey._version']
    except KeyError:
        out = __salt__['cmd.run']('{0} help'.format(_find_chocolatey()))
        for line in out.splitlines():
            if line.lower().startswith('version: '):
                try:
                    __context__['chocolatey._version'] = \
                        line.split(None, 1)[-1].strip("'")
                    return __context__['chocolatey._version']
                except Exception:
                    pass
        raise CommandExecutionError('Unable to determine Chocolatey version')


def bootstrap(force=False):
    '''
    Download and install the latest version of the Chocolatey package manager
    via the official bootstrap.

    Chocolatey requires Windows PowerShell and the .NET v4.0 runtime. Depending
    on the host's version of Windows, chocolatey.bootstrap will attempt to
    ensure these prerequisites are met by downloading and executing the
    appropriate installers from Microsoft.

    Note that if PowerShell is installed, you may have to restart the host
    machine for Chocolatey to work.

    force
        Run the bootstrap process even if Chocolatey is found in the path.

    CLI Example:

    .. code-block:: bash

        salt '*' chocolatey.bootstrap
        salt '*' chocolatey.bootstrap force=True
    '''
    # Check if Chocolatey is already present in the path
    try:
        choc_path = _find_chocolatey()
    except CommandExecutionError:
        choc_path = None
    if choc_path and not force:
        return 'Chocolatey found at {0}'.format(choc_path)

    # The following lookup tables are required to determine the correct
    # download required to install PowerShell. That's right, there's more
    # than one! You're welcome.
    ps_downloads = {
        ('Vista', 'x86'): 'http://download.microsoft.com/download/A/7/5/A75BC017-63CE-47D6-8FA4-AFB5C21BAC54/Windows6.0-KB968930-x86.msu',
        ('Vista', 'AMD64'): 'http://download.microsoft.com/download/3/C/8/3C8CF51E-1D9D-4DAA-AAEA-5C48D1CD055C/Windows6.0-KB968930-x64.msu',
        ('2008Server', 'x86'): 'http://download.microsoft.com/download/F/9/E/F9EF6ACB-2BA8-4845-9C10-85FC4A69B207/Windows6.0-KB968930-x86.msu',
        ('2008Server', 'AMD64'): 'http://download.microsoft.com/download/2/8/6/28686477-3242-4E96-9009-30B16BED89AF/Windows6.0-KB968930-x64.msu'
    }

    # It took until .NET v4.0 for Microsoft got the hang of making installers,
    # this should work under any version of Windows
    net4_url = 'http://download.microsoft.com/download/1/B/E/1BE39E79-7E39-46A3-96FF-047F95396215/dotNetFx40_Full_setup.exe'

    temp_dir = tempfile.gettempdir()

    # Check if PowerShell is installed. This should be the case for every
    # Windows release following Server 2008.
    ps_path = 'C:\\Windows\\SYSTEM32\\WindowsPowerShell\\v1.0\\powershell.exe'

    if not __salt__['cmd.has_exec'](ps_path):
        if (__grains__['osrelease'], __grains__['cpuarch']) in ps_downloads:
            # Install the appropriate release of PowerShell v2.0
            url = ps_downloads[(__grains__['osrelease'], __grains__['cpuarch'])]
            dest = os.path.join(temp_dir, 'powershell.exe')
            __salt__['cp.get_url'](url, dest)
            result = __salt__['cmd.run_all'](dest + ' /quiet /norestart')
            if result['retcode'] != 0:
                err = ('Installing Windows PowerShell failed. Please run the '
                       'installer GUI on the host to get a more specific '
                       'reason.')
                log.error(err)
                raise CommandExecutionError(err)
        else:
            err = 'Windows PowerShell not found'
            log.error(err)
            raise CommandNotFoundError(err)

    # Run the .NET Framework 4 web installer
    dest = os.path.join(temp_dir, 'dotnet4.exe')
    __salt__['cp.get_url'](net4_url, dest)
    result = __salt__['cmd.run_all'](dest + ' /q /norestart')
    if result['retcode'] != 0:
        err = ('Installing .NET v4.0 failed. Please run the installer GUI on '
               'the host to get a more specific reason.')
        log.error(err)
        raise CommandExecutionError(err)

    # Run the Chocolatey bootstrap.
    result = __salt__['cmd.run_all'](
        '{0} -NoProfile -ExecutionPolicy unrestricted '
        '-Command "iex ((new-object net.webclient).'
        'DownloadString(\'https://chocolatey.org/install.ps1\'))" '
        '&& SET PATH=%PATH%;%systemdrive%\\chocolatey\\bin'
        .format(ps_path)
    )

    if result['retcode'] != 0:
        err = 'Bootstrapping Chocolatey failed: {0}'.format(result['stderr'])
        log.error(err)
        raise CommandExecutionError(err)

    return result['stdout']


def list_(filter, all_versions=False, pre_versions=False, source=None):
    '''
    Instructs Chocolatey to pull a vague package list from the repository.

    filter
        Term used to filter down results. Searches against name/description/tag.

    all_versions
        Display all available package versions in results. Defaults to False.

    pre_versions
        Display pre-release packages in results. Defaults to False.

    source
        Chocolatey repository (directory, share or remote URL feed) the package
        comes from. Defaults to the official Chocolatey feed.

    CLI Example:

    .. code-block:: bash

        salt '*' chocolatey.list <filter>
        salt '*' chocolatey.list <filter> all_versions=True
    '''
    choc_path = _find_chocolatey()
    cmd = choc_path + ' list ' + filter
    if salt.utils.is_true(all_versions):
        cmd += ' -AllVersions'
    if salt.utils.is_true(pre_versions):
        cmd += ' -Prerelease'
    if source:
        cmd += ' -Source ' + source

    result = __salt__['cmd.run_all'](cmd)

    if result['retcode'] != 0:
        err = 'Running chocolatey failed: {0}'.format(result['stderr'])
        log.error(err)
        raise CommandExecutionError(err)

    ret = {}
    pkg_re = re.compile(r'(\S+)\s+(\S+)')
    for line in result['stdout'].split('\n'):
        if line.startswith("No packages"):
            return ret
        for name, ver in pkg_re.findall(line):
            if name not in ret:
                ret[name] = []
            ret[name].append(ver)

    #log.info(repr(ret))
    return ret


def list_webpi():
    '''
    Instructs Chocolatey to pull a full package list from the Microsoft Web PI repository.

    CLI Example:

    .. code-block:: bash

        salt '*' chocolatey.list_webpi
    '''
    choc_path = _find_chocolatey()
    cmd = choc_path + ' list -Source webpi'
    result = __salt__['cmd.run_all'](cmd)

    if result['retcode'] != 0:
        err = 'Running chocolatey failed: {0}'.format(result['stderr'])
        log.error(err)
        raise CommandExecutionError(err)

    return result['stdout']


def list_windowsfeatures():
    '''
    Instructs Chocolatey to pull a full package list from the Windows Features
    list, via the Deployment Image Servicing and Management tool.

    CLI Example:

    .. code-block:: bash

        salt '*' chocolatey.list_windowsfeatures
    '''
    choc_path = _find_chocolatey()
    cmd = choc_path + ' list -Source windowsfeatures'
    result = __salt__['cmd.run_all'](cmd)

    if result['retcode'] != 0:
        err = 'Running chocolatey failed: {0}'.format(result['stderr'])
        log.error(err)
        raise CommandExecutionError(err)

    return result['stdout']


def install(name, version=None, source=None, force=False):
    '''
    Instructs Chocolatey to install a package.

    name
        The name of the package to be installed. Only accepts a single argument.

    version
        Install a specific version of the package. Defaults to latest version.

    source
        Chocolatey repository (directory, share or remote URL feed) the package
        comes from. Defaults to the official Chocolatey feed.

    force
        Reinstall the current version of an existing package.

    CLI Example:

    .. code-block:: bash

        salt '*' chocolatey.install <package name>
        salt '*' chocolatey.install <package name> version=<package version>
    '''
    choc_path = _find_chocolatey()
    # chocolatey helpfully only supports a single package argument
    cmd = choc_path + ' install ' + name
    if version:
        cmd += ' -Version ' + version
    if source:
        cmd += ' -Source ' + source
    if salt.utils.is_true(force):
        cmd += ' -Force'
    result = __salt__['cmd.run_all'](cmd)

    if result['retcode'] != 0:
        err = 'Running chocolatey failed: {0}'.format(result['stderr'])
        log.error(err)
        raise CommandExecutionError(err)

    return result['stdout']


def install_cygwin(name):
    '''
    Instructs Chocolatey to install a package via Cygwin.

    name
        The name of the package to be installed. Only accepts a single argument.

    CLI Example:

    .. code-block:: bash

        salt '*' chocolatey.install_cygwin <package name>
    '''
    choc_path = _find_chocolatey()
    cmd = choc_path + ' cygwin ' + name
    result = __salt__['cmd.run_all'](cmd)

    if result['retcode'] != 0:
        err = 'Running chocolatey failed: {0}'.format(result['stderr'])
        log.error(err)
        raise CommandExecutionError(err)

    return result['stdout']


def install_gem(name, version=None):
    '''
    Instructs Chocolatey to install a package via Ruby's Gems.

    name
        The name of the package to be installed. Only accepts a single argument.

    version
        Install a specific version of the package. Defaults to latest version
        available.

    CLI Example:

    .. code-block:: bash

        salt '*' chocolatey.install_gem <package name>
        salt '*' chocolatey.install_gem <package name> version=<package version>
    '''
    choc_path = _find_chocolatey()
    cmd = choc_path + ' gem ' + name
    if version:
        cmd += ' -Version ' + version
    result = __salt__['cmd.run_all'](cmd)

    if result['retcode'] != 0:
        err = 'Running chocolatey failed: {0}'.format(result['stderr'])
        log.error(err)
        raise CommandExecutionError(err)

    return result['stdout']


def install_missing(name, version=None, source=None):
    '''
    Instructs Chocolatey to install a package if it doesn't already exist.

    .. versionchanged:: 2014.7.0
        If the minion has Chocolatey >= 0.9.8.24 installed, this function calls
        :mod:`chocolatey.install <salt.modules.chocolatey.install>` instead, as
        ``installmissing`` is deprecated as of that version and will be removed
        in Chocolatey 1.0.

    name
        The name of the package to be installed. Only accepts a single argument.

    version
        Install a specific version of the package. Defaults to latest version
        available.

    source
        Chocolatey repository (directory, share or remote URL feed) the package
        comes from. Defaults to the official Chocolatey feed.

    CLI Example:

    .. code-block:: bash

        salt '*' chocolatey.install_missing <package name>
        salt '*' chocolatey.install_missing <package name> version=<package version>
    '''
    choc_path = _find_chocolatey()
    if _LooseVersion(chocolatey_version()) >= _LooseVersion('0.9.8.24'):
        log.warning('installmissing is deprecated, using install')
        return install(name, version=version)

    # chocolatey helpfully only supports a single package argument
    cmd = choc_path + ' installmissing ' + name
    if version:
        cmd += ' -Version ' + version
    if source:
        cmd += ' -Source ' + source
    result = __salt__['cmd.run_all'](cmd)

    if result['retcode'] != 0:
        err = 'Running chocolatey failed: {0}'.format(result['stderr'])
        log.error(err)
        raise CommandExecutionError(err)

    return result['stdout']


def install_python(name, version=None):
    '''
    Instructs Chocolatey to install a package via Python's easy_install.

    name
        The name of the package to be installed. Only accepts a single argument.

    version
        Install a specific version of the package. Defaults to latest version
        available.

    CLI Example:

    .. code-block:: bash

        salt '*' chocolatey.install_python <package name>
        salt '*' chocolatey.install_python <package name> version=<package version>
    '''
    choc_path = _find_chocolatey()
    cmd = choc_path + ' python ' + name
    if version:
        cmd += ' -Version ' + version
    result = __salt__['cmd.run_all'](cmd)

    if result['retcode'] != 0:
        err = 'Running chocolatey failed: {0}'.format(result['stderr'])
        log.error(err)
        raise CommandExecutionError(err)

    return result['stdout']


def install_windowsfeatures(name):
    '''
    Instructs Chocolatey to install a Windows Feature via the Deployment Image
    Servicing and Management tool.

    name
        The name of the feature to be installed. Only accepts a single argument.

    CLI Example:

    .. code-block:: bash

        salt '*' chocolatey.install_windowsfeatures <package name>
    '''
    choc_path = _find_chocolatey()
    cmd = choc_path + ' windowsfeatures ' + name
    result = __salt__['cmd.run_all'](cmd)

    if result['retcode'] != 0:
        err = 'Running chocolatey failed: {0}'.format(result['stderr'])
        log.error(err)
        raise CommandExecutionError(err)

    return result['stdout']


def install_webpi(name):
    '''
    Instructs Chocolatey to install a package via the Microsoft Web PI service.

    name
        The name of the package to be installed. Only accepts a single argument.

    CLI Example:

    .. code-block:: bash

        salt '*' chocolatey.install_webpi <package name>
    '''
    choc_path = _find_chocolatey()
    cmd = choc_path + ' webpi ' + name
    result = __salt__['cmd.run_all'](cmd)

    if result['retcode'] != 0:
        err = 'Running chocolatey failed: {0}'.format(result['stderr'])
        log.error(err)
        raise CommandExecutionError(err)

    return result['stdout']


def uninstall(name, version=None):
    '''
    Instructs Chocolatey to uninstall a package.

    name
        The name of the package to be uninstalled. Only accepts a single argument.

    version
        Uninstalls a specific version of the package. Defaults to latest version
        installed.

    CLI Example:

    .. code-block:: bash

        salt '*' chocolatey.uninstall <package name>
        salt '*' chocolatey.uninstall <package name> version=<package version>
    '''
    choc_path = _find_chocolatey()
    # chocolatey helpfully only supports a single package argument
    cmd = choc_path + ' uninstall ' + name
    if version:
        cmd += ' -Version ' + version
    result = __salt__['cmd.run_all'](cmd)

    if result['retcode'] != 0:
        err = 'Running chocolatey failed: {0}'.format(result['stderr'])
        log.error(err)
        raise CommandExecutionError(err)

    return result['stdout']


def update(name, source=None, pre_versions=False):
    '''
    Instructs Chocolatey to update packages on the system.

    name
        The name of the package to update, or "all" to update everything
        installed on the system.

    source
        Chocolatey repository (directory, share or remote URL feed) the package
        comes from. Defaults to the official Chocolatey feed.

    pre_versions
        Include pre-release packages in comparison. Defaults to False.

    CLI Example:

    .. code-block:: bash

        salt "*" chocolatey.update all
        salt "*" chocolatey.update <package name> pre_versions=True
    '''
    # chocolatey helpfully only supports a single package argument
    choc_path = _find_chocolatey()
    cmd = choc_path + ' update ' + name
    if source:
        cmd += ' -Source ' + source
    if salt.utils.is_true(pre_versions):
        cmd += ' -PreRelease'
    result = __salt__['cmd.run_all'](cmd)

    if result['retcode'] != 0:
        err = 'Running chocolatey failed: {0}'.format(result['stderr'])
        log.error(err)
        raise CommandExecutionError(err)

    return result['stdout']


def version(name, check_remote=False, source=None, pre_versions=False):
    '''
    Instructs Chocolatey to check an installed package version, and optionally
    compare it to one available from a remote feed.

    name
        The name of the package to check.

    check_remote
        Get the version number of the latest package from the remote feed.
        Defaults to False.

    source
        Chocolatey repository (directory, share or remote URL feed) the package
        comes from. Defaults to the official Chocolatey feed.

    pre_versions
        Include pre-release packages in comparison. Defaults to False.

    CLI Example:

    .. code-block:: bash

        salt "*" chocolatey.version <package name>
        salt "*" chocolatey.version <package name> check_remote=True
    '''
    choc_path = _find_chocolatey()
    if not choc_path:
        err = 'Chocolatey not installed. Use chocolatey.bootstrap to install the Chocolatey package manager.'
        log.error(err)
        raise CommandExecutionError(err)

    cmd = choc_path + ' version ' + name
    if not salt.utils.is_true(check_remote):
        cmd += ' -LocalOnly'
    if salt.utils.is_true(pre_versions):
        cmd += ' -Prerelease'
    if source:
        cmd += ' -Source ' + source

    result = __salt__['cmd.run_all'](cmd)

    if result['retcode'] != 0:
        err = 'Running chocolatey failed: {0}'.format(result['stderr'])
        log.error(err)
        raise CommandExecutionError(err)

    ret = {}

    # the next bit is to deal with the stupid default PowerShell formatting.
    # printing two value pairs is shown in columns, whereas printing six
    # pairs is shown in rows...
    if not salt.utils.is_true(check_remote):
        ver_re = re.compile(r'(\S+)\s+(.+)')
        for line in result['stdout'].split('\n'):
            for name, ver in ver_re.findall(line):
                ret['name'] = name
                ret['found'] = ver
    else:
        ver_re = re.compile(r'(\S+)\s+:\s*(.*)')
        for line in result['stdout'].split('\n'):
            for key, value in ver_re.findall(line):
                ret[key] = value

    return ret
