import salt
from salt.modules.yumpkg import _compare_versions


def __virtual__():
    '''
    Confine this module to Mac OS with Homebrew.
    '''

    if salt.utils.which('brew') and __grains__['os'] == 'MacOS':
        return 'pkg'


def list_pkgs(*args):
    '''
    List the packages currently installed in a dict::

        {'<package_name>': '<version>'}

    CLI Example::

        salt '*' pkg.list_pkgs
    '''
    cmd = 'brew list --versions {0}'.format(' '.join(args))

    result_dict = {}

    for line in __salt__['cmd.run'](cmd).splitlines():
        (pkg, version) = line.split(' ')[0:2]
        result_dict[pkg] = version

    return result_dict


def version(name):
    '''
    Returns a version if the package is installed, else returns an empty string

    CLI Example::

        salt '*' pkg.version <package name>
    '''
    pkgs = list_pkgs(name)
    if name in pkgs:
        return pkgs[name]
    else:
        return ''


def remove(pkgs):
    '''
    Removes packages with ``brew uninstall``

    Return a list containing the removed packages:

    CLI Example::

        salt '*' pkg.remove <package,package,package>
    '''
    formulas = ' '.join(pkgs.split(','))
    cmd = '/usr/local/bin/brew uninstall {0}'.format(formulas)

    return __salt__['cmd.run'](cmd)


def install(pkgs):
    '''
    Install the passed package(s) with ``brew install``

    pkgs
        The names of the packages to be installed

    Return a dict containing the new package names and versions::

        {'<package>': {'old': '<old-version>',
                   'new': '<new-version>']}

    CLI Example::

        salt '*' pkg.install 'package package package'
    '''
    if ',' in pkgs:
        pkgs = pkgs.split(',')
    else:
        pkgs = pkgs.split(' ')

    old = list_pkgs(*pkgs)

    formulas = ' '.join(pkgs)
    user = __salt__['file.get_user']('/usr/local')
    cmd = '/usr/local/bin/brew install {0}'.format(formulas)
    __salt__['cmd.run'](cmd, runas=user)

    new = list_pkgs(*pkgs)

    return _compare_versions(old, new)


def list_upgrades():
    '''
    Check whether or not an upgrade is available for all packages

    CLI Example::

        salt '*' pkg.list_upgrades
    '''
    cmd = '/usr/local/bin/brew outdated'

    return __salt__['cmd.run'](cmd).splitlines()


def upgrade_available(pkg):
    '''
    Check whether or not an upgrade is available for a given package

    CLI Example::

        salt '*' pkg.upgrade_available <package name>
    '''
    return pkg in list_upgrades()
