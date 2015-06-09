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


def present(name,
            user=None,
            owner=None,
            conf=None,
            write=None,
            read=None,
            runas=None):
    '''
    Ensure the RabbitMQ VHost exists.

    name
        VHost name
    user
        Initial user permission to set on the VHost, if present

        .. deprecated:: Beryllium
    owner
        Initial owner permission to set on the VHost, if present

        .. deprecated:: Beryllium
    conf
        Initial conf string to apply to the VHost and user. Defaults to .*

        .. deprecated:: Beryllium
    write
        Initial write permissions to apply to the VHost and user.
        Defaults to .*

        .. deprecated:: Beryllium
    read
        Initial read permissions to apply to the VHost and user.
        Defaults to .*

        .. deprecated:: Beryllium
    runas
        Name of the user to run the command

        .. deprecated:: Beryllium
    '''
    ret = {'name': name, 'result': True, 'comment': '', 'changes': {}}

    if runas:
        salt.utils.warn_until(
            'Beryllium',
            'The support for \'runas\' has been deprecated and will be '
            'removed in Salt Beryllium. Ping s0undt3ch for additional '
            'information or see #6961.'
        )

    if any((user, owner, conf, write, read)):
        salt.utils.warn_until(
            'Beryllium',
            'Passed \'owner\', \'user\', \'conf\', \'write\' or \'read\' '
            'arguments. These are being deprecated, and will be removed in '
            'Salt Beryllium. Please update your state files, and set '
            'permissions for user instead. See rabbitmq_user.present.'
        )

    vhost_exists = __salt__['rabbitmq.vhost_exists'](name, runas=runas)

    if __opts__['test']:
        ret['result'] = None
        if vhost_exists:
            ret['comment'] = 'VHost {0} already exists'.format(name)
        else:
            ret['comment'] = 'Creating VHost {0}'.format(name)

    else:
        if vhost_exists:
            ret['comment'] = 'VHost {0} already exists'.format(name)
        else:
            result = __salt__['rabbitmq.add_vhost'](name, runas=runas)
            if 'Error' in result:
                ret['result'] = False
                ret['comment'] = result['Error']
            elif 'Added' in result:
                ret['comment'] = result['Added']
                ret['changes'] = {'old': '', 'new': name}

    return ret


def absent(name,
           runas=None):
    '''
    Ensure the RabbitMQ Virtual Host is absent

    name
        Name of the Virtual Host to remove
    runas
        User to run the command

        .. deprecated:: Beryllium
    '''
    if runas:
        salt.utils.warn_until(
            'Beryllium',
            'The support for \'runas\' has been deprecated and will be '
            'removed in Salt Beryllium.'
        )
    ret = {'name': name, 'result': True, 'comment': '', 'changes': {}}

    vhost_exists = __salt__['rabbitmq.vhost_exists'](name, runas=runas)

    if not vhost_exists:
        ret['comment'] = 'Virtual Host {0} is not present'.format(name)

    elif __opts__['test']:
        ret['result'] = None
        if vhost_exists:
            ret['comment'] = 'Removing Virtual Host {0}'.format(name)

    else:
        if vhost_exists:
            result = __salt__['rabbitmq.delete_vhost'](name, runas=runas)
            if 'Error' in result:
                ret['result'] = False
                ret['comment'] = result['Error']
            elif 'Deleted' in result:
                ret['comment'] = result['Deleted']
                ret['changes'] = {'new': '', 'old': name}
    return ret
