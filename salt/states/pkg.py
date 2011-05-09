'''
State enforcing for packages
'''

def install(name):
    '''
    Verify that the package is installed, return the packages changed in the
    operation and a bool if the job was sucessfull
    '''
    if __minion__['pkg.version'](name):
        return {'changes': {},
                'result': True,
                'comment': 'The package is already installed'}
    changes = __minion__['pkg.install'](name)
    if not changes:
        return {'changes': changes,
                'result': False,
                'comment': 'The package failed to install'}
    return {'changes': changes,
            'result': True,
            'commant': 'Package installed'}

def latest(name):
    '''
    Verify that the latest package is installed
    '''
    version = __minion__['pkg.version'](name)
    avail = ['pkg.available_version'](name)
    if avail > version:
        changes = __minion__['pkg.install'](name, True)
    if not changes:
        return {'changes': changes,
                'result': False,
                'comment': 'The package failed to install'}
    return {'changes': changes,
            'result': True,
            'commant': 'Package installed'}

def remove(name):
    '''
    Verify that the package is removed
    '''
    if not __minion__['pkg.version'](name):
        return {'changes': {},
                'result': True,
                'comment': 'The package is not installed'}
    else:
        changes = __minion__['pkg.remove'](name)
    if not changes:
        return {'changes': changes,
                'result': False,
                'comment': 'The package failed to remove'}
    return {'changes': changes,
            'result': True,
            'commant': 'Package removed'}

def purge(name):
    '''
    Verify that the package is purged
    '''
    if not __minion__['pkg.version'](name):
        return {'changes': {},
                'result': True,
                'comment': 'The package is not installed'}
    else:
        changes = __minion__['pkg.purge'](name)
    if not changes:
        return {'changes': changes,
                'result': False,
                'comment': 'The package failed to purge'}
    return {'changes': changes,
            'result': True,
            'commant': 'Package purged'}
