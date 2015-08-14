# -*- coding: utf-8 -*-
'''
Manage RabbitMQ Queues
=============================

Example:

.. code-block:: yaml

    somequeue:
        rabbitmq_queue.present:
            - vhost: somehost
            - durable: True
            - auto_delete: False
'''
from __future__ import absolute_import

# Import python libs
import logging

# Import salt libs
import salt.utils

log = logging.getLogger(__name__)


def __virtual__():
    '''
    Only load if RabbitMQ rabbitmqcadmin is installed.
    '''
    return salt.utils.which('rabbitmqadmin') is not None


def present(name, vhost, durable, auto_delete):
    '''
    Ensure the RabbitMQ Queue exists.

    name
        Queue name

    vhost
        VHost name

    durable
        is durable

    runas
        Name of the user to run the command

        .. deprecated:: 2015.8.0
    '''
    ret = {'name': name, 'result': True, 'comment': '', 'changes': {}}

    vhost_exists = __salt__['rabbitmq.queue_vhost_exists'](vhost, name)

    if __opts__['test']:
        ret['result'] = None
        if vhost_exists:
            ret['comment'] = 'Queue {0} already exists in VHost {1}'.format(name, vhost)
        else:
            ret['comment'] = 'Creating Queue {0} in VHost {1}'.format(name, vhost)

    else:
        if vhost_exists:
            ret['comment'] = 'Queue {0} already exists in VHost {1}'.format(name, vhost)
        else:
            result = __salt__['rabbitmq.declare_queue'](name, vhost, durable, auto_delete)
            if 'Error' in result:
                ret['result'] = False
                ret['comment'] = result['Error']
            elif 'Added' in result:
                ret['comment'] = result['Declared']
                ret['changes'] = {'old': '', 'new': name}
    return ret


def absent(name):
    #TODO
    pass
