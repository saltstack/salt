# -*- coding: utf-8 -*-
'''
Check Host & Service status from Nagios via JSON RPC.

.. versionadded:: Beryllium

'''

# Import python libs
from __future__ import absolute_import
import logging

# Import Salt libs
# pylint: disable=import-error,no-name-in-module,redefined-builtin
from salt.ext.six.moves.urllib.parse import urljoin as _urljoin
import salt.ext.six.moves.http_client
# pylint: enable=import-error,no-name-in-module

# Import Third Party Libs
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


def _status_query(query, hostname, retcode=True, service=None, method='GET', **kwargs):
    '''
    Send query along to Nagios.
    '''
    data = {}
    req_params = {
        'hostname': hostname,
        'query': query,
    }

    if not retcode:
        req_params['formatoptions'] = 'enumerate'
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
        if result.status_code == salt.ext.six.moves.http_client.OK:
            data = result.json()
        elif result.status_code == salt.ext.six.moves.http_client.UNAUTHORIZED:
            log.error('Nagios authentication failed. Please check the configuration.')
        elif result.status_code == salt.ext.six.moves.http_client.NOT_FOUND:
            log.error('URL {0} for Nagios was not found.'.format(url))
        else:
            log.debug('Results: {0}'.format(result.text))
    except ConnectionError as conn_err:
        log.error('Error {0}'.format(conn_err))

    return data


def status(hostname, service=None, **kwargs):
    '''
    Check status of a particular host or particular service on it in Nagios.
    If service parameter is omitted, then check host itself. By default
    statuses are returned in a numeric format.

    Parameters:

    hostname
        The hostname to check the status of the service in Nagios.

    service
        The service to check the status of in Nagios.

    numeric
        Turn to false in order to return status in text format
        ('OK' instead of 0, 'Warning' instead of 1 etc)

    :return: status:     'OK', 'Warning', 'Critical' or 'Unknown'

    CLI Example:

    .. code-block:: bash

        salt '*' nagios_rpc.service_status hostname=webserver.domain.com
        salt '*' nagios_rpc.service_status hostname=webserver.domain.com service='HTTP'
        salt '*' nagios_rpc.service_status hostname=webserver.domain.com numeric=False
    '''

    config = _config()

    if not config['url']:
        log.error('Missing Nagios URL in the configuration')
        return False

    numeric = kwargs.get('numeric') is True
    target = service and 'service' or 'host'
    results = _status_query(target,
                            hostname,
                            retcode=numeric,
                            service=service,
                            url=config['url'],
                            username=config['username'],
                            password=config['password'])

    return results.get('data', {}).get(target, {}).get('status', not numeric and 'Unknown' or 0)
