'''
Installation of packages using OS package managers such as yum or apt-get.
==========================================================================

Salt can manage software packages via the pkg state module, packages can be
set up to be installed, latest, removed and purged. Package management
declarations are typically rather simple:

.. code-block:: yaml

    vim:
      pkg.installed
'''

# Import python libs
import logging
import os

# Import salt libs
import salt.utils

log = logging.getLogger(__name__)


def __gen_rtag():
    '''
    Return the location of the refresh tag
    '''
    return os.path.join(__opts__['cachedir'], 'pkg_refresh')


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
        either "pkgs" or "sources" is used.

    Usage::

        httpd:
          pkg.installed:
            - fromrepo: mycustomrepo
            - skip_verify: True
            - version: 2.0.6~ubuntu3


    Multiple Package Installation Options: (not supported in Windows)

    pkgs
        A list of packages to install from a software repository.

    Usage::

        mypkgs:
          pkg.installed:
            - pkgs:
              - foo
              - bar
              - baz

    sources
        A list of packages to install, along with the source URI or local path
        from which to install each package.

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

    if all((pkgs, sources)):
        return {'name': name,
                'changes': {},
                'result': False,
                'comment': 'Only one of "pkgs" and "sources" is permitted.'}

    old_pkgs = __salt__['pkg.list_pkgs']()
    if any((pkgs, sources)):
        if pkgs:
            desired_pkgs = __salt__['pkg_resource.pack_pkgs'](pkgs)
        elif sources:
            desired_pkgs = __salt__['pkg_resource.pack_sources'](sources)

        if not desired_pkgs:
            # Badly-formatted SLS
            return {'name': name,
                    'changes': {},
                    'result': False,
                    'comment': 'Invalidly formatted "{0}" parameter. See '
                               'minion log.'.format('pkgs' if pkgs
                                                    else 'sources')}

        targets = [x for x in desired_pkgs if x not in old_pkgs]

        if not targets:
            # All specified packages are installed
            return {'name': name,
                    'changes': {},
                    'result': True,
                    'comment': 'All specified packages are already '
                               'installed'.format(name)}
        else:
            if pkgs:
                pkgs = targets
            elif sources:
                # Remove any targets that are already installed, to avoid
                # upgrading them.
                sources = [x for x in sources if x.keys()[0] in targets]

    else:
        targets = [name]

        cver = old_pkgs.get(name, '')
        if cver == version:
            # The package is installed and is the correct version
            return {'name': name,
                    'changes': {},
                    'result': True,
                    'comment': ('Package {0} is already installed and is the '
                                'correct version').format(name)}

        # if cver is not an empty string, the package is already installed
        elif cver and version is None:
            # The package is installed
            return {'name': name,
                    'changes': {},
                    'result': True,
                    'comment': 'Package {0} is already installed'.format(name)}

    if not sources:
        problems = __salt__['pkg_resource.check_targets'](targets)
        if problems:
            return {'name': name,
                    'changes': {},
                    'result': False,
                    'comment': ' '.join(problems)}

    if __opts__['test']:
        if len(targets) > 1:
            comment = 'The following packages are set to be ' \
                      'installed: {0}'.format(', '.join(targets))
        else:
            comment = 'Package {0} is set to be installed'.format(targets[0])
        return {'name': name,
                'changes': {},
                'result': None,
                'comment': comment}

    if refresh or os.path.isfile(rtag):
        changes = __salt__['pkg.install'](name,
                                          refresh=True,
                                          version=version,
                                          fromrepo=fromrepo,
                                          skip_verify=skip_verify,
                                          pkgs=pkgs,
                                          sources=sources,
                                          **kwargs)
        if os.path.isfile(rtag):
            os.remove(rtag)
    else:
        changes = __salt__['pkg.install'](name,
                                          version=version,
                                          fromrepo=fromrepo,
                                          skip_verify=skip_verify,
                                          pkgs=pkgs,
                                          sources=sources,
                                          **kwargs)

    installed = [x for x in changes.keys() if x in targets]

    # Some (or all) of the requested packages failed to install
    if len(installed) != len(targets):
        if len(targets) > 1:
            failed = [x for x in targets if x not in installed]
            comment = 'The following packages failed to install: ' \
                      '{0}'.format(', '.join(sorted(failed)))
        else:
            comment = 'Package {0} failed to install'.format(targets[0])

        return {'name': name,
                'changes': changes,
                'result': False,
                'comment': comment}

    # Success!
    if len(targets) > 1:
        comment = 'The following pacakages were installed: ' \
                  '{0}'.format(', '.join(sorted(targets)))
    else:
        comment = 'Package {0} installed'.format(targets[0])

    return {'name': name,
            'changes': changes,
            'result': True,
            'comment': comment}


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
    the package. Generally it is better for the ``installed`` function to be
    used, as ``latest`` will update the package whenever a new package is
    available.

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
        desired_pkgs = __salt__['pkg_resource.pack_pkgs'](pkgs)
        if not desired_pkgs:
            # Badly-formatted SLS
            return {'name': name,
                    'changes': {},
                    'result': False,
                    'comment': 'Invalidly formatted "pkgs" parameter. See '
                               'minion log.'}
    else:
        desired_pkgs = [name]

    cur = __salt__['pkg.version'](*desired_pkgs)
    avail = __salt__['pkg.available_version'](*desired_pkgs)

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
                msg = 'No information found for "{0}".'.format(pkg)
                log.error(msg)
                problems.append(msg)
        else:
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
                comment += ' The following packages are already ' \
                           'up-to-date: ' \
                           '{0}.'.format(', '.join(sorted(up_to_date)))

            return {'name': name,
                    'changes': {},
                    'result': None,
                    'comment': comment}

        # Build updated list of pkgs to exclude non-targeted ones
        targeted_pkgs = targets.keys() if pkgs else None

        if refresh or os.path.isfile(rtag):
            changes = __salt__['pkg.install'](name,
                                              refresh=True,
                                              fromrepo=fromrepo,
                                              skip_verify=skip_verify,
                                              pkgs=targeted_pkgs,
                                              **kwargs)
            if os.path.isfile(rtag):
                os.remove(rtag)

        else:
            changes = __salt__['pkg.install'](name,
                                              fromrepo=fromrepo,
                                              skip_verify=skip_verify,
                                              pkgs=targeted_pkgs,
                                              **kwargs)

        if changes:
            # Find failed and successful updates
            failed = [x for x in targets if changes[x]['new'] != targets[x]]
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
                msg = 'The following packages were already up-to-date: ' \
                      '{0}.'.format(', '.join(sorted(up_to_date)))
                comments.append(msg)

            return {'name': name,
                    'changes': changes,
                    'result': False if failed else True,
                    'comment': ' '.join(comments)}
        else:
            if len(targets) > 1:
                comment = 'All targeted packages failed to update: ' \
                          '({0}).'.format(', '.join(sorted(targets.keys())))
            else:
                comment = 'Package {0} failed to ' \
                          'update.'.format(targets.keys()[0])
            if up_to_date:
                comment += ' The following packages were already ' \
                           'up-to-date: ' \
                           '{0}'.format(', '.join(sorted(up_to_date)))
            return {'name': name,
                    'changes': changes,
                    'result': False,
                    'comment': comment}
    else:
        if len(desired_pkgs) > 1:
            comment = 'All packages are up-to-date ' \
                      '({0}).'.format(', '.join(sorted(desired_pkgs)))
        else:
            comment = 'Package {0} is already ' \
                      'up-to-date.'.format(desired_pkgs[0])

        return {'name': name,
                'changes': {},
                'result': True,
                'comment': comment}


def removed(name):
    '''
    Verify that the package is removed, this will remove the package via
    the remove function in the salt pkg module for the platform.

    name
        The name of the package to be removed
    '''
    changes = {}
    if not __salt__['pkg.version'](name):
        return {'name': name,
                'changes': {},
                'result': True,
                'comment': 'Package {0} is not installed'.format(name)}
    else:
        if __opts__['test']:
            return {'name': name,
                    'changes': {},
                    'result': None,
                    'comment': 'Package {0} is set to be installed'.format(
                        name)}
        changes['removed'] = __salt__['pkg.remove'](name)
    if not changes:
        return {'name': name,
                'changes': changes,
                'result': False,
                'comment': 'Package {0} failed to remove'.format(name)}
    return {'name': name,
            'changes': changes,
            'result': True,
            'comment': 'Package {0} removed'.format(name)}


def purged(name):
    '''
    Verify that the package is purged, this will call the purge function in the
    salt pkg module for the platform.

    name
        The name of the package to be purged
    '''
    changes = {}
    if not __salt__['pkg.version'](name):
        return {'name': name,
                'changes': {},
                'result': True,
                'comment': 'Package {0} is not installed'.format(name)}
    else:
        if __opts__['test']:
            return {'name': name,
                    'changes': {},
                    'result': None,
                    'comment': 'Package {0} is set to be purged'.format(name)}
        changes['removed'] = __salt__['pkg.purge'](name)

    if not changes:
        return {'name': name,
                'changes': changes,
                'result': False,
                'comment': 'Package {0} failed to purge'.format(name)}
    return {'name': name,
            'changes': changes,
            'result': True,
            'comment': 'Package {0} purged'.format(name)}


def mod_init(low):
    '''
    Set a flag to tell the install functions to refresh the package database.
    This ensures that the package database is refreshed only once durring
    a state run significaltly improving the speed of package management
    durring a state run.

    It sets a flag for a number of reasons, primarily due to timeline logic.
    When originally setting up the mod_init for pkg a number of corner cases
    arose with different package managers and how they refresh package data.
    '''
    if low['fun'] == 'installed' or low['fun'] == 'latest':
        rtag = __gen_rtag()
        if not os.path.exists(rtag):
            salt.utils.fopen(rtag, 'w+').write('')
        return True
    return False
