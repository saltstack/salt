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

# Import python ilbs
import logging
import os
from distutils.version import LooseVersion

# Import salt libs
import salt.utils

logger = logging.getLogger(__name__)


def __gen_rtag():
    '''
    Return the location of the refresh tag
    '''
    return os.path.join(__opts__['cachedir'], 'pkg_refresh')


def installed(
        name,
        version=None,
        refresh=False,
        repo='',
        skip_verify=False,
        pkgs=None,
        sources=None,
        **kwargs):
    '''
    Verify that the package is installed, and that it is the correct version.

    name
        The name of the package to be installed. This parameter is ignored if
        either "pkgs" or "sources" is used. Additionally, please note that this
        option can only be used to install packages from a software repository.
        To install a package file manually, use the "sources" option detailed
        below.
    repo
        Specify a non-default repository to install from
    skip_verify : False
        Skip the GPG verification check for the package to be installed
    version : None
        Install a specific version of a package. This option is ignored if
        either "pkgs" or "sources" is used.

    Usage::

        httpd:
          pkg.installed:
            - repo: mycustomrepo
            - skip_verify: True
            - version: 2.0.6~ubuntu3


    Multiple Package Installation Options: (not supported in Windows, FreeBSD)

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
                    'comment': 'Invalidly formatted "{0}" parameter. See ' \
                               'minion log.'.format('pkgs' if pkgs
                                                    else 'sources')}

        targets = [x for x in desired_pkgs if x not in old_pkgs]

        if not targets:
            # All specified packages are installed
            return {'name': name,
                    'changes': {},
                    'result': True,
                    'comment': 'All specified packages are already ' \
                               'installed'.format(name)}
        else:
            # Remove any targets that are already installed to avoid upgrading
            if pkgs:
                pkgs = targets
            elif sources:
                sources = [x for x in sources if x.keys()[0] in targets]

    else:
        targets = [name]

        cver = old_pkgs.get(name,'')
        if cver == version:
            # The package is installed and is the correct version
            return {'name': name,
                    'changes': {},
                    'result': True,
                    'comment': ('Package {0} is already installed and is the '
                                'correct version').format(name)}

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
                                          repo=repo,
                                          skip_verify=skip_verify,
                                          pkgs=pkgs,
                                          sources=sources,
                                          **kwargs)
        if os.path.isfile(rtag):
            os.remove(rtag)
    else:
        changes = __salt__['pkg.install'](name,
                                          version=version,
                                          repo=repo,
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
                      '{0}'.format(', '.join(failed))
        else:
            comment = 'Package {0} failed to install'.format(targets[0])

        return {'name': name,
                'changes': changes,
                'result': False,
                'comment': comment}

    # Success!
    if len(targets) > 1:
        comment = 'The following pacakages were installed: ' \
                  '{0}'.format(', '.join(targets))
    else:
        comment = 'Package {0} installed'.format(targets[0])

    return {'name': name,
            'changes': changes,
            'result': True,
            'comment': comment}


def latest(name, refresh=False, repo='', skip_verify=False, **kwargs):
    '''
    Verify that the named package is installed and the latest available
    package. If the package can be updated this state function will update
    the package. Generally it is better for the ``installed`` function to be
    used, as ``latest`` will update the package whenever a new package is
    available.

    name
        The name of the package to maintain at the latest available version
    repo : (default)
        Specify a non-default repository to install from
    skip_verify : False
        Skip the GPG verification check for the package to be installed
    '''
    rtag = __gen_rtag()
    ret = {'name': name, 'changes': {}, 'result': False, 'comment': ''}

    version = __salt__['pkg.version'](name)
    avail = __salt__['pkg.available_version'](name)

    if not version:
        # Net yet installed
        has_newer = True
    elif not avail:
        # Already at latest
        has_newer = False
    else:
        try:
            has_newer = LooseVersion(avail) > LooseVersion(version)
        except AttributeError:
            logger.debug('Error comparing versions'
                         ' for "{0}" ({1} > {2})'.format(name,
                                                         avail,
                                                         version)
                         )
            ret['comment'] = 'No version could be retrieved' \
                             ' for "{0}"'.format(name)
            return ret

    if has_newer:
        if __opts__['test']:
            ret['result'] = None
            ret['comment'] = 'Package {0} is set to be upgraded'.format(name)
            return ret
        if refresh or os.path.isfile(rtag):
            ret['changes'] = __salt__['pkg.install'](name,
                                                     refresh=True,
                                                     repo=repo,
                                                     skip_verify=skip_verify,
                                                     **kwargs)
            if os.path.isfile(rtag):
                os.remove(rtag)

        else:
            ret['changes'] = __salt__['pkg.install'](name,
                                                     repo=repo,
                                                     skip_verify=skip_verify,
                                                     **kwargs)

        if ret['changes']:
            ret['comment'] = 'Package {0} upgraded to latest'.format(name)
            ret['result'] = True
        else:
            ret['comment'] = 'Package {0} failed to install'.format(name)
            ret['result'] = False
            return ret
    else:
        ret['comment'] = 'Package {0} already at latest'.format(name)
        ret['result'] = True

    return ret


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
