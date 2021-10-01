"""
NetBox
======

Module to query NetBox

:codeauthor: Zach Moody <zmoody@do.co>
:maturity:   new
:depends:    pynetbox

The following config should be in the minion config file. In order to
work with ``secrets`` you should provide a token and path to your
private key file:

.. code-block:: yaml

  netbox:
    url: <NETBOX_URL>
    token: <NETBOX_USERNAME_API_TOKEN (OPTIONAL)>
    keyfile: </PATH/TO/NETBOX/KEY (OPTIONAL)>

.. versionadded:: 2018.3.0
"""

import logging
import re

from salt.exceptions import CommandExecutionError

try:
    import pynetbox

    HAS_PYNETBOX = True
except ImportError:
    HAS_PYNETBOX = False

log = logging.getLogger(__name__)

AUTH_ENDPOINTS = ("secrets",)

__func_alias__ = {"filter_": "filter", "get_": "get"}


def __virtual__():
    """
    pynetbox must be installed.
    """
    if not HAS_PYNETBOX:
        return (
            False,
            "The netbox execution module cannot be loaded: "
            "pynetbox library is not installed.",
        )
    else:
        return True


def _config():
    config = __salt__["config.get"]("netbox")
    if not config:
        raise CommandExecutionError(
            "NetBox execution module configuration could not be found"
        )
    return config


def _nb_obj(auth_required=False):
    pynb_kwargs = {}
    pynb_kwargs["token"] = _config().get("token")
    if auth_required:
        pynb_kwargs["private_key_file"] = _config().get("keyfile")
    return pynetbox.api(_config().get("url"), **pynb_kwargs)


def _strip_url_field(input_dict):
    if "url" in input_dict.keys():
        del input_dict["url"]
    for k, v in input_dict.items():
        if isinstance(v, dict):
            _strip_url_field(v)
    return input_dict


def _dict(iterable):
    if iterable:
        return dict(iterable)
    else:
        return {}


def _add(app, endpoint, payload):
    """
    POST a payload
    """
    nb = _nb_obj(auth_required=True)
    try:
        return getattr(getattr(nb, app), endpoint).create(**payload)
    except pynetbox.RequestError as e:
        log.error("%s, %s, %s", e.req.request.headers, e.request_body, e.error)
        return False

def slugify(value):
    """'
    Slugify given value.
    Credit to Djangoproject https://docs.djangoproject.com/en/2.0/_modules/django/utils/text/#slugify
    """
    value = re.sub(r"[^\w\s-]", "", value).strip().lower()
    return re.sub(r"[-\s]+", "-", value)


def _get(app, endpoint, id=None, auth_required=False, **kwargs):
    """
    Helper function to do a GET request to Netbox.
    Returns the actual pynetbox object, which allows manipulation from other functions.
    """
    nb = _nb_obj(auth_required=auth_required)
    if id:
        item = getattr(getattr(nb, app), endpoint).get(id)
    else:
        kwargs = __utils__["args.clean_kwargs"](**kwargs)
        item = getattr(getattr(nb, app), endpoint).get(**kwargs)
    return item


def _if_name_unit(if_name):
    if_name_split = if_name.split(".")
    if len(if_name_split) == 2:
        return if_name_split
    return if_name, "0"


def filter_(app, endpoint, **kwargs):
    """
    Get a list of items from NetBox.

    app
        String of netbox app, e.g., ``dcim``, ``circuits``, ``ipam``
    endpoint
        String of app endpoint, e.g., ``sites``, ``regions``, ``devices``
    kwargs
        Optional arguments that can be used to filter.
        All filter keywords are available in Netbox,
        which can be found by surfing to the corresponding API endpoint,
        and clicking Filters. e.g., ``role=router``

    Returns a list of dictionaries

    .. code-block:: bash

        salt myminion netbox.filter dcim devices status=1 role=router
    """
    ret = []
    nb = _nb_obj(auth_required=True if app in AUTH_ENDPOINTS else False)
    nb_query = getattr(getattr(nb, app), endpoint).filter(
        **__utils__["args.clean_kwargs"](**kwargs)
    )
    if nb_query:
        ret = [_strip_url_field(dict(i)) for i in nb_query]
    return ret


def get_(app, endpoint, id=None, **kwargs):
    """
    Get a single item from NetBox.

    app
        String of netbox app, e.g., ``dcim``, ``circuits``, ``ipam``
    endpoint
        String of app endpoint, e.g., ``sites``, ``regions``, ``devices``

    Returns a single dictionary

    To get an item based on ID.

    .. code-block:: bash

        salt myminion netbox.get dcim devices id=123

    Or using named arguments that correspond with accepted filters on
    the NetBox endpoint.

    .. code-block:: bash

        salt myminion netbox.get dcim devices name=my-router
    """
    return _dict(
        _get(
            app,
            endpoint,
            id=id,
            auth_required=True if app in AUTH_ENDPOINTS else False,
            **kwargs
        )
    )


def create_manufacturer(name):
    """
    .. versionadded:: 2019.2.0

    Create a device manufacturer.

    name
        The name of the manufacturer, e.g., ``Juniper``

    CLI Example:

    .. code-block:: bash

        salt myminion netbox.create_manufacturer Juniper
    """
    nb_man = get_("dcim", "manufacturers", name=name)
    if nb_man:
        return False
    else:
        payload = {"name": name, "slug": slugify(name)}
        man = _add("dcim", "manufacturers", payload)
        if man:
            return {"dcim": {"manufacturers": payload}}
        else:
            return False


def create_device_type(model, manufacturer):
    """
    .. versionadded:: 2019.2.0

    Create a device type. If the manufacturer doesn't exist, create a new manufacturer.

    model
        String of device model, e.g., ``MX480``
    manufacturer
        String of device manufacturer, e.g., ``Juniper``

    CLI Example:

    .. code-block:: bash

        salt myminion netbox.create_device_type MX480 Juniper
    """
    nb_type = get_("dcim", "device-types", model=model)
    if nb_type:
        return False
    nb_man = get_("dcim", "manufacturers", name=manufacturer)
    new_man = None
    if not nb_man:
        new_man = create_manufacturer(manufacturer)
    payload = {"model": model, "manufacturer": nb_man["id"], "slug": slugify(model)}
    typ = _add("dcim", "device-types", payload)
    ret_dict = {"dcim": {"device-types": payload}}
    if new_man:
        ret_dict["dcim"].update(new_man["dcim"])
    if typ:
        return ret_dict
    else:
        return False


def create_device_role(role, color):
    """
    .. versionadded:: 2019.2.0

    Create a device role

    role
        String of device role, e.g., ``router``

    CLI Example:

    .. code-block:: bash

        salt myminion netbox.create_device_role router
    """
    nb_role = get_("dcim", "device-roles", name=role)
    if nb_role:
        return False
    else:
        payload = {"name": role, "slug": slugify(role), "color": color}
        role = _add("dcim", "device-roles", payload)
        if role:
            return {"dcim": {"device-roles": payload}}
        else:
            return False


def create_platform(platform):
    """
    .. versionadded:: 2019.2.0

    Create a new device platform

    platform
        String of device platform, e.g., ``junos``

    CLI Example:

    .. code-block:: bash

        salt myminion netbox.create_platform junos
    """
    nb_platform = get_("dcim", "platforms", slug=slugify(platform))
    if nb_platform:
        return False
    else:
        payload = {"name": platform, "slug": slugify(platform)}
        plat = _add("dcim", "platforms", payload)
        if plat:
            return {"dcim": {"platforms": payload}}
        else:
            return False


def create_site(site):
    """
    .. versionadded:: 2019.2.0

    Create a new device site

    site
        String of device site, e.g., ``BRU``

    CLI Example:

    .. code-block:: bash

        salt myminion netbox.create_site BRU
    """
    nb_site = get_("dcim", "sites", name=site)
    if nb_site:
        return False
    else:
        payload = {"name": site, "slug": slugify(site)}
        site = _add("dcim", "sites", payload)
        if site:
            return {"dcim": {"sites": payload}}
        else:
            return False


def create_device(name, role, model, manufacturer, site):
    """
    .. versionadded:: 2019.2.0

    Create a new device with a name, role, model, manufacturer and site.
    All these components need to be already in Netbox.

    name
        The name of the device, e.g., ``edge_router``
    role
        String of device role, e.g., ``router``
    model
        String of device model, e.g., ``MX480``
    manufacturer
        String of device manufacturer, e.g., ``Juniper``
    site
        String of device site, e.g., ``BRU``

    CLI Example:

    .. code-block:: bash

        salt myminion netbox.create_device edge_router router MX480 Juniper BRU
    """
    try:
        nb_role = get_("dcim", "device-roles", name=role)
        if not nb_role:
            return False

        nb_type = get_("dcim", "device-types", model=model)
        if not nb_type:
            return False
        nb_site = get_("dcim", "sites", name=site)
        if not nb_site:
            return False

        status = {"label": "Active", "value": 1}
    except pynetbox.RequestError as e:
        log.error("%s, %s, %s", e.req.request.headers, e.request_body, e.error)
        return False

    payload = {
        "name": name,
        "display_name": name,
        "slug": slugify(name),
        "device_type": nb_type["id"],
        "device_role": nb_role["id"],
        "site": nb_site["id"],
    }
    new_dev = _add("dcim", "devices", payload)
    if new_dev:
        return {"dcim": {"devices": payload}}
    else:
        return False


def update_device(name, **kwargs):
    """
    .. versionadded:: 2019.2.0

    Add attributes to an existing device, identified by name.

    name
        The name of the device, e.g., ``edge_router``
    kwargs
       Arguments to change in device, e.g., ``serial=JN2932930``

    CLI Example:

    .. code-block:: bash

        salt myminion netbox.update_device edge_router serial=JN2932920
    """
    kwargs = __utils__["args.clean_kwargs"](**kwargs)
    nb_device = _get("dcim", "devices", auth_required=True, name=name)
    for k, v in kwargs.items():
        setattr(nb_device, k, v)
    try:
        nb_device.save()
        return {"dcim": {"devices": kwargs}}
    except pynetbox.RequestError as e:
        log.error("%s, %s, %s", e.req.request.headers, e.request_body, e.error)
        return False


def create_inventory_item(
    device_name,
    item_name,
    manufacturer_name=None,
    serial="",
    part_id="",
    description="",
):
    """
    .. versionadded:: 2019.2.0

    Add an inventory item to an existing device.

    device_name
        The name of the device, e.g., ``edge_router``.
    item_name
        String of inventory item name, e.g., ``Transceiver``.

    manufacturer_name
        String of inventory item manufacturer, e.g., ``Fiberstore``.

    serial
        String of inventory item serial, e.g., ``FS1238931``.

    part_id
        String of inventory item part id, e.g., ``740-01234``.

    description
        String of inventory item description, e.g., ``SFP+-10G-LR``.

    CLI Example:

    .. code-block:: bash

        salt myminion netbox.create_inventory_item edge_router Transceiver part_id=740-01234
    """
    nb_device = get_("dcim", "devices", name=device_name)
    if not nb_device:
        return False
    if manufacturer_name:
        nb_man = get_("dcim", "manufacturers", name=manufacturer_name)
        if not nb_man:
            create_manufacturer(manufacturer_name)
            nb_man = get_("dcim", "manufacturers", name=manufacturer_name)
    payload = {
        "device": nb_device["id"],
        "name": item_name,
        "description": description,
        "serial": serial,
        "part_id": part_id,
        "parent": None,
    }
    if manufacturer_name:
        payload["manufacturer"] = nb_man["id"]
    done = _add("dcim", "inventory-items", payload)
    if done:
        return {"dcim": {"inventory-items": payload}}
    else:
        return done


def delete_inventory_item(item_id):
    """
    .. versionadded:: 2019.2.0

    Remove an item from a devices inventory. Identified by the netbox id

    item_id
        Integer of item to be deleted

    CLI Example:

    .. code-block:: bash

        salt myminion netbox.delete_inventory_item 1354
    """
    nb_inventory_item = _get("dcim", "inventory-items", auth_required=True, id=item_id)
    nb_inventory_item.delete()
    return {"DELETE": {"dcim": {"inventory-items": item_id}}}


def create_interface_connection(interface_a, interface_b):
    """
    .. versionadded:: 2019.2.0

    Create an interface connection between 2 interfaces

    interface_a
        Interface id for Side A
    interface_b
        Interface id for Side B

    CLI Example:

    .. code-block:: bash

        salt myminion netbox.create_interface_connection 123 456
    """
    payload = {"interface_a": interface_a, "interface_b": interface_b}
    ret = _add("dcim", "interface-connections", payload)
    if ret:
        return {"dcim": {"interface-connections": {ret["id"]: payload}}}
    else:
        return ret


def get_interfaces(device_name=None, **kwargs):
    """
    .. versionadded:: 2019.2.0

    Returns interfaces for a specific device using arbitrary netbox filters

    device_name
        The name of the device, e.g., ``edge_router``
    kwargs
        Optional arguments to be used for filtering

    CLI Example:

    .. code-block:: bash

        salt myminion netbox.get_interfaces edge_router name="et-0/0/5"

    """
    if not device_name:
        device_name = __opts__["id"]
    netbox_device = get_("dcim", "devices", name=device_name)
    return filter_("dcim", "interfaces", device_id=netbox_device["id"], **kwargs)


def openconfig_interfaces(device_name=None):
    """
    .. versionadded:: 2019.2.0

    Return a dictionary structured as standardised in the
    `openconfig-interfaces <http://ops.openconfig.net/branches/models/master/openconfig-interfaces.html>`_
    YANG model, containing physical and configuration data available in Netbox,
    e.g., IP addresses, MTU, enabled / disabled, etc.

    device_name: ``None``
        The name of the device to query the interface data for. If not provided,
        will use the Minion ID.

    CLI Example:

    .. code-block:: bash

        salt '*' netbox.openconfig_interfaces
        salt '*' netbox.openconfig_interfaces device_name=cr1.thn.lon
    """
    oc_if = {}
    interfaces = get_interfaces(device_name=device_name)
    ipaddresses = get_ipaddresses(device_name=device_name)
    for interface in interfaces:
        if_name, if_unit = _if_name_unit(interface["name"])
        if if_name not in oc_if:
            oc_if[if_name] = {
                "config": {"name": if_name},
                "subinterfaces": {"subinterface": {}},
            }
        if if_unit == "0":
            oc_if[if_name]["config"]["enabled"] = interface["enabled"]
            if interface["description"]:
                if if_name == interface["name"]:
                    # When that's a real unit 0 interface
                    # Otherwise it will inherit the description from the subif
                    oc_if[if_name]["config"]["description"] = str(
                        interface["description"]
                    )
                else:
                    subif_descr = {
                        "subinterfaces": {
                            "subinterface": {
                                if_unit: {
                                    "config": {
                                        "description": str(interface["description"])
                                    }
                                }
                            }
                        }
                    }
                    oc_if[if_name] = __utils__["dictupdate.update"](
                        oc_if[if_name], subif_descr
                    )
            if interface["mtu"]:
                oc_if[if_name]["config"]["mtu"] = int(interface["mtu"])
        else:
            oc_if[if_name]["subinterfaces"]["subinterface"][if_unit] = {
                "config": {"index": int(if_unit), "enabled": interface["enabled"]}
            }
            if interface["description"]:
                oc_if[if_name]["subinterfaces"]["subinterface"][if_unit]["config"][
                    "description"
                ] = str(interface["description"])
    for ipaddress in ipaddresses:
        ip, prefix_length = ipaddress["address"].split("/")
        if_name = ipaddress["interface"]["name"]
        if_name, if_unit = _if_name_unit(if_name)
        ipvkey = "ipv{}".format(ipaddress["family"])
        if if_unit not in oc_if[if_name]["subinterfaces"]["subinterface"]:
            oc_if[if_name]["subinterfaces"]["subinterface"][if_unit] = {
                "config": {"index": int(if_unit), "enabled": True}
            }
        if ipvkey not in oc_if[if_name]["subinterfaces"]["subinterface"][if_unit]:
            oc_if[if_name]["subinterfaces"]["subinterface"][if_unit][ipvkey] = {
                "addresses": {"address": {}}
            }
        oc_if[if_name]["subinterfaces"]["subinterface"][if_unit][ipvkey]["addresses"][
            "address"
        ][ip] = {"config": {"ip": ip, "prefix_length": int(prefix_length)}}
    return {"interfaces": {"interface": oc_if}}


def openconfig_lacp(device_name=None):
    """
    .. versionadded:: 2019.2.0

    Return a dictionary structured as standardised in the
    `openconfig-lacp <http://ops.openconfig.net/branches/models/master/openconfig-lacp.html>`_
    YANG model, with configuration data for Link Aggregation Control Protocol
    (LACP) for aggregate interfaces.

    .. note::
        The ``interval`` and ``lacp_mode`` keys have the values set as ``SLOW``
        and ``ACTIVE`` respectively, as this data is not currently available
        in Netbox, therefore defaulting to the values defined in the standard.
        See `interval <http://ops.openconfig.net/branches/models/master/docs/openconfig-lacp.html#lacp-interfaces-interface-config-interval>`_
        and `lacp-mode <http://ops.openconfig.net/branches/models/master/docs/openconfig-lacp.html#lacp-interfaces-interface-config-lacp-mode>`_
        for further details.

    device_name: ``None``
        The name of the device to query the LACP information for. If not provided,
        will use the Minion ID.

    CLI Example:

    .. code-block:: bash

        salt '*' netbox.openconfig_lacp
        salt '*' netbox.openconfig_lacp device_name=cr1.thn.lon
    """
    oc_lacp = {}
    interfaces = get_interfaces(device_name=device_name)
    for interface in interfaces:
        if not interface["lag"]:
            continue
        if_name, if_unit = _if_name_unit(interface["name"])
        parent_if = interface["lag"]["name"]
        if parent_if not in oc_lacp:
            oc_lacp[parent_if] = {
                "config": {
                    "name": parent_if,
                    "interval": "SLOW",
                    "lacp_mode": "ACTIVE",
                },
                "members": {"member": {}},
            }
        oc_lacp[parent_if]["members"]["member"][if_name] = {}
    return {"lacp": {"interfaces": {"interface": oc_lacp}}}


def create_interface(
    device_name,
    interface_name,
    mac_address=None,
    description=None,
    enabled=None,
    lag=None,
    lag_parent=None,
    form_factor=None,
):
    """
    .. versionadded:: 2019.2.0

    Attach an interface to a device. If not all arguments are provided,
    they will default to Netbox defaults.

    device_name
        The name of the device, e.g., ``edge_router``
    interface_name
        The name of the interface, e.g., ``TenGigE0/0/0/0``
    mac_address
        String of mac address, e.g., ``50:87:89:73:92:C8``
    description
        String of interface description, e.g., ``NTT``
    enabled
        String of boolean interface status, e.g., ``True``
    lag:
        Boolean of interface lag status, e.g., ``True``
    lag_parent
        String of interface lag parent name, e.g., ``ae13``
    form_factor
        Integer of form factor id, obtained through _choices API endpoint, e.g., ``200``

    CLI Example:

    .. code-block:: bash

        salt myminion netbox.create_interface edge_router ae13 description="Core uplink"
    """
    nb_device = get_("dcim", "devices", name=device_name)

    if not nb_device:
        return False
    if lag_parent:
        lag_interface = get_(
            "dcim", "interfaces", device_id=nb_device["id"], name=lag_parent
        )
        if not lag_interface:
            return False
    if not description:
        description = ""
    if not enabled:
        enabled = "false"
    # Set default form factor to 1200. This maps to SFP+ (10GE). This should be addressed by
    # the _choices endpoint.
    payload = {
        "device": nb_device["id"],
        "name": interface_name,
        "description": description,
        "enabled": enabled,
        "form_factor": 1200,
    }
    if form_factor is not None:
        payload["form_factor"] = form_factor
    if lag:
        payload["form_factor"] = 200
    if lag_parent:
        payload["lag"] = lag_interface["id"]
    if mac_address:
        payload["mac_address"] = mac_address
    nb_interface = get_(
        "dcim", "interfaces", device_id=nb_device["id"], name=interface_name
    )
    if not nb_interface:
        nb_interface = _add("dcim", "interfaces", payload)
    if nb_interface:
        return {"dcim": {"interfaces": {nb_interface["id"]: payload}}}
    else:
        return nb_interface


def update_interface(device_name, interface_name, **kwargs):
    """
    .. versionadded:: 2019.2.0

    Update an existing interface with new attributes.

    device_name
        The name of the device, e.g., ``edge_router``
    interface_name
        The name of the interface, e.g., ``ae13``
    kwargs
        Arguments to change in interface, e.g., ``mac_address=50:87:69:53:32:D0``

    CLI Example:

    .. code-block:: bash

        salt myminion netbox.update_interface edge_router ae13 mac_address=50:87:69:53:32:D0
    """
    nb_device = get_("dcim", "devices", name=device_name)
    nb_interface = _get(
        "dcim",
        "interfaces",
        auth_required=True,
        device_id=nb_device["id"],
        name=interface_name,
    )
    if not nb_device:
        return False
    if not nb_interface:
        return False
    else:
        for k, v in __utils__["args.clean_kwargs"](**kwargs).items():
            setattr(nb_interface, k, v)
        try:
            nb_interface.save()
            return {"dcim": {"interfaces": {nb_interface.id: dict(nb_interface)}}}
        except pynetbox.RequestError as e:
            log.error("%s, %s, %s", e.req.request.headers, e.request_body, e.error)
            return False


def delete_interface(device_name, interface_name):
    """
    .. versionadded:: 2019.2.0

    Delete an interface from a device.

    device_name
        The name of the device, e.g., ``edge_router``.

    interface_name
        The name of the interface, e.g., ``ae13``

    CLI Example:

    .. code-block:: bash

        salt myminion netbox.delete_interface edge_router ae13
    """
    nb_device = get_("dcim", "devices", name=device_name)
    nb_interface = _get(
        "dcim",
        "interfaces",
        auth_required=True,
        device_id=nb_device["id"],
        name=interface_name,
    )
    if nb_interface:
        nb_interface.delete()
        return {
            "DELETE": {"dcim": {"interfaces": {nb_interface.id: nb_interface.name}}}
        }
    return False


def make_interface_lag(device_name, interface_name):
    """
    .. versionadded:: 2019.2.0

    Update an interface to be a LAG.

    device_name
        The name of the device, e.g., ``edge_router``.

    interface_name
        The name of the interface, e.g., ``ae13``.

    CLI Example:

    .. code-block:: bash

        salt myminion netbox.make_interface_lag edge_router ae13
    """
    return update_interface(device_name, interface_name, form_factor=200)


def make_interface_child(device_name, interface_name, parent_name):
    """
    .. versionadded:: 2019.2.0

    Set an interface as part of a LAG.

    device_name
        The name of the device, e.g., ``edge_router``.

    interface_name
        The name of the interface to be attached to LAG, e.g., ``xe-1/0/2``.

    parent_name
        The name of the LAG interface, e.g., ``ae13``.

    CLI Example:

    .. code-block:: bash

        salt myminion netbox.make_interface_child xe-1/0/2 ae13
    """
    nb_device = get_("dcim", "devices", name=device_name)
    nb_parent = get_("dcim", "interfaces", device_id=nb_device["id"], name=parent_name)
    if nb_device and nb_parent:
        return update_interface(device_name, interface_name, lag=nb_parent["id"])
    else:
        return False


def get_ipaddresses(device_name=None, **kwargs):
    """
    .. versionadded:: 2019.2.0

    Filters for an IP address using specified filters

    device_name
        The name of the device to check for the IP address
    kwargs
        Optional arguments that can be used to filter, e.g., ``family=4``

    CLI Example:

    .. code-block:: bash

        salt myminion netbox.get_ipaddresses device_name family=4
    """
    if not device_name:
        device_name = __opts__["id"]
    netbox_device = get_("dcim", "devices", name=device_name)
    return filter_("ipam", "ip-addresses", device_id=netbox_device["id"], **kwargs)


def create_ipaddress(
        address,
        vrf=None,
        tenant=None,
        status=None,
        role=None,
        device=None,
        virtual_machine=None,
        interface=None,
        cluster=None,
        nat_inside=None,
        dns_name=None,
        description=None,
        fail_on_unassigned_address=False
    ):
    """
        .. versionadded:: 2019.2.0
        .. versionchanged:: TBD

        Create an IP Address in Netbox and assign it to a device or
        virtual machine.

        address
            IPv4 or IPv6 address (with mask)
        vrf : None
            The VRF where the address resides.
        tenant : None
            The tenant the address belongs to.
        status: None
            The status of the address. Should be one of:
            - active (Default)
            - reserved
            - deprecated
            - dhcp
            - slaac
        role : None
            The role of the address. When set, should be one of:
            - loopback
            - secondary
            - anycast
            - vip
            - vrrp
            - hsrp
            - glbp
            - carp
        device : None
            Assign the address to this device. This kwarg is mutual exclusive with
            the kwarg "virtual_machine".
        virtual_machine: None
            Assign the address to this virtual machine. this kwarg is mutual exclusive
            with the kwarg "device",
        cluster : None
            In addition to "virtual_machine" users can also supply a "cluster" to
            specificly target a single virtual machine.
        nat_inside : None
            # TODO: How to tell this in a more eloquent way.
            Specify an IP Address where the new newly created ip address acts as
            the mask in network masquarading.
        dns_name : None
            The dns name given to this IP Address.
        description : None
            A description for this IP Address
        fail_on_unassigned_address : bool
            Fail when trying to create an IP Address that is already defined but
            not yet assigned to a device or virtual machine.
            Set this option to ``False`` to overwrite the currently defined IP Address
            with arguments suplied to this execution module.
    """
    # Check if address is already defined in netbox.
    # If so:
    #   - see if it is assigned to an object -> Error
    #   - see if user wants to fail on already defined addreses -> Error
    nb_addr = _get(
        "ipam",
        "ip-addresses",
        auth_required=True,
        address=address,
        vrf=vrf,
    )
    if nb_addr:
        msg="Address {} is already defined".format(address)
        log.warning(msg)
        if nb_addr['assigned_object']:
            msg="Address {} is already assigned to a {} with id {}".format(
                address,
                nb_addr['assigned_object_type'],
                nb_addr['assigned_object_id']
            )
            log.error(msg)
            return False
        if fail_on_unassigned_address:
            log.error("fail_on_unassigned_address is set to true")
            return False

    # Fetch the specified vm or device and store it in nb_object:
    app = ""
    endpoint = ""
    search_kwargs = {}
    # check not working in both entered screnario
    if not (device or virtual_machine):
        log.error("Either device or virtual_machine must be supplied.")
        return False

    if device:
        app = "dcim"
        endpoint = "devices"
        search_kwargs['name'] = device
        search_kwargs['tenant'] = tenant
    if virtual_machine:
        app = "virtualization"
        endpoint = "virtual_machines"
        search_kwargs['name'] = virtual_machine
        search_kwargs['tenant'] = tenant
        search_kwargs['cluster'] = cluster

    nb_object = get_(app, endpoint, **search_kwargs)
    if not nb_object:
        log.error("No device or virtual_machine found.")
        return False

    # Fetch the specified interface name from nb_object and
    # store it in nb_object_iface
    search_kwargs={'name': interface}
    if device:
        search_kwargs['device_id'] = nb_object['id']
    elif virtual_machine:
        search_kwargs['virtual_machine_id'] = nb_object['id']
    nb_object_iface = get_(app, "interfaces", **search_kwargs)
    if not nb_object_iface:
        msg = "No interface {} found for {}".format(interface, nb_object['name'])
        log.error(msg)
        return False

    # Construct the configuration for the interface.
    payload = {}
    payload['address'] = address
    if vrf:
        nb_vrf = get_("ipam", "vrfs", name=vrf)
        if not nb_vrf:
            log.error('No such vrf: {}'.format(vrf))
            return False
        payload['vrf'] = nb_vrf['id']
    if tenant:
        # note "q=tenant" "name=" seems buggy in pynetbox
        nb_tenant = get_("tenancy", "tenants", q=tenant)
        if not nb_tenant:
            log.error('No such tenant: {}'.format(tenant))
            return False
        payload['tenant'] = nb_tenant['id']
    if status:
        valid_options = ['active', 'reserved', 'deprecated', 'dhcp', 'slaac']
        if status not in valid_options:
            log.error('No such status {}, choose one of {}'.format(
                status,
                valid_options
                ))
            return False
        payload['status'] = status
    if role:
        valid_options = [
            'loopback',
            'secondary',
            'anycast',
            'vip',
            'vrrp',
            'hsrp',
            'glbp',
            'carp',
        ]
        if role not in valid_options:
            log.error('No such role {}, choose one of {}'.format(role, valid_options))
            return False
        payload['role'] = role
    if nat_inside:
        nb_inside_addr = get_("ipam", "ip-addresses", address=nat_inside)
        if not nb_inside_addr:
            log.error(
                'IP address {} not found as nat inside address'.format(nat_inside)
            )
            return False
        payload['nat_inside'] = nb_inside_addr['id']
    if dns_name:
        payload['dns_name'] = dns_name
    if description:
        payload['description'] = description
    if device:
        payload['assigned_object_type'] = 'dcim.interface'
        payload['assigned_object_id'] = nb_object['id']
    if virtual_machine:
        payload['assigned_object_type'] = 'virtualization.vminterface'
        payload['assigned_object_id'] = nb_object_iface['id']

    # If we didn't found a nb_addr in the beginning of this function, create one
    if not nb_addr:
        _add("ipam","ip-addresses", payload)
    else:
        for k, v in payload.items():
            setattr(nb_addr, k, v)
        nb_addr.save()

    # Fetch the address object from netbox and return it.
    nb_addr = get_(
        "ipam",
        "ip-addresses",
        address=address,
        vrf=vrf,
    )
    return nb_addr



def delete_ipaddress(ipaddr_id):
    """
    .. versionadded:: 2019.2.0

    Delete an IP address. IP addresses in Netbox are a combination of address
    and the interface it is assigned to.

    id
        The Netbox id for the IP address.

    CLI Example:

    .. code-block:: bash

        salt myminion netbox.delete_ipaddress 9002
    """

    nb_ipaddr = _get("ipam", "ip-addresses", auth_required=True, id=ipaddr_id)
    if nb_ipaddr:
        nb_ipaddr.delete()
        return {"DELETE": {"ipam": {"ip-address": ipaddr_id}}}
    return False


def create_circuit_provider(name, asn=None):
    """
    .. versionadded:: 2019.2.0

    Create a new Netbox circuit provider

    name
        The name of the circuit provider
    asn
        The ASN of the circuit provider

    CLI Example:

    .. code-block:: bash

        salt myminion netbox.create_circuit_provider Telia 1299
    """

    nb_circuit_provider = get_("circuits", "providers", name=name)
    payload = {}
    if nb_circuit_provider:
        if nb_circuit_provider["asn"] == asn:
            return False
        else:
            log.error("Duplicate provider with different ASN: %s: %s", name, asn)
            raise CommandExecutionError(
                "Duplicate provider with different ASN: {}: {}".format(name, asn)
            )
    else:
        payload = {"name": name, "slug": slugify(name)}
        if asn:
            payload["asn"] = asn
        circuit_provider = _add("circuits", "providers", payload)
        if circuit_provider:
            return {"circuits": {"providers": {circuit_provider["id"]: payload}}}
        else:
            return circuit_provider


def get_circuit_provider(name, asn=None):
    """
    .. versionadded:: 2019.2.0

    Get a circuit provider with a given name and optional ASN.

    name
        The name of the circuit provider
    asn
        The ASN of the circuit provider

    CLI Example:

    .. code-block:: bash

        salt myminion netbox.get_circuit_provider Telia 1299
    """
    if asn:
        nb_circuit_provider = get_("circuits", "providers", asn=asn)
    else:
        nb_circuit_provider = get_("circuits", "providers", name=name)
    return nb_circuit_provider


def create_circuit_type(name):
    """
    .. versionadded:: 2019.2.0

    Create a new Netbox circuit type.

    name
        The name of the circuit type

    CLI Example:

    .. code-block:: bash

        salt myminion netbox.create_circuit_type Transit
    """
    nb_circuit_type = get_("circuits", "circuit-types", slug=slugify(name))
    if nb_circuit_type:
        return False
    else:
        payload = {"name": name, "slug": slugify(name)}
        circuit_type = _add("circuits", "circuit-types", payload)
        if circuit_type:
            return {"circuits": {"circuit-types": {circuit_type["id"]: payload}}}
        else:
            return circuit_type


def create_circuit(name, provider_id, circuit_type, description=None):
    """
    .. versionadded:: 2019.2.0

    Create a new Netbox circuit

    name
        Name of the circuit
    provider_id
        The netbox id of the circuit provider
    circuit_type
        The name of the circuit type
    asn
        The ASN of the circuit provider
    description
        The description of the circuit

    CLI Example:

    .. code-block:: bash

        salt myminion netbox.create_circuit NEW_CIRCUIT_01 Telia Transit 1299 "New Telia circuit"
    """

    nb_circuit_provider = get_("circuits", "providers", provider_id)
    nb_circuit_type = get_("circuits", "circuit-types", slug=slugify(circuit_type))
    if nb_circuit_provider and nb_circuit_type:
        payload = {
            "cid": name,
            "provider": nb_circuit_provider["id"],
            "type": nb_circuit_type["id"],
        }
        if description:
            payload["description"] = description
        nb_circuit = get_("circuits", "circuits", cid=name)
        if nb_circuit:
            return False
        circuit = _add("circuits", "circuits", payload)
        if circuit:
            return {"circuits": {"circuits": {circuit["id"]: payload}}}
        else:
            return circuit
    else:
        return False


def create_circuit_termination(
    circuit, interface, device, speed, xconnect_id=None, term_side="A"
):
    """
    .. versionadded:: 2019.2.0

    Terminate a circuit on an interface

    circuit
        The name of the circuit
    interface
        The name of the interface to terminate on
    device
        The name of the device the interface belongs to
    speed
        The speed of the circuit, in Kbps
    xconnect_id
        The cross-connect identifier
    term_side
        The side of the circuit termination

    CLI Example:

    .. code-block:: bash

        salt myminion netbox.create_circuit_termination NEW_CIRCUIT_01 xe-0/0/1 myminion 10000 xconnect_id=XCON01
    """

    nb_device = get_("dcim", "devices", name=device)
    nb_interface = get_("dcim", "interfaces", device_id=nb_device["id"], name=interface)
    nb_circuit = get_("circuits", "circuits", cid=circuit)
    if nb_circuit and nb_device:
        nb_termination = get_("circuits", "circuit-terminations", q=nb_circuit["cid"])
        if nb_termination:
            return False
        payload = {
            "circuit": nb_circuit["id"],
            "interface": nb_interface["id"],
            "site": nb_device["site"]["id"],
            "port_speed": speed,
            "term_side": term_side,
        }
        if xconnect_id:
            payload["xconnect_id"] = xconnect_id
        circuit_termination = _add("circuits", "circuit-terminations", payload)
        if circuit_termination:
            return {
                "circuits": {
                    "circuit-terminations": {circuit_termination["id"]: payload}
                }
            }
        else:
            return circuit_termination

def create_virtual_machine(
        name,
        cluster,
        status=None,
        role=None,
        tenant=None,
        platform=None,
        vcpus=None,
        memory=None,
        disk=None,
        comments=None
    ):
    """
    .. versionadded:: TBD

    Create a new device with a name, role, model, manufacturer and site.
    All these components need to be already in Netbox.

    name
        The name of the virtual_machine, e.g., ``gibson01``
    cluster
        Name of the cluster id, e.g., ``oVirt SuperCluster``
    status : None
        Status of the virtual_machine, e.g., ``staged``
        Must be one of:
            * active (Default)
            * offline
            * planned
            * staged
            * failed
            * decommissioning
    role : None
        Virtual Machine Role, e.g., ``Gibson``
    tenant : None
        Name of the tenant the virtual machine belongs to.
    platform : None
        Name of the platform running on the virtual machine, e.g., ``OS/2 Warp``
    vcpus : None
        Number of virtual cpu's assigned to the virtual machine, e.g., ``8``
    memory : None
        Amount of memory in MB assigned to the virtual machine, e.g., ``4096``
    disk : None
        Amount of disk space assigned to the virtual machine in GB, e.g., ``500``
    comments : None
        Commentary for the virtual machine, e.g., ``Located near the pool on the roof. Tell him about the pool, kate.``


    CLI Example:

    .. code-block:: bash

        salt myminion netbox.create_virtual_machine gibson01 "ovirt SuperCluster"
    """
    additional_payload = {}

    try:
        nb_cluster = get_("virtualization", "clusters", name=cluster)
        if not nb_cluster:
            return False
        valid_status_types = ['offline', 'active', 'planned', 'staged', 'failed', 'decommissioning']
        if status in valid_status_types:
            additional_payload['status'] = status
        elif status:
            log.error('Illegal status type: "{}". Allowed status types: {}'.format(status, valid_status_types))
            return False
        if role:
            nb_vm_role = get_("dcim", "device_roles", name=role)
            if not nb_vm_role:
                log.error('Could not retrieve role "{}"'.format(role))
                return False
            additional_payload['role'] = nb_vm_role['id']
        if tenant:
            nb_tenant = get_("tenancy", "tenants", name=tenant)
            if not nb_tenant:
                log.error('Could not retrieve tenant "{}"'.format(tenant))
                return False
            additional_payload['tenant'] = nb_tenant['id']
        if vcpus:
            additional_payload['vcpus'] = vcpus
        if memory:
            additional_payload['memory'] = memory
        if disk:
            additional_payload['disk'] = disk
        if comments:
            additional_payload['comments'] = comments

    except pynetbox.RequestError as e:
        log.error("%s, %s, %s", e.req.request.headers, e.request_body, e.error)
        return False

    payload = {
        "name": name,
        "display_name": name,
        "slug": slugify(name),
        "cluster": nb_cluster["id"],
    }

    payload.update(additional_payload)

    new_vm = _add("virtualization", "virtual_machines", payload)
    if new_vm:
        return {"virtualization": {"virtual_machine": payload}}
    else:
        return False

def create_virtual_machine_interface(
            name,
            vm_name,
            cluster=None,
            tenant=None,
            enabled=True,
            parent=None,
            mtu=None,
            mac_address=None,
            description=None,
            mode=None,
            untagged_vlan=None,
            tagged_vlans=None,
            ):
    """
    .. versionadded:: TBD

    Create a new interface assigned to a virtual_machine.

    name
        The name of the interface, e.g., ``eth0``
    vm_name
        Name of the virtual_machine the interface belongs to, ``gibson01``
    cluster : None
        The name of the virtualization cluster where the virtual machine resides, e.g., ``oVirt - Cluster3``
        TODO: bug in pynetbox API?: cannot filter by cluster.
    tenant : None
        The name of the tenant the virtual_machine belongs to, e.g., ``cyberdelia``
        note: This MUST be given as lowercase.
    parent: None
        The parent interface this interface belongs to, e.g., ``eth0``
    mtu : None
        MTU size of the interface. e.g., ``9000``
    mac_address : None
        The MAC Address of the interface. e.g., ``00:11:22:33:44:55``
    description : None
        A description for the interface. e.g., ``It's a privilege not a right.``
    mode : None
        The mode of the interface, when set, must be one of "access", "tagged", "tagged-all".
    untagged_vlan : None
        The untagged VLAN assigned to this interface. Specify VLAN by vlan number.
    tagged_vlans : None
        The tagged VLAN's assigned to this interface. Specify VLAN's as a list of vlan numbers.

    CLI Example:

    .. code-block:: bash

        salt myminion netbox.create_virtual_machine_interface eth0 gibson01
    """

    try:
        nb_vm = get_(
                "virtualization",
                "virtual_machines",
                name=vm_name,
                tenant=tenant,
                cluster=cluster
            )

        if not nb_vm:
            log.error('No Virtual Machine found named {} filtered by tenant {} and cluster {}'.format(vm_name, tenant, cluster))
            return False
    except pynetbox.RequestError as e:
        log.error("%s, %s, %s", e.req.request.headers, e.request_body, e.error)
        return False

    optional_payload = {}

    if mtu:
        optional_payload['mtu'] = mtu
    if description:
        optional_payload['description'] = description
    if mac_address:
        optional_payload['mac_address'] = mac_address
    if parent:
        parent_iface = get_("virtualization", "interfaces", name=parent, virtual_machine_id=nb_vm['id'])
        optional_payload['parent'] = parent_iface['id']
    if not enabled:
        optional_payload['enabled'] = False
    if mode in ['access', 'tagged', 'tagged-all']:
        optional_payload['mode'] = mode
    elif mode:
        log.error('Illegal mode, must be one of "access", tagged", "tagged-all".')
    if untagged_vlan:
        vlan = get_('ipam', 'vlans', vid=untagged_vlan )
        optional_payload['untagged_vlan'] = vlan['id']
    if tagged_vlans:
        vlan_ids = []
        for vlan in tagged_vlans:
            vlan = get_('ipam', 'vlans', vid=vlan)
            vlan_ids.append(vlan['id'])

        optional_payload['tagged_vlans'] = vlan_ids

    payload = {
        "name": name,
        "mtu": mtu,
        "virtual_machine": nb_vm['id'],
    }

    payload.update(optional_payload)

    new_vm = _add("virtualization", "interfaces", payload)
    if new_vm:
        return {"virtualization": {"interfaces": payload}}
    else:
        return False
