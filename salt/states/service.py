# -*- coding: utf-8 -*-
'''
Starting or restarting of services and daemons
==============================================

Services are defined as system daemons typically started with system init or
rc scripts. The service state uses whichever service module that is loaded on
the minion with the virtualname of ``service``. Services can be defined as
running or dead.

If you need to know if your init system is supported, see the list of supported
:mod:`service modules <salt.modules.service.py>` for your desired init system
(systemd, sysvinit, launchctl, etc.).

Note that Salt's service execution module, and therefore this service state,
uses OS grains to ascertain which service module should be loaded and used to
execute service functions. As existing distributions change init systems or
new distributions are created, OS detection can sometimes be incomplete.
If your service states are running into trouble with init system detection,
please see the :ref:`Overriding Virtual Module Providers <module-provider-override>`
section of Salt's module documentation to work around possible errors.

.. note::
    The current status of a service is determined by the return code of the init/rc
    script status command. A status return code of 0 it is considered running.  Any
    other return code is considered dead.

.. code-block:: yaml

    httpd:
      service.running: []

The service can also be set to be started at runtime via the enable option:

.. code-block:: yaml

    openvpn:
      service.running:
        - enable: True

By default if a service is triggered to refresh due to a watch statement the
service is by default restarted. If the desired behavior is to reload the
service, then set the reload value to True:

.. code-block:: yaml

    redis:
      service.running:
        - enable: True
        - reload: True
        - watch:
          - pkg: redis

.. note::

    More details regarding ``watch`` can be found in the
    :doc:`Requisites </ref/states/requisites>` documentation.

'''

# Import Python libs
from __future__ import absolute_import
import time


def __virtual__():
    '''
    Only make these states available if a service provider has been detected or
    assigned for this minion
    '''
    return 'service.start' in __salt__


def _enabled_used_error(ret):
    '''
    Warn of potential typo.
    '''
    ret['result'] = False
    ret['comment'] = (
        'Service {0} uses non-existent option "enabled".  ' +
        'Perhaps "enable" option was intended?'
    ).format(ret['name'])
    return ret


def _enable(name, started, result=True, **kwargs):
    '''
    Enable the service
    '''
    ret = {}

    # is service available?
    if not _available(name, ret):
        return ret

    # Check to see if this minion supports enable
    if 'service.enable' not in __salt__ or 'service.enabled' not in __salt__:
        if started is True:
            ret['comment'] = ('Enable is not available on this minion,'
                              ' service {0} started').format(name)
        elif started is None:
            ret['comment'] = ('Enable is not available on this minion,'
                              ' service {0} is in the desired state'
                              ).format(name)
        else:
            ret['comment'] = ('Enable is not available on this minion,'
                              ' service {0} is dead').format(name)
        return ret

    # Service can be enabled
    before_toggle_enable_status = __salt__['service.enabled'](name, **kwargs)
    if before_toggle_enable_status:
        # Service is enabled
        if started is True:
            ret['comment'] = ('Service {0} is already enabled,'
                              ' and is running').format(name)
        elif started is None:
            # always be sure in this case to reset the changes dict
            ret['changes'] = {}
            ret['comment'] = ('Service {0} is already enabled,'
                              ' and is in the desired state').format(name)
        else:
            ret['comment'] = ('Service {0} is already enabled,'
                              ' and is dead').format(name)
        return ret

    # Service needs to be enabled
    if __opts__['test']:
        ret['result'] = None
        ret['comment'] = 'Service {0} set to be enabled'.format(name)
        return ret

    if __salt__['service.enable'](name, **kwargs):
        after_toggle_enable_status = __salt__['service.enabled'](name,
                                                                 **kwargs)
        # Service has been enabled
        ret['changes'] = {}
        # on upstart, certain services like apparmor will always return
        # False, even if correctly activated
        # do not trigger a change
        if before_toggle_enable_status != after_toggle_enable_status:
            ret['changes'][name] = True
        if started is True:
            ret['comment'] = ('Service {0} has been enabled,'
                              ' and is running').format(name)
        elif started is None:
            ret['comment'] = ('Service {0} has been enabled,'
                              ' and is in the desired state').format(name)
        else:
            ret['comment'] = ('Service {0} has been enabled,'
                              ' and is dead').format(name)
        return ret

    # Service failed to be enabled
    if started is True:
        ret['result'] = False
        ret['comment'] = ('Failed when setting service {0} to start at boot,'
                          ' but the service is running').format(name)
    elif started is None:
        ret['result'] = False
        ret['comment'] = ('Failed when setting service {0} to start at boot,'
                          ' but the service was already running').format(name)
    else:
        ret['result'] = False
        ret['comment'] = ('Failed when setting service {0} to start at boot,'
                          ' and the service is dead').format(name)
    return ret


def _disable(name, started, result=True, **kwargs):
    '''
    Disable the service
    '''
    ret = {}

    # is service available?
    if not _available(name, ret):
        ret['result'] = True
        return ret

    # is enable/disable available?
    if 'service.disable' not in __salt__ or 'service.disabled' not in __salt__:
        if started is True:
            ret['comment'] = ('Disable is not available on this minion,'
                              ' service {0} started').format(name)
        elif started is None:
            ret['comment'] = ('Disable is not available on this minion,'
                              ' service {0} is in the desired state'
                              ).format(name)
        else:
            ret['comment'] = ('Disable is not available on this minion,'
                              ' service {0} is dead').format(name)
        return ret

    before_toggle_disable_status = __salt__['service.disabled'](name)
    # Service can be disabled
    if before_toggle_disable_status:
        # Service is disabled
        if started is True:
            ret['comment'] = ('Service {0} is already disabled,'
                              ' and is running').format(name)
        elif started is None:
            # always be sure in this case to reset the changes dict
            ret['changes'] = {}
            ret['comment'] = ('Service {0} is already disabled,'
                              ' and is in the desired state').format(name)
        else:
            ret['comment'] = ('Service {0} is already disabled,'
                              ' and is dead').format(name)
        return ret

    # Service needs to be disabled
    if __opts__['test']:
        ret['result'] = None
        ret['comment'] = 'Service {0} set to be disabled'.format(name)
        return ret

    if __salt__['service.disable'](name, **kwargs):
        # Service has been disabled
        ret['changes'] = {}
        after_toggle_disable_status = __salt__['service.disabled'](name)
        # Service has been disabled
        ret['changes'] = {}
        # on upstart, certain services like apparmor will always return
        # False, even if correctly activated
        # do not trigger a change
        if before_toggle_disable_status != after_toggle_disable_status:
            ret['changes'][name] = True
        if started is True:
            ret['comment'] = ('Service {0} has been disabled,'
                              ' and is running').format(name)
        elif started is None:
            ret['comment'] = ('Service {0} has been disabled,'
                              ' and is in the desired state').format(name)
        else:
            ret['comment'] = ('Service {0} has been disabled,'
                              ' and is dead').format(name)
        return ret

    # Service failed to be disabled
    ret['result'] = False
    if started is True:
        ret['comment'] = ('Failed when setting service {0} to not start'
                          ' at boot, and is running').format(name)
    elif started is None:
        ret['comment'] = ('Failed when setting service {0} to not start'
                          ' at boot, but the service was already running'
                          ).format(name)
        return ret
    else:
        ret['comment'] = ('Failed when setting service {0} to not start'
                          ' at boot, and the service is dead').format(name)
    return ret


def _available(name, ret):
    '''
    Check if the service is available
    '''
    avail = False
    if 'service.available' in __salt__:
        avail = __salt__['service.available'](name)
    elif 'service.get_all' in __salt__:
        avail = name in __salt__['service.get_all']()
    if not avail:
        ret['result'] = False
        ret['comment'] = 'The named service {0} is not available'.format(name)
    return avail


def running(name, enable=None, sig=None, init_delay=None, **kwargs):
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

    init_delay
        Some services may not be truly available for a short period after their
        startup script indicates to the system that they are. Provide an
        'init_delay' to specify that this state should wait an additional given
        number of seconds after a service has started before returning. Useful
        for requisite states wherein a dependent state might assume a service
        has started but is not yet fully initialized.

    .. note::
        ``watch`` can be used with service.running to restart a service when
         another state changes ( example: a file.managed state that creates the
         service's config file ). More details regarding ``watch`` can be found
         in the :doc:`Requisites </ref/states/requisites>` documentation.
    '''
    ret = {'name': name,
           'changes': {},
           'result': True,
           'comment': ''}

    # Check for common error: using enabled option instead of enable
    if 'enabled' in kwargs:
        return _enabled_used_error(ret)

    # Check if the service is available
    if not _available(name, ret):
        return ret

    # lot of custom init script won't or mis implement the status
    # command, so it is just an indicator but can not be fully trusted
    before_toggle_status = __salt__['service.status'](name, sig)
    before_toggle_enable_status = __salt__['service.enabled'](name)

    # See if the service is already running
    if before_toggle_status:
        ret['comment'] = 'The service {0} is already running'.format(name)
        if enable is True and not before_toggle_enable_status:
            ret.update(_enable(name, None, **kwargs))
        elif enable is False and before_toggle_enable_status:
            ret.update(_disable(name, None, **kwargs))
        return ret

    # Run the tests
    if __opts__['test']:
        ret['result'] = None
        ret['comment'] = 'Service {0} is set to start'.format(name)
        return ret

    func_ret = __salt__['service.start'](name)

    if not func_ret:
        ret['result'] = False
        ret['comment'] = 'Service {0} failed to start'.format(name)
        if enable is True:
            ret.update(_enable(name, False, result=False, **kwargs))
        elif enable is False:
            ret.update(_disable(name, False, result=False, **kwargs))
    else:
        ret['comment'] = 'Started Service {0}'.format(name)
        if enable is True:
            ret.update(_enable(name, True, **kwargs))
        elif enable is False:
            ret.update(_disable(name, True, **kwargs))

    # only force a change state if we have explicitly detected them
    after_toggle_status = __salt__['service.status'](name)
    after_toggle_enable_status = __salt__['service.enabled'](name)
    if (
        (before_toggle_enable_status != after_toggle_enable_status) or
        (before_toggle_status != after_toggle_status)
    ) and not ret.get('changes', {}):
        ret['changes'][name] = func_ret

    if init_delay:
        time.sleep(init_delay)
        ret['comment'] = (
            '{0}\nDelayed return for {1} seconds'
            .format(ret['comment'], init_delay)
        )
    return ret


def dead(name, enable=None, sig=None, **kwargs):
    '''
    Ensure that the named service is dead by stopping the service if it is running

    name
        The name of the init or rc script used to manage the service

    enable
        Set the service to be enabled at boot time, ``True`` sets the service
        to be enabled, ``False`` sets the named service to be disabled. The
        default is ``None``, which does not enable or disable anything.

    sig
        The string to search for when looking for the service process with ps
    '''
    ret = {'name': name,
           'changes': {},
           'result': True,
           'comment': ''}

    # Check for common error: using enabled option instead of enable
    if 'enabled' in kwargs:
        return _enabled_used_error(ret)

    # Check if the service is available
    if not _available(name, ret):
        ret['result'] = True
        return ret

    # lot of custom init script won't or mis implement the status
    # command, so it is just an indicator but can not be fully trusted
    before_toggle_status = __salt__['service.status'](name, sig)
    before_toggle_enable_status = __salt__['service.enabled'](name)
    if not before_toggle_status:
        ret['comment'] = 'The service {0} is already dead'.format(name)
        if enable is True and not before_toggle_enable_status:
            ret.update(_enable(name, None, **kwargs))
        elif enable is False and before_toggle_enable_status:
            ret.update(_disable(name, None, **kwargs))
        return ret

    if __opts__['test']:
        ret['result'] = None
        ret['comment'] = 'Service {0} is set to be killed'.format(name)
        return ret

    # be sure to stop, in case we mis detected in the check
    func_ret = __salt__['service.stop'](name)
    if not func_ret:
        ret['result'] = False
        ret['comment'] = 'Service {0} failed to die'.format(name)
        if enable is True:
            ret.update(_enable(name, True, result=False, **kwargs))
        elif enable is False:
            ret.update(_disable(name, True, result=False, **kwargs))
    else:
        ret['comment'] = 'Service {0} was killed'.format(name)
        if enable is True:
            ret.update(_enable(name, False, **kwargs))
        elif enable is False:
            ret.update(_disable(name, False, **kwargs))
    # only force a change state if we have explicitly detected them
    after_toggle_status = __salt__['service.status'](name)
    after_toggle_enable_status = __salt__['service.enabled'](name)
    if (
        (before_toggle_enable_status != after_toggle_enable_status) or
        (before_toggle_status != after_toggle_status)
    ) and not ret.get('changes', {}):
        ret['changes'][name] = func_ret
    return ret


def enabled(name, **kwargs):
    '''
    Verify that the service is enabled on boot, only use this state if you
    don't want to manage the running process, remember that if you want to
    enable a running service to use the enable: True option for the running
    or dead function.

    name
        The name of the init or rc script used to manage the service
    '''
    ret = {'name': name,
           'changes': {},
           'result': True,
           'comment': ''}

    ret.update(_enable(name, None, **kwargs))
    return ret


def disabled(name, **kwargs):
    '''
    Verify that the service is disabled on boot, only use this state if you
    don't want to manage the running process, remember that if you want to
    disable a service to use the enable: False option for the running or dead
    function.

    name
        The name of the init or rc script used to manage the service
    '''
    ret = {'name': name,
           'changes': {},
           'result': True,
           'comment': ''}

    ret.update(_disable(name, None, **kwargs))
    return ret


def mod_watch(name,
              sfun=None,
              sig=None,
              reload=False,
              full_restart=False,
              init_delay=None,
              force=False,
              **kwargs):
    '''
    The service watcher, called to invoke the watch command.

    name
        The name of the init or rc script used to manage the service

    sfun
        The original function which triggered the mod_watch call
        (`service.running`, for example).

    sig
        The string to search for when looking for the service process with ps
    '''
    ret = {'name': name,
           'changes': {},
           'result': True,
           'comment': ''}
    past_participle = None

    if sfun == 'dead':
        verb = 'stop'
        past_participle = verb + 'ped'
        if __salt__['service.status'](name, sig):
            func = __salt__['service.stop']
        else:
            ret['result'] = True
            ret['comment'] = 'Service is already {0}'.format(past_participle)
            return ret
    elif sfun == 'running':
        if __salt__['service.status'](name, sig):
            if 'service.reload' in __salt__ and reload:
                if 'service.force_reload' in __salt__ and force:
                    func = __salt__['service.force_reload']
                    verb = 'forcefully reload'
                else:
                    func = __salt__['service.reload']
                    verb = 'reload'
            elif 'service.full_restart' in __salt__ and full_restart:
                func = __salt__['service.full_restart']
                verb = 'fully restart'
            else:
                func = __salt__['service.restart']
                verb = 'restart'
        else:
            if 'service.stop' in __salt__:
                __salt__['service.stop'](name)
            func = __salt__['service.start']
            verb = 'start'
        if not past_participle:
            past_participle = verb + 'ed'
    else:
        ret['comment'] = 'Unable to trigger watch for service.{0}'.format(sfun)
        ret['result'] = False
        return ret

    if __opts__['test']:
        ret['result'] = None
        ret['comment'] = 'Service is set to be {0}'.format(past_participle)
        return ret

    result = func(name)
    if init_delay:
        time.sleep(init_delay)

    ret['changes'] = {name: result}
    ret['result'] = result
    ret['comment'] = 'Service {0}'.format(past_participle) if result else \
                     'Failed to {0} the service'.format(verb)
    return ret
