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
          password=None,
          force=False,
          runas=None,
        ):
    '''
    Ensure the RabbitMQ user exists.

    name
        User name
    password
        User's password, if one needs to be set
    force
        If user exists, forcibly change the password
    runas
        Name of the user to run the command
    '''
    ret = {'name': name, 'result': True, 'comment': ''}

    user_list = __salt__['rabbitmq.list_users'](user=runas)

    user_exists = False
    for host, users in user_list.iteritems():
        if name in users:
            user_exists = True
            break

    if not user_exists:
        result = __salt__['rabbitmq.add_user'](name, password, user=runas)
    elif force:
        if password is not None:
            result = __salt__['rabbitmq.change_password'](
                name, password, user=runas)
        else:
            result = __salt__['rabbitmq.clear_password'](name, user=runas)
    else:
        result = {'Error': 'User {0} exists and force is not set'.format(name)}

    if 'Error' in result:
        ret['result'] = False
        ret['comment'] = result['Error']
    elif 'Added' in result:
        ret['comment'] = result['Added']
    elif 'Password Changed' in result:
        ret['comment'] = result['Password Changed']
    elif 'Password Cleared' in result:
        ret['comment'] = result['Password Cleared']

    return ret
