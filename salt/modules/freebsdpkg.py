'''
Package support for FreeBSD
'''

# Import python libs
import logging

# Import python libs
import os
import salt.utils


log = logging.getLogger(__name__)


def __virtual__():
    '''
    Set the virtual pkg module if the os is FreeBSD
    '''
    return 'pkg' if __grains__['os'] == 'FreeBSD' else False


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


def available_version(*names):
    '''
    Return the latest version of the named package available for upgrade or
    installation. If more than one package name is specified, a dict of
    name/version pairs is returned.

    If the latest version of a given package is already installed, an empty
    string will be returned for that package.

    CLI Example::

        salt '*' pkg.available_version <package name>
        salt '*' pkg.available_version <package1> <package2> <package3> ...
    '''

    ret = {}

    if _check_pkgng():
        for line in __salt__['cmd.run_stdout']('{0} upgrade -nq'.format(
            _cmd('pkg'))
        ).splitlines():
            if not line.startswith('\t'):
                continue
            line = line.strip()
            if line.startswith('Installing'):
                _, pkg, ver = line.split()
                pkg = pkg.rstrip(':')
            elif line.startswith('Upgrading'):
                _, pkg, _, _, ver = line.split()
                pkg = pkg.rstrip(':')
            elif line.startswith('Reinstalling'):
                _, pkgver = line.split()
                comps = pkgver.split('-')
                pkg = ''.join(comps[:-1])
                ver = comps[-1]
            else:
                # unexpected string
                continue
            if pkg in names:
                ret[pkg] = ver

        # keep pkg.latest culm
        for pkg in set(names) - set(ret) - set(list_pkgs()):
            for line in __salt__['cmd.run']('{0} search -fe {1}'.format(
                _cmd('pkg'), pkg)
            ).splitlines():
                if line.startswith('Version'):
                    _, _, ver = line.split()[:3]
                    ret[pkg] = ver
                    break

    ret.update(dict.fromkeys(set(names) - set(ret), ''))

    if len(names) == 1:
        return ret.values()[0]

    return ret


def version(*names):
    '''
    Returns a string representing the package version or an empty string if not
    installed. If more than one package name is specified, a dict of
    name/version pairs is returned.

    CLI Example::

        salt '*' pkg.version <package name>
        salt '*' pkg.version <package1> <package2> <package3> ...
    '''
    if not names:
        return ''

    ret = {}
    installed = list_pkgs()
    for name in names:
        ret[name] = installed.get(name, '')

    if len(names) == 1:
        return ret[names[0]]
    else:
        return ret


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
                                                                  sources)

    # Support old "repo" argument
    repo = kwargs.get('repo', '')
    if not fromrepo and repo:
        fromrepo = repo

    if not pkg_params:
        return {}

    env = []
    args = []
    if _check_pkgng():
        cmd = _cmd('pkg')
        if fromrepo:
            log.info('Setting PACKAGESITE={0}'.format(fromrepo))
            env.append(('PACKAGESITE', fromrepo))
    else:
        cmd = _cmd('pkg_add')
        if fromrepo:
            log.info('Setting PACKAGEROOT={0}'.format(fromrepo))
            env.append(('PACKAGEROOT', fromrepo))

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
                       'new': '<new-version>'}}

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

    if _check_pkgng():
        cmd = '{0} remove -y {1}'.format(_cmd('pkg'), for_remove)
    else:
        cmd = '{0} {1}'.format(_cmd('pkg_remove'), for_remove)

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


def file_list(*packages):
    '''
    List the files that belong to a package. Not specifying any packages will
    return a list of _every_ file on the system's package database (not
    generally recommended).

    CLI Examples::

        salt '*' pkg.file_list httpd
        salt '*' pkg.file_list httpd postfix
        salt '*' pkg.file_list
    '''
    ret = file_dict(*packages)
    files = []
    for pkg, its_files in ret['files'].items():
        files.extend(its_files)
    ret['files'] = files
    return ret


def file_dict(*packages):
    '''
    List the files that belong to a package, grouped by package. Not
    specifying any packages will return a list of _every_ file on the
    system's package database (not generally recommended).

    CLI Examples::

        salt '*' pkg.file_list httpd
        salt '*' pkg.file_list httpd postfix
        salt '*' pkg.file_list
    '''
    errors = []
    files = {}

    if _check_pkgng():
        if packages:
            match_pattern = '%n ~ {0}'
            matches = [match_pattern.format(p) for p in packages]

            cmd = '{0} query -e \'{1}\' \'%n %Fp\''.format(
                _cmd('pkg'), ' || '.join(matches))
        else:
            cmd = '{0} query -a \'%n %Fp\''.format(_cmd('pkg'))

        for line in __salt__['cmd.run_stdout'](cmd).splitlines():
            pkg, fn = line.split(' ', 1)
            if pkg not in files:
                files[pkg] = []
            files[pkg].append(fn)
    else:
        if packages:
            match_pattern = '\'{0}-[0-9]*\''
            matches = [match_pattern.format(p) for p in packages]

            cmd = '{0} -QL {1}'.format(_cmd('pkg_info'), ' '.join(matches))
        else:
            cmd = '{0} -QLa'.format(_cmd('pkg_info'))

        ret = __salt__['cmd.run_all'](cmd)

        for line in ret['stderr'].splitlines():
            errors.append(line)

        pkg = None
        for line in ret['stdout'].splitlines():
            if pkg is not None and line.startswith('/'):
                files[pkg].append(line)
            elif ':/' in line:
                pkg, fn = line.split(':', 1)
                pkg, ver = pkg.rsplit('-', 1)
                files[pkg] = [fn]
            else:
                continue  # unexpected string
    return {'errors': errors, 'files': files}
