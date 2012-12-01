'''
Package support for FreeBSD
'''

# Import python libs
import os
import salt.utils


def _check_pkgng():
    '''
    Looks to see if pkgng is being used by checking if database exists
    '''
    if os.path.isfile('/var/db/pkg/local.sqlite'):
        return True
    return False


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


def _list_removed(old, new):
    '''
    List the packages which have been removed between the two package objects
    '''
    pkgs = []
    for pkg in old:
        if pkg not in new:
            pkgs.append(pkg)
    return pkgs


def available_version(name):
    '''
    The available version of the package in the repository

    CLI Example::

        salt '*' pkg.available_version <package name>
    '''
    if _check_pkgng():
        cmd = '{0} search -f {1}'.format(_cmd('pkg'), name)
        for line in __salt__['cmd.run'](cmd).splitlines():
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
    pkgs = list_pkgs()
    if name in pkgs:
        return pkgs[name]
    else:
        return ''


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
    else:
        __salt__['cmd.run']('{0} fetch'.format(_cmd('portsnap')))
        if not os.path.isdir('/usr/ports'):
            __salt__['cmd.run']('{0} extract'.format(_cmd('portsnap')))
        else:
            __salt__['cmd.run']('{0} update'.format(_cmd('portsnap')))
    return {}


def list_pkgs():
    '''
    List the packages currently installed as a dict::

        {'<package_name>': '<version>'}

    CLI Example::

        salt '*' pkg.list_pkgs
    '''
    if _check_pkgng():
        pkg_command = '{0} info'.format(_cmd(pkg))
    else:
        pkg_command = '{0}'.format(_cmd('pkg_info'))
    ret = {}
    for line in __salt__['cmd.run'](pkg_command).splitlines():
        if not line:
            continue
        comps = line.split(' ')[0].split('-')
        ret['-'.join(comps[0:-1])] = comps[-1]
    return ret


def install(name, refresh=False, repo='', **kwargs):
    '''
    Install the passed package

    Return a dict containing the new package names and versions::

        {'<package>': {'old': '<old-version>',
                   'new': '<new-version>']}

    CLI Example::

        salt '*' pkg.install <package name>
    '''
    env = ()
    if _check_pkgng():
        pkg_command = '{0} install -y'.format(_cmd('pkg'))
        if not refresh:
            pkg_command += ' -L'
        if repo:
            env = (('PACKAGESITE', repo),)
    else:
        pkg_command = '{0} -r'.format(_cmd('pkg_add'))
        if repo:
            env = (('PACKAGEROOT', repo),)
    old = list_pkgs()
    __salt__['cmd.retcode']('{0} {1}'.format(pkg_command, name), env=env)
    new = list_pkgs()
    pkgs = {}
    for npkg in new:
        if npkg in old:
            if old[npkg] == new[npkg]:
                # no change in the package
                continue
            else:
                # the package was here before and the version has changed
                pkgs[npkg] = {'old': old[npkg],
                              'new': new[npkg]}
        else:
            # the package is freshly installed
            pkgs[npkg] = {'old': '',
                          'new': new[npkg]}
    rehash()
    return pkgs


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
    pkgs = {}
    for npkg in new:
        if npkg in old:
            if old[npkg] == new[npkg]:
                # no change in the package
                continue
            else:
                # the package was here before and the version has changed
                pkgs[npkg] = {'old': old[npkg],
                              'new': new[npkg]}
        else:
            # the package is freshly installed
            pkgs[npkg] = {'old': '',
                          'new': new[npkg]}
    rehash()
    return pkgs


def remove(name):
    '''
    Remove a single package with pkg_delete

    Returns a list containing the removed packages.

    CLI Example::

        salt '*' pkg.remove <package name>
    '''
    old = list_pkgs()
    if name in old:
        name = '{0}-{1}'.format(name, old[name])
        if _check_pkgng():
            pkg_command = '{0} delete -y'.format(_cmd('pkg'))
        else:
            pkg_command - '{0}'.format(_cmd('pkg_delete'))
        __salt__['cmd.retcode']('{0} {1}'.format(pkg_command, name))
    new = list_pkgs()
    return _list_removed(old, new)


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
