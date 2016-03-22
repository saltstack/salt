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

# Import python libs
from __future__ import absolute_import
import logging

# Import salt libs
import salt.utils
import salt.ext.six as six
from salt.exceptions import CommandExecutionError

log = logging.getLogger(__name__)


def __virtual__():
    '''
    Only load if RabbitMQ is installed.
    '''
    return salt.utils.which('rabbitmqctl') is not None


def _check_perms_changes(name, newperms, runas=None, existing=None):
    '''
    Check whether Rabbitmq user's permissions need to be changed.
    '''
    if not newperms:
        return False

    if existing is None:
        try:
            existing = __salt__['rabbitmq.list_user_permissions'](name, runas=runas)
        except CommandExecutionError as err:
            log.error('Error: {0}'.format(err))
            return False

    perm_need_change = False
    for vhost_perms in newperms:
        for vhost, perms in vhost_perms.iteritems():
            if vhost in existing:
                existing_vhost = existing[vhost]
                if perms != existing_vhost:
                    # This checks for setting permissions to nothing in the state,
                    # when previous state runs have already set permissions to
                    # nothing. We don't want to report a change in this case.
                    if existing_vhost == '' and perms == ['', '', '']:
                        continue
                    perm_need_change = True
            else:
                perm_need_change = True

    return perm_need_change


def _get_current_tags(name, runas=None):
    '''
    Whether Rabbitmq user's tags need to be changed
    '''
    try:
        return list(__salt__['rabbitmq.list_users'](runas=runas)[name])
    except CommandExecutionError as err:
        log.error('Error: {0}'.format(err))
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
    ret = {'name': name, 'result': False, 'comment': '', 'changes': {}}
    try:
        user = __salt__['rabbitmq.user_exists'](name, runas=runas)
    except CommandExecutionError as err:
        ret['comment'] = 'Error: {0}'.format(err)
        return ret

    if user and not any((force, perms, tags)):
        log.debug('RabbitMQ user \'{0}\' exists and force is not set.'.format(name))
        ret['comment'] = 'User \'{0}\' is already present.'.format(name)
        ret['result'] = True
        return ret

    if not user:
        ret['changes'].update({'user':
                              {'old': '',
                               'new': name}})
        if __opts__['test']:
            ret['result'] = None
            ret['comment'] = 'User \'{0}\' is set to be created.'.format(name)
            return ret

        log.debug('RabbitMQ user \'{0}\' doesn\'t exist - Creating.'.format(name))
        try:
            __salt__['rabbitmq.add_user'](name, password, runas=runas)
        except CommandExecutionError as err:
            ret['comment'] = 'Error: {0}'.format(err)
            return ret
    else:
        log.debug('RabbitMQ user \'{0}\' exists'.format(name))
        if force:
            if password is not None:
                if not __opts__['test']:
                    try:
                        __salt__['rabbitmq.change_password'](name, password, runas=runas)
                    except CommandExecutionError as err:
                        ret['comment'] = 'Error: {0}'.format(err)
                        return ret
                ret['changes'].update({'password':
                                      {'old': '',
                                       'new': 'Set password.'}})
            else:
                if not __opts__['test']:
                    log.debug('Password for {0} is not set - Clearing password.'.format(name))
                    try:
                        __salt__['rabbitmq.clear_password'](name, runas=runas)
                    except CommandExecutionError as err:
                        ret['comment'] = 'Error: {0}'.format(err)
                        return ret
                ret['changes'].update({'password':
                                      {'old': 'Removed password.',
                                       'new': ''}})

    if tags is not None:
        current_tags = _get_current_tags(name, runas=runas)
        if isinstance(tags, str):
            tags = tags.split()
        # Diff the tags sets. Symmetric difference operator ^ will give us
        # any element in one set, but not both
        if set(tags) ^ set(current_tags):
            if not __opts__['test']:
                try:
                    __salt__['rabbitmq.set_user_tags'](name, tags, runas=runas)
                except CommandExecutionError as err:
                    ret['comment'] = 'Error: {0}'.format(err)
                    return ret
            ret['changes'].update({'tags':
                                  {'old': current_tags,
                                   'new': tags}})
    try:
        existing_perms = __salt__['rabbitmq.list_user_permissions'](name, runas=runas)
    except CommandExecutionError as err:
        ret['comment'] = 'Error: {0}'.format(err)
        return ret

    if _check_perms_changes(name, perms, runas=runas, existing=existing_perms):
        for vhost_perm in perms:
            for vhost, perm in six.iteritems(vhost_perm):
                if not __opts__['test']:
                    try:
                        __salt__['rabbitmq.set_permissions'](
                            vhost, name, perm[0], perm[1], perm[2], runas=runas
                        )
                    except CommandExecutionError as err:
                        ret['comment'] = 'Error: {0}'.format(err)
                        return ret
                new_perms = {vhost: perm}
                if existing_perms != new_perms:
                    if ret['changes'].get('perms') is None:
                        ret['changes'].update({'perms':
                                              {'old': {},
                                               'new': {}}})
                    ret['changes']['perms']['old'].update(existing_perms)
                    ret['changes']['perms']['new'].update(new_perms)

    ret['result'] = True
    if ret['changes'] == {}:
        ret['comment'] = '\'{0}\' is already in the desired state.'.format(name)
        return ret

    if __opts__['test']:
        ret['result'] = None
        ret['comment'] = 'Configuration for \'{0}\' will change.'.format(name)
        return ret

    ret['comment'] = '\'{0}\' was configured.'.format(name)
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
    ret = {'name': name, 'result': False, 'comment': '', 'changes': {}}

    try:
        user_exists = __salt__['rabbitmq.user_exists'](name, runas=runas)
    except CommandExecutionError as err:
        ret['comment'] = 'Error: {0}'.format(err)
        return ret

    if user_exists:
        if not __opts__['test']:
            try:
                __salt__['rabbitmq.delete_user'](name, runas=runas)
            except CommandExecutionError as err:
                ret['comment'] = 'Error: {0}'.format(err)
                return ret
        ret['changes'].update({'name':
                              {'old': name,
                               'new': ''}})
    else:
        ret['result'] = True
        ret['comment'] = 'The user \'{0}\' is not present.'.format(name)
        return ret

    if __opts__['test'] and ret['changes']:
        ret['result'] = None
        ret['comment'] = 'The user \'{0}\' will be removed.'.format(name)
        return ret

    ret['result'] = True
    ret['comment'] = 'The user \'{0}\' was removed.'.format(name)
    return ret
