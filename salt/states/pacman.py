'''
State enforcing for pacman packages
'''

import salt.modules.pacman as pacman

__virtual__ = pacman.__virtual__

def install(name):
    '''
    Verify that the package is installed, return the packages changed in the
    operation and a bool if the job was sucessfull
    '''
    if pacman.version(name):
        return {'changes': {},
                'result': True,
                'comment': 'The package is already installed'}
    changes = pacman.install(name)
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
    version = pacman.version(name)
    avail = pacman.available_version(name)
    if avail > version:
        changes = pacman.install(name, True)
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
    if not pacman.version(name):
        return {'changes': {},
                'result': True,
                'comment': 'The package is not installed'}
    else:
        changes = pacman.remove(name)
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
    if not pacman.version(name):
        return {'changes': {},
                'result': True,
                'comment': 'The package is not installed'}
    else:
        changes = pacman.purge(name)
    if not changes:
        return {'changes': changes,
                'result': False,
                'comment': 'The package failed to purge'}
    return {'changes': changes,
            'result': True,
            'commant': 'Package purged'}
