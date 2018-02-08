# -*- coding: utf-8 -*-
'''

Proxy Minion interface module for managing Netscaler devices.

:codeauthor: :email:`Spencer Ervin <spencer_ervin@hotmail.com>`
:maturity:   new
:depends:    none
:platform:   unix

This proxy minion enables Netscaler to be treated individually like a Salt Minion.

The netscaler proxy leverages the Nitro Rest API. The Salt proxy must have access to the Netscaler device on
HTTPS (tcp/443).

More in-depth conceptual reading on Proxy Minions can be found in the
:ref:`Proxy Minion <proxy-minion>` section of Salt's
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
      proxytype: citrxns
      host: <ip or dns name of netscaler host>
      username: <netscaler username>
      password: <netscaler password>
      useSSL: <boolean>

proxytype
^^^^^^^^^
The ``proxytype`` key and value pair is critical, as it tells Salt which
interface to load from the ``proxy`` directory in Salt's install hierarchy,
or from ``/srv/salt/_proxy`` on the Salt Master (if you have created your
own proxy module, for example). To use this netscaler Proxy Module, set this to
``citrixns``.

host
^^^^
The location, or ip/dns, of the netscaler host. Required.

username
^^^^^^^^
The username used to login to the netscaler host. Required.

password
^^^^^^^^
The password used to login to the netscaler host. Required.

useSSL
^^^^^^^^
When ``True``, instructs the proxy to connect over HTTPS. If set to ``False``, HTTP will be used. This will default to
``True`` and leverage HTTPS. Optional.

'''

from __future__ import absolute_import

# Import Python Libs
import logging
import json

# Import Salt Libs
import salt.exceptions
from salt.ext.six.moves import range

# This must be present or the Salt loader won't load this module.
__proxyenabled__ = ['citrixns']

# Variables are scoped to this module so we can have persistent data.
GRAINS_CACHE = {'vendor': 'Citrix'}
DETAILS = {}

# Set up logging
log = logging.getLogger(__file__)

# Define the module's virtual name
__virtualname__ = 'citrixns'


def __virtual__():
    '''
    Only return if all the modules are available.
    '''
    return __virtualname__


def _url_encode(value):
    '''
    Encodes a string with HTML character codes.
    '''
    codes = [[" ", "%20"],
            ["!", "%21"],
            ["/", "%2F"]]

    for c in codes:
        value = value.replace(c[0], c[1])

    return value


def init(opts):
    '''
    This function gets called when the proxy starts up. For
    netscaler devices, a determination is made on the connection type
    and the appropriate connection details that must be cached.
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

    # Set configuration details
    DETAILS['host'] = opts['proxy']['host']
    DETAILS['username'] = opts['proxy'].get('username')
    DETAILS['password'] = opts['proxy'].get('password')

    useSSL = True
    if 'useSSL' in opts['proxy']:
        if useSSL is False:
            DETAILS['url'] = 'http://{0}/nitro/v1/'.format(opts['proxy']['host'])
        else:
            DETAILS['url'] = 'https://{0}/nitro/v1/'.format(opts['proxy']['host'])
    else:
        DETAILS['url'] = 'https://{0}/nitro/v1/'.format(opts['proxy']['host'])

    DETAILS['headers'] = {'Content-Type': 'application/json'}

    # Ensure connectivity to the device
    log.debug("Attempting to connect to citrixns proxy host.")

    # We send a query to the device to ensure that a valid response is received.
    get("config/nsversion")

    log.debug("Successfully connected to citrixns proxy host.")

    DETAILS['initialized'] = True


def get(path=None):
    '''
    Sends a GET request to the Netscaler.

    Path(str): The URL path to append to the URL query. Includes the URL query as required.

    Returns: Dictionary of parsed JSON response.
    '''

    if not path:
        log.error("Citrix Netscaler POST request called without URL path.")
        raise salt.exceptions.CommandExecutionError("Citrix Netscaler POST request called without URL path.")

    try:
        r = __utils__['http.query']("{0}{1}".format(DETAILS['url'], path),
                                    username=DETAILS['username'],
                                    password=DETAILS['password'],
                                    header_dict=DETAILS['headers'],
                                    method='GET',
                                    decode_type='json',
                                    decode=True,
                                    verify_ssl=False,
                                    raise_error=True)

    except KeyError as err:
        raise salt.exceptions.CommandExecutionError("Did not receive a valid response from host.")

    if not r:
        raise salt.exceptions.CommandExecutionError("Did not receive a valid response from host.")

    if 'dict' in r:
        return r['dict']
    else:
        return None


def post(path=None, payload=None):
    '''
    Sends a POST request to the Netscaler.

    Path(str): The URL path to append to the URL query. Includes the URL query as required.

    payload(str): The payload to include in the POST request.

    Returns: True if the PUT is successful, or the error message
    '''

    if not path:
        log.error("Citrix Netscaler POST request called without URL path.")
        raise salt.exceptions.CommandExecutionError("Citrix Netscaler POST request called without URL path.")

    if not payload:
        payload = {}

    try:
        r = __utils__['http.query']("{0}{1}".format(DETAILS['url'], path),
                                    username=DETAILS['username'],
                                    password=DETAILS['password'],
                                    header_dict=DETAILS['headers'],
                                    data=json.dumps(payload),
                                    method='POST',
                                    decode_type='plain',
                                    decode=True,
                                    verify_ssl=False,
                                    raise_error=True)
    except KeyError as err:
        raise salt.exceptions.CommandExecutionError("Did not receive a valid response from host.")

    if not r:
        raise salt.exceptions.CommandExecutionError("Did not receive a valid response from host.")

    if 'status' in r:
        if r['status'] == 200:
            return True
        else:
            return r
    else:
        return True


def put(path=None, payload=None):
    '''
    Sends a PUT request to the Netscaler.

    Path(str): The URL path to append to the URL query. Includes the URL query as required.

    payload(str): The payload to include in the POST request.

    Returns: True if the PUT is successful, or the error message
    '''

    if not path:
        log.error("Citrix Netscaler PUT request called without URL path.")
        raise salt.exceptions.CommandExecutionError("Citrix Netscaler PUT request called without URL path.")

    if not payload:
        payload = {}

    try:
        r = __utils__['http.query']("{0}{1}".format(DETAILS['url'], path),
                                    username=DETAILS['username'],
                                    password=DETAILS['password'],
                                    header_dict=DETAILS['headers'],
                                    data=json.dumps(payload),
                                    method='PUT',
                                    decode_type='plain',
                                    decode=True,
                                    verify_ssl=False,
                                    raise_error=True)
    except KeyError as err:
        raise salt.exceptions.CommandExecutionError("Did not receive a valid response from host.")

    if not r:
        raise salt.exceptions.CommandExecutionError("Did not receive a valid response from host.")

    if 'status' in r:
        if r['status'] == 200:
            return True
        else:
            return r
    else:
        return True


def build_filter(filter_pairs):
    '''
    Receives a list of filter options, URL encodes, and builds the filter string.

    filter_pairs(list(str)): Key and value pairs to build the filter string.
    '''
    if not isinstance(filter_pairs, list):
        return ""

    try:
        if len(filter_pairs) == 0:
            return ""

        response = "?filter="

        for i in range(0, len(filter_pairs)):
            entry = filter_pairs[i]
            response = "{0}{1}:{2}".format(response, _url_encode(entry[0]), _url_encode(entry[1]))

            if i < (len(filter_pairs) - 1):
                response = "{0},".format(response)

        return response

    except Exception as err:
        return ""


def parse_return(response, key):
    '''
    Validate dictionary responses from device.
    '''
    try:
        if response['errorcode'] != 0:
            return response['message']
        else:
            if key in response:
                return response[key]
            else:
                return None
    except Exception as err:
        return None


def initialized():
    '''
    Since grains are loaded in many different places and some of those
    places occur before the proxy can be initialized, return whether
    our init() function has been called
    '''
    return DETAILS.get('initialized', False)


def grains():
    '''
    Get the grains from the proxied device
    '''
    if not DETAILS.get('grains_cache', {}):
        DETAILS['grains_cache'] = GRAINS_CACHE
        try:
            DETAILS['grains_cache']['citrixns'] = {}

            nsconfig = get("config/nsconfig")
            nshardware = get("config/nshardware")

            DETAILS['grains_cache']['citrixns']['version'] = get("config/nsversion")['nsversion']['version']
            DETAILS['grains_cache']['citrixns']['hostname'] = get("config/nshostname")['nshostname'][0]['hostname']

            DETAILS['grains_cache']['citrixns']['ipaddress'] = nsconfig['nsconfig']['ipaddress']
            DETAILS['grains_cache']['citrixns']['netmask'] = nsconfig['nsconfig']['netmask']
            DETAILS['grains_cache']['citrixns']['systemtype'] = nsconfig['nsconfig']['systemtype']
            DETAILS['grains_cache']['citrixns']['primaryip'] = nsconfig['nsconfig']['primaryip']
            DETAILS['grains_cache']['citrixns']['timezone'] = nsconfig['nsconfig']['timezone']
            DETAILS['grains_cache']['citrixns']['lastconfigchangedtime'] = nsconfig['nsconfig']['lastconfigchangedtime']

            DETAILS['grains_cache']['citrixns']['nshardware'] = nshardware['nshardware']['hwdescription']
            DETAILS['grains_cache']['citrixns']['serial'] = nshardware['nshardware']['serialno']

        except Exception as err:
            pass
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
        get("config/nsversion")
        return True
    except Exception as err:
        return False


def shutdown():
    '''
    Shutdown the connection to the proxy device. For this proxy,
    shutdown is a no-op.
    '''
    log.debug('Citrix Netscaler proxy shutdown() called.')
