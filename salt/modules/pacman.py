'''
A module to wrap pacman calls, since Arch is the best
(https://wiki.archlinux.org/index.php/Arch_is_the_best)
'''

# Import python libs
import copy
import logging
import re

# Import salt libs
import salt.utils

log = logging.getLogger(__name__)


def __virtual__():
    '''
    Set the virtual pkg module if the os is Arch
    '''
    return 'pkg' if __grains__['os'] in ('Arch', 'Arch ARM') else False


def _list_removed(old, new):
    '''
    List the packages which have been removed between the two package objects
    '''
    return [x for x in old if x not in new]


def latest_version(*names, **kwargs):
    '''
    Return the latest version of the named package available for upgrade or
    installation. If more than one package name is specified, a dict of
    name/version pairs is returned.

    If the latest version of a given package is already installed, an empty
    string will be returned for that package.

    CLI Example::

        salt '*' pkg.latest_version <package name>
        salt '*' pkg.latest_version <package1> <package2> <package3> ...
    '''
    if len(names) == 0:
        return ''
    refresh_db()
    ret = {}
    # Initialize the dict with empty strings
    for name in names:
        ret[name] = ''
    cmd = 'pacman -Sp --needed --print-format "%n %v" ' \
          '{0}'.format(' '.join(names))
    for line in __salt__['cmd.run_stdout'](cmd).splitlines():
        try:
            name, version_num = line.split()
            # Only add to return dict if package is in the list of packages
            # passed, otherwise dependencies will make their way into the
            # return data.
            if name in names:
                ret[name] = version_num
        except (ValueError, IndexError):
            pass

    # Return a string if only one package name passed
    if len(names) == 1:
        return ret[names[0]]
    return ret

# available_version is being deprecated
available_version = latest_version


def upgrade_available(name):
    '''
    Check whether or not an upgrade is available for a given package

    CLI Example::

        salt '*' pkg.upgrade_available <package name>
    '''
    return latest_version(name) != ''


def list_upgrades():
    '''
    List all available package upgrades on this system

    CLI Example::

        salt '*' pkg.list_upgrades
    '''
    upgrades = {}
    lines = __salt__['cmd.run'](
        'pacman -Sypu --print-format "%n %v" | egrep -v ' r'"^\s|^:"'
    ).splitlines()
    for line in lines:
        comps = line.split(' ')
        if len(comps) < 2:
            continue
        upgrades[comps[0]] = comps[1]
    return upgrades


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

    if 'pkg.list_pkgs' in __context__:
        if versions_as_list:
            return __context__['pkg.list_pkgs']
        else:
            ret = copy.deepcopy(__context__['pkg.list_pkgs'])
            __salt__['pkg_resource.stringify'](ret)
            return ret

    cmd = 'pacman -Q'
    ret = {}
    out = __salt__['cmd.run'](cmd).splitlines()
    for line in out:
        if not line:
            continue
        try:
            name, version_num = line.split()[0:2]
        except ValueError:
            log.error('Problem parsing pacman -Q: Unexpected formatting in '
                      'line: "{0}"'.format(line))
        else:
            __salt__['pkg_resource.add_pkg'](ret, name, version_num)

    __salt__['pkg_resource.sort_pkglist'](ret)
    __context__['pkg.list_pkgs'] = copy.deepcopy(ret)
    if not versions_as_list:
        __salt__['pkg_resource.stringify'](ret)
    return ret


def refresh_db():
    '''
    Just run a ``pacman -Sy``, return a dict::

        {'<database name>': Bool}

    CLI Example::

        salt '*' pkg.refresh_db
    '''
    cmd = 'LANG=C pacman -Sy'
    ret = {}
    out = __salt__['cmd.run'](cmd).splitlines()
    for line in out:
        if line.strip().startswith('::'):
            continue
        if not line:
            continue
        key = line.strip().split()[0]
        if 'is up to date' in line:
            ret[key] = False
        elif 'downloading' in line:
            key = line.strip().split()[1].split('.')[0]
            ret[key] = True
    return ret


def install(name=None,
            refresh=True,
            pkgs=None,
            sources=None,
            **kwargs):
    '''
    Install the passed package, add refresh=True to install with an -Sy.

    name
        The name of the package to be installed. Note that this parameter is
        ignored if either "pkgs" or "sources" is passed. Additionally, please
        note that this option can only be used to install packages from a
        software repository. To install a package file manually, use the
        "sources" option.

        CLI Example::
            salt '*' pkg.install <package name>

    refresh
        Whether or not to refresh the package database before installing.


    Multiple Package Installation Options:

    pkgs
        A list of packages to install from a software repository. Must be
        passed as a python list. A specific version number can be specified
        by using a single-element dict representing the package and its
        version. As with the ``version`` parameter above, comparison operators
        can be used to target a specific version of a package.

        CLI Examples::
            salt '*' pkg.install pkgs='["foo", "bar"]'
            salt '*' pkg.install pkgs='["foo", {"bar": "1.2.3-4"}]'
            salt '*' pkg.install pkgs='["foo", {"bar": "<1.2.3-4"}]'

    sources
        A list of packages to install. Must be passed as a list of dicts,
        with the keys being package names, and the values being the source URI
        or local path to the package.

        CLI Example::
            salt '*' pkg.install sources='[{"foo": "salt://foo.pkg.tar.xz"},{"bar": "salt://bar.pkg.tar.xz"}]'


    Returns a dict containing the new package names and versions::

        {'<package>': {'old': '<old-version>',
                       'new': '<new-version>'}}
    '''
    pkg_params, pkg_type = __salt__['pkg_resource.parse_targets'](name,
                                                                  pkgs,
                                                                  sources,
                                                                  **kwargs)
    if pkg_params is None or len(pkg_params) == 0:
        return {}

    version_num = kwargs.get('version')
    if version_num:
        if pkgs is None and sources is None:
            # Allow "version" to work for single package target
            pkg_params = {name: version_num}
        else:
            log.warning('"version" parameter will be ignored for multiple '
                        'package targets')

    if pkg_type == 'file':
        cmd = 'pacman -U --noprogressbar --noconfirm ' \
              '{0}'.format(' '.join(pkg_params))
        targets = pkg_params
    elif pkg_type == 'repository':
        targets = []
        problems = []
        for param, version_num in pkg_params.iteritems():
            if version_num is None:
                targets.append(param)
            else:
                match = re.match('^([<>])?(=)?([^<>=]+)$', version_num)
                if match:
                    gt_lt, eq, verstr = match.groups()
                    prefix = gt_lt or ''
                    prefix += eq or ''
                    # If no prefix characters were supplied, use '='
                    prefix = prefix or '='
                    targets.append('{0}{1}{2}'.format(param, prefix, verstr))
                else:
                    msg = 'Invalid version string "{0}" for package ' \
                          '"{1}"'.format(version_num, name)
                    problems.append(msg)
        if problems:
            for problem in problems:
                log.error(problem)
            return {}

        if salt.utils.is_true(refresh):
            cmd = 'pacman -Syu --noprogressbar --noconfirm ' \
                  '"{0}"'.format('" "'.join(targets))
        else:
            cmd = 'pacman -S --noprogressbar --noconfirm ' \
                  '"{0}"'.format('" "'.join(targets))

    old = list_pkgs()
    __salt__['cmd.run_all'](cmd)
    __context__.pop('pkg.list_pkgs', None)
    new = list_pkgs()
    return __salt__['pkg_resource.find_changes'](old, new)


def upgrade():
    '''
    Run a full system upgrade, a pacman -Syu

    Return a dict containing the new package names and versions::

        {'<package>': {'old': '<old-version>',
                       'new': '<new-version>'}}

    CLI Example::

        salt '*' pkg.upgrade
    '''
    old = list_pkgs()
    cmd = 'pacman -Syu --noprogressbar --noconfirm'
    __salt__['cmd.run_all'](cmd)
    __context__.pop('pkg.list_pkgs', None)
    new = list_pkgs()
    return __salt__['pkg_resource.find_changes'](old, new)


def _uninstall(action='remove', name=None, pkgs=None, **kwargs):
    '''
    remove and purge do identical things but with different pacman commands,
    this function performs the common logic.
    '''
    pkg_params = __salt__['pkg_resource.parse_targets'](name, pkgs)[0]
    old = list_pkgs()
    targets = [x for x in pkg_params if x in old]
    if not targets:
        return {}
    remove_arg = '-Rsc' if action == 'purge' else '-R'
    cmd = 'pacman {0} --noprogressbar --noconfirm {1}'.format(remove_arg,
                                                              ' '.join(targets))
    __salt__['cmd.run_all'](cmd)
    __context__.pop('pkg.list_pkgs', None)
    new = list_pkgs()
    return __salt__['pkg_resource.find_changes'](old, new)


def remove(name=None, pkgs=None, **kwargs):
    '''
    Remove packages with ``pacman -R``.

    name
        The name of the package to be deleted.


    Multiple Package Options:

    pkgs
        A list of packages to delete. Must be passed as a python list. The
        ``name`` parameter will be ignored if this option is passed.


    Returns a dict containing the changes.

    CLI Example::

        salt '*' pkg.remove <package name>
        salt '*' pkg.remove <package1>,<package2>,<package3>
        salt '*' pkg.remove pkgs='["foo", "bar"]'
    '''
    return _uninstall(action='remove', name=name, pkgs=pkgs)


def purge(name=None, pkgs=None, **kwargs):
    '''
    Recursively remove a package and all dependencies which were installed
    with it, this will call a ``pacman -Rsc``

    name
        The name of the package to be deleted.


    Multiple Package Options:

    pkgs
        A list of packages to delete. Must be passed as a python list. The
        ``name`` parameter will be ignored if this option is passed.


    Returns a dict containing the changes.

    CLI Example::

        salt '*' pkg.purge <package name>
        salt '*' pkg.purge <package1>,<package2>,<package3>
        salt '*' pkg.purge pkgs='["foo", "bar"]'
    '''
    return _uninstall(action='purge', name=name, pkgs=pkgs)


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
    errors = []
    ret = []
    cmd = 'pacman -Ql {0}'.format(' '.join(packages))
    for line in __salt__['cmd.run'](cmd).splitlines():
        if line.startswith('error'):
            errors.append(line)
        else:
            comps = line.split()
            ret.append(' '.join(comps[1:]))
    return {'errors': errors, 'files': ret}


def file_dict(*packages):
    '''
    List the files that belong to a package, grouped by package. Not
    specifying any packages will return a list of _every_ file on the system's
    package database (not generally recommended).

    CLI Examples::

        salt '*' pkg.file_list httpd
        salt '*' pkg.file_list httpd postfix
        salt '*' pkg.file_list
    '''
    errors = []
    ret = {}
    cmd = 'pacman -Ql {0}'.format(' '.join(packages))
    for line in __salt__['cmd.run'](cmd).splitlines():
        if line.startswith('error'):
            errors.append(line)
        else:
            comps = line.split()
            if not comps[0] in ret:
                ret[comps[0]] = []
            ret[comps[0]].append((' '.join(comps[1:])))
    return {'errors': errors, 'packages': ret}
