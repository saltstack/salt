'''
Manage RabbitMQ VHosts.
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


def exists(name,
           runas=None,
        ):
    '''
    Ensure the RabbitMQ VHost exists.

    name
        VHost name
    runas
        Name of the user to run the command
    '''
    ret = {'name': name, 'result': True, 'comment': ''}

    vhost_exists = __salt__['rabbitmq.vhost_exists'](name, user=runas)

    for host, vhost in vhost_exists:
        if not vhost:
            result = __salt__['rabbitmq.add_vhost'](name, user=runas)
            if 'Error' in result:
                ret['result'] = False
                ret['comment'] = result['Error']
            elif 'Added' in result:
                ret['comment'] = result['Added']
            break
    else:
        ret['comment'] = 'VHost already exists'
