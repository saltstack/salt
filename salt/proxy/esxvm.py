# -*- coding: utf-8 -*-
'''
TODO Add and review comments

'''

# Import Python Libs
from __future__ import absolute_import
import logging
import os

# Import Salt Libs
import salt.exceptions as excs
from salt.utils.dictupdate import merge

# This must be present or the Salt loader won't load this module.
__proxyenabled__ = ['esxvm']


# Variables are scoped to this module so we can have persistent data
# across calls to fns in here.
GRAINS_CACHE = {}
DETAILS = {}


# Set up logging
log = logging.getLogger(__name__)
# Define the module's virtual name
__virtualname__ = 'esxvm'


def __virtual__():
    '''
    Only load if the vsphere execution module is available.
    '''
    return __virtualname__


def init(opts):
    '''
    This function gets called when the proxy starts up. For
    login the protocol and port are cached.
    '''
    log.debug('Initting esxvm proxy module in process '
              '{}'.format(os.getpid()))
    log.debug('Validating esxvm proxy input')
    proxy_conf = merge(opts.get('proxy', {}), __pillar__.get('proxy', {}))
    log.trace('proxy_conf = {0}'.format(proxy_conf))
    # TODO json schema validation

    # Save mandatory fields in cache
    for key in ('vcenter', 'datacenter', 'mechanism'):
        DETAILS[key] = proxy_conf[key]

    # Additional validation
    if DETAILS['mechanism'] == 'userpass':
        if 'username' not in proxy_conf:
            raise excs.InvalidProxyInputError(
                'Mechanism is set to \'userpass\' , but no '
                '\'username\' key found in pillar for this proxy.')
        if not 'passwords' in proxy_conf:
            raise excs.InvalidProxyInputError(
                'Mechanism is set to \'userpass\' , but no '
                '\'passwords\' key found in pillar for this proxy.')
        for key in ('username', 'passwords'):
            DETAILS[key] = proxy_conf[key]
    else:
        if not 'domain' in proxy_conf:
            raise excs.InvalidProxyInputError(
                'Mechanism is set to \'sspi\' , but no '
                '\'domain\' key found in pillar for this proxy.')
        if not 'principal' in proxy_conf:
            raise excs.InvalidProxyInputError(
                'Mechanism is set to \'sspi\' , but no '
                '\'principal\' key found in pillar for this proxy.')
        for key in ('domain', 'principal'):
            DETAILS[key] = proxy_conf[key]

    # Save optional
    DETAILS['protocol'] = proxy_conf.get('protocol')
    DETAILS['port'] = proxy_conf.get('port')

    # Test connection
    if DETAILS['mechanism'] == 'userpass':
        # Get the correct login details
        log.debug('Retrieving credentials and testing vCenter connection for '
                  'mehchanism \'userpass\'')
        try:
            username, password = find_credentials()
            DETAILS['password'] = password
        except excs.SaltSystemExit as err:
            log.critical('Error: {0}'.format(err))
            return False
    return True


def ping():
    '''
    Returns True. 

    CLI Example:

    .. code-block:: bash

        salt esx-vm test.ping
    '''
    return True


def shutdown():
    '''
    Shutdown the connection to the proxy device. For this proxy,
    shutdown is a no-op.
    '''
    log.debug('ESX vm proxy shutdown() called...')


def find_credentials():
    '''
    Cycle through all the possible credentials and return the first one that
    works.
    '''

    # if the username and password were already found don't go through the
    # connection process again
    if 'username' in DETAILS and 'password' in DETAILS:
        return DETAILS['username'], DETAILS['password']

    passwords = __pillar__['proxy']['passwords']
    for password in passwords:
        DETAILS['password'] = password
        if not __salt__['vsphere.test_vcenter_connection']():
            # We are unable to authenticate
            continue
        # If we have data returned from above, we've successfully authenticated.
        return DETAILS['username'], password
    # We've reached the end of the list without successfully authenticating.
    raise excs.VMwareConnectionError('Cannot complete login due to '
                                     'incorrect credentials.')


def get_details():
    '''
    Function that returns the cached details
    '''
    return DETAILS

