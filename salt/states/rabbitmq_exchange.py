# -*- coding: utf-8 -*-
'''
Manage RabbitMQ Exchanges
=============================

Example:

.. code-block:: yaml

    someexchange:
        rabbitmq_exchange.present:
            - vhost: somehost
            - durable: true
'''
from __future__ import absolute_import

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


def present(name, vhost, typename, durable, auto_delete, internal):
    '''
    Ensure the RabbitMQ Exchange exists.

    name
        Exchange name

    typename 
        fanout etc

    vhost
        VHost name

    durable boolean
    
    auto_delete boolean

    internal boolean
    
    runas
        Name of the user to run the command

        .. deprecated:: 2015.8.0
    '''
    ret = {'name': name, 'result': True, 'comment': '', 'changes': {}}

    vhost_exists = __salt__['rabbitmq.exchange_vhost_exists'](vhost,name)

    if __opts__['test']:
        ret['result'] = None
        if vhost_exists:
            ret['comment'] = 'Exchange {0} already exists in VHost {1}'.format(name, vhost)
        else:
            ret['comment'] = 'Creating Exchange {0} in VHost {0}'.format(name, vhost)

    else:
        if vhost_exists:
            ret['comment'] = 'Exchange {0} already exists in VHost {1}'.format(name, vhost)
        else:
            result = __salt__['rabbitmq.declare_exchange'](name, vhost, typename, durable, auto_delete, internal)
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
