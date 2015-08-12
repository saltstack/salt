# -*- coding: utf-8 -*-
'''
Manage RabbitMQ Bindings
=============================

Example:

.. code-block:: yaml

    somebinding:
        rabbitmq_binding.present:
            - source: "goo"
            - vhost: /
            - destination: "blah"
            - destination_type: "queue"
            - routing_key: ""

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


def present(source, vhost, destination, destination_type, routing_key):
    '''
    Ensure the RabbitMQ Binding exists.

    source
        Binding name

    destination

    destination_type

    vhost
        VHost name

    routing_key

    runas
        Name of the user to run the command

        .. deprecated:: 2015.8.0
    '''
    ret = {'name': source, 'result': True, 'comment': '', 'changes': {}}

    vhost_exists = __salt__['rabbitmq.binding_vhost_exists'](vhost,source, destination, destination_type, routing_key )

    if __opts__['test']:
        ret['result'] = None
        if vhost_exists:
            ret['comment'] = 'Binding {0} already exists in VHost {1}'.format(name, vhost)
        else:
            ret['comment'] = 'Creating Binding {0} in VHost {0}'.format(name, vhost)

    else:
        if vhost_exists:
            ret['comment'] = 'Binding {0} already exists in VHost {1}'.format(name, vhost)
        else:
            result = __salt__['rabbitmq.declare_binding'](source, vhost, destination, destination_type, routing_key)
            if 'Error' in result:
                ret['result'] = False
                ret['comment'] = result['Error']
            elif 'Added' in result:
                ret['comment'] = result['Declared']
                ret['changes'] = {'old': '', 'new': source}
    return ret

def absent(name):
    #TODO
    pass
