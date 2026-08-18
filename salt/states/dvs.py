"""
Manage VMware distributed virtual switches (DVSs) and their distributed virtual
portgroups (DVportgroups).

:codeauthor: `Alexandru Bleotu <alexandru.bleotu@morganstaley.com>`

Examples
========

Several settings can be changed for DVSs and DVporgroups. Here are two examples
covering all of the settings. Fewer settings can be used

DVS
---

.. code-block:: python

    'name': 'dvs1',
    'max_mtu': 1000,
    'uplink_names': [
        'dvUplink1',
        'dvUplink2',
        'dvUplink3'
    ],
    'capability': {
        'portgroup_operation_supported': false,
        'operation_supported': true,
        'port_operation_supported': false
    },
    'lacp_api_version': 'multipleLag',
    'contact_email': 'foo@email.com',
    'product_info': {
        'version':
        '6.0.0',
        'vendor':
        'VMware,
        Inc.',
        'name':
        'DVS'
    },
    'network_resource_management_enabled': true,
    'contact_name': 'me@email.com',
    'infrastructure_traffic_resource_pools': [
        {
            'reservation': 0,
            'limit': 1000,
            'share_level': 'high',
            'key': 'management',
            'num_shares': 100
        },
        {
            'reservation': 0,
            'limit': -1,
            'share_level': 'normal',
            'key': 'faultTolerance',
            'num_shares': 50
        },
        {
            'reservation': 0,
            'limit': 32000,
            'share_level': 'normal',
            'key': 'vmotion',
            'num_shares': 50
        },
        {
            'reservation': 10000,
            'limit': -1,
            'share_level': 'normal',
            'key': 'virtualMachine',
            'num_shares': 50
        },
        {
            'reservation': 0,
            'limit': -1,
            'share_level': 'custom',
            'key': 'iSCSI',
            'num_shares': 75
        },
        {
            'reservation': 0,
            'limit': -1,
            'share_level': 'normal',
            'key': 'nfs',
            'num_shares': 50
        },
        {
            'reservation': 0,
            'limit': -1,
            'share_level': 'normal',
            'key': 'hbr',
            'num_shares': 50
        },
        {
            'reservation': 8750,
            'limit': 15000,
            'share_level': 'high',
            'key': 'vsan',
            'num_shares': 100
        },
        {
            'reservation': 0,
            'limit': -1,
            'share_level': 'normal',
            'key': 'vdp',
            'num_shares': 50
        }
    ],
    'link_discovery_protocol': {
        'operation':
        'listen',
        'protocol':
        'cdp'
    },
    'network_resource_control_version': 'version3',
    'description': 'Managed by Salt. Random settings.'

Note: The mandatory attribute is: ``name``.

Portgroup
---------

.. code-block:: python

    'security_policy': {
        'allow_promiscuous': true,
        'mac_changes': false,
        'forged_transmits': true
    },
    'name': 'vmotion-v702',
    'out_shaping': {
        'enabled': true,
        'average_bandwidth': 1500,
        'burst_size': 4096,
        'peak_bandwidth': 1500
    },
    'num_ports': 128,
    'teaming': {
        'port_order': {
            'active': [
                'dvUplink2'
            ],
            'standby': [
                'dvUplink1'
            ]
        },
        'notify_switches': false,
        'reverse_policy': true,
        'rolling_order': false,
        'policy': 'failover_explicit',
        'failure_criteria': {
            'check_error_percent': true,
            'full_duplex': false,
            'check_duplex': false,
            'percentage': 50,
            'check_speed': 'minimum',
            'speed': 20,
            'check_beacon': true
        }
    },
    'type': 'earlyBinding',
    'vlan_id': 100,
    'description': 'Managed by Salt. Random settings.'

Note: The mandatory attributes are: ``name``, ``type``.

Dependencies
============

- pyVmomi Python Module


pyVmomi
-------

PyVmomi can be installed via pip:

.. code-block:: bash

    pip install pyVmomi

.. note::

    Version 6.0 of pyVmomi has some problems with SSL error handling on certain
    versions of Python. If using version 6.0 of pyVmomi, Python 2.7.9,
    or newer must be present. This is due to an upstream dependency
    in pyVmomi 6.0 that is not supported in Python versions 2.7 to 2.7.8. If the
    version of Python is not in the supported range, you will need to install an
    earlier version of pyVmomi. See `Issue #29537`_ for more information.

.. _Issue #29537: https://github.com/saltstack/salt/issues/29537

Based on the note above, to install an earlier version of pyVmomi than the
version currently listed in PyPi, run the following:

.. code-block:: bash

    pip install pyVmomi==5.5.0.2014.1.1

The 5.5.0.2014.1.1 is a known stable version that this original ESXi State
Module was developed against.
"""

import logging
import sys

import salt.exceptions

try:
    from pyVmomi import VmomiSupport

    HAS_PYVMOMI = True
except ImportError:
    HAS_PYVMOMI = False

# Get Logging Started
log = logging.getLogger(__name__)


def __virtual__():
    if not HAS_PYVMOMI:
        return False, "State module did not load: pyVmomi not found"

    # We check the supported vim versions to infer the pyVmomi version
    if (
        "vim25/6.0" in VmomiSupport.versionMap
        and sys.version_info > (2, 7)
        and sys.version_info < (2, 7, 9)
    ):

        return (
            False,
            "State module did not load: Incompatible versions "
            "of Python and pyVmomi present. See Issue #29537.",
        )
    return "dvs"


def mod_init(low):
    """
    Init function
    """
    return True


def _get_datacenter_name():
    """
    Returns the datacenter name configured on the proxy

    Supported proxies: esxcluster, esxdatacenter
    """

    proxy_type = __salt__["vsphere.get_proxy_type"]()
    details = None
    if proxy_type == "esxcluster":
        details = __salt__["esxcluster.get_details"]()
    elif proxy_type == "esxdatacenter":
        details = __salt__["esxdatacenter.get_details"]()
    if not details:
        raise salt.exceptions.CommandExecutionError(
            f"details for proxy type '{proxy_type}' not loaded"
        )
    return details["datacenter"]


def dvs_configured(name, dvs):
    """
    Configures a DVS.

    Creates a new DVS, if it doesn't exist in the provided datacenter or
    reconfigures it if configured differently.

    dvs
        DVS dict representations (see module sysdocs)
    """
    datacenter_name = _get_datacenter_name()
    dvs_name = dvs["name"] if dvs.get("name") else name
    log.info(
        "Running state %s for DVS '%s' in datacenter '%s'",
        name,
        dvs_name,
        datacenter_name,
    )
    changes_required = False
    ret = {"name": name, "changes": {}, "result": None, "comment": None}
    comments = []
    changes = {}
    changes_required = False

    try:
        # TODO dvs validation
        si = __salt__["vsphere.get_service_instance_via_proxy"]()
        dvss = __salt__["vsphere.list_dvss"](dvs_names=[dvs_name], service_instance=si)
        if not dvss:
            changes_required = True
            if __opts__["test"]:
                comments.append(
                    "State {} will create a new DVS '{}' in datacenter '{}'".format(
                        name, dvs_name, datacenter_name
                    )
                )
                log.info(comments[-1])
            else:
                dvs["name"] = dvs_name
                __salt__["vsphere.create_dvs"](
                    dvs_dict=dvs, dvs_name=dvs_name, service_instance=si
                )
                comments.append(
                    "Created a new DVS '{}' in datacenter '{}'".format(
                        dvs_name, datacenter_name
                    )
                )
                log.info(comments[-1])
                changes.update({"dvs": {"new": dvs}})
        else:
            # DVS already exists. Checking various aspects of the config
            props = [
                "description",
                "contact_email",
                "contact_name",
                "lacp_api_version",
                "link_discovery_protocol",
                "max_mtu",
                "network_resource_control_version",
                "network_resource_management_enabled",
            ]
            log.trace(
                "DVS '%s' found in datacenter '%s'. Checking for any updates in %s",
                dvs_name,
                datacenter_name,
                props,
            )
            props_to_original_values = {}
            props_to_updated_values = {}
            current_dvs = dvss[0]
            for prop in props:
                if prop in dvs and dvs[prop] != current_dvs.get(prop):
                    props_to_original_values[prop] = current_dvs.get(prop)
                    props_to_updated_values[prop] = dvs[prop]

            # Simple infrastructure traffic resource control compare doesn't
            # work because num_shares is optional if share_level is not custom
            # We need to do a dedicated compare for this property
            infra_prop = "infrastructure_traffic_resource_pools"
            original_infra_res_pools = []
            updated_infra_res_pools = []
            if infra_prop in dvs:
                if not current_dvs.get(infra_prop):
                    updated_infra_res_pools = dvs[infra_prop]
                else:
                    for idx in range(len(dvs[infra_prop])):
                        if (
                            "num_shares" not in dvs[infra_prop][idx]
                            and current_dvs[infra_prop][idx]["share_level"] != "custom"
                            and "num_shares" in current_dvs[infra_prop][idx]
                        ):

                            del current_dvs[infra_prop][idx]["num_shares"]
                        if dvs[infra_prop][idx] != current_dvs[infra_prop][idx]:

                            original_infra_res_pools.append(
                                current_dvs[infra_prop][idx]
                            )
                            updated_infra_res_pools.append(dict(dvs[infra_prop][idx]))
            if updated_infra_res_pools:
                props_to_original_values["infrastructure_traffic_resource_pools"] = (
                    original_infra_res_pools
                )
                props_to_updated_values["infrastructure_traffic_resource_pools"] = (
                    updated_infra_res_pools
                )
            if props_to_updated_values:
                if __opts__["test"]:
                    changes_string = ""
                    for p in props_to_updated_values:
                        if p == "infrastructure_traffic_resource_pools":
                            changes_string += (
                                "\tinfrastructure_traffic_resource_pools:\n"
                            )
                            for idx in range(len(props_to_updated_values[p])):
                                d = props_to_updated_values[p][idx]
                                s = props_to_original_values[p][idx]
                                changes_string += "\t\t{} from '{}' to '{}'\n".format(
                                    d["key"], s, d
                                )
                        else:
                            changes_string += "\t{} from '{}' to '{}'\n".format(
                                p,
                                props_to_original_values[p],
                                props_to_updated_values[p],
                            )
                    comments.append(
                        "State dvs_configured will update DVS '{}' "
                        "in datacenter '{}':\n{}"
                        "".format(dvs_name, datacenter_name, changes_string)
                    )
                    log.info(comments[-1])
                else:
                    __salt__["vsphere.update_dvs"](
                        dvs_dict=props_to_updated_values,
                        dvs=dvs_name,
                        service_instance=si,
                    )
                    comments.append(
                        "Updated DVS '{}' in datacenter '{}'".format(
                            dvs_name, datacenter_name
                        )
                    )
                    log.info(comments[-1])
                changes.update(
                    {
                        "dvs": {
                            "new": props_to_updated_values,
                            "old": props_to_original_values,
                        }
                    }
                )
        __salt__["vsphere.disconnect"](si)
    except salt.exceptions.CommandExecutionError as exc:
        log.error("Error: %s", exc, exc_info=True)
        if si:
            __salt__["vsphere.disconnect"](si)
        if not __opts__["test"]:
            ret["result"] = False
        ret.update(
            {"comment": str(exc), "result": False if not __opts__["test"] else None}
        )
        return ret
    if not comments:
        # We have no changes
        ret.update(
            {
                "comment": (
                    "DVS '{}' in datacenter '{}' is "
                    "correctly configured. Nothing to be done."
                    "".format(dvs_name, datacenter_name)
                ),
                "result": True,
            }
        )
    else:
        ret.update(
            {
                "comment": "\n".join(comments),
                "changes": changes,
                "result": None if __opts__["test"] else True,
            }
        )
    return ret


def _get_diff_dict(dict1, dict2):
    """
    Returns a dictionary with the diffs between two dictionaries

    It will ignore any key that doesn't exist in dict2
    """
    ret_dict = {}
    for p in dict2.keys():
        if p not in dict1:
            ret_dict.update({p: {"val1": None, "val2": dict2[p]}})
        elif dict1[p] != dict2[p]:
            if isinstance(dict1[p], dict) and isinstance(dict2[p], dict):
                sub_diff_dict = _get_diff_dict(dict1[p], dict2[p])
                if sub_diff_dict:
                    ret_dict.update({p: sub_diff_dict})
            else:
                ret_dict.update({p: {"val1": dict1[p], "val2": dict2[p]}})
    return ret_dict


def _get_val2_dict_from_diff_dict(diff_dict):
    """
    Returns a dictionaries with the values stored in val2 of a diff dict.
    """
    ret_dict = {}
    for p in diff_dict.keys():
        if not isinstance(diff_dict[p], dict):
            raise ValueError(f"Unexpected diff difct '{diff_dict}'")
        if "val2" in diff_dict[p].keys():
            ret_dict.update({p: diff_dict[p]["val2"]})
        else:
            ret_dict.update({p: _get_val2_dict_from_diff_dict(diff_dict[p])})
    return ret_dict


def _get_val1_dict_from_diff_dict(diff_dict):
    """
    Returns a dictionaries with the values stored in val1 of a diff dict.
    """
    ret_dict = {}
    for p in diff_dict.keys():
        if not isinstance(diff_dict[p], dict):
            raise ValueError(f"Unexpected diff difct '{diff_dict}'")
        if "val1" in diff_dict[p].keys():
            ret_dict.update({p: diff_dict[p]["val1"]})
        else:
            ret_dict.update({p: _get_val1_dict_from_diff_dict(diff_dict[p])})
    return ret_dict


def _get_changes_from_diff_dict(diff_dict):
    """
    Returns a list of string message of the differences in a diff dict.

    Each inner message is tabulated one tab deeper
    """
    changes_strings = []
    for p in diff_dict.keys():
        if not isinstance(diff_dict[p], dict):
            raise ValueError(f"Unexpected diff difct '{diff_dict}'")
        if sorted(diff_dict[p].keys()) == ["val1", "val2"]:
            # Some string formatting
            from_str = diff_dict[p]["val1"]
            if isinstance(diff_dict[p]["val1"], str):
                from_str = "'{}'".format(diff_dict[p]["val1"])
            elif isinstance(diff_dict[p]["val1"], list):
                from_str = "'{}'".format(", ".join(diff_dict[p]["val1"]))
            to_str = diff_dict[p]["val2"]
            if isinstance(diff_dict[p]["val2"], str):
                to_str = "'{}'".format(diff_dict[p]["val2"])
            elif isinstance(diff_dict[p]["val2"], list):
                to_str = "'{}'".format(", ".join(diff_dict[p]["val2"]))
            changes_strings.append(f"{p} from {from_str} to {to_str}")
        else:
            sub_changes = _get_changes_from_diff_dict(diff_dict[p])
            if sub_changes:
                changes_strings.append(f"{p}:")
                changes_strings.extend([f"\t{c}" for c in sub_changes])
    return changes_strings


def portgroups_configured(name, dvs, portgroups):
    """
    Configures portgroups on a DVS.

    Creates/updates/removes portgroups in a provided DVS

    dvs
        Name of the DVS

    portgroups
        Portgroup dict representations (see module sysdocs)
    """
    datacenter = _get_datacenter_name()
    log.info("Running state %s on DVS '%s', datacenter '%s'", name, dvs, datacenter)
    changes_required = False
    ret = {"name": name, "changes": {}, "result": None, "comment": None}
    comments = []
    changes = {}
    changes_required = False

    try:
        # TODO portroups validation
        si = __salt__["vsphere.get_service_instance_via_proxy"]()
        current_pgs = __salt__["vsphere.list_dvportgroups"](
            dvs=dvs, service_instance=si
        )
        expected_pg_names = []
        for pg in portgroups:
            pg_name = pg["name"]
            expected_pg_names.append(pg_name)
            del pg["name"]
            log.info("Checking pg '%s'", pg_name)
            filtered_current_pgs = [p for p in current_pgs if p.get("name") == pg_name]
            if not filtered_current_pgs:
                changes_required = True
                if __opts__["test"]:
                    comments.append(
                        "State {} will create a new portgroup "
                        "'{}' in DVS '{}', datacenter "
                        "'{}'".format(name, pg_name, dvs, datacenter)
                    )
                else:
                    __salt__["vsphere.create_dvportgroup"](
                        portgroup_dict=pg,
                        portgroup_name=pg_name,
                        dvs=dvs,
                        service_instance=si,
                    )
                    comments.append(
                        "Created a new portgroup '{}' in DVS "
                        "'{}', datacenter '{}'"
                        "".format(pg_name, dvs, datacenter)
                    )
                log.info(comments[-1])
                changes.update({pg_name: {"new": pg}})
            else:
                # Porgroup already exists. Checking the config
                log.trace(
                    "Portgroup '%s' found in DVS '%s', datacenter '%s'. Checking for any updates.",
                    pg_name,
                    dvs,
                    datacenter,
                )
                current_pg = filtered_current_pgs[0]
                diff_dict = _get_diff_dict(current_pg, pg)

                if diff_dict:
                    changes_required = True
                    if __opts__["test"]:
                        changes_strings = _get_changes_from_diff_dict(diff_dict)
                        log.trace("changes_strings = %s", changes_strings)
                        comments.append(
                            "State {} will update portgroup '{}' in "
                            "DVS '{}', datacenter '{}':\n{}"
                            "".format(
                                name,
                                pg_name,
                                dvs,
                                datacenter,
                                "\n".join([f"\t{c}" for c in changes_strings]),
                            )
                        )
                    else:
                        __salt__["vsphere.update_dvportgroup"](
                            portgroup_dict=pg,
                            portgroup=pg_name,
                            dvs=dvs,
                            service_instance=si,
                        )
                        comments.append(
                            "Updated portgroup '{}' in DVS "
                            "'{}', datacenter '{}'"
                            "".format(pg_name, dvs, datacenter)
                        )
                    log.info(comments[-1])
                    changes.update(
                        {
                            pg_name: {
                                "new": _get_val2_dict_from_diff_dict(diff_dict),
                                "old": _get_val1_dict_from_diff_dict(diff_dict),
                            }
                        }
                    )
        # Add the uplink portgroup to the expected pg names
        uplink_pg = __salt__["vsphere.list_uplink_dvportgroup"](
            dvs=dvs, service_instance=si
        )
        expected_pg_names.append(uplink_pg["name"])
        # Remove any extra portgroups
        for current_pg in current_pgs:
            if current_pg["name"] not in expected_pg_names:
                changes_required = True
                if __opts__["test"]:
                    comments.append(
                        "State {} will remove "
                        "the portgroup '{}' from DVS '{}', "
                        "datacenter '{}'"
                        "".format(name, current_pg["name"], dvs, datacenter)
                    )
                else:
                    __salt__["vsphere.remove_dvportgroup"](
                        portgroup=current_pg["name"], dvs=dvs, service_instance=si
                    )
                    comments.append(
                        "Removed the portgroup '{}' from DVS "
                        "'{}', datacenter '{}'"
                        "".format(current_pg["name"], dvs, datacenter)
                    )
                log.info(comments[-1])
                changes.update({current_pg["name"]: {"old": current_pg}})
        __salt__["vsphere.disconnect"](si)
    except salt.exceptions.CommandExecutionError as exc:
        log.error("Error: %s", exc, exc_info=True)
        if si:
            __salt__["vsphere.disconnect"](si)
        if not __opts__["test"]:
            ret["result"] = False
        ret.update(
            {"comment": exc.strerror, "result": False if not __opts__["test"] else None}
        )
        return ret
    if not changes_required:
        # We have no changes
        ret.update(
            {
                "comment": (
                    "All portgroups in DVS '{}', datacenter "
                    "'{}' exist and are correctly configured. "
                    "Nothing to be done.".format(dvs, datacenter)
                ),
                "result": True,
            }
        )
    else:
        ret.update(
            {
                "comment": "\n".join(comments),
                "changes": changes,
                "result": None if __opts__["test"] else True,
            }
        )
    return ret


def uplink_portgroup_configured(name, dvs, uplink_portgroup):
    """
    Configures the uplink portgroup on a DVS. The state assumes there is only
    one uplink portgroup.

    dvs
        Name of the DVS

    upling_portgroup
        Uplink portgroup dict representations (see module sysdocs)

    """
    datacenter = _get_datacenter_name()
    log.info("Running %s on DVS '%s', datacenter '%s'", name, dvs, datacenter)
    changes_required = False
    ret = {"name": name, "changes": {}, "result": None, "comment": None}
    comments = []
    changes = {}
    changes_required = False

    try:
        # TODO portroups validation
        si = __salt__["vsphere.get_service_instance_via_proxy"]()
        current_uplink_portgroup = __salt__["vsphere.list_uplink_dvportgroup"](
            dvs=dvs, service_instance=si
        )
        log.trace("current_uplink_portgroup = %s", current_uplink_portgroup)
        diff_dict = _get_diff_dict(current_uplink_portgroup, uplink_portgroup)
        if diff_dict:
            changes_required = True
            if __opts__["test"]:
                changes_strings = _get_changes_from_diff_dict(diff_dict)
                log.trace("changes_strings = %s", changes_strings)
                comments.append(
                    "State {} will update the "
                    "uplink portgroup in DVS '{}', datacenter "
                    "'{}':\n{}"
                    "".format(
                        name,
                        dvs,
                        datacenter,
                        "\n".join([f"\t{c}" for c in changes_strings]),
                    )
                )
            else:
                __salt__["vsphere.update_dvportgroup"](
                    portgroup_dict=uplink_portgroup,
                    portgroup=current_uplink_portgroup["name"],
                    dvs=dvs,
                    service_instance=si,
                )
                comments.append(
                    "Updated the uplink portgroup in DVS '{}', datacenter '{}'".format(
                        dvs, datacenter
                    )
                )
            log.info(comments[-1])
            changes.update(
                {
                    "uplink_portgroup": {
                        "new": _get_val2_dict_from_diff_dict(diff_dict),
                        "old": _get_val1_dict_from_diff_dict(diff_dict),
                    }
                }
            )
        __salt__["vsphere.disconnect"](si)
    except salt.exceptions.CommandExecutionError as exc:
        log.error("Error: %s", exc, exc_info=True)
        if si:
            __salt__["vsphere.disconnect"](si)
        if not __opts__["test"]:
            ret["result"] = False
        ret.update(
            {"comment": exc.strerror, "result": False if not __opts__["test"] else None}
        )
        return ret
    if not changes_required:
        # We have no changes
        ret.update(
            {
                "comment": (
                    "Uplink portgroup in DVS '{}', datacenter "
                    "'{}' is correctly configured. "
                    "Nothing to be done.".format(dvs, datacenter)
                ),
                "result": True,
            }
        )
    else:
        ret.update(
            {
                "comment": "\n".join(comments),
                "changes": changes,
                "result": None if __opts__["test"] else True,
            }
        )
    return ret
