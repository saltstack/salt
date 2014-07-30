# -*- coding: utf-8 -*-
'''
Manage RabbitMQ Clusters
========================

Example:

.. code-block:: yaml

    rabbit@rabbit.example.com:
        rabbitmq_cluster.join:
          - user: rabbit
          - host: rabbit.example.com
'''

# Import python libs
import logging

# Import salt libs
import salt.utils

log = logging.getLogger(__name__)


def __virtual__():
    '''
    Only load if RabbitMQ is installed.
    '''
    return salt.utils.which('rabbitmqctl') is not None


def join(name, host, user='rabbit', runas=None):
    '''
    Ensure the current node joined to a cluster with node user@host

    name
        Irrelevant, not used (recommended: user@host)
    user
        The user of node to join to (default: rabbit)
    host
        The host of node to join to
    runas
        The user to run the rabbitmq command as
    '''

    ret = {'name': name, 'result': True, 'comment': '', 'changes': {}}
    result = {}

    joined = __salt__['rabbitmq.cluster_status']()
    if '{0}@{1}'.format(user, host) in joined:
        ret['comment'] = 'Already in cluster'
        return ret

    if __opts__['test']:
        ret['result'] = None
        ret['comment'] = 'Node is set to join cluster {0}@{1}'.format(
            user, host)
        return ret

    result = __salt__['rabbitmq.join_cluster'](host, user, runas=runas)

    if 'Error' in result:
        ret['result'] = False
        ret['comment'] = result['Error']
    elif 'Join' in result:
        ret['comment'] = result['Join']
        ret['changes'] = {'old': '', 'new': '{0}@{1}'.format(user, host)}

    return ret
