# -*- coding: utf-8 -*-
"""
Manage cygwin packages.

Module file to accompany the cyg state.
"""
from __future__ import absolute_import, print_function, unicode_literals

# Import python libs
import logging
import re
import os
import bz2

# Import 3rd-party libs
from salt.ext.six.moves.urllib.request import urlopen as _urlopen  # pylint: disable=no-name-in-module,import-error

# Import Salt libs
import salt.utils.files
import salt.utils.platform
import salt.utils.stringutils
from salt.exceptions import SaltInvocationError

# Import 3rd-party libs
from salt.ext import six


LOG = logging.getLogger(__name__)

DEFAULT_MIRROR = "ftp://mirrors.kernel.org/sourceware/cygwin/"
DEFAULT_MIRROR_KEY = ""

# Define the module's virtual name
__virtualname__ = 'cyg'


def __virtual__():
    '''
    Only works on Windows systems
    '''
    if salt.utils.platform.is_windows():
        return __virtualname__
    return (False, 'Module cyg: module only works on Windows systems.')


__func_alias__ = {
    'list_': 'list'
}


def _get_cyg_dir(cyg_arch='x86_64'):
    """Return the cygwin install directory based on the architecture."""
    if cyg_arch == 'x86_64':
        return 'cygwin64'
    elif cyg_arch == 'x86':
        return 'cygwin'

    raise SaltInvocationError(
        'Invalid architecture {arch}'.format(arch=cyg_arch))


def _check_cygwin_installed(cyg_arch='x86_64'):
    """
    Return True or False if cygwin is installed.

    Use the cygcheck executable to check install. It is installed as part of
    the base package, and we use it to check packages
    """
    path_to_cygcheck = os.sep.join(['C:',
                                    _get_cyg_dir(cyg_arch),
                                    'bin', 'cygcheck.exe'])
    LOG.debug('Path to cygcheck.exe: {0}'.format(path_to_cygcheck))
    if not os.path.exists(path_to_cygcheck):
        LOG.debug('Could not find cygcheck.exe')
        return False
    return True


def _get_all_packages(mirror=DEFAULT_MIRROR,
                      cyg_arch='x86_64'):
    """Return the list of packages based on the mirror provided."""
    if 'cyg.all_packages' not in __context__:
        __context__['cyg.all_packages'] = {}
    if mirror not in __context__['cyg.all_packages']:
        __context__['cyg.all_packages'][mirror] = []
    if not len(__context__['cyg.all_packages'][mirror]):
        pkg_source = '/'.join([mirror, cyg_arch, 'setup.bz2'])

        file_data = _urlopen(pkg_source).read()
        file_lines = bz2.decompress(file_data).decode('utf_8',
                                                      errors='replace'
                                                     ).splitlines()

        packages = [re.search('^@ ([^ ]+)', line).group(1) for
                    line in file_lines if re.match('^@ [^ ]+', line)]

        __context__['cyg.all_packages'][mirror] = packages

    return __context__['cyg.all_packages'][mirror]


def check_valid_package(package,
                        cyg_arch='x86_64',
                        mirrors=None):
    '''
    Check if the package is valid on the given mirrors.

    Args:
        package: The name of the package
        cyg_arch: The cygwin architecture
        mirrors: any mirrors to check

    Returns (bool): True if Valid, otherwise False

    CLI Example:

    .. code-block:: bash

        salt '*' cyg.check_valid_package <package name>
    '''
    if mirrors is None:
        mirrors = [{DEFAULT_MIRROR: DEFAULT_MIRROR_KEY}]

    LOG.debug('Checking Valid Mirrors: {0}'.format(mirrors))

    for mirror in mirrors:
        for mirror_url, key in mirror.items():
            if package in _get_all_packages(mirror_url, cyg_arch):
                return True
    return False


def _run_silent_cygwin(cyg_arch='x86_64',
                       args=None,
                       mirrors=None):
    """
    Retrieve the correct setup.exe.

    Run it with the correct arguments to get the bare minimum cygwin
    installation up and running.
    """
    cyg_cache_dir = os.sep.join(['c:', 'cygcache'])
    cyg_setup = 'setup-{0}.exe'.format(cyg_arch)
    cyg_setup_path = os.sep.join([cyg_cache_dir, cyg_setup])
    cyg_setup_source = 'http://cygwin.com/{0}'.format(cyg_setup)
    # cyg_setup_source_hash = 'http://cygwin.com/{0}.sig'.format(cyg_setup)

    # until a hash gets published that we can verify the newest setup against
    # just go ahead and download a new one.
    if not os.path.exists(cyg_cache_dir):
        os.mkdir(cyg_cache_dir)
    elif os.path.exists(cyg_setup_path):
        os.remove(cyg_setup_path)

    file_data = _urlopen(cyg_setup_source)
    with salt.utils.files.fopen(cyg_setup_path, "wb") as fhw:
        fhw.write(file_data.read())

    setup_command = cyg_setup_path
    options = []
    options.append('--local-package-dir {0}'.format(cyg_cache_dir))

    if mirrors is None:
        mirrors = [{DEFAULT_MIRROR: DEFAULT_MIRROR_KEY}]
    for mirror in mirrors:
        for mirror_url, key in mirror.items():
            options.append('--site {0}'.format(mirror_url))
            if key:
                options.append('--pubkey {0}'.format(key))
    options.append('--no-desktop')
    options.append('--quiet-mode')
    options.append('--disable-buggy-antivirus')
    if args is not None:
        for arg in args:
            options.append(arg)

    cmdline_args = ' '.join(options)
    setup_command = ' '.join([cyg_setup_path, cmdline_args])

    ret = __salt__['cmd.run_all'](
        setup_command
    )

    if ret['retcode'] == 0:
        return ret['stdout']
    else:
        return False


def _cygcheck(args, cyg_arch='x86_64'):
    """Run the cygcheck executable."""
    cmd = ' '.join([
        os.sep.join(['c:', _get_cyg_dir(cyg_arch), 'bin', 'cygcheck']),
        '-c', args])

    ret = __salt__['cmd.run_all'](cmd)

    if ret['retcode'] == 0:
        return ret['stdout']
    else:
        return False


def install(packages=None,
            cyg_arch='x86_64',
            mirrors=None):
    """
    Install one or several packages.

    packages : None
        The packages to install

    cyg_arch : x86_64
        Specify the architecture to install the package under
        Current options are x86 and x86_64

    CLI Example:

    .. code-block:: bash

        salt '*' cyg.install dos2unix
        salt '*' cyg.install dos2unix mirrors=[{'http://mirror': 'http://url/to/public/key}]
    """
    args = []
    # If we want to install packages
    if packages is not None:
        args.append('--packages {pkgs}'.format(pkgs=packages))
        # but we don't have cygwin installed yet
        if not _check_cygwin_installed(cyg_arch):
            # install just the base system
            _run_silent_cygwin(cyg_arch=cyg_arch)

    return _run_silent_cygwin(cyg_arch=cyg_arch, args=args, mirrors=mirrors)


def uninstall(packages,
              cyg_arch='x86_64',
              mirrors=None):
    """
    Uninstall one or several packages.

    packages
        The packages to uninstall.

    cyg_arch : x86_64
        Specify the architecture to remove the package from
        Current options are x86 and x86_64

    CLI Example:

    .. code-block:: bash

        salt '*' cyg.uninstall dos2unix
        salt '*' cyg.uninstall dos2unix mirrors=[{'http://mirror': 'http://url/to/public/key}]
    """
    args = []
    if packages is not None:
        args.append('--remove-packages {pkgs}'.format(pkgs=packages))
        LOG.debug('args: {0}'.format(args))
        if not _check_cygwin_installed(cyg_arch):
            LOG.debug('We\'re convinced cygwin isn\'t installed')
            return True

    return _run_silent_cygwin(cyg_arch=cyg_arch, args=args, mirrors=mirrors)


def update(cyg_arch='x86_64', mirrors=None):
    """
    Update all packages.

    cyg_arch : x86_64
        Specify the cygwin architecture update
        Current options are x86 and x86_64

    CLI Example:

    .. code-block:: bash

        salt '*' cyg.update
        salt '*' cyg.update dos2unix mirrors=[{'http://mirror': 'http://url/to/public/key}]
    """
    args = []
    args.append('--upgrade-also')

    # Can't update something that isn't installed
    if not _check_cygwin_installed(cyg_arch):
        LOG.debug('Cygwin ({0}) not installed,\
                  could not update'.format(cyg_arch))
        return False

    return _run_silent_cygwin(cyg_arch=cyg_arch, args=args, mirrors=mirrors)


def list_(package='', cyg_arch='x86_64'):
    """
    List locally installed packages.

    package : ''
        package name to check. else all

    cyg_arch :
        Cygwin architecture to use
        Options are x86 and x86_64

    CLI Example:

    .. code-block:: bash

        salt '*' cyg.list
    """
    pkgs = {}
    args = ' '.join(['-c', '-d', package])
    stdout = _cygcheck(args, cyg_arch=cyg_arch)
    lines = []
    if isinstance(stdout, six.string_types):
        lines = salt.utils.stringutils.to_unicode(stdout).splitlines()
    for line in lines:
        match = re.match(r'^([^ ]+) *([^ ]+)', line)
        if match:
            pkg = match.group(1)
            version = match.group(2)
            pkgs[pkg] = version
    return pkgs
