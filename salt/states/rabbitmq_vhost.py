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
import logging

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
            conf=None,
            write=None,
            read=None,
            runas=None,
        ):
    '''
    Ensure the RabbitMQ VHost exists.

    name
        VHost name
    user
        Initial user permission to set on the VHost, if present
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
                    user,
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

    if user is not None:
        conf = conf or '.*'
        write = write or '.*'
        read = read or '.*'
        result = __salt__['rabbitmq.set_permissions'](
            name, user, conf, write, read, runas=runas)

        if 'Error' in result:
            ret['result'] = False
            ret['comment'] = result['Error']
        elif 'Permissions Set':
            ret['comment'] += ' {0}'.format(result['Permissions Set'])

    return ret


def absent(name,
           runas=None,
        ):
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
