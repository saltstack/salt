# -*- coding: utf-8 -*-
'''
Management of Zabbix usermacros.
:codeauthor: Raymond Kuiper <qix@the-wired.net>

'''

# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals

# Import Salt libs
from salt.ext import six


def __virtual__():
    '''
    Only make these states available if Zabbix module is available.
    '''
    return 'zabbix.usermacro_create' in __salt__


def present(name, value, hostid=None, **kwargs):
    '''
    Creates a new usermacro.

    :param name: name of the usermacro
    :param value: value of the usermacro
    :param hostid: id's of the hosts to apply the usermacro on, if missing a global usermacro is assumed.

    :param _connection_user: Optional - zabbix user (can also be set in opts or pillar, see module's docstring)
    :param _connection_password: Optional - zabbix password (can also be set in opts or pillar, see module's docstring)
    :param _connection_url: Optional - url of zabbix frontend (can also be set in opts, pillar, see module's docstring)

    .. code-block:: yaml

        override host usermacro:
            zabbix_usermacro.present:
                - name: '{$SNMP_COMMUNITY}''
                - value: 'public'
                - hostid: 21

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
    if hostid:
        comment_usermacro_created = 'Usermacro {0} created on hostid {1}.'.format(name, hostid)
        comment_usermacro_updated = 'Usermacro {0} updated on hostid {1}.'.format(name, hostid)
        comment_usermacro_notcreated = 'Unable to create usermacro: {0} on hostid {1}. '.format(name, hostid)
        comment_usermacro_exists = 'Usermacro {0} already exists on hostid {1}.'.format(name, hostid)
        changes_usermacro_created = {name: {'old': 'Usermacro {0} does not exist on hostid {1}.'.format(name, hostid),
                                            'new': 'Usermacro {0} created on hostid {1}.'.format(name, hostid),
                                            }
                                     }
    else:
        comment_usermacro_created = 'Usermacro {0} created.'.format(name)
        comment_usermacro_updated = 'Usermacro {0} updated.'.format(name)
        comment_usermacro_notcreated = 'Unable to create usermacro: {0}. '.format(name)
        comment_usermacro_exists = 'Usermacro {0} already exists.'.format(name)
        changes_usermacro_created = {name: {'old': 'Usermacro {0} does not exist.'.format(name),
                                            'new': 'Usermacro {0} created.'.format(name),
                                            }
                                     }

    # Zabbix API expects script parameters as a string of arguments seperated by newline characters
    if 'exec_params' in kwargs:
        if isinstance(kwargs['exec_params'], list):
            kwargs['exec_params'] = '\n'.join(kwargs['exec_params'])+'\n'
        else:
            kwargs['exec_params'] = six.text_type(kwargs['exec_params'])+'\n'
    if hostid:
        usermacro_exists = __salt__['zabbix.usermacro_get'](name, hostids=hostid, **connection_args)
    else:
        usermacro_exists = __salt__['zabbix.usermacro_get'](name, globalmacro=True, **connection_args)

    if usermacro_exists:
        usermacroobj = usermacro_exists[0]
        if hostid:
            usermacroid = int(usermacroobj['hostmacroid'])
        else:
            usermacroid = int(usermacroobj['globalmacroid'])
        update_value = False

        if six.text_type(value) != usermacroobj['value']:
            update_value = True

    # Dry run, test=true mode
    if __opts__['test']:
        if usermacro_exists:
            if update_value:
                ret['result'] = None
                ret['comment'] = comment_usermacro_updated
            else:
                ret['result'] = True
                ret['comment'] = comment_usermacro_exists
        else:
            ret['result'] = None
            ret['comment'] = comment_usermacro_created
        return ret

    error = []

    if usermacro_exists:
        if update_value:
            ret['result'] = True
            ret['comment'] = comment_usermacro_updated

            if hostid:
                updated_value = __salt__['zabbix.usermacro_update'](usermacroid,
                                                                    value=value,
                                                                    **connection_args)
            else:
                updated_value = __salt__['zabbix.usermacro_updateglobal'](usermacroid,
                                                                          value=value,
                                                                          **connection_args)
            if not isinstance(updated_value, int):
                if 'error' in updated_value:
                    error.append(updated_value['error'])
                else:
                    ret['changes']['value'] = value
        else:
            ret['result'] = True
            ret['comment'] = comment_usermacro_exists
    else:
        if hostid:
            usermacro_create = __salt__['zabbix.usermacro_create'](name, value, hostid, **connection_args)
        else:
            usermacro_create = __salt__['zabbix.usermacro_createglobal'](name, value, **connection_args)

        if 'error' not in usermacro_create:
            ret['result'] = True
            ret['comment'] = comment_usermacro_created
            ret['changes'] = changes_usermacro_created
        else:
            ret['result'] = False
            ret['comment'] = comment_usermacro_notcreated + six.text_type(usermacro_create['error'])

    # error detected
    if error:
        ret['changes'] = {}
        ret['result'] = False
        ret['comment'] = six.text_type(error)

    return ret


def absent(name, hostid=None, **kwargs):
    '''
    Ensures that the mediatype does not exist, eventually deletes the mediatype.

    :param name: name of the usermacro
    :param hostid: id's of the hosts to apply the usermacro on, if missing a global usermacro is assumed.

    :param _connection_user: Optional - zabbix user (can also be set in opts or pillar, see module's docstring)
    :param _connection_password: Optional - zabbix password (can also be set in opts or pillar, see module's docstring)
    :param _connection_url: Optional - url of zabbix frontend (can also be set in opts, pillar, see module's docstring)

    .. code-block:: yaml

        delete_usermacro:
            zabbix_usermacro.absent:
                - name: '{$SNMP_COMMUNITY}'

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
    if hostid:
        comment_usermacro_deleted = 'Usermacro {0} deleted from hostid {1}.'.format(name, hostid)
        comment_usermacro_notdeleted = 'Unable to delete usermacro: {0} from hostid {1}.'.format(name, hostid)
        comment_usermacro_notexists = 'Usermacro {0} does not exist on hostid {1}.'.format(name, hostid)
        changes_usermacro_deleted = {name: {'old': 'Usermacro {0} exists on hostid {1}.'.format(name, hostid),
                                            'new': 'Usermacro {0} deleted from {1}.'.format(name, hostid),
                                            }
                                     }
    else:
        comment_usermacro_deleted = 'Usermacro {0} deleted.'.format(name)
        comment_usermacro_notdeleted = 'Unable to delete usermacro: {0}.'.format(name)
        comment_usermacro_notexists = 'Usermacro {0} does not exist.'.format(name)
        changes_usermacro_deleted = {name: {'old': 'Usermacro {0} exists.'.format(name),
                                            'new': 'Usermacro {0} deleted.'.format(name),
                                            }
                                     }
    if hostid:
        usermacro_exists = __salt__['zabbix.usermacro_get'](name, hostids=hostid, **connection_args)
    else:
        usermacro_exists = __salt__['zabbix.usermacro_get'](name, globalmacro=True, **connection_args)

    # Dry run, test=true mode
    if __opts__['test']:
        if not usermacro_exists:
            ret['result'] = True
            ret['comment'] = comment_usermacro_notexists
        else:
            ret['result'] = None
            ret['comment'] = comment_usermacro_deleted
        return ret

    if not usermacro_exists:
        ret['result'] = True
        ret['comment'] = comment_usermacro_notexists
    else:
        try:
            if hostid:
                usermacroid = usermacro_exists[0]['hostmacroid']
                usermacro_delete = __salt__['zabbix.usermacro_delete'](usermacroid, **connection_args)
            else:
                usermacroid = usermacro_exists[0]['globalmacroid']
                usermacro_delete = __salt__['zabbix.usermacro_deleteglobal'](usermacroid, **connection_args)
        except KeyError:
            usermacro_delete = False

        if usermacro_delete and 'error' not in usermacro_delete:
            ret['result'] = True
            ret['comment'] = comment_usermacro_deleted
            ret['changes'] = changes_usermacro_deleted
        else:
            ret['result'] = False
            ret['comment'] = comment_usermacro_notdeleted + six.text_type(usermacro_delete['error'])

    return ret
