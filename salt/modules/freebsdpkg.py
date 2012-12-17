'''
Package support for FreeBSD
'''

# Import python libs
import logging

# Import python libs
import os
import salt.utils


log = logging.getLogger(__name__)


def _check_pkgng():
    '''
    Looks to see if pkgng is being used by checking if database exists
    '''
    return os.path.isfile('/var/db/pkg/local.sqlite')


@salt.utils.memoize
def _cmd(cmd):
    return salt.utils.which(cmd)


def search(pkg_name):
    '''
    Use `pkg search` if pkg is being used.

    CLI Example::

        salt '*' pkg.search 'mysql-server'
    '''
    if _check_pkgng():
        res = __salt__['cmd.run']('{0} search {1}'.format(_cmd('pkg'),
                                                          pkg_name
                                                          ))
        res = [x for x in res.splitlines()]
        return {"Results": res}


def __virtual__():
    '''
    Set the virtual pkg module if the os is Arch
    '''
    return 'pkg' if __grains__['os'] == 'FreeBSD' else False


def available_version(name):
    '''
    The available version of the package in the repository

    CLI Example::

        salt '*' pkg.available_version <package name>
    '''
    if _check_pkgng():
        for line in __salt__['cmd.run']('{0} search -f {1}'.format(
            _cmd('pkg'), name)
        ).splitlines():
            if line.startswith('Version'):
                fn, ver = line.split(':', 1)
                return ver.strip()
    return ''


def version(name):
    '''
    Returns a version if the package is installed, else returns an empty string

    CLI Example::

        salt '*' pkg.version <package name>
    '''
    return list_pkgs().get(name, '')


def refresh_db():
    '''
    Use pkg update to get latest repo.txz when using pkgng, else update the
    ports tree with portsnap otherwise. If the ports tree does not exist it
    will be downloaded and set up.

    CLI Example::

        salt '*' pkg.refresh_db
    '''
    if _check_pkgng():
        __salt__['cmd.run']('{0} update'.format(_cmd('pkg')))
    return {}


def list_pkgs():
    '''
    List the packages currently installed as a dict::

        {'<package_name>': '<version>'}

    CLI Example::

        salt '*' pkg.list_pkgs
    '''
    if _check_pkgng():
        pkg_command = '{0} info'.format(_cmd('pkg'))
    else:
        pkg_command = '{0}'.format(_cmd('pkg_info'))
    ret = {}
    for line in __salt__['cmd.run'](pkg_command).splitlines():
        if not line:
            continue
        pkg, ver = line.split(' ')[0].rsplit('-', 1)
        __salt__['pkg_resource.add_pkg'](ret, pkg, ver)
        __salt__['pkg_resource.sort_pkglist'](ret)
    return ret


def install(name=None, refresh=False, repo=None,
            pkgs=None, sources=None, **kwargs):
    '''
    Install the passed package

    name : None
        The name of the package to be installed.

    refresh : False
        Whether or not to refresh the package database before installing.

    repo : None
        Specify a package repository to install from.

    Multiple Package Installation Options:

    pkgs : None
        A list of packages to install from a software repository. Must be
        passed as a python list.

        CLI Example::

            salt '*' pkg.install pkgs='["foo","bar"]'

    sources : None
        A list of packages to install. Must be passed as a list of dicts,
        with the keys being package names, and the values being the source URI
        or local path to the package.

        CLI Example::

            salt '*' pkg.install sources='[{"foo": "salt://foo.deb"},{"bar": "salt://bar.deb"}]'

    Return a dict containing the new package names and versions::

        {'<package>': {'old': '<old-version>',
                   'new': '<new-version>']}

    CLI Example::

        salt '*' pkg.install <package name>
    '''
    pkg_params, pkg_type = __salt__['pkg_resource.parse_targets'](name,
                                                                  pkgs,
                                                                  sources)
    if not pkg_params:
        return {}

    env = []
    args = []
    if _check_pkgng():
        cmd = _cmd('pkg')
        if repo:
            env.append(('PACKAGESITE', repo))
    else:
        cmd = _cmd('pkg_add')
        if repo:
            env.append(('PACKAGEROOT', repo))

    if pkg_type == 'file':
        if _check_pkgng():
            env.append(('ASSUME_ALWAYS_YES', 'yes'))  # might be fixed later
            args.append('add')
    elif pkg_type == 'repository':
        if _check_pkgng():
            args.extend(('install', '-y'))  # Assume yes when asked
            if not refresh:
                args.append('-L')  # do not update repo db
        else:
            args.append('-r')  # use remote repo

    args.extend(pkg_params)

    old = list_pkgs()
    __salt__['cmd.run_all']('{0} {1}'.format(cmd, ' '.join(args)), env=env)
    new = list_pkgs()

    rehash()
    return __salt__['pkg_resource.find_changes'](old, new)


def upgrade():
    '''
    Run pkg upgrade, if pkgng used. Otherwise do nothing

    Return a dict containing the new package names and versions::

        {'<package>': {'old': '<old-version>',
                   'new': '<new-version>']}

    CLI Example::

        salt '*' pkg.upgrade
    '''

    if not _check_pkgng():
        # There is not easy way to upgrade packages with old package system
        return {}

    old = list_pkgs()
    __salt__['cmd.retcode']('{0} upgrade -y'.format(_cmd('pkg')))
    new = list_pkgs()
    return __salt__['pkg_resource.find_changes'](old, new)


def remove(name=None, pkgs=None):
    '''
    Remove a single package.

    name : None
        The name of the package to be deleted.

    pkgs : None
        A list of packages to delete. Must be passed as a python list.

        CLI Example::

            salt '*' pkg.remove pkgs='["foo","bar"]'

    Returns a list containing the removed packages.

    CLI Example::

        salt '*' pkg.remove <package name>
    '''
    pkg_params, pkg_type = __salt__['pkg_resource.parse_targets'](name,
                                                                  pkgs)
    if not pkg_params:
        return {}

    old = list_pkgs()
    args = []

    for p in pkg_params:
        ver = old.get(p, [])
        if not ver:
            continue
        if isinstance(ver, list):
            args.extend(['{0}-{1}'.format(p, v) for v in ver])
        else:
            args.append('{0}-{1}'.format(p, ver))

    if not args:
        return {}

    for_remove = ' '.join(args)

    if _check_pkgng():
        cmd = '{0} remove -y {1}'.format(_cmd('pkg'), for_remove)
    else:
        cmd = '{0} {1}'.format(_cmd('pkg_remove'), for_remove)

    __salt__['cmd.run_all'](cmd)

    new = list_pkgs()

    return __salt__['pkg_resource.find_changes'](old, new)


def purge(name):
    '''
    Remove a single package with pkg_delete

    Returns a list containing the removed packages.

    CLI Example::

        salt '*' pkg.purge <package name>
    '''
    return remove(name)


def rehash():
    '''
    Recomputes internal hash table for the PATH variable.
    Use whenever a new command is created during the current
    session.

    CLI Example::

        salt '*' pkg.rehash
    '''
    shell = __salt__['cmd.run']('echo $SHELL').split('/')
    if shell[len(shell) - 1] in ['csh', 'tcsh']:
        __salt__['cmd.run']('rehash')
