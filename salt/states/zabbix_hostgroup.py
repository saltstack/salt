# -*- coding: utf-8 -*-
'''
Management of Zabbix host groups.

:codeauthor: Jiri Kotlin <jiri.kotlin@ultimum.io>


'''


def __virtual__():
    '''
    Only make these states available if Zabbix module is available.
    '''
    return 'zabbix.hostgroup_create' in __salt__


def present(name):
    '''
    Ensures that the host group exists, eventually creates new host group.

    .. versionadded:: 2016.3.0

    :param name: name of the host group
    :param _connection_user: Optional - zabbix user (can also be set in opts or pillar, see module's docstring)
    :param _connection_password: Optional - zabbix password (can also be set in opts or pillar, see module's docstring)
    :param _connection_url: Optional - url of zabbix frontend (can also be set in opts, pillar, see module's docstring)

    .. code-block:: yaml

        create_testing_host_group:
            zabbix_hostgroup.present:
                - name: 'My hostgroup name'


    '''
    ret = {'name': name, 'changes': {}, 'result': False, 'comment': ''}

    # Comment and change messages
    comment_hostgroup_created = 'Host group {0} created.'.format(name)
    comment_hostgroup_notcreated = 'Unable to create host group: {0}. '.format(name)
    comment_hostgroup_exists = 'Host group {0} already exists.'.format(name)
    changes_hostgroup_created = {name: {'old': 'Host group {0} does not exist.'.format(name),
                                        'new': 'Host group {0} created.'.format(name),
                                        }
                                 }

    hostgroup_exists = __salt__['zabbix.hostgroup_exists'](name)

    # Dry run, test=true mode
    if __opts__['test']:
        if hostgroup_exists:
            ret['result'] = True
            ret['comment'] = comment_hostgroup_exists
        else:
            ret['result'] = None
            ret['comment'] = comment_hostgroup_created
            ret['changes'] = changes_hostgroup_created
        return ret

    if hostgroup_exists:
        ret['result'] = True
        ret['comment'] = comment_hostgroup_exists
    else:
        hostgroup_create = __salt__['zabbix.hostgroup_create'](name)

        if 'error' not in hostgroup_create:
            ret['result'] = True
            ret['comment'] = comment_hostgroup_created
            ret['changes'] = changes_hostgroup_created
        else:
            ret['result'] = False
            ret['comment'] = comment_hostgroup_notcreated + str(hostgroup_create['error'])

    return ret


def absent(name):
    '''
    Ensures that the host group does not exist, eventually delete host group.

    .. versionadded:: 2016.3.0

    :param name: name of the host group
    :param _connection_user: Optional - zabbix user (can also be set in opts or pillar, see module's docstring)
    :param _connection_password: Optional - zabbix password (can also be set in opts or pillar, see module's docstring)
    :param _connection_url: Optional - url of zabbix frontend (can also be set in opts, pillar, see module's docstring)

    .. code-block:: yaml

        delete_testing_host_group:
            zabbix_hostgroup.absent:
                - name: 'My hostgroup name'

    '''

    ret = {'name': name, 'changes': {}, 'result': False, 'comment': ''}

    # Comment and change messages
    comment_hostgroup_deleted = 'Host group {0} deleted.'.format(name)
    comment_hostgroup_notdeleted = 'Unable to delete host group: {0}. '.format(name)
    comment_hostgroup_notexists = 'Host group {0} does not exist.'.format(name)
    changes_hostgroup_deleted = {name: {'old': 'Host group {0} exists.'.format(name),
                                        'new': 'Host group {0} deleted.'.format(name),
                                        }
                                 }

    hostgroup_exists = __salt__['zabbix.hostgroup_exists'](name)

    # Dry run, test=true mode
    if __opts__['test']:
        if not hostgroup_exists:
            ret['result'] = True
            ret['comment'] = comment_hostgroup_notexists
        else:
            ret['result'] = None
            ret['comment'] = comment_hostgroup_deleted
            ret['changes'] = changes_hostgroup_deleted
        return ret

    hostgroup_get = __salt__['zabbix.hostgroup_get'](name)

    if not hostgroup_get:
        ret['result'] = True
        ret['comment'] = comment_hostgroup_notexists
    else:
        try:
            groupid = hostgroup_get[0]['groupid']
            hostgroup_delete = __salt__['zabbix.hostgroup_delete'](groupid)
        except KeyError:
            hostgroup_delete = False

        if hostgroup_delete and 'error' not in hostgroup_delete:
            ret['result'] = True
            ret['comment'] = comment_hostgroup_deleted
            ret['changes'] = changes_hostgroup_deleted
        else:
            ret['result'] = False
            ret['comment'] = comment_hostgroup_notdeleted + str(hostgroup_delete['error'])

    return ret
