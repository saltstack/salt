'''
Service Management
==================
Services are defined as system daemons typically started with system init or
rc scripts, services can be defined as running or dead.

.. code-block:: yaml

    httpd:
      service:
        - running
'''

def running(name, sig=None):
    '''
    Verify that the service is running

    name
        The name of the init or rc script used to manage the service

    sig
        The string to search for when looking for the service process with ps
    '''
    if __salt__['service.status'](name, sig):
        return {'name': name,
                'changes': {},
                'result': True,
                'comment': 'The service is already running'}
    changes = {name: __salt__['service.start'](name)}
    if not changes[name]:
        return {'name': name,
                'changes': {},
                'result': False,
                'comment': 'Service {0} failed to start'.format(name)}
    return {'name': name,
            'changes': changes,
            'result': True,
            'comment': 'Service {0} started'.format(name)}

def dead(name, sig=None):
    '''
    Ensure that the named service is dead
    
    name
        The name of the init or rc script used to manage the service

    sig
        The string to search for when looking for the service process with ps
    '''
    if not __salt__['service.status'](name, sig):
        return {'name': name,
                'changes': {},
                'result': True,
                'comment': 'Service {0} is already dead'.format(name)}
    changes = {name: __salt__['service.stop'](name)}
    if not changes[name]:
        return {'name': name,
                'changes': {},
                'result': False,
                'comment': 'Service {0} failed to stop'.format(name)}
    return {'name': name,
            'changes': changes,
            'result': True,
            'comment': 'Service {0} killed'.format(name)}

def watcher(name, sig=None):
    '''
    The service watcher, called to invoke the watch command. 

    name
        The name of the init or rc script used to manage the service

    sig
        The string to search for when looking for the service process with ps
    '''
    if __salt__['service.status'](name, sig):
        changes = {name: __salt__['service.restart'](name)}
        return {'name': name,
                'changes': changes,
                'result': True,
                'comment': 'Service restarted'}
    return {'name': name,
            'changes': {},
            'result': True,
            'comment': 'Service {0} started'.format(name)}

