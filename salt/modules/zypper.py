'''
Package support for openSUSE via the zypper package manager
'''

# Import Python libs
import logging
import os
import re

# Import Salt libs
import salt.utils

log = logging.getLogger(__name__)


def __virtual__():
    '''
    Set the virtual pkg module if the os is openSUSE
    '''
    if __grains__.get('os_family', '') != 'Suse':
        return False
    # Not all versions of Suse use zypper, check that it is available
    if not salt.utils.which('zypper'):
        return False
    return 'pkg'


def _list_removed(old, new):
    '''
    List the packages which have been removed between the two package objects
    '''
    pkgs = []
    for pkg in old:
        if pkg not in new:
            pkgs.append(pkg)
    return pkgs


def _parse_pkg_meta(path):
    '''
    Retrieve package name and version number from package metadata
    '''
    name = ''
    version = ''
    rel = ''
    result = __salt__['cmd.run_all']('rpm -qpi "{0}"'.format(path))
    if result['retcode'] == 0:
        for line in result['stdout'].splitlines():
            if not name:
                m = re.match('^Name\s*:\s*(\S+)', line)
                if m:
                    name = m.group(1)
                    continue
            if not version:
                m = re.match('^Version\s*:\s*(\S+)', line)
                if m:
                    version = m.group(1)
                    continue
            if not rel:
                m = re.match('^Release\s*:\s*(\S+)', line)
                if m:
                    version = m.group(1)
                    continue
    if rel:
        version += '-{0}'.format(rel)
    return name, version


def _available_versions():
    '''
    The available versions of packages
    '''
    cmd = 'zypper packages -i'
    ret = {}
    out = __salt__['cmd.run'](cmd).splitlines()
    for line in out:
        if not line:
            continue
        if '|' not in line:
            continue
        comps = []
        for comp in line.split('|'):
            comps.append(comp.strip())
        if comps[0] == 'v':
            ret[comps[2]] = comps[3]
    return ret


def available_version(name):
    '''
    Return the available version of a given package

    CLI Example::

        salt '*' pkg.available_version <package name>
    '''
    avail = _available_versions()
    return avail.get(name, '')


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
    cmd = 'rpm -qa --queryformat "%{NAME}_|-%{VERSION}_|-%{RELEASE}\n"'
    ret = {}
    for line in __salt__['cmd.run'](cmd).splitlines():
        name, version, rel = line.split('_|-')
        pkgver = version
        if rel: pkgver += '-{0}'.format(rel)
        ret[name] = pkgver
    return ret


def refresh_db():
    '''
    Just run a ``zypper refresh``, return a dict::

        {'<database name>': Bool}

    CLI Example::

        salt '*' pkg.refresh_db
    '''
    cmd = 'zypper refresh'
    ret = {}
    out = __salt__['cmd.run'](cmd).splitlines()
    for line in out:
        if not line:
            continue
        if line.strip().startswith('Repository'):
            key = line.split("'")[1].strip()
            if 'is up to date' in line:
                ret[key] = False
        elif line.strip().startswith('Building'):
            key = line.split("'")[1].strip()
            if 'done' in line:
                ret[key] = True
    return ret


def install(name=None, refresh=False, pkgs=None, sources=None, **kwargs):
    '''
    Install the passed package(s), add refresh=True to run 'zypper refresh'
    before package is installed.

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
        A list of RPM sources to use for installing the package(s) defined in
        pkgs. Must be passed as a list of dicts.

        CLI Example::
            salt '*' pkg.install sources='[{"foo": "salt://foo.rpm"},{"bar": "salt://bar.rpm"}]'


    Returns a dict containing the new package names and versions::

        {'<package>': {'old': '<old-version>',
                       'new': '<new-version>']}

    '''
    # Catch both boolean input from state and string input from CLI
    if refresh is True or refresh == 'True':
        refresh_db()

    if pkgs and sources:
        log.error('Only one of "pkgs" and "sources" can be used.')
        return {}
    elif pkgs:
        if name:
            log.warning('"name" parameter will be ignored in favor of "pkgs"')
        pkgs = __salt__['config.pack_pkgs'](pkgs)
        if not pkgs:
            return pkgs
        pkg_param = ' '.join(pkgs)
    elif sources:
        if name:
            log.warning('"name" parameter will be ignored in favor of '
                        '"sources"')
        sources = __salt__['config.pack_sources'](sources)
        if not sources:
            return sources

        srcinfo = []
        for pkg_name,pkg_src in sources.iteritems():
            if __salt__['config.valid_fileproto'](pkg_src):
                # Cached RPM from master
                srcinfo.append((pkg_name,
                                pkg_src,
                               __salt__['cp.cache_file'](pkg_src),
                               'remote'))
            else:
                # RPM file local to the minion
                srcinfo.append((pkg_name,pkg_src,pkg_src,'local'))

        # Check metadata to make sure the name passed matches the source
        problems = []
        for pkg_name,pkg_uri,pkg_path,pkg_type in srcinfo:
            pkgmeta_name,pkgmeta_version = _parse_pkg_meta(pkg_path)
            if not pkgmeta_name:
                if pkg_type == 'remote':
                    problems.append('Failed to cache {0}. Are you sure this '
                                    'path is correct?'.format(pkg_uri))
                elif pkg_type == 'local':
                    if not os.path.isfile(pkg_path):
                        problems.append('Package file {0} not found. Are '
                                        'you sure this path is '
                                        'correct?'.format(pkg_path))
                    else:
                        problems.append('Unable to parse package metadata for '
                                        '{0}'.format(pkg_path))
            elif pkg_name != pkgmeta_name:
                problems.append('Package file {0} (Name: {1}) does not '
                                'match the specified package name '
                                '({2})'.format(pkg_uri,pkgmeta_name,pkg_name))

        # If any problems are found in the caching or metadata parsing done in
        # the above for loop, log each problem and then return an empty dict.
        # Do not proceed to attempt package installation.
        if problems:
            for problem in problems: log.error(problem)
            return {}

        # srcinfo is a 4-tuple (pkg_name,pkg_uri,pkg_path,pkg_type), so grab
        # the path (3rd element of tuple).
        pkg_param = ' '.join([x[2] for x in srcinfo])

    elif name:
        pkg_param = name
    else:
        log.error('No package sources passed.')
        return {}


    pkgs = {}
    if pkg_param is not None:
        old = list_pkgs()
        cmd = 'zypper -n install -l {0}'.format(pkg_param)
        __salt__['cmd.retcode'](cmd)
        new = list_pkgs()
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
    Run a full system upgrade, a zypper upgrade

    Return a dict containing the new package names and versions::

        {'<package>': {'old': '<old-version>',
                   'new': '<new-version>']}

    CLI Example::

        salt '*' pkg.upgrade
    '''
    old = list_pkgs()
    cmd = 'zypper -n up -l'
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
    Remove a single package with ``zypper remove``

    Return a list containing the removed packages.

    CLI Example::

        salt '*' pkg.remove <package name>
    '''
    old = list_pkgs()
    cmd = 'zypper -n remove {0}'.format(name)
    __salt__['cmd.retcode'](cmd)
    new = list_pkgs()
    return _list_removed(old, new)


def purge(name):
    '''
    Recursively remove a package and all dependencies which were installed
    with it, this will call a ``zypper remove -u``

    Return a list containing the removed packages.

    CLI Example::

        salt '*' pkg.purge <package name>
    '''
    old = list_pkgs()
    cmd = 'zypper -n remove -u {0}'.format(name)
    __salt__['cmd.retcode'](cmd)
    new = list_pkgs()
    return _list_removed(old, new)
