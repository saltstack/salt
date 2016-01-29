# -*- coding: utf-8 -*-
'''
Management of Zabbix users.

:codeauthor: Jiri Kotlin <jiri.kotlin@ultimum.io>
'''


def __virtual__():
    '''
    Only make these states available if Zabbix module is available.
    '''
    return 'zabbix.user_create' in __salt__


def present(alias, passwd, usrgrps, **kwargs):
    '''
    Ensures that the user exists, eventually creates new user.

    NOTE: use argument firstname instead of name to not mess values with name from salt sls

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

                firstname: string with firstname of the user, use 'firstname' instead of 'name' parameter to not mess
                            with value supplied from Salt sls file.

    '''
    ret = {'name': alias, 'changes': {}, 'result': False, 'comment': ''}

    # Comment and change messages
    comment_user_created = 'User {0} created.'.format(alias)
    comment_user_notcreated = 'Unable to create user: {0}.'.format(alias)
    comment_user_exists = 'User {0} already exists.'.format(alias)
    changes_user_created = {alias: {'old': 'User {0} does not exist.'.format(alias),
                                    'new': 'User {0} created.'.format(alias),
                                    }
                            }

    user_exists = __salt__['zabbix.user_exists'](alias)

    # Dry run, test=true mode
    if __opts__['test']:
        if user_exists:
            ret['result'] = True
            ret['comment'] = comment_user_exists
        else:
            ret['result'] = None
            ret['comment'] = comment_user_created
            ret['changes'] = changes_user_created

    if user_exists:
        ret['result'] = True
        ret['comment'] = comment_user_exists
    else:
        user_create = __salt__['zabbix.user_create'](alias, passwd, usrgrps, **kwargs)

        if user_create:
            ret['result'] = True
            ret['comment'] = comment_user_created
            ret['changes'] = changes_user_created
        else:
            ret['result'] = False
            ret['comment'] = comment_user_notcreated

    return ret


def absent(name):
    '''
    Ensures that the user does not exist, eventually delete user.

    Args:
        name: user alias
    '''
    ret = {'name': name, 'changes': {}, 'result': False, 'comment': ''}

    # Comment and change messages
    comment_user_deleted = 'USer {0} deleted.'.format(name)
    comment_user_notdeleted = 'Unable to delete user: {0}.'.format(name)
    comment_user_notexists = 'User {0} does not exist.'.format(name)
    changes_user_deleted = {name: {'old': 'User {0} exists.'.format(name),
                                   'new': 'User {0} deleted.'.format(name),
                                   }
                            }

    user_get = __salt__['zabbix.user_get'](name)

    # Dry run, test=true mode
    if __opts__['test']:
        if not user_get:
            ret['result'] = True
            ret['comment'] = comment_user_notexists
        else:
            ret['result'] = None
            ret['comment'] = comment_user_deleted
            ret['changes'] = changes_user_deleted

    if not user_get:
        ret['result'] = True
        ret['comment'] = comment_user_notexists
    else:
        try:
            userid = user_get[0]['userid']
            user_delete = __salt__['zabbix.user_delete'](userid)
        except KeyError:
            user_delete = False

        if user_delete:
            ret['result'] = True
            ret['comment'] = comment_user_deleted
            ret['changes'] = changes_user_deleted
        else:
            ret['result'] = False
            ret['comment'] = comment_user_notdeleted

    return ret
