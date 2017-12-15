# -*- coding: utf-8 -*-
'''

Proxy Minion interface module for managing Cisco Integrated Management Controller devices.

:codeauthor: :email:`Spencer Ervin <spencer_ervin@hotmail.com>`
:maturity:   new
:depends:    none
:platform:   unix

This proxy minion enables Cisco Integrated Management Controller devices (hereafter referred to
as simply 'cimc' devices to be treated individually like a Salt Minion.

The cimc proxy leverages the XML API functionality on the Cisco Integrated Management Controller.
The Salt proxy must have access to the cimc on HTTPS (tcp/443).

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
      proxytype: cimc
      host: <ip or dns name of cimc host>
      username: <cimc username>
      password: <cimc password>

proxytype
^^^^^^^^^
The ``proxytype`` key and value pair is critical, as it tells Salt which
interface to load from the ``proxy`` directory in Salt's install hierarchy,
or from ``/srv/salt/_proxy`` on the Salt Master (if you have created your
own proxy module, for example). To use this cimc Proxy Module, set this to
``cimc``.

host
^^^^
The location, or ip/dns, of the cimc host. Required.

username
^^^^^^^^
The username used to login to the cimc host. Required.

password
^^^^^^^^
The password used to login to the cimc host. Required.

'''

from __future__ import absolute_import, print_function, unicode_literals

# Import Python Libs
import logging
import re

# Import Salt Libs
import salt.exceptions
from salt._compat import ElementTree as ET

# This must be present or the Salt loader won't load this module.
__proxyenabled__ = ['cimc']

# Variables are scoped to this module so we can have persistent data.
GRAINS_CACHE = {'vendor': 'Cisco'}
DETAILS = {}

# Set up logging
log = logging.getLogger(__file__)

# Define the module's virtual name
__virtualname__ = 'cimc'


def __virtual__():
    '''
    Only return if all the modules are available.
    '''
    return __virtualname__


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

    DETAILS['url'] = 'https://{0}/nuova'.format(opts['proxy']['host'])
    DETAILS['headers'] = {'Content-Type': 'application/x-www-form-urlencoded',
                          'Content-Length': 62,
                          'USER-Agent': 'lwp-request/2.06'}

    # Set configuration details
    DETAILS['host'] = opts['proxy']['host']
    DETAILS['username'] = opts['proxy'].get('username')
    DETAILS['password'] = opts['proxy'].get('password')

    # Ensure connectivity to the device
    log.debug("Attempting to connect to cimc proxy host.")
    get_config_resolver_class("computeRackUnit")
    log.debug("Successfully connected to cimc proxy host.")

    DETAILS['initialized'] = True


def set_config_modify(dn=None, inconfig=None, hierarchical=False):
    '''
    The configConfMo method configures the specified managed object in a single subtree (for example, DN).
    '''
    ret = {}
    cookie = logon()

    # Declare if the search contains hierarchical results.
    h = "false"
    if hierarchical is True:
        h = "true"

    payload = '<configConfMo cookie="{0}" inHierarchical="{1}" dn="{2}">' \
              '<inConfig>{3}</inConfig></configConfMo>'.format(cookie, h, dn, inconfig)
    r = __utils__['http.query'](DETAILS['url'],
                                data=payload,
                                method='POST',
                                decode_type='plain',
                                decode=True,
                                verify_ssl=False,
                                raise_error=True,
                                headers=DETAILS['headers'])
    answer = re.findall(r'(<[\s\S.]*>)', r['text'])[0]
    items = ET.fromstring(answer)
    logout(cookie)
    for item in items:
        ret[item.tag] = prepare_return(item)
    return ret


def get_config_resolver_class(cid=None, hierarchical=False):
    '''
    The configResolveClass method returns requested managed object in a given class.
    '''
    ret = {}
    cookie = logon()

    # Declare if the search contains hierarchical results.
    h = "false"
    if hierarchical is True:
        h = "true"

    payload = '<configResolveClass cookie="{0}" inHierarchical="{1}" classId="{2}"/>'.format(cookie, h, cid)
    r = __utils__['http.query'](DETAILS['url'],
                                data=payload,
                                method='POST',
                                decode_type='plain',
                                decode=True,
                                verify_ssl=False,
                                raise_error=True,
                                headers=DETAILS['headers'])

    answer = re.findall(r'(<[\s\S.]*>)', r['text'])[0]
    items = ET.fromstring(answer)
    logout(cookie)
    for item in items:
        ret[item.tag] = prepare_return(item)
    return ret


def logon():
    '''
    Logs into the cimc device and returns the session cookie.
    '''
    content = {}
    payload = "<aaaLogin inName='{0}' inPassword='{1}'></aaaLogin>".format(DETAILS['username'], DETAILS['password'])
    r = __utils__['http.query'](DETAILS['url'],
                                data=payload,
                                method='POST',
                                decode_type='plain',
                                decode=True,
                                verify_ssl=False,
                                raise_error=False,
                                headers=DETAILS['headers'])
    answer = re.findall(r'(<[\s\S.]*>)', r['text'])[0]
    items = ET.fromstring(answer)
    for item in items.attrib:
        content[item] = items.attrib[item]

    if 'outCookie' not in content:
        raise salt.exceptions.CommandExecutionError("Unable to log into proxy device.")

    return content['outCookie']


def logout(cookie=None):
    '''
    Closes the session with the device.
    '''
    payload = '<aaaLogout cookie="{0}" inCookie="{0}"></aaaLogout>'.format(cookie)
    __utils__['http.query'](DETAILS['url'],
                            data=payload,
                            method='POST',
                            decode_type='plain',
                            decode=True,
                            verify_ssl=False,
                            raise_error=True,
                            headers=DETAILS['headers'])
    return


def prepare_return(x):
    '''
    Converts the etree to dict
    '''
    ret = {}
    for a in list(x):
        if a.tag not in ret:
            ret[a.tag] = []
        ret[a.tag].append(prepare_return(a))
    for a in x.attrib:
        ret[a] = x.attrib[a]
    return ret


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
            compute_rack = get_config_resolver_class('computeRackUnit', False)
            DETAILS['grains_cache'] = compute_rack['outConfigs']['computeRackUnit']
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
        cookie = logon()
        logout(cookie)
    except Exception as err:
        log.debug(err)
        return False
    return True


def shutdown():
    '''
    Shutdown the connection to the proxy device. For this proxy,
    shutdown is a no-op.
    '''
    log.debug('CIMC proxy shutdown() called.')
