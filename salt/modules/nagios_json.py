# -*- coding: utf-8 -*-
'''
Check Host & Service status from Nagios via JSON.
'''

# Import python libs
from __future__ import absolute_import
import logging
import requests

# Import 3rd-party libs
from requests.exceptions import ConnectionError
# pylint: disable=import-error,no-name-in-module,redefined-builtin
from salt.ext.six.moves.urllib.parse import urljoin as _urljoin
# pylint: enable=import-error,no-name-in-module

log = logging.getLogger(__name__)


def __virtual__():
    '''
    Only load if nagios-plugins are installed
    '''
    return 'nagios_json'


def _config():
    '''
    Get configuration items for URL, Username and Password
    '''
    nagios_url = __salt__['config.get']('nagios_json:nagios_url', '')
    nagios_username = __salt__['config.get']('nagios_json:nagios_username', '')
    nagios_password = __salt__['config.get']('nagios_json:nagios_password', '')

    config = {
        'nagios_url': nagios_url,
        'nagios_username': nagios_username,
        'nagios_password': nagios_password,
    }
    return config


def _status_query(query, method='GET', **kwargs):
    '''
    Send query along to Nagios
    '''
    headers = {}
    parameters = {}
    data = {}

    nagios_url = kwargs.get('nagios_url')
    nagios_username = kwargs.get('nagios_username')
    nagios_password = kwargs.get('nagios_password')

    query_params = {
        'service': [
            'hostname',
            'servicedescription',
        ],
        'host': [
            'hostname',
        ],
    }
    parameters['query'] = query
    for param in query_params[query]:
        parameters[param] = kwargs[param]

    if not nagios_url.endswith('/'):
        nagios_url = nagios_url + '/'

    if 'cgi-bin' in nagios_url:
        url = _urljoin(nagios_url, 'statusjson.cgi')
    else:
        url = _urljoin(nagios_url, 'cgi-bin/statusjson.cgi')

    try:
        if nagios_username and nagios_password:
            result = requests.request(
                method=method,
                url=url,
                headers=headers,
                params=parameters,
                data=data,
                verify=True,
                auth=(nagios_username, nagios_password)
            )
        else:
            result = requests.request(
                method=method,
                url=url,
                headers=headers,
                params=parameters,
                data=data,
                verify=True,
            )
        if result.status_code == 200:
            data = result.json()
        elif result.status_code == 401:
            log.info('Authentication failed. Check nagios_username and nagios_password.')
        elif result.status_code == 404:
            log.info('Url {0} not found.'.format(url))
        else:
            log.info('Results: {0}'.format(result.text))
    except ConnectionError as _error:
        log.info('Error {0}'.format(_error))
    return data


def service_status(hostname, service_description):
    '''
    Check the status in Nagios for a particular
    service on a particular host
    '''

    config = _config()

    if not config['nagios_url']:
        log.error('Missing nagios_url')
        return False

    results = _status_query(query='service',
                            nagios_url=config['nagios_url'],
                            nagios_username=config['nagios_username'],
                            nagios_password=config['nagios_password'],
                            hostname=hostname,
                            servicedescription=service_description)

    data = results.get('data', '')
    if data:
        status = data.get('service', '').get('status', '')
        if status and status == 0:
            return False
        elif status and status > 0:
            return True
        else:
            return False
    else:
        return False


def host_status(hostname):
    '''
    Check the status in Nagios for a particular host
    '''

    config = _config()

    if not config['nagios_url']:
        log.error('Missing nagios_url')
        return False

    results = _status_query(query='host',
                            nagios_url=config['nagios_url'],
                            nagios_username=config['nagios_username'],
                            nagios_password=config['nagios_password'],
                            hostname=hostname)

    data = results.get('data', '')
    if data:
        status = data.get('host', '').get('status', '')
        if status and status == 0:
            return False
        elif status and status > 0:
            return True
        else:
            return False
    else:
        return False
