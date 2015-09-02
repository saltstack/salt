# -*- coding: utf-8 -*-
'''
Manage RabbitMQ Exchanges
=============================

Example:

.. code-block:: yaml

    someexchange:
        rabbitmq_exchange.present:
            - name: some_exchange
            - vhost: /
            - typename: fanout
            - durable: True
            - auto_delete: False
            - internal: False
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


def present(name, vhost, typename, durable, auto_delete, internal):
    '''
    Ensure the RabbitMQ Exchange exists.

    name
        Exchange name

    typename
        Direct, Fanout, Topic, Headers

    vhost
        VHost name

    durable
        Is the exhange durable? Will it survive a broker crash.

    auto_delete
        Is the exchange to be removed when the last queue is removed.

    internal
        Normally always False

    runas
        Name of the user to run the command

        .. deprecated:: 2015.8.0
    '''
    ret = {'name': name, 'comment': '', 'changes': {}}

    vhost_exists = __salt__['rabbitmq.exchange_vhost_exists'](vhost, name)

    if __opts__['test']:
        ret['result'] = None
        if vhost_exists:
            ret['comment'] = 'Exchange {0} already exists in VHost {1}'.format(name, vhost)
        else:
            ret['comment'] = 'Creating Exchange {0} in VHost {1}'.format(name, vhost)

    else:

        if vhost_exists:
            ret['result'] = True
            ret['comment'] = 'Exchange {0} already exists in VHost {1}'.format(name, vhost)
        else:
            result = __salt__['rabbitmq.declare_exchange'](name, vhost, typename, durable, auto_delete, internal)
            if 'Error' in result:
                ret['result'] = False
                ret['comment'] = result['Error']
            elif 'Added' in result:
                ret['result'] = True
                ret['comment'] = result['Declared']
                ret['changes'] = {'old': '',
                                  'new': {
                                      "name": name,
                                      "vhost": vhost,
                                      "typename": typename,
                                      "durable": durable,
                                      "auto_delete": auto_delete,
                                      "internal": internal
                                  }
                }
    return ret


def absent(name):
    #TODO
    pass
