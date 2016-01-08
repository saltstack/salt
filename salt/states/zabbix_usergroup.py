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

    Args:
        alias: user alias
        passwd: user's password
        usrgrps: user groups to add the user to

        optional kwargs:
                _connection_user: zabbix user (can also be set in opts or pillar,
                                               see execution module's docstring)
                _connection_password: zabbix password (can also be set in opts or pillar,
                                                      see execution module's docstring)
                _connection_url: url of zabbix frontend (can also be set in opts or pillar,
                                                         see execution module's docstring)

                all standard user group properties: keyword argument names differ depending on your zabbix version, see:

                https://www.zabbix.com/documentation/2.0/manual/appendix/api/usergroup/definitions#user_group

    '''
    ret = {'name': name, 'changes': {}, 'result': False, 'comment': ''}

    # Comment and change messages
    comment_usergroup_created = 'User group {0} created.'.format(name)
    comment_usergroup_notcreated = 'Unable to create user group: {0}.'.format(name)
    comment_usergroup_exists = 'User group {0} already exists.'.format(name)
    changes_usergroup_created = {name: {'old': 'User group {0} does not exist.'.format(name),
                                        'new': 'User group {0} created.'.format(name),
                                        }
                                 }

    usergroup_exists = __salt__['zabbix.usergroup_exists'](name)

    # Dry run, test=true mode
    if __opts__['test']:
        if usergroup_exists:
            ret['result'] = True
            ret['comment'] = comment_usergroup_exists
        else:
            ret['result'] = None
            ret['comment'] = comment_usergroup_created
            ret['changes'] = changes_usergroup_created

    if usergroup_exists:
        ret['result'] = True
        ret['comment'] = comment_usergroup_exists
    else:
        usergroup_create = __salt__['zabbix.usergroup_create'](name, **kwargs)

        if usergroup_create:
            ret['result'] = True
            ret['comment'] = comment_usergroup_created
            ret['changes'] = changes_usergroup_created
        else:
            ret['result'] = False
            ret['comment'] = comment_usergroup_notcreated

    return ret


def absent(name):
    '''
    Ensures that the user group does not exist, eventually delete user group.

    Args:
        name: name of the user group
    '''
    ret = {'name': name, 'changes': {}, 'result': False, 'comment': ''}

    # Comment and change messages
    comment_usergroup_deleted = 'User group {0} deleted.'.format(name)
    comment_usergroup_notdeleted = 'Unable to delete user group: {0}.'.format(name)
    comment_usergroup_notexists = 'User group {0} does not exist.'.format(name)
    changes_usergroup_deleted = {name: {'old': 'User group {0} exists.'.format(name),
                                        'new': 'User group {0} deleted.'.format(name),
                                        }
                                 }

    usergroup_exists = __salt__['zabbix.usergroup_exists'](name)

    # Dry run, test=true mode
    if __opts__['test']:
        if not usergroup_exists:
            ret['result'] = True
            ret['comment'] = comment_usergroup_notexists
        else:
            ret['result'] = None
            ret['comment'] = comment_usergroup_deleted
            ret['changes'] = changes_usergroup_deleted

    usergroup_get = __salt__['zabbix.usergroup_get'](name)

    if not usergroup_get:
        ret['result'] = True
        ret['comment'] = comment_usergroup_notexists
    else:
        try:
            usrgrpid = usergroup_get[0]['usrgrpid']
            usergroup_delete = __salt__['zabbix.usergroup_delete'](usrgrpid)
        except KeyError:
            usergroup_delete = False

        if usergroup_delete:
            ret['result'] = True
            ret['comment'] = comment_usergroup_deleted
            ret['changes'] = changes_usergroup_deleted
        else:
            ret['result'] = False
            ret['comment'] = comment_usergroup_notdeleted

    return ret
