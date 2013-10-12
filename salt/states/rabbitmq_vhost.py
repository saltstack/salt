# -*- coding: utf-8 -*-
'''
Manage RabbitMQ Virtual Hosts.

.. code-block:: yaml

    virtual_host:
        rabbitmq_vhost.present:
            - user: rabbit_user
            - conf: .*
            - write: .*
            - read: .*
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
    name = 'rabbitmq_vhost'
    if not __salt__['cmd.has_exec']('rabbitmqctl'):
        name = False
    return name


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
        .. deprecated:: 0.17.0
    owner
        Initial owner permission to set on the VHost, if present
    conf
        Initial conf string to apply to the VHost and user. Defaults to .*
    write
        Initial write permissions to apply to the VHost and user.
        Defaults to .*
    read
        Initial read permissions to apply to the VHost and user.
        Defaults to .*
    runas
        Name of the user to run the command
    '''
    ret = {'name': name, 'result': True, 'comment': '', 'changes': {}}

    salt.utils.warn_until(
        (0, 18),
        'Please start deprecating \'runas\' at this stage. Ping s0undt3ch for '
        'additional information or see #6961.',
        _dont_call_warnings=True
    )
    if user:
        # Warn users about the deprecation
        ret.setdefault('warnings', []).append(
            'The \'user\' argument is being deprecated in favor of \'owner\', '
            'please update your state files.'
        )
    if user is not None and owner is not None:
        # owner wins over user but let warn about the deprecation.
        ret.setdefault('warnings', []).append(
            'Passed both the \'owner\' and \'user\' arguments. Please don\'t. '
            '\'user\' is being ignored in favor of \'owner\'.'
        )
        user = None
    elif user is not None:
        # Support old runas usage
        owner = user
        user = None

    vhost_exists = __salt__['rabbitmq.vhost_exists'](name, runas=runas)

    if __opts__['test']:
        ret['result'] = None
        if vhost_exists:
            ret['comment'] = 'VHost {0} already exists'.format(name)
        else:
            ret['comment'] = 'Creating VHost {0}'.format(name)

        if user is not None:
            ret['comment'] += (
                ' Setting permissions for {0} {1} {2} {3}'.format(
                    owner,
                    conf or '.*',
                    write or '.*',
                    read or '.*'
                )
            )
    elif not vhost_exists:
        result = __salt__['rabbitmq.add_vhost'](name, runas=runas)
        if 'Error' in result:
            ret['result'] = False
            ret['comment'] = result['Error']
        elif 'Added' in result:
            ret['comment'] = result['Added']
    else:
        ret['comment'] = 'VHost {0} already exists'.format(name)

    if owner is not None:
        conf = conf or '.*'
        write = write or '.*'
        read = read or '.*'
        result = __salt__['rabbitmq.set_permissions'](
            name, owner, conf, write, read, runas=runas)

        if 'Error' in result:
            ret['result'] = False
            ret['comment'] = result['Error']
        elif 'Permissions Set':
            ret['comment'] += ' {0}'.format(result['Permissions Set'])

    return ret


def absent(name,
           runas=None):
    '''
    Ensure the RabbitMQ Virtual Host is absent

    name
        Name of the Virtual Host to remove
    runas
        User to run the command
    '''
    ret = {'name': name, 'result': True, 'comment': '', 'changes': {}}

    vhost_exists = __salt__['rabbitmq.vhost_exists'](name, runas=runas)

    if __opts__['test']:
        ret['result'] = None
        if vhost_exists:
            ret['comment'] = 'Removing Virtual Host {0}'.format(name)
        else:
            ret['comment'] = 'Virtual Host {0} is not present'.format(name)
    else:
        if vhost_exists:
            result = __salt__['rabbitmq.delete_vhost'](name, runas=runas)
            if 'Error' in result:
                ret['result'] = False
                ret['comment'] = result['Error']
            elif 'Deleted' in result:
                ret['comment'] = result['Deleted']
    return ret
