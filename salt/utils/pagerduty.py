# -*- coding: utf-8 -*-
'''
Library for interacting with PagerDuty API

.. versionadded:: 2014.7.0

:configuration: This module can be used by specifying the name of a
    configuration profile in the minion config, minion pillar, or master
    config.

    For example:

    .. code-block:: yaml

        my-pagerduty-account:
            pagerduty.subdomain: mysubdomain
            pagerduty.api_key: F3Rbyjbve43rfFWf2214
'''

import json
import requests
import logging
from salt.version import __version__

log = logging.getLogger(__name__)


def query(method='GET', profile=None, url=None, path='api/v1',
          action=None, api_key=None, service=None, params=None,
          data=None, subdomain=None, client_url=None, description=None,
          opts=None, verify_ssl=True):
    '''
    Query the PagerDuty API
    '''
    user_agent = 'SaltStack {0}'.format(__version__)

    if opts is None:
        opts = {}

    if profile is not None:
        creds = opts.get(profile)
    else:
        creds = {}

    if api_key is not None:
        creds['pagerduty.api_key'] = api_key

    if service is not None:
        creds['pagerduty.service'] = service

    if subdomain is not None:
        creds['pagerduty.subdomain'] = subdomain

    if client_url is None:
        client_url = 'https://{0}.pagerduty.com'.format(
            creds['pagerduty.subdomain']
        )

    if url is None:
        url = 'https://{0}.pagerduty.com/{1}/{2}'.format(
            creds['pagerduty.subdomain'],
            path,
            action
        )

    if params is None:
        params = {}

    if data is None:
        data = {}

    data['client'] = user_agent
    data['service_key'] = creds['pagerduty.service']
    data['client_url'] = client_url
    if 'event_type' not in data:
        data['event_type'] = 'trigger'
    if 'description' not in data:
        if not description:
            data['description'] = 'SaltStack Event Triggered'
        else:
            data['description'] = description

    headers = {
        'User-Agent': user_agent,
        'Authorization': 'Token token={0}'.format(creds['pagerduty.api_key'])
    }
    if method == 'GET':
        data = {}
    else:
        headers['Content-type'] = 'application/json'

    result = requests.request(
        method,
        url,
        headers=headers,
        params=params,
        data=json.dumps(data),
        verify=verify_ssl
    )

    return result.text


def list_items(action, key, profile=None, api_key=None, opts=None):
    '''
    List items belonging to an API call. Used for list_services() and
    list_incidents()
    '''
    items = json.loads(query(
        profile=profile,
        api_key=api_key,
        action=action,
        opts=opts
    ))
    ret = {}
    for item in items[action]:
        ret[item[key]] = item
    return ret
