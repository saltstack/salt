# -*- coding: utf-8 -*-
'''
Spacewalk Runner
================

.. versionadded:: 2016.3.0

Runner to interact with Spacewalk using Spacewalk API

:codeauthor: Nitin Madhok <nmadhok@clemson.edu>

To use this runner, set up the Spacewalk URL, username and password in the
master configuration at ``/etc/salt/master`` or ``/etc/salt/master.d/spacewalk.conf``:

.. code-block:: yaml

    spacewalk:
      spacewalk01.domain.com
        username: "testuser"
        password: "verybadpass"
      spacewalk02.domain.com
        username: "testuser"
        password: "verybadpass"

.. note::

    Optionally, ``protocol`` can be specified if the spacewalk server is
    not using the defaults. Default is ``protocol: https``.

'''
from __future__ import absolute_import

# Import python libs
import atexit
import logging

# Import third party libs
HAS_LIBS = False
try:
    import salt.ext.six as six
    HAS_LIBS = True
except ImportError:
    # Salt version <= 2014.7.0
    try:
        import six
        HAS_LIBS = True
    except ImportError:
        pass

log = logging.getLogger(__name__)


def __virtual__():
    '''
    Check for spacewalk configuration in master config file
    or directory and load runner only if it is specified
    '''
    if not HAS_LIBS:
        return False

    if _get_spacewalk_configuration() is False:
        return False
    return True


def _get_spacewalk_configuration(spacewalk_url=''):
    '''
    Return the configuration read from the master configuration
    file or directory
    '''
    spacewalk_config = __opts__['spacewalk'] if 'spacewalk' in __opts__ else None

    if spacewalk_config:
        try:
            for spacewalk_server, service_config in six.iteritems(spacewalk_config):
                username = service_config.get('username', None)
                password = service_config.get('password', None)
                protocol = service_config.get('protocol', 'https')

                if not username or not password:
                    log.error(
                        "Username or Password has not been specified in the master "
                        "configuration for {0}".format(spacewalk_server)
                    )
                    return False

                ret = {
                    'api_url': "{0}://{1}/rpc/api".format(protocol, spacewalk_server),
                    'username': username,
                    'password': password
                }

                if (not spacewalk_url) or (spacewalk_url == spacewalk_server):
                    return ret
        except Exception as exc:
            log.error(
                "Exception encountered: {0}".format(exc)
            )
            return False

        if spacewalk_url:
            log.error(
                "Configuration for {0} has not been specified in the master "
                "configuration".format(spacewalk_url)
            )
            return False

    return False


def _get_client_and_key(url, user, password, verbose=0):
    '''
    Return the client object and session key for the client
    '''
    session = {}
    session['client'] = six.moves.xmlrpc_client.Server(url, verbose=verbose)
    session['key'] = session['client'].auth.login(user, password)

    return session


def _disconnect_session(session):
    '''
    Disconnect API connection
    '''
    session['client'].auth.logout(session['key'])


def unregister(name, server_url):
    '''
    To unregister specified server from Spacewalk

    CLI Example:

    .. code-block:: bash

        salt-run spacewalk.unregister my-test-vm spacewalk01.domain.com
    '''
    config = _get_spacewalk_configuration(server_url)
    if not config:
        return False

    try:
        session = _get_client_and_key(config['api_url'], config['username'], config['password'])
        atexit.register(_disconnect_session, session)
    except Exception as exc:
        err_msg = "Exception raised when connecting to spacewalk server ({0}): {1}".format(server_url, exc)
        log.error(err_msg)
        return {name: err_msg}

    client = session['client']
    key = session['key']
    systems_list = client.system.getId(key, name)

    if systems_list:
        for system in systems_list:
            out = client.system.deleteSystem(key, system['id'])
            if out == 1:
                return {name: "Successfully unregistered from {0}".format(server_url)}
            else:
                return {name: "Failed to unregister from {0}".format(server_url)}
    else:
        return {name: "System does not exist in spacewalk server ({0})".format(server_url)}
