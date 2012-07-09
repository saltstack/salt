'''
Starting or restarting of services and daemons.
===============================================

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


def _get_stat(name, sig):
    '''
    Return the status of a service based on signature and status, if the
    signature is used then the status option will be ignored
    '''
    stat = False
    if sig:
        if sig == 'detect':
            cmd = "{0[ps]} | grep {1} | grep -v grep | awk '{{print $2}}'"
            cmd = cmd.format(__grains__, name)
        else:
            cmd = "{0[ps]} | grep {1} | grep -v grep | awk '{{print $2}}'"
            cmd = cmd.format(__grains__, sig)
        stat = bool(__salt__['cmd.run'](cmd))
    else:
        stat = __salt__['service.status'](name)
    return stat


def _enable(name, started):
    '''
    Enable the service
    '''
    ret = {'name': name,
           'changes': {},
           'result': True,
           'comment': ''}

    # Check to see if this minion supports enable
    if not 'service.enable' in __salt__ or not 'service.enabled' in __salt__:
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
    if __opts__['test']:
        ret['result'] = None
        ret['comment'] = 'Service {0} set to be enabled'.format(name)
        return ret

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
    if not 'service.disable' in __salt__ or not 'service.disabled' in __salt__:
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
    if __opts__['test']:
        ret['result'] = None
        ret['comment'] = 'Service {0} set to be disabled'.format(name)
        return ret

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
    if _get_stat(name, sig):
        ret['comment'] = 'The service {0} is already running'.format(name)
        if enable is True:
            return _enable(name, None)
        elif enable is False:
            return _disable(name, None)
        else:
            return ret

    if __opts__['test']:
        ret['result'] = None
        ret['comment'] = 'Service {0} is set to start'.format(name)
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
    if not _get_stat(name, sig):
        ret['comment'] = 'The service {0} is already dead'.format(name)
        if enable is True:
            return _enable(name, None)
        elif enable is False:
            return _disable(name, None)
        else:
            return ret
    if __opts__['test']:
        ret['result'] = None
        ret['comment'] = 'Service {0} is set to be killed'.format(name)
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


def enabled(name):
    '''
    Verify that the service is enabled on boot, only use this state if you
    don't want to manage the running process, remember that if you want to
    enable a running service to use the enable: True option for the running
    or dead function.

    name
        The name of the init or rc script used to manage the service
    '''
    return _enable(name, None)


def disabled(name):
    '''
    Verify that the service is disabled on boot, only use this state if you
    don't want to manage the running process, remember that if you want to
    disable a service to use the enable: False option for the running or dead
    function.

    name
        The name of the init or rc script used to manage the service
    '''
    return _disable(name, None)


def mod_watch(name, sig=None, reload=False):
    '''
    The service watcher, called to invoke the watch command.

    name
        The name of the init or rc script used to manage the service

    sig
        The string to search for when looking for the service process with ps
    '''
    if __salt__['service.status'](name, sig):
        if 'service.reload' in __salt__ and reload:
            changes = {name: __salt__['service.reload'](name)}
        else:
            changes = {name: __salt__['service.restart'](name)}
        return {'name': name,
                'changes': changes,
                'result': True,
                'comment': 'Service restarted'}

    return {'name': name,
            'changes': {},
            'result': True,
            'comment': 'Service {0} started'.format(name)}
