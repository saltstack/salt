# -*- coding: utf-8 -*-
'''
Module providing a simple management interface to a marathon cluster.

Currently this only works when run through a proxy minion.

.. versionadded:: 2015.8.2
'''
from __future__ import absolute_import

import json
import logging
import salt.utils
import salt.utils.http
from salt.exceptions import get_error_message


__proxyenabled__ = ['marathon']
log = logging.getLogger(__file__)


def __virtual__():
    # only valid in proxy minions for now
    return salt.utils.is_proxy() and 'proxy' in __opts__


def _base_url():
    '''
    Return the proxy configured base url.
    '''
    base_url = "http://locahost:8080"
    if 'proxy' in __opts__:
        base_url = __opts__['proxy'].get('base_url', base_url)
    return base_url


def _app_id(app_id):
    '''
    Make sure the app_id is in the correct format.
    '''
    if app_id[0] != '/':
        app_id = '/{0}'.format(app_id)
    return app_id


def apps():
    '''
    Return a list of the currently installed app ids.

    CLI Example:
    .. code-block:: bash
        salt marathon-minion-id marathon.apps
    '''
    response = salt.utils.http.query(
        "{0}/v2/apps".format(_base_url()),
        decode_type='json',
        decode=True,
    )
    return {'apps': [app['id'] for app in response['dict']['apps']]}


def has_app(id):
    '''
    Return whether the given app id is currently configured.

    CLI Example:
    .. code-block:: bash
        salt marathon-minion-id marathon.has_app my-app
    '''
    return _app_id(id) in apps()['apps']


def app(id):
    '''
    Return the current server configuration for the specified app.

    CLI Example:
    .. code-block:: bash
        salt marathon-minion-id marathon.app my-app
    '''
    response = salt.utils.http.query(
        "{0}/v2/apps/{1}".format(_base_url(), id),
        decode_type='json',
        decode=True,
    )
    return response['dict']


def update_app(id, config):
    '''
    Update the specified app with the given configuration.

    CLI Example:
    .. code-block:: bash
        salt marathon-minion-id marathon.update_app my-app '<config yaml>'
    '''
    if 'id' not in config:
        config['id'] = id
    config.pop('version', None)
    data = json.dumps(config)
    try:
        response = salt.utils.http.query(
            "{0}/v2/apps/{1}?force=true".format(_base_url(), id),
            method='PUT',
            decode_type='json',
            decode=True,
            data=data,
            header_dict={
                'Content-Type': 'application/json',
                'Accept': 'application/json',
            },
        )
        log.debug('update response: %s', response)
        return response['dict']
    except Exception as ex:
        log.error('unable to update marathon app: %s', get_error_message(ex))
        return {
            'exception': {
                'message': get_error_message(ex),
            }
        }


def rm_app(id):
    '''
    Remove the specified app from the server.

    CLI Example:
    .. code-block:: bash
        salt marathon-minion-id marathon.rm_app my-app
    '''
    response = salt.utils.http.query(
        "{0}/v2/apps/{1}".format(_base_url(), id),
        method='DELETE',
        decode_type='json',
        decode=True,
    )
    return response['dict']


def info():
    '''
    Return configuration and status information about the marathon instance.

    CLI Example:
    .. code-block:: bash
        salt marathon-minion-id marathon.info
    '''
    response = salt.utils.http.query(
        "{0}/v2/info".format(_base_url()),
        decode_type='json',
        decode=True,
    )
    return response['dict']
