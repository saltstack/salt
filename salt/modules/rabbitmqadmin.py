# -*- coding: utf-8 -*-
'''
Module to provide RabbitMQAdmin compatibility to Salt.
Todo: .
'''
from __future__ import absolute_import

# Import salt libs
import salt.utils

# Import python libs
import logging
import random
import string
import json
from salt.ext.six.moves import range

log = logging.getLogger(__name__)

def translate_boolean(v):
    if v :
        return 'true'
    else:
        return 'false'

def __virtual__():
    '''
    Only load if RabbitMQ rabbitmqcadmin is installed.
    '''
    return salt.utils.which('rabbitmqadmin') is not None


def declare_queue(name, vhost, durable, auto_delete, runas=None):
    '''
    Adds a queue via rabbitmqadmin declare queue.

    ./rabbitmqadmin declare queue --vhost=Some_Virtual_Host name=some_outgoing_queue durable=True auto_delete=False

    CLI Example:

    .. code-block:: bash

        salt '*' rabbitmq declare_queue '<queue_name>' '<vhost_name>' True


    Setup:
    rabbitmqadmin is from http://localhost:15672/cli/rabbitmqadmin it needs to be in the path.
    see rabbitmq-formula/rabbitmq/rabbit-management.sls

    '''

    durable = translate_boolean(durable)
    auto_delete = translate_boolean(auto_delete)

    if runas is None:
        runas = salt.utils.get_user()
    res = __salt__['cmd.run']('rabbitmqadmin declare queue --vhost={0} name={1} durable={2} auto_delete={2}'.format(vhost,name,durable, auto_delete),
                              python_shell=False,
                              runas=runas)
    log.debug(res)
    msg = 'Declared'
    return _format_response(res, msg)


def declare_exchange(name, vhost, typename, durable, auto_delete, internal, runas=None):
    '''
    Adds a exchange via rabbitmqctl declare exchange.

    ./rabbitmqadmin declare exchange --vhost=Some_Virtual_Host name=some_exchange type=fanout durable=True auto_delete=False internal=False

    CLI Example:

    .. code-block:: bash

        salt '*' rabbitmq declare_exchange '<exchange_name>' '<vhost_name>' 'fanout' True False False


    Setup:

    rabbitmqadmin is from http://localhost:15672/cli/rabbitmqadmin
    see rabbitmq-formula/rabbitmq/rabbit-management.sls

    '''

    durable = translate_boolean(durable)
    auto_delete = translate_boolean(auto_delete)
    internal = translate_boolean(internal)


    if runas is None:
        runas = salt.utils.get_user()
    res = __salt__['cmd.run']('rabbitmqadmin declare exchange --vhost={0} name={1} type={2} durable={3} auto_delete={4} internal={5}'.format(vhost, name, typename, durable, auto_delete, internal),
                              python_shell=False,
                              runas=runas)
    log.debug(res)
    msg = 'Declared'
    return _format_response(res, msg)


def declare_binding(source, vhost, destination, destination_type, routing_key, runas=None):
    '''
    Adds a exchange via rabbitmqctl declare binding

    rabbitmqadmin declare binding --vhost=Some_Virtual_Host source=bloa destination=bla destination_type=queue routing_key=""

    CLI Example:

    .. code-block:: bash

        salt '*' rabbitmq declare_exchange 'blah' '<vhost_name>' 'boo' "queue" ""

    Setup:

    rabbitmqadmin is from http://localhost:15672/cli/rabbitmqadmin
    see rabbitmq-formula/rabbitmq/rabbit-management.sls

    '''

    if runas is None:
        runas = salt.utils.get_user()
    res = __salt__['cmd.run']('rabbitmqadmin declare binding --vhost={0} source={1} destination={2} destination_type={3} routing_key={4}'.format(vhost, source, destination, destination_type, routing_key),
                              python_shell=False,
                              runas=runas)
    log.debug(res)
    msg = 'Declared'
    return _format_response(res, msg)


def declare_exchange(name, vhost, typename, durable, auto_delete, internal, runas=None):
    '''
    Adds a exchange via rabbitmqctl declare exchange.

    ./rabbitmqadmin declare exchange --vhost=Some_Virtual_Host name=some_exchange type=fanout durable=True auto_delete=False internal=False

    CLI Example:

    .. code-block:: bash

        salt '*' rabbitmq declare_exchange '<exchange_name>' '<vhost_name>' 'fanout' True False False


    Setup:

    rabbitmqadmin is from http://localhost:15672/cli/rabbitmqadmin
    see rabbitmq-formula/rabbitmq/rabbit-management.sls

    '''

    durable = translate_boolean(durable)
    auto_delete = translate_boolean(auto_delete)
    internal = translate_boolean(internal)


    if runas is None:
        runas = salt.utils.get_user()
    res = __salt__['cmd.run']('rabbitmqadmin declare exchange --vhost={0} name={1} type={2} durable={3} auto_delete={4} internal={5}'.format(vhost, name, typename, durable, auto_delete, internal),
                              python_shell=False,
                              runas=runas)
    log.debug(res)
    msg = 'Declared'
    return _format_response(res, msg)

def exchange_vhost_exists(name, vhost, runas=None, *kwargs):
    '''
    Returns whether the exchange exists on the specified virtual host.

    CLI Example:

    .. code-block:: bash

        salt '*' rabbitmq.exchange_vhost_exists queuename vhostname
    '''
    if runas is None:
        runas = salt.utils.get_user()
    res = __salt__['cmd.run'](
        'rabbitmqadmin list exchanges --format pretty_json',
        python_shell=False,
        runas=runas,
        )

    # example
    #    "auto_delete": false,
    #    "durable": true,
    #    "internal": false,
    #    "name": "amq.topic",
    #    "type": "topic",
    #    "vhost": "guest"

    res = json.loads(res)
    log.debug(res)
    for exchange in res:
        log.debug(exchange)
        if exchange['name'] == name and exchange['vhost'] == vhost :
            return True

    return False

def binding_vhost_exists(source, destination, destination_type, routing_key, vhost, runas=None, *kwargs):
    '''
    Returns whether the bindiing exists on the specified virtual host.

    CLI Example:

    .. code-block:: bash

        salt '*' rabbitmq.exchange_vhost_exists source vhostname destination destination_type
    '''
    if runas is None:
        runas = salt.utils.get_user()
    res = __salt__['cmd.run'](
        'rabbitmqadmin list bindings --format pretty_json',
        python_shell=False,
        runas=runas,
        )

    log.debug(res)
    res = json.loads(res)
    log.debug(res)
    for binding in res:
        log.debug(binding)
        if (
                binding['source'] == source and
                binding['destination'] == destination and
                binding['destination_type'] == destination_type and
                binding['routing_key'] == routing_key
        ):
            return True
    return False
