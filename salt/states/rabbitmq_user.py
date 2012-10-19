'''
Manage RabbitMQ Users.
'''
import logging


def __virtual__():
    '''
    Only load if RabbitMQ is installed.
    '''
    name = 'rabbitmq_user'
    if not __salt__['cmd.has_exec']('rabbitmqctl'):
        name = False
    return name


def exists(name,
          password,
          runas=None,
        ):
    '''
    Ensure the RabbitMQ user exists.

    name
        User name
    password
        User's password
    runas
        Name of the user to run the command
    '''
    ret = {'name': name, 'result': True, 'comment': ''}

    result = __salt__['rabbitmq.add_user'](name, password, user=runas)
