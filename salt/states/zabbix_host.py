# -*- coding: utf-8 -*-
'''
Management of Zabbix hosts.

:codeauthor: Jiri Kotlin <jiri.kotlin@ultimum.io>
'''


def __virtual__():
    '''
    Only make these states available if Zabbix module is available.
    '''
    return 'zabbix.host_create' in __salt__


def present(host, groups, interfaces, **kwargs):
    '''
    Ensures that the host exists, eventually creates new host.

    NOTE: please use argument visible_name instead of name to not mess with name from salt sls

    Args:
        host: technical name of the host
        groups: groupids of host groups to add the host to
        interfaces: interfaces to be created for the host

        optional kwargs:
                _connection_user: zabbix user (can also be set in opts or pillar, see module's docstring)
                _connection_password: zabbix password (can also be set in opts or pillar, see module's docstring)
                _connection_url: url of zabbix frontend (can also be set in opts or pillar, see module's docstring)

                visible_name: string with visible name of the host, use 'visible_name' instead of 'name' parameter
                              to not mess with value supplied from Salt sls file.

                all standard host properties: keyword argument names differ depending on your zabbix version, see:

                https://www.zabbix.com/documentation/2.4/manual/api/reference/host/object#host

    '''
    ret = {'name': host, 'changes': {}, 'result': False, 'comment': ''}

    # Comment and change messages
    comment_host_created = 'Host {0} created.'.format(host)
    comment_host_notcreated = 'Unable to create host: {0}.'.format(host)
    comment_host_exists = 'Host {0} already exists.'.format(host)
    changes_host_created = {host: {'old': 'Host {0} does not exist.'.format(host),
                                   'new': 'Host {0} created.'.format(host),
                                   }
                            }

    host_exists = __salt__['zabbix.host_exists'](host)

    # Dry run, test=true mode
    if __opts__['test']:
        if host_exists:
            ret['result'] = True
            ret['comment'] = comment_host_exists
        else:
            ret['result'] = None
            ret['comment'] = comment_host_created
            ret['changes'] = changes_host_created

    if host_exists:
        ret['result'] = True
        ret['comment'] = comment_host_exists
    else:
        host_create = __salt__['zabbix.host_create'](host, groups, interfaces, **kwargs)

        if host_create:
            ret['result'] = True
            ret['comment'] = comment_host_created
            ret['changes'] = changes_host_created
        else:
            ret['result'] = False
            ret['comment'] = comment_host_notcreated

    return ret


def absent(name):
    """
    Ensures that the host does not exists, eventually deletes host.

    Args:
        name: technical name of the host

    """
    ret = {'name': name, 'changes': {}, 'result': False, 'comment': ''}

    # Comment and change messages
    comment_host_deleted = 'Host {0} deleted.'.format(name)
    comment_host_notdeleted = 'Unable to delete host: {0}.'.format(name)
    comment_host_notexists = 'Host {0} does not exist.'.format(name)
    changes_host_deleted = {name: {'old': 'Host {0} exists.'.format(name),
                                   'new': 'Host {0} deleted.'.format(name),
                                   }
                            }

    host_exists = __salt__['zabbix.host_exists'](name)

    # Dry run, test=true mode
    if __opts__['test']:
        if not host_exists:
            ret['result'] = True
            ret['comment'] = comment_host_notexists
        else:
            ret['result'] = None
            ret['comment'] = comment_host_deleted
            ret['changes'] = changes_host_deleted

    host_get = __salt__['zabbix.host_get'](name)

    if not host_get:
        ret['result'] = True
        ret['comment'] = comment_host_notexists
    else:
        try:
            hostid = host_get[0]['hostid']
            host_delete = __salt__['zabbix.host_delete'](hostid)
        except KeyError:
            host_delete = False

        if host_delete:
            ret['result'] = True
            ret['comment'] = comment_host_deleted
            ret['changes'] = changes_host_deleted
        else:
            ret['result'] = False
            ret['comment'] = comment_host_notdeleted

    return ret
