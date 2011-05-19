'''
State enforcing for packages
'''

def running(name, sig=None):
    '''
    Verify that the package is installed, return the packages changed in the
    operation and a bool if the job was sucessfull
    '''
    if __salt__['service.status'](name):
        return {'name': name,
                'changes': {},
                'result': True,
                'comment': 'The service is already running'}
    changes = __salt__['service.start'](name)
    if not changes:
        return {'name': name,
                'changes': changes,
                'result': False,
                'comment': 'Service ' + name + ' failed to start'}
    return {'name': name,
            'changes': changes,
            'result': True,
            'comment': 'Service ' + name + ' installed'}

def dead(name, sig=None):
    '''
    Ensure that the named service is dead
    '''
    if not __salt__['service.status'](name):
        return {'name': name,
                'changes': {},
                'result': True,
                'comment': 'Service ' + name + ' is already dead'}
    changes = __salt__['service.stop'](name)
    if not changes:
        return {'name': name,
                'changes': changes,
                'result': False,
                'comment': 'Service ' + name + ' failed to stop'}
    return {'name': name,
            'changes': changes,
            'result': True,
            'comment': 'Service ' + name + ' killed'}
