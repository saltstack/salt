# -*- coding: utf-8 -*-
'''
Installation of packages using OS package managers such as yum or apt-get
=========================================================================

Salt can manage software packages via the pkg state module, packages can be
set up to be installed, latest, removed and purged. Package management
declarations are typically rather simple:

.. code-block:: yaml

    vim:
      pkg.installed

A more involved example involves pulling from a custom repository.
Note that the pkgrepo has a require_in clause.
This is necessary and can not be replaced by a require clause in the pkg.

.. code-block:: yaml

    base:
      pkgrepo.managed:
        - humanname: Logstash PPA
        - name: ppa:wolfnet/logstash
        - dist: precise
        - file: /etc/apt/sources.list.d/logstash.list
        - keyid: 28B04E4A
        - keyserver: keyserver.ubuntu.com
        - require_in:
          - pkg: logstash

    logstash:
      pkg.installed
'''

from __future__ import absolute_import

# Import python libs
import logging
import os
import re

# Import salt libs
import salt.utils
from salt.output import nested
from salt.utils import namespaced_function as _namespaced_function
from salt.utils.odict import OrderedDict as _OrderedDict
from salt.ext.six import string_types
import salt.ext.six as six  # pylint: disable=W0611
from salt.exceptions import (
    CommandExecutionError, MinionError, SaltInvocationError
)
from salt.modules.pkg_resource import _repack_pkgs

_repack_pkgs = _namespaced_function(_repack_pkgs, globals())

if salt.utils.is_windows():
    from salt.modules.win_pkg import _get_package_info
    from salt.modules.win_pkg import get_repo_data
    from salt.modules.win_pkg import _get_latest_pkg_version
    from salt.modules.win_pkg import _reverse_cmp_pkg_versions
    _get_package_info = _namespaced_function(_get_package_info, globals())
    get_repo_data = _namespaced_function(get_repo_data, globals())
    _get_latest_pkg_version = \
        _namespaced_function(_get_latest_pkg_version, globals())
    _reverse_cmp_pkg_versions = \
        _namespaced_function(_reverse_cmp_pkg_versions, globals())
    # The following imports are used by the namespaced win_pkg funcs
    # and need to be included in their globals.
    # pylint: disable=W0611
    try:
        import msgpack
    except ImportError:
        import msgpack_pure as msgpack
    from distutils.version import LooseVersion  # pylint: disable=E0611,F0401
    # pylint: enable=W0611

log = logging.getLogger(__name__)


def __virtual__():
    '''
    Only make these states available if a pkg provider has been detected or
    assigned for this minion
    '''
    return 'pkg.install' in __salt__


def __gen_rtag():
    '''
    Return the location of the refresh tag
    '''
    return os.path.join(__opts__['cachedir'], 'pkg_refresh')


def _fulfills_version_spec(versions, oper, desired_version):
    '''
    Returns True if any of the installed versions match the specified version,
    otherwise returns False
    '''
    cmp_func = __salt__.get('pkg.version_cmp')
    for ver in versions:
        if salt.utils.compare_versions(ver1=ver,
                                       oper=oper,
                                       ver2=desired_version,
                                       cmp_func=cmp_func):
            return True
    return False


def _find_unpurge_targets(desired):
    '''
    Find packages which are marked to be purged but can't yet be removed
    because they are dependencies for other installed packages. These are the
    packages which will need to be 'unpurged' because they are part of
    pkg.installed states. This really just applies to Debian-based Linuxes.
    '''
    return [
        x for x in desired
        if x in __salt__['pkg.list_pkgs'](purge_desired=True)
    ]


def _find_remove_targets(name=None,
                         version=None,
                         pkgs=None,
                         **kwargs):
    '''
    Inspect the arguments to pkg.removed and discover what packages need to
    be removed. Return a dict of packages to remove.
    '''
    cur_pkgs = __salt__['pkg.list_pkgs'](versions_as_list=True, **kwargs)
    if pkgs:
        to_remove = _repack_pkgs(pkgs)

        if not to_remove:
            # Badly-formatted SLS
            return {'name': name,
                    'changes': {},
                    'result': False,
                    'comment': 'Invalidly formatted pkgs parameter. See '
                               'minion log.'}
    else:
        _normalize_name = __salt__.get('pkg.normalize_name', lambda pkgname: pkgname)
        to_remove = {_normalize_name(name): version}

        cver = cur_pkgs.get(name, [])

    version_spec = False
    # Find out which packages will be targeted in the call to pkg.remove
    # Check current versions against specified versions
    targets = []
    problems = []
    for pkgname, pkgver in to_remove.items():
        cver = cur_pkgs.get(pkgname, [])
        # Package not installed, no need to remove
        if not cver:
            continue
        # No version specified and pkg is installed
        elif __salt__['pkg_resource.version_clean'](pkgver) is None:
            targets.append(pkgname)
            continue
        version_spec = True
        match = re.match('^([<>])?(=)?([^<>=]+)$', pkgver)
        if not match:
            msg = 'Invalid version specification {0!r} for package ' \
                  '{1!r}.'.format(pkgver, pkgname)
            problems.append(msg)
        else:
            gt_lt, eq, verstr = match.groups()
            comparison = gt_lt or ''
            comparison += eq or ''
            # A comparison operator of "=" is redundant, but possible.
            # Change it to "==" so that the version comparison works
            if comparison in ['=', '']:
                comparison = '=='
            if not _fulfills_version_spec(cver, comparison, verstr):
                log.debug('Current version ({0} did not match ({1}) specified ({2}), skipping remove {3}'.format(cver, comparison, verstr, pkgname))
            else:
                targets.append(pkgname)

    if problems:
        return {'name': name,
                'changes': {},
                'result': False,
                'comment': ' '.join(problems)}

    if not targets:
        # All specified packages are already absent
        msg = (
            'All specified packages{0} are already absent.'
            .format(' (matching specified versions)' if version_spec else '')
        )
        return {'name': name,
                'changes': {},
                'result': True,
                'comment': msg}

    return targets


def _find_install_targets(name=None,
                          version=None,
                          pkgs=None,
                          sources=None,
                          skip_suggestions=False,
                          pkg_verify=False,
                          normalize=True,
                          **kwargs):
    '''
    Inspect the arguments to pkg.installed and discover what packages need to
    be installed. Return a dict of desired packages
    '''
    if all((pkgs, sources)):
        return {'name': name,
                'changes': {},
                'result': False,
                'comment': 'Only one of "pkgs" and "sources" is permitted.'}

    # dict for packages that fail pkg.verify and their altered files
    altered_files = {}
    # Get the ignore_types list if any from the pkg_verify argument
    if isinstance(pkg_verify, list) and any(x.get('ignore_types') is not None
                                        for x in pkg_verify
                                        if isinstance(x, _OrderedDict)
                                        and 'ignore_types' in x):
        ignore_types = next(x.get('ignore_types')
                            for x in pkg_verify
                            if 'ignore_types' in x)
    else:
        ignore_types = []

    cur_pkgs = __salt__['pkg.list_pkgs'](versions_as_list=True, **kwargs)
    if any((pkgs, sources)):
        if pkgs:
            desired = _repack_pkgs(pkgs)
        elif sources:
            desired = __salt__['pkg_resource.pack_sources'](sources)

        if not desired:
            # Badly-formatted SLS
            return {'name': name,
                    'changes': {},
                    'result': False,
                    'comment': 'Invalidly formatted {0!r} parameter. See '
                               'minion log.'.format('pkgs' if pkgs
                                                    else 'sources')}
        to_unpurge = _find_unpurge_targets(desired)
    else:
        if salt.utils.is_windows():
            pkginfo = _get_package_info(name)
            if not pkginfo:
                return {'name': name,
                        'changes': {},
                        'result': False,
                        'comment': 'Package {0} not found in the '
                                   'repository.'.format(name)}
            if version is None:
                version = _get_latest_pkg_version(pkginfo)

        if normalize:
            _normalize_name = __salt__.get('pkg.normalize_name', lambda pkgname: pkgname)
            desired = {_normalize_name(name): version}
        else:
            desired = {name: version}

        to_unpurge = _find_unpurge_targets(desired)

        cver = cur_pkgs.get(name, [])
        if name not in to_unpurge:
            if version and version in cver and not pkg_verify:
                # The package is installed and is the correct version
                return {'name': name,
                        'changes': {},
                        'result': True,
                        'comment': 'Version {0} of package {1!r} is already '
                                   'installed.'.format(version, name)}

            # if cver is not an empty string, the package is already installed
            elif cver and version is None and not pkg_verify:
                # The package is installed
                return {'name': name,
                        'changes': {},
                        'result': True,
                        'comment': 'Package {0} is already '
                                   'installed.'.format(name)}

    version_spec = False
    # Find out which packages will be targeted in the call to pkg.install
    if sources:
        targets = []
        to_reinstall = []
        for x in desired:
            if x not in cur_pkgs:
                targets.append(x)
            elif pkg_verify:
                retval = __salt__['pkg.verify'](x, ignore_types=ignore_types)
                if retval:
                    to_reinstall.append(x)
                    altered_files[x] = retval
    else:
        # Check for alternate package names if strict processing is not
        # enforced.
        # Takes extra time. Disable for improved performance
        if not skip_suggestions:
            # Perform platform-specific pre-flight checks
            problems = _preflight_check(desired, **kwargs)
            comments = []
            if problems.get('no_suggest'):
                comments.append(
                    'The following package(s) were not found, and no possible '
                    'matches were found in the package db: '
                    '{0}'.format(', '.join(sorted(problems['no_suggest'])))
                )
            if problems.get('suggest'):
                for pkgname, suggestions in problems['suggest'].items():
                    comments.append(
                        'Package {0!r} not found (possible matches: {1})'
                        .format(pkgname, ', '.join(suggestions))
                    )
            if comments:
                if len(comments) > 1:
                    comments.append('')
                return {'name': name,
                        'changes': {},
                        'result': False,
                        'comment': '. '.join(comments).rstrip()}

        # Check current versions against desired versions
        targets = {}
        to_reinstall = {}
        problems = []
        for pkgname, pkgver in desired.items():
            cver = cur_pkgs.get(pkgname, [])
            # Package not yet installed, so add to targets
            if not cver:
                targets[pkgname] = pkgver
                continue
            elif not __salt__['pkg_resource.check_extra_requirements'](pkgname,
                                                                       pkgver):
                targets[pkgname] = pkgver
                continue
            # No version specified and pkg is installed
            elif __salt__['pkg_resource.version_clean'](pkgver) is None:
                if pkg_verify:
                    retval = __salt__['pkg.verify'](pkgname, ignore_types=ignore_types)
                    if retval:
                        to_reinstall[pkgname] = pkgver
                        altered_files[pkgname] = retval
                continue
            version_spec = True
            match = re.match('^([<>])?(=)?([^<>=]+)$', pkgver)
            if not match:
                msg = 'Invalid version specification {0!r} for package ' \
                      '{1!r}.'.format(pkgver, pkgname)
                problems.append(msg)
            else:
                gt_lt, eq, verstr = match.groups()
                comparison = gt_lt or ''
                comparison += eq or ''
                # A comparison operator of "=" is redundant, but possible.
                # Change it to "==" so that the version comparison works
                if comparison in ['=', '']:
                    comparison = '=='
                if 'allow_updates' in kwargs:
                    if kwargs['allow_updates']:
                        comparison = '>='
                if not _fulfills_version_spec(cver, comparison, verstr):
                    log.debug('Current version ({0} did not match ({1}) desired ({2}), add to targets'.format(cver, comparison, verstr))
                    targets[pkgname] = pkgver
                elif pkg_verify and comparison == '==':
                    retval = __salt__['pkg.verify'](pkgname, ignore_types=ignore_types)
                    if retval:
                        to_reinstall[pkgname] = pkgver
                        altered_files[pkgname] = retval

        if problems:
            return {'name': name,
                    'changes': {},
                    'result': False,
                    'comment': ' '.join(problems)}

    if not any((targets, to_unpurge, to_reinstall)):
        # All specified packages are installed
        msg = (
            'All specified packages are already installed{0}.'
            .format(' and are at the desired version' if version_spec else '')
        )
        return {'name': name,
                'changes': {},
                'result': True,
                'comment': msg}

    return desired, targets, to_unpurge, to_reinstall, altered_files


def _verify_install(desired, new_pkgs):
    '''
    Determine whether or not the installed packages match what was requested in
    the SLS file.
    '''
    ok = []
    failed = []
    for pkgname, pkgver in desired.items():
        cver = new_pkgs.get(pkgname)
        if not cver:
            failed.append(pkgname)
            continue
        elif not __salt__['pkg_resource.version_clean'](pkgver):
            ok.append(pkgname)
            continue
        elif pkgver.endswith("*") and cver[0].startswith(pkgver[:-1]):
            ok.append(pkgname)
            continue

        match = re.match('^([<>])?(=)?([^<>=]+)$', pkgver)
        gt_lt, eq, verstr = match.groups()
        comparison = gt_lt or ''
        comparison += eq or ''
        # A comparison operator of "=" is redundant, but possible.
        # Change it to "==" so that the version comparison works.
        if comparison in ('=', ''):
            comparison = '=='
        if _fulfills_version_spec(cver, comparison, verstr):
            ok.append(pkgname)
        else:
            failed.append(pkgname)
    return ok, failed


def _get_desired_pkg(name, desired):
    '''
    Helper function that retrieves and nicely formats the desired pkg (and
    version if specified) so that helpful information can be printed in the
    comment for the state.
    '''
    if not desired[name] or desired[name].startswith(('<', '>', '=')):
        oper = ''
    else:
        oper = '='
    return '{0}{1}{2}'.format(name, oper,
                              '' if not desired[name] else desired[name])


def _preflight_check(desired, fromrepo, **kwargs):
    '''
    Perform platform-specific checks on desired packages
    '''
    if 'pkg.check_db' not in __salt__:
        return {}
    ret = {'suggest': {}, 'no_suggest': []}
    pkginfo = __salt__['pkg.check_db'](
        *list(desired.keys()), fromrepo=fromrepo, **kwargs
    )
    for pkgname in pkginfo:
        if pkginfo[pkgname]['found'] is False:
            if pkginfo[pkgname]['suggestions']:
                ret['suggest'][pkgname] = pkginfo[pkgname]['suggestions']
            else:
                ret['no_suggest'].append(pkgname)
    return ret


def _nested_output(obj):
    '''
    Serialize obj and format for output
    '''
    nested.__opts__ = __opts__
    ret = nested.output(obj).rstrip()
    return ret


def installed(
        name,
        version=None,
        refresh=None,
        fromrepo=None,
        skip_verify=False,
        skip_suggestions=False,
        pkgs=None,
        sources=None,
        allow_updates=False,
        pkg_verify=False,
        normalize=True,
        **kwargs):
    '''
    Ensure that the package is installed, and that it is the correct version
    (if specified).

    name
        The name of the package to be installed. This parameter is ignored if
        either "pkgs" or "sources" is used. Additionally, please note that this
        option can only be used to install packages from a software repository.
        To install a package file manually, use the "sources" option detailed
        below.

    fromrepo
        Specify a repository from which to install

        .. note::

            Distros which use APT (Debian, Ubuntu, etc.) do not have a concept
            of repositories, in the same way as YUM-based distros do. When a
            source is added, it is assigned to a given release. Consider the
            following source configuration:

            .. code-block:: text

                deb http://ppa.launchpad.net/saltstack/salt/ubuntu precise main

            The packages provided by this source would be made available via
            the ``precise`` release, therefore ``fromrepo`` would need to be
            set to ``precise`` for Salt to install the package from this
            source.

            Having multiple sources in the same release may result in the
            default install candidate being newer than what is desired. If this
            is the case, the desired version must be specified using the
            ``version`` parameter.

            If the ``pkgs`` parameter is being used to install multiple
            packages in the same state, then instead of using ``version``,
            use the method of version specification described in the **Multiple
            Package Installation Options** section below.

            Running the shell command ``apt-cache policy pkgname`` on a minion
            can help elucidate the APT configuration and aid in properly
            configuring states:

            .. code-block:: bash

                root@saltmaster:~# salt ubuntu01 cmd.run 'apt-cache policy ffmpeg'
                ubuntu01:
                    ffmpeg:
                    Installed: (none)
                    Candidate: 7:0.10.11-1~precise1
                    Version table:
                        7:0.10.11-1~precise1 0
                            500 http://ppa.launchpad.net/jon-severinsson/ffmpeg/ubuntu/ precise/main amd64 Packages
                        4:0.8.10-0ubuntu0.12.04.1 0
                            500 http://us.archive.ubuntu.com/ubuntu/ precise-updates/main amd64 Packages
                            500 http://security.ubuntu.com/ubuntu/ precise-security/main amd64 Packages
                        4:0.8.1-0ubuntu1 0
                            500 http://us.archive.ubuntu.com/ubuntu/ precise/main amd64 Packages

            The release is located directly after the source's URL. The actual
            release name is the part before the slash, so to install version
            **4:0.8.10-0ubuntu0.12.04.1** either ``precise-updates`` or
            ``precise-security`` could be used for the ``fromrepo`` value.

    skip_verify
        Skip the GPG verification check for the package to be installed

    skip_suggestions
        Force strict package naming. Disables lookup of package alternatives.

        .. versionadded:: 2014.1.1

    version
        Install a specific version of a package. This option is ignored if
        either "pkgs" or "sources" is used. Currently, this option is supported
        for the following pkg providers: :mod:`apt <salt.modules.aptpkg>`,
        :mod:`ebuild <salt.modules.ebuild>`,
        :mod:`pacman <salt.modules.pacman>`,
        :mod:`yumpkg <salt.modules.yumpkg>`, and
        :mod:`zypper <salt.modules.zypper>`. The version number includes the
        release designation where applicable, to allow Salt to target a
        specific release of a given version. When in doubt, using the
        ``pkg.latest_version`` function for an uninstalled package will tell
        you the version available.

        .. code-block:: bash

            # salt myminion pkg.latest_version httpd
            myminion:
                2.2.15-30.el6.centos

        Also, while this function is not yet implemented for all pkg frontends,
        :mod:`pkg.list_repo_pkgs <salt.modules.yumpkg.list_repo_pkgs>` will
        show all versions available in the various repositories for a given
        package, irrespective of whether or not it is installed.

        .. code-block:: bash

            # salt myminion pkg.list_repo_pkgs httpd
            myminion:
                ----------
                base:
                    |_
                      ----------
                      httpd:
                          2.2.15-29.el6.centos
                updates:
                    |_
                      ----------
                      httpd:
                          2.2.15-30.el6.centos

        The version strings returned by either of these functions can be used
        as version specifiers in pkg states.

    refresh
        Update the repo database of available packages prior to installing the
        requested package.

    hold
        Force the package to be held at the current installed version.
        Currently works with YUM & APT based systems.

        .. versionadded:: 2014.7.0

    allow_updates
        Allow the package to be updated outside Salt's control (e.g. auto updates on Windows).
        This means a package on the Minion can have a newer version than the latest available
        in the repository without enforcing a re-installation of the package.

        .. versionadded:: 2014.7.0

    Example:

    .. code-block:: yaml

        httpd:
          pkg.installed:
            - fromrepo: mycustomrepo
            - skip_verify: True
            - skip_suggestions: True
            - version: 2.0.6~ubuntu3
            - refresh: True
            - hold: False

    pkg_verify
        .. versionadded:: 2014.7.0

        For requested packages that are already installed and would not be targeted for
        upgrade or downgrade, use pkg.verify to determine if any of the files installed
        by the package have been altered. If files have been altered, the reinstall
        option of pkg.install is used to force a reinstall.  Types to ignore can be
        passed to pkg.verify (see example below).  Currently, this option is supported
        for the following pkg providers: :mod:`yumpkg <salt.modules.yumpkg>`.

    Examples:

    .. code-block:: yaml

        httpd:
          pkg.installed:
            - version: 2.2.15-30.el6.centos
            - pkg_verify: True

    .. code-block:: yaml

        mypkgs:
          pkg.installed:
            - pkgs:
              - foo
              - bar: 1.2.3-4
              - baz
            - pkg_verify:
              - ignore_types: [config,doc]

    normalize
        Normalize the package name by removing the architecture.  Default is True.
        This is useful for poorly created packages which might include the
        architecture as an actual part of the name such as kernel modules
        which match a specific kernel version.

        .. versionadded:: 2014.7.0

    Example:

    .. code-block:: yaml

        gpfs.gplbin-2.6.32-279.31.1.el6.x86_64:
          pkg.installed:
            - normalize: False

    **Multiple Package Installation Options: (not supported in Windows or
    pkgng)**

    pkgs
        A list of packages to install from a software repository. All packages
        listed under ``pkgs`` will be installed via a single command.

    Example:

    .. code-block:: yaml

        mypkgs:
          pkg.installed:
            - pkgs:
              - foo
              - bar
              - baz
            - hold: True

    ``NOTE:`` For :mod:`apt <salt.modules.aptpkg>`,
    :mod:`ebuild <salt.modules.ebuild>`,
    :mod:`pacman <salt.modules.pacman>`, :mod:`yumpkg <salt.modules.yumpkg>`,
    and :mod:`zypper <salt.modules.zypper>`, version numbers can be specified
    in the ``pkgs`` argument. For example:

    .. code-block:: yaml

        mypkgs:
          pkg.installed:
            - pkgs:
              - foo
              - bar: 1.2.3-4
              - baz

    Additionally, :mod:`ebuild <salt.modules.ebuild>`,
    :mod:`pacman <salt.modules.pacman>` and
    :mod:`zypper <salt.modules.zypper>` support the ``<``, ``<=``, ``>=``, and
    ``>`` operators for more control over what versions will be installed. For
    example:

    .. code-block:: yaml

        mypkgs:
          pkg.installed:
            - pkgs:
              - foo
              - bar: '>=1.2.3-4'
              - baz

    ``NOTE:`` When using comparison operators, the expression must be enclosed
    in quotes to avoid a YAML render error.

    With :mod:`ebuild <salt.modules.ebuild>` is also possible to specify a use
    flag list and/or if the given packages should be in package.accept_keywords
    file and/or the overlay from which you want the package to be installed.
    For example:

    .. code-block:: yaml

        mypkgs:
          pkg.installed:
            - pkgs:
              - foo: '~'
              - bar: '~>=1.2:slot::overlay[use,-otheruse]'
              - baz

    names
        A list of packages to install from a software repository. Each package
        will be installed individually by the package manager.

        .. warning::

            Unlike ``pkgs``, the ``names`` parameter cannot specify a version.
            In addition, it makes a separate call to the package management
            frontend to install each package, whereas ``pkgs`` makes just a
            single call. It is therefore recommended to use ``pkgs`` instead of
            ``names`` to install multiple packages, both for the additional
            features and the performance improvement that it brings.

    sources
        A list of packages to install, along with the source URI or local path
        from which to install each package. In the example below, ``foo``,
        ``bar``, ``baz``, etc. refer to the name of the package, as it would
        appear in the output of the ``pkg.version`` or ``pkg.list_pkgs`` salt
        CLI commands.

    .. code-block:: yaml

        mypkgs:
          pkg.installed:
            - sources:
              - foo: salt://rpms/foo.rpm
              - bar: http://somesite.org/bar.rpm
              - baz: ftp://someothersite.org/baz.rpm
              - qux: /minion/path/to/qux.rpm

    install_recommends
        Whether to install the packages marked as recommended.  Default is True.
        Currently only works with APT based systems.

        .. versionadded:: 2015.5.0

    .. code-block:: yaml

        httpd:
          pkg.installed:
            - install_recommends: False

    only_upgrade
        Only upgrade the packages, if they are already installed. Default is False.
        Currently only works with APT based systems.

        .. versionadded:: 2015.5.0

    .. code-block:: yaml

        httpd:
          pkg.installed:
            - only_upgrade: True

    '''
    if isinstance(pkgs, list) and len(pkgs) == 0:
        return {'name': name,
                'changes': {},
                'result': True,
                'comment': 'No packages to install provided'}

    kwargs['saltenv'] = __env__
    rtag = __gen_rtag()
    refresh = bool(
        salt.utils.is_true(refresh)
        or (os.path.isfile(rtag) and refresh is not False)
    )
    if not isinstance(pkg_verify, list):
        pkg_verify = pkg_verify is True
    if (pkg_verify or isinstance(pkg_verify, list)) and 'pkg.verify' not in __salt__:
        return {'name': name,
                'changes': {},
                'result': False,
                'comment': 'pkg.verify not implemented'}

    if not isinstance(version, string_types) and version is not None:
        version = str(version)

    kwargs['allow_updates'] = allow_updates
    result = _find_install_targets(name, version, pkgs, sources,
                                   fromrepo=fromrepo,
                                   skip_suggestions=skip_suggestions,
                                   pkg_verify=pkg_verify,
                                   normalize=normalize,
                                   **kwargs)

    try:
        desired, targets, to_unpurge, to_reinstall, altered_files = result
    except ValueError:
        # _find_install_targets() found no targets or encountered an error

        # check that the hold function is available
        if 'pkg.hold' in __salt__:
            if 'hold' in kwargs:
                try:
                    if kwargs['hold']:
                        hold_ret = __salt__['pkg.hold'](
                            name=name, pkgs=pkgs, sources=sources
                        )
                    else:
                        hold_ret = __salt__['pkg.unhold'](
                            name=name, pkgs=pkgs, sources=sources
                        )
                except (CommandExecutionError, SaltInvocationError) as exc:
                    return {'name': name,
                            'changes': {},
                            'result': False,
                            'comment': str(exc)}

                if 'result' in hold_ret and not hold_ret['result']:
                    return {'name': name,
                            'changes': {},
                            'result': False,
                            'comment': 'An error was encountered while '
                                       'holding/unholding package(s): {0}'
                                       .format(hold_ret['comment'])}
                else:
                    modified_hold = [hold_ret[x] for x in hold_ret
                                     if hold_ret[x]['changes']]
                    not_modified_hold = [hold_ret[x] for x in hold_ret
                                         if not hold_ret[x]['changes']
                                         and hold_ret[x]['result']]
                    failed_hold = [hold_ret[x] for x in hold_ret
                                   if not hold_ret[x]['result']]

                    if modified_hold:
                        for i in modified_hold:
                            result['comment'] += ' {0}'.format(i['comment'])
                            result['result'] = i['result']
                            result['changes'][i['name']] = i['changes']

                    if not_modified_hold:
                        for i in not_modified_hold:
                            result['comment'] += ' {0}'.format(i['comment'])
                            result['result'] = i['result']

                    if failed_hold:
                        for i in failed_hold:
                            result['comment'] += ' {0}'.format(i['comment'])
                            result['result'] = i['result']
        return result

    if to_unpurge and 'lowpkg.unpurge' not in __salt__:
        return {'name': name,
                'changes': {},
                'result': False,
                'comment': 'lowpkg.unpurge not implemented'}

    # Remove any targets not returned by _find_install_targets
    if pkgs:
        pkgs = [dict([(x, y)]) for x, y in targets.items()]
        pkgs.extend([dict([(x, y)]) for x, y in to_reinstall.items()])
    elif sources:
        oldsources = sources
        sources = [x for x in oldsources if next(iter(list(x.keys()))) in targets]
        sources.extend([x for x in oldsources if next(iter(list(x.keys()))) in to_reinstall])

    comment = []
    if __opts__['test']:
        if targets:
            if sources:
                summary = ', '.join(targets)
            else:
                summary = ', '.join([_get_desired_pkg(x, targets)
                                     for x in targets])
            comment.append('The following packages are set to be '
                           'installed/updated: {0}'.format(summary))
        if to_unpurge:
            comment.append(
                'The following packages will have their selection status '
                'changed from \'purge\' to \'install\': {0}'
                .format(', '.join(to_unpurge))
            )
        if to_reinstall:
            # Add a comment for each package in to_reinstall with its pkg.verify output
            for x in to_reinstall:
                if sources:
                    pkgstr = x
                else:
                    pkgstr = _get_desired_pkg(x, to_reinstall)
                comment.append('\nPackage {0} is set to be reinstalled because the '
                               'following files have been altered:'.format(pkgstr))
                comment.append('\n' + _nested_output(altered_files[x]))
        return {'name': name,
                'changes': {},
                'result': None,
                'comment': ' '.join(comment)}

    changes = {'installed': {}}
    modified_hold = None
    not_modified_hold = None
    failed_hold = None
    if targets or to_reinstall:
        reinstall = bool(to_reinstall)
        try:
            pkg_ret = __salt__['pkg.install'](name,
                                            refresh=refresh,
                                            version=version,
                                            fromrepo=fromrepo,
                                            skip_verify=skip_verify,
                                            pkgs=pkgs,
                                            sources=sources,
                                            reinstall=reinstall,
                                            normalize=normalize,
                                            **kwargs)

            if os.path.isfile(rtag) and refresh:
                os.remove(rtag)
        except CommandExecutionError as exc:
            return {'name': name,
                    'changes': {},
                    'result': False,
                    'comment': 'An error was encountered while installing '
                               'package(s): {0}'.format(exc)}

        if isinstance(pkg_ret, dict):
            changes['installed'].update(pkg_ret)
        elif isinstance(pkg_ret, string_types):
            comment.append(pkg_ret)

        if 'pkg.hold' in __salt__:
            if 'hold' in kwargs:
                try:
                    if kwargs['hold']:
                        hold_ret = __salt__['pkg.hold'](
                            name=name, pkgs=pkgs, sources=sources
                        )
                    else:
                        hold_ret = __salt__['pkg.unhold'](
                            name=name, pkgs=pkgs, sources=sources
                        )
                except (CommandExecutionError, SaltInvocationError) as exc:
                    comment.append(str(exc))
                    return {'name': name,
                            'changes': changes,
                            'result': False,
                            'comment': ' '.join(comment)}
                else:
                    if 'result' in hold_ret and not hold_ret['result']:
                        return {'name': name,
                                'changes': {},
                                'result': False,
                                'comment': 'An error was encountered while '
                                           'holding/unholding package(s): {0}'
                                           .format(hold_ret['comment'])}
                    else:
                        modified_hold = [hold_ret[x] for x in hold_ret
                                         if hold_ret[x]['changes']]
                        not_modified_hold = [hold_ret[x] for x in hold_ret
                                             if not hold_ret[x]['changes']
                                             and hold_ret[x]['result']]
                        failed_hold = [hold_ret[x] for x in hold_ret
                                       if not hold_ret[x]['result']]

    if to_unpurge:
        changes['purge_desired'] = __salt__['lowpkg.unpurge'](*to_unpurge)

    # Analyze pkg.install results for packages in targets
    if sources:
        modified = [x for x in changes['installed'] if x in targets]
        not_modified = [x for x in desired if x not in targets and x not in to_reinstall]
        failed = [x for x in targets if x not in modified]
    else:
        ok, failed = \
            _verify_install(
                desired, __salt__['pkg.list_pkgs'](
                    versions_as_list=True, **kwargs
                )
            )
        modified = [x for x in ok if x in targets]
        not_modified = [x for x in ok if x not in targets and x not in to_reinstall]
        failed = [x for x in failed if x in targets]

    # If there was nothing unpurged, just set the changes dict to the contents
    # of changes['installed'].
    if not changes.get('purge_desired'):
        changes = changes['installed']

    if modified:
        if sources:
            summary = ', '.join(modified)
        else:
            summary = ', '.join([_get_desired_pkg(x, desired)
                                 for x in modified])
        if len(summary) < 20:
            comment.append('The following packages were installed/updated: '
                           '{0}'.format(summary))
        else:
            comment.append(
                '{0} targeted package{1} {2} installed/updated.'.format(
                    len(modified),
                    's' if len(modified) > 1 else '',
                    'were' if len(modified) > 1 else 'was'
                )
            )

    if modified_hold:
        for i in modified_hold:
            change_name = i['name']
            if change_name in changes:
                comment.append(i['comment'])
                if len(changes[change_name]['new']) > 0:
                    changes[change_name]['new'] += '\n'
                changes[change_name]['new'] += '{0}'.format(i['changes']['new'])
                if len(changes[change_name]['old']) > 0:
                    changes[change_name]['old'] += '\n'
                changes[change_name]['old'] += '{0}'.format(i['changes']['old'])

    # Any requested packages that were not targeted for install or reinstall
    if not_modified:
        if sources:
            summary = ', '.join(not_modified)
        else:
            summary = ', '.join([_get_desired_pkg(x, desired)
                                 for x in not_modified])
        if len(not_modified) <= 20:
            comment.append('The following packages were already installed: '
                           '{0}'.format(summary))
        else:
            comment.append(
                '{0} targeted package{1} {2} already installed.'.format(
                    len(not_modified),
                    's' if len(not_modified) > 1 else '',
                    'were' if len(not_modified) > 1 else 'was'
                )
            )

    if not_modified_hold:
        for i in not_modified_hold:
            comment.append(i['comment'])

    result = True

    if failed:
        if sources:
            summary = ', '.join(failed)
        else:
            summary = ', '.join([_get_desired_pkg(x, desired)
                                 for x in failed])
        comment.insert(0, 'The following packages failed to '
                          'install/update: {0}'.format(summary))
        result = False

    if failed_hold:
        for i in failed_hold:
            comment.append(i['comment'])
        result = False

    # Get the ignore_types list if any from the pkg_verify argument
    if isinstance(pkg_verify, list) and any(x.get('ignore_types') is not None
                                        for x in pkg_verify
                                        if isinstance(x, _OrderedDict)
                                        and 'ignore_types' in x):
        ignore_types = next(x.get('ignore_types')
                            for x in pkg_verify
                            if 'ignore_types' in x)
    else:
        ignore_types = []

    # Rerun pkg.verify for packages in to_reinstall to determine failed
    modified = []
    failed = []
    for x in to_reinstall:
        retval = __salt__['pkg.verify'](x, ignore_types=ignore_types)
        if retval:
            failed.append(x)
            altered_files[x] = retval
        else:
            modified.append(x)

    if modified:
        # Add a comment for each package in modified with its pkg.verify output
        for x in modified:
            if sources:
                pkgstr = x
            else:
                pkgstr = _get_desired_pkg(x, desired)
            comment.append('\nPackage {0} was reinstalled.  The following files '
                           'were remediated:'.format(pkgstr))
            comment.append(_nested_output(altered_files[x]))

    if failed:
        # Add a comment for each package in failed with its pkg.verify output
        for x in failed:
            if sources:
                pkgstr = x
            else:
                pkgstr = _get_desired_pkg(x, desired)
            comment.append(
                '\nReinstall was not successful for package {0}.  The following '
                'files could not be remediated:'.format(pkgstr)
            )
            comment.append(_nested_output(altered_files[x]))
        result = False

    return {'name': name,
            'changes': changes,
            'result': result,
            'comment': ' '.join(comment)}


def latest(
        name,
        refresh=None,
        fromrepo=None,
        skip_verify=False,
        pkgs=None,
        **kwargs):
    '''
    Ensure that the named package is installed and the latest available
    package. If the package can be updated, this state function will update
    the package. Generally it is better for the
    :mod:`installed <salt.states.pkg.installed>` function to be
    used, as :mod:`latest <salt.states.pkg.latest>` will update the package
    whenever a new package is available.

    name
        The name of the package to maintain at the latest available version.
        This parameter is ignored if "pkgs" is used.

    fromrepo
        Specify a repository from which to install

    skip_verify
        Skip the GPG verification check for the package to be installed

    refresh
        Update the repo database of available packages prior to installing the
        requested package.


    Multiple Package Installation Options:

    (Not yet supported for: Windows, FreeBSD, OpenBSD, MacOS, and Solaris
    pkgutil)

    pkgs
        A list of packages to maintain at the latest available version.

    .. code-block:: yaml

        mypkgs:
          pkg.latest:
            - pkgs:
              - foo
              - bar
              - baz

    install_recommends
        Whether to install the packages marked as recommended.  Default is True.
        Currently only works with APT based systems.

        .. versionadded:: 2015.5.0

    .. code-block:: yaml

        httpd:
          pkg.latest:
            - install_recommends: False

    only_upgrade
        Only upgrade the packages, if they are already installed. Default is False.
        Currently only works with APT based systems.

        .. versionadded:: 2015.5.0

    .. code-block:: yaml

        httpd:
          pkg.latest:
            - only_upgrade: True

    '''
    rtag = __gen_rtag()
    refresh = bool(
        salt.utils.is_true(refresh)
        or (os.path.isfile(rtag) and refresh is not False)
    )

    if kwargs.get('sources'):
        return {'name': name,
                'changes': {},
                'result': False,
                'comment': 'The "sources" parameter is not supported.'}
    elif pkgs:
        desired_pkgs = list(_repack_pkgs(pkgs).keys())
        if not desired_pkgs:
            # Badly-formatted SLS
            return {'name': name,
                    'changes': {},
                    'result': False,
                    'comment': 'Invalidly formatted "pkgs" parameter. See '
                               'minion log.'}
    else:
        desired_pkgs = [name]

    cur = __salt__['pkg.version'](*desired_pkgs, **kwargs)
    try:
        avail = __salt__['pkg.latest_version'](*desired_pkgs,
                                               fromrepo=fromrepo,
                                               refresh=refresh,
                                               **kwargs)
    except CommandExecutionError as exc:
        return {'name': name,
                'changes': {},
                'result': False,
                'comment': 'An error was encountered while checking the '
                           'newest available version of package(s): {0}'
                           .format(exc)}

    # Remove the rtag if it exists, ensuring only one refresh per salt run
    # (unless overridden with refresh=True)
    if os.path.isfile(rtag) and refresh:
        os.remove(rtag)

    # Repack the cur/avail data if only a single package is being checked
    if isinstance(cur, string_types):
        cur = {desired_pkgs[0]: cur}
    if isinstance(avail, string_types):
        avail = {desired_pkgs[0]: avail}

    targets = {}
    problems = []
    cmp_func = __salt__.get('pkg.version_cmp')
    for pkg in desired_pkgs:
        if not avail[pkg]:
            if not cur[pkg]:
                msg = 'No information found for {0!r}.'.format(pkg)
                log.error(msg)
                problems.append(msg)
        elif not cur[pkg] \
                or salt.utils.compare_versions(ver1=cur[pkg],
                                               oper='<',
                                               ver2=avail[pkg],
                                               cmp_func=cmp_func):
            targets[pkg] = avail[pkg]

    if problems:
        return {'name': name,
                'changes': {},
                'result': False,
                'comment': ' '.join(problems)}

    if targets:
        # Find up-to-date packages
        if not pkgs:
            # There couldn't have been any up-to-date packages if this state
            # only targeted a single package and is being allowed to proceed to
            # the install step.
            up_to_date = []
        else:
            up_to_date = [x for x in pkgs if x not in targets]

        if __opts__['test']:
            to_be_upgraded = ', '.join(sorted(targets))
            comment = 'The following packages are set to be ' \
                      'installed/upgraded: ' \
                      '{0}'.format(to_be_upgraded)
            if up_to_date:
                up_to_date_nb = len(up_to_date)
                if up_to_date_nb <= 10:
                    up_to_date_sorted = sorted(up_to_date)
                    up_to_date_details = ', '.join(
                        '{0} ({1})'.format(name, cur[name])
                        for name in up_to_date_sorted
                    )
                    comment += (
                        ' The following packages are already '
                        'up-to-date: {0}'
                    ).format(up_to_date_details)
                else:
                    comment += ' {0} packages are already up-to-date.'.format(
                        up_to_date_nb
                    )

            return {'name': name,
                    'changes': {},
                    'result': None,
                    'comment': comment}

        # Build updated list of pkgs to exclude non-targeted ones
        targeted_pkgs = list(targets.keys()) if pkgs else None

        try:
            # No need to refresh, if a refresh was necessary it would have been
            # performed above when pkg.latest_version was run.
            changes = __salt__['pkg.install'](name,
                                              refresh=False,
                                              fromrepo=fromrepo,
                                              skip_verify=skip_verify,
                                              pkgs=targeted_pkgs,
                                              **kwargs)
        except CommandExecutionError as exc:
            return {'name': name,
                    'changes': {},
                    'result': False,
                    'comment': 'An error was encountered while installing '
                               'package(s): {0}'.format(exc)}

        if changes:
            # Find failed and successful updates
            failed = [x for x in targets
                      if not changes.get(x) or changes[x]['new'] != targets[x]]
            successful = [x for x in targets if x not in failed]

            comments = []
            if failed:
                msg = 'The following packages failed to update: ' \
                      '{0}'.format(', '.join(sorted(failed)))
                comments.append(msg)
            if successful:
                msg = 'The following packages were successfully ' \
                      'installed/upgraded: ' \
                      '{0}'.format(', '.join(sorted(successful)))
                comments.append(msg)
            if up_to_date:
                if len(up_to_date) <= 10:
                    msg = 'The following packages were already up-to-date: ' \
                        '{0}'.format(', '.join(sorted(up_to_date)))
                else:
                    msg = '{0} packages were already up-to-date. '.format(
                        len(up_to_date))
                comments.append(msg)

            return {'name': name,
                    'changes': changes,
                    'result': False if failed else True,
                    'comment': ' '.join(comments)}
        else:
            if len(targets) > 10:
                comment = ('{0} targeted packages failed to update. '
                           'See debug log for details.'.format(len(targets)))
            elif len(targets) > 1:
                comment = ('The following targeted packages failed to update. '
                           'See debug log for details: ({0}).'
                           .format(', '.join(sorted(targets))))
            else:
                comment = 'Package {0} failed to ' \
                          'update.'.format(next(iter(list(targets.keys()))))
            if up_to_date:
                if len(up_to_date) <= 10:
                    comment += ' The following packages were already ' \
                        'up-to-date: ' \
                        '{0}'.format(', '.join(sorted(up_to_date)))
                else:
                    comment += '{0} packages were already ' \
                        'up-to-date.'.format(len(up_to_date))

            return {'name': name,
                    'changes': changes,
                    'result': False,
                    'comment': comment}
    else:
        if len(desired_pkgs) > 10:
            comment = 'All {0} packages are up-to-date.'.format(
                len(desired_pkgs))
        elif len(desired_pkgs) > 1:
            comment = 'All packages are up-to-date ' \
                '({0}).'.format(', '.join(sorted(desired_pkgs)))
        else:
            comment = 'Package {0} is already ' \
                'up-to-date.'.format(desired_pkgs[0])

        return {'name': name,
                'changes': {},
                'result': True,
                'comment': comment}


def _uninstall(action='remove', name=None, version=None, pkgs=None, **kwargs):
    '''
    Common function for package removal
    '''
    if action not in ('remove', 'purge'):
        return {'name': name,
                'changes': {},
                'result': False,
                'comment': 'Invalid action {0!r}. '
                           'This is probably a bug.'.format(action)}

    try:
        pkg_params = __salt__['pkg_resource.parse_targets'](name, pkgs)[0]
    except MinionError as exc:
        return {'name': name,
                'changes': {},
                'result': False,
                'comment': 'An error was encountered while parsing targets: '
                           '{0}'.format(exc)}
    targets = _find_remove_targets(name, version, pkgs, **kwargs)
    if isinstance(targets, dict) and 'result' in targets:
        return targets
    elif not isinstance(targets, list):
        return {'name': name,
                'changes': {},
                'result': False,
                'comment': 'An error was encountered while checking targets: '
                           '{0}'.format(targets)}
    if action == 'purge':
        old_removed = __salt__['pkg.list_pkgs'](versions_as_list=True,
                                                removed=True,
                                                **kwargs)
        targets.extend([x for x in pkg_params if x in old_removed])
    targets.sort()

    if not targets:
        return {'name': name,
                'changes': {},
                'result': True,
                'comment': 'None of the targeted packages are installed'
                           '{0}'.format(' or partially installed'
                                        if action == 'purge' else '')}

    if __opts__['test']:
        return {'name': name,
                'changes': {},
                'result': None,
                'comment': 'The following packages will be {0}d: '
                           '{1}.'.format(action, ', '.join(targets))}

    changes = __salt__['pkg.{0}'.format(action)](name, pkgs=pkgs, **kwargs)
    new = __salt__['pkg.list_pkgs'](versions_as_list=True, **kwargs)
    failed = [x for x in pkg_params if x in new]
    if action == 'purge':
        new_removed = __salt__['pkg.list_pkgs'](versions_as_list=True,
                                                removed=True,
                                                **kwargs)
        failed.extend([x for x in pkg_params if x in new_removed])
    failed.sort()

    if failed:
        return {'name': name,
                'changes': changes,
                'result': False,
                'comment': 'The following packages failed to {0}: '
                           '{1}.'.format(action, ', '.join(failed))}

    comments = []
    not_installed = sorted([x for x in pkg_params if x not in targets])
    if not_installed:
        comments.append('The following packages were not installed: '
                        '{0}'.format(', '.join(not_installed)))
        comments.append('The following packages were {0}d: '
                        '{1}.'.format(action, ', '.join(targets)))
    else:
        comments.append('All targeted packages were {0}d.'.format(action))

    return {'name': name,
            'changes': changes,
            'result': True,
            'comment': ' '.join(comments)}


def removed(name, version=None, pkgs=None, **kwargs):
    '''
    Verify that a package is not installed, calling ``pkg.remove`` if necessary
    to remove the package.

    name
        The name of the package to be removed.

    version
        The version of the package that should be removed. Don't do anything if
        the package is installed with an unmatching version.


    Multiple Package Options:

    pkgs
        A list of packages to remove. Must be passed as a python list. The
        ``name`` parameter will be ignored if this option is passed. It accepts
        version numbers as well.

    .. versionadded:: 0.16.0
    '''
    try:
        return _uninstall(action='remove', name=name, version=version,
                          pkgs=pkgs, **kwargs)
    except CommandExecutionError as exc:
        return {'name': name,
                'changes': {},
                'result': False,
                'comment': str(exc)}


def purged(name, version=None, pkgs=None, **kwargs):
    '''
    Verify that a package is not installed, calling ``pkg.purge`` if necessary
    to purge the package. All configuration files are also removed.

    name
        The name of the package to be purged.

    version
        The version of the package that should be removed. Don't do anything if
        the package is installed with an unmatching version.


    Multiple Package Options:

    pkgs
        A list of packages to purge. Must be passed as a python list. The
        ``name`` parameter will be ignored if this option is passed. It accepts
        version numbers as well.

    .. versionadded:: 0.16.0
    '''
    try:
        return _uninstall(action='purge', name=name, version=version,
                          pkgs=pkgs, **kwargs)
    except CommandExecutionError as exc:
        return {'name': name,
                'changes': {},
                'result': False,
                'comment': str(exc)}


def uptodate(name, refresh=False, **kwargs):
    '''
    .. versionadded:: 2014.7.0

    Verify that the system is completely up to date.

    name
        The name has no functional value and is only used as a tracking
        reference

    refresh
        refresh the package database before checking for new upgrades

    kwargs
        Any keyword arguments to pass through to ``pkg.upgrade``.

        .. versionadded:: 2015.5.0
    '''
    ret = {'name': name,
           'changes': {},
           'result': False,
           'comment': 'Failed to update.'}

    if 'pkg.list_upgrades' not in __salt__:
        ret['comment'] = 'State pkg.uptodate is not available'
        return ret

    if isinstance(refresh, bool):
        try:
            packages = __salt__['pkg.list_upgrades'](refresh=refresh)
        except Exception as e:
            ret['comment'] = str(e)
            return ret
    else:
        ret['comment'] = 'refresh must be a boolean.'
        return ret

    if not packages:
        ret['comment'] = 'System is already up-to-date.'
        ret['result'] = True
        return ret
    elif __opts__['test']:
        ret['comment'] = 'System update will be performed'
        ret['result'] = None
        return ret

    updated = __salt__['pkg.upgrade'](refresh=refresh, **kwargs)

    if updated.get('result') is False:
        ret.update(updated)
    elif updated:
        ret['changes'] = updated
        ret['comment'] = 'Upgrade successful.'
        ret['result'] = True
    else:
        ret['comment'] = 'Upgrade failed.'

    return ret


def mod_init(low):
    '''
    Set a flag to tell the install functions to refresh the package database.
    This ensures that the package database is refreshed only once during
    a state run significantly improving the speed of package management
    during a state run.

    It sets a flag for a number of reasons, primarily due to timeline logic.
    When originally setting up the mod_init for pkg a number of corner cases
    arose with different package managers and how they refresh package data.

    It also runs the "ex_mod_init" from the package manager module that is
    currently loaded. The "ex_mod_init" is expected to work as a normal
    "mod_init" function.

    .. seealso::
       :py:func:`salt.modules.ebuild.ex_mod_init`

    '''
    ret = True
    if 'pkg.ex_mod_init' in __salt__:
        ret = __salt__['pkg.ex_mod_init'](low)

    if low['fun'] == 'installed' or low['fun'] == 'latest':
        rtag = __gen_rtag()
        if not os.path.exists(rtag):
            salt.utils.fopen(rtag, 'w+').write('')
        return ret
    return False


def mod_aggregate(low, chunks, running):
    '''
    The mod_aggregate function which looks up all packages in the available
    low chunks and merges them into a single pkgs ref in the present low data
    '''
    pkgs = []
    agg_enabled = [
            'installed',
            'latest',
            'removed',
            'purged',
            ]
    if low.get('fun') not in agg_enabled:
        return low
    for chunk in chunks:
        tag = salt.utils.gen_state_tag(chunk)
        if tag in running:
            # Already ran the pkg state, skip aggregation
            continue
        if chunk.get('state') == 'pkg':
            if '__agg__' in chunk:
                continue
            # Check for the same function
            if chunk.get('fun') != low.get('fun'):
                continue
            # Pull out the pkg names!
            if 'pkgs' in chunk:
                pkgs.extend(chunk['pkgs'])
                chunk['__agg__'] = True
            elif 'name' in chunk:
                pkgs.append(chunk['name'])
                chunk['__agg__'] = True
    if pkgs:
        if 'pkgs' in low:
            low['pkgs'].extend(pkgs)
        else:
            low['pkgs'] = pkgs
    return low
