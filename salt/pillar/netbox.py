# -*- coding: utf-8 -*-
'''
A module that adds data to the Pillar structure from a NetBox API.


Configuring the NetBox ext_pillar
====================================

.. code-block:: yaml

  ext_pillar:
    - netbox:
        api_url: http://netbox_url.com/api/

The following are optional, and determine whether or not the module will
attempt to configure the ``proxy`` pillar data for use with the napalm
proxy-minion:

.. code-block:: yaml

        proxy_return: True
        proxy_username: admin
        api_token: 123abc

Create a token in your NetBox instance at
http://netbox_url.com/user/api-tokens/

By default, this module will query the NetBox API for the platform associated
with the device, and use the 'NAPALM driver' field to set the napalm
proxy-minion driver. (Currently only 'napalm' is supported for drivertype.)

This module assumes you will use SSH keys to authenticate to the network device
If password authentication is desired, it is recommended to create another
``proxy`` key in pillar_roots (or git_pillar) with just the ``passwd`` key and
use :py:func:`salt.renderers.gpg <salt.renderers.gpg>` to encrypt the value.
If any additional options for the proxy setup are needed they should also be
configured in pillar_roots.
'''


from __future__ import absolute_import, print_function, unicode_literals
import logging

try:
    import requests
    import ipaddress
    _HAS_DEPENDENCIES = True
except ImportError:
    _HAS_DEPENDENCIES = False

log = logging.getLogger(__name__)


def __virtual__():
    return _HAS_DEPENDENCIES


def ext_pillar(minion_id, pillar, *args, **kwargs):
    '''
    Query NetBox API for minion data
    '''

    # Pull settings from kwargs
    api_url = kwargs['api_url'].rstrip('/')

    api_token = kwargs.get('api_token', None)
    proxy_username = kwargs.get('proxy_username', None)
    proxy_return = kwargs.get('proxy_return', True)

    ret = {}

    headers = {}
    if api_token:
        headers['Authorization'] = 'Token ' + api_token

    # Fetch device from API
    device_results = requests.get(
        api_url + '/dcim/devices/',
        params={'name': minion_id, },
        headers=headers,
    )

    # Check status code for API call
    if device_results.status_code != requests.codes.ok:
        log.warning('API query failed for "%s", status code: %d',
                 minion_id, device_results.status_code)

    # Assign results from API call to "netbox" key
    try:
        devices = device_results.json()['results']
        if len(devices) == 1:
            ret['netbox'] = devices[0]
        elif len(devices) > 1:
            log.error('More than one device found for "%s"', minion_id)
    except Exception:
        log.error('Device not found for "%s"', minion_id)
    if proxy_return:
        # Attempt to add "proxy" key, based on platform API call
        try:
            # Fetch device from API
            platform_results = requests.get(
                ret['netbox']['platform']['url'],
                headers=headers,
            )

            # Check status code for API call
            if platform_results.status_code != requests.codes.ok:
                log.info('API query failed for "%s", status code: %d',
                         minion_id, platform_results.status_code)

            # Assign results from API call to "proxy" key if the platform has a
            # napalm_driver defined.
            napalm_driver = platform_results.json().get('napalm_driver')
            if napalm_driver:
                ret['proxy'] = {
                    'host': str(ipaddress.IPv4Interface(
                                ret['netbox']['primary_ip4']['address']).ip),
                    'driver': napalm_driver,
                    'proxytype': 'napalm',
                }

                if proxy_username:
                    ret['proxy']['username'] = proxy_username

        except Exception:
            log.debug(
                'Could not create proxy config data for "%s"', minion_id)

    return ret
