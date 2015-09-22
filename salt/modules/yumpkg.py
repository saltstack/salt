# -*- coding: utf-8 -*-
'''
Support for YUM

.. note::
    This module makes heavy use of the **repoquery** utility, from the
    yum-utils_ package. This package will be installed as a dependency if salt
    is installed via EPEL. However, if salt has been installed using pip, or a
    host is being managed using salt-ssh, then as of version 2014.7.0
    yum-utils_ will be installed automatically to satisfy this dependency.

    .. _yum-utils: http://yum.baseurl.org/wiki/YumUtils

'''

# Import python libs
from __future__ import absolute_import
import copy
import logging
import os
import re
from distutils.version import LooseVersion as _LooseVersion  # pylint: disable=no-name-in-module,import-error

# Import 3rd-party libs
# pylint: disable=import-error,redefined-builtin
import salt.ext.six as six
from salt.ext.six import string_types
from salt.ext.six.moves import shlex_quote as _cmd_quote, range

try:
    import yum
    HAS_YUM = True
except ImportError:
    from salt.ext.six.moves import configparser
    HAS_YUM = False

try:
    import rpmUtils.miscutils
    HAS_RPMUTILS = True
except ImportError:
    HAS_RPMUTILS = False
# pylint: enable=import-error

# Import salt libs
import salt.utils
import salt.utils.decorators as decorators
from salt.exceptions import (
    CommandExecutionError, MinionError, SaltInvocationError
)

log = logging.getLogger(__name__)

__QUERYFORMAT = '%{NAME}_|-%{VERSION}_|-%{RELEASE}_|-%{ARCH}_|-%{REPOID}'

# These arches compiled from the rpmUtils.arch python module source
__ARCHES_64 = ('x86_64', 'athlon', 'amd64', 'ia32e', 'ia64', 'geode')
__ARCHES_32 = ('i386', 'i486', 'i586', 'i686')
__ARCHES_PPC = ('ppc', 'ppc64', 'ppc64iseries', 'ppc64pseries')
__ARCHES_S390 = ('s390', 's390x')
__ARCHES_SPARC = (
    'sparc', 'sparcv8', 'sparcv9', 'sparcv9v', 'sparc64', 'sparc64v'
)
__ARCHES_ALPHA = (
    'alpha', 'alphaev4', 'alphaev45', 'alphaev5', 'alphaev56',
    'alphapca56', 'alphaev6', 'alphaev67', 'alphaev68', 'alphaev7'
)
__ARCHES_ARM = ('armv5tel', 'armv5tejl', 'armv6l', 'armv7l')
__ARCHES_SH = ('sh3', 'sh4', 'sh4a')

__ARCHES = __ARCHES_64 + __ARCHES_32 + __ARCHES_PPC + __ARCHES_S390 + \
    __ARCHES_ALPHA + __ARCHES_ARM + __ARCHES_SH

# Define the module's virtual name
__virtualname__ = 'pkg'


def __virtual__():
    '''
    Confine this module to yum based systems
    '''
    if __opts__.get('yum_provider') == 'yumpkg_api':
        return False
    try:
        os_grain = __grains__['os'].lower()
        os_family = __grains__['os_family'].lower()
    except Exception:
        return False

    enabled = ('amazon', 'xcp', 'xenserver')

    if os_family == 'redhat' or os_grain in enabled:
        return __virtualname__
    return False


def _parse_pkginfo(line):
    '''
    A small helper to parse a repoquery; returns a namedtuple
    '''
    # Importing `collections` here since this function is re-namespaced into
    # another module
    import collections
    pkginfo = collections.namedtuple(
        'PkgInfo',
        ('name', 'version', 'arch', 'repoid')
    )

    try:
        name, pkg_version, release, arch, repoid = line.split('_|-')
    # Handle unpack errors (should never happen with the queryformat we are
    # using, but can't hurt to be careful).
    except ValueError:
        return None

    if not _check_32(arch):
        if arch not in (__grains__['osarch'], 'noarch'):
            name += '.{0}'.format(arch)
    if release:
        pkg_version += '-{0}'.format(release)

    return pkginfo(name, pkg_version, arch, repoid)


def _repoquery_pkginfo(repoquery_args):
    '''
    Wrapper to call repoquery and parse out all the tuples
    '''
    ret = []
    for line in _repoquery(repoquery_args):
        pkginfo = _parse_pkginfo(line)
        if pkginfo is not None:
            ret.append(pkginfo)
    return ret


def _check_repoquery():
    '''
    Check for existence of repoquery and install yum-utils if it is not
    present.
    '''
    if not salt.utils.which('repoquery'):
        __salt__['cmd.run'](
            ['yum', '-y', 'install', 'yum-utils'],
            python_shell=False,
            output_loglevel='trace'
        )
        # Check again now that we've installed yum-utils
        if not salt.utils.which('repoquery'):
            raise CommandExecutionError('Unable to install yum-utils')


def _repoquery(repoquery_args, query_format=__QUERYFORMAT):
    '''
    Runs a repoquery command and returns a list of namedtuples
    '''
    _check_repoquery()
    cmd = 'repoquery --plugins --queryformat {0} {1}'.format(
        _cmd_quote(query_format), repoquery_args
    )
    call = __salt__['cmd.run_all'](cmd, output_loglevel='trace')
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
        return out.splitlines()


def _get_repo_options(**kwargs):
    '''
    Returns a string of '--enablerepo' and '--disablerepo' options to be used
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

    repo_arg = ''
    if fromrepo:
        log.info('Restricting to repo {0!r}'.format(fromrepo))
        repo_arg = ('--disablerepo={0!r} --enablerepo={1!r}'
                    .format('*', fromrepo))
    else:
        repo_arg = ''
        if disablerepo:
            log.info('Disabling repo {0!r}'.format(disablerepo))
            repo_arg += '--disablerepo={0!r}'.format(disablerepo)
        if enablerepo:
            log.info('Enabling repo {0!r}'.format(enablerepo))
            repo_arg += '--enablerepo={0!r}'.format(enablerepo)
    return repo_arg


def _get_excludes_option(**kwargs):
    '''
    Returns a string of '--disableexcludes' option to be used in the yum command,
    based on the kwargs.
    '''
    disable_excludes_arg = ''
    disable_excludes = kwargs.get('disableexcludes', '')

    if disable_excludes:
        log.info('Disabling excludes for {0!r}'.format(disable_excludes))
        disable_excludes_arg = ('--disableexcludes={0!r}'.format(disable_excludes))

    return disable_excludes_arg


def _get_branch_option(**kwargs):
    '''
    Returns a string of '--branch' option to be used in the yum command,
    based on the kwargs. This feature requires 'branch' plugin for YUM.
    '''
    # Get branch option from the kwargs
    branch = kwargs.get('branch', '')

    branch_arg = ''
    if branch:
        log.info('Adding branch {0!r}'.format(branch))
        branch_arg = ('--branch={0!r}'.format(branch))
    return branch_arg


def _check_32(arch):
    '''
    Returns True if both the OS arch and the passed arch are 32-bit
    '''
    return all(x in __ARCHES_32 for x in (__grains__['osarch'], arch))


def _rpm_pkginfo(name):
    '''
    Parses RPM metadata and returns a pkginfo namedtuple
    '''
    # REPOID is not a valid tag for the rpm command. Remove it and replace it
    # with 'none'
    queryformat = __QUERYFORMAT.replace('%{REPOID}', 'none')
    output = __salt__['cmd.run_stdout'](
        'rpm -qp --queryformat {0!r} {1}'.format(_cmd_quote(queryformat), name),
        output_loglevel='trace',
        ignore_retcode=True
    )
    return _parse_pkginfo(output)


def _rpm_installed(name):
    '''
    Parses RPM metadata to determine if the RPM target is already installed.
    Returns the name of the installed package if found, otherwise None.
    '''
    pkg = _rpm_pkginfo(name)
    try:
        return pkg.name if pkg.name in list_pkgs() else None
    except AttributeError:
        return None


def _get_yum_config():
    '''
    Returns a dict representing the yum config options and values.

    We try to pull all of the yum config options into a standard dict object.
    This is currently only used to get the reposdir settings, but could be used
    for other things if needed.

    If the yum python library is available, use that, which will give us
    all of the options, including all of the defaults not specified in the
    yum config.  Additionally, they will all be of the correct object type.

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
            for name, value in yb.conf.iteritems():
                conf[name] = value
        except (AttributeError, yum.Errors.ConfigError) as exc:
            raise CommandExecutionError(
                'Could not query yum config: {0}'.format(exc)
            )
    else:
        # fall back to parsing the config ourselves
        # Look for the config the same order yum does
        fn = None
        paths = ('/etc/yum/yum.conf', '/etc/yum.conf')
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
                    conf[opt] = [x.strip() for x in cp.get('main', opt).split(',')]
                else:
                    conf[opt] = cp.get('main', opt)
        else:
            log.warning('Could not find [main] section in {0}, using internal defaults'.format(fn))

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
    Takes a basedir argument as a string or a list.  If the string or list is empty,
    then look up the default from the 'reposdir' option in the yum config.

    Returns a list of directories.
    '''
    if basedir is None:
        basedir = []

    # if we are passed a string (for backward compatibility), convert to a list
    if isinstance(basedir, basestring):
        basedir = [x.strip() for x in basedir.split(',')]

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
        if arch not in __ARCHES + ('noarch',):
            return name
    except ValueError:
        return name
    if arch in (__grains__['osarch'], 'noarch') or _check_32(arch):
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

    # Initialize the return dict with empty strings, and populate namearch_map.
    # namearch_map will provide a means of distinguishing between multiple
    # matches for the same package name, for example a target of 'glibc' on an
    # x86_64 arch would return both x86_64 and i686 versions when searched
    # using repoquery:
    #
    # $ repoquery --all --pkgnarrow=available glibc
    # glibc-0:2.12-1.132.el6.i686
    # glibc-0:2.12-1.132.el6.x86_64
    #
    # Note that the logic in the for loop below would place the osarch into the
    # map for noarch packages, but those cases are accounted for when iterating
    # through the repoquery results later on. If the repoquery match for that
    # package is a noarch, then the package is assumed to be noarch, and the
    # namearch_map is ignored.
    ret = {}
    namearch_map = {}
    for name in names:
        ret[name] = ''
        try:
            arch = name.rsplit('.', 1)[-1]
            if arch not in __ARCHES:
                arch = __grains__['osarch']
        except ValueError:
            arch = __grains__['osarch']
        namearch_map[name] = arch

    repo_arg = _get_repo_options(**kwargs)
    exclude_arg = _get_excludes_option(**kwargs)

    # Refresh before looking for the latest version available
    if refresh:
        refresh_db(**kwargs)

    # Get updates for specified package(s)
    updates = _repoquery_pkginfo(
        '{0} {1} --pkgnarrow=available {2}'
        .format(repo_arg, exclude_arg, ' '.join(names))
    )

    for name in names:
        for pkg in (x for x in updates if x.name == name):
            if pkg.arch == 'noarch' or pkg.arch == namearch_map[name] \
                    or _check_32(pkg.arch):
                ret[name] = pkg.version
                # no need to check another match, if there was one
                break

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


def version_cmp(pkg1, pkg2):
    '''
    .. versionadded:: 2015.5.4

    Do a cmp-style comparison on two packages. Return -1 if pkg1 < pkg2, 0 if
    pkg1 == pkg2, and 1 if pkg1 > pkg2. Return None if there was a problem
    making the comparison.

    CLI Example:

    .. code-block:: bash

        salt '*' pkg.version_cmp '0.2-001' '0.2.0.1-002'
    '''
    if HAS_RPMUTILS:
        try:
            cmp_result = rpmUtils.miscutils.compareEVR(
                rpmUtils.miscutils.stringToVersion(pkg1),
                rpmUtils.miscutils.stringToVersion(pkg2)
            )
            if cmp_result not in (-1, 0, 1):
                raise Exception(
                    'cmp result \'{0}\' is invalid'.format(cmp_result)
                )
            return cmp_result
        except Exception as exc:
            log.warning(
                'Failed to compare version \'{0}\' to \'{1}\' using '
                'rpmUtils: {2}'.format(pkg1, pkg2, exc)
            )
    # Fall back to distutils.version.LooseVersion (should only need to do
    # this for RHEL5, or if an exception is raised when attempting to compare
    # using rpmUtils)
    return salt.utils.version_cmp(pkg1, pkg2)


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
    for pkginfo in _repoquery_pkginfo('--all --pkgnarrow=installed'):
        if pkginfo is None:
            continue
        __salt__['pkg_resource.add_pkg'](ret, pkginfo.name, pkginfo.version)

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
        data shown below reflects the updated return dict structure.

    Returns all available packages. Optionally, package names (and name globs)
    can be passed and the results will be filtered to packages matching those
    names. This is recommended as it speeds up the function considerably.

    This function can be helpful in discovering the version or repo to specify
    in a :mod:`pkg.installed <salt.states.pkg.installed>` state.

    The return data is a dictionary of repo names, with each repo containing a
    dictionary in which the keys are package names, and the values are a list
    of version numbers. Here is an example of the return data:

    .. code-block:: python

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

    CLI Example:

    .. code-block:: bash

        salt '*' pkg.list_repo_pkgs
        salt '*' pkg.list_repo_pkgs foo bar baz
        salt '*' pkg.list_repo_pkgs 'samba4*' fromrepo=base,updates
    '''
    try:
        repos = tuple(x.strip() for x in kwargs.get('fromrepo').split(','))
    except AttributeError:
        # Search in all enabled repos
        repos = tuple(
            x for x, y in six.iteritems(list_repos())
            if str(y.get('enabled', '1')) == '1'
        )

    ret = {}
    for repo in repos:
        repoquery_cmd = '--all --repoid="{0}" --show-duplicates'.format(repo)
        for arg in args:
            repoquery_cmd += ' "{0}"'.format(arg)
        all_pkgs = _repoquery_pkginfo(repoquery_cmd)
        for pkg in all_pkgs:
            repo_dict = ret.setdefault(pkg.repoid, {})
            version_list = repo_dict.setdefault(pkg.name, [])
            version_list.append(pkg.version)

    for reponame in ret:
        for pkgname in ret[reponame]:
            sorted_versions = sorted(
                [_LooseVersion(x) for x in ret[reponame][pkgname]],
                reverse=True
            )
            ret[reponame][pkgname] = [x.vstring for x in sorted_versions]
    return ret


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
        refresh_db(**kwargs)
    updates = _repoquery_pkginfo(
        '{0} {1} --all --pkgnarrow=updates'.format(repo_arg, exclude_arg)
    )
    return dict([(x.name, x.version) for x in updates])


def check_db(*names, **kwargs):
    '''
    .. versionadded:: 0.17.0

    Returns a dict containing the following information for each specified
    package:

    1. A key ``found``, which will be a boolean value denoting if a match was
       found in the package database.
    2. If ``found`` is ``False``, then a second key called ``suggestions`` will
       be present, which will contain a list of possible matches.

    The ``fromrepo``, ``enablerepo`` and ``disablerepo`` arguments are
    supported, as used in pkg states, and the ``disableexcludes`` option is
    also supported.

    .. versionadded:: 2014.7.0
        Support for the ``disableexcludes`` option

    CLI Examples:

    .. code-block:: bash

        salt '*' pkg.check_db <package1> <package2> <package3>
        salt '*' pkg.check_db <package1> <package2> <package3> fromrepo=epel-testing
        salt '*' pkg.check_db <package1> <package2> <package3> disableexcludes=main
    '''
    normalize = kwargs.pop('normalize') if kwargs.get('normalize') else False
    repo_arg = _get_repo_options(**kwargs)
    exclude_arg = _get_excludes_option(**kwargs)
    repoquery_base = \
        '{0} {1} --all --quiet --whatprovides'.format(repo_arg, exclude_arg)

    if 'pkg._avail' in __context__:
        avail = __context__['pkg._avail']
    else:
        # get list of available packages
        avail = []
        lines = _repoquery(
            '{0} --pkgnarrow=all --all'.format(repo_arg),
            query_format='%{NAME}_|-%{ARCH}'
        )
        for line in lines:
            try:
                name, arch = line.split('_|-')
            except ValueError:
                continue
            if normalize:
                avail.append(normalize_name('.'.join((name, arch))))
            else:
                avail.append('.'.join((name, arch)))
        __context__['pkg._avail'] = avail

    ret = {}
    repoquery_cmd = repoquery_base + ' {0}'.format(" ".join(names))
    provides = sorted(
        set(x.name for x in _repoquery_pkginfo(repoquery_cmd))
    )
    for name in names:
        ret.setdefault(name, {})['found'] = name in avail
        if not ret[name]['found']:
            if name in provides:
                # Package was not in avail but was found by the repoquery_cmd
                ret[name]['found'] = True
            else:
                ret[name]['suggestions'] = provides
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
        Refesh a disabled repo using this option

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

    repo_arg = _get_repo_options(**kwargs)
    exclude_arg = _get_excludes_option(**kwargs)
    branch_arg = _get_branch_option(**kwargs)

    clean_cmd = 'yum -q clean expire-cache {repo} {exclude} {branch}'.format(
        repo=repo_arg,
        exclude=exclude_arg,
        branch=branch_arg
    )
    update_cmd = 'yum -q check-update {repo} {exclude} {branch}'.format(
        repo=repo_arg,
        exclude=exclude_arg,
        branch=branch_arg
    )

    __salt__['cmd.run'](clean_cmd)
    return retcodes.get(
        __salt__['cmd.retcode'](update_cmd, ignore_retcode=True),
        False
    )


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


def group_install(name,
                  skip=(),
                  include=(),
                  **kwargs):
    '''
    .. versionadded:: 2014.1.0

    Install the passed package group(s). This is basically a wrapper around
    pkg.install, which performs package group resolution for the user. This
    function is currently considered experimental, and should be expected to
    undergo changes.

    name
        Package group to install. To install more than one group, either use a
        comma-separated list or pass the value as a python list.

        CLI Examples:

        .. code-block:: bash

            salt '*' pkg.group_install 'Group 1'
            salt '*' pkg.group_install 'Group 1,Group 2'
            salt '*' pkg.group_install '["Group 1", "Group 2"]'

    skip
        The name(s), in a list, of any packages that would normally be
        installed by the package group ("default" packages), which should not
        be installed. Can be passed either as a comma-separated list or a
        python list.

        CLI Examples:

        .. code-block:: bash

            salt '*' pkg.group_install 'My Group' skip='foo,bar'
            salt '*' pkg.group_install 'My Group' skip='["foo", "bar"]'

    include
        The name(s), in a list, of any packages which are included in a group,
        which would not normally be installed ("optional" packages). Note that
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
    groups = name.split(',') if isinstance(name, string_types) else name

    if not groups:
        raise SaltInvocationError('no groups specified')
    elif not isinstance(groups, list):
        raise SaltInvocationError('\'groups\' must be a list')

    # pylint: disable=maybe-no-member
    if isinstance(skip, string_types):
        skip = skip.split(',')
    if not isinstance(skip, (list, tuple)):
        raise SaltInvocationError('\'skip\' must be a list')

    if isinstance(include, string_types):
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


def install(name=None,
            refresh=False,
            skip_verify=False,
            pkgs=None,
            sources=None,
            reinstall=False,
            normalize=True,
            **kwargs):
    '''
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

        Works with sources when the package header of the source can be
        matched to the name and version of an installed package.

        .. versionadded:: 2014.7.0

    skip_verify
        Skip the GPG verification check (e.g., ``--nogpgcheck``)

    version
        Install a specific version of the package, e.g. 1.2.3-4.el5. Ignored
        if "pkgs" or "sources" is passed.


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

    normalize
        Normalize the package name by removing the architecture.  Default is True.
        This is useful for poorly created packages which might include the
        architecture as an actual part of the name such as kernel modules
        which match a specific kernel version.

        .. versionadded:: 2014.7.0

    Example:

    .. code-block:: bash

        salt -G role:nsd pkg.install gpfs.gplbin-2.6.32-279.31.1.el6.x86_64 normalize=False


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

    old = list_pkgs()
    targets = []
    downgrade = []
    to_reinstall = {}
    if pkg_type == 'repository':
        pkg_params_items = six.iteritems(pkg_params)
    else:
        pkg_params_items = []
        for pkg_source in pkg_params:
            rpm_info = _rpm_pkginfo(pkg_source)
            if rpm_info is not None:
                pkg_params_items.append([rpm_info.name, rpm_info.version, pkg_source])
            else:
                pkg_params_items.append([pkg_source, None, pkg_source])

    for pkg_item_list in pkg_params_items:
        pkgname = pkg_item_list[0]
        version_num = pkg_item_list[1]
        if version_num is None:
            if reinstall and pkg_type == 'repository' and pkgname in old:
                to_reinstall[pkgname] = pkgname
            else:
                targets.append(pkgname)
        else:
            cver = old.get(pkgname, '')
            arch = ''
            try:
                namepart, archpart = pkgname.rsplit('.', 1)
            except ValueError:
                pass
            else:
                if archpart in __ARCHES:
                    arch = '.' + archpart
                    pkgname = namepart

            if pkg_type == 'repository':
                pkgstr = '"{0}-{1}{2}"'.format(pkgname, version_num, arch)
            else:
                pkgstr = pkg_item_list[2]
            if reinstall and cver \
                    and salt.utils.compare_versions(ver1=version_num,
                                                    oper='==',
                                                    ver2=cver,
                                                    cmp_func=version_cmp):
                to_reinstall[pkgname] = pkgstr
            elif not cver or salt.utils.compare_versions(ver1=version_num,
                                                         oper='>=',
                                                         ver2=cver,
                                                         cmp_func=version_cmp):
                targets.append(pkgstr)
            else:
                downgrade.append(pkgstr)

    if targets:
        cmd = 'yum -y {repo} {exclude} {branch} {gpgcheck} install {pkg}'.format(
            repo=repo_arg,
            exclude=exclude_arg,
            branch=branch_arg,
            gpgcheck='--nogpgcheck' if skip_verify else '',
            pkg=' '.join(targets),
        )
        __salt__['cmd.run'](cmd, output_loglevel='trace')

    if downgrade:
        cmd = 'yum -y {repo} {exclude} {branch} {gpgcheck} downgrade {pkg}'.format(
            repo=repo_arg,
            exclude=exclude_arg,
            branch=branch_arg,
            gpgcheck='--nogpgcheck' if skip_verify else '',
            pkg=' '.join(downgrade),
        )
        __salt__['cmd.run'](cmd, output_loglevel='trace')

    if to_reinstall:
        cmd = 'yum -y {repo} {exclude} {branch} {gpgcheck} reinstall {pkg}'.format(
            repo=repo_arg,
            exclude=exclude_arg,
            branch=branch_arg,
            gpgcheck='--nogpgcheck' if skip_verify else '',
            pkg=' '.join(six.itervalues(to_reinstall)),
        )
        __salt__['cmd.run'](cmd, output_loglevel='trace')

    __context__.pop('pkg.list_pkgs', None)
    new = list_pkgs()
    ret = salt.utils.compare_dicts(old, new)
    for pkgname in to_reinstall:
        if not pkgname not in old:
            ret.update({pkgname: {'old': old.get(pkgname, ''),
                                  'new': new.get(pkgname, '')}})
        else:
            if pkgname not in ret:
                ret.update({pkgname: {'old': old.get(pkgname, ''),
                                      'new': new.get(pkgname, '')}})
    if ret:
        __context__.pop('pkg._avail', None)
    return ret


def upgrade(refresh=True, skip_verify=False, **kwargs):
    '''
    Run a full system upgrade, a yum upgrade

    .. versionchanged:: 2014.7.0

    Return a dict containing the new package names and versions::

        {'<package>': {'old': '<old-version>',
                       'new': '<new-version>'}}

    CLI Example:

    .. code-block:: bash

        salt '*' pkg.upgrade

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
    '''
    repo_arg = _get_repo_options(**kwargs)
    exclude_arg = _get_excludes_option(**kwargs)
    branch_arg = _get_branch_option(**kwargs)

    if salt.utils.is_true(refresh):
        refresh_db(**kwargs)

    old = list_pkgs()
    cmd = 'yum -q -y {repo} {exclude} {branch} {gpgcheck} upgrade'.format(
        repo=repo_arg,
        exclude=exclude_arg,
        branch=branch_arg,
        gpgcheck='--nogpgcheck' if skip_verify else '')

    __salt__['cmd.run'](cmd, output_loglevel='trace')
    __context__.pop('pkg.list_pkgs', None)
    new = list_pkgs()
    ret = salt.utils.compare_dicts(old, new)
    if ret:
        __context__.pop('pkg._avail', None)
    return ret


def remove(name=None, pkgs=None, **kwargs):  # pylint: disable=W0613
    '''
    Remove packages with ``yum -q -y remove``.

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
    try:
        pkg_params = __salt__['pkg_resource.parse_targets'](name, pkgs)[0]
    except MinionError as exc:
        raise CommandExecutionError(exc)

    old = list_pkgs()
    targets = [x for x in pkg_params if x in old]
    if not targets:
        return {}
    quoted_targets = [_cmd_quote(target) for target in targets]
    cmd = 'yum -q -y remove {0}'.format(' '.join(quoted_targets))
    __salt__['cmd.run'](cmd, output_loglevel='trace')
    __context__.pop('pkg.list_pkgs', None)
    new = list_pkgs()
    ret = salt.utils.compare_dicts(old, new)
    if ret:
        __context__.pop('pkg._avail', None)
    return ret


def purge(name=None, pkgs=None, **kwargs):  # pylint: disable=W0613
    '''
    Package purges are not supported by yum, this function is identical to
    :mod:`pkg.remove <salt.modules.yumpkg.remove>`.

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
    return remove(name=name, pkgs=pkgs)


def hold(name=None, pkgs=None, sources=None, **kwargs):  # pylint: disable=W0613
    '''
    .. versionadded:: 2014.7.0

    Hold packages with ``yum -q versionlock``.

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

    on_redhat_5 = __grains__.get('osmajorrelease', None) == '5'
    lock_pkg = 'yum-versionlock' if on_redhat_5 else 'yum-plugin-versionlock'
    if lock_pkg not in list_pkgs():
        raise SaltInvocationError(
            'Packages cannot be held, {0} is not installed.'.format(lock_pkg)
        )
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
            ret = check_db(pkg)
            if not ret[pkg]['found']:
                raise SaltInvocationError(
                    'Package {0} not available in repository.'.format(name)
                )
        targets.extend(pkgs)
    elif sources:
        for source in sources:
            targets.append(next(iter(source)))
    else:
        ret = check_db(name)
        if not ret[name]['found']:
            raise SaltInvocationError(
                'Package {0} not available in repository.'.format(name)
            )
        targets.append(name)

    current_locks = get_locked_packages(full=False)
    ret = {}
    for target in targets:
        if isinstance(target, dict):
            target = next(iter(target))

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
                cmd = 'yum -q versionlock {0}'.format(target)
                out = __salt__['cmd.run_all'](cmd)

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

    Hold packages with ``yum -q versionlock``.

    name
        The name of the package to be deleted.

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

    on_redhat_5 = __grains__.get('osmajorrelease', None) == '5'
    lock_pkg = 'yum-versionlock' if on_redhat_5 else 'yum-plugin-versionlock'
    if lock_pkg not in list_pkgs():
        raise SaltInvocationError(
            'Packages cannot be unheld, {0} is not installed.'.format(lock_pkg)
        )
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

    current_locks = get_locked_packages(full=True)
    ret = {}
    for target in targets:
        if isinstance(target, dict):
            target = next(iter(target))

        ret[target] = {'name': target,
                       'changes': {},
                       'result': False,
                       'comment': ''}

        search_locks = [lock for lock in current_locks
                        if target in lock]
        if search_locks:
            if 'test' in __opts__ and __opts__['test']:
                ret[target].update(result=None)
                ret[target]['comment'] = ('Package {0} is set to be unheld.'
                                          .format(target))
            else:
                quoted_targets = [_cmd_quote(item) for item in search_locks]
                cmd = 'yum -q versionlock delete {0}'.format(
                        ' '.join(quoted_targets)
                        )
                out = __salt__['cmd.run_all'](cmd)

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


def get_locked_packages(pattern=None, full=True):
    '''
    Get packages that are currently locked
    ``yum -q versionlock list``.

    CLI Example:

    .. code-block:: bash

        salt '*' pkg.get_locked_packages
    '''
    cmd = 'yum -q versionlock list'
    ret = __salt__['cmd.run'](cmd).split('\n')

    if pattern:
        if full:
            _pat = r'(\d\:{0}\-\S+)'.format(pattern)
        else:
            _pat = r'\d\:({0}\-\S+)'.format(pattern)
    else:
        if full:
            _pat = r'(\d\:\w+(?:[\.\-][^\-]+)*-\S+)'
        else:
            _pat = r'\d\:(\w+(?:[\.\-][^\-]+)*-\S+)'
    pat = re.compile(_pat)

    current_locks = []
    for item in ret:
        match = pat.search(item)
        if match:
            if not full:
                woarch = match.group(1).rsplit('.', 1)[0]
                worel = woarch.rsplit('-', 1)[0]
                wover = worel.rsplit('-', 1)[0]
                _match = wover
            else:
                _match = match.group(1)
            current_locks.append(_match)
    return current_locks


def verify(*names, **kwargs):
    '''
    .. versionadded:: 2014.1.0

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


def group_list():
    '''
    .. versionadded:: 2014.1.0

    Lists all groups known by yum on this system

    CLI Example:

    .. code-block:: bash

        salt '*' pkg.group_list
    '''
    ret = {'installed': [], 'available': [], 'available languages': {}}
    cmd = 'yum grouplist'
    out = __salt__['cmd.run_stdout'](cmd, output_loglevel='trace').splitlines()
    key = None
    for idx in range(len(out)):
        if out[idx] == 'Installed Groups:':
            key = 'installed'
            continue
        elif out[idx] == 'Available Groups:':
            key = 'available'
            continue
        elif out[idx] == 'Available Language Groups:':
            key = 'available languages'
            continue
        elif out[idx] == 'Done':
            continue

        if key is None:
            continue

        if key != 'available languages':
            ret[key].append(out[idx].strip())
        else:
            line = out[idx].strip()
            try:
                name, lang = re.match(r'(.+) \[(.+)\]', line).groups()
            except AttributeError:
                pass
            else:
                ret[key][line] = {'name': name, 'language': lang}
    return ret


def group_info(name):
    '''
    .. versionadded:: 2014.1.0

    Lists packages belonging to a certain group

    CLI Example:

    .. code-block:: bash

        salt '*' pkg.group_info 'Perl Support'
    '''
    # Not using _repoquery_pkginfo() here because group queries are handled
    # differently, and ignore the '--queryformat' param
    ret = {
        'mandatory packages': [],
        'optional packages': [],
        'default packages': [],
        'description': ''
    }
    cmd_template = 'repoquery --plugins --group --grouppkgs={0} --list {1}'

    cmd = cmd_template.format('all', _cmd_quote(name))
    out = __salt__['cmd.run_stdout'](cmd, output_loglevel='trace')
    all_pkgs = set(out.splitlines())

    if not all_pkgs:
        raise CommandExecutionError('Group {0!r} not found'.format(name))

    for pkgtype in ('mandatory', 'optional', 'default'):
        cmd = cmd_template.format(pkgtype, _cmd_quote(name))
        packages = set(
            __salt__['cmd.run_stdout'](
                cmd, output_loglevel='trace'
            ).splitlines()
        )
        ret['{0} packages'.format(pkgtype)].extend(sorted(packages))
        all_pkgs -= packages

    # 'contitional' is not a valid --grouppkgs value. Any pkgs that show up
    # in '--grouppkgs=all' that aren't in mandatory, optional, or default are
    # considered to be conditional packages.
    ret['conditional packages'] = sorted(all_pkgs)

    cmd = 'repoquery --plugins --group --info {0}'.format(_cmd_quote(name))
    out = __salt__['cmd.run_stdout'](
            cmd, output_loglevel='trace'
            )
    if out:
        ret['description'] = '\n'.join(out.splitlines()[1:]).strip()

    return ret


def group_diff(name):
    '''
    .. versionadded:: 2014.1.0

    Lists packages belonging to a certain group, and which are installed

    CLI Example:

    .. code-block:: bash

        salt '*' pkg.group_diff 'Perl Support'
    '''
    ret = {
        'mandatory packages': {'installed': [], 'not installed': []},
        'optional packages': {'installed': [], 'not installed': []},
        'default packages': {'installed': [], 'not installed': []},
        'conditional packages': {'installed': [], 'not installed': []},
    }
    pkgs = list_pkgs()
    group_pkgs = group_info(name)
    for pkgtype in ('mandatory', 'optional', 'default', 'conditional'):
        for member in group_pkgs.get('{0} packages'.format(pkgtype), []):
            key = '{0} packages'.format(pkgtype)
            if member in pkgs:
                ret[key]['installed'].append(member)
            else:
                ret[key]['not installed'].append(member)
    return ret


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
    log.debug('Searching for repos in {0}'.format(basedirs))
    for bdir in basedirs:
        if not os.path.exists(bdir):
            continue
        for repofile in os.listdir(bdir):
            repopath = '{0}/{1}'.format(bdir, repofile)
            if not repofile.endswith('.repo'):
                continue
            filerepos = _parse_repo_file(repopath)[1]
            for reponame in filerepos.keys():
                repo = filerepos[reponame]
                repo['file'] = repopath
                repos[reponame] = repo
    return repos


def get_repo(repo, basedir=None, **kwargs):  # pylint: disable=W0613
    '''
    Display a repo from <basedir> (default basedir: all dirs in `reposdir` yum option).

    CLI Examples:

    .. code-block:: bash

        salt '*' pkg.get_repo myrepo
        salt '*' pkg.get_repo myrepo basedir=/path/to/dir
        salt '*' pkg.get_repo myrepo basedir=/path/to/dir,/path/to/another/dir
    '''
    repos = list_repos(basedir)

    # Find out what file the repo lives in
    repofile = ''
    for arepo in repos.keys():
        if arepo == repo:
            repofile = repos[arepo]['file']

    if repofile:
        # Return just one repo
        filerepos = _parse_repo_file(repofile)[1]
        return filerepos[repo]
    return {}


def del_repo(repo, basedir=None, **kwargs):  # pylint: disable=W0613
    '''
    Delete a repo from <basedir> (default basedir: all dirs in `reposdir` yum option).

    If the .repo file that the repo exists in does not contain any other repo
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
    for arepo in repos.keys():
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
    for stanza in filerepos.keys():
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
                not in filerepos[repo].keys():
            raise SaltInvocationError(
                'Cannot delete baseurl without specifying mirrorlist'
            )
    if 'mirrorlist' in todelete:
        if 'baseurl' not in repo_opts and 'baseurl' \
                not in filerepos[repo].keys():
            raise SaltInvocationError(
                'Cannot delete mirrorlist without specifying baseurl'
            )

    # Delete anything in the todelete list
    for key in todelete:
        if key in filerepos[repo].keys():
            del filerepos[repo][key]

    # Old file or new, write out the repos(s)
    filerepos[repo].update(repo_opts)
    content = header
    for stanza in filerepos.keys():
        comments = ''
        if 'comments' in filerepos[stanza].keys():
            comments = '\n'.join(filerepos[stanza]['comments'])
            del filerepos[stanza]['comments']
        content += '\n[{0}]'.format(stanza)
        for line in filerepos[stanza].keys():
            content += '\n{0}={1}'.format(line, filerepos[stanza][line])
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
                        'Failed to parse line in {0}, offending line was '
                        '\'{1}\''.format(filename, line.rstrip())
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


def expand_repo_def(repokwargs):
    '''
    Take a repository definition and expand it to the full pkg repository dict
    that can be used for comparison. This is a helper function to make
    certain repo managers sane for comparison in the pkgrepo states.

    There is no use to calling this function via the CLI.
    '''
    # YUM doesn't need the data massaged.
    return repokwargs


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
    for path in paths:
        cmd = 'rpm -qf --queryformat {0} {1!r}'.format(
                _cmd_quote('%{{NAME}}'),
                path
                )
        ret[path] = __salt__['cmd.run_stdout'](
                cmd.format(path),
                output_loglevel='trace'
                )
        if 'not owned' in ret[path].lower():
            ret[path] = ''
    if len(ret) == 1:
        return next(ret.itervalues())
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
        log.debug('Removing cached package {0}'.format(purge_target))
        try:
            os.unlink(purge_target)
        except OSError as exc:
            log.error('Unable to remove {0}: {1}'.format(purge_target, exc))

    __salt__['cmd.run'](
        'yumdownloader -q {0} --destdir={1}'.format(
            ' '.join(packages), CACHE_DIR
        ),
        output_loglevel='trace'
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
                ret[path] = __salt__['lowpkg.diff'](local_pkgs[pkg]['path'], path) or 'Unchanged'

    return ret
