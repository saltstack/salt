# -*- coding: utf-8 -*-
'''
Package support for openSUSE via the zypper package manager

:depends: - ``zypp`` Python module.  Install with ``zypper install python-zypp``
'''

# Import python libs
from __future__ import absolute_import
import copy
import logging
import re
import os

# Import 3rd-party libs
# pylint: disable=import-error,redefined-builtin,no-name-in-module
import salt.ext.six as six
from salt.exceptions import SaltInvocationError
from salt.ext.six.moves import configparser
from salt.ext.six.moves.urllib.parse import urlparse as _urlparse
# pylint: enable=import-error,redefined-builtin,no-name-in-module

from xml.dom import minidom as dom

# Import salt libs
import salt.utils
from salt.exceptions import (
    CommandExecutionError, MinionError)

log = logging.getLogger(__name__)

HAS_ZYPP = False
ZYPP_HOME = '/etc/zypp'
LOCKS = '{0}/locks'.format(ZYPP_HOME)
REPOS = '{0}/repos.d'.format(ZYPP_HOME)
DEFAULT_PRIORITY = 99

# Define the module's virtual name
__virtualname__ = 'pkg'


def __virtual__():
    '''
    Set the virtual pkg module if the os is openSUSE
    '''
    if __grains__.get('os_family', '') != 'Suse':
        return (False, "Module zypper: non SUSE OS not suppored by zypper package manager")
    # Not all versions of Suse use zypper, check that it is available
    if not salt.utils.which('zypper'):
        return (False, "Module zypper: zypper package manager not found")
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
    call = __salt__['cmd.run_all'](
        ['zypper', 'list-updates'],
        output_loglevel='trace',
        python_shell=False
    )
    if call['retcode'] != 0:
        comment = ''
        if 'stderr' in call:
            comment += call['stderr']
        if 'stdout' in call:
            comment += call['stdout']
        raise CommandExecutionError(
            '{0}'.format(comment)
        )
    else:
        out = call['stdout']

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
list_updates = salt.utils.alias_function(list_upgrades, 'list_updates')


def info_installed(*names, **kwargs):
    '''
    Return the information of the named package(s), installed on the system.

    :param names:
        Names of the packages to get information about.

    :param attr:
        Comma-separated package attributes. If no 'attr' is specified, all available attributes returned.

        Valid attributes are:
            version, vendor, release, build_date, build_date_time_t, install_date, install_date_time_t,
            build_host, group, source_rpm, arch, epoch, size, license, signature, packager, url,
            summary, description.

    :param errors:
        Handle RPM field errors (true|false). By default, various mistakes in the textual fields are simply ignored and
        omitted from the data. Otherwise a field with a mistake is not returned, instead a 'N/A (bad UTF-8)'
        (not available, broken) text is returned.

        Valid attributes are:
            ignore, report

    CLI example:

    .. code-block:: bash

        salt '*' pkg.info_installed <package1>
        salt '*' pkg.info_installed <package1> <package2> <package3> ...
        salt '*' pkg.info_installed <package1> attr=version,vendor
        salt '*' pkg.info_installed <package1> <package2> <package3> ... attr=version,vendor
        salt '*' pkg.info_installed <package1> <package2> <package3> ... attr=version,vendor errors=true
    '''
    ret = dict()
    for pkg_name, pkg_nfo in __salt__['lowpkg.info'](*names, **kwargs).items():
        t_nfo = dict()
        # Translate dpkg-specific keys to a common structure
        for key, value in pkg_nfo.items():
            if type(value) == str:
                # Check, if string is encoded in a proper UTF-8
                value_ = value.decode('UTF-8', 'ignore').encode('UTF-8', 'ignore')
                if value != value_:
                    value = kwargs.get('errors') and value_ or 'N/A (invalid UTF-8)'
                    log.error('Package {0} has bad UTF-8 code in {1}: {2}'.format(pkg_name, key, value))
            if key == 'source_rpm':
                t_nfo['source'] = value
            else:
                t_nfo[key] = value

        ret[pkg_name] = t_nfo

    return ret


def info_available(*names, **kwargs):
    '''
    Return the information of the named package available for the system.

    CLI example:

    .. code-block:: bash

        salt '*' pkg.info_available <package1>
        salt '*' pkg.info_available <package1> <package2> <package3> ...
    '''
    ret = {}

    if not names:
        return ret
    else:
        names = sorted(list(set(names)))

    # Refresh db before extracting the latest package
    if salt.utils.is_true(kwargs.pop('refresh', True)):
        refresh_db()

    pkg_info = []
    batch = names[:]
    batch_size = 200

    # Run in batches
    while batch:
        cmd = ['zypper', 'info', '-t', 'package']
        cmd.extend(batch[:batch_size])
        pkg_info.extend(
            re.split(
                'Information for package*',
                __salt__['cmd.run_stdout'](
                    cmd,
                    output_loglevel='trace',
                    python_shell=False
                )
            )
        )
        batch = batch[batch_size:]

    for pkg_data in pkg_info:
        nfo = {}
        for line in [data for data in pkg_data.split('\n') if ':' in data]:
            if line.startswith('-----'):
                continue
            kw = [data.strip() for data in line.split(':', 1)]
            if len(kw) == 2 and kw[1]:
                nfo[kw[0].lower()] = kw[1]
        if nfo.get('name'):
            name = nfo.pop('name')
            ret[name] = nfo
        if nfo.get('status'):
            nfo['status'] = nfo.get('status')
        if nfo.get('installed'):
            nfo['installed'] = nfo.get('installed').lower() == 'yes' and True or False

    return ret


def info(*names, **kwargs):
    '''
    .. deprecated:: Nitrogen
       Use :py:func:`~salt.modules.pkg.info_available` instead.

    Return the information of the named package available for the system.

    CLI example:

    .. code-block:: bash

        salt '*' pkg.info <package1>
        salt '*' pkg.info <package1> <package2> <package3> ...
    '''
    salt.utils.warn_until('Nitrogen', "Please use 'pkg.info_available' instead")
    return info_available(*names)


def latest_version(*names, **kwargs):
    '''
    Return the latest version of the named package available for upgrade or
    installation. If more than one package name is specified, a dict of
    name/version pairs is returned.

    If the latest version of a given package is already installed, an empty
    dict will be returned for that package.

    CLI example:

    .. code-block:: bash

        salt '*' pkg.latest_version <package name>
        salt '*' pkg.latest_version <package1> <package2> <package3> ...
    '''
    ret = dict()

    if not names:
        return ret

    names = sorted(list(set(names)))
    package_info = info_available(*names)
    for name in names:
        pkg_info = package_info.get(name, {})
        status = pkg_info.get('status', '').lower()
        if status.find('not installed') > -1 or status.find('out-of-date') > -1:
            ret[name] = pkg_info.get('version')

    # Return a string if only one package name passed
    if len(names) == 1 and len(ret):
        return ret[names[0]]

    return ret


# available_version is being deprecated
available_version = salt.utils.alias_function(latest_version, 'available_version')


def upgrade_available(name):
    '''
    Check whether or not an upgrade is available for a given package

    CLI Example:

    .. code-block:: bash

        salt '*' pkg.upgrade_available <package name>
    '''
    return latest_version(name).get(name) is not None


def version(*names, **kwargs):
    '''
    Returns a string representing the package version or an empty dict if not
    installed. If more than one package name is specified, a dict of
    name/version pairs is returned.

    CLI Example:

    .. code-block:: bash

        salt '*' pkg.version <package name>
        salt '*' pkg.version <package1> <package2> <package3> ...
    '''
    return __salt__['pkg_resource.version'](*names, **kwargs) or {}


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

    cmd = ['rpm', '-qa', '--queryformat', '%{NAME}_|-%{VERSION}_|-%{RELEASE}_|-%|EPOCH?{%{EPOCH}}:{}|\\n']
    ret = {}
    out = __salt__['cmd.run'](
        cmd,
        output_loglevel='trace',
        python_shell=False
    )
    for line in out.splitlines():
        name, pkgver, rel, epoch = line.split('_|-')
        if epoch:
            pkgver = '{0}:{1}'.format(epoch, pkgver)
        if rel:
            pkgver += '-{0}'.format(rel)
        __salt__['pkg_resource.add_pkg'](ret, name, pkgver)

    __salt__['pkg_resource.sort_pkglist'](ret)
    __context__['pkg.list_pkgs'] = copy.deepcopy(ret)
    if not versions_as_list:
        __salt__['pkg_resource.stringify'](ret)
    return ret


def _get_configured_repos():
    '''
    Get all the info about repositories from the configurations.
    '''

    repos_cfg = configparser.ConfigParser()
    repos_cfg.read([REPOS + '/' + fname for fname in os.listdir(REPOS)])

    return repos_cfg


def _get_repo_info(alias, repos_cfg=None):
    '''
    Get one repo meta-data.
    '''
    try:
        meta = dict((repos_cfg or _get_configured_repos()).items(alias))
        meta['alias'] = alias
        for key, val in six.iteritems(meta):
            if val in ['0', '1']:
                meta[key] = int(meta[key]) == 1
            elif val == 'NONE':
                meta[key] = None
        return meta
    except (ValueError, configparser.NoSectionError) as error:
        return {}


def get_repo(repo, **kwargs):  # pylint: disable=unused-argument
    '''
    Display a repo.

    CLI Example:

    .. code-block:: bash

        salt '*' pkg.get_repo alias
    '''
    return _get_repo_info(repo)


def list_repos():
    '''
    Lists all repos.

    CLI Example:

    .. code-block:: bash

       salt '*' pkg.list_repos
    '''
    repos_cfg = _get_configured_repos()
    all_repos = {}
    for alias in repos_cfg.sections():
        all_repos[alias] = _get_repo_info(alias, repos_cfg=repos_cfg)

    return all_repos


def del_repo(repo):
    '''
    Delete a repo.

    CLI Examples:

    .. code-block:: bash

        salt '*' pkg.del_repo alias
    '''
    repos_cfg = _get_configured_repos()
    for alias in repos_cfg.sections():
        if alias == repo:
            cmd = ['zypper', '-x', '--non-interactive', 'rr', '--loose-auth',
                   '--loose-query', alias]
            doc = dom.parseString(
                __salt__['cmd.run'](
                    cmd,
                    output_loglevel='trace',
                    python_shell=False
                )
            )
            msg = doc.getElementsByTagName('message')
            if doc.getElementsByTagName('progress') and msg:
                return {
                    repo: True,
                    'message': msg[0].childNodes[0].nodeValue,
                }

    raise CommandExecutionError('Repository \'{0}\' not found.'.format(repo))


def mod_repo(repo, **kwargs):
    '''
    Modify one or more values for a repo. If the repo does not exist, it will
    be created, so long as the following values are specified:

    repo or alias
        alias by which the zypper refers to the repo

    url, mirrorlist or baseurl
        the URL for zypper to reference

    enabled
        enable or disable (True or False) repository,
        but do not remove if disabled.

    refresh
        enable or disable (True or False) auto-refresh of the repository.

    cache
        Enable or disable (True or False) RPM files caching.

    gpgcheck
        Enable or disable (True or False) GOG check for this repository.

    gpgautoimport
        Automatically trust and import new repository.

    Key/Value pairs may also be removed from a repo's configuration by setting
    a key to a blank value. Bear in mind that a name cannot be deleted, and a
    url can only be deleted if a mirrorlist is specified (or vice versa).

    CLI Examples:

    .. code-block:: bash

        salt '*' pkg.mod_repo alias alias=new_alias
        salt '*' pkg.mod_repo alias url= mirrorlist=http://host.com/
    '''

    repos_cfg = _get_configured_repos()
    added = False

    # An attempt to add new one?
    if repo not in repos_cfg.sections():
        url = kwargs.get('url', kwargs.get('mirrorlist', kwargs.get('baseurl')))
        if not url:
            raise CommandExecutionError(
                'Repository \'{0}\' not found and no URL passed'.format(repo)
            )

        if not _urlparse(url).scheme:
            raise CommandExecutionError(
                'Repository \'{0}\' not found and URL is invalid'.format(repo)
            )

        # Is there already such repo under different alias?
        for alias in repos_cfg.sections():
            repo_meta = _get_repo_info(alias, repos_cfg=repos_cfg)

            # Complete user URL, in case it is not
            new_url = _urlparse(url)
            if not new_url.path:
                new_url = _urlparse.ParseResult(scheme=new_url.scheme,  # pylint: disable=E1123
                                                netloc=new_url.netloc,
                                                path='/',
                                                params=new_url.params,
                                                query=new_url.query,
                                                fragment=new_url.fragment)
            base_url = _urlparse(repo_meta['baseurl'])

            if new_url == base_url:
                raise CommandExecutionError(
                    'Repository \'{0}\' already exists as \'{1}\'.'.format(
                        repo,
                        alias
                    )
                )

        # Add new repo
        doc = None
        try:
            # Try to parse the output and find the error,
            # but this not always working (depends on Zypper version)
            doc = dom.parseString(
                __salt__['cmd.run'](
                    ['zypper', '-x', 'ar', url, repo],
                    output_loglevel='trace',
                    python_shell=False
                )
            )
        except Exception:
            # No XML out available, but the the result is still unknown
            pass

        if doc:
            msg_nodes = doc.getElementsByTagName('message')
            if msg_nodes:
                msg_node = msg_nodes[0]
                if msg_node.getAttribute('type') == 'error':
                    raise CommandExecutionError(
                        msg_node.childNodes[0].nodeValue
                    )

        # Verify the repository has been added
        repos_cfg = _get_configured_repos()
        if repo not in repos_cfg.sections():
            raise CommandExecutionError(
                'Failed add new repository \'{0}\' for unknown reason. '
                'Please look into Zypper logs.'.format(repo)
            )
        added = True

    # Modify added or existing repo according to the options
    cmd_opt = []

    if 'enabled' in kwargs:
        cmd_opt.append(kwargs['enabled'] and '--enable' or '--disable')

    if 'refresh' in kwargs:
        cmd_opt.append(kwargs['refresh'] and '--refresh' or '--no-refresh')

    if 'cache' in kwargs:
        cmd_opt.append(
            kwargs['cache'] and '--keep-packages' or '--no-keep-packages'
        )

    if 'gpgcheck' in kwargs:
        cmd_opt.append(kwargs['gpgcheck'] and '--gpgcheck' or '--no-gpgcheck')

    if kwargs.get('gpgautoimport') is True:
        cmd_opt.append('--gpg-auto-import-keys')

    if 'priority' in kwargs:
        cmd_opt.append("--priority='{0}'".format(kwargs.get('priority', DEFAULT_PRIORITY)))

    if 'humanname' in kwargs:
        cmd_opt.append("--name='{0}'".format(kwargs.get('humanname')))

    if cmd_opt:
        cmd = ['zypper', '-x', 'mr']
        cmd.extend(cmd_opt)
        cmd.append(repo)
        __salt__['cmd.run'](cmd, output_loglevel='trace', python_shell=False)

    # If repo nor added neither modified, error should be thrown
    if not added and not cmd_opt:
        raise CommandExecutionError(
            'Modification of the repository \'{0}\' was not specified.'
            .format(repo)
        )

    return get_repo(repo)


def refresh_db():
    '''
    Just run a ``zypper refresh``, return a dict::

        {'<database name>': Bool}

    CLI Example:

    .. code-block:: bash

        salt '*' pkg.refresh_db
    '''
    cmd = ['zypper', 'refresh']
    ret = {}
    call = __salt__['cmd.run_all'](
        cmd,
        output_loglevel='trace',
        python_shell=False
    )
    if call['retcode'] != 0:
        msg = 'Failed to refresh zypper'
        if call['stderr']:
            msg += ': ' + call['stderr']

        raise CommandExecutionError(msg)
    else:
        out = call['stdout']

    for line in out.splitlines():
        if not line:
            continue
        if line.strip().startswith('Repository'):
            key = line.split('\'')[1].strip()
            if 'is up to date' in line:
                ret[key] = False
        elif line.strip().startswith('Building'):
            key = line.split('\'')[1].strip()
            if 'done' in line:
                ret[key] = True
    return ret


def install(name=None,
            refresh=False,
            fromrepo=None,
            pkgs=None,
            sources=None,
            downloadonly=None,
            skip_verify=False,
            version=None,
            **kwargs):
    '''
    Install the passed package(s), add refresh=True to run 'zypper refresh'
    before package is installed.

    name
        The name of the package to be installed. Note that this parameter is
        ignored if either ``pkgs`` or ``sources`` is passed. Additionally,
        please note that this option can only be used to install packages from
        a software repository. To install a package file manually, use the
        ``sources`` option.

        CLI Example:

        .. code-block:: bash

            salt '*' pkg.install <package name>

    refresh
        Whether or not to refresh the package database before installing.

    fromrepo
        Specify a package repository to install from.

    downloadonly
        Only download the packages, do not install.

    skip_verify
        Skip the GPG verification check (e.g., ``--no-gpg-checks``)

    version
        Can be either a version number, or the combination of a comparison
        operator (<, >, <=, >=, =) and a version number (ex. '>1.2.3-4').
        This parameter is ignored if ``pkgs`` or ``sources`` is passed.


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
    try:
        pkg_params, pkg_type = __salt__['pkg_resource.parse_targets'](name, pkgs, sources, **kwargs)
    except MinionError as exc:
        raise CommandExecutionError(exc)

    if pkg_params is None or len(pkg_params) == 0:
        return {}

    version_num = version
    if version_num:
        if pkgs is None and sources is None:
            # Allow "version" to work for single package target
            pkg_params = {name: version_num}
        else:
            log.warning("'version' parameter will be ignored for multiple package targets")

    if pkg_type == 'repository':
        targets = []
        problems = []
        for param, version_num in six.iteritems(pkg_params):
            if version_num is None:
                targets.append(param)
            else:
                match = re.match(r'^([<>])?(=)?([^<>=]+)$', version_num)
                if match:
                    gt_lt, equal, verstr = match.groups()
                    targets.append('{0}{1}{2}'.format(param, ((gt_lt or '') + (equal or '')) or '=', verstr))
                    log.debug(targets)
                else:
                    msg = ('Invalid version string {0!r} for package {1!r}'.format(version_num, name))
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
        fromrepoopt = ['--force', '--force-resolution', '--from', fromrepo]
        log.info('Targeting repo \'{0}\''.format(fromrepo))
    else:
        fromrepoopt = ''
    cmd_install = ['zypper', '--non-interactive']
    if not refresh:
        cmd_install.append('--no-refresh')
    if skip_verify:
        cmd_install.append('--no-gpg-checks')
    cmd_install.extend(['install', '--name', '--auto-agree-with-licenses'])
    if downloadonly:
        cmd_install.append('--download-only')
    if fromrepo:
        cmd_install.extend(fromrepoopt)

    errors = []

    # Split the targets into batches of 500 packages each, so that
    # the maximal length of the command line is not broken
    while targets:
        cmd = cmd_install + targets[:500]
        targets = targets[500:]
        call = __salt__['cmd.run_all'](cmd, output_loglevel='trace', python_shell=False)
        if call['retcode'] != 0:
            raise CommandExecutionError(call['stderr'])  # Fixme: This needs a proper report mechanism.
        else:
            for line in call['stdout'].splitlines():
                match = re.match(r"^The selected package '([^']+)'.+has lower version", line)
                if match:
                    downgrades.append(match.group(1))

    while downgrades:
        cmd = cmd_install + ['--force'] + downgrades[:500]
        downgrades = downgrades[500:]
        out = __salt__['cmd.run_all'](cmd,
                                      output_loglevel='trace',
                                      python_shell=False)

        if out['retcode'] != 0 and out['stderr']:
            errors.append(out['stderr'])

    __context__.pop('pkg.list_pkgs', None)
    new = list_pkgs()
    ret = salt.utils.compare_dicts(old, new)

    if errors:
        raise CommandExecutionError(
            'Problem encountered installing package(s)',
            info={'errors': errors, 'changes': ret}
        )

    return ret


def upgrade(refresh=True, skip_verify=False):
    '''
    Run a full system upgrade, a zypper upgrade

    Return a dict containing the new package names and versions::

        {'<package>': {'old': '<old-version>',
                       'new': '<new-version>'}}

    CLI Example:

    .. code-block:: bash

        salt '*' pkg.upgrade


    Options:

    skip_verify
        Skip the GPG verification check (e.g., ``--no-gpg-checks``)

    '''
    ret = {'changes': {},
           'result': True,
           'comment': '',
    }

    if salt.utils.is_true(refresh):
        refresh_db()
    old = list_pkgs()
    cmd = ['zypper', '--non-interactive']
    if skip_verify:
        cmd.append('--no-gpg-checks')
    cmd.extend(['update', '--auto-agree-with-licenses'])
    call = __salt__['cmd.run_all'](
        cmd,
        output_loglevel='trace',
        python_shell=False,
        redirect_stderr=True
    )

    if call['retcode'] != 0:
        ret['result'] = False
        if call['stdout']:
            ret['comment'] = call['stdout']

    __context__.pop('pkg.list_pkgs', None)
    new = list_pkgs()
    ret['changes'] = salt.utils.compare_dicts(old, new)

    return ret


def _uninstall(action='remove', name=None, pkgs=None):
    '''
    remove and purge do identical things but with different zypper commands,
    this function performs the common logic.
    '''
    try:
        pkg_params = __salt__['pkg_resource.parse_targets'](name, pkgs)[0]
    except MinionError as exc:
        raise CommandExecutionError(exc)

    old = list_pkgs()
    targets = [x for x in pkg_params if x in old]
    if not targets:
        return {}

    errors = []
    while targets:
        cmd = ['zypper', '--non-interactive', 'remove']
        if action == 'purge':
            cmd.append('-u')
        cmd.extend(targets[:500])
        out = __salt__['cmd.run_all'](cmd,
                                      output_loglevel='trace',
                                      python_shell=False)

        if out['retcode'] != 0 and out['stderr']:
            errors.append(out['stderr'])

        targets = targets[500:]

    __context__.pop('pkg.list_pkgs', None)
    new = list_pkgs()
    ret = salt.utils.compare_dicts(old, new)

    if errors:
        raise CommandExecutionError(
            'Problem encountered removing package(s)',
            info={'errors': errors, 'changes': ret}
        )

    return ret


def remove(name=None, pkgs=None, **kwargs):  # pylint: disable=unused-argument
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


def purge(name=None, pkgs=None, **kwargs):  # pylint: disable=unused-argument
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


def list_locks():
    '''
    List current package locks.

    Return a dict containing the locked package with attributes::

        {'<package>': {'case_sensitive': '<case_sensitive>',
                       'match_type': '<match_type>'
                       'type': '<type>'}}

    CLI Example:

    .. code-block:: bash

        salt '*' pkg.list_locks
    '''
    locks = {}
    if os.path.exists(LOCKS):
        with salt.utils.fopen(LOCKS) as fhr:
            for meta in [item.split('\n') for item in fhr.read().split('\n\n')]:
                lock = {}
                for element in [el for el in meta if el]:
                    if ':' in element:
                        lock.update(dict([tuple([i.strip() for i in element.split(':', 1)]), ]))
                if lock.get('solvable_name'):
                    locks[lock.pop('solvable_name')] = lock

    return locks


def clean_locks():
    '''
    Remove unused locks that do not currently (with regard to repositories
    used) lock any package.

    CLI Example:

    .. code-block:: bash

        salt '*' pkg.clean_locks
    '''
    LCK = "removed"
    out = {LCK: 0}
    if not os.path.exists("/etc/zypp/locks"):
        return out

    cmd = ['zypper', '--non-interactive', '-x', 'cl']
    doc = dom.parseString(__salt__['cmd.run'](cmd, output_loglevel='trace', python_shell=False))
    for node in doc.getElementsByTagName("message"):
        text = node.childNodes[0].nodeValue.lower()
        if text.startswith(LCK):
            out[LCK] = text.split(" ")[1]
            break

    return out


def remove_lock(packages, **kwargs):  # pylint: disable=unused-argument
    '''
    Remove specified package lock.

    CLI Example:

    .. code-block:: bash

        salt '*' pkg.remove_lock <package name>
        salt '*' pkg.remove_lock <package1>,<package2>,<package3>
        salt '*' pkg.remove_lock pkgs='["foo", "bar"]'
    '''

    locks = list_locks()
    try:
        packages = list(__salt__['pkg_resource.parse_targets'](packages)[0].keys())
    except MinionError as exc:
        raise CommandExecutionError(exc)

    removed = []
    missing = []
    for pkg in packages:
        if locks.get(pkg):
            removed.append(pkg)
        else:
            missing.append(pkg)

    if removed:
        cmd = ['zypper', '--non-interactive', 'rl']
        cmd.extend(removed)
        __salt__['cmd.run'](cmd, output_loglevel='trace', python_shell=False)

    return {'removed': len(removed), 'not_found': missing}


def add_lock(packages, **kwargs):  # pylint: disable=unused-argument
    '''
    Add a package lock. Specify packages to lock by exact name.

    CLI Example:

    .. code-block:: bash

        salt '*' pkg.add_lock <package name>
        salt '*' pkg.add_lock <package1>,<package2>,<package3>
        salt '*' pkg.add_lock pkgs='["foo", "bar"]'
    '''
    locks = list_locks()
    added = []
    try:
        packages = list(__salt__['pkg_resource.parse_targets'](packages)[0].keys())
    except MinionError as exc:
        raise CommandExecutionError(exc)

    for pkg in packages:
        if not locks.get(pkg):
            added.append(pkg)

    if added:
        cmd = ['zypper', '--non-interactive', 'al']
        cmd.extend(added)
        __salt__['cmd.run'](cmd, output_loglevel='trace', python_shell=False)

    return {'added': len(added), 'packages': added}


def verify(*names, **kwargs):
    '''
    Runs an rpm -Va on a system, and returns the results in a dict

    Files with an attribute of config, doc, ghost, license or readme in the
    package header can be ignored using the ``ignore_types`` keyword argument

    CLI Example:

    .. code-block:: bash

        salt '*' pkg.verify
        salt '*' pkg.verify httpd
        salt '*' pkg.verify 'httpd postfix'
        salt '*' pkg.verify 'httpd postfix' ignore_types=['config','doc']
    '''
    return __salt__['lowpkg.verify'](*names, **kwargs)


def file_list(*packages):
    '''
    List the files that belong to a package. Not specifying any packages will
    return a list of *every* file on the system's rpm database (not generally
    recommended).

    CLI Examples:

    .. code-block:: bash

        salt '*' pkg.file_list httpd
        salt '*' pkg.file_list httpd postfix
        salt '*' pkg.file_list
    '''
    return __salt__['lowpkg.file_list'](*packages)


def file_dict(*packages):
    '''
    List the files that belong to a package, grouped by package. Not
    specifying any packages will return a list of *every* file on the system's
    rpm database (not generally recommended).

    CLI Examples:

    .. code-block:: bash

        salt '*' pkg.file_list httpd
        salt '*' pkg.file_list httpd postfix
        salt '*' pkg.file_list
    '''
    return __salt__['lowpkg.file_dict'](*packages)


def modified(*packages, **flags):
    '''
    List the modified files that belong to a package. Not specifying any packages
    will return a list of _all_ modified files on the system's RPM database.

    .. versionadded:: 2015.5.0

    Filtering by flags (True or False):

    size
        Include only files where size changed.

    mode
        Include only files which file's mode has been changed.

    checksum
        Include only files which MD5 checksum has been changed.

    device
        Include only files which major and minor numbers has been changed.

    symlink
        Include only files which are symbolic link contents.

    owner
        Include only files where owner has been changed.

    group
        Include only files where group has been changed.

    time
        Include only files where modification time of the file has been changed.

    capabilities
        Include only files where capabilities differ or not. Note: supported only on newer RPM versions.

    CLI Examples:

    .. code-block:: bash

        salt '*' pkg.modified
        salt '*' pkg.modified httpd
        salt '*' pkg.modified httpd postfix
        salt '*' pkg.modified httpd owner=True group=False
    '''

    return __salt__['lowpkg.modified'](*packages, **flags)


def owner(*paths):
    '''
    Return the name of the package that owns the file. Multiple file paths can
    be passed. If a single path is passed, a string will be returned,
    and if multiple paths are passed, a dictionary of file/package name
    pairs will be returned.

    If the file is not owned by a package, or is not present on the minion,
    then an empty string will be returned for that path.

    CLI Examples:

    .. code-block:: bash

        salt '*' pkg.owner /usr/bin/apachectl
        salt '*' pkg.owner /usr/bin/apachectl /etc/httpd/conf/httpd.conf
    '''
    return __salt__['lowpkg.owner'](*paths)


def _get_patterns(installed_only=None):
    '''
    List all known patterns in repos.
    '''
    patterns = {}
    doc = dom.parseString(
        __salt__['cmd.run'](
            ['zypper', '--xmlout', 'se', '-t', 'pattern'],
            output_loglevel='trace',
            python_shell=False
        )
    )
    for element in doc.getElementsByTagName('solvable'):
        installed = element.getAttribute('status') == 'installed'
        if (installed_only and installed) or not installed_only:
            patterns[element.getAttribute('name')] = {
                'installed': installed,
                'summary': element.getAttribute('summary'),
            }

    return patterns


def list_patterns():
    '''
    List all known patterns from available repos.

    CLI Examples:

    .. code-block:: bash

        salt '*' pkg.list_patterns
    '''
    return _get_patterns()


def list_installed_patterns():
    '''
    List installed patterns on the system.

    CLI Examples:

    .. code-block:: bash

        salt '*' pkg.list_installed_patterns
    '''
    return _get_patterns(installed_only=True)


def search(criteria):
    '''
    List known packags, available to the system.

    CLI Examples:

    .. code-block:: bash

        salt '*' pkg.search <criteria>
    '''
    doc = dom.parseString(
        __salt__['cmd.run'](
            ['zypper', '--xmlout', 'se', criteria],
            output_loglevel='trace',
            python_shell=False
        )
    )
    solvables = doc.getElementsByTagName('solvable')
    if not solvables:
        raise CommandExecutionError(
            'No packages found matching \'{0}\''.format(criteria)
        )

    out = {}
    for solvable in [s for s in solvables
                     if s.getAttribute('status') == 'not-installed' and
                        s.getAttribute('kind') == 'package']:
        out[solvable.getAttribute('name')] = {
            'summary': solvable.getAttribute('summary')
        }
    return out


def _get_first_aggregate_text(node_list):
    '''
    Extract text from the first occurred DOM aggregate.
    '''
    if not node_list:
        return ''

    out = []
    for node in node_list[0].childNodes:
        if node.nodeType == dom.Document.TEXT_NODE:
            out.append(node.nodeValue)
    return '\n'.join(out)


def list_products(all=False):
    '''
    List all available or installed SUSE products.

    all
        List all products available or only installed. Default is False.

    CLI Examples:

    .. code-block:: bash

        salt '*' pkg.list_products
        salt '*' pkg.list_products all=True
    '''
    ret = list()
    doc = dom.parseString(__salt__['cmd.run'](("zypper -x products{0}".format(not all and ' -i' or '')),
                                              output_loglevel='trace'))
    for prd in doc.getElementsByTagName('product-list')[0].getElementsByTagName('product'):
        p_data = dict()
        p_nfo = dict(prd.attributes.items())
        p_name = p_nfo.pop('name')
        p_data[p_name] = p_nfo
        p_data[p_name]['eol'] = prd.getElementsByTagName('endoflife')[0].getAttribute('text')
        descr = _get_first_aggregate_text(prd.getElementsByTagName('description'))
        p_data[p_name]['description'] = " ".join([line.strip() for line in descr.split(os.linesep)])
        ret.append(p_data)

    return ret


def download(*packages):
    '''
    Download packages to the local disk.

    CLI example:

    .. code-block:: bash

        salt '*' pkg.download httpd
        salt '*' pkg.download httpd postfix
    '''
    if not packages:
        raise SaltInvocationError('No packages specified')

    cmd = ['zypper', '-x', '--non-interactive', 'download']
    cmd.extend(packages)

    doc = dom.parseString(
        __salt__['cmd.run'](
            cmd,
            output_loglevel='trace',
            python_shell=False
        )
    )
    pkg_ret = {}
    for dld_result in doc.getElementsByTagName('download-result'):
        repo = dld_result.getElementsByTagName('repository')[0]
        path = dld_result.getElementsByTagName(
            'localfile')[0].getAttribute('path')
        pkg_info = {
            'repository-name': repo.getAttribute('name'),
            'repository-alias': repo.getAttribute('alias'),
            'path': path
        }
        key = _get_first_aggregate_text(
            dld_result.getElementsByTagName('name')
        )
        pkg_ret[key] = pkg_info

    if pkg_ret:
        return pkg_ret

    raise CommandExecutionError(
        'Unable to download packages: {0}'.format(', '.join(packages))
    )


def diff(*paths):
    '''
    Return a formatted diff between current files and original in a package.
    NOTE: this function includes all files (configuration and not), but does
    not work on binary content.

    :param path: Full path to the installed file
    :return: Difference string or raises and exception if examined file is binary.

    CLI example:

    .. code-block:: bash

        salt '*' pkg.diff /etc/apache2/httpd.conf /etc/sudoers
    '''
    ret = {}

    pkg_to_paths = {}
    for pth in paths:
        pth_pkg = __salt__['lowpkg.owner'](pth)
        if not pth_pkg:
            ret[pth] = os.path.exists(pth) and 'Not managed' or 'N/A'
        else:
            if pkg_to_paths.get(pth_pkg) is None:
                pkg_to_paths[pth_pkg] = []
            pkg_to_paths[pth_pkg].append(pth)

    if pkg_to_paths:
        local_pkgs = __salt__['pkg.download'](*pkg_to_paths.keys())
        for pkg, files in pkg_to_paths.items():
            for path in files:
                ret[path] = __salt__['lowpkg.diff'](
                    local_pkgs[pkg]['path'],
                    path
                ) or 'Unchanged'

    return ret
