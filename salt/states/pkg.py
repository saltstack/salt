'''
Package Management
==================
Salt can manage software packages via the pkg state module, packages can be
set up to be installed, latest, removed and purged. Package management
declarations are typically rather simple:

.. code-block:: yaml

    vim:
      pkg:
        - installed
'''
# Import python ilbs
import logging
import os
from distutils.version import LooseVersion

logger = logging.getLogger(__name__)

def installed(name, version=None, refresh=False, repo='', skip_verify=False):
    '''
    Verify that the package is installed, and only that it is installed. This
    state will not upgrade an existing package and only verify that it is
    installed

    name
        The name of the package to install
    repo
        Specify a non-default repository to install from
    skip_verify : False
        Skip the GPG verification check for the package to be installed

    Usage::

        httpd:
          pkg:
            - installed
            - repo: mycustomrepo
            - skip_verify: True
    '''
    rtag = __gen_rtag()
    cver = __salt__['pkg.version'](name)
    if cver == version:
        # The package is installed and is the correct version
        return {'name': name,
                'changes': {},
                'result': True,
                'comment': 'Package {0} is already installed and is the correct version'.format(name)}
    elif cver:
        # The package is installed
        return {'name': name,
                'changes': {},
                'result': True,
                'comment': 'Package {0} is already installed'.format(name)}
    if refresh or os.path.isfile(rtag):
        changes = __salt__['pkg.install'](name,
                          True,
                          version=version,
                          repo=repo,
                          skip_verify=skip_verify)
        if os.path.isfile(rtag):
            os.remove(rtag)
    else:
        changes = __salt__['pkg.install'](name,
                          version=version,
                          repo=repo,
                          skip_verify=skip_verify)
    if not changes:
        return {'name': name,
                'changes': changes,
                'result': False,
                'comment': 'Package {0} failed to install'.format(name)}
    return {'name': name,
            'changes': changes,
            'result': True,
            'comment': 'Package {0} installed'.format(name)}


def latest(name, refresh=False, repo='', skip_verify=False):
    '''
    Verify that the named package is installed and the latest available
    package. If the package can be updated this state function will update
    the package. Generally it is better for the installed function to be
    used, as ``latest`` will update the package the package whenever a new
    package is available

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
            logger.debug("Error comparing versions for '%s' (%s > %s)",
                    name, avail, version)
            ret['comment'] = "No version could be retrieved for '{0}'".format(name)
            return ret

    if has_newer:
        if refresh or os.path.isfile(rtag):
            ret['changes'] = __salt__['pkg.install'](name,
                             True,
                             repo=repo,
                             skip_verify=skip_verify)
            if os.path.isfile(rtag):
                os.remove(rtag)

        else:
            ret['changes'] = __salt__['pkg.install'](name,
                             repo=repo,
                             skip_verify=skip_verify)

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
    Refresh the package database here so that it only needs to happen once
    '''
    if low['fun'] == 'installed' or low['fun'] == 'latest':
        rtag = __gen_rtag()
        if not os.path.exists(rtag):
            open(rtag, 'w+').write('')
        return True
    else:
        return False

def __gen_rtag():
    '''
    Return the location of the refresh tag
    '''
    return os.path.join(__opts__['cachedir'], 'pkg_refresh')
