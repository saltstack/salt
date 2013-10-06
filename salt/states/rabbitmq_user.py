# -*- coding: utf-8 -*-
'''
Manage RabbitMQ Users.

.. code-block:: yaml

    rabbit_user:
        rabbitmq_user.present:
            - password: password
            - force: True
'''

# Import python libs
import logging

log = logging.getLogger(__name__)


def __virtual__():
    '''
    Only load if RabbitMQ is installed.
    '''
    name = 'rabbitmq_user'
    if not __salt__['cmd.has_exec']('rabbitmqctl'):
        name = False
    return name


def present(name,
           password=None,
           force=False,
           runas=None):
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
    ret = {'name': name, 'result': True, 'comment': '', 'changes': {}}
    result = {}

    user_exists = __salt__['rabbitmq.user_exists'](name, runas=runas)

    if __opts__['test']:
        ret['result'] = None

        if not user_exists:
            ret['comment'] = 'User {0} is set to be created'
        elif force:
            ret['comment'] = 'User {0} is set to be updated'
        else:
            ret['comment'] = 'User {0} is not going to be modified'
        ret['comment'] = ret['comment'].format(name)
    else:
        if not user_exists:
            log.debug(
                "User doesn't exist - Creating")
            result = __salt__['rabbitmq.add_user'](
                name, password, runas=runas)
        elif force:
            log.debug('User exists and force is set - Overriding password')
            if password is not None:
                result = __salt__['rabbitmq.change_password'](
                    name, password, runas=runas)
            else:
                log.debug('Password is not set - Clearing password')
                result = __salt__['rabbitmq.clear_password'](
                    name, runas=runas)
        else:
            log.debug('User exists, and force is not set - Abandoning')
            ret['comment'] = 'User {0} is not going to be modified'.format(name)

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


def absent(name,
           runas=None):
    '''
    Ensure the named user is absent

    name
        The name of the user to remove
    runas
        User to run the command
    '''
    ret = {'name': name, 'result': True, 'comment': '', 'changes': {}}

    user_exists = __salt__['rabbitmq.user_exists'](name, runas=runas)

    if __opts__['test']:
        ret['result'] = None
        if user_exists:
            ret['comment'] = 'Removing user {0}'.format(name)
        else:
            ret['comment'] = 'User {0} is not present'.format(name)
    else:
        if user_exists:
            result = __salt__['rabbitmq.delete_user'](name, runas=runas)
            if 'Error' in result:
                ret['result'] = False
                ret['comment'] = result['Error']
            elif 'Deleted' in result:
                ret['comment'] = 'Deleted'
        else:
            ret['comment'] = 'User {0} is not present'.format(name)

    return ret
