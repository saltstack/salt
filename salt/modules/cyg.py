# -*- coding: utf-8 -*-
'''
Manage cygwin packages.
'''

# Import python libs
import logging
import re
import os
import bz2
from urllib import urlopen
import salt.utils
from salt.exceptions import SaltInvocationError

LOG = logging.getLogger(__name__)

# Define the module's virtual name
__virtualname__ = 'cyg'


def __virtual__():
    '''
    Only works on Windows systems
    '''
    if salt.utils.is_windows():
        return __virtualname__
    return False

__func_alias__ = {
    'list_': 'list'
}


def _get_cyg_dir(cyg_arch='x86_64'):
    '''
    Returns the cygwin install directory based on the architecture
    '''
    if cyg_arch == 'x86_64':
        return 'cygwin64'
    elif cyg_arch == 'x86':
        return 'cygwin'

    raise SaltInvocationError(
        'Invalid architecture {arch}'.format(arch=cyg_arch))


def _check_cygwin_installed(cyg_arch='x86_64'):
    '''
    Returns True or False if the given architecture of cygwin is installed
    '''
    # Use the cygcheck executable to check install.
    # It is installed as part of the base package,
    # and we use it to check packages
    path_to_cygcheck = os.sep.join(['C:',
                                    _get_cyg_dir(cyg_arch),
                                    'bin', 'cygcheck.exe'])
    LOG.debug('Path to cygcheck.exe: {}'.format(path_to_cygcheck))
    if not os.path.exists(path_to_cygcheck):
        LOG.debug('Could not find cygcheck.exe')
        return False
    return True


def _get_all_packages(mirror="ftp://mirrors.kernel.org/sourceware/cygwin/",
                      cyg_arch='x86_64'):
    '''
    Returns the list of packages based on the mirror
    provided.
    '''
    if 'cyg.all_packages' not in __context__:
        __context__['cyg.all_packages'] = {}
    if mirror not in __context__['cyg.all_packages']:
        __context__['cyg.all_packages'][mirror] = []
    if not len(__context__['cyg.all_packages'][mirror]):
        pkg_source = '/'.join([mirror, cyg_arch, 'setup.bz2'])

        file_data = urlopen(pkg_source).read()
        file_lines = bz2.decompress(file_data
                                    ).decode('utf_8',
                                             errors='replace').splitlines()

        packages = [re.search('^@ ([^ ]+)', line).group(1) for
                    line in file_lines if re.match('^@ [^ ]+', line)]

        __context__['cyg.all_packages'][mirror] = packages

    return __context__['cyg.all_packages'][mirror]


def check_valid_package(package,
                        mirrors=None,
                        cyg_arch='x86_64'):
    '''
    Checks if the package is valid on the given mirrors
    '''
    if mirrors is None:
        mirrors = ['ftp://mirrors.kernel.org/sourceware/cygwin/']

    for mirror in mirrors:
        if package in _get_all_packages(mirror, cyg_arch):
            return True
    return False


def _run_silent_cygwin(cyg_arch='x86_64', args=None):
    '''
    Retrieves the correct setup.exe and runs it with the correct
    arguments to get the bare minumum cygwin installation up and running.
    '''
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

    file_data = urlopen(cyg_setup_source)
    open(cyg_setup_path, "wb").write(file_data.read())

    setup_command = cyg_setup_path
    options = []
    options.append('--local-package-dir {0}'.format(cyg_cache_dir))
    # options.append('--site ftp://ftp.cygwinports.org/pub/cygwinports/')
    # options.append('--pubkey http://cygwinports.org/ports.gpg')
    options.append('--site ftp://mirrors.kernel.org/sourceware/cygwin/')
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
    '''
    Runs the cygcheck executable
    '''
    bashcmd = ' '.join([
        os.sep.join(['c:', _get_cyg_dir(cyg_arch), 'bin', 'bash']),
        '--login', '-c'])
    cygcheck = '\'cygcheck {0}\''.format(args)
    cmdline = ' '.join([bashcmd, cygcheck])

    ret = __salt__['cmd.run_all'](
        cmdline
    )

    if ret['retcode'] == 0:
        return ret['stdout']
    else:
        return False


def install(packages=None,
            cyg_arch='x86_64'):
    '''
    Installs one or several packages.

    packages : None
        The packages to install

    cyg_arch : x86_64
        Specify the architecture to install the package under
        Current options are x86 and x86_64

    CLI Example:

    .. code-block:: bash

        salt '*' cyg.install dos2unix
    '''
    args = []
    # If we want to install packages
    if packages is not None:
        args.append('--packages {pkgs}'.format(pkgs=packages))
        # but we don't have cygwin installed yet
        if not _check_cygwin_installed(cyg_arch):
            # install just the base system
            _run_silent_cygwin(cyg_arch=cyg_arch)

    return _run_silent_cygwin(cyg_arch=cyg_arch, args=args)


def uninstall(packages,
              cyg_arch='x86_64'):
    '''
    Uninstall one or several packages.

    packages
        The packages to uninstall.

    cyg_arch : x86_64
        Specify the architecture to remove the package from
        Current options are x86 and x86_64

    CLI Example:

    .. code-block:: bash

        salt '*' cyg.uninstall dos2unix
    '''
    LOG.debug('Entered cyg.uninstall')
    args = []
    if packages is not None:
        LOG.debug('We have packages: {0}'.format(packages))
        args.append('--remove-packages {pkgs}'.format(pkgs=packages))
        LOG.debug('args: {0}'.format(args))
        if not _check_cygwin_installed(cyg_arch):
            LOG.debug('We\'re convinced cygwin isn\'t installed')
            return True

    return _run_silent_cygwin(cyg_arch=cyg_arch, args=args)


def update(cyg_arch='x86_64'):
    '''
    Update all packages.

    cyg_arch : x86_64
        Specify the cygwin architecture update
        Current options are x86 and x86_64

    CLI Example:

    .. code-block:: bash

        salt '*' cyg.update
    '''
    args = []
    args.append('--upgrade-also')

    # Can't update something that isn't installed
    if not _check_cygwin_installed(cyg_arch):
        LOG.debug('Cygwin ({}) not installed,\
                  could not update'.format(cyg_arch))
        return False

    return _run_silent_cygwin(cyg_arch=cyg_arch, args=args)


def list_(package='', cyg_arch='x86_64'):
    '''
    List locally installed packages.

    package : ''
        package name to check. else all

    cyg_arch :
        Cygwin architecture to use
        Options are x86 and x86_64

    CLI Example:

    .. code-block:: bash

        salt '*' cyg.list
    '''
    pkgs = {}
    args = ' '.join(['-c', '-d', package])
    stdout = _cygcheck(args, cyg_arch=cyg_arch)
    lines = []
    if isinstance(stdout, str):
        lines = stdout.splitlines()
    for line in lines:
        match = re.match(r'^([^ ]+) *([^ ]+)', line)
        if match:
            pkg = match.group(1)
            version = match.group(2)
            pkgs[pkg] = version
    return pkgs


# def sources_add(source_uri, ruby=None, runas=None):
#     '''
#     Add a gem source.

#     source_uri
#         The source URI to add.
#     ruby : None
#         If RVM or rbenv are installed, the ruby version and gemset to use.
#     runas : None
#         The user to run gem as.

#     CLI Example:

#     .. code-block:: bash

#         salt '*' gem.sources_add http://rubygems.org/
#     '''
#     return _gem('sources --add {source_uri}'.
#                 format(source_uri=source_uri), ruby, runas=runas)


# def sources_remove(source_uri, ruby=None, runas=None):
#     '''
#     Remove a gem source.

#     source_uri
#         The source URI to remove.
#     ruby : None
#         If RVM or rbenv are installed, the ruby version and gemset to use.
#     runas : None
#         The user to run gem as.

#     CLI Example:

#     .. code-block:: bash

#         salt '*' gem.sources_remove http://rubygems.org/
#     '''
#     return _gem('sources --remove {source_uri}'.
#                 format(source_uri=source_uri), ruby, runas=runas)


# def sources_list(ruby=None, runas=None):
#     '''
#     List the configured gem sources.

#     ruby : None
#         If RVM or rbenv are installed, the ruby version and gemset to use.
#     runas : None
#         The user to run gem as.

#     CLI Example:

#     .. code-block:: bash

#         salt '*' gem.sources_list
#     '''
#     ret = _gem('sources', ruby, runas=runas)
#     return [] if ret is False else ret.splitlines()[2:]
