# -*- coding: utf-8 -*-

'''
StatusPage
==========

Manage the StatusPage_ configuration.

.. _StatusPage: https://www.statuspage.io/

In the minion configuration file, the following block is required:

.. code-block:: yaml

  statuspage:
    api_key: <API_KEY>
    page_id: <PAGE_ID>

.. versionadded:: Nitrogen
'''

from __future__ import unicode_literals
from __future__ import absolute_import

# import python std lib
import time
import logging

# import salt
from salt.ext import six

# ----------------------------------------------------------------------------------------------------------------------
# module properties
# ----------------------------------------------------------------------------------------------------------------------

__virtualname__ = 'statuspage'

log = logging.getLogger(__file__)

_DO_NOT_COMPARE_FIELDS = [
    'created_at',
    'updated_at'
]

_MATCH_KEYS = [
    'id',
    'name'
]

_PACE = 1  # 1 request per second

# ----------------------------------------------------------------------------------------------------------------------
# property functions
# ----------------------------------------------------------------------------------------------------------------------


def __virtual__():
    '''
    Return the execution module virtualname.
    '''
    return __virtualname__


def _default_ret(name):
    '''
    Default dictionary returned.
    '''
    return {
        'name': name,
        'result': False,
        'comment': '',
        'changes': {}
    }


def _compute_diff_ret():
    '''
    Default dictionary retuned by the _compute_diff helper.
    '''
    return {
        'add': [],
        'update': [],
        'remove': []
    }


def _clear_dict(endpoint_props):
    '''
    Eliminates None entries from the features of the endpoint dict.
    '''
    return dict(
        (prop_name, prop_val)
        for prop_name, prop_val in six.iteritems(endpoint_props)
        if prop_val is not None
    )


def _ignore_keys(endpoint_props):
    '''
    Ignores some keys that might be different without any important info.
    These keys are defined under _DO_NOT_COMPARE_FIELDS.
    '''
    return dict(
        (prop_name, prop_val)
        for prop_name, prop_val in six.iteritems(endpoint_props)
        if prop_name not in _DO_NOT_COMPARE_FIELDS
    )


def _unique(list_of_dicts):
    '''
    Returns an unique list of dictionaries given a list that may contain duplicates.
    '''
    unique_list = []
    for ele in list_of_dicts:
        if ele not in unique_list:
            unique_list.append(ele)
    return unique_list


def _clear_ignore(endpoint_props):
    '''
    Both _clear_dict and _ignore_keys in a single iteration.
    '''
    return dict(
        (prop_name, prop_val)
        for prop_name, prop_val in six.iteritems(endpoint_props)
        if prop_name not in _DO_NOT_COMPARE_FIELDS and prop_val is not None
    )


def _clear_ignore_list(lst):
    '''
    Apply _clear_ignore to a list.
    '''
    return _unique([
        _clear_ignore(ele)
        for ele in lst
    ])


def _find_match(ele, lst):
    '''
    Find a matching element in a list.
    '''
    for _ele in lst:
        for match_key in _MATCH_KEYS:
            if _ele.get(match_key) == ele.get(match_key):
                return ele


def _update_on_fields(prev_ele, new_ele):
    '''
    Return a dict with fields that differ between two dicts.
    '''
    fields_update = dict(
        (prop_name, prop_val)
        for prop_name, prop_val in six.iteritems(new_ele)
        if new_ele.get(prop_name) != prev_ele.get(prop_name) or prop_name in _MATCH_KEYS
    )
    if len(set(fields_update.keys()) | set(_MATCH_KEYS)) > len(set(_MATCH_KEYS)):
        if 'id' not in fields_update:
            # in case of update, the ID is necessary
            # if not specified in the pillar,
            # will try to get it from the prev_ele
            fields_update['id'] = prev_ele['id']
        return fields_update


def _compute_diff(expected_endpoints, configured_endpoints):
    '''
    Compares configured endpoints with the expected configuration and returns the differences.
    '''
    new_endpoints = []
    update_endpoints = []
    remove_endpoints = []

    ret = _compute_diff_ret()

    # noth configured => configure with expected endpoints
    if not configured_endpoints:
        ret.update({
            'add': expected_endpoints
        })
        return ret

    # noting expected => remove everything
    if not expected_endpoints:
        ret.update({
            'remove': configured_endpoints
        })
        return ret

    expected_endpoints_clear = _clear_ignore_list(expected_endpoints)
    configured_endpoints_clear = _clear_ignore_list(configured_endpoints)

    for expected_endpoint_clear in expected_endpoints_clear:
        if expected_endpoint_clear not in configured_endpoints_clear:
            # none equal => add or update
            matching_ele = _find_match(expected_endpoint_clear, configured_endpoints_clear)
            if not matching_ele:
                # new element => add
                new_endpoints.append(expected_endpoint_clear)
            else:
                # element matched, but some fields are different
                update_fields = _update_on_fields(matching_ele, expected_endpoint_clear)
                if update_fields:
                    update_endpoints.append(update_fields)
    for configured_endpoint_clear in configured_endpoints_clear:
        if configured_endpoint_clear not in expected_endpoints_clear:
            matching_ele = _find_match(configured_endpoint_clear, expected_endpoints_clear)
            if not matching_ele:
                #  no match found => remove
                remove_endpoints.append(configured_endpoint_clear)

    return {
        'add': new_endpoints,
        'update': update_endpoints,
        'remove': remove_endpoints
    }

# ----------------------------------------------------------------------------------------------------------------------
# callable functions
# ----------------------------------------------------------------------------------------------------------------------


def create(name,
           endpoint='incidents',
           api_url=None,
           page_id=None,
           api_key=None,
           api_version=None,
           **kwargs):
    '''
    Insert a new entry under a specific endpoint.

    endpoint: incidents
        Insert under this specific endpoint.

    page_id
        Page ID. Can also be specified in the config file.

    api_key
        API key. Can also be specified in the config file.

    api_version: 1
        API version. Can also be specified in the config file.

    api_url
        Custom API URL in case the user has a StatusPage service running in a custom environment.

    **kwargs
        Other params.

    SLS Example:

    .. code-block:: yaml

        create-my-component:
            statuspage.create:
                - endpoint: components
                - name: my component
                - group_id: 993vgplshj12
    '''
    ret = _default_ret(name)
    endpoint_sg = endpoint[:-1]  # singular
    if __opts__['test']:
        ret['comment'] = 'The following {endpoint} would be created:'.format(endpoint=endpoint_sg)
        ret['result'] = None
        ret['changes'][endpoint] = {}
        for karg, warg in six.iteritems(kwargs):
            if warg is None or karg.startswith('__'):
                continue
            ret['changes'][endpoint][karg] = warg
        return ret
    sp_create = __salt__['statuspage.create'](endpoint=endpoint,
                                              api_url=api_url,
                                              page_id=page_id,
                                              api_key=api_key,
                                              api_version=api_version,
                                              **kwargs)
    if not sp_create.get('result'):
        ret['comment'] = 'Unable to create {endpoint}: {msg}'.format(endpoint=endpoint_sg,
                                                                     msg=sp_create.get('comment'))
    else:
        ret['comment'] = '{endpoint} created!'.format(endpoint=endpoint_sg)
        ret['result'] = True
        ret['changes'] = sp_create.get('out')


def update(name,
           endpoint='incidents',
           id=None,
           api_url=None,
           page_id=None,
           api_key=None,
           api_version=None,
           **kwargs):
    '''
    Update attribute(s) of a specific endpoint.

    id
        The unique ID of the enpoint entry.

    endpoint: incidents
        Endpoint name.

    page_id
        Page ID. Can also be specified in the config file.

    api_key
        API key. Can also be specified in the config file.

    api_version: 1
        API version. Can also be specified in the config file.

    api_url
        Custom API URL in case the user has a StatusPage service running in a custom environment.

    SLS Example:

    .. code-block:: yaml

        update-my-incident:
            statuspage.update:
                - id: dz959yz2nd4l
                - status: resolved
    '''
    ret = _default_ret(name)
    endpoint_sg = endpoint[:-1]  # singular
    if not id:
        log.error('Invalid {endpoint} ID'.format(endpoint=endpoint_sg))
        ret['comment'] = 'Please specify a valid {endpoint} ID'.format(endpoint=endpoint_sg)
        return ret
    if __opts__['test']:
        ret['comment'] = '{endpoint} #{id} would be updated:'.format(endpoint=endpoint_sg, id=id)
        ret['result'] = None
        ret['changes'][endpoint] = {}
        for karg, warg in six.iteritems(kwargs):
            if warg is None or karg.startswith('__'):
                continue
            ret['changes'][endpoint][karg] = warg
        return ret
    sp_update = __salt__['statuspage.update'](endpoint=endpoint,
                                              id=id,
                                              api_url=api_url,
                                              page_id=page_id,
                                              api_key=api_key,
                                              api_version=api_version,
                                              **kwargs)
    if not sp_update.get('result'):
        ret['comment'] = 'Unable to update {endpoint} #{id}: {msg}'.format(endpoint=endpoint_sg,
                                                                           id=id,
                                                                           msg=sp_update.get('comment'))
    else:
        ret['comment'] = '{endpoint} #{id} updated!'.format(endpoint=endpoint_sg, id=id)
        ret['result'] = True
        ret['changes'] = sp_update.get('out')


def delete(name,
           endpoint='incidents',
           id=None,
           api_url=None,
           page_id=None,
           api_key=None,
           api_version=None):
    '''
    Remove an entry from an endpoint.

    endpoint: incidents
        Request a specific endpoint.

    page_id
        Page ID. Can also be specified in the config file.

    api_key
        API key. Can also be specified in the config file.

    api_version: 1
        API version. Can also be specified in the config file.

    api_url
        Custom API URL in case the user has a StatusPage service running in a custom environment.

    SLS Example:

    .. code-block:: yaml

        delete-my-component:
            statuspage.delete:
                - endpoint: components
                - id: ftgks51sfs2d
    '''
    ret = _default_ret(name)
    endpoint_sg = endpoint[:-1]  # singular
    if not id:
        log.error('Invalid {endpoint} ID'.format(endpoint=endpoint_sg))
        ret['comment'] = 'Please specify a valid {endpoint} ID'.format(endpoint=endpoint_sg)
        return ret
    if __opts__['test']:
        ret['comment'] = '{endpoint} #{id} would be removed!'.format(endpoint=endpoint_sg, id=id)
        ret['result'] = None
    sp_delete = __salt__['statuspage.delete'](endpoint=endpoint,
                                              id=id,
                                              api_url=api_url,
                                              page_id=page_id,
                                              api_key=api_key,
                                              api_version=api_version)
    if not sp_delete.get('result'):
        ret['comment'] = 'Unable to delete {endpoint} #{id}: {msg}'.format(endpoint=endpoint_sg,
                                                                           id=id,
                                                                           msg=sp_delete.get('comment'))
    else:
        ret['comment'] = '{endpoint} #{id} deleted!'.format(endpoint=endpoint_sg, id=id)
        ret['result'] = True


def managed(name,
            config,
            api_url=None,
            page_id=None,
            api_key=None,
            api_version=None,
            pace=_PACE,
            allow_empty=False):
    '''
    Manage the StatusPage configuration.

    config
        Dictionary with the expected configuration of the StatusPage.
        The main level keys of this dictionary represent the endpoint name.
        If a certain endpoint does not exist in this structure, it will be ignored / not configured.

    page_id
        Page ID. Can also be specified in the config file.

    api_key
        API key. Can also be specified in the config file.

    api_version: 1
        API version. Can also be specified in the config file.

    api_url
        Custom API URL in case the user has a StatusPage service running in a custom environment.

    pace: 1
        Max requests per second allowed by the API.

    allow_empty: False
        Allow empty config.

    SLS example:

    .. code-block:: yaml

        my-statuspage-config:
            statuspage.managed:
                - config:
                    components:
                        - name: component1
                          group_id: uy4g37rf
                        - name: component2
                          group_id: 3n4uyu4gf
                    incidents:
                        - name: incident1
                          status: resolved
                          impact: major
                          backfilled: false
                        - name: incident2
                          status: investigating
                          impact: minor
    '''
    complete_diff = {}
    ret = _default_ret(name)
    if not config and not allow_empty:
        ret.update({
            'result': False,
            'comment': 'Cannot remove everything. To allow this, please set the option `allow_empty` as True.'
        })
        return ret
    is_empty = True
    for endpoint_name, endpoint_expected_config in six.iteritems(config):
        if endpoint_expected_config:
            is_empty = False
        endpoint_existing_config_ret = __salt__['statuspage.retrieve'](endpoint=endpoint_name,
                                                                       api_url=api_url,
                                                                       page_id=page_id,
                                                                       api_key=api_key,
                                                                       api_version=api_version)
        if not endpoint_existing_config_ret.get('result'):
            ret.update({
                'comment': endpoint_existing_config_ret.get('comment')
            })
            return ret  # stop at first error
        endpoint_existing_config = endpoint_existing_config_ret.get('out')
        complete_diff[endpoint_name] = _compute_diff(endpoint_expected_config, endpoint_existing_config)
    if is_empty and not allow_empty:
        ret.update({
            'result': False,
            'comment': 'Cannot remove everything. To allow this, please set the option `allow_empty` as True.'
        })
        return ret
    any_changes = False
    for endpoint_name, endpoint_diff in six.iteritems(complete_diff):
        if endpoint_diff.get('add') or endpoint_diff.get('update') or endpoint_diff.get('remove'):
            any_changes = True
    if not any_changes:
        ret.update({
            'result': True,
            'comment': 'No changes required.',
            'changes': {}
        })
        return ret
    ret.update({
        'changes': complete_diff
    })
    if __opts__.get('test'):
        ret.update({
            'comment': 'Testing mode. Would apply the following changes:',
            'result': None
        })
        return ret
    for endpoint_name, endpoint_diff in six.iteritems(complete_diff):
        endpoint_sg = endpoint_name[:-1]  # singular
        for new_endpoint in endpoint_diff.get('add'):
            log.debug('Defining new {endpoint}: {props}'.format(
                endpoint=endpoint_sg,
                props=new_endpoint
            ))
            adding = __salt__['statuspage.create'](endpoint=endpoint_name,
                                                   api_url=api_url,
                                                   page_id=page_id,
                                                   api_key=api_key,
                                                   api_version=api_version,
                                                   **new_endpoint)
            if not adding.get('result'):
                ret.update({
                    'comment': adding.get('comment')
                })
                return ret
            if pace:
                time.sleep(1/pace)
        for update_endpoint in endpoint_diff.get('update'):
            if 'id' not in update_endpoint:
                continue
            endpoint_id = update_endpoint.pop('id')
            log.debug('Updating {endpoint} #{id}: {props}'.format(
                endpoint=endpoint_sg,
                id=endpoint_id,
                props=update_endpoint
            ))
            updating = __salt__['statuspage.update'](endpoint=endpoint_name,
                                                     id=endpoint_id,
                                                     api_url=api_url,
                                                     page_id=page_id,
                                                     api_key=api_key,
                                                     api_version=api_version,
                                                     **update_endpoint)
            if not updating.get('result'):
                ret.update({
                    'comment': updating.get('comment')
                })
                return ret
            if pace:
                time.sleep(1/pace)
        for remove_endpoint in endpoint_diff.get('remove'):
            if 'id' not in remove_endpoint:
                continue
            endpoint_id = remove_endpoint.pop('id')
            log.debug('Removing {endpoint} #{id}'.format(
                endpoint=endpoint_sg,
                id=endpoint_id
            ))
            removing = __salt__['statuspage.delete'](endpoint=endpoint_name,
                                                     id=endpoint_id,
                                                     api_url=api_url,
                                                     page_id=page_id,
                                                     api_key=api_key,
                                                     api_version=api_version)
            if not removing.get('result'):
                ret.update({
                    'comment': removing.get('comment')
                })
                return ret
            if pace:
                time.sleep(1/pace)
    ret.update({
        'result': True,
        'comment': 'StatusPage updated.'
    })
    return ret
