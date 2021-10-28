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
from pprint import pprint # debug

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


def create_manufacturer(name, description=None):
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
        if description:
            payload['description'] = description
        man = _add("dcim", "manufacturers", payload)
        if man:
            return {"dcim": {"manufacturers": payload}}
        else:
            return False

def get_manufacturer(name):
    nb_manufacturer = get_(
        "dcim",
        "manufacturers",
        name=name
    )
    return nb_manufacturer

def delete_manufacturer(name):
    nb_manufacturer = _get("dcim", "manufacturers", auth_required=True, name=name)
    if not nb_manufacturer:
        log.error("No such manufacturer {}".format(name))
        return None
    nb_manufacturer.delete()
    return {"DELETE": {"dcim": {"manufacturers": name}}}

def update_manufacturer(name, **kwargs):
    kwargs = __utils__["args.clean_kwargs"](**kwargs)
    nb_manufacturer = _get("dcim", "manufacturers", auth_required=True, name=name)
    if not nb_manufacturer:
        log.error("No such manufacturer with name {}.".format(name))
        return False

    pprint(nb_manufacturer)
    for k, v in kwargs.items():
        setattr(nb_manufacturer, k, v)

    try:
        nb_manufacturer.save()
        ret = get_manufacturer(name)
    except pynetbox.RequestError as e:
        log.error("%s, %s, %s", e.req.request.headers, e.request_body, e.error)
        return False
    return ret

def check_manufacturer(name, **kwargs):
    """
    returns: 
        - False if error
        - None if vminterface does not exist
        - {} if there are no changes
        - {'with': 'changes'} for changes
    """
    kwargs = __utils__["args.clean_kwargs"](**kwargs)

    try:
        nb_manufacturer = _get(
            "dcim",
            "manufacturers",
            name=name
        )
        if not nb_manufacturer:
            log.info('No such manufacturer: {}'.format(name))
            return None
    except pynetbox.RequestError as e:
        log.error("%s, %s, %s", e.req.request.headers, e.request_body, e.error)
        return False

    required_changes={}
    for k, v in kwargs.items():
        if v == None:
            # state module sets al available options default to None
            continue
       
        # Resolve kwargs to their ID if needed.
        # Not needed

        # Check if the attribute has an ID attribute.
        # If so, use it.
        value_from_netbox = ""
        nb_attribute = getattr(nb_manufacturer, k)
        if hasattr(nb_attribute, "id"):
            value_from_netbox = nb_attribute.id
        else:
            value_from_netbox = nb_attribute

        if v == value_from_netbox:
            print("Gelijk: {}".format(v))
        else:
            print("BOOM: {} != {}".format(v, getattr(nb_manufacturer, k)))
            required_changes[k]=v
    return required_changes

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


def create_device_role(role, color="133700", vm_role=True, description=None):
    """
    .. versionadded:: 2019.2.0

    Create a device role

    role
        String of device role, e.g., ``router``

    color:
        Color of device role, e.v., ``red``. 
        Default: ``grey``

    vm_role:
        Boolean to control wether or not device role is 
        assignable to a virtual machine.
        Default: True

    description:
        Description of device role
        Default: None

    CLI Example:

    .. code-block:: bash

        salt myminion netbox.create_device_role router
    """
    nb_role = get_("dcim", "device-roles", name=role)
    if nb_role:
        return False
    else:
        payload = {"name": role, "slug": slugify(role), "color": color, "vm_role": vm_role}
        if description:
            payload['description'] = description
        role = _add("dcim", "device-roles", payload)
        if role:
            return {"dcim": {"device-roles": payload}}
        else:
            return False

def get_device_role(name):
    nb_device_role = get_(
        "dcim",
        "device_roles",
        name=name
    )
    return nb_device_role

def delete_device_role(name):
    nb_device_role = _get("dcim", "device_roles", auth_required=True, name=name)
    if not nb_device_role:
        log.error("No such device_role {}".format(name))
        return None
    nb_device_role.delete()
    return {"DELETE": {"dcim": {"device_roles": name}}}

def update_device_role(name, **kwargs):
    kwargs = __utils__["args.clean_kwargs"](**kwargs)
    nb_device_role = _get("dcim", "device-roles", auth_required=True, name=name)
    if not nb_device_role:
        log.error("No such device_role with name {}.".format(name))
        return False

    pprint(nb_device_role)
    for k, v in kwargs.items():
        setattr(nb_device_role, k, v)

    try:
        nb_device_role.save()
        ret = get_device_role(name)
    except pynetbox.RequestError as e:
        log.error("%s, %s, %s", e.req.request.headers, e.request_body, e.error)
        return False
    return ret

def check_device_role(name, **kwargs):
    """
    returns: 
        - False if error
        - None if vminterface does not exist
        - {} if there are no changes
        - {'with': 'changes'} for changes
    """
    kwargs = __utils__["args.clean_kwargs"](**kwargs)

    try:
        nb_device_role = _get(
            "dcim",
            "device_roles",
            name=name
        )
        if not nb_device_role:
            log.info('No such device_role: {}'.format(name))
            return None
    except pynetbox.RequestError as e:
        log.error("%s, %s, %s", e.req.request.headers, e.request_body, e.error)
        return False

    required_changes={}
    for k, v in kwargs.items():
        if v == None:
            # state module sets al available options default to None
            continue
       
        # Resolve kwargs to their ID if needed.
        # Not needed

        # Check if the attribute has an ID attribute.
        # If so, use it.
        value_from_netbox = ""
        nb_attribute = getattr(nb_device_role, k)
        if hasattr(nb_attribute, "id"):
            value_from_netbox = nb_attribute.id
        else:
            value_from_netbox = nb_attribute

        if v == value_from_netbox:
            print("Gelijk: {}".format(v))
        else:
            print("BOOM: {} != {}".format(v, getattr(nb_device_role, k)))
            required_changes[k]=v
    return required_changes


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


def create_ipaddress_org(ip_address, family, device=None, interface=None):
    """
    .. versionadded:: 2019.2.0

    Add an IP address, and optionally attach it to an interface.

    ip_address
        The IP address and CIDR, e.g., ``192.168.1.1/24``
    family
        Integer of IP family, e.g., ``4``
    device
        The name of the device to attach IP to, e.g., ``edge_router``
    interface
        The name of the interface to attach IP to, e.g., ``ae13``

    CLI Example:

    .. code-block:: bash

        salt myminion netbox.create_ipaddress 192.168.1.1/24 4 device=edge_router interface=ae13
    """
    nb_addr = None
    payload = {"family": family, "address": ip_address}
    if interface and device:
        nb_device = get_("dcim", "devices", name=device)
        if not nb_device:
            return False
        nb_interface = get_(
            "dcim", "interfaces", device_id=nb_device["id"], name=interface
        )
        if not nb_interface:
            return False
        nb_addr = get_(
            "ipam",
            "ip-addresses",
            q=ip_address,
            interface_id=nb_interface["id"],
            family=family,
        )
        if nb_addr:
            log.error(nb_addr)
            return False
        else:
            payload["interface"] = nb_interface["id"]
    ipaddr = _add("ipam", "ip-addresses", payload)
    if ipaddr:
        return {"ipam": {"ip-addresses": payload}}
    else:
        return ipaddr


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

def create_vminterface(
            name,
            vm_name,
            cluster,
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
    cluster
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
        nb_cluster = get_(
            "virtualization",
            "clusters",
            name=cluster
        )

        if not nb_cluster:
            log.error('No virtualization cluster found named {}'.format(cluster))
            return False
    except pynetbox.RequestError as e:
        log.error("%s, %s, %s", e.req.request.headers, e.request_body, e.error)
        return False

    try:
        nb_vm = get_(
            "virtualization",
            "virtual_machines",
            name=vm_name,
            tenant=tenant,
            cluster=nb_cluster['id']
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

def update_virtual_machine(name, cluster, **kwargs):
    """
    .. versionadded:: TBD

    Add attributes to an existing virtual machine, identified by name and cluster.

    name
        The name of the virtual_machine, e.g., ``gibson01``
    cluster
        The name of the cluster where the virtual_machine is residing, e.g., ``supercluster 1``
    kwargs
       Arguments to change in device, e.g., ``comments=This is a payphone.... Don't ask.``

    CLI Example:

    .. code-block:: bash

        salt myminion netbox.update_virtual_machine gibson01 comments="This is a payphone..... Don't ask."
    """
    nb_cluster = None
    kwargs = __utils__["args.clean_kwargs"](**kwargs)

    nb_virtual_machine = _get("virtualization", "virtual_machines", auth_required=True, name=name)
    for k, v in kwargs.items():
        setattr(nb_virtual_machine, k, v)
    try:
        nb_virtual_machine.save()
        x = get_(
            'virtualization',
            'virtual_machines',
            name=name
        )
        return x
    except pynetbox.RequestError as e:
        log.error("%s, %s, %s", e.req.request.headers, e.request_body, e.error)
        return False

def update_vminterface(name, virtual_machine, cluster, **kwargs):
    """
    .. versionadded:: TBD

    Add attributes to an existing vminterface, identified by name, virtual_machine, and cluster.

    name
        The name of the vminterface e.g., ``eth0``
    virtual_machine
        Name of the virtual machine to which assign the virtual interface, e.g., ``gibson01``
    cluster
        The name of the cluster where the virtual_machine is residing, e.g., ``supercluster 1``
    kwargs
       Arguments to change in device, e.g., ``comments=This is a payphone.... Don't ask.``

    CLI Example:

    .. code-block:: bash

        salt myminion netbox.update_vminterface eth0 gibson01 "supercluster 1" comments="This is a payphone..... Don't ask."
    """
    try:
        nb_cluster = get_(
            "virtualization",
            "clusters",
            name=cluster
        )

        if not nb_cluster:
            log.error('No virtualization cluster found named {}'.format(cluster))
            return False
    except pynetbox.RequestError as e:
        log.error("%s, %s, %s", e.req.request.headers, e.request_body, e.error)
        return False

    try:
        nb_vm = get_(
            "virtualization",
            "virtual_machines",
            name=virtual_machine,
            cluster=nb_cluster['id']
        )

        if not nb_vm:
            log.error('No Virtual Machine found named {} filtered by tenant {} and cluster {}'.format(vm_name, tenant, cluster))
            return False
    except pynetbox.RequestError as e:
        log.error("%s, %s, %s", e.req.request.headers, e.request_body, e.error)
        return False

    kwargs = __utils__["args.clean_kwargs"](**kwargs)

    nb_vminterface = _get(
        "virtualization", 
        "interfaces", 
        auth_required=True, 
        name=name,
        virtual_machine_id=nb_vm['id'],
        cluster_id=nb_cluster['id'],
    )
    for k, v in kwargs.items():
        setattr(nb_vminterface, k, v)
    try:
        nb_vminterface.save()
        x = get_(
            'virtualization',
            'interfaces',
            name=name,
            virtual_machine_id=nb_vm['id'],
            cluster_id=nb_cluster['id'],
        )
        return x
    except pynetbox.RequestError as e:
        log.error("%s, %s, %s", e.req.request.headers, e.request_body, e.error)
        return False

def check_virtual_machine(name, cluster, **kwargs):
    """
    returns: 
        - False if error
        - None if machines does not exist
        - {} if there are no changes
        - {'with': 'changes'} for changes
    """
    kwargs = __utils__["args.clean_kwargs"](**kwargs)
    try:
        nb_vm = _get("virtualization", "virtual_machines", name=name)
    except Exception as e:
        log.error("Error finding vm {}: ".format(name, e))
        return False

    changes={}
    if not nb_vm:
        return None
    for k, v in kwargs.items():
        if v == None:
            # state module sets al available options default to None
            continue
       
        # Resolve kwargs to their ID if needed.
        if k == "tenant":
            nb_tenant = get_("tenancy", "tenants", name=v)
            if nb_tenant:
                v = nb_tenant['id']
            else:
                log.error("Could not resolve tenant {} to an ID".format(v))
                return False
        if k == "cluster":
            nb_cluster = get_("virtualization", "clusters", name=v)
            if nb_cluster:
                v = nb_cluster['id']
            else:
                log.error("Could not resolve cluster {} to an ID".format(v))
                return False

        # Check if the attribute has an ID attribute.
        # If so, use it.
        value_from_netbox = ""
        nb_attribute = getattr(nb_vm, k)
        if hasattr(nb_attribute, "id"):
            value_from_netbox = nb_attribute.id
        else:
            value_from_netbox = nb_attribute
        
        
        if v == value_from_netbox:
            print("Gelijk: {}".format(v))
        else:
            print("BOOM: {} != {}".format(v, getattr(nb_vm, k)))
            changes[k]=v
    return changes

def check_vminterface(name, virtual_machine, cluster, **kwargs):
    """
    returns: 
        - False if error
        - None if vminterface does not exist
        - {} if there are no changes
        - {'with': 'changes'} for changes
    """
    try:
        nb_cluster = get_(
            "virtualization",
            "clusters",
            name=cluster
        )

        if not nb_cluster:
            log.error('No virtualization cluster found named {}'.format(cluster))
            return False
    except pynetbox.RequestError as e:
        log.error("%s, %s, %s", e.req.request.headers, e.request_body, e.error)
        return False

    try:
        nb_vm = get_(
            "virtualization",
            "virtual_machines",
            name=virtual_machine,
            cluster=nb_cluster['id']
        )
        if not nb_vm:
            log.warning('No virtual machine {} found in cluster {}'.format(virtual_machine, cluster))
            return None
    except pynetbox.RequestError as e:
        log.error("%s, %s, %s", e.req.request.headers, e.request_body, e.error)
        return False
    
    try:
        nb_vmiface = _get(
            "virtualization",
            "interfaces",
            name=name,
            virtual_machine_id=nb_vm['id'],
            cluster_id=nb_cluster['id'],
        )
        if not nb_vmiface:
            log.info('No virtual interface {} found for virtual machine {} found in cluster {}'.format(name, virtual_machine, cluster))
            return None
    except pynetbox.RequestError as e:
        log.error("%s, %s, %s", e.req.request.headers, e.request_body, e.error)
        return False

    kwargs = __utils__["args.clean_kwargs"](**kwargs)

    changes={}
    for k, v in kwargs.items():
        if v == None:
            # state module sets al available options default to None
            continue
       
        # Resolve kwargs to their ID if needed.
        if k == "parent":
            nb_iface = get_(
                "virtualization",
                "interfaces", 
                name=v,
                virtual_machine_id=nb_vm['id'],
                cluster_id=nb_cluster['id']
            )
            if nb_iface:
                v = nb_iface['id']
            else:
                log.error("Could not resolve vminterface {} to an ID".format(v))
                return False

        if k == "untagged_vlan":
            nb_vlan = get_(
                "ipam",
                "vlans", 
                vid=v
            )
            if nb_vlan:
                v = nb_vlan['id']
            else:
                log.error("Could not resolve vlan {} to an ID".format(v))
                return False

        if k == "tagged_vlans":
            vlan_list = []
            for i in v:
                nb_vlan = get_(
                    "ipam",
                    "vlans", 
                    vid=i
                )
                if nb_vlan:
                    vlan_list.append(nb_vlan['id'])
                else:
                    log.error("Could not resolve vlan {} to an ID".format(v))
                    return False
            v = vlan_list


        # Check if the attribute has an ID attribute.
        # If so, use it.
        value_from_netbox = ""
        nb_attribute = getattr(nb_vmiface, k)
        if hasattr(nb_attribute, "id"):
            value_from_netbox = nb_attribute.id
        else:
            value_from_netbox = nb_attribute

        # Netbox returns the mode as an object and it's string representation
        # is capitalized, so we work around that right here.
        if k == "mode" and v:
            v = v.lower()
            value_from_netbox = str(value_from_netbox).lower()

        # Netbox gives tagged_vlans as a list of vlan records
        # and input receives tagged_vlans as a list of vlan record id's.
        # 
        # Here, first we create a list of vlan records id's of what exists
        # in Netbox.
        #
        # Next both lists are cast to a set because sets can be
        # compared and have no order (What we want). 
        # When comparing lists order is taken into account (What we don't want).
        #
        # When both sets are compared and changes are found, v is set
        # as the list of requested vlan record id's.
        # Else, v and  vlan_from_netbox are set to the identical list
        # "vlan_list_from_input". This is done so later the lists can
        # be correctly tested for equality.
        if k == "tagged_vlans" and v:
            vlan_list_from_input = v
            vlan_list_from_netbox = []
            for vlan in value_from_netbox:
                vlan_list_from_netbox.append(vlan['id'])
            
            if set(vlan_list_from_input) == set(vlan_list_from_netbox):
                v = vlan_list_from_input
                value_from_netbox = vlan_list_from_input
            else:
                v = vlan_list_from_input
                value_from_netbox = vlan_list_from_netbox

        
        if v == value_from_netbox:
            print("Gelijk: {}".format(v))
        else:
            print("BOOM: {} != {}".format(v, getattr(nb_vmiface, k)))
            changes[k]=v
    return changes


def delete_virtual_machine(name, cluster):
    nb_cluster = get_("virtualization", "clusters", name=cluster)
    if not nb_cluster:
        log.error("Could not resolve cluster {} to an ID".format(cluster))
        return False

    nb_vm = _get("virtualization", "virtual_machines", name=name, cluster_id=nb_cluster['id'])
    if nb_vm:
        nb_vm.delete()
        return {"DELETE": {"virtualization": name}}
    return False

def create_ipaddress(
        address,
        family,
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
        family
            IP family 4 or 6. This is only build in this module for
            backwards compatibility it is not used at all.
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

    if tenant:
        nb_tenant = get_(
            "tenancy",
            "tenants",
            name=tenant
        )
        if not nb_tenant:
            log.error("No such tenant: {}".format(tenant))
            return False

    if cluster:
        nb_cluster = get_(
            "virtualization",
            "clusters",
            name=cluster
        )
        if not nb_cluster:
            log.error("No such cluster: {}".format(cluster))
            return False

    if device:
        app = "dcim"
        endpoint = "devices"
        search_kwargs['name'] = device
        search_kwargs['tenant'] = nb_tenant['id']
    if virtual_machine:
        app = "virtualization"
        endpoint = "virtual_machines"
        search_kwargs['name'] = virtual_machine
        search_kwargs['cluster'] = nb_cluster['id']

    if device or virtual_machine:
        if not interface:
            log.error("Interface is mandatory when specifying device or virtual_machine")
            return False

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
        # update attributes and save
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

def check_ipaddress(address, **kwargs):
    """
    returns: 
        - False if error
        - None if vminterface does not exist
        - {} if there are no changes
        - {'with': 'changes'} for changes

    ip addresses are a bit strange, they can be assigned to 
    device records as well a virtual machine objects....

    notes:
        address=address,
        interface=interface,
        virtual_machine=virtual_machine,
        cluster=cluster,
        device=device,
        vrf=vrf,
        tenant=tenant,
        status=status,
        role=role,
        nat_inside=nat_inside,
        dns_name=dns_name,
        description=description
    """
    kwargs = __utils__["args.clean_kwargs"](**kwargs)

    # Check if address is Sane
    try:
        nb_ipaddress = _get(
            "ipam",
            "ip_addresses",
            address=address
        )
        if not nb_ipaddress:
            log.info('No ip address {} found'.format(address))
            return None
    except pynetbox.RequestError as e:
        log.error("%s, %s, %s", e.req.request.headers, e.request_body, e.error)
        return False

    # If the kwargs 'virtual_machine' is given. Use the keys 'cluster'
    # and 'interface' in kwargs to look up the interface's ID. If found
    # remove 'virtual_machine', 'cluster', 'interface' from kwargs and add
    # 'assigned_object_type' and 'assigned_object_id'.
    # This is required because ipaddresses can be assigned to dcim.interfaces and
    # virtualization.vminterfaces.
    if kwargs.get('virtual_machine'):
        if not kwargs.get('cluster'):
            log.error("cluster must be specified when specifying virtual_machine")
            return False
        if not kwargs.get('interface'):
            log.error("interface must be specified when specifying virtual_machine")
            return False
        
        nb_cluster = get_(
            "virtualization",
            "clusters",
            name=kwargs['cluster']
        )
        if not nb_cluster:
            log.error("No such cluster {}".format(kwargs['cluster']))
            return False

        nb_vm = get_(
            "virtualization",
            "virtual_machines",
            name=kwargs['virtual_machine'],
            cluster=nb_cluster['id']
        )
        if not nb_vm:
            log.error("No such virtual_machine {} in cluster {}".format(
                kwargs['virtual_machine'],
                kwargs['cluster'],
                )
            )
            return False

        nb_iface = get_(
            "virtualization",
            "interfaces",
            name=kwargs['interface']
        )
        if not nb_iface:
            log.error("Could not find interface {} on vm {} in cluster {}".format(
                kwargs['interface'],
                kwargs['virtual_machine'],
                kwargs['cluster'],
                )
            )
            return False

        # remove information from kwargs that are only needed to lookup
        # the nb_iface['id']
        del kwargs['virtual_machine']
        del kwargs['cluster']
        del kwargs['interface']
        # place the proper kwargs for the api with the information we
        # found in NetBox.
        kwargs['assigned_object_id'] = nb_iface['id']
        kwargs['assigned_object_type'] = "virtualization.vminterface"

    # Do the same for 'device'
    if kwargs.get('device'):
        if not kwargs.get('interface'):
            log.error("Interface is mandatory when supplying device.")
            return False

        if kwargs.get('tenant'):
            nb_tenant = get_(
                "tenancy",
                "tenant",
                name=kwargs['tenant']
            )
            if not nb_tenant:
                log.error("No such tenant: {}".format(kwargs['tenant']))
                return False
            tenant_id = nb_tenant['id']
        else:
            tenant_id = None
            

        nb_device = get_(
            "dcim",
            "devices",
            name=kwargs['device'],
            tenant=tenant_id
        )
        if not nb_device:
            log.error("No such device {}".format(kwargs['device']))
            return False
        
        nb_iface = get_(
            "dcim",
            "interfaces",
            name=kwargs['interface'],
            device=nb_device['id']
        )
        if not nb_iface:
            log.error("No interface {} found for device {}".format(
                kwargs['interface'],
                kwargs['device']
                )
            )
            return False

        del kwargs['tenant']
        del kwargs['device']
        del kwargs['interface']
        kwargs['assigned_object_id'] = nb_iface['id']
        kwargs['assigned_object_type'] = "dcim.interface"

    changes={}
    for k, v in kwargs.items():
        if v == None:
            # state module sets al available options default to None
            continue
       
        # Resolve kwargs to their ID if needed.
        if k == "tenant":
            nb_tenant = get_(
                "tenancy",
                "tenants",
                name=v
            )
            if nb_tenant:
                v = nb_tenant['id']
            else:
                log.error("Could not resolv tenant {} to an ID".format(v))
                return False

        if k == "vrf":
            nb_vrf = get_(
                "ipam",
                "vrfs",
                name=v
            )
            if nb_vrf:
                v = nb_vrf['id']
            else:
                log.error("Could not resolv vrf {} to an ID".format(v))
                return False

        if k == "status":
            valid_status_types = [
                'active',
                'reserved',
                'deprecated',
                'dhcp',
                'slaac',
            ]
            if v not in valid_status_types:
                log.error("Illegal status type {} for ipaddress {}".format(v, address))
                return False

        if k == "nat_inside":
            nb_nat_inside = get_(
                "ipam",
                "ip_addresses",
                address=v
            )
            if nb_nat_inside:
                v = nb_nat_inside['id']
            else:
                log.error("Could not find internal nat address {}".format(v))
                return False

        # Check if the attribute has an ID attribute.
        # If so, use it.
        value_from_netbox = ""
        nb_attribute = getattr(nb_ipaddress, k)
        if hasattr(nb_attribute, "id"):
            value_from_netbox = nb_attribute.id
        else:
            value_from_netbox = nb_attribute

        if v == value_from_netbox:
            print("Gelijk: {}".format(v))
        else:
            print("BOOM: {} != {}".format(v, getattr(nb_ipaddress, k)))
            changes[k]=v
    return changes

def update_ipaddress(address, **kwargs):
    """
    .. versionadded:: TBD

    """

    nb_cluster = None
    kwargs = __utils__["args.clean_kwargs"](**kwargs)

    nb_ipaddress = _get("ipam", "ip_addresses", auth_required=True, address=address)
    for k, v in kwargs.items():
        setattr(nb_ipaddress, k, v)
    try:
        nb_ipaddress.save()
        x = get_(
            'ipam',
            'ip_addresses',
            address=address
        )
        return x
    except pynetbox.RequestError as e:
        log.error("%s, %s, %s", e.req.request.headers, e.request_body, e.error)
        return False

def get_cluster_type(name):
    nb_cluster_type = get_(
        "virtualization",
        "cluster_types",
        name=name
    )
    return nb_cluster_type

def create_cluster_type(name, description=None):
    """
    salt-call netbox.create_cluster_type oVirt description="A oVirt virtualization cluster"
    """
    nb_cluster_type = get_("virtualization", "cluster_types", name=name)
    if nb_cluster_type:
        log.error("A cluster type with name {} already exists within Netbox.".format(name))
        return False
    else:
        payload = {"name": name, "slug": slugify(name)}
        if description:
            payload['description'] = description
        cluster_type = _add("virtualization", "cluster_types", payload)
        if cluster_type:
            return {"virtualization": {"cluster_types": payload}}
        else:
            log.error("Failed to create cluster type with name {}".format(name))
            return False

def update_cluster_type(name, **kwargs):
    nb_cluster_type = _get("virtualization", "cluster_types", name=name)
    if not nb_cluster_type:
        log.error("No such cluster type with name {}.".format(name))
        return False

    kwargs = __utils__["args.clean_kwargs"](**kwargs)

    for k, v in kwargs.items():
        setattr(nb_cluster_type, k, v)

    try:
        nb_cluster_type.save()
        ret = get_cluster_type(name)
    except pynetbox.RequestError as e:
        log.error("%s, %s, %s", e.req.request.headers, e.request_body, e.error)
        return False

    return ret

def delete_cluster_type(name):
    """
    .. versionadded:: TBD

    name
        name of the cluster_type to delete

    CLI Example:

    .. code-block:: bash

        salt myminion netbox.cluster_type oVirt
    """
    nb_cluster_type = _get("virtualization", "cluster_types", auth_required=True, name=name)
    if not nb_cluster_type:
        log.error("No such cluster_type {}".format(name))
        return None
    nb_cluster_type.delete()
    return {"DELETE": {"virtualization": {"cluster_types": name}}}

def check_cluster_type(name, **kwargs):
    """
    returns: 
        - False if error
        - None if vminterface does not exist
        - {} if there are no changes
        - {'with': 'changes'} for changes

    ip addresses are a bit strange, they can be assigned to 
    device records as well a virtual machine objects....

    """
    kwargs = __utils__["args.clean_kwargs"](**kwargs)

    # Check if address is Sane
    try:
        nb_cluster_type = _get(
            "virtualization",
            "cluster_types",
            name=name
        )
        if not nb_cluster_type:
            log.error('No such cluster_type: {}'.format(name))
            return None
    except pynetbox.RequestError as e:
        log.error("%s, %s, %s", e.req.request.headers, e.request_body, e.error)
        return False

    required_changes={}
    for k, v in kwargs.items():
        if v == None:
            # state module sets al available options default to None
            continue
       
        # Resolve kwargs to their ID if needed.
        # <not needed>

        # Check if the attribute has an ID attribute.
        # If so, use it.
        value_from_netbox = ""
        nb_attribute = getattr(nb_cluster_type, k)
        if hasattr(nb_attribute, "id"):
            value_from_netbox = nb_attribute.id
        else:
            value_from_netbox = nb_attribute

        if v == value_from_netbox:
            print("Gelijk: {}".format(v))
        else:
            print("BOOM: {} != {}".format(v, getattr(nb_cluster_type, k)))
            required_changes[k]=v
    return required_changes




def get_cluster(name):
    nb_cluster = get_(
        "virtualization",
        "clusters",
        name=name
    )
    return nb_cluster

def create_cluster(
        name, 
        cluster_type=None, # type is a reserved keyword
        group=None,
        tenant=None,
        site=None,
        comments=None):
    """
    salt-call netbox.create_cluster yolocluster cluster_type=oVirt
    """

    if cluster_type == None:
        log.error("kwargs cluster_type is mandatory")
        return False

    nb_cluster = get_("virtualization", "clusters", name=name)
    if nb_cluster:
        log.error("A cluster type with name {} already exists within Netbox.".format(name))
        return False
    else:
        nb_cluster_type = get_("virtualization", "cluster_types", name=cluster_type)
        if not nb_cluster_type:
            log.error("No such cluster type: {}".format(cluster_type))
            return False

        pprint(nb_cluster_type)
        payload = {"name": name, "slug": slugify(name), "type": nb_cluster_type['id'] }

        if group:
            nb_cluster_group = get_("virtualization","cluster_groups", name=group)
            if not nb_cluster_group:
                log.error("No such cluster_group: {}".format(cluster_group))
                return False
            payload['group'] = nb_cluster_group.id
        if tenant:
            nb_tenant = get_("tenancy", "tenants", name=tenant)
            if not nb_tenant:
                log.error("No such tenant: {}".format(tenant))
                return False
            payload['tenant'] = nb_tenant['id']
        if site:
            nb_site = get_("dcim", "sites", name=site)
            if not nb_site:
                log.error("No such site: {}".format(site))
                return False
            payload['site'] = nb_site['id']
        if comments:
            payload['comments'] = comments

        cluster = _add("virtualization", "clusters", payload)
        if cluster:
            return {"virtualization": {"clusters": payload}}
        else:
            log.error("Failed to create cluster type with name {}".format(name))
            return False

def update_cluster(name, **kwargs):
    nb_cluster = _get("virtualization", "clusters", name=name)
    if not nb_cluster:
        log.error("No such cluster with name {}.".format(name))
        return False

    for k, v in kwargs.items():
        setattr(nb_cluster, k, v)

    try:
        nb_cluster.save()
        ret = get_cluster(name)
    except pynetbox.RequestError as e:
        log.error("%s, %s, %s", e.req.request.headers, e.request_body, e.error)
        return False

    return ret

def delete_cluster(name):
    """
    .. versionadded:: TBD

    name
        name of the cluster to delete

    CLI Example:

    .. code-block:: bash

        salt myminion netbox.cluster oVirt
    """
    nb_cluster = _get("virtualization", "clusters", auth_required=True, name=name)
    if not nb_cluster:
        log.error("No such cluster {}".format(name))
        return None
    nb_cluster.delete()
    return {"DELETE": {"virtualization": {"clusters": name}}}

def check_cluster(name, **kwargs):
    """
    returns: 
        - False if error
        - None if vminterface does not exist
        - {} if there are no changes
        - {'with': 'changes'} for changes
    """
    kwargs = __utils__["args.clean_kwargs"](**kwargs)

    try:
        nb_cluster = _get(
            "virtualization",
            "clusters",
            name=name
        )
        if not nb_cluster:
            log.info('No such cluster: {}'.format(name))
            return None
    except pynetbox.RequestError as e:
        log.error("%s, %s, %s", e.req.request.headers, e.request_body, e.error)
        return False

    required_changes={}
    for k, v in kwargs.items():
        if v == None:
            # state module sets al available options default to None
            continue
       
        # Resolve kwargs to their ID if needed.
        if k == 'cluster_type':
            nb_cluster_type = get_("virtualization", "cluster_types", name=v)
            if not nb_cluster_type:
                log.error("error retrieving cluster_type: {}".format(v))
                return False
            v = nb_cluster_type['id']  
            k = 'type' # we don't use the word "type" in salt because
                       # it is a reserved keyword in python. However
                       # in the Netbox API this refers to a cluster type
                       # so we swap the key from the kwarg "cluster_type" with "type" here.

        if k == 'group':
            nb_cluster_group = get_("virtualization", "cluster_groups", name=v)
            if not nb_cluster_group:
                log.error("No such cluster group: {}".format(v))
                return False
            v = nb_cluster_group['id']

        if k == 'site':
            nb_site = get_("dcim", "sites", name=v)
            if not nb_site:
                log.error("No such site: {}".format(v))
                return False
            v = nb_site['id']

        if k == 'tenant':
            nb_tenant = get_("tenancy", "tenants", name=v)
            if not nb_tenant:
                log.error("No such tenant: {}".format(v))
                return False
            v = nb_tenant['id']

        # Check if the attribute has an ID attribute.
        # If so, use it.
        value_from_netbox = ""
        nb_attribute = getattr(nb_cluster, k)
        if hasattr(nb_attribute, "id"):
            value_from_netbox = nb_attribute.id
        else:
            value_from_netbox = nb_attribute

        if v == value_from_netbox:
            print("Gelijk: {}".format(v))
        else:
            print("BOOM: {} != {}".format(v, getattr(nb_cluster, k)))
            required_changes[k]=v
    return required_changes

# get
# create
# update
# delete
# check


