# -*- coding: utf-8 -*-
'''
.. versionadded:: 2017.7

Management of Zabbix Valuemap object over Zabbix API.

:codeauthor: Jakub Sliva <jakub.sliva@ultimum.io>
'''
from __future__ import absolute_import
from __future__ import unicode_literals
import logging
import json

try:
    from salt.ext import six
    from salt.exceptions import SaltException
    IMPORTS_OK = True
except ImportError:
    IMPORTS_OK = False


log = logging.getLogger(__name__)


def __virtual__():
    '''
    Only make these states available if Zabbix module and run_query function is available
    and all 3rd party modules imported.
    '''
    if 'zabbix.run_query' in __salt__ and IMPORTS_OK:
        return True
    return False, 'Import zabbix or other needed modules failed.'


def present(name, params, **kwargs):
    '''
    Creates Zabbix Value map object or if differs update it according defined parameters

    :param name: Zabbix Value map name
    :param params: Definition of the Zabbix Value map
    :param _connection_user: Optional - zabbix user (can also be set in opts or pillar, see module's docstring)
    :param _connection_password: Optional - zabbix password (can also be set in opts or pillar, see module's docstring)
    :param _connection_url: Optional - url of zabbix frontend (can also be set in opts, pillar, see module's docstring)

    .. code-block:: yaml

        zabbix-valuemap-present:
            zabbix_valuemap.present:
                - name: Number mapping
                - params:
                    mappings:
                        - value: 1
                          newvalue: one
                        - value: 2
                          newvalue: two
    '''
    zabbix_id_mapper = __salt__['zabbix.get_zabbix_id_mapper']()

    dry_run = __opts__['test']
    ret = {'name': name, 'result': False, 'comment': '', 'changes': {}}

    # Create input params substituting functions with their results
    params['name'] = name
    input_params = __salt__['zabbix.substitute_params'](params, **kwargs)
    log.info('Zabbix Value map: input params: %s', six.text_type(json.dumps(input_params, indent=4)))

    search = {'output': 'extend',
              'selectMappings': 'extend',
              'filter': {
                  'name': name
              }}
    # GET Value map object if exists
    valuemap_get = __salt__['zabbix.run_query']('valuemap.get', search, **kwargs)
    log.info('Zabbix Value map: valuemap.get result: %s', six.text_type(json.dumps(valuemap_get, indent=4)))

    existing_obj = __salt__['zabbix.substitute_params'](valuemap_get[0], **kwargs) \
        if valuemap_get and len(valuemap_get) == 1 else False

    if existing_obj:
        diff_params = __salt__['zabbix.compare_params'](input_params, existing_obj)
        log.info('Zabbix Value map: input params: {%s', six.text_type(json.dumps(input_params, indent=4)))
        log.info('Zabbix Value map: Object comparison result. Differences: %s', six.text_type(diff_params))

        if diff_params:
            diff_params[zabbix_id_mapper['valuemap']] = existing_obj[zabbix_id_mapper['valuemap']]
            log.info('Zabbix Value map: update params: %s', six.text_type(json.dumps(diff_params, indent=4)))

            if dry_run:
                ret['result'] = True
                ret['comment'] = 'Zabbix Value map "{0}" would be fixed.'.format(name)
                ret['changes'] = {name: {'old': 'Zabbix Value map "{0}" differs '
                                                'in following parameters: {1}'.format(name, diff_params),
                                         'new': 'Zabbix Value map "{0}" would correspond to definition.'.format(name)}}
            else:
                valuemap_update = __salt__['zabbix.run_query']('valuemap.update', diff_params, **kwargs)
                log.info('Zabbix Value map: valuemap.update result: %s', six.text_type(valuemap_update))
                if valuemap_update:
                    ret['result'] = True
                    ret['comment'] = 'Zabbix Value map "{0}" updated.'.format(name)
                    ret['changes'] = {name: {'old': 'Zabbix Value map "{0}" differed '
                                                    'in following parameters: {1}'.format(name, diff_params),
                                             'new': 'Zabbix Value map "{0}" fixed.'.format(name)}}

        else:
            ret['result'] = True
            ret['comment'] = 'Zabbix Value map "{0}" already exists and corresponds to a definition.'.format(name)

    else:
        if dry_run:
            ret['result'] = True
            ret['comment'] = 'Zabbix Value map "{0}" would be created.'.format(name)
            ret['changes'] = {name: {'old': 'Zabbix Value map "{0}" does not exist.'.format(name),
                                     'new': 'Zabbix Value map "{0}" would be created '
                                            'according definition.'.format(name)}}
        else:
            # ACTION.CREATE
            valuemap_create = __salt__['zabbix.run_query']('valuemap.create', input_params, **kwargs)
            log.info('Zabbix Value map: valuemap.create result: %s', valuemap_create)

            if valuemap_create:
                ret['result'] = True
                ret['comment'] = 'Zabbix Value map "{0}" created.'.format(name)
                ret['changes'] = {name: {'old': 'Zabbix Value map "{0}" did not exist.'.format(name),
                                         'new': 'Zabbix Value map "{0}" created according definition.'.format(name)}}

    return ret


def absent(name, **kwargs):
    '''
    Makes the Zabbix Value map to be absent (either does not exist or delete it).

    :param name: Zabbix Value map name
    :param _connection_user: Optional - zabbix user (can also be set in opts or pillar, see module's docstring)
    :param _connection_password: Optional - zabbix password (can also be set in opts or pillar, see module's docstring)
    :param _connection_url: Optional - url of zabbix frontend (can also be set in opts, pillar, see module's docstring)

    .. code-block:: yaml

        zabbix-valuemap-absent:
            zabbix_valuemap.absent:
                - name: Value map name
    '''
    dry_run = __opts__['test']
    ret = {'name': name, 'result': False, 'comment': '', 'changes': {}}

    try:
        object_id = __salt__['zabbix.get_object_id_by_params']('valuemap', {'filter': {'name': name}}, **kwargs)
    except SaltException:
        object_id = False

    if not object_id:
        ret['result'] = True
        ret['comment'] = 'Zabbix Value map "{0}" does not exist.'.format(name)
    else:
        if dry_run:
            ret['result'] = True
            ret['comment'] = 'Zabbix Value map "{0}" would be deleted.'.format(name)
            ret['changes'] = {name: {'old': 'Zabbix Value map "{0}" exists.'.format(name),
                                     'new': 'Zabbix Value map "{0}" would be deleted.'.format(name)}}
        else:
            valuemap_delete = __salt__['zabbix.run_query']('valuemap.delete', [object_id], **kwargs)

            if valuemap_delete:
                ret['result'] = True
                ret['comment'] = 'Zabbix Value map "{0}" deleted.'.format(name)
                ret['changes'] = {name: {'old': 'Zabbix Value map "{0}" existed.'.format(name),
                                         'new': 'Zabbix Value map "{0}" deleted.'.format(name)}}

    return ret
