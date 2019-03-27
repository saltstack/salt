# -*- coding: utf-8 -*-
'''
Proxy Minion interface module for managing Blue Coat SSL Decryption devices

:codeauthor: Spencer Ervin <spencer_ervin@hotmail.com>
:maturity:   new
:depends:    none
:platform:   unix

This proxy minion enables Blue Coat SSL Visibility devices (hereafter referred
to as simply 'bluecoat_sslv') to be treated individually like a Salt Minion.
The bluecoat_sslv proxy leverages the JSON API functionality on the Blue Coat
SSL Visibility devices. The Salt proxy must have access to the Blue Coat device
on HTTPS (tcp/443). More in-depth conceptual reading on Proxy Minions can be
found in the :ref:`Proxy Minion <proxy-minion>` section of Salt's
documentation.

Configuration
=============

To use this integration proxy module, please configure the following:

Pillar
------

Proxy minions get their configuration from Salt's Pillar. Every proxy must
have a stanza in Pillar and a reference in the Pillar top-file that matches
the ID.

.. code-block:: yaml

    proxy:
      proxytype: bluecoat_sslv
      host: <ip or dns name of cimc host>
      username: <cimc username>
      password: <cimc password>
      auth: <authentication type>

proxytype
^^^^^^^^^

The ``proxytype`` key and value pair is critical, as it tells Salt which
interface to load from the ``proxy`` directory in Salt's install hierarchy,
or from ``/srv/salt/_proxy`` on the Salt Master (if you have created your
own proxy module, for example). To use this bluecoat_sslv Proxy Module, set this to
``bluecoat_sslv``.

host
^^^^

The location, or ip/dns, of the bluecoat_sslv host. Required.

username
^^^^^^^^

The username used to login to the bluecoat_sslv host. Required.

password
^^^^^^^^

The password used to login to the bluecoat_sslv host. Required.

auth
^^^^

The authentication type used to by the system. Use ``local`` to use the local user database. For
TACACS+ set this value to ``tacacs``.

'''

from __future__ import absolute_import, print_function, unicode_literals

# Import Python Libs
import logging
import json
import requests

# Import Salt Libs
import salt.exceptions

# This must be present or the Salt loader won't load this module.
__proxyenabled__ = ['bluecoat_sslv']

# Variables are scoped to this module so we can have persistent data.
GRAINS_CACHE = {'vendor': 'Blue Coat'}
DETAILS = {}

# Set up logging
log = logging.getLogger(__file__)

# Define the module's virtual name
__virtualname__ = 'bluecoat_sslv'


def __virtual__():
    '''
    Only return if all the modules are available.
    '''
    return __virtualname__


def _validate_response_code(response_code_to_check):
    formatted_response_code = response_code_to_check
    if formatted_response_code not in [200, 201, 202, 204]:
        log.error("Received error HTTP status code: %s", formatted_response_code)
        raise salt.exceptions.CommandExecutionError(
            "Did not receive a valid response from host.")


def init(opts):
    '''
    This function gets called when the proxy starts up.
    '''
    if 'host' not in opts['proxy']:
        log.critical('No \'host\' key found in pillar for this proxy.')
        return False
    if 'username' not in opts['proxy']:
        log.critical('No \'username\' key found in pillar for this proxy.')
        return False
    if 'password' not in opts['proxy']:
        log.critical('No \'passwords\' key found in pillar for this proxy.')
        return False
    if 'auth' not in opts['proxy']:
        log.critical('No \'auth\' key found in pillar for this proxy.')
        return False

    DETAILS['url'] = 'https://{0}/json'.format(opts['proxy']['host'])
    DETAILS['headers'] = {'Content-Type': 'application/json-rpc'}

    # Set configuration details
    DETAILS['host'] = opts['proxy']['host']
    DETAILS['username'] = opts['proxy'].get('username')
    DETAILS['password'] = opts['proxy'].get('password')
    DETAILS['auth'] = opts['proxy'].get('auth')

    # Ensure connectivity to the device
    log.debug("Attempting to connect to bluecoat_sslv proxy host.")
    session, cookies, csrf_token = logon()
    log.debug("Successfully connected to bluecoat_sslv proxy host.")
    logout(session, cookies, csrf_token)

    DETAILS['initialized'] = True


def call(payload, apply_changes=False):
    '''
    Sends a post command to the device and returns the decoded data.
    '''
    session, cookies, csrf_token = logon()
    response = _post_request(session, payload, cookies, csrf_token)
    if apply_changes:
        apply_payload = {"jsonrpc": "2.0",
                         "id": "ID1",
                         "method": "apply_policy_changes",
                         "params": []}
        _post_request(session, apply_payload, cookies, csrf_token)
    logout(session, cookies, csrf_token)
    return response


def _post_request(session, payload, cookies, csrf_token):
    response = session.post(DETAILS['url'],
                            data=json.dumps(payload),
                            cookies=cookies,
                            headers={'X-CSRF-Token': csrf_token})
    _validate_response_code(response.status_code)
    return json.loads(response.text)


def logon():
    '''
    Logs into the bluecoat_sslv device and returns the session cookies.
    '''
    session = requests.session()
    payload = {"jsonrpc": "2.0",
               "id": "ID0",
               "method": "login",
               "params": [DETAILS['username'], DETAILS['password'], DETAILS['auth'], True]
               }

    logon_response = session.post(DETAILS['url'], data=json.dumps(payload), verify=False)

    if logon_response.status_code != 200:
        log.error("Error logging into proxy. HTTP Error code: %s",
                  logon_response.status_code)
        raise salt.exceptions.CommandExecutionError(
            "Did not receive a valid response from host.")

    try:
        cookies = {'sslng_csrf_token': logon_response.cookies['sslng_csrf_token'],
                   'sslng_session_id': logon_response.cookies['sslng_session_id']}
        csrf_token = logon_response.cookies['sslng_csrf_token']
    except KeyError:
        log.error("Unable to authentication to the bluecoat_sslv proxy.")
        raise salt.exceptions.CommandExecutionError(
            "Did not receive a valid response from host.")

    return session, cookies, csrf_token


def logout(session, cookies, csrf_token):
    '''
    Closes the session with the device.
    '''
    payload = {"jsonrpc": "2.0",
               "id": "ID0",
               "method": "logout",
               "params": []
               }
    session.post(DETAILS['url'],
                 data=json.dumps(payload),
                 cookies=cookies,
                 headers={'X-CSRF-Token': csrf_token})


def initialized():
    '''
    Since grains are loaded in many different places and some of those
    places occur before the proxy can be initialized, return whether
    our init() function has been called
    '''
    return DETAILS.get('initialized', False)


def _get_grain_information():
    response = {}
    session, cookies, csrf_token = logon()

    software_payload = {"jsonrpc": "2.0",
                        "id": "ID1",
                        "method": "get_platform_information_sw_rev",
                        "params": []}
    platform_payload = {"jsonrpc": "2.0",
                        "id": "ID2",
                        "method": "get_platform_information_chassis",
                        "params": []}
    software_response = _post_request(session, software_payload, cookies, csrf_token)
    platform_response = _post_request(session, platform_payload, cookies, csrf_token)

    logout(session, cookies, csrf_token)
    try:
        for item in software_response['result']:
            response[item['key']] = item['value']
        for item in platform_response['result']:
            response[item['key']] = item['value']
    except KeyError:
        return response


def grains():
    '''
    Get the grains from the proxied device
    '''
    if not DETAILS.get('grains_cache', {}):
        DETAILS['grains_cache'] = GRAINS_CACHE
        try:
            DETAILS['grains_cache'] = _get_grain_information()
        except salt.exceptions.CommandExecutionError:
            pass
        except Exception as err:
            log.error(err)
    return DETAILS['grains_cache']


def grains_refresh():
    '''
    Refresh the grains from the proxied device
    '''
    DETAILS['grains_cache'] = None
    return grains()


def ping():
    '''
    Returns true if the device is reachable, else false.
    '''
    try:
        session, cookies, csrf_token = logon()
        logout(session, cookies, csrf_token)
    except salt.exceptions.CommandExecutionError:
        return False
    except Exception as err:
        log.debug(err)
        return False
    return True


def shutdown():
    '''
    Shutdown the connection to the proxy device. For this proxy,
    shutdown is a no-op.
    '''
    log.debug('bluecoat_sslv proxy shutdown() called.')
