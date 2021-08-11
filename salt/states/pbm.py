"""
Manages VMware storage policies
(called pbm because the vCenter endpoint is /pbm)

Examples
========

Storage policy
--------------

.. code-block:: python

    {
        "name": "salt_storage_policy"
        "description": "Managed by Salt. Random capability values.",
        "resource_type": "STORAGE",
        "subprofiles": [
            {
                "capabilities": [
                    {
                        "setting": {
                            "type": "scalar",
                            "value": 2
                        },
                        "namespace": "VSAN",
                        "id": "hostFailuresToTolerate"
                    },
                    {
                        "setting": {
                            "type": "scalar",
                            "value": 2
                        },
                        "namespace": "VSAN",
                        "id": "stripeWidth"
                    },
                    {
                        "setting": {
                            "type": "scalar",
                            "value": true
                        },
                        "namespace": "VSAN",
                        "id": "forceProvisioning"
                    },
                    {
                        "setting": {
                            "type": "scalar",
                            "value": 50
                        },
                        "namespace": "VSAN",
                        "id": "proportionalCapacity"
                    },
                    {
                        "setting": {
                            "type": "scalar",
                            "value": 0
                        },
                        "namespace": "VSAN",
                        "id": "cacheReservation"
                    }
                ],
                "name": "Rule-Set 1: VSAN",
                "force_provision": null
            }
        ],
    }

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
    versions of Python. If using version 6.0 of pyVmomi, Python 2.6,
    Python 2.7.9, or newer must be present. This is due to an upstream dependency
    in pyVmomi 6.0 that is not supported in Python versions 2.7 to 2.7.8. If the
    version of Python is not in the supported range, you will need to install an
    earlier version of pyVmomi. See
    `Issue #29537 <https://github.com/saltstack/salt/issues/29537>` for more
    information.
"""


import copy
import logging
import sys

from salt.exceptions import ArgumentValueError, CommandExecutionError
from salt.utils.dictdiffer import recursive_diff
from salt.utils.listdiffer import list_diff

# External libraries
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
    return True


def mod_init(low):
    """
    Init function
    """
    return True


def default_vsan_policy_configured(name, policy):
    """
    Configures the default VSAN policy on a vCenter.
    The state assumes there is only one default VSAN policy on a vCenter.

    policy
        Dict representation of a policy
    """
    # TODO Refactor when recurse_differ supports list_differ
    # It's going to make the whole thing much easier
    policy_copy = copy.deepcopy(policy)
    proxy_type = __salt__["vsphere.get_proxy_type"]()
    log.trace("proxy_type = %s", proxy_type)
    # All allowed proxies have a shim execution module with the same
    # name which implementes a get_details function
    # All allowed proxies have a vcenter detail
    vcenter = __salt__["{}.get_details".format(proxy_type)]()["vcenter"]
    log.info("Running %s on vCenter '%s'", name, vcenter)
    log.trace("policy = %s", policy)
    changes_required = False
    ret = {"name": name, "changes": {}, "result": None, "comment": None}
    comments = []
    changes = {}
    changes_required = False
    si = None

    try:
        # TODO policy schema validation
        si = __salt__["vsphere.get_service_instance_via_proxy"]()
        current_policy = __salt__["vsphere.list_default_vsan_policy"](si)
        log.trace("current_policy = %s", current_policy)
        # Building all diffs between the current and expected policy
        # XXX We simplify the comparison by assuming we have at most 1
        # sub_profile
        if policy.get("subprofiles"):
            if len(policy["subprofiles"]) > 1:
                raise ArgumentValueError(
                    "Multiple sub_profiles ({0}) are not supported in the input policy"
                )
            subprofile = policy["subprofiles"][0]
            current_subprofile = current_policy["subprofiles"][0]
            capabilities_differ = list_diff(
                current_subprofile["capabilities"],
                subprofile.get("capabilities", []),
                key="id",
            )
            del policy["subprofiles"]
            if subprofile.get("capabilities"):
                del subprofile["capabilities"]
            del current_subprofile["capabilities"]
            # Get the subprofile diffs without the capability keys
            subprofile_differ = recursive_diff(current_subprofile, dict(subprofile))

        del current_policy["subprofiles"]
        policy_differ = recursive_diff(current_policy, policy)
        if policy_differ.diffs or capabilities_differ.diffs or subprofile_differ.diffs:

            if (
                "name" in policy_differ.new_values
                or "description" in policy_differ.new_values
            ):

                raise ArgumentValueError(
                    "'name' and 'description' of the default VSAN policy "
                    "cannot be updated"
                )
            changes_required = True
            if __opts__["test"]:
                str_changes = []
                if policy_differ.diffs:
                    str_changes.extend(
                        [change for change in policy_differ.changes_str.split("\n")]
                    )
                if subprofile_differ.diffs or capabilities_differ.diffs:
                    str_changes.append("subprofiles:")
                    if subprofile_differ.diffs:
                        str_changes.extend(
                            [
                                "  {}".format(change)
                                for change in subprofile_differ.changes_str.split("\n")
                            ]
                        )
                    if capabilities_differ.diffs:
                        str_changes.append("  capabilities:")
                        str_changes.extend(
                            [
                                "  {}".format(change)
                                for change in capabilities_differ.changes_str2.split(
                                    "\n"
                                )
                            ]
                        )
                comments.append(
                    "State {} will update the default VSAN policy on "
                    "vCenter '{}':\n{}"
                    "".format(name, vcenter, "\n".join(str_changes))
                )
            else:
                __salt__["vsphere.update_storage_policy"](
                    policy=current_policy["name"],
                    policy_dict=policy_copy,
                    service_instance=si,
                )
                comments.append(
                    "Updated the default VSAN policy in vCenter '{}'".format(vcenter)
                )
            log.info(comments[-1])

            new_values = policy_differ.new_values
            new_values["subprofiles"] = [subprofile_differ.new_values]
            new_values["subprofiles"][0][
                "capabilities"
            ] = capabilities_differ.new_values
            if not new_values["subprofiles"][0]["capabilities"]:
                del new_values["subprofiles"][0]["capabilities"]
            if not new_values["subprofiles"][0]:
                del new_values["subprofiles"]
            old_values = policy_differ.old_values
            old_values["subprofiles"] = [subprofile_differ.old_values]
            old_values["subprofiles"][0][
                "capabilities"
            ] = capabilities_differ.old_values
            if not old_values["subprofiles"][0]["capabilities"]:
                del old_values["subprofiles"][0]["capabilities"]
            if not old_values["subprofiles"][0]:
                del old_values["subprofiles"]
            changes.update(
                {"default_vsan_policy": {"new": new_values, "old": old_values}}
            )
            log.trace(changes)
        __salt__["vsphere.disconnect"](si)
    except CommandExecutionError as exc:
        log.error("Error: %s", exc)
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
                    "Default VSAN policy in vCenter "
                    "'{}' is correctly configured. "
                    "Nothing to be done.".format(vcenter)
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


def storage_policies_configured(name, policies):
    """
    Configures storage policies on a vCenter.

    policies
        List of dict representation of the required storage policies
    """
    comments = []
    changes = []
    changes_required = False
    ret = {"name": name, "changes": {}, "result": None, "comment": None}
    log.trace("policies = %s", policies)
    si = None
    try:
        proxy_type = __salt__["vsphere.get_proxy_type"]()
        log.trace("proxy_type = %s", proxy_type)
        # All allowed proxies have a shim execution module with the same
        # name which implementes a get_details function
        # All allowed proxies have a vcenter detail
        vcenter = __salt__["{}.get_details".format(proxy_type)]()["vcenter"]
        log.info("Running state '%s' on vCenter '%s'", name, vcenter)
        si = __salt__["vsphere.get_service_instance_via_proxy"]()
        current_policies = __salt__["vsphere.list_storage_policies"](
            policy_names=[policy["name"] for policy in policies], service_instance=si
        )
        log.trace("current_policies = %s", current_policies)
        # TODO Refactor when recurse_differ supports list_differ
        # It's going to make the whole thing much easier
        for policy in policies:
            policy_copy = copy.deepcopy(policy)
            filtered_policies = [
                p for p in current_policies if p["name"] == policy["name"]
            ]
            current_policy = filtered_policies[0] if filtered_policies else None

            if not current_policy:
                changes_required = True
                if __opts__["test"]:
                    comments.append(
                        "State {} will create the storage policy "
                        "'{}' on vCenter '{}'"
                        "".format(name, policy["name"], vcenter)
                    )
                else:
                    __salt__["vsphere.create_storage_policy"](
                        policy["name"], policy, service_instance=si
                    )
                    comments.append(
                        "Created storage policy '{}' on vCenter '{}'".format(
                            policy["name"], vcenter
                        )
                    )
                    changes.append({"new": policy, "old": None})
                log.trace(comments[-1])
                # Continue with next
                continue

            # Building all diffs between the current and expected policy
            # XXX We simplify the comparison by assuming we have at most 1
            # sub_profile
            if policy.get("subprofiles"):
                if len(policy["subprofiles"]) > 1:
                    raise ArgumentValueError(
                        "Multiple sub_profiles ({0}) are not "
                        "supported in the input policy"
                    )
                subprofile = policy["subprofiles"][0]
                current_subprofile = current_policy["subprofiles"][0]
                capabilities_differ = list_diff(
                    current_subprofile["capabilities"],
                    subprofile.get("capabilities", []),
                    key="id",
                )
                del policy["subprofiles"]
                if subprofile.get("capabilities"):
                    del subprofile["capabilities"]
                del current_subprofile["capabilities"]
                # Get the subprofile diffs without the capability keys
                subprofile_differ = recursive_diff(current_subprofile, dict(subprofile))

            del current_policy["subprofiles"]
            policy_differ = recursive_diff(current_policy, policy)
            if (
                policy_differ.diffs
                or capabilities_differ.diffs
                or subprofile_differ.diffs
            ):

                changes_required = True
                if __opts__["test"]:
                    str_changes = []
                    if policy_differ.diffs:
                        str_changes.extend(
                            [change for change in policy_differ.changes_str.split("\n")]
                        )
                    if subprofile_differ.diffs or capabilities_differ.diffs:

                        str_changes.append("subprofiles:")
                        if subprofile_differ.diffs:
                            str_changes.extend(
                                [
                                    "  {}".format(change)
                                    for change in subprofile_differ.changes_str.split(
                                        "\n"
                                    )
                                ]
                            )
                        if capabilities_differ.diffs:
                            str_changes.append("  capabilities:")
                            str_changes.extend(
                                [
                                    "  {}".format(change)
                                    for change in capabilities_differ.changes_str2.split(
                                        "\n"
                                    )
                                ]
                            )
                    comments.append(
                        "State {} will update the storage policy '{}'"
                        " on vCenter '{}':\n{}"
                        "".format(name, policy["name"], vcenter, "\n".join(str_changes))
                    )
                else:
                    __salt__["vsphere.update_storage_policy"](
                        policy=current_policy["name"],
                        policy_dict=policy_copy,
                        service_instance=si,
                    )
                    comments.append(
                        "Updated the storage policy '{}' in vCenter '{}'".format(
                            policy["name"], vcenter
                        )
                    )
                log.info(comments[-1])

                # Build new/old values to report what was changed
                new_values = policy_differ.new_values
                new_values["subprofiles"] = [subprofile_differ.new_values]
                new_values["subprofiles"][0][
                    "capabilities"
                ] = capabilities_differ.new_values
                if not new_values["subprofiles"][0]["capabilities"]:
                    del new_values["subprofiles"][0]["capabilities"]
                if not new_values["subprofiles"][0]:
                    del new_values["subprofiles"]
                old_values = policy_differ.old_values
                old_values["subprofiles"] = [subprofile_differ.old_values]
                old_values["subprofiles"][0][
                    "capabilities"
                ] = capabilities_differ.old_values
                if not old_values["subprofiles"][0]["capabilities"]:
                    del old_values["subprofiles"][0]["capabilities"]
                if not old_values["subprofiles"][0]:
                    del old_values["subprofiles"]
                changes.append({"new": new_values, "old": old_values})
            else:
                # No diffs found - no updates required
                comments.append(
                    "Storage policy '{}' is up to date. Nothing to be done.".format(
                        policy["name"]
                    )
                )
        __salt__["vsphere.disconnect"](si)
    except CommandExecutionError as exc:
        log.error("Error: %s", exc)
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
                    "All storage policy in vCenter "
                    "'{}' is correctly configured. "
                    "Nothing to be done.".format(vcenter)
                ),
                "result": True,
            }
        )
    else:
        ret.update(
            {
                "comment": "\n".join(comments),
                "changes": {"storage_policies": changes},
                "result": None if __opts__["test"] else True,
            }
        )
    return ret


def default_storage_policy_assigned(name, policy, datastore):
    """
    Assigns a default storage policy to a datastore

    policy
        Name of storage policy

    datastore
        Name of datastore
    """
    log.info(
        "Running state %s for policy '%s', datastore '%s'.", name, policy, datastore
    )
    changes = {}
    changes_required = False
    ret = {"name": name, "changes": {}, "result": None, "comment": None}
    si = None
    try:
        si = __salt__["vsphere.get_service_instance_via_proxy"]()
        existing_policy = __salt__["vsphere.list_default_storage_policy_of_datastore"](
            datastore=datastore, service_instance=si
        )
        if existing_policy["name"] == policy:
            comment = (
                "Storage policy '{}' is already assigned to "
                "datastore '{}'. Nothing to be done."
                "".format(policy, datastore)
            )
        else:
            changes_required = True
            changes = {
                "default_storage_policy": {
                    "old": existing_policy["name"],
                    "new": policy,
                }
            }
            if __opts__["test"]:
                comment = "State {} will assign storage policy '{}' to datastore '{}'.".format(
                    name, policy, datastore
                )
            else:
                __salt__["vsphere.assign_default_storage_policy_to_datastore"](
                    policy=policy, datastore=datastore, service_instance=si
                )
                comment = "Storage policy '{} was assigned to datastore '{}'.".format(
                    policy, name
                )
        log.info(comment)
    except CommandExecutionError as exc:
        log.error("Error: %s", exc)
        if si:
            __salt__["vsphere.disconnect"](si)
        ret.update(
            {"comment": exc.strerror, "result": False if not __opts__["test"] else None}
        )
        return ret

    ret["comment"] = comment
    if changes_required:
        ret.update({"changes": changes, "result": None if __opts__["test"] else True})
    else:
        ret["result"] = True
    return ret
