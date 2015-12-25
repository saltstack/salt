# -*- coding: utf-8 -*-
'''
Wrapper around uptime API
=========================
'''

# Import Python Libs
from __future__ import absolute_import
import logging

try:
    import requests
    ENABLED = True
except ImportError:
    ENABLED = False


from salt.exceptions import CommandExecutionError

log = logging.getLogger(__name__)


def __virtual__():
    '''
    Only load this module if the requests python module is available
    '''
    if ENABLED:
        return 'uptime'
    return (False, 'uptime module needs the python requests module to work')


def create(name, **params):
    '''Create a check on a given URL.

    Additional parameters can be used and are passed to API (for
    example interval, maxTime, etc). See the documentation
    https://github.com/fzaninotto/uptime for a full list of the
    parameters.

    CLI Example:

    .. code-block:: bash

        salt '*' uptime.create http://example.org

    '''
    if check_exists(name):
        msg = 'Trying to create check that already exists : {0}'.format(name)
        log.error(msg)
        raise CommandExecutionError(msg)
    application_url = _get_application_url()
    log.debug('[uptime] trying PUT request')
    params.update(url=name)
    req = requests.put('{0}/api/checks'.format(application_url), data=params)
    if not req.ok:
        raise CommandExecutionError(
            'request to uptime failed : {0}'.format(req.reason)
        )
    log.debug('[uptime] PUT request successfull')
    return req.json()['_id']


def delete(name):
    '''
    Delete a check on a given URL

    CLI Example:

    .. code-block:: bash

        salt '*' uptime.delete http://example.org
    '''
    if not check_exists(name):
        msg = "Trying to delete check that doesn't exists : {0}".format(name)
        log.error(msg)
        raise CommandExecutionError(msg)
    application_url = _get_application_url()
    log.debug('[uptime] trying DELETE request')
    jcontent = requests.get('{0}/api/checks'.format(application_url)).json()
    url_id = [x['_id'] for x in jcontent if x['url'] == name][0]
    req = requests.delete('{0}/api/checks/{1}'.format(application_url, url_id))
    if not req.ok:
        raise CommandExecutionError(
            'request to uptime failed : {0}'.format(req.reason)
        )
    log.debug('[uptime] DELETE request successfull')
    return True


def _get_application_url():
    '''
    Helper function to get application url from pillar
    '''
    application_url = __salt__['pillar.get']('uptime:application_url')
    if application_url is None:
        log.error('Could not load {0} pillar'.format('uptime:application_url'))
        msg = '{0} pillar is required for authentication'
        raise CommandExecutionError(
            msg.format('uptime:application_url')
        )
    return application_url


def checks_list():
    '''
    List URL checked by uptime

    CLI Example:

    .. code-block:: bash

        salt '*' uptime.checks_list
    '''
    application_url = _get_application_url()
    log.debug('[uptime] get checks')
    jcontent = requests.get('{0}/api/checks'.format(application_url)).json()
    return [x['url'] for x in jcontent]


def check_exists(name):
    '''
    Check if a given URL is in being monitored by uptime

    CLI Example:

    .. code-block:: bash

        salt '*' uptime.check_exists http://example.org
    '''
    if name in checks_list():
        log.debug('[uptime] found {0} in checks'.format(name))
        return True
    return False
