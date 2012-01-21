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
import logging
from distutils.version import LooseVersion

logger = logging.getLogger(__name__)

def installed(name, repo='', skip_verify=False):
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
          - pkg
          - installed
          - repo: mycustomrepo
          - skip_verify: True
    '''
    if __salt__['pkg.version'](name):
        return {'name': name,
                'changes': {},
                'result': True,
                'comment': 'Package ' + name + ' is already installed'}
    changes = __salt__['pkg.install'](name,
                                      True,
				      repo=repo,
				      skip_verify=skip_verify)
    if not changes:
        return {'name': name,
                'changes': changes,
                'result': False,
                'comment': 'Package ' + name + ' failed to install'}
    return {'name': name,
            'changes': changes,
            'result': True,
            'comment': 'Package ' + name + ' installed'}


def latest(name, repo='', skip_verify=False):
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
    ret = {'name': name, 'changes': {}, 'result': False, 'comment': ''}

    version = __salt__['pkg.version'](name)
    avail = __salt__['pkg.available_version'](name)

    try:
        has_newer = LooseVersion(avail) > LooseVersion(version)
    except AttributeError:
        # Not yet installed
        if not version:
            has_newer = True
        else:
            logger.debug("Error comparing versions for '%s' (%s > %s)",
                    name, avail, version)
            ret['comment'] = "No version could be retrieved for '{0}'".format(name)
            return ret

    if has_newer:
        ret['changes'] = __salt__['pkg.install'](name,
	                                         True,
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
                'comment': 'Package ' + name + ' is not installed'}
    else:
        changes['removed'] = __salt__['pkg.remove'](name)
    if not changes:
        return {'name': name,
                'changes': changes,
                'result': False,
                'comment': 'Package ' + name + ' failed to remove'}
    return {'name': name,
        'changes': changes,
        'result': True,
        'comment': 'Package ' + name + ' removed'}


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
                'comment': 'Package ' + name + ' is not installed'}
    else:
        changes['removed'] = __salt__['pkg.purge'](name)

    if not changes:
        return {'name': name,
                'changes': changes,
                'result': False,
                'comment': 'Package ' + name + ' failed to purge'}
    return {'name': name,
        'changes': changes,
        'result': True,
        'comment': 'Package ' + name + ' purged'}
