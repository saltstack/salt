"""
Manage VMware ESXi Clusters.

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
from salt.config.schemas.esxcluster import ESXClusterConfigSchema, LicenseSchema
from salt.utils import dictupdate
from salt.utils.dictdiffer import recursive_diff
from salt.utils.listdiffer import list_diff

# External libraries
try:
    import jsonschema

    HAS_JSONSCHEMA = True
except ImportError:
    HAS_JSONSCHEMA = False

try:
    from pyVmomi import VmomiSupport

    HAS_PYVMOMI = True
except ImportError:
    HAS_PYVMOMI = False

# Get Logging Started
log = logging.getLogger(__name__)


def __virtual__():
    if not HAS_JSONSCHEMA:
        return False, "State module did not load: jsonschema not found"
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
            "State module did not load: Incompatible versions of Python and pyVmomi"
            " present. See Issue #29537.",
        )
    return True


def mod_init(low):
    """
    Retrieves and adapt the login credentials from the proxy connection module
    """
    return True


def _get_vsan_datastore(si, cluster_name):
    """Retrieves the vsan_datastore"""

    log.trace("Retrieving vsan datastore")
    vsan_datastores = [
        ds
        for ds in __salt__["vsphere.list_datastores_via_proxy"](service_instance=si)
        if ds["type"] == "vsan"
    ]

    if not vsan_datastores:
        raise salt.exceptions.VMwareObjectRetrievalError(
            "No vSAN datastores where retrieved for cluster '{}'".format(cluster_name)
        )
    return vsan_datastores[0]


def cluster_configured(name, cluster_config):
    """
    Configures a cluster. Creates a new cluster, if it doesn't exist on the
    vCenter or reconfigures it if configured differently

    Supported proxies: esxdatacenter, esxcluster

    name
        Name of the state. If the state is run in by an ``esxdatacenter``
        proxy, it will be the name of the cluster.

    cluster_config
        Configuration applied to the cluster.
        Complex datastructure following the ESXClusterConfigSchema.
        Valid example is:

    .. code-block:: yaml

        drs:
            default_vm_behavior: fullyAutomated
            enabled: true
            vmotion_rate: 3
        ha:
            admission_control
            _enabled: false
            default_vm_settings:
                isolation_response: powerOff
                restart_priority: medium
            enabled: true
            hb_ds_candidate_policy: userSelectedDs
            host_monitoring: enabled
            options:
                - key: das.ignoreinsufficienthbdatastore
                  value: 'true'
            vm_monitoring: vmMonitoringDisabled
        vm_swap_placement: vmDirectory
        vsan:
            auto_claim_storage: false
            compression_enabled: true
            dedup_enabled: true
            enabled: true

    """
    proxy_type = __salt__["vsphere.get_proxy_type"]()
    if proxy_type == "esxdatacenter":
        cluster_name, datacenter_name = (
            name,
            __salt__["esxdatacenter.get_details"]()["datacenter"],
        )
    elif proxy_type == "esxcluster":
        cluster_name, datacenter_name = (
            __salt__["esxcluster.get_details"]()["cluster"],
            __salt__["esxcluster.get_details"]()["datacenter"],
        )
    else:
        raise salt.exceptions.CommandExecutionError(
            "Unsupported proxy {}".format(proxy_type)
        )
    log.info(
        "Running %s for cluster '%s' in datacenter '%s'",
        name,
        cluster_name,
        datacenter_name,
    )
    cluster_dict = cluster_config
    log.trace("cluster_dict = %s", cluster_dict)
    changes_required = False
    ret = {"name": name, "changes": {}, "result": None, "comment": "Default"}
    comments = []
    changes = {}
    changes_required = False

    try:
        log.trace("Validating cluster_configured state input")
        schema = ESXClusterConfigSchema.serialize()
        log.trace("schema = %s", schema)
        try:
            jsonschema.validate(cluster_dict, schema)
        except jsonschema.exceptions.ValidationError as exc:
            raise salt.exceptions.InvalidESXClusterPayloadError(exc)
        current = None
        si = __salt__["vsphere.get_service_instance_via_proxy"]()
        try:
            current = __salt__["vsphere.list_cluster"](
                datacenter_name, cluster_name, service_instance=si
            )
        except salt.exceptions.VMwareObjectRetrievalError:
            changes_required = True
            if __opts__["test"]:
                comments.append(
                    "State {} will create cluster '{}' in datacenter '{}'.".format(
                        name, cluster_name, datacenter_name
                    )
                )
                log.info(comments[-1])
                __salt__["vsphere.disconnect"](si)
                ret.update({"result": None, "comment": "\n".join(comments)})
                return ret
            log.trace(
                "Creating cluster '%s' in datacenter '%s'.",
                cluster_name,
                datacenter_name,
            )
            __salt__["vsphere.create_cluster"](
                cluster_dict, datacenter_name, cluster_name, service_instance=si
            )
            comments.append(
                "Created cluster '{}' in datacenter '{}'".format(
                    cluster_name, datacenter_name
                )
            )
            log.info(comments[-1])
            changes.update({"new": cluster_dict})
        if current:
            # Cluster already exists
            # We need to handle lists sepparately
            ldiff = None
            if "ha" in cluster_dict and "options" in cluster_dict["ha"]:
                ldiff = list_diff(
                    current.get("ha", {}).get("options", []),
                    cluster_dict.get("ha", {}).get("options", []),
                    "key",
                )
                log.trace("options diffs = %s", ldiff.diffs)
                # Remove options if exist
                del cluster_dict["ha"]["options"]
                if "ha" in current and "options" in current["ha"]:
                    del current["ha"]["options"]
            diff = recursive_diff(current, cluster_dict)
            log.trace("diffs = %s", diff.diffs)
            if not (diff.diffs or (ldiff and ldiff.diffs)):
                # No differences
                comments.append(
                    "Cluster '{}' in datacenter '{}' is up to date. Nothing to be done.".format(
                        cluster_name, datacenter_name
                    )
                )
                log.info(comments[-1])
            else:
                changes_required = True
                changes_str = ""
                if diff.diffs:
                    changes_str = "{}{}".format(changes_str, diff.changes_str)
                if ldiff and ldiff.diffs:
                    changes_str = "{}\nha:\n  options:\n{}".format(
                        changes_str,
                        "\n".join(
                            ["  {}".format(l) for l in ldiff.changes_str2.split("\n")]
                        ),
                    )
                # Apply the changes
                if __opts__["test"]:
                    comments.append(
                        "State {} will update cluster '{}' in datacenter '{}':\n{}".format(
                            name, cluster_name, datacenter_name, changes_str
                        )
                    )
                else:
                    new_values = diff.new_values
                    old_values = diff.old_values
                    if ldiff and ldiff.new_values:
                        dictupdate.update(
                            new_values, {"ha": {"options": ldiff.new_values}}
                        )
                    if ldiff and ldiff.old_values:
                        dictupdate.update(
                            old_values, {"ha": {"options": ldiff.old_values}}
                        )
                    log.trace("new_values = %s", new_values)
                    __salt__["vsphere.update_cluster"](
                        new_values, datacenter_name, cluster_name, service_instance=si
                    )
                    comments.append(
                        "Updated cluster '{}' in datacenter '{}'".format(
                            cluster_name, datacenter_name
                        )
                    )
                    log.info(comments[-1])
                    changes.update({"new": new_values, "old": old_values})
        __salt__["vsphere.disconnect"](si)
        ret_status = True
        if __opts__["test"] and changes_required:
            ret_status = None
        ret.update(
            {"result": ret_status, "comment": "\n".join(comments), "changes": changes}
        )
        return ret
    except salt.exceptions.CommandExecutionError as exc:
        log.error("Error: %s", exc, exc_info=True)
        if si:
            __salt__["vsphere.disconnect"](si)
        ret.update({"result": False, "comment": str(exc)})
        return ret


def vsan_datastore_configured(name, datastore_name):
    """
    Configures the cluster's VSAN datastore

    WARNING: The VSAN datastore is created automatically after the first
    ESXi host is added to the cluster; the state assumes that the datastore
    exists and errors if it doesn't.
    """

    cluster_name, datacenter_name = (
        __salt__["esxcluster.get_details"]()["cluster"],
        __salt__["esxcluster.get_details"]()["datacenter"],
    )
    display_name = "{}/{}".format(datacenter_name, cluster_name)
    log.info("Running vsan_datastore_configured for '%s'", display_name)
    ret = {"name": name, "changes": {}, "result": None, "comment": "Default"}
    comments = []
    changes = {}
    changes_required = False

    try:
        si = __salt__["vsphere.get_service_instance_via_proxy"]()
        # Checking if we need to rename the vsan datastore
        vsan_ds = _get_vsan_datastore(si, cluster_name)
        if vsan_ds["name"] == datastore_name:
            comments.append(
                "vSAN datastore is correctly named '{}'. Nothing to be done.".format(
                    vsan_ds["name"]
                )
            )
            log.info(comments[-1])
        else:
            # vsan_ds needs to be updated
            changes_required = True
            if __opts__["test"]:
                comments.append(
                    "State {} will rename the vSAN datastore to '{}'.".format(
                        name, datastore_name
                    )
                )
                log.info(comments[-1])
            else:
                log.trace(
                    "Renaming vSAN datastore '%s' to '%s'",
                    vsan_ds["name"],
                    datastore_name,
                )
                __salt__["vsphere.rename_datastore"](
                    datastore_name=vsan_ds["name"],
                    new_datastore_name=datastore_name,
                    service_instance=si,
                )
                comments.append(
                    "Renamed vSAN datastore to '{}'.".format(datastore_name)
                )
                changes = {
                    "vsan_datastore": {
                        "new": {"name": datastore_name},
                        "old": {"name": vsan_ds["name"]},
                    }
                }
                log.info(comments[-1])
        __salt__["vsphere.disconnect"](si)

        ret.update(
            {
                "result": True
                if (not changes_required)
                else None
                if __opts__["test"]
                else True,
                "comment": "\n".join(comments),
                "changes": changes,
            }
        )
        return ret
    except salt.exceptions.CommandExecutionError as exc:
        log.error("Error: %s", exc, exc_info=True)
        if si:
            __salt__["vsphere.disconnect"](si)
        ret.update({"result": False, "comment": exc.strerror})
        return ret


def licenses_configured(name, licenses=None):
    """
    Configures licenses on the cluster entity

    Checks if each license exists on the server:
        - if it doesn't, it creates it
    Check if license is assigned to the cluster:
        - if it's not assigned to the cluster:
            - assign it to the cluster if there is space
            - error if there's no space
        - if it's assigned to the cluster nothing needs to be done
    """
    ret = {"name": name, "changes": {}, "result": None, "comment": "Default"}
    if not licenses:
        raise salt.exceptions.ArgumentValueError("No licenses provided")
    cluster_name, datacenter_name = (
        __salt__["esxcluster.get_details"]()["cluster"],
        __salt__["esxcluster.get_details"]()["datacenter"],
    )
    display_name = "{}/{}".format(datacenter_name, cluster_name)
    log.info("Running licenses configured for '%s'", display_name)
    log.trace("licenses = %s", licenses)
    entity = {"type": "cluster", "datacenter": datacenter_name, "cluster": cluster_name}
    log.trace("entity = %s", entity)

    comments = []
    changes = {}
    has_errors = False
    needs_changes = False
    try:
        # Validate licenses
        log.trace("Validating licenses")
        schema = LicenseSchema.serialize()
        try:
            jsonschema.validate({"licenses": licenses}, schema)
        except jsonschema.exceptions.ValidationError as exc:
            raise salt.exceptions.InvalidLicenseError(exc)

        si = __salt__["vsphere.get_service_instance_via_proxy"]()
        # Retrieve licenses
        existing_licenses = __salt__["vsphere.list_licenses"](service_instance=si)
        # Cycle through licenses
        for license_name, license in licenses.items():
            # Check if license already exists
            filtered_licenses = [l for l in existing_licenses if l["key"] == license]
            # TODO Update license description - not of interest right now
            if not filtered_licenses:
                # License doesn't exist - add and assign to cluster
                needs_changes = True
                if __opts__["test"]:
                    # If it doesn't exist it clearly needs to be assigned as
                    # well so we can stop the check here
                    comments.append(
                        "State {} will add license '{}', and assign it to cluster '{}'.".format(
                            name, license_name, display_name
                        )
                    )
                    log.info(comments[-1])
                    continue
                else:
                    try:
                        existing_license = __salt__["vsphere.add_license"](
                            key=license, description=license_name, service_instance=si
                        )
                    except salt.exceptions.VMwareApiError as ex:
                        comments.append(ex.err_msg)
                        log.error(comments[-1])
                        has_errors = True
                        continue
                    comments.append("Added license '{}'.".format(license_name))
                    log.info(comments[-1])
            else:
                # License exists let's check if it's assigned to the cluster
                comments.append(
                    "License '{}' already exists. Nothing to be done.".format(
                        license_name
                    )
                )
                log.info(comments[-1])
                existing_license = filtered_licenses[0]

            log.trace("Checking licensed entities...")
            assigned_licenses = __salt__["vsphere.list_assigned_licenses"](
                entity=entity, entity_display_name=display_name, service_instance=si
            )

            # Checking if any of the licenses already assigned have the same
            # name as the new license; the already assigned license would be
            # replaced by the new license
            #
            # Licenses with different names but matching features would be
            # replaced as well, but searching for those would be very complex
            #
            # the name check if good enough for now
            already_assigned_license = (
                assigned_licenses[0] if assigned_licenses else None
            )

            if already_assigned_license and already_assigned_license["key"] == license:

                # License is already assigned to entity
                comments.append(
                    "License '{}' already assigned to cluster '{}'. Nothing to be done.".format(
                        license_name, display_name
                    )
                )
                log.info(comments[-1])
                continue

            needs_changes = True
            # License needs to be assigned to entity

            if existing_license["capacity"] <= existing_license["used"]:
                # License is already fully used
                comments.append(
                    "Cannot assign license '{}' to cluster '{}'. No free capacity"
                    " available.".format(license_name, display_name)
                )
                log.error(comments[-1])
                has_errors = True
                continue

            # Assign license
            if __opts__["test"]:
                comments.append(
                    "State {} will assign license '{}' to cluster '{}'.".format(
                        name, license_name, display_name
                    )
                )
                log.info(comments[-1])
            else:
                try:
                    __salt__["vsphere.assign_license"](
                        license_key=license,
                        license_name=license_name,
                        entity=entity,
                        entity_display_name=display_name,
                        service_instance=si,
                    )
                except salt.exceptions.VMwareApiError as ex:
                    comments.append(ex.err_msg)
                    log.error(comments[-1])
                    has_errors = True
                    continue
                comments.append(
                    "Assigned license '{}' to cluster '{}'.".format(
                        license_name, display_name
                    )
                )
                log.info(comments[-1])
                # Note: Because the already_assigned_license was retrieved
                # from the assignment license manager it doesn't have a used
                # value - that's a limitation from VMware. The license would
                # need to be retrieved again from the license manager to get
                # the value

                # Hide license keys
                assigned_license = __salt__["vsphere.list_assigned_licenses"](
                    entity=entity, entity_display_name=display_name, service_instance=si
                )[0]
                assigned_license["key"] = "<hidden>"
                if already_assigned_license:
                    already_assigned_license["key"] = "<hidden>"
                if (
                    already_assigned_license
                    and already_assigned_license["capacity"] == sys.maxsize
                ):

                    already_assigned_license["capacity"] = "Unlimited"

                changes[license_name] = {
                    "new": assigned_license,
                    "old": already_assigned_license,
                }
            continue
        __salt__["vsphere.disconnect"](si)

        ret.update(
            {
                "result": True
                if (not needs_changes)
                else None
                if __opts__["test"]
                else False
                if has_errors
                else True,
                "comment": "\n".join(comments),
                "changes": changes if not __opts__["test"] else {},
            }
        )

        return ret
    except salt.exceptions.CommandExecutionError as exc:
        log.error("Error: %s", exc, exc_info=True)
        if si:
            __salt__["vsphere.disconnect"](si)
        ret.update({"result": False, "comment": exc.strerror})
        return ret
