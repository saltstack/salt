# -*- coding: utf-8 -*-
'''
Support for YUM/DNF

.. important::
    If you feel that Salt should be using this module to manage packages on a
    minion, and it is using a different module (or gives an error similar to
    *'pkg.install' is not available*), see :ref:`here
    <module-provider-override>`.

.. note::
    DNF is fully supported as of version 2015.5.10 and 2015.8.4 (partial
    support for DNF was initially added in 2015.8.0), and DNF is used
    automatically in place of YUM in Fedora 22 and newer.
'''

# Import python libs
from __future__ import absolute_import
import contextlib
import copy
import fnmatch
import itertools
import logging
import os
import re
import string

# pylint: disable=import-error,redefined-builtin
# Import 3rd-party libs
from salt.ext import six
from salt.ext.six.moves import zip

try:
    import yum
    HAS_YUM = True
except ImportError:
    from salt.ext.six.moves import configparser
    HAS_YUM = False
# pylint: enable=import-error,redefined-builtin

# Import salt libs
import salt.utils
import salt.utils.itertools
import salt.utils.systemd
import salt.utils.decorators as decorators
import salt.utils.pkg.rpm
from salt.utils.versions import LooseVersion as _LooseVersion
from salt.exceptions import (
    CommandExecutionError, MinionError, SaltInvocationError
)

log = logging.getLogger(__name__)

__HOLD_PATTERN = r'\w+(?:[.-][^-]+)*'

# Define the module's virtual name
__virtualname__ = 'pkg'


def __virtual__():
    '''
    Confine this module to yum based systems
    '''
    if __opts__.get('yum_provider') == 'yumpkg_api':
        return (False, "Module yumpkg: yumpkg_api provider not available")
    try:
        os_grain = __grains__['os'].lower()
        os_family = __grains__['os_family'].lower()
    except Exception:
        return (False, "Module yumpkg: no yum based system detected")

    enabled = ('amazon', 'xcp', 'xenserver', 'virtuozzolinux', 'virtuozzo')

    if os_family == 'redhat' or os_grain in enabled:
        return __virtualname__
    return (False, "Module yumpkg: no yum based system detected")


def _strip_headers(output, *args):
    if not args:
        args_lc = ('installed packages',
                   'available packages',
                   'updated packages',
                   'upgraded packages')
    else:
        args_lc = [x.lower() for x in args]
    ret = ''
    for line in salt.utils.itertools.split(output, '\n'):
        if line.lower() not in args_lc:
            ret += line + '\n'
    return ret


def _get_hold(line, pattern=__HOLD_PATTERN, full=True):
    '''
    Resolve a package name from a line containing the hold expression. If the
    regex is not matched, None is returned.

    yum ==> 2:vim-enhanced-7.4.629-5.el6.*
    dnf ==> vim-enhanced-2:7.4.827-1.fc22.*
    '''
    if full:
        if _yum() == 'dnf':
            lock_re = r'({0}-\S+)'.format(pattern)
        else:
            lock_re = r'(\d+:{0}-\S+)'.format(pattern)
    else:
        if _yum() == 'dnf':
            lock_re = r'({0}-\S+)'.format(pattern)
        else:
            lock_re = r'\d+:({0}-\S+)'.format(pattern)

    match = re.search(lock_re, line)
    if match:
        if not full:
            woarch = match.group(1).rsplit('.', 1)[0]
            worel = woarch.rsplit('-', 1)[0]
            return worel.rsplit('-', 1)[0]
        else:
            return match.group(1)
    return None


def _yum():
    '''
    return yum or dnf depending on version
    '''
    contextkey = 'yum_bin'
    if contextkey not in __context__:
        if 'fedora' in __grains__['os'].lower() \
                and int(__grains__['osrelease']) >= 22:
            __context__[contextkey] = 'dnf'
        else:
            __context__[contextkey] = 'yum'
    return __context__[contextkey]


def _yum_pkginfo(output):
    '''
    Parse yum/dnf output (which could contain irregular line breaks if package
    names are long) retrieving the name, version, etc., and return a list of
    pkginfo namedtuples.
    '''
    cur = {}
    keys = itertools.cycle(('name', 'version', 'repoid'))
    values = salt.utils.itertools.split(_strip_headers(output))
    osarch = __grains__['osarch']
    for (key, value) in zip(keys, values):
        if key == 'name':
            try:
                cur['name'], cur['arch'] = value.rsplit('.', 1)
            except ValueError:
                cur['name'] = value
                cur['arch'] = osarch
            cur['name'] = salt.utils.pkg.rpm.resolve_name(cur['name'],
                                                          cur['arch'],
                                                          osarch)
        else:
            if key == 'version':
                # Suppport packages with no 'Release' parameter
                value = value.rstrip('-')
            elif key == 'repoid':
                # Installed packages show a '@' at the beginning
                value = value.lstrip('@')
            cur[key] = value
            if key == 'repoid':
                # We're done with this package, create the pkginfo namedtuple
                pkginfo = salt.utils.pkg.rpm.pkginfo(**cur)
                # Clear the dict for the next package
                cur = {}
                # Yield the namedtuple
                if pkginfo is not None:
                    yield pkginfo


def _check_versionlock():
    '''
    Ensure that the appropriate versionlock plugin is present
    '''
    if _yum() == 'dnf':
        vl_plugin = 'python-dnf-plugins-extras-versionlock'
    else:
        vl_plugin = 'yum-versionlock' \
            if __grains__.get('osmajorrelease') == '5' \
            else 'yum-plugin-versionlock'

    if vl_plugin not in list_pkgs():
        raise SaltInvocationError(
            'Cannot proceed, {0} is not installed.'.format(vl_plugin)
        )


def _get_repo_options(**kwargs):
    '''
    Returns a list of '--enablerepo' and '--disablerepo' options to be used
    in the yum command, based on the kwargs.
    '''
    # Get repo options from the kwargs
    fromrepo = kwargs.get('fromrepo', '')
    repo = kwargs.get('repo', '')
    disablerepo = kwargs.get('disablerepo', '')
    enablerepo = kwargs.get('enablerepo', '')

    # Support old 'repo' argument
    if repo and not fromrepo:
        fromrepo = repo

    ret = []
    if fromrepo:
        log.info('Restricting to repo \'%s\'', fromrepo)
        ret.extend(['--disablerepo=*', '--enablerepo=' + fromrepo])
    else:
        if disablerepo:
            targets = [disablerepo] \
                if not isinstance(disablerepo, list) \
                else disablerepo
            log.info('Disabling repo(s): %s', ', '.join(targets))
            ret.extend(
                ['--disablerepo={0}'.format(x) for x in targets]
            )
        if enablerepo:
            targets = [enablerepo] \
                if not isinstance(enablerepo, list) \
                else enablerepo
            log.info('Enabling repo(s): %s', ', '.join(targets))
            ret.extend(['--enablerepo={0}'.format(x) for x in targets])
    return ret


def _get_excludes_option(**kwargs):
    '''
    Returns a list of '--disableexcludes' option to be used in the yum command,
    based on the kwargs.
    '''
    disable_excludes = kwargs.get('disableexcludes', '')
    ret = []
    if disable_excludes:
        log.info('Disabling excludes for \'%s\'', disable_excludes)
        ret.append('--disableexcludes={0}'.format(disable_excludes))
    return ret


def _get_branch_option(**kwargs):
    '''
    Returns a list of '--branch' option to be used in the yum command,
    based on the kwargs. This feature requires 'branch' plugin for YUM.
    '''
    branch = kwargs.get('branch', '')
    ret = []
    if branch:
        log.info('Adding branch \'%s\'', branch)
        ret.append('--branch=\'{0}\''.format(branch))
    return ret


def _get_yum_config():
    '''
    Returns a dict representing the yum config options and values.

    We try to pull all of the yum config options into a standard dict object.
    This is currently only used to get the reposdir settings, but could be used
    for other things if needed.

    If the yum python library is available, use that, which will give us all of
    the options, including all of the defaults not specified in the yum config.
    Additionally, they will all be of the correct object type.

    If the yum library is not available, we try to read the yum.conf
    directly ourselves with a minimal set of "defaults".
    '''
    # in case of any non-fatal failures, these defaults will be used
    conf = {
        'reposdir': ['/etc/yum/repos.d', '/etc/yum.repos.d'],
    }

    if HAS_YUM:
        try:
            yb = yum.YumBase()
            yb.preconf.init_plugins = False
            for name, value in six.iteritems(yb.conf):
                conf[name] = value
        except (AttributeError, yum.Errors.ConfigError) as exc:
            raise CommandExecutionError(
                'Could not query yum config: {0}'.format(exc)
            )
    else:
        # fall back to parsing the config ourselves
        # Look for the config the same order yum does
        fn = None
        paths = ('/etc/yum/yum.conf', '/etc/yum.conf', '/etc/dnf/dnf.conf')
        for path in paths:
            if os.path.exists(path):
                fn = path
                break

        if not fn:
            raise CommandExecutionError(
                'No suitable yum config file found in: {0}'.format(paths)
            )

        cp = configparser.ConfigParser()
        try:
            cp.read(fn)
        except (IOError, OSError) as exc:
            raise CommandExecutionError(
                'Unable to read from {0}: {1}'.format(fn, exc)
            )

        if cp.has_section('main'):
            for opt in cp.options('main'):
                if opt in ('reposdir', 'commands', 'excludes'):
                    # these options are expected to be lists
                    conf[opt] = [x.strip()
                                 for x in cp.get('main', opt).split(',')]
                else:
                    conf[opt] = cp.get('main', opt)
        else:
            log.warning(
                'Could not find [main] section in %s, using internal '
                'defaults',
                fn
            )

    return conf


def _get_yum_config_value(name):
    '''
    Look for a specific config variable and return its value
    '''
    conf = _get_yum_config()
    if name in conf.keys():
        return conf.get(name)
    return None


def _normalize_basedir(basedir=None):
    '''
    Takes a basedir argument as a string or a list. If the string or list is
    empty, then look up the default from the 'reposdir' option in the yum
    config.

    Returns a list of directories.
    '''
    # if we are passed a string (for backward compatibility), convert to a list
    if isinstance(basedir, six.string_types):
        basedir = [x.strip() for x in basedir.split(',')]

    if basedir is None:
        basedir = []

    # nothing specified, so use the reposdir option as the default
    if not basedir:
        basedir = _get_yum_config_value('reposdir')

    if not isinstance(basedir, list) or not basedir:
        raise SaltInvocationError('Could not determine any repo directories')

    return basedir


def normalize_name(name):
    '''
    Strips the architecture from the specified package name, if necessary.
    Circumstances where this would be done include:

    * If the arch is 32 bit and the package name ends in a 32-bit arch.
    * If the arch matches the OS arch, or is ``noarch``.

    CLI Example:

    .. code-block:: bash

        salt '*' pkg.normalize_name zsh.x86_64
    '''
    try:
        arch = name.rsplit('.', 1)[-1]
        if arch not in salt.utils.pkg.rpm.ARCHES + ('noarch',):
            return name
    except ValueError:
        return name
    if arch in (__grains__['osarch'], 'noarch') \
            or salt.utils.pkg.rpm.check_32(arch, osarch=__grains__['osarch']):
        return name[:-(len(arch) + 1)]
    return name


def latest_version(*names, **kwargs):
    '''
    Return the latest version of the named package available for upgrade or
    installation. If more than one package name is specified, a dict of
    name/version pairs is returned.

    If the latest version of a given package is already installed, an empty
    string will be returned for that package.

    A specific repo can be requested using the ``fromrepo`` keyword argument,
    and the ``disableexcludes`` option is also supported.

    .. versionadded:: 2014.7.0
        Support for the ``disableexcludes`` option

    CLI Example:

    .. code-block:: bash

        salt '*' pkg.latest_version <package name>
        salt '*' pkg.latest_version <package name> fromrepo=epel-testing
        salt '*' pkg.latest_version <package name> disableexcludes=main
        salt '*' pkg.latest_version <package1> <package2> <package3> ...
    '''
    refresh = salt.utils.is_true(kwargs.pop('refresh', True))
    if len(names) == 0:
        return ''

    repo_arg = _get_repo_options(**kwargs)
    exclude_arg = _get_excludes_option(**kwargs)

    # Refresh before looking for the latest version available
    if refresh:
        refresh_db(**kwargs)

    cur_pkgs = list_pkgs(versions_as_list=True)

    # Get available versions for specified package(s)
    cmd = [_yum(), '--quiet']
    cmd.extend(repo_arg)
    cmd.extend(exclude_arg)
    cmd.extend(['list', 'available'])
    cmd.extend(names)
    out = __salt__['cmd.run_all'](cmd,
                                  output_loglevel='trace',
                                  ignore_retcode=True,
                                  python_shell=False)
    if out['retcode'] != 0:
        if out['stderr']:
            # Check first if this is just a matter of the packages being
            # up-to-date.
            if not all([x in cur_pkgs for x in names]):
                log.error(
                    'Problem encountered getting latest version for the '
                    'following package(s): %s. Stderr follows: \n%s',
                    ', '.join(names),
                    out['stderr']
                )
        updates = []
    else:
        # Sort by version number (highest to lowest) for loop below
        updates = sorted(
            _yum_pkginfo(out['stdout']),
            key=lambda pkginfo: _LooseVersion(pkginfo.version),
            reverse=True
        )

    def _check_cur(pkg):
        if pkg.name in cur_pkgs:
            for installed_version in cur_pkgs[pkg.name]:
                # If any installed version is greater than the one found by
                # yum/dnf list available, then it is not an upgrade.
                if salt.utils.compare_versions(ver1=installed_version,
                                               oper='>',
                                               ver2=pkg.version,
                                               cmp_func=version_cmp):
                    return False
            # pkg.version is greater than all installed versions
            return True
        else:
            # Package is not installed
            return True

    ret = {}
    for name in names:
        # Derive desired pkg arch (for arch-specific packages) based on the
        # package name(s) passed to the function. On a 64-bit OS, "pkgame"
        # would be assumed to match the osarch, while "pkgname.i686" would
        # have an arch of "i686". This desired arch is then compared against
        # the updates derived from _yum_pkginfo() above, so that we can
        # distinguish an update for a 32-bit version of a package from its
        # 64-bit counterpart.
        try:
            arch = name.rsplit('.', 1)[-1]
            if arch not in salt.utils.pkg.rpm.ARCHES:
                arch = __grains__['osarch']
        except ValueError:
            arch = __grains__['osarch']

        # This loop will iterate over the updates derived by _yum_pkginfo()
        # above, which have been sorted descendingly by version number,
        # ensuring that the latest available version for the named package is
        # examined first. The call to _check_cur() will ensure that a package
        # seen by yum as "available" will only be detected as an upgrade if it
        # has a version higher than all currently-installed versions of the
        # package.
        for pkg in (x for x in updates if x.name == name):
            # This if/or statement makes sure that we account for noarch
            # packages as well as arch-specific packages.
            if pkg.arch == 'noarch' or pkg.arch == arch \
                    or salt.utils.pkg.rpm.check_32(pkg.arch):
                if _check_cur(pkg):
                    ret[name] = pkg.version
                    # no need to check another match, if there was one
                    break
        else:
            ret[name] = ''

    # Return a string if only one package name passed
    if len(names) == 1:
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


def version_cmp(pkg1, pkg2, ignore_epoch=False):
    '''
    .. versionadded:: 2015.5.4

    Do a cmp-style comparison on two packages. Return -1 if pkg1 < pkg2, 0 if
    pkg1 == pkg2, and 1 if pkg1 > pkg2. Return None if there was a problem
    making the comparison.

    ignore_epoch : False
        Set to ``True`` to ignore the epoch when comparing versions

        .. versionadded:: 2015.8.10,2016.3.2

    CLI Example:

    .. code-block:: bash

        salt '*' pkg.version_cmp '0.2-001' '0.2.0.1-002'
    '''

    return __salt__['lowpkg.version_cmp'](pkg1, pkg2, ignore_epoch=ignore_epoch)


def list_pkgs(versions_as_list=False, **kwargs):
    '''
    List the packages currently installed in a dict::

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

    ret = {}
    cmd = ['rpm', '-qa', '--queryformat',
           salt.utils.pkg.rpm.QUERYFORMAT.replace('%{REPOID}', '(none)\n')]
    output = __salt__['cmd.run'](cmd,
                                 python_shell=False,
                                 output_loglevel='trace')
    for line in output.splitlines():
        pkginfo = salt.utils.pkg.rpm.parse_pkginfo(
            line,
            osarch=__grains__['osarch']
        )
        if pkginfo is not None:
            __salt__['pkg_resource.add_pkg'](ret,
                                             pkginfo.name,
                                             pkginfo.version)

    __salt__['pkg_resource.sort_pkglist'](ret)
    __context__['pkg.list_pkgs'] = copy.deepcopy(ret)
    if not versions_as_list:
        __salt__['pkg_resource.stringify'](ret)
    return ret


def list_repo_pkgs(*args, **kwargs):
    '''
    .. versionadded:: 2014.1.0
    .. versionchanged:: 2014.7.0
        All available versions of each package are now returned. This required
        a slight modification to the structure of the return dict. The return
        data shown below reflects the updated return dict structure. Note that
        packages which are version-locked using :py:mod:`pkg.hold
        <salt.modules.yumpkg.hold>` will only show the currently-installed
        version, as locking a package will make other versions appear
        unavailable to yum/dnf.
    .. versionchanged:: Nitrogen
        By default, the versions for each package are no longer organized by
        repository. To get results organized by repository, use
        ``byrepo=True``.

    Returns all available packages. Optionally, package names (and name globs)
    can be passed and the results will be filtered to packages matching those
    names. This is recommended as it speeds up the function considerably.

    .. warning::
        Running this function on RHEL/CentOS 6 and earlier will be more
        resource-intensive, as the version of yum that ships with older
        RHEL/CentOS has no yum subcommand for listing packages from a
        repository. Thus, a ``yum list installed`` and ``yum list available``
        are run, which generates a lot of output, which must then be analyzed
        to determine which package information to include in the return data.

    This function can be helpful in discovering the version or repo to specify
    in a :mod:`pkg.installed <salt.states.pkg.installed>` state.

    The return data will be a dictionary mapping package names to a list of
    version numbers, ordered from newest to oldest. If ``byrepo`` is set to
    ``True``, then the return dictionary will contain repository names at the
    top level, and each repository will map packages to lists of version
    numbers. For example:

    .. code-block:: python

        # With byrepo=False (default)
        {
            'bash': ['4.1.2-15.el6_5.2',
                     '4.1.2-15.el6_5.1',
                     '4.1.2-15.el6_4'],
            'kernel': ['2.6.32-431.29.2.el6',
                       '2.6.32-431.23.3.el6',
                       '2.6.32-431.20.5.el6',
                       '2.6.32-431.20.3.el6',
                       '2.6.32-431.17.1.el6',
                       '2.6.32-431.11.2.el6',
                       '2.6.32-431.5.1.el6',
                       '2.6.32-431.3.1.el6',
                       '2.6.32-431.1.2.0.1.el6',
                       '2.6.32-431.el6']
        }
        # With byrepo=True
        {
            'base': {
                'bash': ['4.1.2-15.el6_4'],
                'kernel': ['2.6.32-431.el6']
            },
            'updates': {
                'bash': ['4.1.2-15.el6_5.2', '4.1.2-15.el6_5.1'],
                'kernel': ['2.6.32-431.29.2.el6',
                           '2.6.32-431.23.3.el6',
                           '2.6.32-431.20.5.el6',
                           '2.6.32-431.20.3.el6',
                           '2.6.32-431.17.1.el6',
                           '2.6.32-431.11.2.el6',
                           '2.6.32-431.5.1.el6',
                           '2.6.32-431.3.1.el6',
                           '2.6.32-431.1.2.0.1.el6']
            }
        }

    fromrepo : None
        Only include results from the specified repo(s). Multiple repos can be
        specified, comma-separated.

    enablerepo (ignored if ``fromrepo`` is specified)
        Specify a disabled package repository (or repositories) to enable.
        (e.g., ``yum --enablerepo='somerepo'``)

        .. versionadded:: Nitrogen

    disablerepo (ignored if ``fromrepo`` is specified)
        Specify an enabled package repository (or repositories) to disable.
        (e.g., ``yum --disablerepo='somerepo'``)

        .. versionadded:: Nitrogen

    byrepo : False
        When ``True``, the return data for each package will be organized by
        repository.

        .. versionadded:: Nitrogen

    cacheonly : False
        When ``True``, the repo information will be retrieved from the cached
        repo metadata. This is equivalent to passing the ``-C`` option to
        yum/dnf.

        .. versionadded:: Nitrogen

    CLI Examples:

    .. code-block:: bash

        salt '*' pkg.list_repo_pkgs
        salt '*' pkg.list_repo_pkgs foo bar baz
        salt '*' pkg.list_repo_pkgs 'samba4*' fromrepo=base,updates
        salt '*' pkg.list_repo_pkgs 'python2-*' byrepo=True
    '''
    byrepo = kwargs.pop('byrepo', False)
    cacheonly = kwargs.pop('cacheonly', False)
    fromrepo = kwargs.pop('fromrepo', '') or ''
    disablerepo = kwargs.pop('disablerepo', '') or ''
    enablerepo = kwargs.pop('enablerepo', '') or ''

    repo_arg = _get_repo_options(fromrepo=fromrepo, **kwargs)

    if fromrepo and not isinstance(fromrepo, list):
        try:
            fromrepo = [x.strip() for x in fromrepo.split(',')]
        except AttributeError:
            fromrepo = [x.strip() for x in str(fromrepo).split(',')]

    if disablerepo and not isinstance(disablerepo, list):
        try:
            disablerepo = [x.strip() for x in disablerepo.split(',')
                           if x != '*']
        except AttributeError:
            disablerepo = [x.strip() for x in str(disablerepo).split(',')
                           if x != '*']

    if enablerepo and not isinstance(enablerepo, list):
        try:
            enablerepo = [x.strip() for x in enablerepo.split(',')
                          if x != '*']
        except AttributeError:
            enablerepo = [x.strip() for x in str(enablerepo).split(',')
                          if x != '*']

    if fromrepo:
        repos = fromrepo
    else:
        repos = [
            repo_name for repo_name, repo_info in six.iteritems(list_repos())
            if repo_name in enablerepo
            or (repo_name not in disablerepo
                and str(repo_info.get('enabled', '1')) == '1')
        ]

    ret = {}

    def _check_args(args, name):
        '''
        Do glob matching on args and return True if a match was found.
        Otherwise, return False
        '''
        for arg in args:
            if fnmatch.fnmatch(name, arg):
                return True
        return False

    def _parse_output(output, strict=False):
        for pkg in _yum_pkginfo(output):
            if strict and (pkg.repoid not in repos
                           or not _check_args(args, pkg.name)):
                continue
            repo_dict = ret.setdefault(pkg.repoid, {})
            version_list = repo_dict.setdefault(pkg.name, set())
            version_list.add(pkg.version)

    yum_version = None if _yum() != 'yum' else _LooseVersion(
                __salt__['cmd.run'](
                    ['yum', '--version'],
                    python_shell=False
                ).splitlines()[0].strip()
            )
    # Really old version of yum; does not even have --showduplicates option
    if yum_version and yum_version < _LooseVersion('3.2.13'):
        cmd_prefix = ['yum', '--quiet']
        if cacheonly:
            cmd_prefix.append('-C')
        cmd_prefix.append('list')
        for pkg_src in ('installed', 'available'):
            # Check installed packages first
            out = __salt__['cmd.run_all'](
                cmd_prefix + [pkg_src],
                output_loglevel='trace',
                ignore_retcode=True,
                python_shell=False
            )
            if out['retcode'] == 0:
                _parse_output(out['stdout'], strict=True)
    # The --showduplicates option is added in 3.2.13, but the
    # repository-packages subcommand is only in 3.4.3 and newer
    elif yum_version and yum_version < _LooseVersion('3.4.3'):
        cmd_prefix = ['yum', '--quiet', '--showduplicates']
        if cacheonly:
            cmd_prefix.append('-C')
        cmd_prefix.append('list')
        for pkg_src in ('installed', 'available'):
            # Check installed packages first
            out = __salt__['cmd.run_all'](
                cmd_prefix + [pkg_src],
                output_loglevel='trace',
                ignore_retcode=True,
                python_shell=False
            )
            if out['retcode'] == 0:
                _parse_output(out['stdout'], strict=True)
    else:
        for repo in repos:
            cmd = [_yum(), '--quiet', 'repository-packages', repo,
                   'list', '--showduplicates']
            if cacheonly:
                cmd.append('-C')
            # Can't concatenate because args is a tuple, using list.extend()
            cmd.extend(args)

            out = __salt__['cmd.run_all'](cmd,
                                          output_loglevel='trace',
                                          ignore_retcode=True,
                                          python_shell=False)
            if out['retcode'] != 0 and 'Error:' in out['stdout']:
                continue
            _parse_output(out['stdout'])

    if byrepo:
        for reponame in ret:
            # Sort versions newest to oldest
            for pkgname in ret[reponame]:
                sorted_versions = sorted(
                    [_LooseVersion(x) for x in ret[reponame][pkgname]],
                    reverse=True
                )
                ret[reponame][pkgname] = [x.vstring for x in sorted_versions]
        return ret
    else:
        byrepo_ret = {}
        for reponame in ret:
            for pkgname in ret[reponame]:
                byrepo_ret.setdefault(pkgname, []).extend(ret[reponame][pkgname])
        for pkgname in byrepo_ret:
            sorted_versions = sorted(
                [_LooseVersion(x) for x in byrepo_ret[pkgname]],
                reverse=True
            )
            byrepo_ret[pkgname] = [x.vstring for x in sorted_versions]
        return byrepo_ret


def list_upgrades(refresh=True, **kwargs):
    '''
    Check whether or not an upgrade is available for all packages

    The ``fromrepo``, ``enablerepo``, and ``disablerepo`` arguments are
    supported, as used in pkg states, and the ``disableexcludes`` option is
    also supported.

    .. versionadded:: 2014.7.0
        Support for the ``disableexcludes`` option

    CLI Example:

    .. code-block:: bash

        salt '*' pkg.list_upgrades
    '''
    repo_arg = _get_repo_options(**kwargs)
    exclude_arg = _get_excludes_option(**kwargs)

    if salt.utils.is_true(refresh):
        refresh_db(check_update=False, **kwargs)

    cmd = [_yum(), '--quiet']
    cmd.extend(repo_arg)
    cmd.extend(exclude_arg)
    cmd.extend(['list', 'upgrades' if _yum() == 'dnf' else 'updates'])
    out = __salt__['cmd.run_all'](cmd,
                                  output_loglevel='trace',
                                  ignore_retcode=True,
                                  python_shell=False)
    if out['retcode'] != 0 and 'Error:' in out:
        return {}

    return dict([(x.name, x.version) for x in _yum_pkginfo(out['stdout'])])

# Preserve expected CLI usage (yum list updates)
list_updates = salt.utils.alias_function(list_upgrades, 'list_updates')


def info_installed(*names):
    '''
    .. versionadded:: 2015.8.1

    Return the information of the named package(s), installed on the system.

    CLI example:

    .. code-block:: bash

        salt '*' pkg.info_installed <package1>
        salt '*' pkg.info_installed <package1> <package2> <package3> ...
    '''
    ret = dict()
    for pkg_name, pkg_nfo in __salt__['lowpkg.info'](*names).items():
        t_nfo = dict()
        # Translate dpkg-specific keys to a common structure
        for key, value in pkg_nfo.items():
            if key == 'source_rpm':
                t_nfo['source'] = value
            else:
                t_nfo[key] = value

        ret[pkg_name] = t_nfo

    return ret


def refresh_db(**kwargs):
    '''
    Check the yum repos for updated packages

    Returns:

    - ``True``: Updates are available
    - ``False``: An error occurred
    - ``None``: No updates are available

    repo
        Refresh just the specified repo

    disablerepo
        Do not refresh the specified repo

    enablerepo
        Refresh a disabled repo using this option

    branch
        Add the specified branch when refreshing

    disableexcludes
        Disable the excludes defined in your config files. Takes one of three
        options:
        - ``all`` - disable all excludes
        - ``main`` - disable excludes defined in [main] in yum.conf
        - ``repoid`` - disable excludes defined for that repo


    CLI Example:

    .. code-block:: bash

        salt '*' pkg.refresh_db
    '''
    retcodes = {
        100: True,
        0: None,
        1: False,
    }

    check_update_ = kwargs.pop('check_update', True)

    repo_arg = _get_repo_options(**kwargs)
    exclude_arg = _get_excludes_option(**kwargs)
    branch_arg = _get_branch_option(**kwargs)

    clean_cmd = [_yum(), '--quiet', 'clean', 'expire-cache']
    update_cmd = [_yum(), '--quiet', 'check-update']
    for args in (repo_arg, exclude_arg, branch_arg):
        if args:
            clean_cmd.extend(args)
            update_cmd.extend(args)

    __salt__['cmd.run'](clean_cmd, python_shell=False)
    if check_update_:
        result = __salt__['cmd.retcode'](update_cmd,
                                         output_loglevel='trace',
                                         ignore_retcode=True,
                                         python_shell=False)
        return retcodes.get(result, False)
    return True


def clean_metadata(**kwargs):
    '''
    .. versionadded:: 2014.1.0

    Cleans local yum metadata. Functionally identical to :mod:`refresh_db()
    <salt.modules.yumpkg.refresh_db>`.

    CLI Example:

    .. code-block:: bash

        salt '*' pkg.clean_metadata
    '''
    return refresh_db(**kwargs)


def install(name=None,
            refresh=False,
            skip_verify=False,
            pkgs=None,
            sources=None,
            downloadonly=False,
            reinstall=False,
            normalize=True,
            update_holds=False,
            **kwargs):
    '''
    .. versionchanged:: 2015.8.12,2016.3.3,2016.11.0
        On minions running systemd>=205, `systemd-run(1)`_ is now used to
        isolate commands which modify installed packages from the
        ``salt-minion`` daemon's control group. This is done to keep systemd
        from killing any yum/dnf commands spawned by Salt when the
        ``salt-minion`` service is restarted. (see ``KillMode`` in the
        `systemd.kill(5)`_ manpage for more information). If desired, usage of
        `systemd-run(1)`_ can be suppressed by setting a :mod:`config option
        <salt.modules.config.get>` called ``systemd.scope``, with a value of
        ``False`` (no quotes).

    .. _`systemd-run(1)`: https://www.freedesktop.org/software/systemd/man/systemd-run.html
    .. _`systemd.kill(5)`: https://www.freedesktop.org/software/systemd/man/systemd.kill.html

    Install the passed package(s), add refresh=True to clean the yum database
    before package is installed.

    name
        The name of the package to be installed. Note that this parameter is
        ignored if either "pkgs" or "sources" is passed. Additionally, please
        note that this option can only be used to install packages from a
        software repository. To install a package file manually, use the
        "sources" option.

        32-bit packages can be installed on 64-bit systems by appending the
        architecture designation (``.i686``, ``.i586``, etc.) to the end of the
        package name.

        CLI Example:

        .. code-block:: bash

            salt '*' pkg.install <package name>

    refresh
        Whether or not to update the yum database before executing.

    reinstall
        Specifying reinstall=True will use ``yum reinstall`` rather than
        ``yum install`` for requested packages that are already installed.

        If a version is specified with the requested package, then
        ``yum reinstall`` will only be used if the installed version
        matches the requested version.

        Works with ``sources`` when the package header of the source can be
        matched to the name and version of an installed package.

        .. versionadded:: 2014.7.0

    skip_verify
        Skip the GPG verification check (e.g., ``--nogpgcheck``)

    downloadonly
        Only download the packages, do not install.

    version
        Install a specific version of the package, e.g. 1.2.3-4.el5. Ignored
        if "pkgs" or "sources" is passed.

    update_holds : False
        If ``True``, and this function would update the package version, any
        packages held using the yum/dnf "versionlock" plugin will be unheld so
        that they can be updated. Otherwise, if this function attempts to
        update a held package, the held package(s) will be skipped and an
        error will be raised.

        .. versionadded:: 2016.11.0


    Repository Options:

    fromrepo
        Specify a package repository (or repositories) from which to install.
        (e.g., ``yum --disablerepo='*' --enablerepo='somerepo'``)

    enablerepo (ignored if ``fromrepo`` is specified)
        Specify a disabled package repository (or repositories) to enable.
        (e.g., ``yum --enablerepo='somerepo'``)

    disablerepo (ignored if ``fromrepo`` is specified)
        Specify an enabled package repository (or repositories) to disable.
        (e.g., ``yum --disablerepo='somerepo'``)

    disableexcludes
        Disable exclude from main, for a repo or for everything.
        (e.g., ``yum --disableexcludes='main'``)

        .. versionadded:: 2014.7.0


    Multiple Package Installation Options:

    pkgs
        A list of packages to install from a software repository. Must be
        passed as a python list. A specific version number can be specified
        by using a single-element dict representing the package and its
        version.

        CLI Examples:

        .. code-block:: bash

            salt '*' pkg.install pkgs='["foo", "bar"]'
            salt '*' pkg.install pkgs='["foo", {"bar": "1.2.3-4.el5"}]'

    sources
        A list of RPM packages to install. Must be passed as a list of dicts,
        with the keys being package names, and the values being the source URI
        or local path to the package.

        CLI Example:

        .. code-block:: bash

            salt '*' pkg.install sources='[{"foo": "salt://foo.rpm"}, {"bar": "salt://bar.rpm"}]'

    normalize : True
        Normalize the package name by removing the architecture. This is useful
        for poorly created packages which might include the architecture as an
        actual part of the name such as kernel modules which match a specific
        kernel version.

        .. code-block:: bash

            salt -G role:nsd pkg.install gpfs.gplbin-2.6.32-279.31.1.el6.x86_64 normalize=False

        .. versionadded:: 2014.7.0


    Returns a dict containing the new package names and versions::

        {'<package>': {'old': '<old-version>',
                       'new': '<new-version>'}}
    '''
    repo_arg = _get_repo_options(**kwargs)
    exclude_arg = _get_excludes_option(**kwargs)
    branch_arg = _get_branch_option(**kwargs)

    if salt.utils.is_true(refresh):
        refresh_db(**kwargs)
    reinstall = salt.utils.is_true(reinstall)

    try:
        if "advisory_ids" in kwargs:
            if pkgs:
                raise SaltInvocationError('Cannot use "advisory_ids" and "pkgs" at the same time')
            pkg_params, pkg_type = kwargs['advisory_ids'], 'advisory'
        else:
            pkg_params, pkg_type = __salt__['pkg_resource.parse_targets'](
                name, pkgs, sources, normalize=normalize, **kwargs
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

    old = list_pkgs(versions_as_list=False)
    # Use of __context__ means no duplicate work here, just accessing
    # information already in __context__ from the previous call to list_pkgs()
    old_as_list = list_pkgs(versions_as_list=True)

    to_install = []
    to_downgrade = []
    to_reinstall = []
    # The above three lists will be populated with tuples containing the
    # package name and the string being used for this particular package
    # modification. The reason for this method is that the string we use for
    # installation, downgrading, or reinstallation will be different than the
    # package name in a couple cases:
    #
    #   1) A specific version is being targeted. In this case the string being
    #      passed to install/downgrade/reinstall will contain the version
    #      information after the package name.
    #   2) A binary package is being installed via the "sources" param. In this
    #      case the string being passed will be the path to the local copy of
    #      the package in the minion cachedir.
    #
    # The reason that we need both items is to be able to modify the installed
    # version of held packages.

    if pkg_type == 'repository':
        has_wildcards = [x for x, y in six.iteritems(pkg_params)
                         if y is not None and '*' in y]
        _available = list_repo_pkgs(*has_wildcards, byrepo=False, **kwargs)
        pkg_params_items = six.iteritems(pkg_params)
    else:
        pkg_params_items = []
        for pkg_source in pkg_params:
            if 'lowpkg.bin_pkg_info' in __salt__:
                rpm_info = __salt__['lowpkg.bin_pkg_info'](pkg_source)
            else:
                rpm_info = None
            if rpm_info is None:
                log.error(
                    'pkg.install: Unable to get rpm information for {0}. '
                    'Version comparisons will be unavailable, and return '
                    'data may be inaccurate if reinstall=True.'
                    .format(pkg_source)
                )
                pkg_params_items.append([pkg_source])
            else:
                pkg_params_items.append(
                    [rpm_info['name'], pkg_source, rpm_info['version']]
                )

    errors = []
    for pkg_item_list in pkg_params_items:
        if pkg_type == 'repository':
            pkgname, version_num = pkg_item_list
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
                    to_reinstall.append((pkgname, pkgname))
                else:
                    to_install.append((pkgname, pkgname))
            else:
                to_install.append((pkgname, pkgpath))
        else:
            # If we are installing a package file and not one from the repo,
            # and version_num is not None, then we can assume that pkgname is
            # not None, since the only way version_num is not None is if RPM
            # metadata parsing was successful.
            if pkg_type == 'repository':
                if _yum() == 'yum':
                    # yum install does not support epoch without the arch, and
                    # we won't know what the arch will be when it's not
                    # provided. It could either be the OS architecture, or
                    # 'noarch', and we don't make that distinction in the
                    # pkg.list_pkgs return data.
                    version_num = version_num.split(':', 1)[-1]
                arch = ''
                try:
                    namepart, archpart = pkgname.rsplit('.', 1)
                except ValueError:
                    pass
                else:
                    if archpart in salt.utils.pkg.rpm.ARCHES:
                        arch = '.' + archpart
                        pkgname = namepart

                if '*' in version_num:
                    # Resolve wildcard matches
                    candidates = _available.get(pkgname, [])
                    match = salt.utils.fnmatch_multiple(candidates, version_num)
                    if match is not None:
                        version_num = match
                    else:
                        errors.append(
                            'No version matching \'{0}\' found for package '
                            '\'{1}\' (available: {2})'.format(
                                version_num,
                                pkgname,
                                ', '.join(candidates) if candidates else 'none'
                            )
                        )
                        continue

                pkgstr = '{0}-{1}{2}'.format(pkgname, version_num, arch)
            else:
                pkgstr = pkgpath

            # Lambda to trim the epoch from the currently-installed version if
            # no epoch is specified in the specified version
            norm_epoch = lambda x, y: x.split(':', 1)[-1] \
                if ':' not in y \
                else x
            cver = old_as_list.get(pkgname, [])
            if reinstall and cver:
                for ver in cver:
                    ver = norm_epoch(ver, version_num)
                    if salt.utils.compare_versions(ver1=version_num,
                                                   oper='==',
                                                   ver2=ver,
                                                   cmp_func=version_cmp):
                        # This version is already installed, so we need to
                        # reinstall.
                        to_reinstall.append((pkgname, pkgstr))
                        break
            else:
                if not cver:
                    to_install.append((pkgname, pkgstr))
                else:
                    for ver in cver:
                        ver = norm_epoch(ver, version_num)
                        if salt.utils.compare_versions(ver1=version_num,
                                                       oper='>=',
                                                       ver2=ver,
                                                       cmp_func=version_cmp):
                            to_install.append((pkgname, pkgstr))
                            break
                    else:
                        if re.match('kernel(-.+)?', name):
                            # kernel and its subpackages support multiple
                            # installs as their paths do not conflict.
                            # Performing a yum/dnf downgrade will be a no-op
                            # so just do an install instead. It will fail if
                            # there are other interdependencies that have
                            # conflicts, and that's OK. We don't want to force
                            # anything, we just want to properly handle it if
                            # someone tries to install a kernel/kernel-devel of
                            # a lower version than the currently-installed one.
                            # TODO: find a better way to determine if a package
                            # supports multiple installs.
                            to_install.append((pkgname, pkgstr))
                        else:
                            # None of the currently-installed versions are
                            # greater than the specified version, so this is a
                            # downgrade.
                            to_downgrade.append((pkgname, pkgstr))

    def _add_common_args(cmd):
        '''
        DRY function to add args common to all yum/dnf commands
        '''
        for arg in (repo_arg, exclude_arg, branch_arg):
            if arg:
                cmd.extend(arg)
        if skip_verify:
            cmd.append('--nogpgcheck')
        if downloadonly:
            cmd.append('--downloadonly')

    try:
        holds = list_holds(full=False)
    except SaltInvocationError:
        holds = []
        log.debug(
            'Failed to get holds, versionlock plugin is probably not '
            'installed'
        )
    unhold_prevented = []

    @contextlib.contextmanager
    def _temporarily_unhold(pkgs, targets):
        '''
        Temporarily unhold packages that need to be updated. Add any
        successfully-removed ones (and any packages not in the list of current
        holds) to the list of targets.
        '''
        to_unhold = {}
        for pkgname, pkgstr in pkgs:
            if pkgname in holds:
                if update_holds:
                    to_unhold[pkgname] = pkgstr
                else:
                    unhold_prevented.append(pkgname)
            else:
                targets.append(pkgstr)

        if not to_unhold:
            yield
        else:
            log.debug('Unholding packages: {0}'.format(', '.join(to_unhold)))
            try:
                # Using list() here for python3 compatibility, dict.keys() no
                # longer returns a list in python3.
                unhold_names = list(to_unhold.keys())
                for unheld_pkg, outcome in \
                        six.iteritems(unhold(pkgs=unhold_names)):
                    if outcome['result']:
                        # Package was successfully unheld, add to targets
                        targets.append(to_unhold[unheld_pkg])
                    else:
                        # Failed to unhold package
                        errors.append(unheld_pkg)
                yield
            except Exception as exc:
                errors.append(
                    'Error encountered unholding packages {0}: {1}'
                    .format(', '.join(to_unhold), exc)
                )
            finally:
                hold(pkgs=unhold_names)

    targets = []
    with _temporarily_unhold(to_install, targets):
        if targets:
            if pkg_type == 'advisory':
                targets = ["--advisory={0}".format(t) for t in targets]
            cmd = []
            if salt.utils.systemd.has_scope(__context__) \
                and __salt__['config.get']('systemd.scope', True):
                cmd.extend(['systemd-run', '--scope'])
            cmd.extend([_yum(), '-y'])
            if _yum() == 'dnf':
                cmd.extend(['--best', '--allowerasing'])
            _add_common_args(cmd)
            cmd.append('install' if pkg_type is not 'advisory' else 'update')
            cmd.extend(targets)
            out = __salt__['cmd.run_all'](
                cmd,
                output_loglevel='trace',
                python_shell=False,
                redirect_stderr=True
            )
            if out['retcode'] != 0:
                errors.append(out['stdout'])

    targets = []
    with _temporarily_unhold(to_downgrade, targets):
        if targets:
            cmd = []
            if salt.utils.systemd.has_scope(__context__) \
                and __salt__['config.get']('systemd.scope', True):
                cmd.extend(['systemd-run', '--scope'])
            cmd.extend([_yum(), '-y'])
            _add_common_args(cmd)
            cmd.append('downgrade')
            cmd.extend(targets)
            out = __salt__['cmd.run_all'](
                cmd,
                output_loglevel='trace',
                python_shell=False,
                redirect_stderr=True
            )
            if out['retcode'] != 0:
                errors.append(out['stdout'])

    targets = []
    with _temporarily_unhold(to_reinstall, targets):
        if targets:
            cmd = []
            if salt.utils.systemd.has_scope(__context__) \
                and __salt__['config.get']('systemd.scope', True):
                cmd.extend(['systemd-run', '--scope'])
            cmd.extend([_yum(), '-y'])
            _add_common_args(cmd)
            cmd.append('reinstall')
            cmd.extend(targets)
            out = __salt__['cmd.run_all'](
                cmd,
                output_loglevel='trace',
                python_shell=False,
                redirect_stderr=True
            )
            if out['retcode'] != 0:
                errors.append(out['stdout'])

    __context__.pop('pkg.list_pkgs', None)
    new = list_pkgs(versions_as_list=False)

    ret = salt.utils.compare_dicts(old, new)

    for pkgname, _ in to_reinstall:
        if pkgname not in ret or pkgname in old:
            ret.update({pkgname: {'old': old.get(pkgname, ''),
                                  'new': new.get(pkgname, '')}})

    if unhold_prevented:
        errors.append(
            'The following package(s) could not be updated because they are '
            'being held: {0}. Set \'update_holds\' to True to temporarily '
            'unhold these packages so that they can be updated.'.format(
                ', '.join(unhold_prevented)
            )
        )

    if errors:
        raise CommandExecutionError(
            'Error occurred installing{0} package(s)'.format(
                '/reinstalling' if to_reinstall else ''
            ),
            info={'errors': errors, 'changes': ret}
        )

    return ret


def upgrade(name=None,
            pkgs=None,
            refresh=True,
            skip_verify=False,
            normalize=True,
            **kwargs):
    '''
    Run a full system upgrade (a ``yum upgrade`` or ``dnf upgrade``), or
    upgrade specified packages. If the packages aren't installed, they will
    not be installed.

    .. versionchanged:: 2014.7.0
    .. versionchanged:: 2015.8.12,2016.3.3,2016.11.0
        On minions running systemd>=205, `systemd-run(1)`_ is now used to
        isolate commands which modify installed packages from the
        ``salt-minion`` daemon's control group. This is done to keep systemd
        from killing any yum/dnf commands spawned by Salt when the
        ``salt-minion`` service is restarted. (see ``KillMode`` in the
        `systemd.kill(5)`_ manpage for more information). If desired, usage of
        `systemd-run(1)`_ can be suppressed by setting a :mod:`config option
        <salt.modules.config.get>` called ``systemd.scope``, with a value of
        ``False`` (no quotes).

    .. _`systemd-run(1)`: https://www.freedesktop.org/software/systemd/man/systemd-run.html
    .. _`systemd.kill(5)`: https://www.freedesktop.org/software/systemd/man/systemd.kill.html

    Run a full system upgrade, a yum upgrade

    Returns a dictionary containing the changes:

    .. code-block:: python

        {'<package>':  {'old': '<old-version>',
                        'new': '<new-version>'}}


    CLI Example:

    .. code-block:: bash

        salt '*' pkg.upgrade
        salt '*' pkg.upgrade name=openssl

    Repository Options:

    fromrepo
        Specify a package repository (or repositories) from which to install.
        (e.g., ``yum --disablerepo='*' --enablerepo='somerepo'``)

    enablerepo (ignored if ``fromrepo`` is specified)
        Specify a disabled package repository (or repositories) to enable.
        (e.g., ``yum --enablerepo='somerepo'``)

    disablerepo (ignored if ``fromrepo`` is specified)
        Specify an enabled package repository (or repositories) to disable.
        (e.g., ``yum --disablerepo='somerepo'``)

    disableexcludes
        Disable exclude from main, for a repo or for everything.
        (e.g., ``yum --disableexcludes='main'``)

        .. versionadded:: 2014.7

    name
        The name of the package to be upgraded. Note that this parameter is
        ignored if "pkgs" is passed.

        32-bit packages can be upgraded on 64-bit systems by appending the
        architecture designation (``.i686``, ``.i586``, etc.) to the end of the
        package name.

        Warning: if you forget 'name=' and run pkg.upgrade openssl, ALL packages
        are upgraded. This will be addressed in next releases.

        CLI Example:

        .. code-block:: bash

            salt '*' pkg.upgrade name=openssl

        .. versionadded:: 2016.3.0

    pkgs
        A list of packages to upgrade from a software repository. Must be
        passed as a python list. A specific version number can be specified
        by using a single-element dict representing the package and its
        version. If the package was not already installed on the system,
        it will not be installed.

        CLI Examples:

        .. code-block:: bash

            salt '*' pkg.upgrade pkgs='["foo", "bar"]'
            salt '*' pkg.upgrade pkgs='["foo", {"bar": "1.2.3-4.el5"}]'

        .. versionadded:: 2016.3.0

    normalize : True
        Normalize the package name by removing the architecture. This is useful
        for poorly created packages which might include the architecture as an
        actual part of the name such as kernel modules which match a specific
        kernel version.

        .. code-block:: bash

            salt -G role:nsd pkg.upgrade gpfs.gplbin-2.6.32-279.31.1.el6.x86_64 normalize=False

        .. versionadded:: 2016.3.0
    '''
    repo_arg = _get_repo_options(**kwargs)
    exclude_arg = _get_excludes_option(**kwargs)
    branch_arg = _get_branch_option(**kwargs)

    if salt.utils.is_true(refresh):
        refresh_db(**kwargs)

    old = list_pkgs()

    targets = []
    if name or pkgs:
        try:
            pkg_params = __salt__['pkg_resource.parse_targets'](
                name=name,
                pkgs=pkgs,
                sources=None,
                normalize=normalize,
                **kwargs)[0]
        except MinionError as exc:
            raise CommandExecutionError(exc)

        if pkg_params:
            # Calling list.extend() on a dict will extend it using the
            # dictionary's keys.
            targets.extend(pkg_params)

    cmd = []
    if salt.utils.systemd.has_scope(__context__) \
            and __salt__['config.get']('systemd.scope', True):
        cmd.extend(['systemd-run', '--scope'])
    cmd.extend([_yum(), '--quiet', '-y'])
    for args in (repo_arg, exclude_arg, branch_arg):
        if args:
            cmd.extend(args)
    if skip_verify:
        cmd.append('--nogpgcheck')
    cmd.append('upgrade')
    cmd.extend(targets)

    result = __salt__['cmd.run_all'](cmd,
                                     output_loglevel='trace',
                                     python_shell=False)
    __context__.pop('pkg.list_pkgs', None)
    new = list_pkgs()
    ret = salt.utils.compare_dicts(old, new)

    if result['retcode'] != 0:
        raise CommandExecutionError(
            'Problem encountered upgrading packages',
            info={'changes': ret, 'result': result}
        )

    return ret


def remove(name=None, pkgs=None, **kwargs):  # pylint: disable=W0613
    '''
    .. versionchanged:: 2015.8.12,2016.3.3,2016.11.0
        On minions running systemd>=205, `systemd-run(1)`_ is now used to
        isolate commands which modify installed packages from the
        ``salt-minion`` daemon's control group. This is done to keep systemd
        from killing any yum/dnf commands spawned by Salt when the
        ``salt-minion`` service is restarted. (see ``KillMode`` in the
        `systemd.kill(5)`_ manpage for more information). If desired, usage of
        `systemd-run(1)`_ can be suppressed by setting a :mod:`config option
        <salt.modules.config.get>` called ``systemd.scope``, with a value of
        ``False`` (no quotes).

    .. _`systemd-run(1)`: https://www.freedesktop.org/software/systemd/man/systemd-run.html
    .. _`systemd.kill(5)`: https://www.freedesktop.org/software/systemd/man/systemd.kill.html

    Remove packages

    name
        The name of the package to be removed


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
    try:
        pkg_params = __salt__['pkg_resource.parse_targets'](name, pkgs)[0]
    except MinionError as exc:
        raise CommandExecutionError(exc)

    old = list_pkgs()
    targets = [x for x in pkg_params if x in old]
    if not targets:
        return {}

    cmd = []
    if salt.utils.systemd.has_scope(__context__) \
            and __salt__['config.get']('systemd.scope', True):
        cmd.extend(['systemd-run', '--scope'])
    cmd.extend([_yum(), '-y', 'remove'] + targets)

    out = __salt__['cmd.run_all'](
        [_yum(), '-y', 'remove'] + targets,
        output_loglevel='trace',
        python_shell=False
    )

    if out['retcode'] != 0 and out['stderr']:
        errors = [out['stderr']]
    else:
        errors = []

    __context__.pop('pkg.list_pkgs', None)
    new = list_pkgs()
    ret = salt.utils.compare_dicts(old, new)

    if errors:
        raise CommandExecutionError(
            'Error occurred removing package(s)',
            info={'errors': errors, 'changes': ret}
        )

    return ret


def purge(name=None, pkgs=None, **kwargs):  # pylint: disable=W0613
    '''
    .. versionchanged:: 2015.8.12,2016.3.3,2016.11.0
        On minions running systemd>=205, `systemd-run(1)`_ is now used to
        isolate commands which modify installed packages from the
        ``salt-minion`` daemon's control group. This is done to keep systemd
        from killing any yum/dnf commands spawned by Salt when the
        ``salt-minion`` service is restarted. (see ``KillMode`` in the
        `systemd.kill(5)`_ manpage for more information). If desired, usage of
        `systemd-run(1)`_ can be suppressed by setting a :mod:`config option
        <salt.modules.config.get>` called ``systemd.scope``, with a value of
        ``False`` (no quotes).

    .. _`systemd-run(1)`: https://www.freedesktop.org/software/systemd/man/systemd-run.html
    .. _`systemd.kill(5)`: https://www.freedesktop.org/software/systemd/man/systemd.kill.html

    Package purges are not supported by yum, this function is identical to
    :mod:`pkg.remove <salt.modules.yumpkg.remove>`.

    name
        The name of the package to be purged


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
    return remove(name=name, pkgs=pkgs)


def hold(name=None, pkgs=None, sources=None, normalize=True, **kwargs):  # pylint: disable=W0613
    '''
    .. versionadded:: 2014.7.0

    Version-lock packages

    .. note::
        Requires the appropriate ``versionlock`` plugin package to be installed:

        - On RHEL 5: ``yum-versionlock``
        - On RHEL 6 & 7: ``yum-plugin-versionlock``
        - On Fedora: ``python-dnf-plugins-extras-versionlock``


    name
        The name of the package to be held.

    Multiple Package Options:

    pkgs
        A list of packages to hold. Must be passed as a python list. The
        ``name`` parameter will be ignored if this option is passed.

    Returns a dict containing the changes.

    CLI Example:

    .. code-block:: bash

        salt '*' pkg.hold <package name>
        salt '*' pkg.hold pkgs='["foo", "bar"]'
    '''
    _check_versionlock()

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
            targets.append(next(six.iterkeys(source)))
    else:
        targets.append(name)

    current_locks = list_holds(full=False)
    ret = {}
    for target in targets:
        if isinstance(target, dict):
            target = next(six.iterkeys(target))

        ret[target] = {'name': target,
                       'changes': {},
                       'result': False,
                       'comment': ''}

        if target not in current_locks:
            if 'test' in __opts__ and __opts__['test']:
                ret[target].update(result=None)
                ret[target]['comment'] = ('Package {0} is set to be held.'
                                          .format(target))
            else:
                out = __salt__['cmd.run_all'](
                    [_yum(), 'versionlock', target],
                    python_shell=False
                )

                if out['retcode'] == 0:
                    ret[target].update(result=True)
                    ret[target]['comment'] = ('Package {0} is now being held.'
                                              .format(target))
                    ret[target]['changes']['new'] = 'hold'
                    ret[target]['changes']['old'] = ''
                else:
                    ret[target]['comment'] = ('Package {0} was unable to be held.'
                                              .format(target))
        else:
            ret[target].update(result=True)
            ret[target]['comment'] = ('Package {0} is already set to be held.'
                                      .format(target))
    return ret


def unhold(name=None, pkgs=None, sources=None, **kwargs):  # pylint: disable=W0613
    '''
    .. versionadded:: 2014.7.0

    Remove version locks

    .. note::
        Requires the appropriate ``versionlock`` plugin package to be installed:

        - On RHEL 5: ``yum-versionlock``
        - On RHEL 6 & 7: ``yum-plugin-versionlock``
        - On Fedora: ``python-dnf-plugins-extras-versionlock``


    name
        The name of the package to be unheld

    Multiple Package Options:

    pkgs
        A list of packages to unhold. Must be passed as a python list. The
        ``name`` parameter will be ignored if this option is passed.

    Returns a dict containing the changes.

    CLI Example:

    .. code-block:: bash

        salt '*' pkg.unhold <package name>
        salt '*' pkg.unhold pkgs='["foo", "bar"]'
    '''
    _check_versionlock()

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
        for pkg in salt.utils.repack_dictlist(pkgs):
            targets.append(pkg)
    elif sources:
        for source in sources:
            targets.append(next(iter(source)))
    else:
        targets.append(name)

    # Yum's versionlock plugin doesn't support passing just the package name
    # when removing a lock, so we need to get the full list and then use
    # fnmatch below to find the match.
    current_locks = list_holds(full=_yum() == 'yum')

    ret = {}
    for target in targets:
        if isinstance(target, dict):
            target = next(six.iterkeys(target))

        ret[target] = {'name': target,
                       'changes': {},
                       'result': False,
                       'comment': ''}

        if _yum() == 'dnf':
            search_locks = [x for x in current_locks if x == target]
        else:
            # To accommodate yum versionlock's lack of support for removing
            # locks using just the package name, we have to use fnmatch to do
            # glob matching on the target name, and then for each matching
            # expression double-check that the package name (obtained via
            # _get_hold()) matches the targeted package.
            search_locks = [
                x for x in current_locks
                if fnmatch.fnmatch(x, '*{0}*'.format(target))
                and target == _get_hold(x, full=False)
            ]

        if search_locks:
            if __opts__['test']:
                ret[target].update(result=None)
                ret[target]['comment'] = ('Package {0} is set to be unheld.'
                                          .format(target))
            else:
                out = __salt__['cmd.run_all'](
                    [_yum(), 'versionlock', 'delete'] + search_locks,
                    python_shell=False
                )

                if out['retcode'] == 0:
                    ret[target].update(result=True)
                    ret[target]['comment'] = ('Package {0} is no longer held.'
                                              .format(target))
                    ret[target]['changes']['new'] = ''
                    ret[target]['changes']['old'] = 'hold'
                else:
                    ret[target]['comment'] = ('Package {0} was unable to be '
                                              'unheld.'.format(target))
        else:
            ret[target].update(result=True)
            ret[target]['comment'] = ('Package {0} is not being held.'
                                      .format(target))
    return ret


def list_holds(pattern=__HOLD_PATTERN, full=True):
    r'''
    .. versionchanged:: 2016.3.0,2015.8.4,2015.5.10
        Function renamed from ``pkg.get_locked_pkgs`` to ``pkg.list_holds``.

    List information on locked packages

    .. note::
        Requires the appropriate ``versionlock`` plugin package to be installed:

        - On RHEL 5: ``yum-versionlock``
        - On RHEL 6 & 7: ``yum-plugin-versionlock``
        - On Fedora: ``python-dnf-plugins-extras-versionlock``

    pattern : \w+(?:[.-][^-]+)*
        Regular expression used to match the package name

    full : True
        Show the full hold definition including version and epoch. Set to
        ``False`` to return just the name of the package(s) being held.


    CLI Example:

    .. code-block:: bash

        salt '*' pkg.list_holds
        salt '*' pkg.list_holds full=False
    '''
    _check_versionlock()

    out = __salt__['cmd.run']([_yum(), 'versionlock', 'list'],
                              python_shell=False)
    ret = []
    for line in salt.utils.itertools.split(out, '\n'):
        match = _get_hold(line, pattern=pattern, full=full)
        if match is not None:
            ret.append(match)
    return ret

get_locked_packages = salt.utils.alias_function(list_holds, 'get_locked_packages')


def verify(*names, **kwargs):
    '''
    .. versionadded:: 2014.1.0

    Runs an rpm -Va on a system, and returns the results in a dict

    Pass options to modify rpm verify behavior using the ``verify_options``
    keyword argument

    Files with an attribute of config, doc, ghost, license or readme in the
    package header can be ignored using the ``ignore_types`` keyword argument

    CLI Example:

    .. code-block:: bash

        salt '*' pkg.verify
        salt '*' pkg.verify httpd
        salt '*' pkg.verify 'httpd postfix'
        salt '*' pkg.verify 'httpd postfix' ignore_types=['config','doc']
        salt '*' pkg.verify 'httpd postfix' verify_options=['nodeps','nosize']
    '''
    return __salt__['lowpkg.verify'](*names, **kwargs)


def group_list():
    '''
    .. versionadded:: 2014.1.0

    Lists all groups known by yum on this system

    CLI Example:

    .. code-block:: bash

        salt '*' pkg.group_list
    '''
    ret = {'installed': [],
           'available': [],
           'installed environments': [],
           'available environments': [],
           'available languages': {}}

    section_map = {
        'installed groups:': 'installed',
        'available groups:': 'available',
        'installed environment groups:': 'installed environments',
        'available environment groups:': 'available environments',
        'available language groups:': 'available languages',
    }

    out = __salt__['cmd.run_stdout'](
        [_yum(), 'grouplist', 'hidden'],
        output_loglevel='trace',
        python_shell=False
    )
    key = None
    for line in salt.utils.itertools.split(out, '\n'):
        line_lc = line.lower()
        if line_lc == 'done':
            break

        section_lookup = section_map.get(line_lc)
        if section_lookup is not None and section_lookup != key:
            key = section_lookup
            continue

        # Ignore any administrative comments (plugin info, repo info, etc.)
        if key is None:
            continue

        line = line.strip()
        if key != 'available languages':
            ret[key].append(line)
        else:
            match = re.match(r'(.+) \[(.+)\]', line)
            if match:
                name, lang = match.groups()
                ret[key][line] = {'name': name, 'language': lang}
    return ret


def group_info(name, expand=False):
    '''
    .. versionadded:: 2014.1.0
    .. versionchanged:: 2016.3.0,2015.8.4,2015.5.10
        The return data has changed. A new key ``type`` has been added to
        distinguish environment groups from package groups. Also, keys for the
        group name and group ID have been added. The ``mandatory packages``,
        ``optional packages``, and ``default packages`` keys have been renamed
        to ``mandatory``, ``optional``, and ``default`` for accuracy, as
        environment groups include other groups, and not packages. Finally,
        this function now properly identifies conditional packages.

    Lists packages belonging to a certain group

    name
        Name of the group to query

    expand : False
        If the specified group is an environment group, then the group will be
        expanded and the return data will include package names instead of
        group names.

        .. versionadded:: 2016.3.0

    CLI Example:

    .. code-block:: bash

        salt '*' pkg.group_info 'Perl Support'
    '''
    pkgtypes = ('mandatory', 'optional', 'default', 'conditional')
    ret = {}
    for pkgtype in pkgtypes:
        ret[pkgtype] = set()

    cmd = [_yum(), '--quiet', 'groupinfo', name]
    out = __salt__['cmd.run_stdout'](
        cmd,
        output_loglevel='trace',
        python_shell=False
    )

    g_info = {}
    for line in salt.utils.itertools.split(out, '\n'):
        try:
            key, value = [x.strip() for x in line.split(':')]
            g_info[key.lower()] = value
        except ValueError:
            continue

    if 'environment group' in g_info:
        ret['type'] = 'environment group'
    elif 'group' in g_info:
        ret['type'] = 'package group'

    ret['group'] = g_info.get('environment group') or g_info.get('group')
    ret['id'] = g_info.get('environment-id') or g_info.get('group-id')
    if not ret['group'] and not ret['id']:
        raise CommandExecutionError('Group \'{0}\' not found'.format(name))

    ret['description'] = g_info.get('description', '')

    pkgtypes_capturegroup = '(' + '|'.join(pkgtypes) + ')'
    for pkgtype in pkgtypes:
        target_found = False
        for line in salt.utils.itertools.split(out, '\n'):
            line = line.strip().lstrip(string.punctuation)
            match = re.match(
                pkgtypes_capturegroup + r' (?:groups|packages):\s*$',
                line.lower()
            )
            if match:
                if target_found:
                    # We've reached a new section, break from loop
                    break
                else:
                    if match.group(1) == pkgtype:
                        # We've reached the targeted section
                        target_found = True
                    continue
            if target_found:
                if expand and ret['type'] == 'environment group':
                    expanded = group_info(line, expand=True)
                    # Don't shadow the pkgtype variable from the outer loop
                    for p_type in pkgtypes:
                        ret[p_type].update(set(expanded[p_type]))
                else:
                    ret[pkgtype].add(line)

    for pkgtype in pkgtypes:
        ret[pkgtype] = sorted(ret[pkgtype])

    return ret


def group_diff(name):
    '''
    .. versionadded:: 2014.1.0
    .. versionchanged:: 2016.3.0,2015.8.4,2015.5.10
        Environment groups are now supported. The key names have been renamed,
        similar to the changes made in :py:func:`pkg.group_info
        <salt.modules.yumpkg.group_info>`.

    Lists which of a group's packages are installed and which are not
    installed

    CLI Example:

    .. code-block:: bash

        salt '*' pkg.group_diff 'Perl Support'
    '''
    pkgtypes = ('mandatory', 'optional', 'default', 'conditional')
    ret = {}
    for pkgtype in pkgtypes:
        ret[pkgtype] = {'installed': [], 'not installed': []}

    pkgs = list_pkgs()
    group_pkgs = group_info(name, expand=True)
    for pkgtype in pkgtypes:
        for member in group_pkgs.get(pkgtype, []):
            if member in pkgs:
                ret[pkgtype]['installed'].append(member)
            else:
                ret[pkgtype]['not installed'].append(member)
    return ret


def group_install(name,
                  skip=(),
                  include=(),
                  **kwargs):
    '''
    .. versionadded:: 2014.1.0

    Install the passed package group(s). This is basically a wrapper around
    :py:func:`pkg.install <salt.modules.yumpkg.install>`, which performs
    package group resolution for the user. This function is currently
    considered experimental, and should be expected to undergo changes.

    name
        Package group to install. To install more than one group, either use a
        comma-separated list or pass the value as a python list.

        CLI Examples:

        .. code-block:: bash

            salt '*' pkg.group_install 'Group 1'
            salt '*' pkg.group_install 'Group 1,Group 2'
            salt '*' pkg.group_install '["Group 1", "Group 2"]'

    skip
        Packages that would normally be installed by the package group
        ("default" packages), which should not be installed. Can be passed
        either as a comma-separated list or a python list.

        CLI Examples:

        .. code-block:: bash

            salt '*' pkg.group_install 'My Group' skip='foo,bar'
            salt '*' pkg.group_install 'My Group' skip='["foo", "bar"]'

    include
        Packages which are included in a group, which would not normally be
        installed by a ``yum groupinstall`` ("optional" packages). Note that
        this will not enforce group membership; if you include packages which
        are not members of the specified groups, they will still be installed.
        Can be passed either as a comma-separated list or a python list.

        CLI Examples:

        .. code-block:: bash

            salt '*' pkg.group_install 'My Group' include='foo,bar'
            salt '*' pkg.group_install 'My Group' include='["foo", "bar"]'

    .. note::

        Because this is essentially a wrapper around pkg.install, any argument
        which can be passed to pkg.install may also be included here, and it
        will be passed along wholesale.
    '''
    groups = name.split(',') if isinstance(name, six.string_types) else name

    if not groups:
        raise SaltInvocationError('no groups specified')
    elif not isinstance(groups, list):
        raise SaltInvocationError('\'groups\' must be a list')

    # pylint: disable=maybe-no-member
    if isinstance(skip, six.string_types):
        skip = skip.split(',')
    if not isinstance(skip, (list, tuple)):
        raise SaltInvocationError('\'skip\' must be a list')

    if isinstance(include, six.string_types):
        include = include.split(',')
    if not isinstance(include, (list, tuple)):
        raise SaltInvocationError('\'include\' must be a list')
    # pylint: enable=maybe-no-member

    targets = []
    for group in groups:
        group_detail = group_info(group)
        targets.extend(group_detail.get('mandatory packages', []))
        targets.extend(
            [pkg for pkg in group_detail.get('default packages', [])
             if pkg not in skip]
        )
    if include:
        targets.extend(include)

    # Don't install packages that are already installed, install() isn't smart
    # enough to make this distinction.
    pkgs = [x for x in targets if x not in list_pkgs()]
    if not pkgs:
        return {}

    return install(pkgs=pkgs, **kwargs)

groupinstall = salt.utils.alias_function(group_install, 'groupinstall')


def list_repos(basedir=None):
    '''
    Lists all repos in <basedir> (default: all dirs in `reposdir` yum option).

    CLI Example:

    .. code-block:: bash

        salt '*' pkg.list_repos
        salt '*' pkg.list_repos basedir=/path/to/dir
        salt '*' pkg.list_repos basedir=/path/to/dir,/path/to/another/dir
    '''

    basedirs = _normalize_basedir(basedir)
    repos = {}
    log.debug('Searching for repos in %s', basedirs)
    for bdir in basedirs:
        if not os.path.exists(bdir):
            continue
        for repofile in os.listdir(bdir):
            repopath = '{0}/{1}'.format(bdir, repofile)
            if not repofile.endswith('.repo'):
                continue
            filerepos = _parse_repo_file(repopath)[1]
            for reponame in filerepos:
                repo = filerepos[reponame]
                repo['file'] = repopath
                repos[reponame] = repo
    return repos


def get_repo(name, basedir=None, **kwargs):  # pylint: disable=W0613
    '''
    Display a repo from <basedir> (default basedir: all dirs in ``reposdir``
    yum option).

    CLI Examples:

    .. code-block:: bash

        salt '*' pkg.get_repo myrepo
        salt '*' pkg.get_repo myrepo basedir=/path/to/dir
        salt '*' pkg.get_repo myrepo basedir=/path/to/dir,/path/to/another/dir
    '''
    repos = list_repos(basedir)

    # Find out what file the repo lives in
    repofile = ''
    for repo in repos:
        if repo == name:
            repofile = repos[repo]['file']

    if repofile:
        # Return just one repo
        filerepos = _parse_repo_file(repofile)[1]
        return filerepos[name]
    return {}


def del_repo(repo, basedir=None, **kwargs):  # pylint: disable=W0613
    '''
    Delete a repo from <basedir> (default basedir: all dirs in `reposdir` yum
    option).

    If the .repo file in which the repo exists does not contain any other repo
    configuration, the file itself will be deleted.

    CLI Examples:

    .. code-block:: bash

        salt '*' pkg.del_repo myrepo
        salt '*' pkg.del_repo myrepo basedir=/path/to/dir
        salt '*' pkg.del_repo myrepo basedir=/path/to/dir,/path/to/another/dir
    '''
    # this is so we know which dirs are searched for our error messages below
    basedirs = _normalize_basedir(basedir)
    repos = list_repos(basedirs)

    if repo not in repos:
        return 'Error: the {0} repo does not exist in {1}'.format(
            repo, basedirs)

    # Find out what file the repo lives in
    repofile = ''
    for arepo in repos:
        if arepo == repo:
            repofile = repos[arepo]['file']

    # See if the repo is the only one in the file
    onlyrepo = True
    for arepo in six.iterkeys(repos):
        if arepo == repo:
            continue
        if repos[arepo]['file'] == repofile:
            onlyrepo = False

    # If this is the only repo in the file, delete the file itself
    if onlyrepo:
        os.remove(repofile)
        return 'File {0} containing repo {1} has been removed'.format(
            repofile, repo)

    # There must be other repos in this file, write the file with them
    header, filerepos = _parse_repo_file(repofile)
    content = header
    for stanza in six.iterkeys(filerepos):
        if stanza == repo:
            continue
        comments = ''
        if 'comments' in filerepos[stanza]:
            comments = '\n'.join(filerepos[stanza]['comments'])
            del filerepos[stanza]['comments']
        content += '\n[{0}]'.format(stanza)
        for line in filerepos[stanza]:
            content += '\n{0}={1}'.format(line, filerepos[stanza][line])
        content += '\n{0}\n'.format(comments)

    with salt.utils.fopen(repofile, 'w') as fileout:
        fileout.write(content)

    return 'Repo {0} has been removed from {1}'.format(repo, repofile)


def mod_repo(repo, basedir=None, **kwargs):
    '''
    Modify one or more values for a repo. If the repo does not exist, it will
    be created, so long as the following values are specified:

    repo
        name by which the yum refers to the repo
    name
        a human-readable name for the repo
    baseurl
        the URL for yum to reference
    mirrorlist
        the URL for yum to reference

    Key/Value pairs may also be removed from a repo's configuration by setting
    a key to a blank value. Bear in mind that a name cannot be deleted, and a
    baseurl can only be deleted if a mirrorlist is specified (or vice versa).

    CLI Examples:

    .. code-block:: bash

        salt '*' pkg.mod_repo reponame enabled=1 gpgcheck=1
        salt '*' pkg.mod_repo reponame basedir=/path/to/dir enabled=1
        salt '*' pkg.mod_repo reponame baseurl= mirrorlist=http://host.com/
    '''
    # Filter out '__pub' arguments, as well as saltenv
    repo_opts = dict(
        (x, kwargs[x]) for x in kwargs
        if not x.startswith('__') and x not in ('saltenv',)
    )

    if all(x in repo_opts for x in ('mirrorlist', 'baseurl')):
        raise SaltInvocationError(
            'Only one of \'mirrorlist\' and \'baseurl\' can be specified'
        )

    # Build a list of keys to be deleted
    todelete = []
    for key in repo_opts:
        if repo_opts[key] != 0 and not repo_opts[key]:
            del repo_opts[key]
            todelete.append(key)

    # Add baseurl or mirrorlist to the 'todelete' list if the other was
    # specified in the repo_opts
    if 'mirrorlist' in repo_opts:
        todelete.append('baseurl')
    elif 'baseurl' in repo_opts:
        todelete.append('mirrorlist')

    # Fail if the user tried to delete the name
    if 'name' in todelete:
        raise SaltInvocationError('The repo name cannot be deleted')

    # Give the user the ability to change the basedir
    repos = {}
    basedirs = _normalize_basedir(basedir)
    repos = list_repos(basedirs)

    repofile = ''
    header = ''
    filerepos = {}
    if repo not in repos:
        # If the repo doesn't exist, create it in a new file in the first
        # repo directory that exists
        newdir = None
        for d in basedirs:
            if os.path.exists(d):
                newdir = d
                break
        if not newdir:
            raise SaltInvocationError(
                'The repo does not exist and needs to be created, but none '
                'of the following basedir directories exist: {0}'.format(basedirs)
            )

        repofile = '{0}/{1}.repo'.format(newdir, repo)

        if 'name' not in repo_opts:
            raise SaltInvocationError(
                'The repo does not exist and needs to be created, but a name '
                'was not given'
            )

        if 'baseurl' not in repo_opts and 'mirrorlist' not in repo_opts:
            raise SaltInvocationError(
                'The repo does not exist and needs to be created, but either '
                'a baseurl or a mirrorlist needs to be given'
            )
        filerepos[repo] = {}
    else:
        # The repo does exist, open its file
        repofile = repos[repo]['file']
        header, filerepos = _parse_repo_file(repofile)

    # Error out if they tried to delete baseurl or mirrorlist improperly
    if 'baseurl' in todelete:
        if 'mirrorlist' not in repo_opts and 'mirrorlist' \
                not in filerepos[repo]:
            raise SaltInvocationError(
                'Cannot delete baseurl without specifying mirrorlist'
            )
    if 'mirrorlist' in todelete:
        if 'baseurl' not in repo_opts and 'baseurl' \
                not in filerepos[repo]:
            raise SaltInvocationError(
                'Cannot delete mirrorlist without specifying baseurl'
            )

    # Delete anything in the todelete list
    for key in todelete:
        if key in six.iterkeys(filerepos[repo].copy()):
            del filerepos[repo][key]

    _bool_to_str = lambda x: '1' if x else '0'
    # Old file or new, write out the repos(s)
    filerepos[repo].update(repo_opts)
    content = header
    for stanza in six.iterkeys(filerepos):
        comments = ''
        if 'comments' in six.iterkeys(filerepos[stanza]):
            comments = '\n'.join(filerepos[stanza]['comments'])
            del filerepos[stanza]['comments']
        content += '\n[{0}]'.format(stanza)
        for line in six.iterkeys(filerepos[stanza]):
            content += '\n{0}={1}'.format(
                line,
                filerepos[stanza][line]
                    if not isinstance(filerepos[stanza][line], bool)
                    else _bool_to_str(filerepos[stanza][line])
            )
        content += '\n{0}\n'.format(comments)

    with salt.utils.fopen(repofile, 'w') as fileout:
        fileout.write(content)

    return {repofile: filerepos}


def _parse_repo_file(filename):
    '''
    Turn a single repo file into a dict
    '''
    repos = {}
    header = ''
    repo = ''
    with salt.utils.fopen(filename, 'r') as rfile:
        for line in rfile:
            if line.startswith('['):
                repo = line.strip().replace('[', '').replace(']', '')
                repos[repo] = {}

            # Even though these are essentially uselss, I want to allow the
            # user to maintain their own comments, etc
            if not line:
                if not repo:
                    header += line
            if line.startswith('#'):
                if not repo:
                    header += line
                else:
                    if 'comments' not in repos[repo]:
                        repos[repo]['comments'] = []
                    repos[repo]['comments'].append(line.strip())
                continue

            # These are the actual configuration lines that matter
            if '=' in line:
                try:
                    comps = line.strip().split('=')
                    repos[repo][comps[0].strip()] = '='.join(comps[1:])
                except KeyError:
                    log.error(
                        'Failed to parse line in %s, offending line was '
                        '\'%s\'', filename, line.rstrip()
                    )

    return (header, repos)


def file_list(*packages):
    '''
    .. versionadded:: 2014.1.0

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
    .. versionadded:: 2014.1.0

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


def owner(*paths):
    '''
    .. versionadded:: 2014.7.0

    Return the name of the package that owns the file. Multiple file paths can
    be passed. Like :mod:`pkg.version <salt.modules.yumpkg.version`, if a
    single path is passed, a string will be returned, and if multiple paths are
    passed, a dictionary of file/package name pairs will be returned.

    If the file is not owned by a package, or is not present on the minion,
    then an empty string will be returned for that path.

    CLI Examples:

    .. code-block:: bash

        salt '*' pkg.owner /usr/bin/apachectl
        salt '*' pkg.owner /usr/bin/apachectl /etc/httpd/conf/httpd.conf
    '''
    if not paths:
        return ''
    ret = {}
    cmd_prefix = ['rpm', '-qf', '--queryformat', '%{name}']
    for path in paths:
        ret[path] = __salt__['cmd.run_stdout'](
            cmd_prefix + [path],
            output_loglevel='trace',
            python_shell=False
        )
        if 'not owned' in ret[path].lower():
            ret[path] = ''
    if len(ret) == 1:
        return next(six.itervalues(ret))
    return ret


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
        Include only files where modification time of the file has been
        changed.

    capabilities
        Include only files where capabilities differ or not. Note: supported
        only on newer RPM versions.

    CLI Examples:

    .. code-block:: bash

        salt '*' pkg.modified
        salt '*' pkg.modified httpd
        salt '*' pkg.modified httpd postfix
        salt '*' pkg.modified httpd owner=True group=False
    '''

    return __salt__['lowpkg.modified'](*packages, **flags)


@decorators.which('yumdownloader')
def download(*packages):
    '''
    .. versionadded:: 2015.5.0

    Download packages to the local disk. Requires ``yumdownloader`` from
    ``yum-utils`` package.

    .. note::

        ``yum-utils`` will already be installed on the minion if the package
        was installed from the Fedora / EPEL repositories.

    CLI example:

    .. code-block:: bash

        salt '*' pkg.download httpd
        salt '*' pkg.download httpd postfix
    '''
    if not packages:
        raise SaltInvocationError('No packages were specified')

    CACHE_DIR = '/var/cache/yum/packages'
    if not os.path.exists(CACHE_DIR):
        os.makedirs(CACHE_DIR)
    cached_pkgs = os.listdir(CACHE_DIR)
    to_purge = []
    for pkg in packages:
        to_purge.extend([os.path.join(CACHE_DIR, x)
                         for x in cached_pkgs
                         if x.startswith('{0}-'.format(pkg))])
    for purge_target in set(to_purge):
        log.debug('Removing cached package %s', purge_target)
        try:
            os.unlink(purge_target)
        except OSError as exc:
            log.error('Unable to remove %s: %s', purge_target, exc)

    cmd = ['yumdownloader', '-q', '--destdir={0}'.format(CACHE_DIR)]
    cmd.extend(packages)
    __salt__['cmd.run'](
        cmd,
        output_loglevel='trace',
        python_shell=False
    )
    ret = {}
    for dld_result in os.listdir(CACHE_DIR):
        if not dld_result.endswith('.rpm'):
            continue
        pkg_name = None
        pkg_file = None
        for query_pkg in packages:
            if dld_result.startswith('{0}-'.format(query_pkg)):
                pkg_name = query_pkg
                pkg_file = dld_result
                break
        if pkg_file is not None:
            ret[pkg_name] = os.path.join(CACHE_DIR, pkg_file)

    if not ret:
        raise CommandExecutionError(
            'Unable to download any of the following packages: {0}'
            .format(', '.join(packages))
        )

    failed = [x for x in packages if x not in ret]
    if failed:
        ret['_error'] = ('The following package(s) failed to download: {0}'
                         .format(', '.join(failed)))
    return ret


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
                    local_pkgs[pkg]['path'], path) or 'Unchanged'

    return ret
