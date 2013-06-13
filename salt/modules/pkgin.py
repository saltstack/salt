'''
Package support for pkgin based systems, inspired from freebsdpkg.py
'''

# Import python libs
import logging

# Import salt libs
import salt.utils


log = logging.getLogger(__name__)

@salt.utils.memoize
def _check_pkgin():
    '''
    Looks to see if pkgin is present on the system, return full path
    '''
    return salt.utils.which('pkgin')


def __virtual__():
    '''
    Set the virtual pkg module if the os is supported by pkgin
    '''
    supported = ['NetBSD', 'SunOS', 'DragonFly', 'Minix', 'Darwin']

    if __grains__['os'] in supported and _check_pkgin():
        return 'pkg'

    return False


def _splitpkg(name):
    # name is in the format foobar-1.0nb1, already space-splitted
    if name[0].isalnum() and name != 'No': # avoid < > = and 'No result'
        return name.rsplit('-', 1)


def search(pkg_name):
    '''
    Searches for an exact match using pkgin ^package$

    CLI Example::

        salt '*' pkg.search 'mysql-server'
    '''

    pkglist = {}
    pkgin = _check_pkgin()

    if pkgin:
        for p in __salt__['cmd.run']('{0} se ^{1}$'.format(pkgin, pkg_name)
                                     ).splitlines():
            if p:
                s = _splitpkg(p.split()[0])
                if s:
                    pkglist[s[0]] = s[1]

        return pkglist


def latest_version(*names, **kwargs):
    '''
    Return the latest version of the named package available for upgrade or
    installation.

    If the latest version of a given package is already installed, an empty
    string will be returned for that package.

    CLI Example::

        salt '*' pkg.latest_version <package name>
        salt '*' pkg.latest_version <package1> <package2> ...
    '''

    pkglist = {}
    pkgin = _check_pkgin()

    for name in names:
        if pkgin:
            for line in __salt__['cmd.run']('{0} se ^{1}$'.format(pkgin, name)
                                           ).splitlines():
                p = line.split() # pkgname-version status
                if p:
                    s = _splitpkg(p[0])
                    if s:
                        if len(p) > 1 and p[1] == '<':
                            pkglist[s[0]] = s[1]
                        else:
                            pkglist[s[0]] = ''

    if len(names) == 1 and pkglist:
        return pkglist[names[0]]

    return pkglist


# available_version is being deprecated
available_version = latest_version


def version(*names, **kwargs):
    '''
    Returns a string representing the package version or an empty string if not
    installed. If more than one package name is specified, a dict of
    name/version pairs is returned.

    CLI Example::

        salt '*' pkg.version <package name>
        salt '*' pkg.version <package1> <package2> <package3> ...
    '''
    return __salt__['pkg_resource.version'](*names, **kwargs)


def refresh_db():
    '''
    Use pkg update to get latest pkg_summary

    CLI Example::

        salt '*' pkg.refresh_db
    '''

    pkgin = _check_pkgin()

    if pkgin:
        __salt__['cmd.run']('{0} up'.format(pkgin))

    return {}


def list_pkgs(versions_as_list=False, **kwargs):
    '''
    List the packages currently installed as a dict::

        {'<package_name>': '<version>'}

    CLI Example::

        salt '*' pkg.list_pkgs
    '''
    versions_as_list = salt.utils.is_true(versions_as_list)
    # 'removed' not yet implemented or not applicable
    if salt.utils.is_true(kwargs.get('removed')):
        return {}

    pkgin = _check_pkgin()
    if pkgin:
        pkg_command = '{0} ls'.format(pkgin)
    else:
        pkg_command = 'pkg_info'

    ret = {}

    for line in __salt__['cmd.run'](pkg_command).splitlines():
        if not line:
            continue
        pkg, ver = line.split(' ')[0].rsplit('-', 1)
        __salt__['pkg_resource.add_pkg'](ret, pkg, ver)

    __salt__['pkg_resource.sort_pkglist'](ret)
    if not versions_as_list:
        __salt__['pkg_resource.stringify'](ret)
    return ret


def install(name=None, refresh=False, fromrepo=None,
            pkgs=None, sources=None, **kwargs):
    '''
    Install the passed package

    name
        The name of the package to be installed.

    refresh
        Whether or not to refresh the package database before installing.

    fromrepo
        Specify a package repository to install from.


    Multiple Package Installation Options:

    pkgs
        A list of packages to install from a software repository. Must be
        passed as a python list.

        CLI Example::

            salt '*' pkg.install pkgs='["foo","bar"]'

    sources
        A list of packages to install. Must be passed as a list of dicts,
        with the keys being package names, and the values being the source URI
        or local path to the package.

        CLI Example::

            salt '*' pkg.install sources='[{"foo": "salt://foo.deb"},{"bar": "salt://bar.deb"}]'

    Return a dict containing the new package names and versions::

        {'<package>': {'old': '<old-version>',
                       'new': '<new-version>'}}

    CLI Example::

        salt '*' pkg.install <package name>
    '''
    pkg_params, pkg_type = __salt__['pkg_resource.parse_targets'](name,
                                                                  pkgs,
                                                                  sources,
                                                                  **kwargs)

    # Support old "repo" argument
    repo = kwargs.get('repo', '')
    if not fromrepo and repo:
        fromrepo = repo

    if not pkg_params:
        return {}

    env = []
    args = []
    pkgin = _check_pkgin()
    if pkgin:
        cmd = pkgin
        if fromrepo:
            log.info('Setting PKG_REPOS={0}'.format(fromrepo))
            env.append(('PKG_REPOS', fromrepo))
    else:
        cmd = 'pkg_add'
        if fromrepo:
            log.info('Setting PKG_PATH={0}'.format(fromrepo))
            env.append(('PKG_PATH', fromrepo))

    if pkg_type == 'file':
        cmd = 'pkg_add'
    elif pkg_type == 'repository':
        if pkgin:
            if refresh:
                args.append('-f')  # update repo db
            args.extend(('-y', 'in'))  # Assume yes when asked

    args.extend(pkg_params)

    old = list_pkgs()
    __salt__['cmd.run_all']('{0} {1}'.format(cmd, ' '.join(args)), env=env)
    new = list_pkgs()

    rehash()
    return __salt__['pkg_resource.find_changes'](old, new)


def upgrade():
    '''
    Run pkg upgrade, if pkgin used. Otherwise do nothing

    Return a dict containing the new package names and versions::

        {'<package>': {'old': '<old-version>',
                       'new': '<new-version>'}}

    CLI Example::

        salt '*' pkg.upgrade
    '''

    pkgin = _check_pkgin()
    if not pkgin:
        # There is not easy way to upgrade packages with old package system
        return {}

    old = list_pkgs()
    __salt__['cmd.retcode']('{0} -y fug'.format(pkgin))
    new = list_pkgs()
    return __salt__['pkg_resource.find_changes'](old, new)


def remove(name=None, pkgs=None, **kwargs):
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

    for param in pkg_params:
        ver = old.get(param, [])
        if not ver:
            continue
        if isinstance(ver, list):
            args.extend(['{0}-{1}'.format(param, v) for v in ver])
        else:
            args.append('{0}-{1}'.format(param, ver))

    if not args:
        return {}

    for_remove = ' '.join(args)

    pkgin = _check_pkgin()
    if pkgin:
        cmd = '{0} -y remove {1}'.format(pkgin, for_remove)
    else:
        cmd = 'pkg_remove {0}'.format(for_remove)

    __salt__['cmd.run_all'](cmd)

    new = list_pkgs()

    return __salt__['pkg_resource.find_changes'](old, new)


def purge(name, **kwargs):
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


def perform_cmp(pkg1='', pkg2=''):
    '''
    Do a cmp-style comparison on two packages. Return -1 if pkg1 < pkg2, 0 if
    pkg1 == pkg2, and 1 if pkg1 > pkg2. Return None if there was a problem
    making the comparison.

    CLI Example::

        salt '*' pkg.perform_cmp '0.2.4-0' '0.2.4.1-0'
        salt '*' pkg.perform_cmp pkg1='0.2.4-0' pkg2='0.2.4.1-0'
    '''
    return __salt__['pkg_resource.perform_cmp'](pkg1=pkg1, pkg2=pkg2)


def compare(pkg1='', oper='==', pkg2=''):
    '''
    Compare two version strings.

    CLI Example::

        salt '*' pkg.compare '0.2.4-0' '<' '0.2.4.1-0'
        salt '*' pkg.compare pkg1='0.2.4-0' oper='<' pkg2='0.2.4.1-0'
    '''
    return __salt__['pkg_resource.compare'](pkg1=pkg1, oper=oper, pkg2=pkg2)


def file_list(package):
    '''
    List the files that belong to a package.

    CLI Examples::

        salt '*' pkg.file_list nginx
    '''
    ret = file_dict(package)
    files = []
    for pkg_files in ret['files'].values():
        files.extend(pkg_files)
    ret['files'] = files
    return ret


def file_dict(package):
    '''
    List the files that belong to a package.

    CLI Examples::

        salt '*' pkg.file_list nginx
    '''
    errors = []
    files = {}
    files[package] = None

    cmd = 'pkg_info -qL {0}'.format(package)
    ret = __salt__['cmd.run_all'](cmd)

    for line in ret['stderr'].splitlines():
        errors.append(line)

    for line in ret['stdout'].splitlines():
        if line.startswith('/'):
            if files[package] is None:
                files[package] = [line]
            else:
                files[package].append(line)
        else:
            continue  # unexpected string

    print files
    return {'errors': errors, 'files': files}

# vim: tabstop=4 expandtab shiftwidth=4 softtabstop=4
