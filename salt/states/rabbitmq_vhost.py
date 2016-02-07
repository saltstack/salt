# -*- coding: utf-8 -*-
'''
Manage RabbitMQ Virtual Hosts
=============================

Example:

.. code-block:: yaml

    virtual_host:
      rabbitmq_vhost.present:
        - user: rabbit_user
        - conf: .*
        - write: .*
        - read: .*
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


def present(name):
    '''
    Ensure the RabbitMQ VHost exists.

    name
        VHost name

    user
        Initial user permission to set on the VHost, if present

        .. deprecated:: 2015.8.0
    owner
        Initial owner permission to set on the VHost, if present

        .. deprecated:: 2015.8.0
    conf
        Initial conf string to apply to the VHost and user. Defaults to .*

        .. deprecated:: 2015.8.0
    write
        Initial write permissions to apply to the VHost and user.
        Defaults to .*

        .. deprecated:: 2015.8.0
    read
        Initial read permissions to apply to the VHost and user.
        Defaults to .*

        .. deprecated:: 2015.8.0
    runas
        Name of the user to run the command

        .. deprecated:: 2015.8.0
    '''
    ret = {'name': name, 'result': True, 'comment': '', 'changes': {}}

    vhost_exists = __salt__['rabbitmq.vhost_exists'](name)

    if vhost_exists:
        ret['comment'] = 'VHost {0} already exists'.format(name)
        return ret

    if __opts__['test']:
        ret['result'] = None
        ret['comment'] = 'Creating VHost {0}'.format(name)
        ret['changes'] = {'old': '', 'new': name}
        return ret

    result = __salt__['rabbitmq.add_vhost'](name)
    if 'Error' in result:
        ret['result'] = False
        ret['comment'] = result['Error']
    elif 'Added' in result:
        ret['comment'] = result['Added']
        ret['changes'] = {'old': '', 'new': name}

    return ret


def absent(name):
    '''
    Ensure the RabbitMQ Virtual Host is absent

    name
        Name of the Virtual Host to remove
    runas
        User to run the command

        .. deprecated:: 2015.8.0
    '''
    ret = {'name': name, 'result': True, 'comment': '', 'changes': {}}

    vhost_exists = __salt__['rabbitmq.vhost_exists'](name)

    if not vhost_exists:
        ret['comment'] = 'Virtual Host {0} is not present'.format(name)

    elif __opts__['test']:
        ret['result'] = None
        if vhost_exists:
            ret['comment'] = 'Removing Virtual Host {0}'.format(name)

    else:
        if vhost_exists:
            result = __salt__['rabbitmq.delete_vhost'](name)
            if 'Error' in result:
                ret['result'] = False
                ret['comment'] = result['Error']
            elif 'Deleted' in result:
                ret['comment'] = result['Deleted']
                ret['changes'] = {'new': '', 'old': name}
    return ret
