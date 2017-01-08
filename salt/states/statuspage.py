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

from __future__ import absolute_import

# import python std lib
import logging

# import salt
from salt.ext import six

# ----------------------------------------------------------------------------------------------------------------------
# module properties
# ----------------------------------------------------------------------------------------------------------------------

__virtualname__ = 'statuspage'

log = logging.getLogger(__file__)

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
                                              api_version=api_version,
                                              **kwargs)
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
            api_version=None):
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
    # retrieve everything, per endpoint
    # compare
    # build out dict
    # make calls
    # return
