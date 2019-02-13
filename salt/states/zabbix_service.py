# -*- coding: utf-8 -*-
'''
Management of Zabbix services.


'''
from __future__ import absolute_import, print_function, unicode_literals


def __virtual__():
    '''
    Only make these states available if Zabbix module is available.
    '''
    return 'zabbix.service_add' in __salt__


def present(host, service_root, trigger_desc, service_name=None, **kwargs):
    '''
    .. versionadded:: Fluorine

    Ensure service exists under service root.

    :param host: Technical name of the host
    :param service_root: Path of service (path is split by /)
    :param service_name: Name of service
    :param trigger_desc: Description of trigger in zabbix
    :param _connection_user: Optional - zabbix user (can also be set in opts or pillar, see module's docstring)
    :param _connection_password: Optional - zabbix password (can also be set in opts or pillar, see module's docstring)
    :param _connection_url: Optional - url of zabbix frontend (can also be set in opts, pillar, see module's docstring)

    .. note::
        If services on path does not exists they are created.

    .. code-block:: yaml
        create_service_icmp:
            zabbix_service.present:
                - host: server-1
                - service_root: Server-group/server icmp
                - service_name: server-1-icmp
                - trigger_desc: is unavailable by ICMP
    '''
    if not service_name:
        service_name = host

    changes_service_added = {host: {'old': 'Service {0} does not exist under {1}.'.format(service_name, service_root),
                                    'new': 'Service {0} added under {1}.'.format(service_name, service_root),
                                    }
                             }

    connection_args = {}
    if '_connection_user' in kwargs:
        connection_args['_connection_user'] = kwargs['_connection_user']
    if '_connection_password' in kwargs:
        connection_args['_connection_password'] = kwargs['_connection_password']
    if '_connection_url' in kwargs:
        connection_args['_connection_url'] = kwargs['_connection_url']

    ret = {'name': host, 'changes': {}, 'result': False, 'comment': ''}

    host_exists = __salt__['zabbix.host_exists'](host, **connection_args)

    if not host_exists:
        ret['comment'] = 'Host {0} does not exists.'.format(host)
        return ret

    host = __salt__['zabbix.host_get'](name=host, **connection_args)[0]
    hostid = host['hostid']

    trigger = __salt__['zabbix.triggerid_get'](hostid=hostid, trigger_desc=trigger_desc, **kwargs)

    if not trigger:
        ret['comment'] = 'Trigger with description: "{0}" does not exists for host {1}.'.format(
            trigger_desc, host['name'])
        return ret

    trigger_id = trigger['result']['triggerid']

    root_services = service_root.split('/')
    root_id = None

    if __opts__['test']:
        for root_s in root_services:
            service = __salt__['zabbix.service_get'](service_rootid=root_id, service_name=root_s, **kwargs)
            if not service:
                ret['result'] = None
                ret['comment'] = "Service {0} will be added".format(service_name)
                ret['changes'] = changes_service_added
                return ret

            root_id = service[0]['serviceid']

        service = __salt__['zabbix.service_get'](service_rootid=root_id, service_name=service_name, **kwargs)
        if service:
            ret['result'] = True
            ret['comment'] = "Service {0} already exists".format(service_name)
        else:
            ret['result'] = None
            ret['comment'] = "Service {0} will be added".format(service_name)
            ret['changes'] = changes_service_added
        return ret

    root_id = None
    # ensure that root services exists
    for root_s in root_services:
        service = __salt__['zabbix.service_get'](service_rootid=root_id, service_name=root_s, **kwargs)
        if not service:
            service = __salt__['zabbix.service_add'](service_rootid=root_id, service_name=root_s, **kwargs)
            root_id = service['serviceids'][0]
        else:
            root_id = service[0]['serviceid']

    service = __salt__['zabbix.service_get'](service_rootid=root_id, service_name=service_name, **kwargs)
    if not service:
        service = __salt__['zabbix.service_add'](
            service_rootid=root_id, service_name=service_name, triggerid=trigger_id, **kwargs)
        if service:
            ret['comment'] = "Service {0} added {1} {0} {2}".format(service_name, root_id, trigger_id)
            ret['changes'] = changes_service_added
            ret['result'] = True
        else:
            ret['comment'] = "Service {0} could not be added".format(service_name)
            ret['result'] = False

    else:
        ret['comment'] = "Service {0} already exists".format(service_name)
        ret['result'] = True

    return ret


def absent(host, service_root, service_name=None, **kwargs):
    '''
    .. versionadded:: Fluorine
    Ensure service does not exists under service root.

    :param host: Technical name of the host
    :param service_root: Path of service (path is split /)
    :param service_name: Name of service
    :param _connection_user: Optional - zabbix user (can also be set in opts or pillar, see module's docstring)
    :param _connection_password: Optional - zabbix password (can also be set in opts or pillar, see module's docstring)
    :param _connection_url: Optional - url of zabbix frontend (can also be set in opts, pillar, see module's docstring)


    .. code-block:: yaml
        delete_service_icmp:
            zabbix_service.absent:
                - host: server-1
                - service_root: server-group/server icmp
                - service_name: server-1-icmp
    '''
    if not service_name:
        service_name = host

    changes_service_deleted = {host: {'old': 'Service {0} exist under {1}.'.format(service_name, service_root),
                                      'new': 'Service {0} deleted under {1}.'.format(service_name, service_root),
                                      }
                               }

    connection_args = {}
    if '_connection_user' in kwargs:
        connection_args['_connection_user'] = kwargs['_connection_user']
    if '_connection_password' in kwargs:
        connection_args['_connection_password'] = kwargs['_connection_password']
    if '_connection_url' in kwargs:
        connection_args['_connection_url'] = kwargs['_connection_url']

    ret = {'name': host, 'changes': {}, 'result': False, 'comment': ''}

    host_exists = __salt__['zabbix.host_exists'](host, **connection_args)

    if not host_exists:
        ret['comment'] = 'Host {0} does not exists.'.format(host)
        return ret

    root_services = service_root.split('/')
    root_id = None

    if __opts__['test']:
        for root_s in root_services:
            service = __salt__['zabbix.service_get'](service_rootid=root_id, service_name=root_s, **kwargs)
            if not service:
                ret['result'] = None
                ret['comment'] = "Service {0} will be deleted".format(service_name)
                ret['changes'] = changes_service_deleted
                return ret

            root_id = service[0]['serviceid']

        service = __salt__['zabbix.service_get'](service_rootid=root_id, service_name=service_name, **kwargs)
        if not service:
            ret['result'] = True
            ret['comment'] = "Service {0} does not exists".format(service_name)
        else:
            ret['result'] = None
            ret['comment'] = "Service {0} will be deleted".format(service_name)
            ret['changes'] = changes_service_deleted
        return ret

    root_id = None
    # ensure that root services exists
    for root_s in root_services:
        service = __salt__['zabbix.service_get'](service_rootid=root_id, service_name=root_s, **kwargs)
        if not service:
            ret['result'] = True
            ret['comment'] = "Service {0} does not exists".format(service_name)
            return ret
        else:
            root_id = service[0]['serviceid']

    service = __salt__['zabbix.service_get'](service_rootid=root_id, service_name=service_name, **kwargs)
    if not service:
        ret['result'] = True
        ret['comment'] = "Service {0} does not exists".format(service_name)
        return ret
    else:
        service = __salt__['zabbix.service_delete'](service_id=service[0]['serviceid'], **connection_args)
        if service:
            ret['comment'] = "Service {0} deleted".format(service_name)
            ret['changes'] = changes_service_deleted
            ret['result'] = True
        else:
            ret['comment'] = "Service {0} could not be deleted".format(service_name)
            ret['result'] = False

    return ret
