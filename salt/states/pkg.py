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
        - name: deb http://ppa.launchpad.net/wolfnet/logstash/ubuntu precise main
        - dist: precise
        - file: /etc/apt/sources.list.d/logstash.list
        - keyid: 28B04E4A
        - keyserver: keyserver.ubuntu.com
        - require_in:
          - pkg: logstash

    logstash:
      pkg.installed
'''

# Import python libs
import logging
import os
import re

# Import salt libs
import salt.utils
from salt.exceptions import CommandExecutionError, MinionError
from salt.modules.pkg_resource import _repack_pkgs

if salt.utils.is_windows():
    from salt.utils import namespaced_function as _namespaced_function
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
    import msgpack
    from distutils.version import LooseVersion  # pylint: disable=E0611,F0401

log = logging.getLogger(__name__)


def __virtual__():
    '''
    Only make these states available if a pkg provider has been detected or
    assigned for this minion
    '''
    return 'pkg' if 'pkg.install' in __salt__ else False


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
    for ver in versions:
        if salt.utils.compare_versions(ver1=ver,
                                       oper=oper,
                                       ver2=desired_version,
                                       cmp_func=__salt__.get('version_cmp')):
            return True
    return False


def _find_install_targets(name=None,
                          version=None,
                          pkgs=None,
                          sources=None,
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
        desired = {name: version}

        cver = cur_pkgs.get(name, [])
        if version and version in cver:
            # The package is installed and is the correct version
            return {'name': name,
                    'changes': {},
                    'result': True,
                    'comment': ('Version {0} of package {1!r} is already '
                                'installed').format(version, name)}

        # if cver is not an empty string, the package is already installed
        elif cver and version is None:
            # The package is installed
            return {'name': name,
                    'changes': {},
                    'result': True,
                    'comment': 'Package {0} is already installed'.format(name)}

    version_spec = False
    # Find out which packages will be targeted in the call to pkg.install
    if sources:
        targets = [x for x in desired if x not in cur_pkgs]
    else:
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
            for pkgname, suggestions in problems['suggest'].iteritems():
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
        problems = []
        for pkgname, pkgver in desired.iteritems():
            cver = cur_pkgs.get(pkgname, [])
            # Package not yet installed, so add to targets
            if not cver:
                targets[pkgname] = pkgver
                continue
            elif not __salt__['pkg_resource.check_extra_requirements'](pkgname,
                                                                       pkgver):
                targets[pkgname] = pkgver
                continue
            # No version specified and pkg is installed, do not add to targets
            elif __salt__['pkg_resource.version_clean'](pkgver) is None:
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
                    # Current version did not match desired, add to targets
                    targets[pkgname] = pkgver

        if problems:
            return {'name': name,
                    'changes': {},
                    'result': False,
                    'comment': ' '.join(problems)}

    if not targets:
        # All specified packages are installed
        msg = 'All specified packages are already installed{0}.'.format(
            ' and are at the desired version' if version_spec else '')
        return {'name': name,
                'changes': {},
                'result': True,
                'comment': msg}

    return desired, targets


def _verify_install(desired, new_pkgs):
    '''
    Determine whether or not the installed packages match what was requested in
    the SLS file.
    '''
    ok = []
    failed = []
    for pkgname, pkgver in desired.iteritems():
        cver = new_pkgs.get(pkgname)
        if not cver:
            failed.append(pkgname)
            continue
        elif not __salt__['pkg_resource.version_clean'](pkgver):
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
    Perform platform-specifc checks on desired packages
    '''
    if 'pkg.check_db' not in __salt__:
        return {}
    ret = {'suggest': {}, 'no_suggest': []}
    pkginfo = __salt__['pkg.check_db'](
        *desired.keys(), fromrepo=fromrepo, **kwargs
    )
    for pkgname in pkginfo:
        if pkginfo[pkgname]['found'] is False:
            if pkginfo[pkgname]['suggestions']:
                ret['suggest'][pkgname] = pkginfo[pkgname]['suggestions']
            else:
                ret['no_suggest'].append(pkgname)
    return ret


def installed(
        name,
        version=None,
        refresh=False,
        fromrepo=None,
        skip_verify=False,
        pkgs=None,
        sources=None,
        **kwargs):
    '''
    Verify that the package is installed, and that it is the correct version
    (if specified).

    name
        The name of the package to be installed. This parameter is ignored if
        either "pkgs" or "sources" is used. Additionally, please note that this
        option can only be used to install packages from a software repository.
        To install a package file manually, use the "sources" option detailed
        below.

    fromrepo
        Specify a repository from which to install

    skip_verify
        Skip the GPG verification check for the package to be installed

    version
        Install a specific version of a package. This option is ignored if
        either "pkgs" or "sources" is used. Currently, this option is supported
        for the following pkg providers: :mod:`apt <salt.modules.apt>`,
        :mod:`ebuild <salt.modules.ebuild>`,
        :mod:`pacman <salt.modules.pacman>`,
        :mod:`yumpkg <salt.modules.yumpkg>`,
        :mod:`yumpkg5 <salt.modules.yumpkg5>`, and
        :mod:`zypper <salt.modules.zypper>`.

    refresh
        Update the repo database of available packages prior to installing the
        requested package.

    Usage::

        httpd:
          pkg.installed:
            - fromrepo: mycustomrepo
            - skip_verify: True
            - version: 2.0.6~ubuntu3
            - refresh: True

    Multiple Package Installation Options: (not supported in Windows or pkgng)

    pkgs
        A list of packages to install from a software repository.

    Usage::

        mypkgs:
          pkg.installed:
            - pkgs:
              - foo
              - bar
              - baz

    ``NOTE:`` For :mod:`apt <salt.modules.apt>`,
    :mod:`ebuild <salt.modules.ebuild>`,
    :mod:`pacman <salt.modules.pacman>`, :mod:`yumpkg <salt.modules.yumpkg>`,
    :mod:`yumpkg5 <salt.modules.yumpkg5>`,
    and :mod:`zypper <salt.modules.zypper>`, version numbers can be specified
    in the ``pkgs`` argument. Example::

        mypkgs:
          pkg.installed:
            - pkgs:
              - foo
              - bar: 1.2.3-4
              - baz

    Additionally, :mod:`ebuild <salt.modules.ebuild>`,
    :mod:`pacman <salt.modules.pacman>` and
    :mod:`zypper <salt.modules.zypper>` support the ``<``, ``<=``, ``>=``, and
    ``>`` operators for more control over what versions will be installed.
    Example::

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
    Example::

        mypkgs:
            pkg.installed:
                - pkgs:
                    - foo: '~'
                    - bar: '~>=1.2:slot::overlay[use,-otheruse]'
                    - baz

    sources
        A list of packages to install, along with the source URI or local path
        from which to install each package. In the example below, ``foo``,
        ``bar``, ``baz``, etc. refer to the name of the package, as it would
        appear in the output of the ``pkg.version`` or ``pkg.list_pkgs`` salt
        CLI commands.

    Usage::

        mypkgs:
          pkg.installed:
            - sources:
              - foo: salt://rpms/foo.rpm
              - bar: http://somesite.org/bar.rpm
              - baz: ftp://someothersite.org/baz.rpm
              - qux: /minion/path/to/qux.rpm
    '''
    rtag = __gen_rtag()
    refresh = bool(salt.utils.is_true(refresh) or os.path.isfile(rtag))

    if not isinstance(version, basestring) and version is not None:
        version = str(version)

    result = _find_install_targets(name, version, pkgs, sources,
                                   fromrepo=fromrepo, **kwargs)
    try:
        desired, targets = result
    except ValueError:
        # _find_install_targets() found no targets or encountered an error
        return result

    # Remove any targets that are already installed, to avoid upgrading them
    if pkgs:
        pkgs = [dict([(x, y)]) for x, y in targets.iteritems()]
    elif sources:
        sources = [x for x in sources if x.keys()[0] in targets]

    if __opts__['test']:
        if targets:
            if sources:
                summary = ', '.join(targets)
            else:
                summary = ', '.join([_get_desired_pkg(x, targets)
                                     for x in targets])
            comment = 'The following packages are set to be ' \
                      'installed/updated: {0}.'.format(summary)
        else:
            comment = ''
        return {'name': name,
                'changes': {},
                'result': None,
                'comment': comment}

    comment = []
    try:
        pkg_ret = __salt__['pkg.install'](name,
                                          refresh=refresh,
                                          version=version,
                                          fromrepo=fromrepo,
                                          skip_verify=skip_verify,
                                          pkgs=pkgs,
                                          sources=sources,
                                          **kwargs)

        if os.path.isfile(rtag):
            os.remove(rtag)
    except CommandExecutionError as exc:
        return {'name': name,
                'changes': {},
                'result': False,
                'comment': 'An error was encountered while installing '
                           'package(s): {0}'.format(exc)}

    if isinstance(pkg_ret, dict):
        changes = pkg_ret
    elif isinstance(pkg_ret, basestring):
        changes = {}
        comment.append(pkg_ret)
    else:
        changes = {}

    if sources:
        modified = [x for x in changes.keys() if x in targets]
        not_modified = [x for x in desired if x not in targets]
        failed = [x for x in targets if x not in modified]
    else:
        ok, failed = \
            _verify_install(
                desired, __salt__['pkg.list_pkgs'](
                    versions_as_list=True, **kwargs
                )
            )
        modified = [x for x in ok if x in targets]
        not_modified = [x for x in ok if x not in targets]

    if modified:
        if sources:
            summary = ', '.join(modified)
        else:
            summary = ', '.join([_get_desired_pkg(x, desired)
                                 for x in modified])
        if len(summary) < 20:
            comment.append('The following packages were installed/updated: '
                           '{0}.'.format(summary))
        else:
            comment.append(
                '{0} targeted package{1} {2} installed/updated.'.format(
                    len(modified),
                    's' if len(modified) > 1 else '',
                    'were' if len(modified) > 1 else 'was'
                )
            )

    if not_modified:
        if sources:
            summary = ', '.join(not_modified)
        else:
            summary = ', '.join([_get_desired_pkg(x, desired)
                                 for x in not_modified])
        if len(not_modified) <= 20:
            comment.append('The following packages were already installed: '
                           '{0}.'.format(summary))
        else:
            comment.append(
                '{0} targeted package{1} {2} already installed.'.format(
                    len(not_modified),
                    's' if len(not_modified) > 1 else '',
                    'were' if len(not_modified) > 1 else 'was'
                )
            )

    if failed:
        if sources:
            summary = ', '.join(failed)
        else:
            summary = ', '.join([_get_desired_pkg(x, desired)
                                 for x in failed])
        comment.insert(0, 'The following packages failed to '
                          'install/update: {0}.'.format(summary))
        return {'name': name,
                'changes': changes,
                'result': False,
                'comment': ' '.join(comment)}
    else:
        return {'name': name,
                'changes': changes,
                'result': True,
                'comment': ' '.join(comment)}


def latest(
        name,
        refresh=False,
        fromrepo=None,
        skip_verify=False,
        pkgs=None,
        **kwargs):
    '''
    Verify that the named package is installed and the latest available
    package. If the package can be updated this state function will update
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


    Multiple Package Installation Options:

    (Not yet supported for: Windows, FreeBSD, OpenBSD, MacOS, and Solaris
    pkgutil)

    pkgs
        A list of packages to maintain at the latest available version.

    Usage::

        mypkgs:
          pkg.latest:
            - pkgs:
              - foo
              - bar
              - baz
    '''
    rtag = __gen_rtag()

    if kwargs.get('sources'):
        return {'name': name,
                'changes': {},
                'result': False,
                'comment': 'The "sources" parameter is not supported.'}
    elif pkgs:
        desired_pkgs = _repack_pkgs(pkgs).keys()
        if not desired_pkgs:
            # Badly-formatted SLS
            return {'name': name,
                    'changes': {},
                    'result': False,
                    'comment': 'Invalidly formatted "pkgs" parameter. See '
                               'minion log.'}
    else:
        desired_pkgs = [name]

    if salt.utils.is_true(refresh) or os.path.isfile(rtag):
        refresh = True
    else:
        refresh = False

    cur = __salt__['pkg.version'](*desired_pkgs, **kwargs)
    avail = __salt__['pkg.latest_version'](*desired_pkgs,
                                           fromrepo=fromrepo,
                                           refresh=refresh,
                                           **kwargs)
    # Remove the rtag if it exists, ensuring only one refresh per salt run
    # (unless overridden with refresh=True)
    if os.path.isfile(rtag):
        os.remove(rtag)

    # Repack the cur/avail data if only a single package is being checked
    if isinstance(cur, basestring):
        cur = {desired_pkgs[0]: cur}
    if isinstance(avail, basestring):
        avail = {desired_pkgs[0]: avail}

    targets = {}
    problems = []
    for pkg in desired_pkgs:
        if not avail[pkg]:
            if not cur[pkg]:
                msg = 'No information found for {0!r}.'.format(pkg)
                log.error(msg)
                problems.append(msg)
        elif not cur[pkg] \
                or salt.utils.compare_versions(
                    ver1=cur[pkg],
                    oper='<',
                    ver2=avail[pkg],
                    cmp_func=__salt__.get('version_cmp')):
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
            to_be_upgraded = ', '.join(sorted(targets.keys()))
            comment = 'The following packages are set to be ' \
                      'installed/upgraded: ' \
                      '{0}.'.format(to_be_upgraded)
            if up_to_date:
                if len(up_to_date) <= 10:
                    comment += ' The following packages are already ' \
                        'up-to-date: {0}.'.format(', '.join(sorted(up_to_date)))
                else:
                    comment += ' {0} packages are already up-to-date.'.format(
                        len(up_to_date))

            return {'name': name,
                    'changes': {},
                    'result': None,
                    'comment': comment}

        # Build updated list of pkgs to exclude non-targeted ones
        targeted_pkgs = targets.keys() if pkgs else None

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
                      '{0}.'.format(', '.join(sorted(failed)))
                comments.append(msg)
            if successful:
                msg = 'The following packages were successfully ' \
                      'installed/upgraded: ' \
                      '{0}.'.format(', '.join(sorted(successful)))
                comments.append(msg)
            if up_to_date:
                if len(up_to_date) <= 10:
                    msg = 'The following packages were already up-to-date: ' \
                        '{0}.'.format(', '.join(sorted(up_to_date)))
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
                           .format(', '.join(sorted(targets.keys()))))
            else:
                comment = 'Package {0} failed to ' \
                          'update.'.format(targets.keys()[0])
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


def _uninstall(action='remove', name=None, pkgs=None, **kwargs):
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
    old = __salt__['pkg.list_pkgs'](versions_as_list=True, **kwargs)
    targets = [x for x in pkg_params if x in old]
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
                        '{0}.'.format(', '.join(not_installed)))
        comments.append('The following packages were {0}d: '
                        '{1}.'.format(action, ', '.join(targets)))
    else:
        comments.append('All targeted packages were {0}d.'.format(action))

    return {'name': name,
            'changes': changes,
            'result': True,
            'comment': ' '.join(comments)}


def removed(name, pkgs=None, **kwargs):
    '''
    Verify that a package is not installed, calling ``pkg.remove`` if necessary
    to remove the package.

    name
        The name of the package to be removed.


    Multiple Package Options:

    pkgs
        A list of packages to remove. Must be passed as a python list. The
        ``name`` parameter will be ignored if this option is passed.

    .. versionadded:: 0.16.0
    '''
    try:
        return _uninstall(action='remove', name=name, pkgs=pkgs, **kwargs)
    except CommandExecutionError as exc:
        return {'name': name,
                'changes': {},
                'result': False,
                'comment': str(exc)}


def purged(name, pkgs=None, **kwargs):
    '''
    Verify that a package is not installed, calling ``pkg.purge`` if necessary
    to purge the package.

    name
        The name of the package to be purged.


    Multiple Package Options:

    pkgs
        A list of packages to purge. Must be passed as a python list. The
        ``name`` parameter will be ignored if this option is passed.

    .. versionadded:: 0.16.0
    '''
    try:
        return _uninstall(action='purge', name=name, pkgs=pkgs, **kwargs)
    except CommandExecutionError as exc:
        return {'name': name,
                'changes': {},
                'result': False,
                'comment': str(exc)}


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
