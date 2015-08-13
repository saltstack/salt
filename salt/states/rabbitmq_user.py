# -*- coding: utf-8 -*-
'''
Manage RabbitMQ Users
=====================

Example:

.. code-block:: yaml

    rabbit_user:
        rabbitmq_user.present:
            - password: password
            - force: True
            - tags:
                - monitoring
                - user
            - perms:
              - '/':
                - '.*'
                - '.*'
                - '.*'
            - runas: rabbitmq
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


def _check_perms_changes(name, newperms, runas=None):
    '''
    Whether Rabbitmq user's permissions need to be changed
    '''
    if not newperms:
        return False

    existing_perms = __salt__['rabbitmq.list_user_permissions'](name, runas=runas)

    perm_need_change = False
    for vhost_perms in newperms:
        for vhost, perms in vhost_perms.iteritems():
            if vhost in existing_perms:
                if perms != existing_perms[vhost]:
                    perm_need_change = True
            else:
                perm_need_change = True

    return perm_need_change


def _check_tags_changes(name, newtags, runas=None):
    '''
    Whether Rabbitmq user's tags need to be changed
    '''
    if newtags:
        if isinstance(newtags, str):
            newtags = newtags.split()
        return __salt__['rabbitmq.list_users'](runas=runas)[name] - set(newtags)
    else:
        return []


def present(name,
            password=None,
            force=False,
            tags=None,
            perms=(),
            runas=None):
    '''
    Ensure the RabbitMQ user exists.

    name
        User name
    password
        User's password, if one needs to be set
    force
        If user exists, forcibly change the password
    tags
        Optional list of tags for the user
    perms
        A list of dicts with vhost keys and 3-tuple values
    runas
        Name of the user to run the command
    '''

    ret = {'name': name, 'result': True, 'comment': '', 'changes': {}}
    result = {}

    user_exists = __salt__['rabbitmq.user_exists'](name, runas=runas)

    if user_exists and not any((force, perms, tags)):
        log.debug('RabbitMQ user %s exists, '
                  'and force is not set.', name)
        ret['comment'] = 'User {0} already presents'.format(name)
        return ret
    else:
        changes = {'old': '', 'new': ''}

        if not user_exists:
            if __opts__['test']:
                ret['result'] = None
                ret['comment'] = 'User {0} is set to be created'.format(name)
                return ret

            log.debug("RabbitMQ user %s doesn't exist - Creating", name)
            result = __salt__['rabbitmq.add_user'](
                name, password, runas=runas)
        else:
            log.debug('RabbitMQ user %s exists', name)
            if force:
                if __opts__['test']:
                    ret['result'] = None

                if password is not None:
                    if __opts__['test']:
                        ret['comment'] = ('User {0}\'s password is '
                                          'set to be updated'.format(name))
                        return ret

                    result = __salt__['rabbitmq.change_password'](
                        name, password, runas=runas)
                    changes['new'] = 'Set password.\n'
                else:
                    log.debug('Password for %s is not set - Clearing password',
                              name)
                    if __opts__['test']:
                        ret['comment'] = ('User {0}\'s password is '
                                          'set to be removed'.format(name))
                        return ret

                    result = __salt__['rabbitmq.clear_password'](
                        name, runas=runas)
                    changes['old'] += 'Removed password.\n'

        if _check_tags_changes(name, tags, runas=runas):
            if __opts__['test']:
                ret['result'] = None
                ret['comment'] += ('Tags for user {0} '
                                   'is set to be changed'.format(name))
                return ret
            result.update(__salt__['rabbitmq.set_user_tags'](
                name, tags, runas=runas)
            )
            changes['new'] += 'Set tags: {0}\n'.format(tags)

        if _check_perms_changes(name, perms, runas=runas):
            if __opts__['test']:
                ret['result'] = None
                ret['comment'] += ('Permissions for user {0} '
                                   'is set to be changed'.format(name))
                return ret
            for vhost_perm in perms:
                for vhost, perm in vhost_perm.iteritems():
                    result.update(__salt__['rabbitmq.set_permissions'](
                        vhost, name, perm[0], perm[1], perm[2], runas=runas)
                    )
                    changes['new'] += (
                        'Set permissions {0} for vhost {1}'
                    ).format(perm, vhost)

        if 'Error' in result:
            ret['result'] = False
            ret['comment'] = result['Error']
        elif 'Added' in result:
            ret['comment'] = result['Added']
            ret['changes'] = changes
        elif 'Password Changed' in result:
            ret['comment'] = result['Password Changed']
            ret['changes'] = changes
        elif 'Password Cleared' in result:
            ret['comment'] = result['Password Cleared']
            ret['changes'] = changes

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

    if not user_exists:
        ret['comment'] = 'User {0} is not present'.format(name)
    elif __opts__['test']:
        ret['result'] = None
        if user_exists:
            ret['comment'] = 'Removing user {0}'.format(name)
    else:
        result = __salt__['rabbitmq.delete_user'](name, runas=runas)
        if 'Error' in result:
            ret['result'] = False
            ret['comment'] = result['Error']
        elif 'Deleted' in result:
            ret['comment'] = 'Deleted'
            ret['changes'] = {'new': '', 'old': name}

    return ret
