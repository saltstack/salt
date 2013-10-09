# -*- coding: utf-8 -*-
'''
Manage RabbitMQ Clusters

.. code-block:: yaml

    rabbit@rabbit.example.com:
        rabbitmq_cluster.join:
          - user: rabbit
          - host: rabbit.example.com
'''

# Import python libs
import logging

log = logging.getLogger(__name__)


def __virtual__():
    '''
    Only load if RabbitMQ is installed.
    '''
    name = 'rabbitmq_cluster'
    if not __salt__['cmd.has_exec']('rabbitmqctl'):
        name = False
    return name


def join(name, host, user='rabbit', runas=None):
    '''
    Ensure the RabbitMQ plugin is enabled.

    name
        The name of the plugin
    runas
        The user to run the rabbitmq-plugin command as
    '''

    ret = {'name': name, 'result': True, 'comment': '', 'changes': {}}
    result = {}

    if __opts__['test']:
        ret['result'] = None
        ret['comment'] = 'Host is set to join cluster {0}@{1}'.format(
            user, host)
    else:
        joined = __salt__['rabbitmq.cluster_status']()
        if '{0}@{1}'.format(user, host) in joined:
            ret['comment'] = 'Already joined cluster'
            return ret

        result = __salt__['rabbitmq.join_cluster'](host, user, runas=runas)

        if 'Error' in result:
            ret['result'] = False
            ret['comment'] = result['Error']
        elif 'Join' in result:
            ret['comment'] = result['Join']

    return ret
