# -*- coding: utf-8 -*-
'''
Manage cygwin packages.
'''

# Import python libs
import re
from salt.exceptions import SaltInvocationError

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
    if __salt__['file.missing']('c:\\{cyg_dir}\\bin\\cygcheck.exe'.format(_get_cyg_dir(cyg_arch))):
        return False
    return True

def _run_silent_cygwin(cyg_arch='x86_64', args=None):
    '''
    Retrieves the correct setup.exe and runs it with the correct
    arguments to get the bare minumum cygwin installation up and running.
    '''
    cyg_cache_dir = 'c:\\cygcache'
    cyg_setup = 'setup-{0}.exe'.format(cyg_arch)
    cyg_setup_path = '{0}\\{1}'.format(cyg_cache_dir, cyg_setup)
    cyg_setup_source = 'http://cygwin.com/{0}'.format(cyg_setup)
    cyg_setup_source_hash = 'http://cygwin.com/{0}.sig'.format(cyg_setup)
    __salt__['file.managed'](
        cyg_setup_path,
        source=cyg_setup_source,
        source_hash=cyg_setup_source_hash,
        makedirs=True,
        showdiff=False,
        )
    setup_command = cyg_setup_path
    options = []
    options.append('--local-package-dir {0}'.format(cyg_cache_dir))
    # options.append('--site ftp://ftp.cygwinports.org/pub/cygwinports')
    # options.append('--pubkey http://cygwinports.org/ports.gpg')
    options.append('--site ftp://mirrors.kernel.org/sourceware/cygwin/')
    options.append('--no-desktop')
    options.append('--quiet-mode')
    options.append('--disable-buggy-antivirus')
    options.append(args)

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
    bashcmd = 'c:\\{0}\\bin\\bash --login -c'.format(_get_cyg_dir(cyg_arch))
    cygcheck = 'cygcheck {0}'.format(args)
    cmdline = ' '.join([bashcmd, cygcheck])

    ret = __salt__['cmd.run_all'](
        cmdline
        )

    if ret['retcode'] == 0:
        return ret['stdout']
    else:
        return False


def install(packages=None,           # pylint: disable=C0103
            cyg_arch='x86_64'):      # pylint: disable=C0103
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


def uninstall(packages,                # pylint: disable=C0103
              cyg_arch='x86_64'):      # pylint: disable=C0103
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
    args = []
    # If we want to install packages
    if packages is not None:
        args.append('--remove-packages {pkgs}'.format(pkgs=packages))
        # but we don't have cygwin installed yet
        if not _check_cygwin_installed(cyg_arch):
            # install just the base system
            _run_silent_cygwin(cyg_arch=cyg_arch)

    return _run_silent_cygwin(cyg_arch=cyg_arch, args=args)


def update(packages=None,           # pylint: disable=C0103
           cyg_arch='x86_64'):      # pylint: disable=C0103
    '''
    Update one or several gems.

    packages : None
        The packages to update. If None all packages.

    cyg_arch : x86_64
        Specify the architecture to remove the package from
        Current options are x86 and x86_64

    CLI Example:

    .. code-block:: bash

        salt '*' cyg.update dos2unix
    '''
    args = []
    args.append('--upgrade-also')
    # If we want to upgrade packages
    if packages is not None:
        args.append('--packages {pkgs}'.format(pkgs=packages))
        # but we don't have cygwin installed yet
        if not _check_cygwin_installed(cyg_arch):
            # install just the base system
            _run_silent_cygwin(cyg_arch=cyg_arch)

    return _run_silent_cygwin(cyg_arch=cyg_arch, args=args)

def list_(package='', cyg_arch='x86_64'):
    '''
    List locally installed packaes.

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
