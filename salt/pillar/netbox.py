# -*- coding: utf-8 -*-
"""
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
:py:func:`salt.renderers.gpg <salt.renderers.gpg>` to encrypt the value. If
your devices more than one username, leave proxy_username unset, and set 
the ``username`` key in your pillar as well.
If any additional options for the proxy setup are needed they should also be
configured in pillar_roots.

Other available options:

devices: ``True``
    Whether should retrieve physical devices.

virtual_machines: ``False``
    Whether should retrieve virtual machines.

site_details: ``True``
    Whether should retrieve details of the site the device belongs to.

site_prefixes: ``True``
    Whether should retrieve the prefixes of the site the device belongs to.

interfaces: ``False``
    Whether should retrieve the interfaces of the device.

interface_ips: ``False``
    Whether should retrieve the IP addresses for interfaces of the device.
    (interfaces must be set to True as well)

Note that enabling retrieval of interface and IP address information can
have a detrimental impact on pillar performance, so use with caution.
"""

from __future__ import absolute_import, print_function, unicode_literals

import logging

# Import Salt libs
import salt.utils.http
from salt._compat import ipaddress

log = logging.getLogger(__name__)


def ext_pillar(minion_id, pillar, *args, **kwargs):
    """
    Query NetBox API for minion data
    """
    if minion_id == "*":
        log.info("There's no data to collect from NetBox for the Master")
        return {}
    # Pull settings from kwargs
    api_url = kwargs["api_url"].rstrip("/")
    api_token = kwargs.get("api_token")
    devices = kwargs.get("devices", True)
    virtual_machines = kwargs.get("virtual_machines", False)
    interfaces = kwargs.get("interfaces", False)
    interface_ips = kwargs.get("interfaces", False)
    site_details = kwargs.get("site_details", True)
    site_prefixes = kwargs.get("site_prefixes", True)
    proxy_username = kwargs.get("proxy_username", None)
    proxy_return = kwargs.get("proxy_return", True)
    ret = {}

    # Fetch device from API
    headers = {}
    if api_token:
        headers = {"Authorization": "Token {}".format(api_token)}
    nodes = []
    if devices:
        device_url = "{api_url}/{app}/{endpoint}".format(
            api_url=api_url, app="dcim", endpoint="devices"
        )
        device_results = salt.utils.http.query(
            device_url, params={"name": minion_id}, header_dict=headers, decode=True
        )
        # Check status code for API call
        if "error" in device_results:
            log.error(
                'API query failed for "%s", status code: %d',
                minion_id,
                device_results["status"],
            )
            log.error(device_results["error"])
            return ret
        # Set the node type
        for device in device_results["dict"]["results"]:
            device["node_type"] = "device"
        # Assign results from API call to "netbox" key
        nodes.extend(device_results["dict"]["results"])
    if virtual_machines:
        vm_url = "{api_url}/{app}/{endpoint}".format(
            api_url=api_url, app="virtualization", endpoint="virtual-machines"
        )
        vm_results = salt.utils.http.query(
            vm_url, params={"name": minion_id}, header_dict=headers, decode=True
        )
        # Check status code for API call
        if "error" in vm_results:
            log.error(
                'API query failed for "%s", status code: %d',
                minion_id,
                vm_results["status"],
            )
            log.error(vm_results["error"])
            return ret
        # Set the node type
        for vm in vm_results["dict"]["results"]:
            vm["node_type"] = "virtual-machine"
        # Assign results from API call to "netbox" key
        nodes.extend(vm_results["dict"]["results"])
    if len(nodes) == 1:
        ret["netbox"] = nodes[0]
    elif len(nodes) > 1:
        log.error('More than one node found for "%s"', minion_id)
        return ret
    else:
        log.error('Unable to pull NetBox data for "%s"', minion_id)
        return ret
    node_id = ret["netbox"]["id"]
    node_type = ret["netbox"]["node_type"]
    if interfaces:
        log.debug(
            'Retrieving interfaces for "%s"', minion_id,
        )
        if node_type == "device":
            app_name = "dcim"
            node_param = "device_id"
        elif node_type == "virtual-machine":
            app_name = "virtualization"
            node_param = "virtual_machine_id"
        interfaces_url = "{api_url}/{app}/{endpoint}".format(
            api_url=api_url, app=app_name, endpoint="interfaces"
        )
        interfaces_ret = salt.utils.http.query(
            interfaces_url,
            params={node_param: node_id},
            header_dict=headers,
            decode=True,
        )
        if "error" in interfaces_ret:
            log.error(
                "Unable to retrieve interfaces for %s (Type %s, ID %d)",
                minion_id,
                node_type,
                node_id,
            )
            log.error(
                "Status code: %d, error: %s",
                interfaces_ret["status"],
                interfaces_ret["error"],
            )
        else:
            if interface_ips:
                # We get all the IP addresses for the node at once instead of
                # having to make a separate call for each interface
                interface_ips_url = "{api_url}/{app}/{endpoint}".format(
                    api_url=api_url, app="ipam", endpoint="ip-addresses"
                )
                interface_ips_ret = salt.utils.http.query(
                    interface_ips_url,
                    params={node_param: node_id},
                    header_dict=headers,
                    decode=True,
                )
                if "error" in interface_ips_ret:
                    log.error(
                        "Unable to interfaces IP addresses for %s (Type %s, ID %d)",
                        minion_id,
                        node_type,
                        node_id,
                    )
                    log.error(
                        "Status code: %d, error: %s",
                        interface_ips_ret["status"],
                        interface_ips_ret["error"],
                    )
            interface_count = 0
            for interface in interfaces_ret["dict"]["results"]:
                if node_type == "device":
                    del interface["device"]
                elif node_type == "virtual-machine":
                    del interface["virtual_machine"]
                if len(interface_ips_ret["dict"]["results"]) > 0:
                    interfaces_ret["dict"]["results"][interface_count][
                        "ip_addresses"
                    ] = []
                    for ip in interface_ips_ret["dict"]["results"]:
                        if (
                            "assigned_object_id" in ip
                            and ip["assigned_object_id"] == interface["id"]
                        ):
                            del ip["assigned_object_type"]
                            del ip["assigned_object_id"]
                            del ip["assigned_object"]
                            interfaces_ret["dict"]["results"][interface_count][
                                "ip_addresses"
                            ].append(ip)
                interface_count += 1
            ret["netbox"]["interfaces"] = interfaces_ret["dict"]["results"]
    site_id = ret["netbox"]["site"]["id"]
    site_name = ret["netbox"]["site"]["name"]
    if site_details:
        log.debug(
            'Retrieving site details for "%s" - site %s (ID %d)',
            minion_id,
            site_name,
            site_id,
        )
        site_url = "{api_url}/{app}/{endpoint}/{site_id}/".format(
            api_url=api_url, app="dcim", endpoint="sites", site_id=site_id
        )
        site_details_ret = salt.utils.http.query(
            site_url, header_dict=headers, decode=True
        )
        if "error" in site_details_ret:
            log.error(
                "Unable to retrieve site details for %s (ID %d)", site_name, site_id
            )
            log.error(
                "Status code: %d, error: %s",
                site_details_ret["status"],
                site_details_ret["error"],
            )
        else:
            ret["netbox"]["site"] = site_details_ret["dict"]
    if site_prefixes:
        log.debug(
            'Retrieving site prefixes for "%s" - site %s (ID %d)',
            minion_id,
            site_name,
            site_id,
        )
        prefixes_url = "{api_url}/{app}/{endpoint}".format(
            api_url=api_url, app="ipam", endpoint="prefixes"
        )
        site_prefixes_ret = salt.utils.http.query(
            prefixes_url, params={"site_id": site_id}, header_dict=headers, decode=True
        )
        if "error" in site_prefixes_ret:
            log.error(
                "Unable to retrieve site prefixes for %s (ID %d)", site_name, site_id
            )
            log.error(
                "Status code: %d, error: %s",
                site_prefixes_ret["status"],
                site_prefixes_ret["error"],
            )
        else:
            ret["netbox"]["site"]["prefixes"] = site_prefixes_ret["dict"]["results"]
    if proxy_return:
        # Attempt to add "proxy" key, based on platform API call
        try:
            # Fetch device from API
            platform_results = salt.utils.http.query(
                ret["netbox"]["platform"]["url"], header_dict=headers, decode=True
            )
            # Check status code for API call
            if "error" in platform_results:
                log.info(
                    'API query failed for "%s": %s',
                    minion_id,
                    platform_results["error"],
                )
            # Assign results from API call to "proxy" key if the platform has a
            # napalm_driver defined.
            napalm_driver = platform_results["dict"].get("napalm_driver")
            if napalm_driver:
                ret["proxy"] = {
                    "host": str(
                        ipaddress.IPv4Interface(
                            ret["netbox"]["primary_ip4"]["address"]
                        ).ip
                    ),
                    "driver": napalm_driver,
                    "proxytype": "napalm",
                }
                if proxy_username:
                    ret["proxy"]["username"] = proxy_username

        except Exception:  # pylint: disable=broad-except
            log.debug('Could not create proxy config data for "%s"', minion_id)

    return ret
