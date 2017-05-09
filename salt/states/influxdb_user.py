# -*- coding: utf-8 -*-
'''
Management of InfluxDB users
============================

(compatible with InfluxDB version 0.9+)
'''


def __virtual__():
    '''
    Only load if the influxdb module is available
    '''
    if 'influxdb.db_exists' in __salt__:
        return 'influxdb_user'
    return False


def _changes(name, admin, **client_args):
    '''
    Get necessary changes to given user account
    '''

    existing_user = __salt__['influxdb.user_info'](name, **client_args)
    changes = {}

    if existing_user['admin'] != admin:
        changes['admin'] = admin

    return changes


def present(name,
            password,
            admin=False,
            **client_args):
    '''
    Ensure that given user is present.

    name
        Name of the user to manage

    password
        Password of the user

    admin : False
        Whether the user should have cluster administration
        privileges or not.
    '''
    ret = {'name': name,
           'changes': {},
           'result': True,
           'comment': 'User {0} is present and up to date'.format(name)}

    if not __salt__['influxdb.user_exists'](name, **client_args):
        if __opts__['test']:
            ret['result'] = None
            ret['comment'] = 'User {0} will be created'.format(name)
            return ret
        else:
            if __salt__['influxdb.create_user'](
                    name, password, admin=admin, **client_args):
                ret['comment'] = 'Created user {0}'.format(name)
                ret['changes'][name] = 'created'
                return ret
            else:
                ret['comment'] = 'Failed to create user {0}'.format(name)
                ret['result'] = False
                return ret
    else:
        changes = _changes(name, admin, **client_args)
        if changes:
            if __opts__['test']:
                ret['result'] = None
                ret['comment'] = ('The following user attributes are set to '
                                  'be changed:\n')
                for k, v in changes.items():
                    ret['comment'] += u'{0}: {1}\n'.format(k, v)
                return ret
            else:
                pre = __salt__['influxdb.user_info'](name, **client_args)
                for k, v in changes.items():
                    if k == 'admin':
                        if v:
                            __salt__['influxdb.grant_admin_privileges'](name, **client_args)
                            continue
                        else:
                            __salt__['influxdb.revoke_admin_privileges'](name, **client_args)
                            continue

                post = __salt__['influxdb.user_info'](name, **client_args)
                for k in post:
                    if post[k] != pre[k]:
                        ret['changes'][k] = post[k]
                if ret['changes']:
                    ret['comment'] = 'Updated user {0}'.format(name)
    return ret


def absent(name, **client_args):
    '''
    Ensure that given user is absent.

    name
        The name of the user to manage
    '''
    ret = {'name': name,
           'changes': {},
           'result': True,
           'comment': 'User {0} is not present'.format(name)}

    if __salt__['influxdb.user_exists'](name, **client_args):
        if __opts__['test']:
            ret['result'] = None
            ret['comment'] = 'User {0} will be removed'.format(name)
            return ret
        else:
            if __salt__['influxdb.remove_user'](name, **client_args):
                ret['comment'] = 'Removed user {0}'.format(name)
                ret['changes'][name] = 'removed'
                return ret
            else:
                ret['comment'] = 'Failed to remove user {0}'.format(name)
                ret['result'] = False
                return ret
    return ret
