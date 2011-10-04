'''
State enforcing for packages
'''

def running(name, sig=None):
    '''
    Verify that the service is running
    '''
    if __salt__['service.status'](name, sig):
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
    if not __salt__['service.status'](name, sig):
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

def watcher(name, sig=None):
    '''
    The service watcher, called to invoke the watch command. 
    '''
    if __salt__['service.status'](name, sig):
        changes = __salt__['service.restart'](name)
        return {'name': name,
                'changes': changes,
                'result': True,
                'comment': 'Service restarted'}
    return {'name': name,
            'changes': {},
            'result': True,
            'comment': 'Service ' + name + ' installed'}

