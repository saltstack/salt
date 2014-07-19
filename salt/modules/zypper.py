# -*- coding: utf-8 -*-
'''
Package support for openSUSE via the zypper package manager
'''

# Import python libs
import copy
import logging
import re
from contextlib import contextmanager as _contextmanager

# Import salt libs
import salt.utils
from salt.utils.decorators import depends as _depends
from salt.exceptions import (
    CommandExecutionError, MinionError, SaltInvocationError)

log = logging.getLogger(__name__)

HAS_ZYPP = False

try:
    import zypp
    HAS_ZYPP = True
except ImportError:
    pass

# Define the module's virtual name
__virtualname__ = 'pkg'


def __virtual__():
    '''
    Set the virtual pkg module if the os is openSUSE
    '''
    if not HAS_ZYPP:
        return False
    if __grains__.get('os_family', '') != 'Suse':
        return False
    # Not all versions of Suse use zypper, check that it is available
    if not salt.utils.which('zypper'):
        return False
    return __virtualname__


def list_upgrades(refresh=True):
    '''
    List all available package upgrades on this system

    CLI Example:

    .. code-block:: bash

        salt '*' pkg.list_upgrades
    '''
    if salt.utils.is_true(refresh):
        refresh_db()
    ret = {}
    out = __salt__['cmd.run_stdout'](
        'zypper list-updates', output_loglevel='trace'
    )
    for line in out.splitlines():
        if not line:
            continue
        if '|' not in line:
            continue
        try:
            status, repo, name, cur, avail, arch = \
                [x.strip() for x in line.split('|')]
        except (ValueError, IndexError):
            continue
        if status == 'v':
            ret[name] = avail
    return ret

# Provide a list_updates function for those used to using zypper list-updates
list_updates = list_upgrades


def latest_version(*names, **kwargs):
    '''
    Return the latest version of the named package available for upgrade or
    installation. If more than one package name is specified, a dict of
    name/version pairs is returned.

    If the latest version of a given package is already installed, an empty
    string will be returned for that package.

    CLI Example:

    .. code-block:: bash

        salt '*' pkg.latest_version <package name>
        salt '*' pkg.latest_version <package1> <package2> <package3> ...
    '''
    refresh = salt.utils.is_true(kwargs.pop('refresh', True))

    if len(names) == 0:
        return ''

    ret = {}
    for name in names:
        ret[name] = ''

    # Refresh before looking for the latest version available
    if refresh:
        refresh_db()

    restpackages = names
    outputs = []
    # Split call to zypper into batches of 500 packages
    while restpackages:
        cmd = 'zypper info -t package {0}'.format(' '.join(restpackages[:500]))
        output = __salt__['cmd.run_stdout'](cmd, output_loglevel='trace')
        outputs.extend(re.split('Information for package \\S+:\n', output))
        restpackages = restpackages[500:]
    for package in outputs:
        pkginfo = {}
        for line in package.splitlines():
            try:
                key, val = line.split(':', 1)
                key = key.lower()
                val = val.strip()
            except ValueError:
                continue
            else:
                pkginfo[key] = val

        # Ignore if the needed keys weren't found in this iteration
        if not set(('name', 'version', 'status')) <= set(pkginfo.keys()):
            continue

        status = pkginfo['status'].lower()
        if 'not installed' in status or 'out-of-date' in status:
            ret[pkginfo['name']] = pkginfo['version']

    # Return a string if only one package name passed
    if len(names) == 1:
        return ret[names[0]]
    return ret

# available_version is being deprecated
available_version = latest_version


def upgrade_available(name):
    '''
    Check whether or not an upgrade is available for a given package

    CLI Example:

    .. code-block:: bash

        salt '*' pkg.upgrade_available <package name>
    '''
    return latest_version(name) != ''


def version(*names, **kwargs):
    '''
    Returns a string representing the package version or an empty string if not
    installed. If more than one package name is specified, a dict of
    name/version pairs is returned.

    CLI Example:

    .. code-block:: bash

        salt '*' pkg.version <package name>
        salt '*' pkg.version <package1> <package2> <package3> ...
    '''
    return __salt__['pkg_resource.version'](*names, **kwargs)


def list_pkgs(versions_as_list=False, **kwargs):
    '''
    List the packages currently installed as a dict::

        {'<package_name>': '<version>'}

    CLI Example:

    .. code-block:: bash

        salt '*' pkg.list_pkgs
    '''
    versions_as_list = salt.utils.is_true(versions_as_list)
    # not yet implemented or not applicable
    if any([salt.utils.is_true(kwargs.get(x))
            for x in ('removed', 'purge_desired')]):
        return {}

    if 'pkg.list_pkgs' in __context__:
        if versions_as_list:
            return __context__['pkg.list_pkgs']
        else:
            ret = copy.deepcopy(__context__['pkg.list_pkgs'])
            __salt__['pkg_resource.stringify'](ret)
            return ret

    cmd = 'rpm -qa --queryformat "%{NAME}_|-%{VERSION}_|-%{RELEASE}\\n"'
    ret = {}
    out = __salt__['cmd.run'](cmd, output_loglevel='trace')
    for line in out.splitlines():
        name, pkgver, rel = line.split('_|-')
        if rel:
            pkgver += '-{0}'.format(rel)
        __salt__['pkg_resource.add_pkg'](ret, name, pkgver)

    __salt__['pkg_resource.sort_pkglist'](ret)
    __context__['pkg.list_pkgs'] = copy.deepcopy(ret)
    if not versions_as_list:
        __salt__['pkg_resource.stringify'](ret)
    return ret


class _RepoInfo(object):
    '''
    Incapsulate all properties that are dumped in zypp._RepoInfo.dumpOn:
    http://doc.opensuse.org/projects/libzypp/HEAD/classzypp_1_1RepoInfo.html#a2ba8fdefd586731621435428f0ec6ff1
    '''
    repo_types = {}

    if HAS_ZYPP:
        repo_types = {
            zypp.RepoType.NONE_e: 'NONE',
            zypp.RepoType.RPMMD_e: 'rpm-md',
            zypp.RepoType.YAST2_e: 'yast2',
            zypp.RepoType.RPMPLAINDIR_e: 'plaindir',
        }

    def __init__(self, zypp_repo_info=None):
        self.zypp = zypp_repo_info if zypp_repo_info else zypp.RepoInfo()

    @property
    def options(self):
        class_items = self.__class__.__dict__.iteritems()
        return dict([(k, getattr(self, k)) for k, v in class_items
                     if isinstance(v, property) and k != 'options'
                     and getattr(self, k) not in (None, '')])

    def _check_only_mirrorlist_or_url(self):
        if all(x in self.options for x in ('mirrorlist', 'url')):
            raise ValueError(
                'Only one of \'mirrorlist\' and \'url\' can be specified')

    def _zypp_url(self, url):
        return zypp.Url(url) if url else zypp.Url()

    @options.setter
    def options(self, value):
        for k, v in value.iteritems():
            setattr(self, k, v)

    @property
    def alias(self):
        return self.zypp.alias()

    @alias.setter
    def alias(self, value):
        if value:
            self.zypp.setAlias(value)
        else:
            raise ValueError('Alias cannot be empty')

    @property
    def autorefresh(self):
        return self.zypp.autorefresh()

    @autorefresh.setter
    def autorefresh(self, value):
        self.zypp.setAlias(value)

    @property
    def enabled(self):
        return self.zypp.enabled()

    @enabled.setter
    def enabled(self, value):
        self.zypp.setEnabled(value)

    @property
    def gpgcheck(self):
        return self.zypp.gpgCheck()

    @gpgcheck.setter
    def gpgcheck(self, value):
        self.zypp.setGpgCheck(value)

    @property
    def gpgkey(self):
        return self.zypp.gpgKeyUrl().asCompleteString()

    @gpgkey.setter
    def gpgkey(self, value):
        self.zypp.setGpgKeyUrl(self._zypp_url(value))

    @property
    def keeppackages(self):
        return self.zypp.keepPackages()

    @keeppackages.setter
    def keeppackages(self, value):
        self.zypp.setKeepPackages(value)

    @property
    def metadataPath(self):
        return self.zypp.metadataPath().c_str()

    @metadataPath.setter
    def metadataPath(self, value):
        self.zypp.setMetadataPath(value)

    @property
    def mirrorlist(self):
        return self.zypp.mirrorListUrl().asCompleteString()

    @mirrorlist.setter
    def mirrorlist(self, value):
        self.zypp.setMirrorListUrl(self._zypp_url(value))
        # self._check_only_mirrorlist_or_url()

    @property
    def name(self):
        return self.zypp.name()

    @name.setter
    def name(self, value):
        self.zypp.setName(value)

    @property
    def packagesPath(self):
        return self.zypp.packagesPath().c_str()

    @packagesPath.setter
    def packagesPath(self, value):
        self.zypp.setPackagesPath(self._zypp_url(value))

    @property
    def path(self):
        return self.zypp.path().c_str()

    @path.setter
    def path(self, value):
        self.zypp.setPath(self._zypp_url(value))

    @property
    def priority(self):
        return self.zypp.priority()

    @priority.setter
    def priority(self, value):
        self.zypp.setPriority(value)

    @property
    def service(self):
        return self.zypp.service()

    @service.setter
    def service(self, value):
        self.zypp.setService(value)

    @property
    def targetdistro(self):
        return self.zypp.targetDistribution()

    @targetdistro.setter
    def targetdistro(self, value):
        self.zypp.setTargetDistribution(value)

    @property
    def type(self):
        return self.repo_types[self.zypp.type().toEnum()]

    @type.setter
    def type(self, value):
        self.zypp.setType(next(k for k, v in self.repo_types if v == value))

    @property
    def url(self):
        return [url.asCompleteString() for url in self.zypp.baseUrls()]

    @url.setter
    def url(self, value):
        self.zypp.setBaseUrl(self._zypp_url(value))
        # self._check_only_mirrorlist_or_url()


@_contextmanager
def _try_zypp():
    '''
    Convert errors like:
    'RuntimeError: [|] Repository has no alias defined.'
    into
    'ERROR: Repository has no alias defined.'.
    '''
    try:
        yield
    except RuntimeError as e:
        raise CommandExecutionError(re.sub(r'\[.*\] ', '', str(e)))


@_depends('zypp')
def _get_zypp_repo(repo, **kwargs):
    '''
    Get zypp._RepoInfo object by repo alias.
    '''
    with _try_zypp():
        return zypp.RepoManager().getRepositoryInfo(repo)


@_depends('zypp')
def get_repo(repo, **kwargs):
    '''
    Display a repo.

    CLI Example:

    .. code-block:: bash

        salt '*' pkg.get_repo alias
    '''
    r = _RepoInfo(_get_zypp_repo(repo))
    return r.options


@_depends('zypp')
def list_repos():
    '''
    Lists all repos.

    CLI Example:

    .. code-block:: bash

       salt '*' pkg.list_repos
    '''
    with _try_zypp():
        ret = {}
        for r in zypp.RepoManager().knownRepositories():
            ret[r.alias()] = get_repo(r.alias())
        return ret


@_depends('zypp')
def del_repo(repo, **kwargs):
    '''
    Delete a repo.

    CLI Examples:

    .. code-block:: bash

        salt '*' pkg.del_repo alias
        salt '*' pkg.del_repo alias
    '''
    r = _get_zypp_repo(repo)
    with _try_zypp():
        zypp.RepoManager().removeRepository(r)
    return 'File {1} containing repo {0!r} has been removed.\n'.format(
        repo, r.path().c_str())


@_depends('zypp')
def mod_repo(repo, **kwargs):
    '''
    Modify one or more values for a repo. If the repo does not exist, it will
    be created, so long as the following values are specified:

    repo
        alias by which the zypper refers to the repo
    url or mirrorlist
        the URL for zypper to reference

    Key/Value pairs may also be removed from a repo's configuration by setting
    a key to a blank value. Bear in mind that a name cannot be deleted, and a
    url can only be deleted if a mirrorlist is specified (or vice versa).

    CLI Examples:

    .. code-block:: bash

        salt '*' pkg.mod_repo alias alias=new_alias
        salt '*' pkg.mod_repo alias enabled=True
        salt '*' pkg.mod_repo alias url= mirrorlist=http://host.com/
    '''
    # Filter out '__pub' arguments, as well as saltenv
    repo_opts = {}
    for x in kwargs:
        if not x.startswith('__') and x not in ('saltenv',):
            repo_opts[x] = kwargs[x]

    repo_manager = zypp.RepoManager()
    try:
        r = _RepoInfo(repo_manager.getRepositoryInfo(repo))
        new_repo = False
    except RuntimeError:
        r = _RepoInfo()
        r.alias = repo
        new_repo = True
    try:
        r.options = repo_opts
    except ValueError as e:
        raise SaltInvocationError(str(e))
    with _try_zypp():
        if new_repo:
            repo_manager.addRepository(r.zypp)
        else:
            repo_manager.modifyRepository(repo, r.zypp)
    return r.options


def refresh_db():
    '''
    Just run a ``zypper refresh``, return a dict::

        {'<database name>': Bool}

    CLI Example:

    .. code-block:: bash

        salt '*' pkg.refresh_db
    '''
    cmd = 'zypper refresh'
    ret = {}
    out = __salt__['cmd.run'](cmd, output_loglevel='trace')
    for line in out.splitlines():
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


def install(name=None,
            refresh=False,
            fromrepo=None,
            pkgs=None,
            sources=None,
            **kwargs):
    '''
    Install the passed package(s), add refresh=True to run 'zypper refresh'
    before package is installed.

    name
        The name of the package to be installed. Note that this parameter is
        ignored if either "pkgs" or "sources" is passed. Additionally, please
        note that this option can only be used to install packages from a
        software repository. To install a package file manually, use the
        "sources" option.

        CLI Example:

        .. code-block:: bash

            salt '*' pkg.install <package name>

    refresh
        Whether or not to refresh the package database before installing.

    fromrepo
        Specify a package repository to install from.

    version
        Can be either a version number, or the combination of a comparison
        operator (<, >, <=, >=, =) and a version number (ex. '>1.2.3-4').
        This parameter is ignored if "pkgs" or "sources" is passed.


    Multiple Package Installation Options:

    pkgs
        A list of packages to install from a software repository. Must be
        passed as a python list. A specific version number can be specified
        by using a single-element dict representing the package and its
        version. As with the ``version`` parameter above, comparison operators
        can be used to target a specific version of a package.

        CLI Examples:

        .. code-block:: bash

            salt '*' pkg.install pkgs='["foo", "bar"]'
            salt '*' pkg.install pkgs='["foo", {"bar": "1.2.3-4"}]'
            salt '*' pkg.install pkgs='["foo", {"bar": "<1.2.3-4"}]'

    sources
        A list of RPM packages to install. Must be passed as a list of dicts,
        with the keys being package names, and the values being the source URI
        or local path to the package.

        CLI Example:

        .. code-block:: bash

            salt '*' pkg.install sources='[{"foo": "salt://foo.rpm"},{"bar": "salt://bar.rpm"}]'


    Returns a dict containing the new package names and versions::

        {'<package>': {'old': '<old-version>',
                       'new': '<new-version>'}}
    '''
    if salt.utils.is_true(refresh):
        refresh_db()

    try:
        pkg_params, pkg_type = __salt__['pkg_resource.parse_targets'](
            name, pkgs, sources, **kwargs
        )
    except MinionError as exc:
        raise CommandExecutionError(exc)

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

    if pkg_type == 'repository':
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
                    log.debug(targets)
                else:
                    msg = ('Invalid version string {0!r} for package '
                           '{1!r}'.format(version_num, name))
                    problems.append(msg)
        if problems:
            for problem in problems:
                log.error(problem)
            return {}
    else:
        targets = pkg_params

    old = list_pkgs()
    downgrades = []
    if fromrepo:
        fromrepoopt = "--force --force-resolution --from {0} ".format(fromrepo)
        log.info('Targeting repo {0!r}'.format(fromrepo))
    else:
        fromrepoopt = ""
    # Split the targets into batches of 500 packages each, so that
    # the maximal length of the command line is not broken
    while targets:
        # Quotes needed around package targets because of the possibility of
        # output redirection characters "<" or ">" in zypper command.
        cmd = (
            'zypper --non-interactive install --name '
            '--auto-agree-with-licenses {0}"{1}"'
            .format(fromrepoopt, '" "'.join(targets[:500]))
        )
        targets = targets[500:]
        out = __salt__['cmd.run'](cmd, output_loglevel='trace')
        for line in out.splitlines():
            match = re.match(
                "^The selected package '([^']+)'.+has lower version",
                line
            )
            if match:
                downgrades.append(match.group(1))

    while downgrades:
        cmd = (
            'zypper --non-interactive install --name '
            '--auto-agree-with-licenses --force {0}{1}'
            .format(fromrepoopt, ' '.join(downgrades[:500]))
        )
        __salt__['cmd.run'](cmd, output_loglevel='trace')
        downgrades = downgrades[500:]
    __context__.pop('pkg.list_pkgs', None)
    new = list_pkgs()
    return salt.utils.compare_dicts(old, new)


def upgrade(refresh=True):
    '''
    Run a full system upgrade, a zypper upgrade

    Return a dict containing the new package names and versions::

        {'<package>': {'old': '<old-version>',
                       'new': '<new-version>'}}

    CLI Example:

    .. code-block:: bash

        salt '*' pkg.upgrade
    '''
    if salt.utils.is_true(refresh):
        refresh_db()
    old = list_pkgs()
    cmd = 'zypper --non-interactive update --auto-agree-with-licenses'
    __salt__['cmd.run'](cmd, output_loglevel='trace')
    __context__.pop('pkg.list_pkgs', None)
    new = list_pkgs()
    return salt.utils.compare_dicts(old, new)


def _uninstall(action='remove', name=None, pkgs=None):
    '''
    remove and purge do identical things but with different zypper commands,
    this function performs the common logic.
    '''
    try:
        pkg_params = __salt__['pkg_resource.parse_targets'](name, pkgs)[0]
    except MinionError as exc:
        raise CommandExecutionError(exc)

    purge_arg = '-u' if action == 'purge' else ''
    old = list_pkgs()
    targets = [x for x in pkg_params if x in old]
    if not targets:
        return {}
    while targets:
        cmd = (
            'zypper --non-interactive remove {0} {1}'
            .format(purge_arg, ' '.join(targets[:500]))
        )
        __salt__['cmd.run'](cmd, output_loglevel='trace')
        targets = targets[500:]
    __context__.pop('pkg.list_pkgs', None)
    new = list_pkgs()
    return salt.utils.compare_dicts(old, new)


def remove(name=None, pkgs=None, **kwargs):
    '''
    Remove packages with ``zypper -n remove``

    name
        The name of the package to be deleted.


    Multiple Package Options:

    pkgs
        A list of packages to delete. Must be passed as a python list. The
        ``name`` parameter will be ignored if this option is passed.

    .. versionadded:: 0.16.0


    Returns a dict containing the changes.

    CLI Example:

    .. code-block:: bash

        salt '*' pkg.remove <package name>
        salt '*' pkg.remove <package1>,<package2>,<package3>
        salt '*' pkg.remove pkgs='["foo", "bar"]'
    '''
    return _uninstall(action='remove', name=name, pkgs=pkgs)


def purge(name=None, pkgs=None, **kwargs):
    '''
    Recursively remove a package and all dependencies which were installed
    with it, this will call a ``zypper -n remove -u``

    name
        The name of the package to be deleted.


    Multiple Package Options:

    pkgs
        A list of packages to delete. Must be passed as a python list. The
        ``name`` parameter will be ignored if this option is passed.

    .. versionadded:: 0.16.0


    Returns a dict containing the changes.

    CLI Example:

    .. code-block:: bash

        salt '*' pkg.purge <package name>
        salt '*' pkg.purge <package1>,<package2>,<package3>
        salt '*' pkg.purge pkgs='["foo", "bar"]'
    '''
    return _uninstall(action='purge', name=name, pkgs=pkgs)
