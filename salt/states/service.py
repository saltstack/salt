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

def __virtual__():
    '''
    Ensure that the service state returns the correct name
    '''
    return 'service'


def _enable(name, started):
    '''
    Enable the service
    '''
    ret = {'name': name,
           'changes': {},
           'result': True,
           'comment': ''}

    # Check to see if this minion supports enable
    if not 'service.enable' in __salt__:
        if started is True:
            ret['comment'] = ('Enable is not available on this minion,'
                ' service {0} started').format(name)
            return ret
        elif started is None:
            ret['comment'] = ('Enable is not available on this minion,'
                ' service {0} is in the desired state').format(name)
            return ret
        else:
            ret['comment'] = ('Enable is not available on this minion,'
                ' service {0} is dead').format(name)
            return ret

    # Service can be enabled
    if __salt__['service.enabled'](name):
        # Service is enabled
        if started is True:
            ret['changes'][name] = True
            ret['comment'] = ('Service {0} is already enabled,'
                ' and is running').format(name)
            return ret
        elif started is None:
            ret['comment'] = ('Service {0} is already enabled,'
                ' and is in the desired state').format(name)
            return ret
        else:
            ret['comment'] = ('Service {0} is already enabled,'
                ' and is dead').format(name)
            return ret

    # Service needs to be enabled
    if __salt__['service.enable'](name):
        # Service has been enabled
        if started is True:
            ret['changes'][name] = True
            ret['comment'] = ('Service {0} has been enabled,'
                ' and is running').format(name)
            return ret
        elif started is None:
            ret['changes'][name] = True
            ret['comment'] = ('Service {0} has been enabled,'
                ' and is in the desired state').format(name)
            return ret
        else:
            ret['changes'][name] = True
            ret['comment'] = ('Service {0} has been enabled,'
                ' and is dead').format(name)
            return ret

    # Service failed to be enabled
    if started is True:
        ret['changes'][name] = True
        ret['result'] = False
        ret['comment'] = ('Failed when setting service {0} to start at boot,'
            ' but the service is running').format(name)
        return ret
    elif started is None:
        ret['result'] = False
        ret['comment'] = ('Failed when setting service {0} to start at boot,'
            ' but the service was already running').format(name)
        return ret
    else:
        ret['result'] = False
        ret['comment'] = ('Failed when setting service {0} to start at boot,'
            ' and the service is dead').format(name)
        return ret
    
def _disable(name, started):
    '''
    Disable the service
    '''
    ret = {'name': name,
           'changes': {},
           'result': True,
           'comment': ''}

    # is enable/disable available?
    if not 'service.disable' in __salt__:
        if started is True:
            ret['comment'] = ('Disable is not available on this minion,'
                ' service {0} started').format(name)
            return ret
        elif started is None:
            ret['comment'] = ('Disable is not available on this minion,'
                ' service {0} is in the desired state').format(name)
            return ret
        else:
            ret['comment'] = ('Disable is not available on this minion,'
                ' service {0} is dead').format(name)
            return ret

    # Service can be disabled
    if __salt__['service.disabled'](name):
        # Service is disabled
        if started is True:
            ret['changes'][name] = True
            ret['comment'] = ('Service {0} is already disabled,'
                ' and is running').format(name)
            return ret
        elif started is None:
            ret['comment'] = ('Service {0} is already disabled,'
                ' and is in the desired state').format(name)
            return ret
        else:
            ret['comment'] = ('Service {0} is already disabled,'
                ' and is dead').format(name)
            return ret

    # Service needs to be disabled
    if __salt__['service.disable'](name):
        # Service has been disabled
        if started is True:
            ret['changes'][name] = True
            ret['comment'] = ('Service {0} has been disabled,'
                ' and is running').format(name)
            return ret
        elif started is None:
            ret['changes'][name] = True
            ret['comment'] = ('Service {0} has been disabled,'
                ' and is in the desired state').format(name)
            return ret
        else:
            ret['changes'][name] = True
            ret['comment'] = ('Service {0} has been disabled,'
                ' and is dead').format(name)
            return ret

    # Service failed to be disabled
    if started is True:
        ret['result'] = False
        ret['comment'] = ('Failed when setting service {0} to not start'
            ' at boot, and is running').format(name)
        return ret
    elif started is None:
        ret['result'] = False
        ret['comment'] = ('Failed when setting service {0} to not start'
            ' at boot, but the service was already running').format(name)
        return ret
    else:
        ret['changes'][name] = True
        ret['result'] = False
        ret['comment'] = ('Failed when setting service {0} to not start'
            ' at boot, and the service is dead').format(name)
        return ret


def running(name, enable=None, sig=None):
    '''
    Verify that the service is running

    name
        The name of the init or rc script used to manage the service

    enable
        Set the service to be enabled at boot time, True sets the service to
        be enabled, False sets the named service to be disabled. The default
        is None, which does not enable or disable anything.

    sig
        The string to search for when looking for the service process with ps
    '''
    ret = {'name': name,
           'changes': {},
           'result': True,
           'comment': ''}
    if __salt__['service.status'](name, sig):
        ret['comment'] = 'The service {0} is already running'.format(name)
        if enable is True:
            return _enable(name, None)
        elif enable is False:
            return _disable(name, None)
        else:
            return ret

    changes = {name: __salt__['service.start'](name)}

    if not changes[name]:
        ret['result'] = False
        ret['comment'] = 'Service {0} failed to start'.format(name)
        if enable is True:
            return _enable(name, False)
        elif enable is False:
            return _disable(name, False)
        else:
            return ret

    if enable is True:
        return _enable(name, True)
    elif enable is False:
        return _disable(name, True)
    else:
        return ret


def dead(name, enable=None, sig=None):
    '''
    Ensure that the named service is dead

    name
        The name of the init or rc script used to manage the service

    enable
        Set the service to be enabled at boot time, True sets the service to
        be enabled, False sets the named service to be disabled. The default
        is None, which does not enable or disable anything.

    sig
        The string to search for when looking for the service process with ps
    '''
    ret = {'name': name,
           'changes': {},
           'result': True,
           'comment': ''}
    if not __salt__['service.status'](name, sig):
        ret['comment'] = 'The service {0} is already dead'.format(name)
        if enable is True:
            return _enable(name, None)
        elif enable is False:
            return _disable(name, None)
        else:
            return ret

    changes = {name: __salt__['service.stop'](name)}

    if not changes[name]:
        ret['result'] = False
        ret['comment'] = 'Service {0} failed to die'.format(name)
        if enable is True:
            return _enable(name, True)
        elif enable is False:
            return _disable(name, True)
        else:
            return ret

    if enable is True:
        return _enable(name, False)
    elif enable is False:
        return _disable(name, False)
    else:
        return ret


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
