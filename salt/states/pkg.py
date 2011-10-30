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

def installed(name):
    '''
    Verify that the package is installed, and only that it is installed. This
    state will not upgrade an existing package and only verify that it is
    installed

    name
        The name of the package to install
    '''
    if __salt__['pkg.version'](name):
        return {'name': name,
                'changes': {},
                'result': True,
                'comment': 'Package ' + name + ' is already installed'}
    changes = __salt__['pkg.install'](name, True)
    if not changes:
        return {'name': name,
                'changes': changes,
                'result': False,
                'comment': 'Package ' + name + ' failed to install'}
    return {'name': name,
            'changes': changes,
            'result': True,
            'comment': 'Package ' + name + ' installed'}

def latest(name):
    '''
    Verify that the named package is installed and the latest available
    package. If the package can be updated this state function will update
    the package. Generally it is better for the installed function to be
    used, as ``latest`` will update the package the package whenever a new
    package is available

    name
        The name of the package to maintain at the latest available version
    '''
    changes = {}
    version = __salt__['pkg.version'](name)
    avail = __salt__['pkg.available_version'](name)
    if avail > version:
        changes = __salt__['pkg.install'](name, True)
        if not changes:
            return {'name': name,
                    'changes': changes,
                    'result': False,
                    'comment': 'Package ' + name + ' failed to install'}
    return {'name': name,
            'changes': changes,
            'result': True,
            'comment': 'Package ' + name + ' installed'}

def removed(name):
    '''
    Verify that the package is removed, this will remove the package via
    the remove function in the salt pkg module for the platform.

    name
        The name of the package to be removed
    '''
    if not __salt__['pkg.version'](name):
        return {'name': name,
                'changes': {},
                'result': True,
                'comment': 'Package ' + name + ' is not installed'}
    else:
        changes = __salt__['pkg.remove'](name)
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
    if not __salt__['pkg.version'](name):
        return {'name': name,
                'changes': {},
                'result': True,
                'comment': 'Package ' + name + ' is not installed'}
    else:
        changes = __salt__['pkg.purge'](name)
    if not changes:
        return {'name': name,
                'changes': changes,
                'result': False,
                'comment': 'Package ' + name + ' failed to purge'}
        return {'name': name,
            'changes': changes,
            'result': True,
            'comment': 'Package ' + name + ' purged'}
