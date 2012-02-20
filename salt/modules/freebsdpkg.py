'''
Package support for FreeBSD
'''

import os


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


# FIXME: Unused argument 'name' (pylint is your friend)
def available_version(name):
    '''
    The available version of the package in the repository

    CLI Example::

        salt '*' pkg.available_version <package name>
    '''
    pass


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


def list_pkgs():
    '''
    List the packages currently installed as a dict::

        {'<package_name>': '<version>'}

    CLI Example::

        salt '*' pkg.list_pkgs
    '''
    ret = {}
    for line in __salt__['cmd.run']('pkg_info').split('\n'):
        if not line:
            continue
        comps = line.split(' ')[0].split('-')
        ret['-'.join(comps[0:-1])] = comps[-1]
    return ret


def refresh_db():
    '''
    Update the ports tree with portsnap. If the ports tree does not exist it
    will be downloaded and set up.

    CLI Example::

        salt '*' pkg.refresh_db
    '''
    __salt__['cmd.run']('portsnap fetch')
    if not os.path.isdir('/usr/ports'):
        __salt__['cmd.run']('portsnap extract')
    else:
        __salt__['cmd.run']('portsnap update')


def install(name, *args, **kwargs):
    '''
    Install the passed package

    Return a dict containing the new package names and versions::

        {'<package>': {'old': '<old-version>',
                   'new': '<new-version>']}

    CLI Example::

        salt '*' pkg.install <package name>
    '''
    old = list_pkgs()
    __salt__['cmd.retcode']('pkg_add -r {0}'.format(name))
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
    return pkgs


def upgrade():
    '''
    Run a full system upgrade, a ``freebsd-update fetch install``

    Return a dict containing the new package names and versions::

        {'<package>': {'old': '<old-version>',
                   'new': '<new-version>']}

    CLI Example::

        salt '*' pkg.upgrade
    '''
    old = list_pkgs()
    __salt__['cmd.retcode']('freebsd-update fetch install')
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
        __salt__['cmd.retcode']('pkg_delete {0}'.format(name))
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
