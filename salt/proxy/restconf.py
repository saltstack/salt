'''
Proxy Minion to manage Restconf Devices

:codeauthor: Jamie (Bear) Murphy <jamiemurphyit@gmail.com>
:maturity:   new
:platform:   any

Usage
=====

.. note::

    To be able to use this module you need to enable to RESTCONF on your device 
    and having https enabled.

    Cisco Configuration example:

    .. code-block:: bash

        switch# conf t
        switch(config)# restconf
        switch(config)# ip http secure-server

.. note::

    RESTCONF requires modern OS distributions. 
    This plugin has been written specifically to use JSON Restconf endpoints

Pillar
------

The ``restconf`` proxy configuration requires the following parameters in order
to connect to the network switch:

transport: ``https``
    Specifies the type of connection transport to use. Valid values for the
    connection are ``http``, and  ``https``.

host: ``localhost``
    The IP address or DNS host name of the connection device.

username: ``admin``
    The username to pass to the device to authenticate the RESTCONF requests.

password:
    The password to pass to the device to authenticate the RESTCONF requests.

# TODO: timeout not yet implemented
# timeout: ``60``
#     Time in seconds to wait for the device to respond. Default: 60 seconds.

verify: ``True``
    Either a boolean, in which case it controls whether we verify the NX-API
    TLS certificate, or a string, in which case it must be a path to a CA bundle
    to use. Defaults to ``True``.

    When there is no certificate configuration on the device and this option is
    set as ``True`` (default), the commands will fail with the following error:
    ``SSLError: [SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed (_ssl.c:581)``.
    In this case, you either need to configure a proper certificate on the
    device (*recommended*), or bypass the checks setting this argument as ``False``
    with all the security risks considered as you may be MITM'd.

Proxy Pillar Example
--------------------

.. code-block:: yaml

    proxy:
      proxytype: restconf
      host: switch1.example.com
      username: example
      password: example
      verify: false
'''
from __future__ import absolute_import, print_function, unicode_literals

# Import python stdlib
import copy
import logging
import salt.utils.http
import json

# Import Salt modules
from salt.exceptions import SaltException


# -----------------------------------------------------------------------------
# proxy properties
# -----------------------------------------------------------------------------

__proxyenabled__ = ["restconf"]
# proxy name

# -----------------------------------------------------------------------------
# globals
# -----------------------------------------------------------------------------

__virtualname__ = 'restconf'
log = logging.getLogger(__file__)
restconf_device = {}

# -----------------------------------------------------------------------------
# property functions
# -----------------------------------------------------------------------------


def __virtual__():
    '''
    This Proxy Module is widely available as there are no external dependencies.
    '''
    log.debug("restconf proxy __virtual__() called...")
    return __virtualname__

# -----------------------------------------------------------------------------
# proxy functions
# -----------------------------------------------------------------------------


def init(opts):
    log.debug("restconf proxy init(opts) called...")
    # restconf/data/ietf-yang-library:modules-state/module
    '''
    Open the connection to the RESTCONF Device.

    As the communication is HTTP based, there is no connection to maintain,
    however, in order to test the connectivity and make sure we are able to
    bring up this Minion, we are checking the standard restconf state uri.
    '''
    proxy_dict = opts.get('proxy', {})
    conn_args = copy.deepcopy(proxy_dict)
    conn_args.pop('proxytype', None)
    opts['multiprocessing'] = conn_args.pop('multiprocessing', True)
    # This is not a SSH-based proxy, so it should be safe to enable
    # multiprocessing.
    restconf_device['conn_args'] = conn_args
    try:
        response = connection_test()
        if response[0]:
            # Execute a very simple command to confirm we are able to connect properly
            restconf_device['initialized'] = True
            restconf_device['up'] = True
            log.info('Connected to %s', conn_args['hostname'], exc_info=True)

        else:
            restconf_device['initialized'] = False
            restconf_device['up'] = False
            log.error('Unable to connect to %s', conn_args['hostname'], exc_info=True)
    except SaltException:
        log.error('Unable to connect to %s', conn_args['hostname'], exc_info=True)
        raise


def connection_test():
    log.debug("restconf proxy connection_test() called...")
    response = salt.utils.http.query(
            "https://{h}/restconf/yang-library-version".format(h=restconf_device['conn_args']['hostname']),
            method='GET',
            decode_type="json",
            decode=True,
            verify_ssl=restconf_device['conn_args']['verify'],
            username=restconf_device['conn_args']['username'],
            password=restconf_device['conn_args']['password'],
            header_list=['Accept: application/yang-data+json', 'Content-Type: application/yang-data+json']

        )
    log.debug("restconf_response: {r}".format(r=response))
    if 'ietf-restconf:yang-library-version' in str(response):
        return True, response
    else:
        return False, response


def ping():
    log.debug("restconf proxy ping() called...")
    '''
    Connection open successfully?
    '''
    return connection_test()[0]


def initialized():
    '''
    Connection finished initializing?
    '''
    return restconf_device.get('initialized', False)


def shutdown(opts):
    '''
    Closes connection with the device.
    '''
    log.debug('Shutting down the restconf Proxy Minion %s', opts['id'])

# -----------------------------------------------------------------------------
# callable functions
# -----------------------------------------------------------------------------


def request(uri, method='GET', dict_payload=None):
    if dict_payload is None:
        data = ''
    elif isinstance(dict_payload, str):
        data = dict_payload
    else:
        data = json.dumps(dict_payload)
    response = salt.utils.http.query(
            "https://{h}/{u}".format(h=restconf_device['conn_args']['hostname'], u=uri),
            method=method,
            data=data,
            decode=True,
            status=True,
            verify_ssl=restconf_device['conn_args']['verify'],
            username=restconf_device['conn_args']['username'],
            password=restconf_device['conn_args']['password'],
            header_list=['Accept: application/yang-data+json', 'Content-Type: application/yang-data+json']

        )
    log.debug("restconf_request_response: {r}".format(r=response))
    return response
