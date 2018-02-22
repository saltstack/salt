# -*- coding: utf-8 -*-
'''
Support for APT (Advanced Packaging Tool)

.. important::
    If you feel that Salt should be using this module to manage packages on a
    minion, and it is using a different module (or gives an error similar to
    *'pkg.install' is not available*), see :ref:`here
    <module-provider-override>`.

.. note::
    For virtual package support, either the ``python-apt`` or ``dctrl-tools``
    package must be installed.

    For repository management, the ``python-apt`` package must be installed.
'''
from __future__ import absolute_import, print_function, unicode_literals

# Import python libs
import copy
import fnmatch
import os
import re
import logging
import time

# Import third party libs
# pylint: disable=no-name-in-module,import-error,redefined-builtin
from salt.ext import six
from salt.ext.six.moves.urllib.error import HTTPError
from salt.ext.six.moves.urllib.request import Request as _Request, urlopen as _urlopen
# pylint: enable=no-name-in-module,import-error,redefined-builtin

# Import salt libs
import salt.config
import salt.syspaths
from salt.modules.cmdmod import _parse_env
import salt.utils.args
import salt.utils.data
import salt.utils.files
import salt.utils.functools
import salt.utils.itertools
import salt.utils.json
import salt.utils.path
import salt.utils.pkg
import salt.utils.pkg.deb
import salt.utils.stringutils
import salt.utils.systemd
import salt.utils.versions
import salt.utils.yaml
from salt.exceptions import (
    CommandExecutionError, MinionError, SaltInvocationError
)

log = logging.getLogger(__name__)

# pylint: disable=import-error
try:
    import apt.cache
    import apt.debfile
    from aptsources import sourceslist
    HAS_APT = True
except ImportError:
    HAS_APT = False

try:
    import apt_pkg
    HAS_APTPKG = True
except ImportError:
    HAS_APTPKG = False

try:
    import softwareproperties.ppa
    HAS_SOFTWAREPROPERTIES = True
except ImportError:
    HAS_SOFTWAREPROPERTIES = False
# pylint: enable=import-error

APT_LISTS_PATH = "/var/lib/apt/lists"

# Source format for urllib fallback on PPA handling
LP_SRC_FORMAT = 'deb http://ppa.launchpad.net/{0}/{1}/ubuntu {2} main'
LP_PVT_SRC_FORMAT = 'deb https://{0}private-ppa.launchpad.net/{1}/{2}/ubuntu' \
                    ' {3} main'

_MODIFY_OK = frozenset(['uri', 'comps', 'architectures', 'disabled',
                        'file', 'dist'])
DPKG_ENV_VARS = {
    'APT_LISTBUGS_FRONTEND': 'none',
    'APT_LISTCHANGES_FRONTEND': 'none',
    'DEBIAN_FRONTEND': 'noninteractive',
    'UCF_FORCE_CONFFOLD': '1',
}
if six.PY2:
    # Ensure no unicode in env vars on PY2, as it causes problems with
    # subprocess.Popen()
    DPKG_ENV_VARS = salt.utils.data.encode(DPKG_ENV_VARS)

# Define the module's virtual name
__virtualname__ = 'pkg'


def __virtual__():
    '''
    Confirm this module is on a Debian-based system
    '''
    # If your minion is running an OS which is Debian-based but does not have
    # an "os_family" grain of Debian, then the proper fix is NOT to check for
    # the minion's "os_family" grain here in the __virtual__. The correct fix
    # is to add the value from the minion's "os" grain to the _OS_FAMILY_MAP
    # dict in salt/grains/core.py, so that we assign the correct "os_family"
    # grain to the minion.
    if __grains__.get('os_family') == 'Debian':
        return __virtualname__
    return (False, 'The pkg module could not be loaded: unsupported OS family')


def __init__(opts):
    '''
    For Debian and derivative systems, set up
    a few env variables to keep apt happy and
    non-interactive.
    '''
    if __virtual__() == __virtualname__:
        # Export these puppies so they persist
        os.environ.update(DPKG_ENV_VARS)


def _get_ppa_info_from_launchpad(owner_name, ppa_name):
    '''
    Idea from softwareproperties.ppa.
    Uses urllib2 which sacrifices server cert verification.

    This is used as fall-back code or for secure PPAs

    :param owner_name:
    :param ppa_name:
    :return:
    '''

    lp_url = 'https://launchpad.net/api/1.0/~{0}/+archive/{1}'.format(
        owner_name, ppa_name)
    request = _Request(lp_url, headers={'Accept': 'application/json'})
    lp_page = _urlopen(request)
    return salt.utils.json.load(lp_page)


def _reconstruct_ppa_name(owner_name, ppa_name):
    '''
    Stringify PPA name from args.
    '''
    return 'ppa:{0}/{1}'.format(owner_name, ppa_name)


def _check_apt():
    '''
    Abort if python-apt is not installed
    '''
    if not HAS_APT:
        raise CommandExecutionError(
            'Error: \'python-apt\' package not installed'
        )


def _has_dctrl_tools():
    '''
    Return a boolean depending on whether or not dctrl-tools was installed.
    '''
    try:
        return __context__['pkg._has_dctrl_tools']
    except KeyError:
        __context__['pkg._has_dctrl_tools'] = \
            __salt__['cmd.has_exec']('grep-available')
        return __context__['pkg._has_dctrl_tools']


def _get_virtual():
    '''
    Return a dict of virtual package information
    '''
    try:
        return __context__['pkg._get_virtual']
    except KeyError:
        __context__['pkg._get_virtual'] = {}
        if HAS_APT:
            try:
                apt_cache = apt.cache.Cache()
            except SystemError as syserr:
                msg = 'Failed to get virtual package information ({0})'.format(syserr)
                log.error(msg)
                raise CommandExecutionError(msg)
            pkgs = getattr(apt_cache._cache, 'packages', [])
            for pkg in pkgs:
                for item in getattr(pkg, 'provides_list', []):
                    realpkg = item[2].parent_pkg.name
                    if realpkg not in __context__['pkg._get_virtual']:
                        __context__['pkg._get_virtual'][realpkg] = []
                    __context__['pkg._get_virtual'][realpkg].append(pkg.name)
        elif _has_dctrl_tools():
            cmd = ['grep-available', '-F', 'Provides', '-s',
                   'Package,Provides', '-e', '^.+$']
            out = __salt__['cmd.run_stdout'](cmd,
                                             output_loglevel='trace',
                                             python_shell=False)
            virtpkg_re = re.compile(r'Package: (\S+)\nProvides: ([\S, ]+)')
            for realpkg, provides in virtpkg_re.findall(out):
                __context__['pkg._get_virtual'][realpkg] = provides.split(', ')
        return __context__['pkg._get_virtual']


def _warn_software_properties(repo):
    '''
    Warn of missing python-software-properties package.
    '''
    log.warning('The \'python-software-properties\' package is not installed. '
                'For more accurate support of PPA repositories, you should '
                'install this package.')
    log.warning('Best guess at ppa format: %s', repo)


def latest_version(*names, **kwargs):
    '''
    Return the latest version of the named package available for upgrade or
    installation. If more than one package name is specified, a dict of
    name/version pairs is returned.

    If the latest version of a given package is already installed, an empty
    string will be returned for that package.

    A specific repo can be requested using the ``fromrepo`` keyword argument.

    cache_valid_time

        .. versionadded:: 2016.11.0

        Skip refreshing the package database if refresh has already occurred within
        <value> seconds

    CLI Example:

    .. code-block:: bash

        salt '*' pkg.latest_version <package name>
        salt '*' pkg.latest_version <package name> fromrepo=unstable
        salt '*' pkg.latest_version <package1> <package2> <package3> ...
    '''
    refresh = salt.utils.data.is_true(kwargs.pop('refresh', True))
    show_installed = salt.utils.data.is_true(kwargs.pop('show_installed', False))
    if 'repo' in kwargs:
        raise SaltInvocationError(
            'The \'repo\' argument is invalid, use \'fromrepo\' instead'
        )
    fromrepo = kwargs.pop('fromrepo', None)
    cache_valid_time = kwargs.pop('cache_valid_time', 0)

    if len(names) == 0:
        return ''
    ret = {}
    # Initialize the dict with empty strings
    for name in names:
        ret[name] = ''
    pkgs = list_pkgs(versions_as_list=True)
    repo = ['-o', 'APT::Default-Release={0}'.format(fromrepo)] \
        if fromrepo else None

    # Refresh before looking for the latest version available
    if refresh:
        refresh_db(cache_valid_time)

    try:
        virtpkgs = _get_virtual()
    except CommandExecutionError as cee:
        raise CommandExecutionError(cee)
    all_virt = set()
    for provides in six.itervalues(virtpkgs):
        all_virt.update(provides)

    for name in names:
        cmd = ['apt-cache', '-q', 'policy', name]
        if repo is not None:
            cmd.extend(repo)
        out = __salt__['cmd.run_all'](cmd,
                                      output_loglevel='trace',
                                      python_shell=False,
                                      env={'LC_ALL': 'C', 'LANG': 'C'})
        candidate = ''
        for line in out['stdout'].splitlines():
            if 'Candidate' in line:
                candidate = line.split()
        if len(candidate) >= 2:
            candidate = candidate[-1]
            if candidate.lower() == '(none)':
                # Virtual package is a candidate for installation if and only
                # if it is not currently installed.
                if name in all_virt and name not in pkgs:
                    candidate = '1'
                else:
                    candidate = ''
        else:
            candidate = ''

        installed = pkgs.get(name, [])
        if not installed:
            ret[name] = candidate
        elif installed and show_installed:
            ret[name] = candidate
        elif candidate:
            # If there are no installed versions that are greater than or equal
            # to the install candidate, then the candidate is an upgrade, so
            # add it to the return dict
            if not any(
                (salt.utils.versions.compare(ver1=x,
                                             oper='>=',
                                             ver2=candidate,
                                             cmp_func=version_cmp)
                 for x in installed)
            ):
                ret[name] = candidate

    # Return a string if only one package name passed
    if len(names) == 1:
        return ret[names[0]]
    return ret

# available_version is being deprecated
available_version = salt.utils.functools.alias_function(latest_version, 'available_version')


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


def refresh_db(cache_valid_time=0, failhard=False):
    '''
    Updates the APT database to latest packages based upon repositories

    Returns a dict, with the keys being package databases and the values being
    the result of the update attempt. Values can be one of the following:

    - ``True``: Database updated successfully
    - ``False``: Problem updating database
    - ``None``: Database already up-to-date

    cache_valid_time

        .. versionadded:: 2016.11.0

        Skip refreshing the package database if refresh has already occurred within
        <value> seconds

    failhard

        If False, return results of Err lines as ``False`` for the package database that
        encountered the error.
        If True, raise an error with a list of the package databases that encountered
        errors.

    CLI Example:

    .. code-block:: bash

        salt '*' pkg.refresh_db
    '''
    # Remove rtag file to keep multiple refreshes from happening in pkg states
    salt.utils.pkg.clear_rtag(__opts__)
    failhard = salt.utils.data.is_true(failhard)
    ret = {}
    error_repos = list()

    if cache_valid_time:
        try:
            latest_update = os.stat(APT_LISTS_PATH).st_mtime
            now = time.time()
            log.debug("now: %s, last update time: %s, expire after: %s seconds", now, latest_update, cache_valid_time)
            if latest_update + cache_valid_time > now:
                return ret
        except TypeError as exp:
            log.warning("expected integer for cache_valid_time parameter, failed with: %s", exp)
        except IOError as exp:
            log.warning("could not stat cache directory due to: %s", exp)

    cmd = ['apt-get', '-q', 'update']
    call = __salt__['cmd.run_all'](cmd,
                                   output_loglevel='trace',
                                   python_shell=False)
    if call['retcode'] != 0:
        comment = ''
        if 'stderr' in call:
            comment += call['stderr']

        raise CommandExecutionError(comment)
    else:
        out = call['stdout']

    for line in out.splitlines():
        cols = line.split()
        if not cols:
            continue
        ident = ' '.join(cols[1:])
        if 'Get' in cols[0]:
            # Strip filesize from end of line
            ident = re.sub(r' \[.+B\]$', '', ident)
            ret[ident] = True
        elif 'Ign' in cols[0]:
            ret[ident] = False
        elif 'Hit' in cols[0]:
            ret[ident] = None
        elif 'Err' in cols[0]:
            ret[ident] = False
            error_repos.append(ident)

    if failhard and error_repos:
        raise CommandExecutionError('Error getting repos: {0}'.format(', '.join(error_repos)))

    return ret


def install(name=None,
            refresh=False,
            fromrepo=None,
            skip_verify=False,
            debconf=None,
            pkgs=None,
            sources=None,
            reinstall=False,
            ignore_epoch=False,
            **kwargs):
    '''
    .. versionchanged:: 2015.8.12,2016.3.3,2016.11.0
        On minions running systemd>=205, `systemd-run(1)`_ is now used to
        isolate commands which modify installed packages from the
        ``salt-minion`` daemon's control group. This is done to keep systemd
        from killing any apt-get/dpkg commands spawned by Salt when the
        ``salt-minion`` service is restarted. (see ``KillMode`` in the
        `systemd.kill(5)`_ manpage for more information). If desired, usage of
        `systemd-run(1)`_ can be suppressed by setting a :mod:`config option
        <salt.modules.config.get>` called ``systemd.scope``, with a value of
        ``False`` (no quotes).

    .. _`systemd-run(1)`: https://www.freedesktop.org/software/systemd/man/systemd-run.html
    .. _`systemd.kill(5)`: https://www.freedesktop.org/software/systemd/man/systemd.kill.html

    Install the passed package, add refresh=True to update the dpkg database.

    name
        The name of the package to be installed. Note that this parameter is
        ignored if either "pkgs" or "sources" is passed. Additionally, please
        note that this option can only be used to install packages from a
        software repository. To install a package file manually, use the
        "sources" option.

        32-bit packages can be installed on 64-bit systems by appending the
        architecture designation (``:i386``, etc.) to the end of the package
        name.

        CLI Example:

        .. code-block:: bash

            salt '*' pkg.install <package name>

    refresh
        Whether or not to refresh the package database before installing.

    cache_valid_time

        .. versionadded:: 2016.11.0

        Skip refreshing the package database if refresh has already occurred within
        <value> seconds

    fromrepo
        Specify a package repository to install from
        (e.g., ``apt-get -t unstable install somepackage``)

    skip_verify
        Skip the GPG verification check (e.g., ``--allow-unauthenticated``, or
        ``--force-bad-verify`` for install from package file).

    debconf
        Provide the path to a debconf answers file, processed before
        installation.

    version
        Install a specific version of the package, e.g. 1.2.3~0ubuntu0. Ignored
        if "pkgs" or "sources" is passed.

        .. versionchanged:: 2018.3.0
            version can now contain comparison operators (e.g. ``>1.2.3``,
            ``<=2.0``, etc.)

    reinstall : False
        Specifying reinstall=True will use ``apt-get install --reinstall``
        rather than simply ``apt-get install`` for requested packages that are
        already installed.

        If a version is specified with the requested package, then ``apt-get
        install --reinstall`` will only be used if the installed version
        matches the requested version.

        .. versionadded:: 2015.8.0

    ignore_epoch : False
        Only used when the version of a package is specified using a comparison
        operator (e.g. ``>4.1``). If set to ``True``, then the epoch will be
        ignored when comparing the currently-installed version to the desired
        version.

        .. versionadded:: 2018.3.0

    Multiple Package Installation Options:

    pkgs
        A list of packages to install from a software repository. Must be
        passed as a python list.

        CLI Example:

        .. code-block:: bash

            salt '*' pkg.install pkgs='["foo", "bar"]'
            salt '*' pkg.install pkgs='["foo", {"bar": "1.2.3-0ubuntu0"}]'

    sources
        A list of DEB packages to install. Must be passed as a list of dicts,
        with the keys being package names, and the values being the source URI
        or local path to the package.  Dependencies are automatically resolved
        and marked as auto-installed.

        32-bit packages can be installed on 64-bit systems by appending the
        architecture designation (``:i386``, etc.) to the end of the package
        name.

        .. versionchanged:: 2014.7.0

        CLI Example:

        .. code-block:: bash

            salt '*' pkg.install sources='[{"foo": "salt://foo.deb"},{"bar": "salt://bar.deb"}]'

    force_yes
        Passes ``--force-yes`` to the apt-get command.  Don't use this unless
        you know what you're doing.

        .. versionadded:: 0.17.4

    install_recommends
        Whether to install the packages marked as recommended.  Default is True.

        .. versionadded:: 2015.5.0

    only_upgrade
        Only upgrade the packages, if they are already installed. Default is False.

        .. versionadded:: 2015.5.0

    force_conf_new
        Always install the new version of any configuration files.

        .. versionadded:: 2015.8.0

    Returns a dict containing the new package names and versions::

        {'<package>': {'old': '<old-version>',
                       'new': '<new-version>'}}
    '''
    _refresh_db = False
    if salt.utils.data.is_true(refresh):
        _refresh_db = True
        if 'version' in kwargs and kwargs['version']:
            _refresh_db = False
            _latest_version = latest_version(name,
                                             refresh=False,
                                             show_installed=True)
            _version = kwargs.get('version')
            # If the versions don't match, refresh is True, otherwise no need
            # to refresh
            if not _latest_version == _version:
                _refresh_db = True

        if pkgs:
            _refresh_db = False
            for pkg in pkgs:
                if isinstance(pkg, dict):
                    _name = next(six.iterkeys(pkg))
                    _latest_version = latest_version(_name,
                                                     refresh=False,
                                                     show_installed=True)
                    _version = pkg[_name]
                    # If the versions don't match, refresh is True, otherwise
                    # no need to refresh
                    if not _latest_version == _version:
                        _refresh_db = True
                else:
                    # No version specified, so refresh should be True
                    _refresh_db = True

    if debconf:
        __salt__['debconf.set_file'](debconf)

    try:
        pkg_params, pkg_type = __salt__['pkg_resource.parse_targets'](
            name, pkgs, sources, **kwargs
        )
    except MinionError as exc:
        raise CommandExecutionError(exc)

    # Support old "repo" argument
    repo = kwargs.get('repo', '')
    if not fromrepo and repo:
        fromrepo = repo

    if pkg_params is None or len(pkg_params) == 0:
        return {}

    use_scope = salt.utils.systemd.has_scope(__context__) \
        and __salt__['config.get']('systemd.scope', True)
    cmd_prefix = ['systemd-run', '--scope'] if use_scope else []

    old = list_pkgs()
    targets = []
    downgrade = []
    to_reinstall = {}
    errors = []
    if pkg_type == 'repository':
        pkg_params_items = list(six.iteritems(pkg_params))
        has_comparison = [x for x, y in pkg_params_items
                          if y is not None
                          and (y.startswith('<') or y.startswith('>'))]
        _available = list_repo_pkgs(*has_comparison, byrepo=False, **kwargs) \
            if has_comparison else {}
        # Build command prefix
        cmd_prefix.extend(['apt-get', '-q', '-y'])
        if kwargs.get('force_yes', False):
            cmd_prefix.append('--force-yes')
        if 'force_conf_new' in kwargs and kwargs['force_conf_new']:
            cmd_prefix.extend(['-o', 'DPkg::Options::=--force-confnew'])
        else:
            cmd_prefix.extend(['-o', 'DPkg::Options::=--force-confold'])
        cmd_prefix += ['-o', 'DPkg::Options::=--force-confdef']
        if 'install_recommends' in kwargs:
            if not kwargs['install_recommends']:
                cmd_prefix.append('--no-install-recommends')
            else:
                cmd_prefix.append('--install-recommends')
        if 'only_upgrade' in kwargs and kwargs['only_upgrade']:
            cmd_prefix.append('--only-upgrade')
        if skip_verify:
            cmd_prefix.append('--allow-unauthenticated')
        if fromrepo:
            cmd_prefix.extend(['-t', fromrepo])
        cmd_prefix.append('install')
    else:
        pkg_params_items = []
        for pkg_source in pkg_params:
            if 'lowpkg.bin_pkg_info' in __salt__:
                deb_info = __salt__['lowpkg.bin_pkg_info'](pkg_source)
            else:
                deb_info = None
            if deb_info is None:
                log.error(
                    'pkg.install: Unable to get deb information for %s. '
                    'Version comparisons will be unavailable.', pkg_source
                )
                pkg_params_items.append([pkg_source])
            else:
                pkg_params_items.append(
                    [deb_info['name'], pkg_source, deb_info['version']]
                )
        # Build command prefix
        if 'force_conf_new' in kwargs and kwargs['force_conf_new']:
            cmd_prefix.extend(['dpkg', '-i', '--force-confnew'])
        else:
            cmd_prefix.extend(['dpkg', '-i', '--force-confold'])
        if skip_verify:
            cmd_prefix.append('--force-bad-verify')
        if HAS_APT:
            _resolve_deps(name, pkg_params, **kwargs)

    for pkg_item_list in pkg_params_items:
        if pkg_type == 'repository':
            pkgname, version_num = pkg_item_list
            if name \
                    and pkgs is None \
                    and kwargs.get('version') \
                    and len(pkg_params) == 1:
                # Only use the 'version' param if 'name' was not specified as a
                # comma-separated list
                version_num = kwargs['version']
        else:
            try:
                pkgname, pkgpath, version_num = pkg_item_list
            except ValueError:
                pkgname = None
                pkgpath = pkg_item_list[0]
                version_num = None

        if version_num is None:
            if pkg_type == 'repository':
                if reinstall and pkgname in old:
                    to_reinstall[pkgname] = pkgname
                else:
                    targets.append(pkgname)
            else:
                targets.append(pkgpath)
        else:
            # If we are installing a package file and not one from the repo,
            # and version_num is not None, then we can assume that pkgname is
            # not None, since the only way version_num is not None is if DEB
            # metadata parsing was successful.
            if pkg_type == 'repository':
                # Remove leading equals sign(s) to keep from building a pkgstr
                # with multiple equals (which would be invalid)
                version_num = version_num.lstrip('=')
                if pkgname in has_comparison:
                    candidates = _available.get(pkgname, [])
                    target = salt.utils.pkg.match_version(
                        version_num,
                        candidates,
                        cmp_func=version_cmp,
                        ignore_epoch=ignore_epoch,
                    )
                    if target is None:
                        errors.append(
                            'No version matching \'{0}{1}\' could be found '
                            '(available: {2})'.format(
                                pkgname,
                                version_num,
                                ', '.join(candidates) if candidates else None
                            )
                        )
                        continue
                    else:
                        version_num = target
                pkgstr = '{0}={1}'.format(pkgname, version_num)
            else:
                pkgstr = pkgpath

            cver = old.get(pkgname, '')
            if reinstall and cver \
                    and salt.utils.versions.compare(ver1=version_num,
                                                    oper='==',
                                                    ver2=cver,
                                                    cmp_func=version_cmp):
                to_reinstall[pkgname] = pkgstr
            elif not cver or salt.utils.versions.compare(ver1=version_num,
                                                         oper='>=',
                                                         ver2=cver,
                                                         cmp_func=version_cmp):
                targets.append(pkgstr)
            else:
                downgrade.append(pkgstr)

    if fromrepo and not sources:
        log.info('Targeting repo \'%s\'', fromrepo)

    cmds = []
    all_pkgs = []
    if targets:
        all_pkgs.extend(targets)
        cmd = copy.deepcopy(cmd_prefix)
        cmd.extend(targets)
        cmds.append(cmd)

    if downgrade:
        cmd = copy.deepcopy(cmd_prefix)
        if pkg_type == 'repository' and '--force-yes' not in cmd:
            # Downgrading requires --force-yes. Insert this before 'install'
            cmd.insert(-1, '--force-yes')
        cmd.extend(downgrade)
        cmds.append(cmd)

    if to_reinstall:
        all_pkgs.extend(to_reinstall)
        cmd = copy.deepcopy(cmd_prefix)
        if not sources:
            cmd.append('--reinstall')
        cmd.extend([x for x in six.itervalues(to_reinstall)])
        cmds.append(cmd)

    if not cmds:
        ret = {}
    else:
        cache_valid_time = kwargs.pop('cache_valid_time', 0)
        if _refresh_db:
            refresh_db(cache_valid_time)

        env = _parse_env(kwargs.get('env'))
        env.update(DPKG_ENV_VARS.copy())

        hold_pkgs = get_selections(state='hold').get('hold', [])
        # all_pkgs contains the argument to be passed to apt-get install, which
        # when a specific version is requested will be in the format
        # name=version.  Strip off the '=' if present so we can compare the
        # held package names against the pacakges we are trying to install.
        targeted_names = [x.split('=')[0] for x in all_pkgs]
        to_unhold = [x for x in hold_pkgs if x in targeted_names]

        if to_unhold:
            unhold(pkgs=to_unhold)

        for cmd in cmds:
            out = __salt__['cmd.run_all'](cmd,
                                          output_loglevel='trace',
                                          python_shell=False)
            if out['retcode'] != 0 and out['stderr']:
                errors.append(out['stderr'])

        __context__.pop('pkg.list_pkgs', None)
        new = list_pkgs()
        ret = salt.utils.data.compare_dicts(old, new)

        for pkgname in to_reinstall:
            if pkgname not in ret or pkgname in old:
                ret.update({pkgname: {'old': old.get(pkgname, ''),
                                      'new': new.get(pkgname, '')}})

        if to_unhold:
            hold(pkgs=to_unhold)

    if errors:
        raise CommandExecutionError(
            'Problem encountered installing package(s)',
            info={'errors': errors, 'changes': ret}
        )

    return ret


def _uninstall(action='remove', name=None, pkgs=None, **kwargs):
    '''
    remove and purge do identical things but with different apt-get commands,
    this function performs the common logic.
    '''
    try:
        pkg_params = __salt__['pkg_resource.parse_targets'](name, pkgs)[0]
    except MinionError as exc:
        raise CommandExecutionError(exc)

    old = list_pkgs()
    old_removed = list_pkgs(removed=True)
    targets = [x for x in pkg_params if x in old]
    if action == 'purge':
        targets.extend([x for x in pkg_params if x in old_removed])
    if not targets:
        return {}
    cmd = []
    if salt.utils.systemd.has_scope(__context__) \
            and __salt__['config.get']('systemd.scope', True):
        cmd.extend(['systemd-run', '--scope'])
    cmd.extend(['apt-get', '-q', '-y', action])
    cmd.extend(targets)
    env = _parse_env(kwargs.get('env'))
    env.update(DPKG_ENV_VARS.copy())
    out = __salt__['cmd.run_all'](
        cmd,
        env=env,
        output_loglevel='trace',
        python_shell=False,
    )
    if out['retcode'] != 0 and out['stderr']:
        errors = [out['stderr']]
    else:
        errors = []

    __context__.pop('pkg.list_pkgs', None)
    new = list_pkgs()
    new_removed = list_pkgs(removed=True)

    changes = salt.utils.data.compare_dicts(old, new)
    if action == 'purge':
        ret = {
            'removed': salt.utils.data.compare_dicts(old_removed, new_removed),
            'installed': changes
        }
    else:
        ret = changes

    if errors:
        raise CommandExecutionError(
            'Problem encountered removing package(s)',
            info={'errors': errors, 'changes': ret}
        )

    return ret


def autoremove(list_only=False, purge=False):
    '''
    .. versionadded:: 2015.5.0

    Remove packages not required by another package using ``apt-get
    autoremove``.

    list_only : False
        Only retrieve the list of packages to be auto-removed, do not actually
        perform the auto-removal.

    purge : False
        Also remove package config data when autoremoving packages.

        .. versionadded:: 2015.8.0

    CLI Example:

    .. code-block:: bash

        salt '*' pkg.autoremove
        salt '*' pkg.autoremove list_only=True
        salt '*' pkg.autoremove purge=True
    '''
    cmd = []
    if salt.utils.systemd.has_scope(__context__) \
            and __salt__['config.get']('systemd.scope', True):
        cmd.extend(['systemd-run', '--scope'])
    if list_only:
        ret = []
        cmd.extend(['apt-get', '--assume-no'])
        if purge:
            cmd.append('--purge')
        cmd.append('autoremove')
        out = __salt__['cmd.run'](cmd, python_shell=False, ignore_retcode=True)
        found = False
        for line in out.splitlines():
            if found is True:
                if line.startswith(' '):
                    ret.extend(line.split())
                else:
                    found = False
            elif 'The following packages will be REMOVED:' in line:
                found = True
        ret.sort()
        return ret
    else:
        old = list_pkgs()
        cmd.extend(['apt-get', '--assume-yes'])
        if purge:
            cmd.append('--purge')
        cmd.append('autoremove')
        __salt__['cmd.run'](cmd, python_shell=False)
        __context__.pop('pkg.list_pkgs', None)
        new = list_pkgs()
        return salt.utils.data.compare_dicts(old, new)


def remove(name=None, pkgs=None, **kwargs):
    '''
    .. versionchanged:: 2015.8.12,2016.3.3,2016.11.0
        On minions running systemd>=205, `systemd-run(1)`_ is now used to
        isolate commands which modify installed packages from the
        ``salt-minion`` daemon's control group. This is done to keep systemd
        from killing any apt-get/dpkg commands spawned by Salt when the
        ``salt-minion`` service is restarted. (see ``KillMode`` in the
        `systemd.kill(5)`_ manpage for more information). If desired, usage of
        `systemd-run(1)`_ can be suppressed by setting a :mod:`config option
        <salt.modules.config.get>` called ``systemd.scope``, with a value of
        ``False`` (no quotes).

    .. _`systemd-run(1)`: https://www.freedesktop.org/software/systemd/man/systemd-run.html
    .. _`systemd.kill(5)`: https://www.freedesktop.org/software/systemd/man/systemd.kill.html

    Remove packages using ``apt-get remove``.

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
    return _uninstall(action='remove', name=name, pkgs=pkgs, **kwargs)


def purge(name=None, pkgs=None, **kwargs):
    '''
    .. versionchanged:: 2015.8.12,2016.3.3,2016.11.0
        On minions running systemd>=205, `systemd-run(1)`_ is now used to
        isolate commands which modify installed packages from the
        ``salt-minion`` daemon's control group. This is done to keep systemd
        from killing any apt-get/dpkg commands spawned by Salt when the
        ``salt-minion`` service is restarted. (see ``KillMode`` in the
        `systemd.kill(5)`_ manpage for more information). If desired, usage of
        `systemd-run(1)`_ can be suppressed by setting a :mod:`config option
        <salt.modules.config.get>` called ``systemd.scope``, with a value of
        ``False`` (no quotes).

    .. _`systemd-run(1)`: https://www.freedesktop.org/software/systemd/man/systemd-run.html
    .. _`systemd.kill(5)`: https://www.freedesktop.org/software/systemd/man/systemd.kill.html

    Remove packages via ``apt-get purge`` along with all configuration files.

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
    return _uninstall(action='purge', name=name, pkgs=pkgs, **kwargs)


def upgrade(refresh=True, dist_upgrade=False, **kwargs):
    '''
    .. versionchanged:: 2015.8.12,2016.3.3,2016.11.0
        On minions running systemd>=205, `systemd-run(1)`_ is now used to
        isolate commands which modify installed packages from the
        ``salt-minion`` daemon's control group. This is done to keep systemd
        from killing any apt-get/dpkg commands spawned by Salt when the
        ``salt-minion`` service is restarted. (see ``KillMode`` in the
        `systemd.kill(5)`_ manpage for more information). If desired, usage of
        `systemd-run(1)`_ can be suppressed by setting a :mod:`config option
        <salt.modules.config.get>` called ``systemd.scope``, with a value of
        ``False`` (no quotes).

    .. _`systemd-run(1)`: https://www.freedesktop.org/software/systemd/man/systemd-run.html
    .. _`systemd.kill(5)`: https://www.freedesktop.org/software/systemd/man/systemd.kill.html

    Upgrades all packages via ``apt-get upgrade`` or ``apt-get dist-upgrade``
    if  ``dist_upgrade`` is ``True``.

    Returns a dictionary containing the changes:

    .. code-block:: python

        {'<package>':  {'old': '<old-version>',
                        'new': '<new-version>'}}

    dist_upgrade
        Whether to perform the upgrade using dist-upgrade vs upgrade.  Default
        is to use upgrade.

        .. versionadded:: 2014.7.0

    cache_valid_time

        .. versionadded:: 2016.11.0

        Skip refreshing the package database if refresh has already occurred within
        <value> seconds

    download_only
        Only donwload the packages, don't unpack or install them

        .. versionadded:: 2018.3.0

    force_conf_new
        Always install the new version of any configuration files.

        .. versionadded:: 2015.8.0

    CLI Example:

    .. code-block:: bash

        salt '*' pkg.upgrade
    '''
    cache_valid_time = kwargs.pop('cache_valid_time', 0)
    if salt.utils.data.is_true(refresh):
        refresh_db(cache_valid_time)

    old = list_pkgs()
    if 'force_conf_new' in kwargs and kwargs['force_conf_new']:
        force_conf = '--force-confnew'
    else:
        force_conf = '--force-confold'
    cmd = []
    if salt.utils.systemd.has_scope(__context__) \
            and __salt__['config.get']('systemd.scope', True):
        cmd.extend(['systemd-run', '--scope'])

    cmd.extend(['apt-get', '-q', '-y',
                '-o', 'DPkg::Options::={0}'.format(force_conf),
                '-o', 'DPkg::Options::=--force-confdef'])

    if kwargs.get('force_yes', False):
        cmd.append('--force-yes')
    if kwargs.get('skip_verify', False):
        cmd.append('--allow-unauthenticated')
    if kwargs.get('download_only', False):
        cmd.append('--download-only')

    cmd.append('dist-upgrade' if dist_upgrade else 'upgrade')

    result = __salt__['cmd.run_all'](cmd,
                                     output_loglevel='trace',
                                     python_shell=False,
                                     env=DPKG_ENV_VARS.copy())
    __context__.pop('pkg.list_pkgs', None)
    new = list_pkgs()
    ret = salt.utils.data.compare_dicts(old, new)

    if result['retcode'] != 0:
        raise CommandExecutionError(
            'Problem encountered upgrading packages',
            info={'changes': ret, 'result': result}
        )

    return ret


def hold(name=None, pkgs=None, sources=None, **kwargs):  # pylint: disable=W0613
    '''
    .. versionadded:: 2014.7.0

    Set package in 'hold' state, meaning it will not be upgraded.

    name
        The name of the package, e.g., 'tmux'

        CLI Example:

        .. code-block:: bash

            salt '*' pkg.hold <package name>

    pkgs
        A list of packages to hold. Must be passed as a python list.

        CLI Example:

        .. code-block:: bash

            salt '*' pkg.hold pkgs='["foo", "bar"]'
    '''
    if not name and not pkgs and not sources:
        raise SaltInvocationError(
            'One of name, pkgs, or sources must be specified.'
        )
    if pkgs and sources:
        raise SaltInvocationError(
            'Only one of pkgs or sources can be specified.'
        )

    targets = []
    if pkgs:
        targets.extend(pkgs)
    elif sources:
        for source in sources:
            targets.append(next(iter(source)))
    else:
        targets.append(name)

    ret = {}
    for target in targets:
        if isinstance(target, dict):
            target = next(iter(target))

        ret[target] = {'name': target,
                       'changes': {},
                       'result': False,
                       'comment': ''}

        state = get_selections(pattern=target, state='hold')
        if not state:
            ret[target]['comment'] = ('Package {0} not currently held.'
                                      .format(target))
        elif not salt.utils.data.is_true(state.get('hold', False)):
            if 'test' in __opts__ and __opts__['test']:
                ret[target].update(result=None)
                ret[target]['comment'] = ('Package {0} is set to be held.'
                                          .format(target))
            else:
                result = set_selections(selection={'hold': [target]})
                ret[target].update(changes=result[target], result=True)
                ret[target]['comment'] = ('Package {0} is now being held.'
                                          .format(target))
        else:
            ret[target].update(result=True)
            ret[target]['comment'] = ('Package {0} is already set to be held.'
                                      .format(target))
    return ret


def unhold(name=None, pkgs=None, sources=None, **kwargs):  # pylint: disable=W0613
    '''
    .. versionadded:: 2014.7.0

    Set package current in 'hold' state to install state,
    meaning it will be upgraded.

    name
        The name of the package, e.g., 'tmux'

        CLI Example:

        .. code-block:: bash

            salt '*' pkg.unhold <package name>

    pkgs
        A list of packages to hold. Must be passed as a python list.

        CLI Example:

        .. code-block:: bash

            salt '*' pkg.unhold pkgs='["foo", "bar"]'
    '''
    if not name and not pkgs and not sources:
        raise SaltInvocationError(
            'One of name, pkgs, or sources must be specified.'
        )
    if pkgs and sources:
        raise SaltInvocationError(
            'Only one of pkgs or sources can be specified.'
        )

    targets = []
    if pkgs:
        targets.extend(pkgs)
    elif sources:
        for source in sources:
            targets.append(next(iter(source)))
    else:
        targets.append(name)

    ret = {}
    for target in targets:
        if isinstance(target, dict):
            target = next(iter(target))

        ret[target] = {'name': target,
                       'changes': {},
                       'result': False,
                       'comment': ''}

        state = get_selections(pattern=target)
        if not state:
            ret[target]['comment'] = ('Package {0} does not have a state.'
                                      .format(target))
        elif salt.utils.data.is_true(state.get('hold', False)):
            if 'test' in __opts__ and __opts__['test']:
                ret[target].update(result=None)
                ret[target]['comment'] = ('Package {0} is set not to be '
                                          'held.'.format(target))
            else:
                result = set_selections(selection={'install': [target]})
                ret[target].update(changes=result[target], result=True)
                ret[target]['comment'] = ('Package {0} is no longer being '
                                          'held.'.format(target))
        else:
            ret[target].update(result=True)
            ret[target]['comment'] = ('Package {0} is already set not to be '
                                      'held.'.format(target))
    return ret


def _clean_pkglist(pkgs):
    '''
    Go through package list and, if any packages have more than one virtual
    package marker and no actual package versions, remove all virtual package
    markers. If there is a mix of actual package versions and virtual package
    markers, remove the virtual package markers.
    '''
    for name, versions in six.iteritems(pkgs):
        stripped = [v for v in versions if v != '1']
        if not stripped:
            pkgs[name] = ['1']
        elif versions != stripped:
            pkgs[name] = stripped


def list_pkgs(versions_as_list=False,
              removed=False,
              purge_desired=False,
              **kwargs):  # pylint: disable=W0613
    '''
    List the packages currently installed in a dict::

        {'<package_name>': '<version>'}

    removed
        If ``True``, then only packages which have been removed (but not
        purged) will be returned.

    purge_desired
        If ``True``, then only packages which have been marked to be purged,
        but can't be purged due to their status as dependencies for other
        installed packages, will be returned. Note that these packages will
        appear in installed

        .. versionchanged:: 2014.1.1

            Packages in this state now correctly show up in the output of this
            function.

    .. note:: External dependencies

        Virtual package resolution requires the ``dctrl-tools`` package to be
        installed. Virtual packages will show a version of ``1``.

    CLI Example:

    .. code-block:: bash

        salt '*' pkg.list_pkgs
        salt '*' pkg.list_pkgs versions_as_list=True
    '''
    versions_as_list = salt.utils.data.is_true(versions_as_list)
    removed = salt.utils.data.is_true(removed)
    purge_desired = salt.utils.data.is_true(purge_desired)

    if 'pkg.list_pkgs' in __context__:
        if removed:
            ret = copy.deepcopy(__context__['pkg.list_pkgs']['removed'])
        else:
            ret = copy.deepcopy(__context__['pkg.list_pkgs']['purge_desired'])
            if not purge_desired:
                ret.update(__context__['pkg.list_pkgs']['installed'])
        if not versions_as_list:
            __salt__['pkg_resource.stringify'](ret)
        return ret

    ret = {'installed': {}, 'removed': {}, 'purge_desired': {}}
    cmd = ['dpkg-query', '--showformat',
           '${Status} ${Package} ${Version} ${Architecture}\n', '-W']

    out = __salt__['cmd.run_stdout'](
            cmd,
            output_loglevel='trace',
            python_shell=False)
    # Typical lines of output:
    # install ok installed zsh 4.3.17-1ubuntu1 amd64
    # deinstall ok config-files mc 3:4.8.1-2ubuntu1 amd64
    for line in out.splitlines():
        cols = line.split()
        try:
            linetype, status, name, version_num, arch = \
                [cols[x] for x in (0, 2, 3, 4, 5)]
        except (ValueError, IndexError):
            continue
        if __grains__.get('cpuarch', '') == 'x86_64':
            osarch = __grains__.get('osarch', '')
            if arch != 'all' and osarch == 'amd64' and osarch != arch:
                name += ':{0}'.format(arch)
        if len(cols):
            if ('install' in linetype or 'hold' in linetype) and \
                    'installed' in status:
                __salt__['pkg_resource.add_pkg'](ret['installed'],
                                                 name,
                                                 version_num)
            elif 'deinstall' in linetype:
                __salt__['pkg_resource.add_pkg'](ret['removed'],
                                                 name,
                                                 version_num)
            elif 'purge' in linetype and status == 'installed':
                __salt__['pkg_resource.add_pkg'](ret['purge_desired'],
                                                 name,
                                                 version_num)

    # Check for virtual packages. We need dctrl-tools for this.
    if not removed and not HAS_APT:
        try:
            virtpkgs_all = _get_virtual()
        except CommandExecutionError as cee:
            raise CommandExecutionError(cee)
        virtpkgs = set()
        for realpkg, provides in six.iteritems(virtpkgs_all):
            # grep-available returns info on all virtual packages. Ignore any
            # virtual packages that do not have the real package installed.
            if realpkg in ret['installed']:
                virtpkgs.update(provides)
        for virtname in virtpkgs:
            # Set virtual package versions to '1'
            __salt__['pkg_resource.add_pkg'](ret['installed'], virtname, '1')

    for pkglist_type in ('installed', 'removed', 'purge_desired'):
        __salt__['pkg_resource.sort_pkglist'](ret[pkglist_type])
        _clean_pkglist(ret[pkglist_type])

    __context__['pkg.list_pkgs'] = copy.deepcopy(ret)

    if removed:
        ret = ret['removed']
    else:
        ret = copy.deepcopy(__context__['pkg.list_pkgs']['purge_desired'])
        if not purge_desired:
            ret.update(__context__['pkg.list_pkgs']['installed'])
    if not versions_as_list:
        __salt__['pkg_resource.stringify'](ret)
    return ret


def _get_upgradable(dist_upgrade=True, **kwargs):
    '''
    Utility function to get upgradable packages

    Sample return data:
    { 'pkgname': '1.2.3-45', ... }
    '''

    cmd = ['apt-get', '--just-print']
    if dist_upgrade:
        cmd.append('dist-upgrade')
    else:
        cmd.append('upgrade')
    try:
        cmd.extend(['-o', 'APT::Default-Release={0}'.format(kwargs['fromrepo'])])
    except KeyError:
        pass

    call = __salt__['cmd.run_all'](cmd,
                                   python_shell=False,
                                   output_loglevel='trace')

    if call['retcode'] != 0:
        msg = 'Failed to get upgrades'
        for key in ('stderr', 'stdout'):
            if call[key]:
                msg += ': ' + call[key]
                break
        raise CommandExecutionError(msg)
    else:
        out = call['stdout']

    # rexp parses lines that look like the following:
    # Conf libxfont1 (1:1.4.5-1 Debian:testing [i386])
    rexp = re.compile('(?m)^Conf '
                      '([^ ]+) '          # Package name
                      r'\(([^ ]+)')       # Version
    keys = ['name', 'version']
    _get = lambda l, k: l[keys.index(k)]

    upgrades = rexp.findall(out)

    ret = {}
    for line in upgrades:
        name = _get(line, 'name')
        version_num = _get(line, 'version')
        ret[name] = version_num

    return ret


def list_upgrades(refresh=True, dist_upgrade=True, **kwargs):
    '''
    List all available package upgrades.

    refresh
        Whether to refresh the package database before listing upgrades.
        Default: True.

    cache_valid_time

        .. versionadded:: 2016.11.0

        Skip refreshing the package database if refresh has already occurred within
        <value> seconds

    dist_upgrade
        Whether to list the upgrades using dist-upgrade vs upgrade.  Default is
        to use dist-upgrade.

    CLI Example:

    .. code-block:: bash

        salt '*' pkg.list_upgrades
    '''
    cache_valid_time = kwargs.pop('cache_valid_time', 0)
    if salt.utils.data.is_true(refresh):
        refresh_db(cache_valid_time)
    return _get_upgradable(dist_upgrade, **kwargs)


def upgrade_available(name):
    '''
    Check whether or not an upgrade is available for a given package

    CLI Example:

    .. code-block:: bash

        salt '*' pkg.upgrade_available <package name>
    '''
    return latest_version(name) != ''


def version_cmp(pkg1, pkg2, ignore_epoch=False):
    '''
    Do a cmp-style comparison on two packages. Return -1 if pkg1 < pkg2, 0 if
    pkg1 == pkg2, and 1 if pkg1 > pkg2. Return None if there was a problem
    making the comparison.

    ignore_epoch : False
        Set to ``True`` to ignore the epoch when comparing versions

        .. versionadded:: 2015.8.10,2016.3.2

    CLI Example:

    .. code-block:: bash

        salt '*' pkg.version_cmp '0.2.4-0ubuntu1' '0.2.4.1-0ubuntu1'
    '''
    normalize = lambda x: six.text_type(x).split(':', 1)[-1] \
                if ignore_epoch else six.text_type(x)
    # both apt_pkg.version_compare and _cmd_quote need string arguments.
    pkg1 = normalize(pkg1)
    pkg2 = normalize(pkg2)

    # if we have apt_pkg, this will be quickier this way
    # and also do not rely on shell.
    if HAS_APTPKG:
        try:
            # the apt_pkg module needs to be manually initialized
            apt_pkg.init_system()

            # if there is a difference in versions, apt_pkg.version_compare will
            # return an int representing the difference in minor versions, or
            # 1/-1 if the difference is smaller than minor versions. normalize
            # to -1, 0 or 1.
            try:
                ret = apt_pkg.version_compare(pkg1, pkg2)
            except TypeError:
                ret = apt_pkg.version_compare(six.text_type(pkg1), six.text_type(pkg2))
            return 1 if ret > 0 else -1 if ret < 0 else 0
        except Exception:
            # Try to use shell version in case of errors w/python bindings
            pass
    try:
        for oper, ret in (('lt', -1), ('eq', 0), ('gt', 1)):
            cmd = ['dpkg', '--compare-versions', pkg1, oper, pkg2]
            retcode = __salt__['cmd.retcode'](cmd,
                                              output_loglevel='trace',
                                              python_shell=False,
                                              ignore_retcode=True)
            if retcode == 0:
                return ret
    except Exception as exc:
        log.error(exc)
    return None


def _split_repo_str(repo):
    '''
    Return APT source entry as a tuple.
    '''
    split = sourceslist.SourceEntry(repo)
    return split.type, split.uri, split.dist, split.comps


def _consolidate_repo_sources(sources):
    '''
    Consolidate APT sources.
    '''
    if not isinstance(sources, sourceslist.SourcesList):
        raise TypeError(
            '\'{0}\' not a \'{1}\''.format(
                type(sources),
                sourceslist.SourcesList
            )
        )

    consolidated = {}
    delete_files = set()
    base_file = sourceslist.SourceEntry('').file

    repos = [s for s in sources.list if not s.invalid]

    for repo in repos:
        repo.uri = repo.uri.rstrip('/')
        # future lint: disable=blacklisted-function
        key = str((getattr(repo, 'architectures', []),
                   repo.disabled, repo.type, repo.uri, repo.dist))
        # future lint: enable=blacklisted-function
        if key in consolidated:
            combined = consolidated[key]
            combined_comps = set(repo.comps).union(set(combined.comps))
            consolidated[key].comps = list(combined_comps)
        else:
            consolidated[key] = sourceslist.SourceEntry(salt.utils.pkg.deb.strip_uri(repo.line))

        if repo.file != base_file:
            delete_files.add(repo.file)

    sources.list = list(consolidated.values())
    sources.save()
    for file_ in delete_files:
        try:
            os.remove(file_)
        except OSError:
            pass
    return sources


def list_repo_pkgs(*args, **kwargs):  # pylint: disable=unused-import
    '''
    .. versionadded:: 2017.7.0

    Returns all available packages. Optionally, package names (and name globs)
    can be passed and the results will be filtered to packages matching those
    names.

    This function can be helpful in discovering the version or repo to specify
    in a :mod:`pkg.installed <salt.states.pkg.installed>` state.

    The return data will be a dictionary mapping package names to a list of
    version numbers, ordered from newest to oldest. For example:

    .. code-block:: python

        {
            'bash': ['4.3-14ubuntu1.1',
                     '4.3-14ubuntu1'],
            'nginx': ['1.10.0-0ubuntu0.16.04.4',
                      '1.9.15-0ubuntu1']
        }

    CLI Examples:

    .. code-block:: bash

        salt '*' pkg.list_repo_pkgs
        salt '*' pkg.list_repo_pkgs foo bar baz
    '''
    out = __salt__['cmd.run_all'](
        ['apt-cache', 'dump'],
        output_loglevel='trace',
        ignore_retcode=True,
        python_shell=False
    )

    ret = {}
    pkg_name = None
    skip_pkg = False
    new_pkg = re.compile('^Package: (.+)')
    for line in salt.utils.itertools.split(out['stdout'], '\n'):
        try:
            cur_pkg = new_pkg.match(line).group(1)
        except AttributeError:
            pass
        else:
            if cur_pkg != pkg_name:
                pkg_name = cur_pkg
                if args:
                    for arg in args:
                        if fnmatch.fnmatch(pkg_name, arg):
                            skip_pkg = False
                            break
                    else:
                        # Package doesn't match any of the passed args, skip it
                        skip_pkg = True
                else:
                    # No args passed, we're getting all packages
                    skip_pkg = False
                continue
        if not skip_pkg:
            comps = line.strip().split(None, 1)
            if comps[0] == 'Version:':
                ret.setdefault(pkg_name, []).append(comps[1])

    return ret


def list_repos():
    '''
    Lists all repos in the sources.list (and sources.lists.d) files

    CLI Example:

    .. code-block:: bash

       salt '*' pkg.list_repos
       salt '*' pkg.list_repos disabled=True
    '''
    _check_apt()
    repos = {}
    sources = sourceslist.SourcesList()
    for source in sources.list:
        if source.invalid:
            continue
        repo = {}
        repo['file'] = source.file
        repo['comps'] = getattr(source, 'comps', [])
        repo['disabled'] = source.disabled
        repo['dist'] = source.dist
        repo['type'] = source.type
        repo['uri'] = source.uri.rstrip('/')
        repo['line'] = salt.utils.pkg.deb.strip_uri(source.line.strip())
        repo['architectures'] = getattr(source, 'architectures', [])
        repos.setdefault(source.uri, []).append(repo)
    return repos


def get_repo(repo, **kwargs):
    '''
    Display a repo from the sources.list / sources.list.d

    The repo passed in needs to be a complete repo entry.

    CLI Examples:

    .. code-block:: bash

        salt '*' pkg.get_repo "myrepo definition"
    '''
    _check_apt()
    ppa_auth = kwargs.get('ppa_auth', None)
    # we have to be clever about this since the repo definition formats
    # are a bit more "loose" than in some other distributions
    if repo.startswith('ppa:') and __grains__['os'] in ('Ubuntu', 'Mint', 'neon'):
        # This is a PPA definition meaning special handling is needed
        # to derive the name.
        dist = __grains__['lsb_distrib_codename']
        owner_name, ppa_name = repo[4:].split('/')
        if ppa_auth:
            auth_info = '{0}@'.format(ppa_auth)
            repo = LP_PVT_SRC_FORMAT.format(auth_info, owner_name,
                                            ppa_name, dist)
        else:
            if HAS_SOFTWAREPROPERTIES:
                try:
                    if hasattr(softwareproperties.ppa, 'PPAShortcutHandler'):
                        repo = softwareproperties.ppa.PPAShortcutHandler(
                            repo).expand(dist)[0]
                    else:
                        repo = softwareproperties.ppa.expand_ppa_line(
                            repo,
                            dist)[0]
                except NameError as name_error:
                    raise CommandExecutionError(
                        'Could not find ppa {0}: {1}'.format(repo, name_error)
                    )
            else:
                repo = LP_SRC_FORMAT.format(owner_name, ppa_name, dist)

    repos = list_repos()

    if repos:
        try:
            repo_type, repo_uri, repo_dist, repo_comps = _split_repo_str(repo)
            if ppa_auth:
                uri_match = re.search('(http[s]?://)(.+)', repo_uri)
                if uri_match:
                    if not uri_match.group(2).startswith(ppa_auth):
                        repo_uri = '{0}{1}@{2}'.format(uri_match.group(1),
                                                       ppa_auth,
                                                       uri_match.group(2))
        except SyntaxError:
            raise CommandExecutionError(
                'Error: repo \'{0}\' is not a well formatted definition'
                .format(repo)
            )

        for source in six.itervalues(repos):
            for sub in source:
                if (sub['type'] == repo_type and
                    # strip trailing '/' from repo_uri, it's valid in definition
                    # but not valid when compared to persisted source
                    sub['uri'].rstrip('/') == repo_uri.rstrip('/') and
                        sub['dist'] == repo_dist):
                    if not repo_comps:
                        return sub
                    for comp in repo_comps:
                        if comp in sub.get('comps', []):
                            return sub
    return {}


def del_repo(repo, **kwargs):
    '''
    Delete a repo from the sources.list / sources.list.d

    If the .list file is in the sources.list.d directory
    and the file that the repo exists in does not contain any other
    repo configuration, the file itself will be deleted.

    The repo passed in must be a fully formed repository definition
    string.

    CLI Examples:

    .. code-block:: bash

        salt '*' pkg.del_repo "myrepo definition"
    '''
    _check_apt()
    is_ppa = False
    if repo.startswith('ppa:') and __grains__['os'] in ('Ubuntu', 'Mint', 'neon'):
        # This is a PPA definition meaning special handling is needed
        # to derive the name.
        is_ppa = True
        dist = __grains__['lsb_distrib_codename']
        if not HAS_SOFTWAREPROPERTIES:
            _warn_software_properties(repo)
            owner_name, ppa_name = repo[4:].split('/')
            if 'ppa_auth' in kwargs:
                auth_info = '{0}@'.format(kwargs['ppa_auth'])
                repo = LP_PVT_SRC_FORMAT.format(auth_info, dist, owner_name,
                                                ppa_name)
            else:
                repo = LP_SRC_FORMAT.format(owner_name, ppa_name, dist)
        else:
            if hasattr(softwareproperties.ppa, 'PPAShortcutHandler'):
                repo = softwareproperties.ppa.PPAShortcutHandler(repo).expand(dist)[0]
            else:
                repo = softwareproperties.ppa.expand_ppa_line(repo, dist)[0]

    sources = sourceslist.SourcesList()
    repos = [s for s in sources.list if not s.invalid]
    if repos:
        deleted_from = dict()
        try:
            repo_type, repo_uri, repo_dist, repo_comps = _split_repo_str(repo)
        except SyntaxError:
            raise SaltInvocationError(
                'Error: repo \'{0}\' not a well formatted definition'
                .format(repo)
            )

        for source in repos:
            if (source.type == repo_type and source.uri == repo_uri and
                    source.dist == repo_dist):

                s_comps = set(source.comps)
                r_comps = set(repo_comps)
                if s_comps.intersection(r_comps):
                    deleted_from[source.file] = 0
                    source.comps = list(s_comps.difference(r_comps))
                    if not source.comps:
                        try:
                            sources.remove(source)
                        except ValueError:
                            pass
            # PPAs are special and can add deb-src where expand_ppa_line
            # doesn't always reflect this.  Lets just cleanup here for good
            # measure
            if (is_ppa and repo_type == 'deb' and source.type == 'deb-src' and
                    source.uri == repo_uri and source.dist == repo_dist):

                s_comps = set(source.comps)
                r_comps = set(repo_comps)
                if s_comps.intersection(r_comps):
                    deleted_from[source.file] = 0
                    source.comps = list(s_comps.difference(r_comps))
                    if not source.comps:
                        try:
                            sources.remove(source)
                        except ValueError:
                            pass
            sources.save()
        if deleted_from:
            ret = ''
            for source in sources:
                if source.file in deleted_from:
                    deleted_from[source.file] += 1
            for repo_file, count in six.iteritems(deleted_from):
                msg = 'Repo \'{0}\' has been removed from {1}.\n'
                if count == 0 and 'sources.list.d/' in repo_file:
                    if os.path.isfile(repo_file):
                        msg = ('File {1} containing repo \'{0}\' has been '
                               'removed.')
                        try:
                            os.remove(repo_file)
                        except OSError:
                            pass
                ret += msg.format(repo, repo_file)
            # explicit refresh after a repo is deleted
            refresh_db()
            return ret

    raise CommandExecutionError(
        'Repo {0} doesn\'t exist in the sources.list(s)'.format(repo)
    )


def _convert_if_int(value):
    '''
    .. versionadded:: 2017.7.0

    Convert to an int if necessary.

    :param str value: The value to check/convert.

    :return: The converted or passed value.
    :rtype: bool|int|str
    '''
    try:
        value = int(str(value))  # future lint: disable=blacklisted-function
    except ValueError:
        pass
    return value


def get_repo_keys():
    '''
    .. versionadded:: 2017.7.0

    List known repo key details.

    :return: A dictionary containing the repo keys.
    :rtype: dict

    CLI Examples:

    .. code-block:: bash

        salt '*' pkg.get_repo_keys
    '''
    ret = dict()
    repo_keys = list()

    # The double usage of '--with-fingerprint' is necessary in order to
    # retrieve the fingerprint of the subkey.
    cmd = ['apt-key', 'adv', '--list-public-keys', '--with-fingerprint',
           '--with-fingerprint', '--with-colons', '--fixed-list-mode']

    cmd_ret = __salt__['cmd.run_all'](cmd=cmd)

    if cmd_ret['retcode'] != 0:
        log.error(cmd_ret['stderr'])
        return ret

    lines = [line for line in cmd_ret['stdout'].splitlines() if line.strip()]

    # Reference for the meaning of each item in the colon-separated
    # record can be found here: https://goo.gl/KIZbvp
    for line in lines:
        items = [_convert_if_int(item.strip()) if item.strip() else None for item in line.split(':')]
        key_props = dict()

        if len(items) < 2:
            log.debug('Skipping line: %s', line)
            continue

        if items[0] in ('pub', 'sub'):
            key_props.update({
                'algorithm': items[3],
                'bits': items[2],
                'capability': items[11],
                'date_creation': items[5],
                'date_expiration': items[6],
                'keyid': items[4],
                'validity': items[1]
            })

            if items[0] == 'pub':
                repo_keys.append(key_props)
            else:
                repo_keys[-1]['subkey'] = key_props
        elif items[0] == 'fpr':
            if repo_keys[-1].get('subkey', False):
                repo_keys[-1]['subkey'].update({'fingerprint': items[9]})
            else:
                repo_keys[-1].update({'fingerprint': items[9]})
        elif items[0] == 'uid':
            repo_keys[-1].update({
                'uid': items[9],
                'uid_hash': items[7]
            })

    for repo_key in repo_keys:
        ret[repo_key['keyid']] = repo_key
    return ret


def add_repo_key(path=None, text=None, keyserver=None, keyid=None, saltenv='base'):
    '''
    .. versionadded:: 2017.7.0

    Add a repo key using ``apt-key add``.

    :param str path: The path of the key file to import.
    :param str text: The key data to import, in string form.
    :param str keyserver: The server to download the repo key specified by the keyid.
    :param str keyid: The key id of the repo key to add.
    :param str saltenv: The environment the key file resides in.

    :return: A boolean representing whether the repo key was added.
    :rtype: bool

    CLI Examples:

    .. code-block:: bash

        salt '*' pkg.add_repo_key 'salt://apt/sources/test.key'

        salt '*' pkg.add_repo_key text="'$KEY1'"

        salt '*' pkg.add_repo_key keyserver='keyserver.example' keyid='0000AAAA'
    '''
    cmd = ['apt-key']
    kwargs = {'python_shell': False}

    current_repo_keys = get_repo_keys()

    if path:
        cached_source_path = __salt__['cp.cache_file'](path, saltenv)

        if not cached_source_path:
            log.error('Unable to get cached copy of file: %s', path)
            return False

        cmd.extend(['add', cached_source_path])
    elif text:
        log.debug('Received value: %s', text)

        cmd.extend(['add', '-'])
        kwargs.update({'stdin': text})
    elif keyserver:
        if not keyid:
            error_msg = 'No keyid or keyid too short for keyserver: {0}'.format(keyserver)
            raise SaltInvocationError(error_msg)

        cmd.extend(['adv', '--keyserver', keyserver, '--recv', keyid])
    elif keyid:
        error_msg = 'No keyserver specified for keyid: {0}'.format(keyid)
        raise SaltInvocationError(error_msg)
    else:
        raise TypeError('{0}() takes at least 1 argument (0 given)'.format(add_repo_key.__name__))

    # If the keyid is provided or determined, check it against the existing
    # repo key ids to determine whether it needs to be imported.
    if keyid:
        for current_keyid in current_repo_keys:
            if current_keyid[-(len(keyid)):] == keyid:
                log.debug("The keyid '%s' already present: %s", keyid, current_keyid)
                return True

    kwargs.update({'cmd': cmd})
    cmd_ret = __salt__['cmd.run_all'](**kwargs)

    if cmd_ret['retcode'] == 0:
        return True
    log.error('Unable to add repo key: %s', cmd_ret['stderr'])
    return False


def del_repo_key(name=None, **kwargs):
    '''
    .. versionadded:: 2015.8.0

    Remove a repo key using ``apt-key del``

    name
        Repo from which to remove the key. Unnecessary if ``keyid`` is passed.

    keyid
        The KeyID of the GPG key to remove

    keyid_ppa : False
        If set to ``True``, the repo's GPG key ID will be looked up from
        ppa.launchpad.net and removed.

        .. note::

            Setting this option to ``True`` requires that the ``name`` param
            also be passed.

    CLI Examples:

    .. code-block:: bash

        salt '*' pkg.del_repo_key keyid=0123ABCD
        salt '*' pkg.del_repo_key name='ppa:foo/bar' keyid_ppa=True
    '''
    if kwargs.get('keyid_ppa', False):
        if isinstance(name, six.string_types) and name.startswith('ppa:'):
            owner_name, ppa_name = name[4:].split('/')
            ppa_info = _get_ppa_info_from_launchpad(
                owner_name, ppa_name)
            keyid = ppa_info['signing_key_fingerprint'][-8:]
        else:
            raise SaltInvocationError(
                'keyid_ppa requires that a PPA be passed'
            )
    else:
        if 'keyid' in kwargs:
            keyid = kwargs.get('keyid')
        else:
            raise SaltInvocationError(
                'keyid or keyid_ppa and PPA name must be passed'
            )

    cmd = ['apt-key', 'del', keyid]
    result = __salt__['cmd.run_all'](cmd, python_shell=False)
    if result['retcode'] != 0:
        msg = 'Failed to remove keyid {0}'
        if result['stderr']:
            msg += ': {0}'.format(result['stderr'])
        raise CommandExecutionError(msg)
    return keyid


def mod_repo(repo, saltenv='base', **kwargs):
    '''
    Modify one or more values for a repo.  If the repo does not exist, it will
    be created, so long as the definition is well formed.  For Ubuntu the
    ``ppa:<project>/repo`` format is acceptable. ``ppa:`` format can only be
    used to create a new repository.

    The following options are available to modify a repo definition:

    architectures
        A comma-separated list of supported architectures, e.g. ``amd64`` If
        this option is not set, all architectures (configured in the system)
        will be used.

    comps
        A comma separated list of components for the repo, e.g. ``main``

    file
        A file name to be used

    keyserver
        Keyserver to get gpg key from

    keyid
        Key ID to load with the ``keyserver`` argument

    key_url
        URL to a GPG key to add to the APT GPG keyring

    key_text
        GPG key in string form to add to the APT GPG keyring

        .. versionadded:: 2018.3.0

    consolidate : False
        If ``True``, will attempt to de-duplicate and consolidate sources

    comments
        Sometimes you want to supply additional information, but not as
        enabled configuration. All comments provided here will be joined
        into a single string and appended to the repo configuration with a
        comment marker (#) before it.

        .. versionadded:: 2015.8.9

    .. note::
        Due to the way keys are stored for APT, there is a known issue where
        the key won't be updated unless another change is made at the same
        time. Keys should be properly added on initial configuration.

    CLI Examples:

    .. code-block:: bash

        salt '*' pkg.mod_repo 'myrepo definition' uri=http://new/uri
        salt '*' pkg.mod_repo 'myrepo definition' comps=main,universe
    '''
    if 'refresh_db' in kwargs:
        salt.utils.versions.warn_until(
            'Neon',
            'The \'refresh_db\' argument to \'pkg.mod_repo\' has been '
            'renamed to \'refresh\'. Support for using \'refresh_db\' will be '
            'removed in the Neon release of Salt.'
        )
        refresh = kwargs['refresh_db']
    else:
        refresh = kwargs.get('refresh', True)

    _check_apt()
    # to ensure no one sets some key values that _shouldn't_ be changed on the
    # object itself, this is just a white-list of "ok" to set properties
    if repo.startswith('ppa:'):
        if __grains__['os'] in ('Ubuntu', 'Mint', 'neon'):
            # secure PPAs cannot be supported as of the time of this code
            # implementation via apt-add-repository.  The code path for
            # secure PPAs should be the same as urllib method
            if salt.utils.path.which('apt-add-repository') \
                    and 'ppa_auth' not in kwargs:
                repo_info = get_repo(repo)
                if repo_info:
                    return {repo: repo_info}
                else:
                    if float(__grains__['osrelease']) < 12.04:
                        cmd = ['apt-add-repository', repo]
                    else:
                        cmd = ['apt-add-repository', '-y', repo]
                    out = __salt__['cmd.run_all'](cmd,
                                                  python_shell=False,
                                                  **kwargs)
                    if out['retcode']:
                        raise CommandExecutionError(
                            'Unable to add PPA \'{0}\'. \'{1}\' exited with '
                            'status {2!s}: \'{3}\' '.format(
                                repo[4:],
                                cmd,
                                out['retcode'],
                                out['stderr']
                            )
                        )
                    # explicit refresh when a repo is modified.
                    if refresh:
                        refresh_db()
                    return {repo: out}
            else:
                if not HAS_SOFTWAREPROPERTIES:
                    _warn_software_properties(repo)
                else:
                    log.info('Falling back to urllib method for private PPA')

                # fall back to urllib style
                try:
                    owner_name, ppa_name = repo[4:].split('/', 1)
                except ValueError:
                    raise CommandExecutionError(
                        'Unable to get PPA info from argument. '
                        'Expected format "<PPA_OWNER>/<PPA_NAME>" '
                        '(e.g. saltstack/salt) not found.  Received '
                        '\'{0}\' instead.'.format(repo[4:])
                    )
                dist = __grains__['lsb_distrib_codename']
                # ppa has a lot of implicit arguments. Make them explicit.
                # These will defer to any user-defined variants
                kwargs['dist'] = dist
                ppa_auth = ''
                if 'file' not in kwargs:
                    filename = '/etc/apt/sources.list.d/{0}-{1}-{2}.list'
                    kwargs['file'] = filename.format(owner_name, ppa_name,
                                                     dist)
                try:
                    launchpad_ppa_info = _get_ppa_info_from_launchpad(
                        owner_name, ppa_name)
                    if 'ppa_auth' not in kwargs:
                        kwargs['keyid'] = launchpad_ppa_info[
                            'signing_key_fingerprint']
                    else:
                        if 'keyid' not in kwargs:
                            error_str = 'Private PPAs require a ' \
                                        'keyid to be specified: {0}/{1}'
                            raise CommandExecutionError(
                                error_str.format(owner_name, ppa_name)
                            )
                except HTTPError as exc:
                    raise CommandExecutionError(
                        'Launchpad does not know about {0}/{1}: {2}'.format(
                            owner_name, ppa_name, exc)
                    )
                except IndexError as exc:
                    raise CommandExecutionError(
                        'Launchpad knows about {0}/{1} but did not '
                        'return a fingerprint. Please set keyid '
                        'manually: {2}'.format(owner_name, ppa_name, exc)
                    )

                if 'keyserver' not in kwargs:
                    kwargs['keyserver'] = 'keyserver.ubuntu.com'
                if 'ppa_auth' in kwargs:
                    if not launchpad_ppa_info['private']:
                        raise CommandExecutionError(
                            'PPA is not private but auth credentials '
                            'passed: {0}'.format(repo)
                        )
                # assign the new repo format to the "repo" variable
                # so we can fall through to the "normal" mechanism
                # here.
                if 'ppa_auth' in kwargs:
                    ppa_auth = '{0}@'.format(kwargs['ppa_auth'])
                    repo = LP_PVT_SRC_FORMAT.format(ppa_auth, owner_name,
                                                    ppa_name, dist)
                else:
                    repo = LP_SRC_FORMAT.format(owner_name, ppa_name, dist)
        else:
            raise CommandExecutionError(
                'cannot parse "ppa:" style repo definitions: {0}'
                .format(repo)
            )

    sources = sourceslist.SourcesList()
    if kwargs.get('consolidate', False):
        # attempt to de-dup and consolidate all sources
        # down to entries in sources.list
        # this option makes it easier to keep the sources
        # list in a "sane" state.
        #
        # this should remove duplicates, consolidate comps
        # for a given source down to one line
        # and eliminate "invalid" and comment lines
        #
        # the second side effect is removal of files
        # that are not the main sources.list file
        sources = _consolidate_repo_sources(sources)

    repos = [s for s in sources if not s.invalid]
    mod_source = None
    try:
        repo_type, repo_uri, repo_dist, repo_comps = _split_repo_str(repo)
    except SyntaxError:
        raise SyntaxError(
            'Error: repo \'{0}\' not a well formatted definition'.format(repo)
        )

    full_comp_list = set(repo_comps)

    if 'keyid' in kwargs:
        keyid = kwargs.pop('keyid', None)
        keyserver = kwargs.pop('keyserver', None)
        if not keyid or not keyserver:
            error_str = 'both keyserver and keyid options required.'
            raise NameError(error_str)
        if isinstance(keyid, int):  # yaml can make this an int, we need the hex version
            keyid = hex(keyid)
        cmd = ['apt-key', 'export', keyid]
        output = __salt__['cmd.run_stdout'](cmd, python_shell=False, **kwargs)
        imported = output.startswith('-----BEGIN PGP')
        if keyserver:
            if not imported:
                http_proxy_url = _get_http_proxy_url()
                if http_proxy_url:
                    cmd = ['apt-key', 'adv', '--keyserver-options', 'http-proxy={0}'.format(http_proxy_url),
                           '--keyserver', keyserver, '--logger-fd', '1', '--recv-keys', keyid]
                else:
                    cmd = ['apt-key', 'adv', '--keyserver', keyserver,
                           '--logger-fd', '1', '--recv-keys', keyid]
                ret = __salt__['cmd.run_all'](cmd,
                                              python_shell=False,
                                              **kwargs)
                if ret['retcode'] != 0:
                    raise CommandExecutionError(
                        'Error: key retrieval failed: {0}'.format(ret['stdout'])
                    )

    elif 'key_url' in kwargs:
        key_url = kwargs['key_url']
        fn_ = __salt__['cp.cache_file'](key_url, saltenv)
        if not fn_:
            raise CommandExecutionError(
                'Error: file not found: {0}'.format(key_url)
            )
        cmd = ['apt-key', 'add', fn_]
        out = __salt__['cmd.run_stdout'](cmd, python_shell=False, **kwargs)
        if not out.upper().startswith('OK'):
            raise CommandExecutionError(
                'Error: failed to add key from {0}'.format(key_url)
            )

    elif 'key_text' in kwargs:
        key_text = kwargs['key_text']
        cmd = ['apt-key', 'add', '-']
        out = __salt__['cmd.run_stdout'](cmd, stdin=key_text,
                                         python_shell=False, **kwargs)
        if not out.upper().startswith('OK'):
            raise CommandExecutionError(
                'Error: failed to add key:\n{0}'.format(key_text)
            )

    if 'comps' in kwargs:
        kwargs['comps'] = kwargs['comps'].split(',')
        full_comp_list |= set(kwargs['comps'])
    else:
        kwargs['comps'] = list(full_comp_list)

    if 'architectures' in kwargs:
        kwargs['architectures'] = kwargs['architectures'].split(',')

    if 'disabled' in kwargs:
        kwargs['disabled'] = salt.utils.data.is_true(kwargs['disabled'])

    kw_type = kwargs.get('type')
    kw_dist = kwargs.get('dist')

    for source in repos:
        # This series of checks will identify the starting source line
        # and the resulting source line.  The idea here is to ensure
        # we are not returning bogus data because the source line
        # has already been modified on a previous run.
        repo_matches = source.type == repo_type and source.uri == repo_uri and source.dist == repo_dist
        kw_matches = source.dist == kw_dist and source.type == kw_type

        if repo_matches or kw_matches:
            for comp in full_comp_list:
                if comp in getattr(source, 'comps', []):
                    mod_source = source
            if not source.comps:
                mod_source = source
            if mod_source:
                break

    if 'comments' in kwargs:
        kwargs['comments'] = \
            salt.utils.pkg.deb.combine_comments(kwargs['comments'])

    if not mod_source:
        mod_source = sourceslist.SourceEntry(repo)
        if 'comments' in kwargs:
            mod_source.comment = kwargs['comments']
        sources.list.append(mod_source)
    elif 'comments' in kwargs:
        mod_source.comment = kwargs['comments']

    for key in kwargs:
        if key in _MODIFY_OK and hasattr(mod_source, key):
            setattr(mod_source, key, kwargs[key])
    sources.save()
    # on changes, explicitly refresh
    if refresh:
        refresh_db()
    return {
        repo: {
            'architectures': getattr(mod_source, 'architectures', []),
            'comps': mod_source.comps,
            'disabled': mod_source.disabled,
            'file': mod_source.file,
            'type': mod_source.type,
            'uri': mod_source.uri,
            'line': mod_source.line
        }
    }


def file_list(*packages):
    '''
    List the files that belong to a package. Not specifying any packages will
    return a list of _every_ file on the system's package database (not
    generally recommended).

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
    specifying any packages will return a list of _every_ file on the system's
    package database (not generally recommended).

    CLI Examples:

    .. code-block:: bash

        salt '*' pkg.file_dict httpd
        salt '*' pkg.file_dict httpd postfix
        salt '*' pkg.file_dict
    '''
    return __salt__['lowpkg.file_dict'](*packages)


def expand_repo_def(**kwargs):
    '''
    Take a repository definition and expand it to the full pkg repository dict
    that can be used for comparison.  This is a helper function to make
    the Debian/Ubuntu apt sources sane for comparison in the pkgrepo states.

    This is designed to be called from pkgrepo states and will have little use
    being called on the CLI.
    '''
    if 'repo' not in kwargs:
        raise SaltInvocationError('missing \'repo\' argument')

    _check_apt()

    sanitized = {}
    repo = salt.utils.pkg.deb.strip_uri(kwargs['repo'])
    if repo.startswith('ppa:') and __grains__['os'] in ('Ubuntu', 'Mint', 'neon'):
        dist = __grains__['lsb_distrib_codename']
        owner_name, ppa_name = repo[4:].split('/', 1)
        if 'ppa_auth' in kwargs:
            auth_info = '{0}@'.format(kwargs['ppa_auth'])
            repo = LP_PVT_SRC_FORMAT.format(auth_info, owner_name, ppa_name,
                                            dist)
        else:
            if HAS_SOFTWAREPROPERTIES:
                if hasattr(softwareproperties.ppa, 'PPAShortcutHandler'):
                    repo = softwareproperties.ppa.PPAShortcutHandler(repo).expand(dist)[0]
                else:
                    repo = softwareproperties.ppa.expand_ppa_line(repo, dist)[0]
            else:
                repo = LP_SRC_FORMAT.format(owner_name, ppa_name, dist)

        if 'file' not in kwargs:
            filename = '/etc/apt/sources.list.d/{0}-{1}-{2}.list'
            kwargs['file'] = filename.format(owner_name, ppa_name, dist)

    source_entry = sourceslist.SourceEntry(repo)
    for list_args in ('architectures', 'comps'):
        if list_args in kwargs:
            kwargs[list_args] = kwargs[list_args].split(',')
    for kwarg in _MODIFY_OK:
        if kwarg in kwargs:
            setattr(source_entry, kwarg, kwargs[kwarg])

    sanitized['file'] = source_entry.file
    sanitized['comps'] = getattr(source_entry, 'comps', [])
    sanitized['disabled'] = source_entry.disabled
    sanitized['dist'] = source_entry.dist
    sanitized['type'] = source_entry.type
    sanitized['uri'] = source_entry.uri.rstrip('/')
    sanitized['line'] = source_entry.line.strip()
    sanitized['architectures'] = getattr(source_entry, 'architectures', [])

    return sanitized


def _parse_selections(dpkgselection):
    '''
    Parses the format from ``dpkg --get-selections`` and return a format that
    pkg.get_selections and pkg.set_selections work with.
    '''
    ret = {}
    if isinstance(dpkgselection, six.string_types):
        dpkgselection = dpkgselection.split('\n')
    for line in dpkgselection:
        if line:
            _pkg, _state = line.split()
            if _state in ret:
                ret[_state].append(_pkg)
            else:
                ret[_state] = [_pkg]
    return ret


def get_selections(pattern=None, state=None):
    '''
    View package state from the dpkg database.

    Returns a dict of dicts containing the state, and package names:

    .. code-block:: python

        {'<host>':
            {'<state>': ['pkg1',
                         ...
                        ]
            },
            ...
        }

    CLI Example:

    .. code-block:: bash

        salt '*' pkg.get_selections
        salt '*' pkg.get_selections 'python-*'
        salt '*' pkg.get_selections state=hold
        salt '*' pkg.get_selections 'openssh*' state=hold
    '''
    ret = {}
    cmd = ['dpkg', '--get-selections']
    cmd.append(pattern if pattern else '*')
    stdout = __salt__['cmd.run_stdout'](cmd,
                                        output_loglevel='trace',
                                        python_shell=False)
    ret = _parse_selections(stdout)
    if state:
        return {state: ret.get(state, [])}
    return ret


# TODO: allow state=None to be set, and that *args will be set to that state
# TODO: maybe use something similar to pkg_resources.pack_pkgs to allow a list
# passed to selection, with the default state set to whatever is passed by the
# above, but override that if explicitly specified
# TODO: handle path to selection file from local fs as well as from salt file
# server
def set_selections(path=None, selection=None, clear=False, saltenv='base'):
    '''
    Change package state in the dpkg database.

    The state can be any one of, documented in ``dpkg(1)``:

    - install
    - hold
    - deinstall
    - purge

    This command is commonly used to mark specific packages to be held from
    being upgraded, that is, to be kept at a certain version. When a state is
    changed to anything but being held, then it is typically followed by
    ``apt-get -u dselect-upgrade``.

    Note: Be careful with the ``clear`` argument, since it will start
    with setting all packages to deinstall state.

    Returns a dict of dicts containing the package names, and the new and old
    versions:

    .. code-block:: python

        {'<host>':
            {'<package>': {'new': '<new-state>',
                           'old': '<old-state>'}
            },
            ...
        }

    CLI Example:

    .. code-block:: bash

        salt '*' pkg.set_selections selection='{"install": ["netcat"]}'
        salt '*' pkg.set_selections selection='{"hold": ["openssh-server", "openssh-client"]}'
        salt '*' pkg.set_selections salt://path/to/file
        salt '*' pkg.set_selections salt://path/to/file clear=True
    '''
    ret = {}
    if not path and not selection:
        return ret
    if path and selection:
        err = ('The \'selection\' and \'path\' arguments to '
               'pkg.set_selections are mutually exclusive, and cannot be '
               'specified together')
        raise SaltInvocationError(err)

    if isinstance(selection, six.string_types):
        try:
            selection = salt.utils.yaml.safe_load(selection)
        except (salt.utils.yaml.parser.ParserError, salt.utils.yaml.scanner.ScannerError) as exc:
            raise SaltInvocationError(
                'Improperly-formatted selection: {0}'.format(exc)
            )

    if path:
        path = __salt__['cp.cache_file'](path, saltenv)
        with salt.utils.files.fopen(path, 'r') as ifile:
            content = [salt.utils.stringutils.to_unicode(x)
                       for x in ifile.readlines()]
        selection = _parse_selections(content)

    if selection:
        valid_states = ('install', 'hold', 'deinstall', 'purge')
        bad_states = [x for x in selection if x not in valid_states]
        if bad_states:
            raise SaltInvocationError(
                'Invalid state(s): {0}'.format(', '.join(bad_states))
            )

        if clear:
            cmd = 'dpkg --clear-selections'
            if not __opts__['test']:
                result = __salt__['cmd.run_all'](cmd, output_loglevel='trace')
                if result['retcode'] != 0:
                    err = ('Running dpkg --clear-selections failed: '
                           '{0}'.format(result['stderr']))
                    log.error(err)
                    raise CommandExecutionError(err)

        sel_revmap = {}
        for _state, _pkgs in six.iteritems(get_selections()):
            sel_revmap.update(dict((_pkg, _state) for _pkg in _pkgs))

        for _state, _pkgs in six.iteritems(selection):
            for _pkg in _pkgs:
                if _state == sel_revmap.get(_pkg):
                    continue
                cmd = 'dpkg --set-selections'
                cmd_in = '{0} {1}'.format(_pkg, _state)
                if not __opts__['test']:
                    result = __salt__['cmd.run_all'](cmd,
                                                     stdin=cmd_in,
                                                     output_loglevel='trace')
                    if result['retcode'] != 0:
                        log.error(
                            'failed to set state %s for package %s',
                            _state, _pkg
                        )
                    else:
                        ret[_pkg] = {'old': sel_revmap.get(_pkg),
                                     'new': _state}
    return ret


def _resolve_deps(name, pkgs, **kwargs):
    '''
    Installs missing dependencies and marks them as auto installed so they
    are removed when no more manually installed packages depend on them.

    .. versionadded:: 2014.7.0

    :depends:   - python-apt module
    '''
    missing_deps = []
    for pkg_file in pkgs:
        deb = apt.debfile.DebPackage(filename=pkg_file, cache=apt.Cache())
        if deb.check():
            missing_deps.extend(deb.missing_deps)

    if missing_deps:
        cmd = ['apt-get', '-q', '-y']
        cmd = cmd + ['-o', 'DPkg::Options::=--force-confold']
        cmd = cmd + ['-o', 'DPkg::Options::=--force-confdef']
        cmd.append('install')
        cmd.extend(missing_deps)

        ret = __salt__['cmd.retcode'](
            cmd,
            env=kwargs.get('env'),
            python_shell=False
        )

        if ret != 0:
            raise CommandExecutionError(
                'Error: unable to resolve dependencies for: {0}'.format(name)
            )
        else:
            try:
                cmd = ['apt-mark', 'auto'] + missing_deps
                __salt__['cmd.run'](
                    cmd,
                    env=kwargs.get('env'),
                    python_shell=False
                )
            except MinionError as exc:
                raise CommandExecutionError(exc)
    return


def owner(*paths):
    '''
    .. versionadded:: 2014.7.0

    Return the name of the package that owns the file. Multiple file paths can
    be passed. Like :mod:`pkg.version <salt.modules.aptpkg.version>`, if a
    single path is passed, a string will be returned, and if multiple paths are
    passed, a dictionary of file/package name pairs will be returned.

    If the file is not owned by a package, or is not present on the minion,
    then an empty string will be returned for that path.

    CLI Example:

    .. code-block:: bash

        salt '*' pkg.owner /usr/bin/apachectl
        salt '*' pkg.owner /usr/bin/apachectl /usr/bin/basename
    '''
    if not paths:
        return ''
    ret = {}
    for path in paths:
        cmd = ['dpkg', '-S', path]
        output = __salt__['cmd.run_stdout'](cmd,
                                            output_loglevel='trace',
                                            python_shell=False)
        ret[path] = output.split(':')[0]
        if 'no path found' in ret[path].lower():
            ret[path] = ''
    if len(ret) == 1:
        return next(six.itervalues(ret))
    return ret


def info_installed(*names, **kwargs):
    '''
    Return the information of the named package(s) installed on the system.

    .. versionadded:: 2015.8.1

    names
        The names of the packages for which to return information.

    failhard
        Whether to throw an exception if none of the packages are installed.
        Defaults to True.

        .. versionadded:: 2016.11.3

    CLI example:

    .. code-block:: bash

        salt '*' pkg.info_installed <package1>
        salt '*' pkg.info_installed <package1> <package2> <package3> ...
        salt '*' pkg.info_installed <package1> failhard=false
    '''
    kwargs = salt.utils.args.clean_kwargs(**kwargs)
    failhard = kwargs.pop('failhard', True)
    if kwargs:
        salt.utils.args.invalid_kwargs(kwargs)

    ret = dict()
    for pkg_name, pkg_nfo in __salt__['lowpkg.info'](*names, failhard=failhard).items():
        t_nfo = dict()
        # Translate dpkg-specific keys to a common structure
        for key, value in pkg_nfo.items():
            if key == 'package':
                t_nfo['name'] = value
            elif key == 'origin':
                t_nfo['vendor'] = value
            elif key == 'section':
                t_nfo['group'] = value
            elif key == 'maintainer':
                t_nfo['packager'] = value
            elif key == 'homepage':
                t_nfo['url'] = value
            else:
                t_nfo[key] = value

        ret[pkg_name] = t_nfo

    return ret


def _get_http_proxy_url():
    '''
    Returns the http_proxy_url if proxy_username, proxy_password, proxy_host, and proxy_port
    config values are set.

    Returns a string.
    '''
    http_proxy_url = ''
    host = __salt__['config.option']('proxy_host')
    port = __salt__['config.option']('proxy_port')
    username = __salt__['config.option']('proxy_username')
    password = __salt__['config.option']('proxy_password')

    # Set http_proxy_url for use in various internet facing actions...eg apt-key adv
    if host and port:
        if username and password:
            http_proxy_url = 'http://{0}:{1}@{2}:{3}'.format(
                username,
                password,
                host,
                port
            )
        else:
            http_proxy_url = 'http://{0}:{1}'.format(
                host,
                port
            )

    return http_proxy_url
