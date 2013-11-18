# -*- coding: utf-8 -*-
'''
Manage RabbitMQ Policies.

:maintainer:    Benn Eichhorn <benn@getlocalmeasure.com>
:maturity:      new
:platform:      all

.. code-block:: yaml

    rabbit_policy:
        rabbitmq_policy.present:
            - name: HA
            - pattern: '.*'
            - definition: '{"ha-mode": "all"}'
'''

# Import python libs
import logging
from salt import exceptions, utils

log = logging.getLogger(__name__)


def __virtual__():
    '''
    Only load if RabbitMQ is installed.
    '''
    name = 'rabbitmq_policy'
    try:
        utils.check_or_die('rabbitmqctl')
    except exceptions.CommandNotFoundError:
        name = False
    return name


def present(name,
            pattern,
            definition,
            priority=0,
            vhost='/',
            runas=None):
    '''
    Ensure the RabbitMQ policy exists.

    Reference: http://www.rabbitmq.com/ha.html

    name
        Policy name
    pattern
        A regex of queues to apply the policy to
    definition
        A json dict describing the policy
    priority
        Priority (defaults to 0)
    vhost
        Virtual host to apply to (defaults to '/')
    runas
        Name of the user to run the command as
    '''
    ret = {'name': name, 'result': True, 'comment': '', 'changes': {}}
    result = {}

    policies = __salt__['rabbitmq.list_policies'](runas=runas)
    policy = policies.get(vhost, {}).get(name)
    updates = []
    if policy:
        if policy.get('pattern') != pattern:
            updates.append('Pattern')
        if policy.get('definition') != definition:
            updates.append('Definition')
        if policy.get('priority') != priority:
            updates.append('Priority')

    if policy and not updates:
        ret['comment'] = 'Policy {0} {1} is already present'.format(vhost, name)
        return ret

    if __opts__['test']:
        ret['result'] = None
        if not policy:
            ret['comment'] = 'Policy {0} {1} is set to be created'.format(vhost, name)
        elif updates:
            ret['comment'] = 'Policy {0} {1} is set to be updated'.format(vhost, name)
        ret['comment'] = ret['comment'].format(name)
    else:
        changes = {'new': '', 'old': ''}
        if not policy:
            changes['new'] = policy
            log.debug(
                "Policy doesn't exist - Creating")
            result = __salt__['rabbitmq.set_policy'](
                vhost, name, pattern, definition, priority=priority, runas=runas)
        elif updates:
            changes['old'] = policy
            changes['new'] = updates
            log.debug('Policy exists but needs updating')
            result = __salt__['rabbitmq.set_policy'](
                vhost, name, pattern, definition, priority=priority, runas=runas)

        if 'Error' in result:
            ret['result'] = False
            ret['comment'] = result['Error']
        elif 'Set' in result:
            ret['comment'] = result['Set']
            ret['changes'] = changes

    return ret


def absent(name,
           vhost='/',
           runas=None):
    '''
    Ensure the named policy is absent

    Reference: http://www.rabbitmq.com/ha.html

    name
        The name of the policy to remove
    runas
        Name of the user to run the command as
    '''
    ret = {'name': name, 'result': True, 'comment': '', 'changes': {}}

    policy_exists = __salt__['rabbitmq.policy_exists'](
        vhost, name, runas=runas)

    if not policy_exists:
        ret['comment'] = 'Policy {0} {1} is not present'.format(vhost, name)
        return ret

    if __opts__['test']:
        ret['result'] = None
        ret['comment'] = 'Removing policy {0} {1}'.format(vhost, name)
    else:
        result = __salt__['rabbitmq.delete_policy'](vhost, name, runas=runas)
        if 'Error' in result:
            ret['result'] = False
            ret['comment'] = result['Error']
        elif 'Deleted' in result:
            ret['comment'] = 'Deleted'
            ret['changes'] = {'new': '', 'old': name}

    return ret
