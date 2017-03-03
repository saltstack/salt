# -*- coding: utf-8 -*-
'''
Management of Zabbix user groups.

:codeauthor: Jiri Kotlin <jiri.kotlin@ultimum.io>

'''


def __virtual__():
    '''
    Only make these states available if Zabbix module is available.
    '''
    return 'zabbix.usergroup_create' in __salt__


def present(name, **kwargs):
    '''
    Creates new user.
    NOTE: This function accepts all standard user group properties: keyword argument names differ depending on your
    zabbix version, see:
    https://www.zabbix.com/documentation/2.0/manual/appendix/api/usergroup/definitions#user_group

    .. versionadded:: 2016.3.0

    :param name: name of the user group
    :param _connection_user: Optional - zabbix user (can also be set in opts or pillar, see module's docstring)
    :param _connection_password: Optional - zabbix password (can also be set in opts or pillar, see module's docstring)
    :param _connection_url: Optional - url of zabbix frontend (can also be set in opts, pillar, see module's docstring)

    .. code-block:: yaml

        make_new_thai_monks_usergroup:
            zabbix_usergroup.present:
                - name: 'Thai monks'
                - gui_access: 1
                - debug_mode: 0
                - users_status: 0

    '''
    connection_args = {}
    if '_connection_user' in kwargs:
        connection_args['_connection_user'] = kwargs['_connection_user']
    if '_connection_password' in kwargs:
        connection_args['_connection_password'] = kwargs['_connection_password']
    if '_connection_url' in kwargs:
        connection_args['_connection_url'] = kwargs['_connection_url']

    ret = {'name': name, 'changes': {}, 'result': False, 'comment': ''}

    # Comment and change messages
    comment_usergroup_created = 'User group {0} created.'.format(name)
    comment_usergroup_updated = 'User group {0} updated.'.format(name)
    comment_usergroup_notcreated = 'Unable to create user group: {0}. '.format(name)
    comment_usergroup_exists = 'User group {0} already exists.'.format(name)
    changes_usergroup_created = {name: {'old': 'User group {0} does not exist.'.format(name),
                                        'new': 'User group {0} created.'.format(name),
                                        }
                                 }

    usergroup_exists = __salt__['zabbix.usergroup_exists'](name, **connection_args)

    if usergroup_exists:
        usergroup = __salt__['zabbix.usergroup_get'](name, **connection_args)[0]
        usrgrpid = int(usergroup['usrgrpid'])
        update_debug_mode = False
        update_gui_access = False
        update_users_status = False

        if 'debug_mode' in kwargs:
            if int(kwargs['debug_mode']) != int(usergroup['debug_mode']):
                update_debug_mode = True

        if 'gui_access' in kwargs:
            if int(kwargs['gui_access']) != int(usergroup['gui_access']):
                update_gui_access = True

        if 'users_status' in kwargs:
            if int(kwargs['users_status']) != int(usergroup['users_status']):
                update_users_status = True

    # Dry run, test=true mode
    if __opts__['test']:
        if usergroup_exists:
            if update_debug_mode or update_gui_access or update_users_status:
                ret['result'] = None
                ret['comment'] = comment_usergroup_updated
            else:
                ret['result'] = True
                ret['comment'] = comment_usergroup_exists
        else:
            ret['result'] = None
            ret['comment'] = comment_usergroup_created
        return ret

    error = []

    if usergroup_exists:
        if update_debug_mode or update_gui_access or update_users_status:
            ret['result'] = True
            ret['comment'] = comment_usergroup_updated

            if update_debug_mode:
                updated_debug = __salt__['zabbix.usergroup_update'](usrgrpid,
                                                                    debug_mode=kwargs['debug_mode'],
                                                                    **connection_args)
                if 'error' in updated_debug:
                    error.append(updated_debug['error'])
                else:
                    ret['changes']['debug_mode'] = kwargs['debug_mode']

            if update_gui_access:
                updated_gui = __salt__['zabbix.usergroup_update'](usrgrpid,
                                                                  gui_access=kwargs['gui_access'],
                                                                  **connection_args)
                if 'error' in updated_gui:
                    error.append(updated_gui['error'])
                else:
                    ret['changes']['gui_access'] = kwargs['gui_access']

            if update_users_status:
                updated_status = __salt__['zabbix.usergroup_update'](usrgrpid,
                                                                     users_status=kwargs['users_status'],
                                                                     **connection_args)
                if 'error' in updated_status:
                    error.append(updated_status['error'])
                else:
                    ret['changes']['users_status'] = kwargs['users_status']

        else:
            ret['result'] = True
            ret['comment'] = comment_usergroup_exists
    else:
        usergroup_create = __salt__['zabbix.usergroup_create'](name, **kwargs)

        if 'error' not in usergroup_create:
            ret['result'] = True
            ret['comment'] = comment_usergroup_created
            ret['changes'] = changes_usergroup_created
        else:
            ret['result'] = False
            ret['comment'] = comment_usergroup_notcreated + str(usergroup_create['error'])

    # error detected
    if error:
        ret['changes'] = {}
        ret['result'] = False
        ret['comment'] = str(error)

    return ret


def absent(name, **kwargs):
    '''
    Ensures that the user group does not exist, eventually delete user group.

    .. versionadded:: 2016.3.0

    :param name: name of the user group
    :param _connection_user: Optional - zabbix user (can also be set in opts or pillar, see module's docstring)
    :param _connection_password: Optional - zabbix password (can also be set in opts or pillar, see module's docstring)
    :param _connection_url: Optional - url of zabbix frontend (can also be set in opts, pillar, see module's docstring)

    .. code-block:: yaml

        delete_thai_monks_usrgrp:
            zabbix_usergroup.absent:
                - name: 'Thai monks'
    '''
    connection_args = {}
    if '_connection_user' in kwargs:
        connection_args['_connection_user'] = kwargs['_connection_user']
    if '_connection_password' in kwargs:
        connection_args['_connection_password'] = kwargs['_connection_password']
    if '_connection_url' in kwargs:
        connection_args['_connection_url'] = kwargs['_connection_url']

    ret = {'name': name, 'changes': {}, 'result': False, 'comment': ''}

    # Comment and change messages
    comment_usergroup_deleted = 'User group {0} deleted.'.format(name)
    comment_usergroup_notdeleted = 'Unable to delete user group: {0}. '.format(name)
    comment_usergroup_notexists = 'User group {0} does not exist.'.format(name)
    changes_usergroup_deleted = {name: {'old': 'User group {0} exists.'.format(name),
                                        'new': 'User group {0} deleted.'.format(name),
                                        }
                                 }

    usergroup_exists = __salt__['zabbix.usergroup_exists'](name, **connection_args)

    # Dry run, test=true mode
    if __opts__['test']:
        if not usergroup_exists:
            ret['result'] = True
            ret['comment'] = comment_usergroup_notexists
        else:
            ret['result'] = None
            ret['comment'] = comment_usergroup_deleted
        return ret

    usergroup_get = __salt__['zabbix.usergroup_get'](name, **connection_args)

    if not usergroup_get:
        ret['result'] = True
        ret['comment'] = comment_usergroup_notexists
    else:
        try:
            usrgrpid = usergroup_get[0]['usrgrpid']
            usergroup_delete = __salt__['zabbix.usergroup_delete'](usrgrpid, **connection_args)
        except KeyError:
            usergroup_delete = False

        if usergroup_delete and 'error' not in usergroup_delete:
            ret['result'] = True
            ret['comment'] = comment_usergroup_deleted
            ret['changes'] = changes_usergroup_deleted
        else:
            ret['result'] = False
            ret['comment'] = comment_usergroup_notdeleted + str(usergroup_delete['error'])

    return ret
