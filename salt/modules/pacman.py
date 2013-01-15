'''
A module to wrap pacman calls, since Arch is the best
(https://wiki.archlinux.org/index.php/Arch_is_the_best)
'''

# Import python libs
import logging

log = logging.getLogger(__name__)


def __virtual__():
    '''
    Set the virtual pkg module if the os is Arch
    '''
    return 'pkg' if __grains__['os'] == 'Arch' else False


def _list_removed(old, new):
    '''
    List the packages which have been removed between the two package objects
    '''
    pkgs = []
    for pkg in old:
        if pkg not in new:
            pkgs.append(pkg)
    return pkgs


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
            name, version = line.split()
            # Only add to return dict if package is in the list of packages
            # passed, otherwise dependencies will make their way into the
            # return data.
            if name in names:
                ret[name] = version
        except (ValueError, IndexError):
            pass

    # Return a string if only one package name passed
    if len(names) == 1:
        return ret[names[0]]
    return ret


def upgrade_available(name):
    '''
    Check whether or not an upgrade is available for a given package

    CLI Example::

        salt '*' pkg.upgrade_available <package name>
    '''
    return available_version(name) != ''


def list_upgrades():
    '''
    List all available package upgrades on this system

    CLI Example::

        salt '*' pkg.list_upgrades
    '''
    upgrades = {}
    lines = __salt__['cmd.run'](
            'pacman -Sypu --print-format "%n %v" | egrep -v "^\s|^:"'
            ).splitlines()
    for line in lines:
        comps = line.split(' ')
        if len(comps) < 2:
            continue
        upgrades[comps[0]] = comps[1]
    return upgrades


def version(*names):
    '''
    Returns a string representing the package version or an empty string if not
    installed. If more than one package name is specified, a dict of
    name/version pairs is returned.

    CLI Example::

        salt '*' pkg.version <package name>
        salt '*' pkg.version <package1> <package2> <package3> ...
    '''
    pkgs = list_pkgs()
    if len(names) == 0:
        return ''
    elif len(names) == 1:
        return pkgs.get(names[0], '')
    else:
        ret = {}
        for name in names:
            ret[name] = pkgs.get(name, '')
        return ret


def list_pkgs():
    '''
    List the packages currently installed as a dict::

        {'<package_name>': '<version>'}

    CLI Example::

        salt '*' pkg.list_pkgs
    '''
    cmd = 'pacman -Q'
    ret = {}
    out = __salt__['cmd.run'](cmd).splitlines()
    for line in out:
        if not line:
            continue
        try:
            name, version = line.split()[0:2]
        except ValueError:
            log.error('Problem parsing pacman -Q: Unexpected formatting in '
                      'line: "{0}"'.format(line))
        else:
            __salt__['pkg_resource.add_pkg'](ret, name, version)
    __salt__['pkg_resource.sort_pkglist'](ret)
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


def install(name=None, refresh=False, pkgs=None, sources=None, **kwargs):
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
        passed as a python list.

        CLI Example::
            salt '*' pkg.install pkgs='["foo","bar"]'

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
                                                                  sources)
    if pkg_params is None or len(pkg_params) == 0:
        return {}
    elif pkg_type == 'file':
        cmd = 'pacman -U --noprogressbar --noconfirm ' \
              '{0}'.format(' '.join(pkg_params))
    elif pkg_type == 'repository':
        fname = ' '.join(pkg_params)
        if len(pkg_params) == 1:
            for vkey, vsign in (('gt', '>'), ('lt', '<'),
                                ('eq', '='), ('version', '=')):
                if kwargs.get(vkey) is not None:
                    fname = '"{0}{1}{2}"'.format(fname, vsign, kwargs[vkey])
                    break
        # Catch both boolean input from state and string input from CLI
        if refresh is True or refresh == 'True':
            cmd = 'pacman -Syu --noprogressbar --noconfirm {0}'.format(fname)
        else:
            cmd = 'pacman -S --noprogressbar --noconfirm {0}'.format(fname)

    old = list_pkgs()
    stderr = __salt__['cmd.run_all'](cmd).get('stderr', '')
    if stderr:
        log.error(stderr)
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
    cmd = 'pacman -Syu --noprogressbar --noconfirm '
    __salt__['cmd.retcode'](cmd)
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
    Remove a single package with ``pacman -R``

    Return a list containing the removed packages.

    CLI Example::

        salt '*' pkg.remove <package name>
    '''
    old = list_pkgs()
    cmd = 'pacman -R --noprogressbar --noconfirm {0}'.format(name)
    __salt__['cmd.retcode'](cmd)
    new = list_pkgs()
    return _list_removed(old, new)


def purge(name):
    '''
    Recursively remove a package and all dependencies which were installed
    with it, this will call a ``pacman -Rsc``

    Return a list containing the removed packages.

    CLI Example::

        salt '*' pkg.purge <package name>
    '''
    old = list_pkgs()
    cmd = 'pacman -R --noprogressbar --noconfirm {0}'.format(name)
    __salt__['cmd.retcode'](cmd)
    new = list_pkgs()
    return _list_removed(old, new)


def compare(version1='', version2=''):
    '''
    Compare two version strings. Return -1 if version1 < version2,
    0 if version1 == version2, and 1 if version1 > version2. Return None if
    there was a problem making the comparison.

    CLI Example::

        salt '*' pkg.compare '0.2.4-0' '0.2.4.1-0'
    '''
    return __salt__['pkg_resource.compare'](version1, version2)
