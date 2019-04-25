# -*- coding: utf-8 -*-
'''
A module that adds data to the Pillar structure from a NetBox API.

.. versionadded:: 2019.2.0

Configuring the NetBox ext_pillar
---------------------------------

.. code-block:: yaml

  ext_pillar:
    - netbox:
        api_url: http://netbox_url.com/api/
        api_token: 123abc

Create a token in your NetBox instance at
http://netbox_url.com/user/api-tokens/

The following options are optional, and determine whether or not
the module will attempt to configure the ``proxy`` pillar data for
use with the napalm proxy-minion:

.. code-block:: yaml

  proxy_return: True
  proxy_username: admin

By default, this module will query the NetBox API for the platform
associated with the device, and use the 'NAPALM driver' field to
set the napalm proxy-minion driver. (Currently only 'napalm' is supported
for drivertype.)

This module currently only supports the napalm proxy minion and assumes
you will use SSH keys to authenticate to the network device.  If password
authentication is desired, it is recommended to create another ``proxy``
key in pillar_roots (or git_pillar) with just the ``passwd`` key and use
:py:func:`salt.renderers.gpg <salt.renderers.gpg>` to encrypt the value.
If any additional options for the proxy setup are needed they should also be
configured in pillar_roots.

Other available options:

site_details: ``True``
    Whether should retrieve details of the site the device belongs to.

site_prefixes: ``True``
    Whether should retrieve the prefixes of the site the device belongs to.

device_interfaces: ``False``
    Whether should retrieve the interfaces of the device.

ip_addresses: ``False``
    Whether should retrieve the IPv4/IPv6 addresses of the device.  If
    both ip_addresses and device_interfaces are enabled, addresses will be
    collated with each interface.
'''

from __future__ import absolute_import, print_function, unicode_literals
import logging

# Import Salt libs
import salt.utils.http
from salt._compat import ipaddress

log = logging.getLogger(__name__)


def ext_pillar(minion_id, pillar, *args, **kwargs):
    '''
    Query NetBox API for minion data
    '''
    if minion_id == '*':
        log.info('There\'s no data to collect from NetBox for the Master')
        return {}
    # Pull settings from kwargs
    api_url = kwargs['api_url'].rstrip('/')
    api_token = kwargs.get('api_token')
    site_details = kwargs.get('site_details', True)
    site_prefixes = kwargs.get('site_prefixes', True)
    device_interfaces = kwargs.get('device_interfaces', False)
    ip_addresses = kwargs.get('ip_addresses', False)
    proxy_username = kwargs.get('proxy_username', None)
    proxy_return = kwargs.get('proxy_return', True)
    ret = {}

    # Fetch device from API
    headers = {}
    if api_token:
        headers = {
            'Authorization': 'Token {}'.format(api_token)
        }
    device_url = '{api_url}/{app}/{endpoint}'.format(api_url=api_url,
                                                     app='dcim',
                                                     endpoint='devices')
    device_results = salt.utils.http.query(device_url,
                                           params={'name': minion_id},
                                           header_dict=headers,
                                           decode=True)
    # Check status code for API call
    if 'error' in device_results:
        log.error('API query failed for "%s", status code: %d',
                  minion_id, device_results['status'])
        log.error(device_results['error'])
        return ret
    # Assign results from API call to "netbox" key
    devices = device_results['dict']['results']
    if len(devices) == 1:
        ret['netbox'] = devices[0]
    elif len(devices) > 1:
        log.error('More than one device found for "%s"', minion_id)
        return ret
    else:
        log.error('Unable to pull NetBox data for "%s"', minion_id)
        return ret
    device_id = ret['netbox']['id']
    interfaces = {}
    if device_interfaces:
        log.debug('Retrieving interface details for "%s" device_id=%d', minion_id, device_id)
        interfaces_url = '{api_url}/{app}/{endpoint}/'
        interfaces_url = interfaces_url.format(api_url=api_url,
                                               app='dcim',
                                               endpoint='interfaces')
        while interfaces_url:
            interfaces_ret = salt.utils.http.query(interfaces_url,
                                                   params={'device_id': device_id},
                                                   header_dict=headers,
                                                   decode=True)
            if 'error' in interfaces_ret:
                log.error('API query failed for "%s", status code: %d',
                          minion_id, interfaces_ret['status'])
                log.error(interfaces_ret['error'])
                return ret
            for interface in interfaces_ret['dict']['results']:
                if ip_addresses:
                    interface['addresses'] = []
                interfaces[interface['name']] = interface
            interfaces_url = interfaces_ret['dict']['next']
        ret['netbox']['interfaces'] = interfaces
    if ip_addresses:
        log.debug('Retrieving address details for "%s" device_id=%d', minion_id, device_id)
        addresses = []  # if not gathering interfaces, addresses go here
        addresses_url = '{api_url}/{app}/{endpoint}/'
        addresses_url = addresses_url.format(api_url=api_url,
                                             app='ipam',
                                             endpoint='ip-addresses')
        while addresses_url:
            addresses_ret = salt.utils.http.query(addresses_url,
                                                  params={'device_id': device_id},
                                                  header_dict=headers,
                                                  decode=True)
            if 'error' in addresses_ret:
                log.error('API query failed for "%s", status code: %d',
                          minion_id, addresses_ret['status'])
                log.error(addresses_ret['error'])
                return ret
            for address in addresses_ret['dict']['results']:
                interface_name = address['interface']['name']
                if interface_name in interfaces:
                    if 'interface' in address:
                        del address['interface']  # remove nested repetition
                    interfaces[interface_name]['addresses'].append(address)
                else:
                    addresses.append(address)
            addresses_url = addresses_ret['dict']['next']
        ret['netbox']['addresses'] = addresses
    site_id = ret['netbox']['site']['id']
    site_name = ret['netbox']['site']['name']
    if site_details:
        log.debug('Retrieving site details for "%s" - site %s (ID %d)',
                  minion_id, site_name, site_id)
        site_url = '{api_url}/{app}/{endpoint}/{site_id}/'.format(api_url=api_url,
                                                                  app='dcim',
                                                                  endpoint='sites',
                                                                  site_id=site_id)
        site_details_ret = salt.utils.http.query(site_url,
                                                 header_dict=headers,
                                                 decode=True)
        if 'error' in site_details_ret:
            log.error('Unable to retrieve site details for %s (ID %d)',
                      site_name, site_id)
            log.error('Status code: %d, error: %s',
                      site_details_ret['status'],
                      site_details_ret['error'])
        else:
            ret['netbox']['site'] = site_details_ret['dict']
    if site_prefixes:
        log.debug('Retrieving site prefixes for "%s" - site %s (ID %d)',
                  minion_id, site_name, site_id)
        prefixes_url = '{api_url}/{app}/{endpoint}'.format(api_url=api_url,
                                                           app='ipam',
                                                           endpoint='prefixes')
        site_prefixes_ret = salt.utils.http.query(prefixes_url,
                                                  params={'site_id': site_id},
                                                  header_dict=headers,
                                                  decode=True)
        if 'error' in site_prefixes_ret:
            log.error('Unable to retrieve site prefixes for %s (ID %d)',
                      site_name, site_id)
            log.error('Status code: %d, error: %s',
                      site_prefixes_ret['status'],
                      site_prefixes_ret['error'])
        else:
            ret['netbox']['site']['prefixes'] = site_prefixes_ret['dict']['results']
    if proxy_return:
        # Attempt to add "proxy" key, based on platform API call
        try:
            # Fetch device from API
            platform_results = salt.utils.http.query(ret['netbox']['platform']['url'],
                                                     header_dict=headers,
                                                     decode=True)
            # Check status code for API call
            if 'error' in platform_results:
                log.info('API query failed for "%s": %s',
                         minion_id, platform_results['error'])
            # Assign results from API call to "proxy" key if the platform has a
            # napalm_driver defined.
            napalm_driver = platform_results['dict'].get('napalm_driver')
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
