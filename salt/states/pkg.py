'''
State enforcing for packages
'''

def installed(name):
    '''
    Verify that the package is installed, return the packages changed in the
    operation and a bool if the job was sucessfull
    '''
    if __salt__['pkg.version'](name):
        return {'changes': {},
                'result': True,
                'comment': 'The package is already installed'}
    changes = __salt__['pkg.install'](name)
    if not changes:
        return {'changes': changes,
                'result': False,
                'comment': 'The package failed to install'}
    return {'name': name,
            'changes': changes,
            'result': True,
            'comment': 'Package installed'}

def latest(name):
    '''
    Verify that the latest package is installed
    '''
    version = __salt__['pkg.version'](name)
    avail = ['pkg.available_version'](name)
    if avail > version:
        changes = __salt__['pkg.install'](name, True)
    if not changes:
        return {'name': name,
                'changes': changes,
                'result': False,
                'comment': 'The package failed to install'}
    return {'name': name,
            'changes': changes,
            'result': True,
            'comment': 'Package installed'}

def removed(name):
    '''
    Verify that the package is removed
    '''
    if not __salt__['pkg.version'](name):
        return {'name': name,
                'changes': {},
                'result': True,
                'comment': 'The package is not installed'}
    else:
        changes = __salt__['pkg.remove'](name)
    if not changes:
        return {'name': name,
                'changes': changes,
                'result': False,
                'comment': 'The package failed to remove'}
        return {'name': name,
            'changes': changes,
            'result': True,
            'comment': 'Package removed'}

def purged(name):
    '''
    Verify that the package is purged
    '''
    if not __salt__['pkg.version'](name):
        return {'name': name,
                'changes': {},
                'result': True,
                'comment': 'The package is not installed'}
    else:
        changes = __salt__['pkg.purge'](name)
    if not changes:
        return {'name': name,
                'changes': changes,
                'result': False,
                'comment': 'The package failed to purge'}
        return {'name': name,
            'changes': changes,
            'result': True,
            'comment': 'Package purged'}
