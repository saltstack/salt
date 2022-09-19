"""
Azure (ARM) DNS State Module

.. versionadded:: 3000

.. warning::

    This cloud provider will be removed from Salt in version 3007 in favor of
    the `saltext.azurerm Salt Extension
    <https://github.com/salt-extensions/saltext-azurerm>`_

:maintainer: <devops@eitr.tech>
:maturity: new
:depends:
    * `azure <https://pypi.python.org/pypi/azure>`_ >= 2.0.0
    * `azure-common <https://pypi.python.org/pypi/azure-common>`_ >= 1.1.8
    * `azure-mgmt <https://pypi.python.org/pypi/azure-mgmt>`_ >= 1.0.0
    * `azure-mgmt-compute <https://pypi.python.org/pypi/azure-mgmt-compute>`_ >= 1.0.0
    * `azure-mgmt-dns <https://pypi.python.org/pypi/azure-mgmt-dns>`_ >= 1.0.1
    * `azure-mgmt-network <https://pypi.python.org/pypi/azure-mgmt-network>`_ >= 1.7.1
    * `azure-mgmt-resource <https://pypi.python.org/pypi/azure-mgmt-resource>`_ >= 1.1.0
    * `azure-mgmt-storage <https://pypi.python.org/pypi/azure-mgmt-storage>`_ >= 1.0.0
    * `azure-mgmt-web <https://pypi.python.org/pypi/azure-mgmt-web>`_ >= 0.32.0
    * `azure-storage <https://pypi.python.org/pypi/azure-storage>`_ >= 0.34.3
    * `msrestazure <https://pypi.python.org/pypi/msrestazure>`_ >= 0.4.21

:platform: linux

:configuration:
    This module requires Azure Resource Manager credentials to be passed as a dictionary of
    keyword arguments to the ``connection_auth`` parameter in order to work properly. Since the authentication
    parameters are sensitive, it's recommended to pass them to the states via pillar.

Required provider parameters:

    if using username and password:

        * ``subscription_id``
        * ``username``
        * ``password``

    if using a service principal:

        * ``subscription_id``
        * ``tenant``
        * ``client_id``
        * ``secret``

Optional provider parameters:

    **cloud_environment**: Used to point the cloud driver to different API endpoints, such as Azure GovCloud. Possible values:

    Possible values:

        * ``AZURE_PUBLIC_CLOUD`` (default)
        * ``AZURE_CHINA_CLOUD``
        * ``AZURE_US_GOV_CLOUD``
        * ``AZURE_GERMAN_CLOUD``

    Example Pillar for Azure Resource Manager authentication:

    .. code-block:: yaml

        azurearm:
            user_pass_auth:
                subscription_id: 3287abc8-f98a-c678-3bde-326766fd3617
                username: fletch
                password: 123pass
            mysubscription:
                subscription_id: 3287abc8-f98a-c678-3bde-326766fd3617
                tenant: ABCDEFAB-1234-ABCD-1234-ABCDEFABCDEF
                client_id: ABCDEFAB-1234-ABCD-1234-ABCDEFABCDEF
                secret: XXXXXXXXXXXXXXXXXXXXXXXX
                cloud_environment: AZURE_PUBLIC_CLOUD

    Example states using Azure Resource Manager authentication:

    .. code-block:: none

        {% set profile = salt['pillar.get']('azurearm:mysubscription') %}
        Ensure DNS zone exists:
            azurearm_dns.zone_present:
                - name: contoso.com
                - resource_group: my_rg
                - tags:
                    how_awesome: very
                    contact_name: Elmer Fudd Gantry
                - connection_auth: {{ profile }}

        Ensure DNS record set exists:
            azurearm_dns.record_set_present:
                - name: web
                - zone_name: contoso.com
                - resource_group: my_rg
                - record_type: A
                - ttl: 300
                - arecords:
                  - ipv4_address: 10.0.0.1
                - tags:
                    how_awesome: very
                    contact_name: Elmer Fudd Gantry
                - connection_auth: {{ profile }}

        Ensure DNS record set is absent:
            azurearm_dns.record_set_absent:
                - name: web
                - zone_name: contoso.com
                - resource_group: my_rg
                - record_type: A
                - connection_auth: {{ profile }}

        Ensure DNS zone is absent:
            azurearm_dns.zone_absent:
                - name: contoso.com
                - resource_group: my_rg
                - connection_auth: {{ profile }}

"""
import logging
from functools import wraps

import salt.utils.azurearm

__virtualname__ = "azurearm_dns"

log = logging.getLogger(__name__)


def __virtual__():
    """
    Only make this state available if the azurearm_dns module is available.
    """
    if "azurearm_dns.zones_list_by_resource_group" in __salt__:
        return __virtualname__
    return (False, "azurearm_dns module could not be loaded")


def _deprecation_message(function):
    """
    Decorator wrapper to warn about azurearm deprecation
    """

    @wraps(function)
    def wrapped(*args, **kwargs):
        salt.utils.versions.warn_until(
            "Chlorine",
            "The 'azurearm' functionality in Salt has been deprecated and its "
            "functionality will be removed in version 3007 in favor of the "
            "saltext.azurerm Salt Extension. "
            "(https://github.com/salt-extensions/saltext-azurerm)",
            category=FutureWarning,
        )
        ret = function(*args, **salt.utils.args.clean_kwargs(**kwargs))
        return ret

    return wrapped


@_deprecation_message
def zone_present(
    name,
    resource_group,
    etag=None,
    if_match=None,
    if_none_match=None,
    registration_virtual_networks=None,
    resolution_virtual_networks=None,
    tags=None,
    zone_type="Public",
    connection_auth=None,
    **kwargs
):
    """
    .. versionadded:: 3000

    Ensure a DNS zone exists.

    :param name:
        Name of the DNS zone (without a terminating dot).

    :param resource_group:
        The resource group assigned to the DNS zone.

    :param etag:
        The etag of the zone. `Etags <https://docs.microsoft.com/en-us/azure/dns/dns-zones-records#etags>`_ are used
        to handle concurrent changes to the same resource safely.

    :param if_match:
        The etag of the DNS zone. Omit this value to always overwrite the current zone. Specify the last-seen etag
        value to prevent accidentally overwritting any concurrent changes.

    :param if_none_match:
        Set to '*' to allow a new DNS zone to be created, but to prevent updating an existing zone. Other values will
        be ignored.

    :param registration_virtual_networks:
        A list of references to virtual networks that register hostnames in this DNS zone. This is only when zone_type
        is Private. (requires `azure-mgmt-dns <https://pypi.python.org/pypi/azure-mgmt-dns>`_ >= 2.0.0rc1)

    :param resolution_virtual_networks:
        A list of references to virtual networks that resolve records in this DNS zone. This is only when zone_type is
        Private. (requires `azure-mgmt-dns <https://pypi.python.org/pypi/azure-mgmt-dns>`_ >= 2.0.0rc1)

    :param tags:
        A dictionary of strings can be passed as tag metadata to the DNS zone object.

    :param zone_type:
        The type of this DNS zone (Public or Private). Possible values include: 'Public', 'Private'. Default value: 'Public'
         (requires `azure-mgmt-dns <https://pypi.python.org/pypi/azure-mgmt-dns>`_ >= 2.0.0rc1)

    :param connection_auth:
        A dict with subscription and authentication parameters to be used in connecting to the
        Azure Resource Manager API.

    Example usage:

    .. code-block:: yaml

        Ensure DNS zone exists:
            azurearm_dns.zone_present:
                - name: contoso.com
                - resource_group: my_rg
                - zone_type: Private
                - registration_virtual_networks:
                  - /subscriptions/{{ sub }}/resourceGroups/my_rg/providers/Microsoft.Network/virtualNetworks/test_vnet
                - tags:
                    how_awesome: very
                    contact_name: Elmer Fudd Gantry
                - connection_auth: {{ profile }}

    """
    ret = {"name": name, "result": False, "comment": "", "changes": {}}

    if not isinstance(connection_auth, dict):
        ret[
            "comment"
        ] = "Connection information must be specified via connection_auth dictionary!"
        return ret

    zone = __salt__["azurearm_dns.zone_get"](
        name, resource_group, azurearm_log_level="info", **connection_auth
    )

    if "error" not in zone:
        tag_changes = __utils__["dictdiffer.deep_diff"](
            zone.get("tags", {}), tags or {}
        )
        if tag_changes:
            ret["changes"]["tags"] = tag_changes

        # The zone_type parameter is only accessible in azure-mgmt-dns >=2.0.0rc1
        if zone.get("zone_type"):
            if zone.get("zone_type").lower() != zone_type.lower():
                ret["changes"]["zone_type"] = {
                    "old": zone["zone_type"],
                    "new": zone_type,
                }

            if zone_type.lower() == "private":
                # The registration_virtual_networks parameter is only accessible in azure-mgmt-dns >=2.0.0rc1
                if registration_virtual_networks and not isinstance(
                    registration_virtual_networks, list
                ):
                    ret["comment"] = (
                        "registration_virtual_networks must be supplied as a list of"
                        " VNET ID paths!"
                    )
                    return ret
                reg_vnets = zone.get("registration_virtual_networks", [])
                remote_reg_vnets = sorted(
                    vnet["id"].lower() for vnet in reg_vnets if "id" in vnet
                )
                local_reg_vnets = sorted(
                    vnet.lower() for vnet in registration_virtual_networks or []
                )
                if local_reg_vnets != remote_reg_vnets:
                    ret["changes"]["registration_virtual_networks"] = {
                        "old": remote_reg_vnets,
                        "new": local_reg_vnets,
                    }

                # The resolution_virtual_networks parameter is only accessible in azure-mgmt-dns >=2.0.0rc1
                if resolution_virtual_networks and not isinstance(
                    resolution_virtual_networks, list
                ):
                    ret["comment"] = (
                        "resolution_virtual_networks must be supplied as a list of VNET"
                        " ID paths!"
                    )
                    return ret
                res_vnets = zone.get("resolution_virtual_networks", [])
                remote_res_vnets = sorted(
                    vnet["id"].lower() for vnet in res_vnets if "id" in vnet
                )
                local_res_vnets = sorted(
                    vnet.lower() for vnet in resolution_virtual_networks or []
                )
                if local_res_vnets != remote_res_vnets:
                    ret["changes"]["resolution_virtual_networks"] = {
                        "old": remote_res_vnets,
                        "new": local_res_vnets,
                    }

        if not ret["changes"]:
            ret["result"] = True
            ret["comment"] = "DNS zone {} is already present.".format(name)
            return ret

        if __opts__["test"]:
            ret["result"] = None
            ret["comment"] = "DNS zone {} would be updated.".format(name)
            return ret

    else:
        ret["changes"] = {
            "old": {},
            "new": {
                "name": name,
                "resource_group": resource_group,
                "etag": etag,
                "registration_virtual_networks": registration_virtual_networks,
                "resolution_virtual_networks": resolution_virtual_networks,
                "tags": tags,
                "zone_type": zone_type,
            },
        }

    if __opts__["test"]:
        ret["comment"] = "DNS zone {} would be created.".format(name)
        ret["result"] = None
        return ret

    zone_kwargs = kwargs.copy()
    zone_kwargs.update(connection_auth)

    zone = __salt__["azurearm_dns.zone_create_or_update"](
        name=name,
        resource_group=resource_group,
        etag=etag,
        if_match=if_match,
        if_none_match=if_none_match,
        registration_virtual_networks=registration_virtual_networks,
        resolution_virtual_networks=resolution_virtual_networks,
        tags=tags,
        zone_type=zone_type,
        **zone_kwargs
    )

    if "error" not in zone:
        ret["result"] = True
        ret["comment"] = "DNS zone {} has been created.".format(name)
        return ret

    ret["comment"] = "Failed to create DNS zone {}! ({})".format(
        name, zone.get("error")
    )
    return ret


@_deprecation_message
def zone_absent(name, resource_group, connection_auth=None):
    """
    .. versionadded:: 3000

    Ensure a DNS zone does not exist in the resource group.

    :param name:
        Name of the DNS zone.

    :param resource_group:
        The resource group assigned to the DNS zone.

    :param connection_auth:
        A dict with subscription and authentication parameters to be used in connecting to the
        Azure Resource Manager API.
    """
    ret = {"name": name, "result": False, "comment": "", "changes": {}}

    if not isinstance(connection_auth, dict):
        ret[
            "comment"
        ] = "Connection information must be specified via connection_auth dictionary!"
        return ret

    zone = __salt__["azurearm_dns.zone_get"](
        name, resource_group, azurearm_log_level="info", **connection_auth
    )

    if "error" in zone:
        ret["result"] = True
        ret["comment"] = "DNS zone {} was not found.".format(name)
        return ret

    elif __opts__["test"]:
        ret["comment"] = "DNS zone {} would be deleted.".format(name)
        ret["result"] = None
        ret["changes"] = {
            "old": zone,
            "new": {},
        }
        return ret

    deleted = __salt__["azurearm_dns.zone_delete"](
        name, resource_group, **connection_auth
    )

    if deleted:
        ret["result"] = True
        ret["comment"] = "DNS zone {} has been deleted.".format(name)
        ret["changes"] = {"old": zone, "new": {}}
        return ret

    ret["comment"] = "Failed to delete DNS zone {}!".format(name)
    return ret


@_deprecation_message
def record_set_present(
    name,
    zone_name,
    resource_group,
    record_type,
    if_match=None,
    if_none_match=None,
    etag=None,
    metadata=None,
    ttl=None,
    arecords=None,
    aaaa_records=None,
    mx_records=None,
    ns_records=None,
    ptr_records=None,
    srv_records=None,
    txt_records=None,
    cname_record=None,
    soa_record=None,
    caa_records=None,
    connection_auth=None,
    **kwargs
):
    """
    .. versionadded:: 3000

    Ensure a record set exists in a DNS zone.

    :param name:
        The name of the record set, relative to the name of the zone.

    :param zone_name:
        Name of the DNS zone (without a terminating dot).

    :param resource_group:
        The resource group assigned to the DNS zone.

    :param record_type:
        The type of DNS record in this record set. Record sets of type SOA can be updated but not created
        (they are created when the DNS zone is created). Possible values include: 'A', 'AAAA', 'CAA', 'CNAME',
        'MX', 'NS', 'PTR', 'SOA', 'SRV', 'TXT'

    :param if_match:
        The etag of the record set. Omit this value to always overwrite the current record set. Specify the last-seen
        etag value to prevent accidentally overwritting any concurrent changes.

    :param if_none_match:
        Set to '*' to allow a new record set to be created, but to prevent updating an existing record set. Other values
        will be ignored.

    :param etag:
        The etag of the record set. `Etags <https://docs.microsoft.com/en-us/azure/dns/dns-zones-records#etags>`__ are
        used to handle concurrent changes to the same resource safely.

    :param metadata:
        A dictionary of strings can be passed as tag metadata to the record set object.

    :param ttl:
        The TTL (time-to-live) of the records in the record set. Required when specifying record information.

    :param arecords:
        The list of A records in the record set. View the
        `Azure SDK documentation <https://docs.microsoft.com/en-us/python/api/azure.mgmt.dns.models.arecord?view=azure-python>`__
        to create a list of dictionaries representing the record objects.

    :param aaaa_records:
        The list of AAAA records in the record set. View the
        `Azure SDK documentation <https://docs.microsoft.com/en-us/python/api/azure.mgmt.dns.models.aaaarecord?view=azure-python>`__
        to create a list of dictionaries representing the record objects.

    :param mx_records:
        The list of MX records in the record set. View the
        `Azure SDK documentation <https://docs.microsoft.com/en-us/python/api/azure.mgmt.dns.models.mxrecord?view=azure-python>`__
        to create a list of dictionaries representing the record objects.

    :param ns_records:
        The list of NS records in the record set. View the
        `Azure SDK documentation <https://docs.microsoft.com/en-us/python/api/azure.mgmt.dns.models.nsrecord?view=azure-python>`__
        to create a list of dictionaries representing the record objects.

    :param ptr_records:
        The list of PTR records in the record set. View the
        `Azure SDK documentation <https://docs.microsoft.com/en-us/python/api/azure.mgmt.dns.models.ptrrecord?view=azure-python>`__
        to create a list of dictionaries representing the record objects.

    :param srv_records:
        The list of SRV records in the record set. View the
        `Azure SDK documentation <https://docs.microsoft.com/en-us/python/api/azure.mgmt.dns.models.srvrecord?view=azure-python>`__
        to create a list of dictionaries representing the record objects.

    :param txt_records:
        The list of TXT records in the record set. View the
        `Azure SDK documentation <https://docs.microsoft.com/en-us/python/api/azure.mgmt.dns.models.txtrecord?view=azure-python>`__
        to create a list of dictionaries representing the record objects.

    :param cname_record:
        The CNAME record in the record set. View the
        `Azure SDK documentation <https://docs.microsoft.com/en-us/python/api/azure.mgmt.dns.models.cnamerecord?view=azure-python>`__
        to create a dictionary representing the record object.

    :param soa_record:
        The SOA record in the record set. View the
        `Azure SDK documentation <https://docs.microsoft.com/en-us/python/api/azure.mgmt.dns.models.soarecord?view=azure-python>`__
        to create a dictionary representing the record object.

    :param caa_records:
        The list of CAA records in the record set. View the
        `Azure SDK documentation <https://docs.microsoft.com/en-us/python/api/azure.mgmt.dns.models.caarecord?view=azure-python>`__
        to create a list of dictionaries representing the record objects.

    :param connection_auth:
        A dict with subscription and authentication parameters to be used in connecting to the
        Azure Resource Manager API.

    Example usage:

    .. code-block:: yaml

        Ensure record set exists:
            azurearm_dns.record_set_present:
                - name: web
                - zone_name: contoso.com
                - resource_group: my_rg
                - record_type: A
                - ttl: 300
                - arecords:
                  - ipv4_address: 10.0.0.1
                - metadata:
                    how_awesome: very
                    contact_name: Elmer Fudd Gantry
                - connection_auth: {{ profile }}

    """
    ret = {"name": name, "result": False, "comment": "", "changes": {}}

    record_vars = [
        "arecords",
        "aaaa_records",
        "mx_records",
        "ns_records",
        "ptr_records",
        "srv_records",
        "txt_records",
        "cname_record",
        "soa_record",
        "caa_records",
    ]

    if not isinstance(connection_auth, dict):
        ret[
            "comment"
        ] = "Connection information must be specified via connection_auth dictionary!"
        return ret

    rec_set = __salt__["azurearm_dns.record_set_get"](
        name,
        zone_name,
        resource_group,
        record_type,
        azurearm_log_level="info",
        **connection_auth
    )

    if "error" not in rec_set:
        metadata_changes = __utils__["dictdiffer.deep_diff"](
            rec_set.get("metadata", {}), metadata or {}
        )
        if metadata_changes:
            ret["changes"]["metadata"] = metadata_changes

        for record_str in record_vars:
            # pylint: disable=eval-used
            record = eval(record_str)
            if record:
                if not ttl:
                    ret[
                        "comment"
                    ] = "TTL is required when specifying record information!"
                    return ret
                if not rec_set.get(record_str):
                    ret["changes"] = {"new": {record_str: record}}
                    continue
                if record_str[-1] != "s":
                    if not isinstance(record, dict):
                        ret[
                            "comment"
                        ] = "{} record information must be specified as a dictionary!".format(
                            record_str
                        )
                        return ret
                    for k, v in record.items():
                        if v != rec_set[record_str].get(k):
                            ret["changes"] = {"new": {record_str: record}}
                elif record_str[-1] == "s":
                    if not isinstance(record, list):
                        ret["comment"] = (
                            "{} record information must be specified as a list of"
                            " dictionaries!".format(record_str)
                        )
                        return ret
                    local, remote = (
                        sorted(config) for config in (record, rec_set[record_str])
                    )
                    for val in local:
                        for key in val:
                            local_val = val[key]
                            remote_val = remote.get(key)
                            if isinstance(local_val, str):
                                local_val = local_val.lower()
                            if isinstance(remote_val, str):
                                remote_val = remote_val.lower()
                            if local_val != remote_val:
                                ret["changes"] = {"new": {record_str: record}}

        if not ret["changes"]:
            ret["result"] = True
            ret["comment"] = "Record set {} is already present.".format(name)
            return ret

        if __opts__["test"]:
            ret["result"] = None
            ret["comment"] = "Record set {} would be updated.".format(name)
            return ret

    else:
        ret["changes"] = {
            "old": {},
            "new": {
                "name": name,
                "zone_name": zone_name,
                "resource_group": resource_group,
                "record_type": record_type,
                "etag": etag,
                "metadata": metadata,
                "ttl": ttl,
            },
        }
        for record in record_vars:
            # pylint: disable=eval-used
            if eval(record):
                # pylint: disable=eval-used
                ret["changes"]["new"][record] = eval(record)

    if __opts__["test"]:
        ret["comment"] = "Record set {} would be created.".format(name)
        ret["result"] = None
        return ret

    rec_set_kwargs = kwargs.copy()
    rec_set_kwargs.update(connection_auth)

    rec_set = __salt__["azurearm_dns.record_set_create_or_update"](
        name=name,
        zone_name=zone_name,
        resource_group=resource_group,
        record_type=record_type,
        if_match=if_match,
        if_none_match=if_none_match,
        etag=etag,
        ttl=ttl,
        metadata=metadata,
        arecords=arecords,
        aaaa_records=aaaa_records,
        mx_records=mx_records,
        ns_records=ns_records,
        ptr_records=ptr_records,
        srv_records=srv_records,
        txt_records=txt_records,
        cname_record=cname_record,
        soa_record=soa_record,
        caa_records=caa_records,
        **rec_set_kwargs
    )

    if "error" not in rec_set:
        ret["result"] = True
        ret["comment"] = "Record set {} has been created.".format(name)
        return ret

    ret["comment"] = "Failed to create record set {}! ({})".format(
        name, rec_set.get("error")
    )
    return ret


@_deprecation_message
def record_set_absent(name, zone_name, resource_group, connection_auth=None):
    """
    .. versionadded:: 3000

    Ensure a record set does not exist in the DNS zone.

    :param name:
        Name of the record set.

    :param zone_name:
        Name of the DNS zone.

    :param resource_group:
        The resource group assigned to the DNS zone.

    :param connection_auth:
        A dict with subscription and authentication parameters to be used in connecting to the
        Azure Resource Manager API.
    """
    ret = {"name": name, "result": False, "comment": "", "changes": {}}

    if not isinstance(connection_auth, dict):
        ret[
            "comment"
        ] = "Connection information must be specified via connection_auth dictionary!"
        return ret

    rec_set = __salt__["azurearm_dns.record_set_get"](
        name, zone_name, resource_group, azurearm_log_level="info", **connection_auth
    )

    if "error" in rec_set:
        ret["result"] = True
        ret["comment"] = "Record set {} was not found in zone {}.".format(
            name, zone_name
        )
        return ret

    elif __opts__["test"]:
        ret["comment"] = "Record set {} would be deleted.".format(name)
        ret["result"] = None
        ret["changes"] = {
            "old": rec_set,
            "new": {},
        }
        return ret

    deleted = __salt__["azurearm_dns.record_set_delete"](
        name, zone_name, resource_group, **connection_auth
    )

    if deleted:
        ret["result"] = True
        ret["comment"] = "Record set {} has been deleted.".format(name)
        ret["changes"] = {"old": rec_set, "new": {}}
        return ret

    ret["comment"] = "Failed to delete record set {}!".format(name)
    return ret
