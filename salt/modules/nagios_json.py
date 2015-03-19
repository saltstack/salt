# -*- coding: utf-8 -*-
'''
Check Host & Service status from Nagios via JSON RPC.

.. versionadded:: Beryllium

'''

# Import python libs
from __future__ import absolute_import
import logging
import httplib

# Import 3rd-party libs
# pylint: disable=import-error,no-name-in-module,redefined-builtin
from salt.ext.six.moves.urllib.parse import urljoin as _urljoin
# pylint: enable=import-error,no-name-in-module

try:
    import requests
    from requests.exceptions import ConnectionError
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False

log = logging.getLogger(__name__)


def __virtual__():
    '''
    Only load if requests is successfully imported
    '''
    if REQUESTS_AVAILABLE:
        return 'nagios_rpc'
    log.debug('Unable to initialize "nagios_rpc": library "requests" is not installed.')

    return False


def _config():
    '''
    Get configuration items for URL, Username and Password
    '''
    return {
        'url': __salt__['config.get']('nagios:url', ''),
        'username': __salt__['config.get']('nagios:username', ''),
        'password': __salt__['config.get']('nagios:password', ''),
    }


def _status_query(query, hostname, service=None, method='GET', **kwargs):
    '''
    Send query along to Nagios.
    '''
    data = {}
    req_params = {
        'hostname': hostname,
        'query': query,
    }

    if service:
        req_params['servicedescription'] = service
    url = kwargs.get('url')
    username = kwargs.get('username')
    password = kwargs.get('password')

    # Make sure "cgi-bin/statusjson.cgi" in the URL
    url = url.split("cgi-bin")[0]
    if not url.endswith('/'):
        url += '/'
    url = _urljoin(url, 'statusjson.cgi')

    try:
        if username and password:
            auth = (username, password,)
        else:
            auth = None
        result = requests.request(method=method,
                                  url=url,
                                  params=req_params,
                                  data=data,
                                  verify=True,
                                  auth=auth)
        if result.status_code == httplib.OK:
            data = result.json()
        elif result.status_code == httplib.UNAUTHORIZED:
            log.error('Nagios authentication failed. Please check the configuration.')
        elif result.status_code == httplib.NOT_FOUND:
            log.error('URL {0} for Nagios was not found.'.format(url))
        else:
            log.debug('Results: {0}'.format(result.text))
    except ConnectionError as conn_err:
        log.error('Error {0}'.format(conn_err))

    return data


def status(hostname, service=None):
    '''
    Check the status in Nagios for a particular
    service on a particular host

    :param hostname:                The hostname to check the status of the service in Nagios.
    :param service_description:     The service to check the status of in Nagios.
    :return: Boolean                True is the status is 'OK' or 'Warning', False if 'Critical'

    CLI Example:

    .. code-block:: bash

        salt '*' nagios_json.service_status hostname=webserver.domain.com service_description='HTTP'

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

    if not config['url']:
        return False


    return results.get('data', {}).get(target, {}).get('status', 0) > 0
