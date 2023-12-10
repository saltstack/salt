"""
A module that adds data to the Pillar structure from a NetBox API.

.. versionadded:: 2019.2.0

Configuring the NetBox ext_pillar
---------------------------------

To use this pillar, you must first create a token in your NetBox instance at
http://netbox.example.com/user/api-tokens/ (substituting the hostname of your
NetBox instance)

The NetBox api_url and api_token must be set in the master
config.

For example ``/etc/salt/master.d/netbox.conf``:

.. code-block:: yaml

  ext_pillar:
    - netbox:
        api_url: http://netbox.example.com/api/
        api_token: 123abc


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

If you use more than one username for your devices, leave proxy_username unset,
and set the ``username`` key in your pillar as well. If any additional options
for the proxy setup are needed, they should also be configured in pillar_roots.

Other available configuration options:

site_details: ``True``
    Whether should retrieve details of the site the device belongs to.

site_prefixes: ``True``
    Whether should retrieve the prefixes of the site the device belongs to.

devices: ``True``
    .. versionadded:: 3004

    Whether should retrieve physical devices.

virtual_machines: ``False``
    .. versionadded:: 3004

    Whether should retrieve virtual machines.

interfaces: ``False``
    .. versionadded:: 3004

    Whether should retrieve the interfaces of the device.

interface_ips: ``False``
    .. versionadded:: 3004

    Whether should retrieve the IP addresses for interfaces of the device.
    (interfaces must be set to True as well)

api_query_result_limit: ``Use NetBox default``
    .. versionadded:: 3004

    An integer specifying how many results should be returned for each query
    to the NetBox API. Leaving this unset will use NetBox's default value.

connected_devices: ``False``
    .. versionadded:: 3006.0

    Whether connected_devices key should be populated with device objects.
    If set to True it will force `interfaces` to also be true as a dependency

Note that each option you enable can have a detrimental impact on pillar
performance, so use them with caution.

After configuring the pillar, you must restart the Salt master for the changes
to take effect.

For example:

.. code-block:: shell

  systemctl restart salt-master

To query perform a quick test of the pillar, you should refresh the pillar on
the minion with the following:

.. code-block:: shell

  salt minion1 saltutil.refresh_pillar

And then query the pillar:

.. code-block:: shell

  salt minion1 pillar.items 'netbox'

Example output:

.. code-block:: text

  minion1:
      netbox:
          ----------
          id:
              511
          url:
              https://netbox.example.com/api/dcim/devices/511/
          name:
              minion1
          node_type:
              device
          display_name:
              minion1
          device_type:
              ----------
              id:
                  4
              url:
                  https://netbox.example.com/api/dcim/device-types/4/
              manufacturer:
                  ----------
                  id:
                      1
                  url:
                      https://netbox.example.com/api/dcim/manufacturers/1/
                  name:
                      Cisco
                  slug:
                      cisco
              model:
                  ISR2901
              slug:
                  isr2901
              display_name:
                  Cisco ISR2901
          device_role:
              ----------
              id:
                  45
              url:
                  https://netbox.example.com/api/dcim/device-roles/45/
              name:
                  Network
              slug:
                  network
          interfaces:
              |_
                ----------
                id:
                    8158
                ip_addresses:
                    |_
                      ----------
                      id:
                          1146
                      url:
                          https://netbox.example.com/api/ipam/ip-addresses/1146/
                      family:
                          ----------
                          value:
                              4
                          label:
                              IPv4
                      address:
                          192.0.2.1/24
                      vrf:
                          None
                      tenant:
                          None
                      status:
                          ----------
                          value:
                              active
                           label:
                              Active
                      role:
                          None
                      nat_inside:
                          None
                      nat_outside:
                          None
                      dns_name:
                      description:
                      tags:
                      custom_fields:
                      created:
                          2021-02-19
                      last_updated:
                          2021-02-19T06:12:04.153386Z
                url:
                    https://netbox.example.com/api/dcim/interfaces/8158/
                name:
                    GigabitEthernet0/0
                label:
                type:
                    ----------
                    value:
                        1000base-t
                    label:
                        1000BASE-T (1GE)
                enabled:
                    True
                lag:
                    None
                mtu:
                    None
                mac_address:
                    None
                mgmt_only:
                    False
                description:
                mode:
                    None
                untagged_vlan:
                    None
                tagged_vlans:
                cable:
                    None
                cable_peer:
                    None
                cable_peer_type:
                    None
                connected_endpoint:
                    None
                connected_endpoint_type:
                    None
                connected_endpoint_reachable:
                    None
                tags:
                count_ipaddresses:
                    1
              |_
                ----------
                id:
                    8159
                ip_addresses:
                    |_
                      ----------
                      id:
                          1147
                      url:
                          https://netbox.example.com/api/ipam/ip-addresses/1147/
                      family:
                          ----------
                          value:
                              4
                          label:
                              IPv4
                      address:
                          198.51.100.1/24
                      vrf:
                          None
                      tenant:
                          None
                      status:
                          ----------
                          value:
                              active
                          label:
                              Active
                      role:
                          None
                      nat_inside:
                          None
                      nat_outside:
                          None
                      dns_name:
                      description:
                      tags:
                      custom_fields:
                      created:
                          2021-02-19
                      last_updated:
                          2021-02-19T06:12:40.508154Z
                      url:
                          https://netbox.example.com/api/dcim/interfaces/8159/
                      name:
                          GigabitEthernet0/1
                      label:
                      type:
                          ----------
                          value:
                              1000base-t
                          label:
                              1000BASE-T (1GE)
                      enabled:
                          True
                      lag:
                          None
                      mtu:
                          None
                      mac_address:
                          None
                      mgmt_only:
                          False
                      description:
                      mode:
                          None
                      untagged_vlan:
                          None
                      tagged_vlans:
                      cable:
                          None
                      cable_peer:
                          None
                      cable_peer_type:
                          None
                      connected_endpoint:
                          None
                      connected_endpoint_type:
                          None
                      connected_endpoint_reachable:
                          None
                      tags:
                      count_ipaddresses:
                          1
          tenant:
              None
          platform:
              ----------
              id:
                  1
              url:
                  https://netbox.example.com/api/dcim/platforms/1/
              name:
                  Cisco IOS
              slug:
                  ios
          serial:
          asset_tag:
              None
          site:
              ----------
              id:
                  18
              url:
                  https://netbox.example.com/api/dcim/sites/18/
              name:
                  Site 1
              slug:
                  site1
              status:
                  ----------
                  value:
                      active
                  label:
                      Active
              region:
                  None
              tenant:
                  None
              facility:
              asn:
                  None
              time_zone:
                  None
              description:
              physical_address:
              shipping_address:
              latitude:
                  None
              longitude:
                  None
              contact_name:
              contact_phone:
              contact_email:
              comments:
              tags:
              custom_fields:
              created:
                  2021-02-25
              last_updated:
                  2021-02-25T14:21:07.898957Z
              circuit_count:
                  0
              device_count:
                  1
              prefix_count:
                  2
              rack_count:
                  0
              virtualmachine_count:
                  1
              vlan_count:
                  0
              prefixes:
                  |_
                    ----------
                    id:
                        284
                    url:
                        https://netbox.example.com/api/ipam/prefixes/284/
                    family:
                        ----------
                        value:
                            4
                        label:
                            IPv4
                    prefix:
                        192.0.2.0/24
                    vrf:
                        None
                    tenant:
                        None
                    vlan:
                        None
                          ----------
                        value:
                            active
                        label:
                            Active
                    role:
                        None
                    is_pool:
                        False
                    description:
                    tags:
                    custom_fields:
                    created:
                        2021-02-25
                    last_updated:
                        2021-02-25T15:08:27.136305Z
                  |_
                    ----------
                    id:
                        285
                    url:
                        https://netbox.example.com/api/ipam/prefixes/285/
                    family:
                        ----------
                        value:
                            4
                        label:
                            IPv4
                    prefix:
                        198.51.100.0/24
                    vrf:
                        None
                    tenant:
                        None
                    vlan:
                        None
                    status:
                        ----------
                        value:
                            active
                        label:
                            Active
                    role:
                        None
                    is_pool:
                        False
                    description:
                    tags:
                    custom_fields:
                    created:
                        2021-02-25
                    last_updated:
                        2021-02-25T15:08:59.880440Z
          rack:
              None
          position:
              None
          face:
              None
          parent_device:
              None
          status:
              ----------
              value:
                  active
              label:
                  Active
          primary_ip:
              ----------
              id:
                  1146
              url:
                  https://netbox.example.com/api/ipam/ip-addresses/1146/
              family:
                  4
              address:
                  192.0.2.1/24
          primary_ip4:
              ----------
              id:
                  1146
              url:
                  https://netbox.example.com/api/ipam/ip-addresses/1146/
              family:
                  4
              address:
                  192.0.2.1/24
          primary_ip6:
              None
          cluster:
              None
          virtual_chassis:
              None
          vc_position:
              None
          vc_priority:
              None
          comments:
          local_context_data:
              None
          tags:
          custom_fields:
          config_context:
          connected_devices:
        ----------
        512:
            ----------
            airflow:
                None
            asset_tag:
                001
            cluster:
                None
            comments:
            config_context:
            created:
                2022-03-10T00:00:00Z
            custom_fields:
            device_role:
                ----------
                display:
                    Network switch
                id:
                    512
                name:
                    Network switch
                slug:
                    network_switch
                url:
                    https://netbox.example.com/api/dcim/device-roles/5/
            device_type:
                ----------
                display:
                    Nexus 3048
                id:
                    40
                manufacturer:
                    ----------
                    display:
                        Cisco
                    id:
                        1
                    name:
                        Cisco
                    slug:
                        cisco
                    url:
                        https://netbox.example.com/api/dcim/manufacturers/1/
                model:
                    Nexus 3048
                slug:
                    n3k-c3048tp-1ge
                url:
                    https://netbox.example.com/api/dcim/device-types/40/
            display:
                another device (001)
            face:
                ----------
                label:
                    Front
                value:
                    front
            id:
                1533
            last_updated:
                2022-08-22T13:50:15.923868Z
            local_context_data:
                None
            location:
                ----------
                _depth:
                    2
                display:
                    Location Name
                id:
                    2
                name:
                    Location Name
                slug:
                    location-name
                url:
                    https://netbox.example.com/api/dcim/locations/2
            name:
                another device
            parent_device:
                None
            platform:
                None
            position:
                18.0
            primary_ip:
                ----------
                address:
                    192.168.1.1/24
                display:
                    192.168.1.1/24
                family:
                    4
                id:
                    1234
                url:
                    https://netbox.example.com/api/ipam/ip-addresses/1234/
            primary_ip4:
                ----------
                address:
                    192.168.1.1/24
                display:
                    192.168.1.1/24
                family:
                    4
                id:
                    1234
                url:
                    https://netbox.example.com/api/ipam/ip-addresses/1234/
            primary_ip6:
                None
            rack:
                ----------
                display:
                    RackName
                id:
                    139
                name:
                    RackName
                url:
                    https://netbox.example.com/api/dcim/racks/139/
            serial:
                ABCD12345
            site:
                ----------
                display:
                    SiteName
                id:
                    2
                name:
                    SiteName
                slug:
                    sitename
                url:
                    https://netbox.example.com/api/dcim/sites/2/
            status:
                ----------
                label:
                    Active
                value:
                    active
            tags:
            tenant:
                None
            url:
                https://netbox.example.com/api/dcim/devices/1533/
            vc_position:
                None
            vc_priority:
                None
            virtual_chassis:
                None
          created:
              2021-02-19
          last_updated:
              2021-02-19T06:12:04.171105Z
"""

import logging

import salt.utils.http
import salt.utils.url
from salt._compat import ipaddress

# Set up logging
log = logging.getLogger(__name__)


def _get_devices(api_url, minion_id, headers, api_query_result_limit):
    device_url = "{api_url}/{app}/{endpoint}".format(
        api_url=api_url, app="dcim", endpoint="devices"
    )
    device_results = []
    params = {"name": minion_id}
    if api_query_result_limit:
        params["limit"] = api_query_result_limit
    device_ret = salt.utils.http.query(
        device_url, params=params, header_dict=headers, decode=True
    )
    while True:
        # Check status code for API call
        if "error" in device_ret:
            log.error(
                'API query failed for "%s", status code: %d, error %s',
                minion_id,
                device_ret["status"],
                device_ret["error"],
            )
            return []
        else:
            device_results.extend(device_ret["dict"]["results"])
        # Check if we need to paginate and fetch the next result list
        if device_ret["dict"]["next"]:
            device_ret = salt.utils.http.query(
                device_ret["dict"]["next"], header_dict=headers, decode=True
            )
        else:
            break

    # Set the node type
    device_count = 0
    for device in device_results:
        device_results[device_count]["node_type"] = "device"
        device_count += 1

    # Return the results
    return device_results


def _get_virtual_machines(api_url, minion_id, headers, api_query_result_limit):
    vm_url = "{api_url}/{app}/{endpoint}".format(
        api_url=api_url, app="virtualization", endpoint="virtual-machines"
    )
    vm_results = []
    params = {"name": minion_id}
    if api_query_result_limit:
        params["limit"] = api_query_result_limit
    vm_ret = salt.utils.http.query(
        vm_url, params=params, header_dict=headers, decode=True
    )
    while True:
        # Check status code for API call
        if "error" in vm_ret:
            log.error(
                'API query failed for "%s", status code: %d, error %s',
                minion_id,
                vm_ret["status"],
                vm_ret["error"],
            )
            return []
        else:
            vm_results.extend(vm_ret["dict"]["results"])
        # Check if we need to paginate and fetch the next result list
        if vm_ret["dict"]["next"]:
            vm_ret = salt.utils.http.query(
                vm_ret["dict"]["next"], header_dict=headers, decode=True
            )
        else:
            break

    # Set the node type
    vm_count = 0
    for vm in vm_results:
        vm_results[vm_count]["node_type"] = "virtual-machine"
        vm_count += 1

    # Return the results
    return vm_results


def _get_interfaces(
    api_url, minion_id, node_id, node_type, headers, api_query_result_limit
):
    log.debug(
        'Retrieving interfaces for "%s"',
        node_id,
    )
    interfaces_results = []
    if node_type == "device":
        app_name = "dcim"
        node_param = "device_id"
    elif node_type == "virtual-machine":
        app_name = "virtualization"
        node_param = "virtual_machine_id"
    interfaces_url = "{api_url}/{app}/{endpoint}".format(
        api_url=api_url, app=app_name, endpoint="interfaces"
    )
    params = {node_param: node_id}
    if api_query_result_limit:
        params["limit"] = api_query_result_limit
    interfaces_ret = salt.utils.http.query(
        interfaces_url,
        params=params,
        header_dict=headers,
        decode=True,
    )
    while True:
        # Check status code for API call
        if "error" in interfaces_ret:
            log.error(
                'Unable to retrieve interfaces for "%s" (Type %s, ID %d), status code: %d, error %s',
                minion_id,
                node_type,
                node_id,
                interfaces_ret["status"],
                interfaces_ret["error"],
            )
            return []
        else:
            interfaces_results.extend(interfaces_ret["dict"]["results"])
        # Check if we need to paginate and fetch the next result list
        if interfaces_ret["dict"]["next"]:
            interfaces_ret = salt.utils.http.query(
                interfaces_ret["dict"]["next"], header_dict=headers, decode=True
            )
        else:
            break

    # Clean up duplicate data in the dictionary
    interface_count = 0
    for interface in interfaces_results:
        if node_type == "device":
            del interfaces_results[interface_count]["device"]
        elif node_type == "virtual-machine":
            del interfaces_results[interface_count]["virtual_machine"]
        interface_count += 1

    # Return the results
    return interfaces_results


def _get_interface_ips(
    api_url, minion_id, node_id, node_type, headers, api_query_result_limit
):
    # We get all the IP addresses for the node at once instead of
    # having to make a separate call for each interface
    log.debug(
        'Retrieving IP addresses for "%s"',
        node_id,
    )
    interface_ips_results = []
    if node_type == "device":
        app_name = "dcim"
        node_param = "device_id"
    elif node_type == "virtual-machine":
        app_name = "virtualization"
        node_param = "virtual_machine_id"
    interface_ips_url = "{api_url}/{app}/{endpoint}".format(
        api_url=api_url, app="ipam", endpoint="ip-addresses"
    )
    params = {node_param: node_id}
    if api_query_result_limit:
        params["limit"] = api_query_result_limit
    interface_ips_ret = salt.utils.http.query(
        interface_ips_url,
        params=params,
        header_dict=headers,
        decode=True,
    )

    while True:
        # Check status code for API call
        if "error" in interface_ips_ret:
            log.error(
                'Unable to retrieve interface IP addresses for "%s" (Type %s, ID %d), status code: %d, error %s',
                minion_id,
                node_type,
                node_id,
                interface_ips_ret["status"],
                interface_ips_ret["error"],
            )
            return []
        else:
            interface_ips_results.extend(interface_ips_ret["dict"]["results"])
        # Check if we need to paginate and fetch the next result list
        if interface_ips_ret["dict"]["next"]:
            interface_ips_ret = salt.utils.http.query(
                interface_ips_ret["dict"]["next"], header_dict=headers, decode=True
            )
        else:
            break

    # Return the results
    return interface_ips_results


def _associate_ips_to_interfaces(interfaces_list, interface_ips_list):
    interface_count = 0
    for interface in interfaces_list:
        if len(interface_ips_list) > 0:
            interfaces_list[interface_count]["ip_addresses"] = []
            for ip in interface_ips_list:
                if (
                    "assigned_object_id" in ip
                    and ip["assigned_object_id"] == interface["id"]
                ):
                    del ip["assigned_object_type"]
                    del ip["assigned_object_id"]
                    del ip["assigned_object"]
                    interfaces_list[interface_count]["ip_addresses"].append(ip)
        interface_count += 1
    return interfaces_list


def _get_site_details(api_url, minion_id, site_name, site_id, headers):
    log.debug(
        'Retrieving site details for "%s" - site %s (ID %d)',
        minion_id,
        site_name,
        site_id,
    )
    site_url = "{api_url}/{app}/{endpoint}/{site_id}/".format(
        api_url=api_url, app="dcim", endpoint="sites", site_id=site_id
    )
    site_details_ret = salt.utils.http.query(site_url, header_dict=headers, decode=True)
    if "error" in site_details_ret:
        log.error(
            "Unable to retrieve site details for %s (ID %d), status code: %d, error %s",
            site_name,
            site_id,
            site_details_ret["status"],
            site_details_ret["error"],
        )
        return {}
    else:
        # Return the results
        return site_details_ret["dict"]


def _get_connected_devices(api_url, minion_id, interfaces, headers):
    log.debug('Retrieving connected devices for "%s"', minion_id)
    connected_devices_result = {}
    connected_devices_ids = []
    for int_short in interfaces:
        if "connected_endpoints" in int_short.keys():
            if int_short["connected_endpoints"]:
                for device_short in int_short["connected_endpoints"]:
                    if (
                        "device" in device_short.keys()
                        and not device_short["device"]["id"] in connected_devices_ids
                    ):
                        connected_devices_ids.append(device_short["device"]["id"])
    log.debug("connected_devices_ids: %s", connected_devices_ids)

    for dev_id in connected_devices_ids:
        device_url = "{api_url}/{app}/{endpoint}/{dev_id}".format(
            api_url=api_url, app="dcim", endpoint="devices", dev_id=dev_id
        )
        device_results = []
        device_ret = salt.utils.http.query(device_url, header_dict=headers, decode=True)
        if "error" in device_ret:
            log.error(
                'API query failed for "%s", status code: %d, error %s',
                minion_id,
                device_ret["status"],
                device_ret["error"],
            )
        else:
            connected_devices_result[dev_id] = dict(device_ret["dict"])

    return connected_devices_result


def _get_site_prefixes(
    api_url, minion_id, site_name, site_id, headers, api_query_result_limit
):
    log.debug(
        'Retrieving site prefixes for "%s" - site %s (ID %d)',
        minion_id,
        site_name,
        site_id,
    )
    site_prefixes_results = []
    prefixes_url = "{api_url}/{app}/{endpoint}".format(
        api_url=api_url, app="ipam", endpoint="prefixes"
    )
    params = {"site_id": site_id}
    if api_query_result_limit:
        params["limit"] = api_query_result_limit
    site_prefixes_ret = salt.utils.http.query(
        prefixes_url, params=params, header_dict=headers, decode=True
    )

    while True:
        # Check status code for API call
        if "error" in site_prefixes_ret:
            log.error(
                "Unable to retrieve site prefixes for %s (ID %d), status code: %d, error %s",
                site_name,
                site_id,
                site_prefixes_ret["status"],
                site_prefixes_ret["error"],
            )
            return []
        else:
            site_prefixes_results.extend(site_prefixes_ret["dict"]["results"])
        # Check if we need to paginate and fetch the next result list
        if site_prefixes_ret["dict"]["next"]:
            site_prefixes_ret = salt.utils.http.query(
                site_prefixes_ret["dict"]["next"], header_dict=headers, decode=True
            )
        else:
            break

    # Clean up duplicate data in the dictionary
    prefix_count = 0
    for prefix in site_prefixes_results:
        del site_prefixes_results[prefix_count]["site"]
        prefix_count += 1

    # Return the results
    return site_prefixes_results


def _get_proxy_details(api_url, minion_id, primary_ip, platform_id, headers):
    log.debug(
        'Retrieving proxy details for "%s"',
        minion_id,
    )
    platform_url = "{api_url}/{app}/{endpoint}/{id}/".format(
        api_url=api_url, app="dcim", endpoint="platforms", id=platform_id
    )
    platform_ret = salt.utils.http.query(platform_url, header_dict=headers, decode=True)
    # Check status code for API call
    if "error" in platform_ret:
        log.error(
            "Unable to proxy details for %s, status code: %d, error %s",
            minion_id,
            platform_ret["status"],
            platform_ret["error"],
        )
    else:
        # Assign results from API call to "proxy" key if the platform has a
        # napalm_driver defined.
        napalm_driver = platform_ret["dict"].get("napalm_driver")
        if napalm_driver:
            proxy = {
                "host": str(ipaddress.ip_interface(primary_ip).ip),
                "driver": napalm_driver,
                "proxytype": "napalm",
            }
            return proxy


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
    interface_ips = kwargs.get("interface_ips", False)
    site_details = kwargs.get("site_details", True)
    site_prefixes = kwargs.get("site_prefixes", True)
    proxy_username = kwargs.get("proxy_username", None)
    proxy_return = kwargs.get("proxy_return", True)
    connected_devices = kwargs.get("connected_devices", False)
    if connected_devices and not interfaces:
        # connected_devices logic requires interfaces to be populated
        interfaces = True
        log.debug(
            "netbox pillar interfaces set to 'True' as connected_devices is 'True'"
        )
    api_query_result_limit = kwargs.get("api_query_result_limit")

    ret = {}

    # Check that we have a valid API URL:
    if not salt.utils.url.validate(api_url, ["http", "https"]):
        log.error(
            'Provided URL for api_url "%s" is malformed or is not an http/https URL',
            api_url,
        )
        return ret

    # Check that the user has enabled at least one of the node options
    if not devices and not virtual_machines:
        log.error("At least one of devices or virtual_machines must be True")
        return ret

    # Check that the user has enabled interfaces if they've enabled interface_ips
    if interface_ips and not interfaces:
        log.error("The value for interfaces must be True if interface_ips is True")
        return ret

        # Check that the user has enabled interfaces if they've enabled interface_ips
    if api_query_result_limit and int(api_query_result_limit) <= 0:
        log.error(
            "The value for api_query_result_limit must be a postive integer if set"
        )
        return ret

    # Fetch device from API
    headers = {}
    if api_token:
        headers = {"Authorization": f"Token {api_token}"}
    else:
        log.error("The value for api_token is not set")
        return ret
    nodes = []
    if devices:
        nodes.extend(_get_devices(api_url, minion_id, headers, api_query_result_limit))
    if virtual_machines:
        nodes.extend(
            _get_virtual_machines(api_url, minion_id, headers, api_query_result_limit)
        )
    if len(nodes) == 1:
        # Return the 0th (and only) item in the list
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
        interfaces_list = _get_interfaces(
            api_url, minion_id, node_id, node_type, headers, api_query_result_limit
        )
        if len(interfaces_list) > 0 and interface_ips:
            interface_ips_list = _get_interface_ips(
                api_url, minion_id, node_id, node_type, headers, api_query_result_limit
            )
            ret["netbox"]["interfaces"] = _associate_ips_to_interfaces(
                interfaces_list, interface_ips_list
            )
    site_id = ret["netbox"]["site"]["id"]
    site_name = ret["netbox"]["site"]["name"]
    if site_details:
        ret["netbox"]["site"] = _get_site_details(
            api_url, minion_id, site_name, site_id, headers
        )
    if site_prefixes:
        ret["netbox"]["site"]["prefixes"] = _get_site_prefixes(
            api_url, minion_id, site_name, site_id, headers, api_query_result_limit
        )
    if connected_devices:
        ret["netbox"]["connected_devices"] = _get_connected_devices(
            api_url, minion_id, ret["netbox"]["interfaces"], headers
        )
    if proxy_return:
        if ret["netbox"]["platform"]:
            platform_id = ret["netbox"]["platform"]["id"]
        else:
            log.error(
                'You have set "proxy_return" to "True" but you have not set the platform in NetBox for "%s"',
                minion_id,
            )
            return
        if ret["netbox"]["primary_ip"]:
            primary_ip = ret["netbox"]["primary_ip"]["address"]
        else:
            log.error(
                'You have set "proxy_return" to "True" but you have not set the primary IPv4 or IPv6 address in NetBox for "%s"',
                minion_id,
            )
            return
        proxy = _get_proxy_details(api_url, minion_id, primary_ip, platform_id, headers)
        if proxy:
            ret["proxy"] = proxy
            if proxy_username:
                ret["proxy"]["username"] = proxy_username

    return ret
