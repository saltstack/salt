# -*- coding: utf-8 -*-
'''
Module for sending data to OpsGenie

.. versionadded:: 2018.3.0

:configuration: This module can be used in Reactor System for
    posting data to OpsGenie as a remote-execution function.

    For example:

    .. code-block:: yaml

        opsgenie_event_poster:
          local.opsgenie.post_data:
            - tgt: 'salt-minion'
            - kwarg:
                name: event.reactor
                api_key: XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXXX
                reason: {{ data['data']['reason'] }}
                action_type: Create
'''
# Import Python libs
from __future__ import absolute_import, print_function, unicode_literals
import logging
import requests

# Import Salt libs
import salt.exceptions
import salt.utils.json

API_ENDPOINT = "https://api.opsgenie.com/v1/json/saltstack?apiKey="

log = logging.getLogger(__name__)


def post_data(api_key=None, name='OpsGenie Execution Module', reason=None,
              action_type=None):
    '''
    Post data to OpsGenie. It's designed for Salt's Event Reactor.

    After configuring the sls reaction file as shown above, you can trigger the
    module with your designated tag (og-tag in this case).

    CLI Example:

    .. code-block:: bash

        salt-call event.send 'og-tag' '{"reason" : "Overheating CPU!"}'

    Required parameters:

    api_key
        It's the API Key you've copied while adding integration in OpsGenie.

    reason
        It will be used as alert's default message in OpsGenie.

    action_type
        OpsGenie supports the default values Create/Close for action_type. You
        can customize this field with OpsGenie's custom actions for other
        purposes like adding notes or acknowledging alerts.

    Optional parameters:

    name
        It will be used as alert's alias. If you want to use the close
        functionality you must provide name field for both states like in
        this case.
    '''
    if api_key is None or reason is None or action_type is None:
        raise salt.exceptions.SaltInvocationError(
            'API Key or Reason or Action Type cannot be None.')

    data = dict()
    data['name'] = name
    data['reason'] = reason
    data['actionType'] = action_type
    data['cpuModel'] = __grains__['cpu_model']
    data['cpuArch'] = __grains__['cpuarch']
    data['fqdn'] = __grains__['fqdn']
    data['host'] = __grains__['host']
    data['id'] = __grains__['id']
    data['kernel'] = __grains__['kernel']
    data['kernelRelease'] = __grains__['kernelrelease']
    data['master'] = __grains__['master']
    data['os'] = __grains__['os']
    data['saltPath'] = __grains__['saltpath']
    data['saltVersion'] = __grains__['saltversion']
    data['username'] = __grains__['username']
    data['uuid'] = __grains__['uuid']

    log.debug('Below data will be posted:\n%s', data)
    log.debug('API Key: %s \t API Endpoint: %s', api_key, API_ENDPOINT)

    response = requests.post(
        url=API_ENDPOINT + api_key,
        data=salt.utils.json.dumps(data),
        headers={'Content-Type': 'application/json'})
    return response.status_code, response.text
