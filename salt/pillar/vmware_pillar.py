"""
Pillar data from vCenter or an ESXi host

.. versionadded:: 2017.7.0

:depends: - pyVmomi

This external pillar can pull attributes from objects in vCenter or an ESXi host and provide those attributes
as pillar data to minions.  This can allow for pillar based targeting of minions on ESXi host, Datastore, VM
configuration, etc.  This setup requires only the salt master have access to the vCenter server/ESXi hosts.

The pillar will return an empty dict if the 'os' or 'virtual' grain are not 'VMWare', 'ESXi', or 'VMWare ESXi'.

Defaults
========

- The external pillar will search for Virtual Machines with the VM name matching the minion id.
- Data will be returned into the 'vmware' pillar key.
- The external pillar has a default set of properties to return for both VirtualMachine and HostSystem types.


Configuring the VMWare pillar
=============================

The required minimal configuration in the salt master ext_pillar setup:

.. code-block:: yaml

    ext_pillar:
        - vmware:
            host: <vcenter/esx host>
            username: <user to connect with>
            password: <password>

Optionally, the following keyword arguments can be passed to the ext_pillar for customized configuration:

    pillar_key
        Optionally set the pillar key to return the data into.  Default is ``vmware``.

    protocol
        Optionally set to alternate protocol if the vCenter server or ESX/ESXi host is not
        using the default protocol. Default protocol is ``https``.

    port
        Optionally set to alternate port if the vCenter server or ESX/ESXi host is not
        using the default port. Default port is ``443``.

    property_name
        Property name to match the minion id against.  Defaults to ``name``.

    property_types
        Optionally specify a list of pyVmomi vim types to search for the minion id in 'property_name'.
        Default is ``['VirtualMachine']``.

        For example, to search both vim.VirtualMachine and vim.HostSystem object types:

        .. code-block:: yaml

           ext_pillar:
               - vmware:
                   host: myesx
                   username: root
                   password: complex_password
                   property_types:
                     - VirtualMachine
                     - HostSystem

        Additionally, the list of property types can be dicts, the item of the dict being a list specifying
        the attribute to return for that vim object type.

        The pillar will attempt to recurse the attribute and return all child attributes.

        To explicitly specify deeper attributes without attempting to recurse an attribute, convert the list
        item to a dict with the item of the dict being the child attributes to return.  Follow this pattern
        to return attributes as deep within the object as necessary.

        .. note::
            Be careful when specifying custom attributes!  Many attributes have objects as attributes which
            have the parent object as an attribute and which will cause the pillar to fail due to the attempt
            to convert all sub-objects recursively (i.e. infinite attribute loops).  Specifying only the
            sub-attributes you would like returned will keep the infinite recursion from occurring.

            A maximum recursion exception will occur in this case and the pillar will not return as desired.

        .. code-block:: yaml

            ext_pillar:
                - vmware:
                    host: myvcenter
                    username: my_user
                    password: my_pass
                    replace_default_attributes: True
                    property_types:
                      - VirtualMachine:
                          - config:
                             - bootOptions:
                                 - bootDelay
                                 - bootRetryDelay
                      - HostSystem:
                          - datastore:
                             - name

        The above ext_pillar example would return a pillar like the following for a VirtualMachine object that's
        name matched the minion id:

        .. code-block:: yaml

            vmware:
              config:
                bootOptions:
                  bootDelay: 1000
                  bootRetryDelay: 1000

        If you were to retrieve these virtual machine attributes via pyVmomi directly, this would be the same as

        .. code-block:: python

            vmObject.config.bootOptions.bootDelay
            vmObject.config.bootOptionis.bootRetryDelay

        The above ext_pillar example would return a pillar like the following for a HostySystem object that's name
        matched the minion id:

        .. code-block:: yaml

            vmware:
              datastore:
                 - name: Datastore1
                 - name: Datastore2

        The 'datastore' property of a HostSystem object is a list of datastores, thus a list is returned.

    replace_default_attributes
        If custom attributes are specified by the property_types parameter, replace_default_attributes determines
        if those will be added to default attributes (False) or replace the default attributes completely (True).
        The default setting is 'False'.

        .. note::

            vCenter "Custom Attributes" (i.e. Annotations) will always be returned if it exists on the object as
            part of the pillar regardless of this setting.

"""

import logging

import salt.utils.dictupdate as dictupdate
import salt.utils.vmware

try:
    # pylint: disable=no-name-in-module
    from pyVmomi import vim
    from pyVim.connect import Disconnect

    HAS_LIBS = True
    # pylint: enable=no-name-in-module
except ImportError:
    HAS_LIBS = False


__virtualname__ = "vmware"

# Set up logging
log = logging.getLogger(__name__)


def __virtual__():
    """
    Only return if python-etcd is installed
    """
    return __virtualname__ if HAS_LIBS else False


def ext_pillar(minion_id, pillar, **kwargs):  # pylint: disable=W0613
    """
    Check vmware/vcenter for all data
    """
    vmware_pillar = {}
    host = None
    username = None
    password = None
    property_types = []
    property_name = "name"
    protocol = None
    port = None
    pillar_key = "vmware"
    replace_default_attributes = False
    type_specific_pillar_attributes = {
        "VirtualMachine": [
            {
                "config": [
                    "version",
                    "guestId",
                    "files",
                    "tools",
                    "flags",
                    "memoryHotAddEnabled",
                    "cpuHotAddEnabled",
                    "cpuHotRemoveEnabled",
                    "datastoreUrl",
                    "swapPlacement",
                    "bootOptions",
                    "scheduledHardwareUpgradeInfo",
                    "memoryAllocation",
                    "cpuAllocation",
                ]
            },
            {
                "summary": [
                    {"runtime": [{"host": ["name", {"parent": "name"}]}, "bootTime"]},
                    {
                        "guest": [
                            "toolsStatus",
                            "toolsVersionStatus",
                            "toolsVersionStatus2",
                            "toolsRunningStatus",
                        ]
                    },
                    {"config": ["cpuReservation", "memoryReservation"]},
                    {"storage": ["committed", "uncommitted", "unshared"]},
                    {"dasVmProtection": ["dasProtected"]},
                ]
            },
            {
                "storage": [
                    {
                        "perDatastoreUsage": [
                            {"datastore": "name"},
                            "committed",
                            "uncommitted",
                            "unshared",
                        ]
                    }
                ]
            },
        ],
        "HostSystem": [
            {
                "datastore": [
                    "name",
                    "overallStatus",
                    {
                        "summary": [
                            "url",
                            "freeSpace",
                            "maxFileSize",
                            "maxVirtualDiskCapacity",
                            "maxPhysicalRDMFileSize",
                            "maxVirtualRDMFileSize",
                            {
                                "vmfs": [
                                    "capacity",
                                    "blockSizeMb",
                                    "maxBlocks",
                                    "majorVersion",
                                    "version",
                                    "uuid",
                                    {"extent": ["diskName", "partition"]},
                                    "vmfsUpgradeable",
                                    "ssd",
                                    "local",
                                ],
                            },
                        ],
                    },
                    {"vm": "name"},
                ]
            },
            {
                "vm": [
                    "name",
                    "overallStatus",
                    {"summary": [{"runtime": "powerState"}]},
                ]
            },
        ],
    }
    pillar_attributes = [
        {"summary": ["overallStatus"]},
        {"network": ["name", {"config": {"distributedVirtualSwitch": "name"}}]},
        {"datastore": ["name"]},
        {"parent": ["name"]},
    ]

    if "pillar_key" in kwargs:
        pillar_key = kwargs["pillar_key"]
    vmware_pillar[pillar_key] = {}

    if "host" not in kwargs:
        log.error(
            "VMWare external pillar configured but host is not specified in ext_pillar"
            " configuration."
        )
        return vmware_pillar
    else:
        host = kwargs["host"]
        log.debug("vmware_pillar -- host = %s", host)

    if "username" not in kwargs:
        log.error(
            "VMWare external pillar requested but username is not specified in"
            " ext_pillar configuration."
        )
        return vmware_pillar
    else:
        username = kwargs["username"]
        log.debug("vmware_pillar -- username = %s", username)

    if "password" not in kwargs:
        log.error(
            "VMWare external pillar requested but password is not specified in"
            " ext_pillar configuration."
        )
        return vmware_pillar
    else:
        password = kwargs["password"]
        log.debug("vmware_pillar -- password = %s", password)

    if "replace_default_attributes" in kwargs:
        replace_default_attributes = kwargs["replace_default_attributes"]
        if replace_default_attributes:
            pillar_attributes = []
            type_specific_pillar_attributes = {}

    if "property_types" in kwargs:
        for prop_type in kwargs["property_types"]:
            if isinstance(prop_type, dict):
                next_prop_type_key = next(iter(prop_type))
                property_types.append(getattr(vim, next_prop_type_key))
                if isinstance(prop_type[next_prop_type_key], list):
                    pillar_attributes = (
                        pillar_attributes + prop_type[next_prop_type_key]
                    )
                else:
                    log.warning(
                        "A property_type dict was specified, but its value is not a"
                        " list"
                    )
            else:
                property_types.append(getattr(vim, prop_type))
    else:
        property_types = [vim.VirtualMachine]
    log.debug("vmware_pillar -- property_types = %s", property_types)

    if "property_name" in kwargs:
        property_name = kwargs["property_name"]
    else:
        property_name = "name"
    log.debug("vmware_pillar -- property_name = %s", property_name)

    if "protocol" in kwargs:
        protocol = kwargs["protocol"]
        log.debug("vmware_pillar -- protocol = %s", protocol)

    if "port" in kwargs:
        port = kwargs["port"]
        log.debug("vmware_pillar -- port = %s", port)

    virtualgrain = None
    osgrain = None
    if "virtual" in __grains__:
        virtualgrain = __grains__["virtual"].lower()
    if "os" in __grains__:
        osgrain = __grains__["os"].lower()

    if virtualgrain == "vmware" or osgrain == "vmware esxi" or osgrain == "esxi":
        vmware_pillar[pillar_key] = {}
        try:
            _conn = salt.utils.vmware.get_service_instance(
                host,
                username,
                password,
                protocol,
                port,
                verify_ssl=kwargs.get("verify_ssl", True),
            )
            if _conn:
                data = None
                for prop_type in property_types:
                    data = salt.utils.vmware.get_mor_by_property(
                        _conn, prop_type, minion_id, property_name=property_name
                    )
                    if data:
                        type_name = type(data).__name__.replace("vim.", "")
                        if hasattr(data, "availableField"):
                            vmware_pillar[pillar_key]["annotations"] = {}
                            for availableField in data.availableField:
                                for customValue in data.customValue:
                                    if availableField.key == customValue.key:
                                        vmware_pillar[pillar_key]["annotations"][
                                            availableField.name
                                        ] = customValue.value
                        type_specific_pillar_attribute = []
                        if type_name in type_specific_pillar_attributes:
                            type_specific_pillar_attribute = (
                                type_specific_pillar_attributes[type_name]
                            )
                        vmware_pillar[pillar_key] = dictupdate.update(
                            vmware_pillar[pillar_key],
                            _crawl_attribute(
                                data, pillar_attributes + type_specific_pillar_attribute
                            ),
                        )
                        break
                # explicitly disconnect from vCenter when we are done, connections linger idle otherwise
                Disconnect(_conn)
            else:
                log.error(
                    "Unable to obtain a connection with %s, please verify "
                    "your vmware ext_pillar configuration",
                    host,
                )
        except RuntimeError:
            log.error(
                "A runtime error occurred in the vmware_pillar, "
                "this is likely caused by an infinite recursion in "
                "a requested attribute.  Verify your requested attributes "
                "and reconfigure the pillar."
            )

        return vmware_pillar
    else:
        return {}


def _recurse_config_to_dict(t_data):
    """
    helper function to recurse through a vim object and attempt to return all child objects
    """
    if not isinstance(t_data, type(None)):
        if isinstance(t_data, list):
            t_list = []
            for i in t_data:
                t_list.append(_recurse_config_to_dict(i))
            return t_list
        elif isinstance(t_data, dict):
            t_dict = {}
            for k, v in t_data.items():
                t_dict[k] = _recurse_config_to_dict(v)
            return t_dict
        else:
            if hasattr(t_data, "__dict__"):
                return _recurse_config_to_dict(t_data.__dict__)
            else:
                return _serializer(t_data)


def _crawl_attribute(this_data, this_attr):
    """
    helper function to crawl an attribute specified for retrieval
    """
    if isinstance(this_data, list):
        t_list = []
        for d in this_data:
            t_list.append(_crawl_attribute(d, this_attr))
        return t_list
    else:
        if isinstance(this_attr, dict):
            t_dict = {}
            for k in this_attr:
                if hasattr(this_data, k):
                    t_dict[k] = _crawl_attribute(
                        getattr(this_data, k, None), this_attr[k]
                    )
            return t_dict
        elif isinstance(this_attr, list):
            this_dict = {}
            for l in this_attr:
                this_dict = dictupdate.update(this_dict, _crawl_attribute(this_data, l))
            return this_dict
        else:
            return {
                this_attr: _recurse_config_to_dict(getattr(this_data, this_attr, None))
            }


def _serializer(obj):
    """
    helper function to serialize some objects for prettier return
    """
    import datetime

    if isinstance(obj, datetime.datetime):
        if obj.utcoffset() is not None:
            obj = obj - obj.utcoffset()
        return obj.__str__()
    return obj
