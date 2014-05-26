# -*- coding: utf-8 -*-
'''
Manage modjk workers
====================

Send commands to a :strong:`modjk` load balancer via the peer system.

This module can be used with the :doc:`prereq </ref/states/requisites>`
requisite to remove/add the worker from the load balancer before
deploying/restarting service.

Mandatory Settings:

- The minion needs to have permission to publish the :strong:`modjk.*`
  functions (see :doc:`here </ref/peer>` for information on configuring
  peer publishing permissions)

- The modjk load balancer must be configured as stated in the :strong:`modjk`
  execution module :mod:`documentation <salt.modules.modjk>`
'''


def __virtual__():
    '''
    Check if we have peer access ?
    '''
    return True


def _send_command(cmd,
                  worker,
                  lbn,
                  target,
                  profile='default',
                  expr_form='glob'):
    '''
    Send a command to the modjk loadbalancer
    The minion need to be able to publish the commands to the load balancer

    cmd:
        worker_stop - won't get any traffic from the lbn
        worker_activate - activate the worker
        worker_disable - will get traffic only for current sessions
    '''

    ret = {
        'code': False,
        'msg': 'OK',
        'minions': [],
    }

    # Send the command to target
    func = 'modjk.{0}'.format(cmd)
    args = [worker, lbn, profile]
    response = __salt__['publish.publish'](target, func, args, expr_form)

    # Get errors and list of affeced minions
    errors = []
    minions = []
    for minion in response:
        minions.append(minion)
        if not response[minion]:
            errors.append(minion)

    # parse response
    if not response:
        ret['msg'] = 'no servers answered the published command {0}'.format(
            cmd
        )
        return ret
    elif len(errors) > 0:
        ret['msg'] = 'the following minions return False'
        ret['minions'] = errors
        return ret
    else:
        ret['code'] = True
        ret['msg'] = 'the commad was published successfully'
        ret['minions'] = minions
        return ret


def _worker_status(target,
                   worker,
                   activation,
                   profile='default',
                   expr_form='glob'):
    '''
    Check if the worker is in `activation` state in the targeted load balancers

    The function will return the following dictionary:
        result - False if no server returned from the published command
        errors - list of servers that couldn't find the worker
        wrong_state - list of servers that the worker was in the wrong state
                      (not activation)
    '''

    ret = {
        'result': True,
        'errors': [],
        'wrong_state': [],
    }

    args = [worker, profile]
    status = __salt__['publish.publish'](
        target, 'modjk.worker_status', args, expr_form
    )

    # Did we got any respone from someone ?
    if not status:
        ret['result'] = False
        return ret

    # Search for errors & status
    for balancer in status:
        if not status[balancer]:
            ret['errors'].append(balancer)
        elif status[balancer]['activation'] != activation:
            ret['wrong_state'].append(balancer)

    return ret


def _talk2modjk(name, lbn, target, action, profile='default', expr_form='glob'):
    '''
    Wrapper function for the stop/disable/activate functions
    '''

    ret = {'name': name,
           'result': True,
           'changes': {},
           'comment': ''}

    action_map = {
        'worker_stop': 'STP',
        'worker_disable': 'DIS',
        'worker_activate': 'ACT',
    }

    # Check what needs to be done
    status = _worker_status(
        target, name, action_map[action], profile, expr_form
    )
    if not status['result']:
        ret['result'] = False
        ret['comment'] = ('no servers answered the published command '
                          'modjk.worker_status')
        return ret
    if status['errors']:
        ret['result'] = False
        ret['comment'] = ('the following balancers could not find the '
                          'worker {0}: {1}'.format(name, status['errors']))
        return ret
    if not status['wrong_state']:
        ret['comment'] = ('the worker is in the desired activation state on '
                          'all the balancers')
        return ret
    else:
        ret['comment'] = ('the action {0} will be sent to the balancers '
                          '{1}'.format(action, status['wrong_state']))
        ret['changes'] = {action: status['wrong_state']}

    if __opts__['test']:
        ret['result'] = None
        return ret

    # Send the action command to target
    response = _send_command(action, name, lbn, target, profile, expr_form)
    ret['comment'] = response['msg']
    ret['result'] = response['code']
    return ret


def stop(name, lbn, target, profile='default', expr_form='glob'):
    '''
    Stop the named worker from the lbn load balancers at the targeted minions
    The worker won't get any traffic from the lbn

    Example:

    .. code-block:: yaml

        disable-before-deploy:
          modjk_worker.stop:
            - name: {{ grains['id'] }}
            - lbn: application
            - target: 'roles:balancer'
            - expr_form: grain
    '''

    return _talk2modjk(name, lbn, target, 'worker_stop', profile, expr_form)


def activate(name, lbn, target, profile='default', expr_form='glob'):
    '''
    Activate the named worker from the lbn load balancers at the targeted
    minions

    Example:

    .. code-block:: yaml

        disable-before-deploy:
          modjk_worker.activate:
            - name: {{ grains['id'] }}
            - lbn: application
            - target: 'roles:balancer'
            - expr_form: grain
    '''

    return _talk2modjk(name, lbn, target, 'worker_activate', profile, expr_form)


def disable(name, lbn, target, profile='default', expr_form='glob'):
    '''
    Disable the named worker from the lbn load balancers at the targeted
    minions.
    The worker will get traffic only for current sessions and won't get new
    ones.

    Example:

    .. code-block:: yaml

        disable-before-deploy:
          modjk_worker.disable:
            - name: {{ grains['id'] }}
            - lbn: application
            - target: 'roles:balancer'
            - expr_form: grain
    '''

    return _talk2modjk(name, lbn, target, 'worker_disable', profile, expr_form)
