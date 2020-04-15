# -*- coding: utf-8 -*-
"""
Azure (ARM) Network Execution Module

.. versionadded:: 2019.2.0

:maintainer: <devops@decisionlab.io>
:maturity: new
:depends:
    * `azure <https://pypi.python.org/pypi/azure>`_ >= 2.0.0
    * `azure-common <https://pypi.python.org/pypi/azure-common>`_ >= 1.1.8
    * `azure-mgmt <https://pypi.python.org/pypi/azure-mgmt>`_ >= 1.0.0
    * `azure-mgmt-compute <https://pypi.python.org/pypi/azure-mgmt-compute>`_ >= 1.0.0
    * `azure-mgmt-network <https://pypi.python.org/pypi/azure-mgmt-network>`_ >= 1.7.1
    * `azure-mgmt-resource <https://pypi.python.org/pypi/azure-mgmt-resource>`_ >= 1.1.0
    * `azure-mgmt-storage <https://pypi.python.org/pypi/azure-mgmt-storage>`_ >= 1.0.0
    * `azure-mgmt-web <https://pypi.python.org/pypi/azure-mgmt-web>`_ >= 0.32.0
    * `azure-storage <https://pypi.python.org/pypi/azure-storage>`_ >= 0.34.3
    * `msrestazure <https://pypi.python.org/pypi/msrestazure>`_ >= 0.4.21
:platform: linux

:configuration: This module requires Azure Resource Manager credentials to be passed as keyword arguments
    to every function in order to work properly.

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

**cloud_environment**: Used to point the cloud driver to different API endpoints, such as Azure GovCloud.
    Possible values:
      * ``AZURE_PUBLIC_CLOUD`` (default)
      * ``AZURE_CHINA_CLOUD``
      * ``AZURE_US_GOV_CLOUD``
      * ``AZURE_GERMAN_CLOUD``

"""

# Python libs
from __future__ import absolute_import

import logging

# Salt libs
from salt.exceptions import SaltInvocationError  # pylint: disable=unused-import
from salt.ext.six.moves import range

# Azure libs
HAS_LIBS = False
try:
    import azure.mgmt.network.models  # pylint: disable=unused-import
    from msrest.exceptions import SerializationError
    from msrestazure.azure_exceptions import CloudError

    HAS_LIBS = True
except ImportError:
    pass

__virtualname__ = "azurearm_network"

log = logging.getLogger(__name__)


def __virtual__():
    if not HAS_LIBS:
        return (
            False,
            "The following dependencies are required to use the AzureARM modules: "
            "Microsoft Azure SDK for Python >= 2.0rc6, "
            "MS REST Azure (msrestazure) >= 0.4",
        )

    return __virtualname__


def check_dns_name_availability(name, region, **kwargs):
    """
    .. versionadded:: 2019.2.0

    Check whether a domain name in the current zone is available for use.

    :param name: The DNS name to query.

    :param region: The region to query for the DNS name in question.

    CLI Example:

    .. code-block:: bash

        salt-call azurearm_network.check_dns_name_availability testdnsname westus

    """
    netconn = __utils__["azurearm.get_client"]("network", **kwargs)
    try:
        check_dns_name = netconn.check_dns_name_availability(
            location=region, domain_name_label=name
        )
        result = check_dns_name.as_dict()
    except CloudError as exc:
        __utils__["azurearm.log_cloud_error"]("network", str(exc), **kwargs)
        result = {"error": str(exc)}

    return result


def check_ip_address_availability(
    ip_address, virtual_network, resource_group, **kwargs
):
    """
    .. versionadded:: 2019.2.0

    Check that a private ip address is available within the specified
    virtual network.

    :param ip_address: The ip_address to query.

    :param virtual_network: The virtual network to query for the IP address
        in question.

    :param resource_group: The resource group name assigned to the
        virtual network.

    CLI Example:

    .. code-block:: bash

        salt-call azurearm_network.check_ip_address_availability 10.0.0.4 testnet testgroup

    """
    netconn = __utils__["azurearm.get_client"]("network", **kwargs)
    try:
        check_ip = netconn.virtual_networks.check_ip_address_availability(
            resource_group_name=resource_group,
            virtual_network_name=virtual_network,
            ip_address=ip_address,
        )
        result = check_ip.as_dict()
    except CloudError as exc:
        __utils__["azurearm.log_cloud_error"]("network", str(exc), **kwargs)
        result = {"error": str(exc)}

    return result


def default_security_rule_get(name, security_group, resource_group, **kwargs):
    """
    .. versionadded:: 2019.2.0

    Get details about a default security rule within a security group.

    :param name: The name of the security rule to query.

    :param security_group: The network security group containing the
        security rule.

    :param resource_group: The resource group name assigned to the
        network security group.

    CLI Example:

    .. code-block:: bash

        salt-call azurearm_network.default_security_rule_get DenyAllOutBound testnsg testgroup

    """
    result = {}

    default_rules = default_security_rules_list(
        security_group=security_group, resource_group=resource_group, **kwargs
    )

    if isinstance(default_rules, dict) and "error" in default_rules:
        return default_rules

    try:
        for default_rule in default_rules:
            if default_rule["name"] == name:
                result = default_rule
        if not result:
            result = {
                "error": "Unable to find {0} in {1}!".format(name, security_group)
            }
    except KeyError as exc:
        log.error("Unable to find {0} in {1}!".format(name, security_group))
        result = {"error": str(exc)}

    return result


def default_security_rules_list(security_group, resource_group, **kwargs):
    """
    .. versionadded:: 2019.2.0

    List default security rules within a security group.

    :param security_group: The network security group to query.

    :param resource_group: The resource group name assigned to the
        network security group.

    CLI Example:

    .. code-block:: bash

        salt-call azurearm_network.default_security_rules_list testnsg testgroup

    """
    result = {}

    secgroup = network_security_group_get(
        security_group=security_group, resource_group=resource_group, **kwargs
    )

    if "error" in secgroup:
        return secgroup

    try:
        result = secgroup["default_security_rules"]
    except KeyError as exc:
        log.error("No default security rules found for {0}!".format(security_group))
        result = {"error": str(exc)}

    return result


def security_rules_list(security_group, resource_group, **kwargs):
    """
    .. versionadded:: 2019.2.0

    List security rules within a network security group.

    :param security_group: The network security group to query.

    :param resource_group: The resource group name assigned to the
        network security group.

    CLI Example:

    .. code-block:: bash

        salt-call azurearm_network.security_rules_list testnsg testgroup

    """
    netconn = __utils__["azurearm.get_client"]("network", **kwargs)
    try:
        secrules = netconn.security_rules.list(
            network_security_group_name=security_group,
            resource_group_name=resource_group,
        )
        result = __utils__["azurearm.paged_object_to_list"](secrules)
    except CloudError as exc:
        __utils__["azurearm.log_cloud_error"]("network", str(exc), **kwargs)
        result = {"error": str(exc)}

    return result


def security_rule_create_or_update(
    name,
    access,
    direction,
    priority,
    protocol,
    security_group,
    resource_group,
    source_address_prefix=None,
    destination_address_prefix=None,
    source_port_range=None,
    destination_port_range=None,
    source_address_prefixes=None,
    destination_address_prefixes=None,
    source_port_ranges=None,
    destination_port_ranges=None,
    **kwargs
):
    """
    .. versionadded:: 2019.2.0

    Create or update a security rule within a specified network security group.

    :param name: The name of the security rule to create.

    :param access:
        'allow' or 'deny'

    :param direction:
        'inbound' or 'outbound'

    :param priority:
        Integer between 100 and 4096 used for ordering rule application.

    :param protocol:
        'tcp', 'udp', or '*'

    :param destination_address_prefix:
        The CIDR or destination IP range. Asterix '*' can also be used to match all destination IPs.
        Default tags such as 'VirtualNetwork', 'AzureLoadBalancer' and 'Internet' can also be used.
        If this is an ingress rule, specifies where network traffic originates from.

    :param destination_port_range:
        The destination port or range. Integer or range between 0 and 65535. Asterix '*'
        can also be used to match all ports.

    :param source_address_prefix:
        The CIDR or source IP range. Asterix '*' can also be used to match all source IPs.
        Default tags such as 'VirtualNetwork', 'AzureLoadBalancer' and 'Internet' can also be used.
        If this is an ingress rule, specifies where network traffic originates from.

    :param source_port_range:
        The source port or range. Integer or range between 0 and 65535. Asterix '*'
        can also be used to match all ports.

    :param destination_address_prefixes:
        A list of destination_address_prefix values. This parameter overrides destination_address_prefix
        and will cause any value entered there to be ignored.

    :param destination_port_ranges:
        A list of destination_port_range values. This parameter overrides destination_port_range
        and will cause any value entered there to be ignored.

    :param source_address_prefixes:
        A list of source_address_prefix values. This parameter overrides source_address_prefix
        and will cause any value entered there to be ignored.

    :param source_port_ranges:
        A list of source_port_range values. This parameter overrides source_port_range
        and will cause any value entered there to be ignored.

    :param security_group: The network security group containing the
        security rule.

    :param resource_group: The resource group name assigned to the
        network security group.

    CLI Example:

    .. code-block:: bash

        salt-call azurearm_network.security_rule_create_or_update testrule1 allow outbound 101 tcp testnsg testgroup \
                  source_address_prefix='*' destination_address_prefix=internet source_port_range='*' \
                  destination_port_range='1-1024'

    """
    exclusive_params = [
        ("source_port_ranges", "source_port_range"),
        ("source_address_prefixes", "source_address_prefix"),
        ("destination_port_ranges", "destination_port_range"),
        ("destination_address_prefixes", "destination_address_prefix"),
    ]

    for params in exclusive_params:
        # pylint: disable=eval-used
        if not eval(params[0]) and not eval(params[1]):
            log.error(
                "Either the {0} or {1} parameter must be provided!".format(
                    params[0], params[1]
                )
            )
            return False
        # pylint: disable=eval-used
        if eval(params[0]):
            # pylint: disable=exec-used
            exec("{0} = None".format(params[1]))

    netconn = __utils__["azurearm.get_client"]("network", **kwargs)

    try:
        rulemodel = __utils__["azurearm.create_object_model"](
            "network",
            "SecurityRule",
            name=name,
            access=access,
            direction=direction,
            priority=priority,
            protocol=protocol,
            source_port_ranges=source_port_ranges,
            source_port_range=source_port_range,
            source_address_prefixes=source_address_prefixes,
            source_address_prefix=source_address_prefix,
            destination_port_ranges=destination_port_ranges,
            destination_port_range=destination_port_range,
            destination_address_prefixes=destination_address_prefixes,
            destination_address_prefix=destination_address_prefix,
            **kwargs
        )
    except TypeError as exc:
        result = {
            "error": "The object model could not be built. ({0})".format(str(exc))
        }
        return result

    try:
        secrule = netconn.security_rules.create_or_update(
            resource_group_name=resource_group,
            network_security_group_name=security_group,
            security_rule_name=name,
            security_rule_parameters=rulemodel,
        )
        secrule.wait()
        secrule_result = secrule.result()
        result = secrule_result.as_dict()
    except CloudError as exc:
        __utils__["azurearm.log_cloud_error"]("network", str(exc), **kwargs)
        result = {"error": str(exc)}
    except SerializationError as exc:
        result = {
            "error": "The object model could not be parsed. ({0})".format(str(exc))
        }

    return result


def security_rule_delete(security_rule, security_group, resource_group, **kwargs):
    """
    .. versionadded:: 2019.2.0

    Delete a security rule within a specified security group.

    :param name: The name of the security rule to delete.

    :param security_group: The network security group containing the
        security rule.

    :param resource_group: The resource group name assigned to the
        network security group.

    CLI Example:

    .. code-block:: bash

        salt-call azurearm_network.security_rule_delete testrule1 testnsg testgroup

    """
    result = False
    netconn = __utils__["azurearm.get_client"]("network", **kwargs)
    try:
        secrule = netconn.security_rules.delete(
            network_security_group_name=security_group,
            resource_group_name=resource_group,
            security_rule_name=security_rule,
        )
        secrule.wait()
        result = True
    except CloudError as exc:
        __utils__["azurearm.log_cloud_error"]("network", str(exc), **kwargs)

    return result


def security_rule_get(security_rule, security_group, resource_group, **kwargs):
    """
    .. versionadded:: 2019.2.0

    Get a security rule within a specified network security group.

    :param name: The name of the security rule to query.

    :param security_group: The network security group containing the
        security rule.

    :param resource_group: The resource group name assigned to the
        network security group.

    CLI Example:

    .. code-block:: bash

        salt-call azurearm_network.security_rule_get testrule1 testnsg testgroup

    """
    netconn = __utils__["azurearm.get_client"]("network", **kwargs)
    try:
        secrule = netconn.security_rules.get(
            network_security_group_name=security_group,
            resource_group_name=resource_group,
            security_rule_name=security_rule,
        )
        result = secrule.as_dict()
    except CloudError as exc:
        __utils__["azurearm.log_cloud_error"]("network", str(exc), **kwargs)
        result = {"error": str(exc)}

    return result


def network_security_group_create_or_update(
    name, resource_group, **kwargs
):  # pylint: disable=invalid-name
    """
    .. versionadded:: 2019.2.0

    Create or update a network security group.

    :param name: The name of the network security group to create.

    :param resource_group: The resource group name assigned to the
        network security group.

    CLI Example:

    .. code-block:: bash

        salt-call azurearm_network.network_security_group_create_or_update testnsg testgroup

    """
    if "location" not in kwargs:
        rg_props = __salt__["azurearm_resource.resource_group_get"](
            resource_group, **kwargs
        )

        if "error" in rg_props:
            log.error("Unable to determine location from resource group specified.")
            return False
        kwargs["location"] = rg_props["location"]

    netconn = __utils__["azurearm.get_client"]("network", **kwargs)

    try:
        secgroupmodel = __utils__["azurearm.create_object_model"](
            "network", "NetworkSecurityGroup", **kwargs
        )
    except TypeError as exc:
        result = {
            "error": "The object model could not be built. ({0})".format(str(exc))
        }
        return result

    try:
        secgroup = netconn.network_security_groups.create_or_update(
            resource_group_name=resource_group,
            network_security_group_name=name,
            parameters=secgroupmodel,
        )
        secgroup.wait()
        secgroup_result = secgroup.result()
        result = secgroup_result.as_dict()
    except CloudError as exc:
        __utils__["azurearm.log_cloud_error"]("network", str(exc), **kwargs)
        result = {"error": str(exc)}
    except SerializationError as exc:
        result = {
            "error": "The object model could not be parsed. ({0})".format(str(exc))
        }

    return result


def network_security_group_delete(name, resource_group, **kwargs):
    """
    .. versionadded:: 2019.2.0

    Delete a network security group within a resource group.

    :param name: The name of the network security group to delete.

    :param resource_group: The resource group name assigned to the
        network security group.

    CLI Example:

    .. code-block:: bash

        salt-call azurearm_network.network_security_group_delete testnsg testgroup

    """
    result = False
    netconn = __utils__["azurearm.get_client"]("network", **kwargs)
    try:
        secgroup = netconn.network_security_groups.delete(
            resource_group_name=resource_group, network_security_group_name=name
        )
        secgroup.wait()
        result = True
    except CloudError as exc:
        __utils__["azurearm.log_cloud_error"]("network", str(exc), **kwargs)

    return result


def network_security_group_get(name, resource_group, **kwargs):
    """
    .. versionadded:: 2019.2.0

    Get details about a network security group within a resource group.

    :param name: The name of the network security group to query.

    :param resource_group: The resource group name assigned to the
        network security group.

    CLI Example:

    .. code-block:: bash

        salt-call azurearm_network.network_security_group_get testnsg testgroup

    """
    netconn = __utils__["azurearm.get_client"]("network", **kwargs)
    try:
        secgroup = netconn.network_security_groups.get(
            resource_group_name=resource_group, network_security_group_name=name
        )
        result = secgroup.as_dict()
    except CloudError as exc:
        __utils__["azurearm.log_cloud_error"]("network", str(exc), **kwargs)
        result = {"error": str(exc)}

    return result


def network_security_groups_list(resource_group, **kwargs):
    """
    .. versionadded:: 2019.2.0

    List all network security groups within a resource group.

    :param resource_group: The resource group name to list network security \
        groups within.

    CLI Example:

    .. code-block:: bash

        salt-call azurearm_network.network_security_groups_list testgroup

    """
    result = {}
    netconn = __utils__["azurearm.get_client"]("network", **kwargs)
    try:
        secgroups = __utils__["azurearm.paged_object_to_list"](
            netconn.network_security_groups.list(resource_group_name=resource_group)
        )
        for secgroup in secgroups:
            result[secgroup["name"]] = secgroup
    except CloudError as exc:
        __utils__["azurearm.log_cloud_error"]("network", str(exc), **kwargs)
        result = {"error": str(exc)}

    return result


def network_security_groups_list_all(**kwargs):  # pylint: disable=invalid-name
    """
    .. versionadded:: 2019.2.0

    List all network security groups within a subscription.

    CLI Example:

    .. code-block:: bash

        salt-call azurearm_network.network_security_groups_list_all

    """
    result = {}
    netconn = __utils__["azurearm.get_client"]("network", **kwargs)
    try:
        secgroups = __utils__["azurearm.paged_object_to_list"](
            netconn.network_security_groups.list_all()
        )
        for secgroup in secgroups:
            result[secgroup["name"]] = secgroup
    except CloudError as exc:
        __utils__["azurearm.log_cloud_error"]("network", str(exc), **kwargs)
        result = {"error": str(exc)}

    return result


def subnets_list(virtual_network, resource_group, **kwargs):
    """
    .. versionadded:: 2019.2.0

    List all subnets within a virtual network.

    :param virtual_network: The virtual network name to list subnets within.

    :param resource_group: The resource group name assigned to the
        virtual network.

    CLI Example:

    .. code-block:: bash

        salt-call azurearm_network.subnets_list testnet testgroup

    """
    result = {}
    netconn = __utils__["azurearm.get_client"]("network", **kwargs)
    try:
        subnets = __utils__["azurearm.paged_object_to_list"](
            netconn.subnets.list(
                resource_group_name=resource_group, virtual_network_name=virtual_network
            )
        )

        for subnet in subnets:
            result[subnet["name"]] = subnet
    except CloudError as exc:
        __utils__["azurearm.log_cloud_error"]("network", str(exc), **kwargs)
        result = {"error": str(exc)}

    return result


def subnet_get(name, virtual_network, resource_group, **kwargs):
    """
    .. versionadded:: 2019.2.0

    Get details about a specific subnet.

    :param name: The name of the subnet to query.

    :param virtual_network: The virtual network name containing the
        subnet.

    :param resource_group: The resource group name assigned to the
        virtual network.

    CLI Example:

    .. code-block:: bash

        salt-call azurearm_network.subnet_get testsubnet testnet testgroup

    """
    netconn = __utils__["azurearm.get_client"]("network", **kwargs)
    try:
        subnet = netconn.subnets.get(
            resource_group_name=resource_group,
            virtual_network_name=virtual_network,
            subnet_name=name,
        )

        result = subnet.as_dict()
    except CloudError as exc:
        __utils__["azurearm.log_cloud_error"]("network", str(exc), **kwargs)
        result = {"error": str(exc)}

    return result


def subnet_create_or_update(
    name, address_prefix, virtual_network, resource_group, **kwargs
):
    """
    .. versionadded:: 2019.2.0

    Create or update a subnet.

    :param name: The name assigned to the subnet being created or updated.

    :param address_prefix: A valid CIDR block within the virtual network.

    :param virtual_network: The virtual network name containing the
        subnet.

    :param resource_group: The resource group name assigned to the
        virtual network.

    CLI Example:

    .. code-block:: bash

        salt-call azurearm_network.subnet_create_or_update testsubnet \
                  '10.0.0.0/24' testnet testgroup

    """
    netconn = __utils__["azurearm.get_client"]("network", **kwargs)

    # Use NSG name to link to the ID of an existing NSG.
    if kwargs.get("network_security_group"):
        nsg = network_security_group_get(
            name=kwargs["network_security_group"],
            resource_group=resource_group,
            **kwargs
        )
        if "error" not in nsg:
            kwargs["network_security_group"] = {"id": str(nsg["id"])}

    # Use Route Table name to link to the ID of an existing Route Table.
    if kwargs.get("route_table"):
        rt_table = route_table_get(
            name=kwargs["route_table"], resource_group=resource_group, **kwargs
        )
        if "error" not in rt_table:
            kwargs["route_table"] = {"id": str(rt_table["id"])}

    try:
        snetmodel = __utils__["azurearm.create_object_model"](
            "network",
            "Subnet",
            address_prefix=address_prefix,
            resource_group=resource_group,
            **kwargs
        )
    except TypeError as exc:
        result = {
            "error": "The object model could not be built. ({0})".format(str(exc))
        }
        return result

    try:
        subnet = netconn.subnets.create_or_update(
            resource_group_name=resource_group,
            virtual_network_name=virtual_network,
            subnet_name=name,
            subnet_parameters=snetmodel,
        )
        subnet.wait()
        sn_result = subnet.result()
        result = sn_result.as_dict()
    except CloudError as exc:
        __utils__["azurearm.log_cloud_error"]("network", str(exc), **kwargs)
        result = {"error": str(exc)}
    except SerializationError as exc:
        result = {
            "error": "The object model could not be parsed. ({0})".format(str(exc))
        }

    return result


def subnet_delete(name, virtual_network, resource_group, **kwargs):
    """
    .. versionadded:: 2019.2.0

    Delete a subnet.

    :param name: The name of the subnet to delete.

    :param virtual_network: The virtual network name containing the
        subnet.

    :param resource_group: The resource group name assigned to the
        virtual network.

    CLI Example:

    .. code-block:: bash

        salt-call azurearm_network.subnet_delete testsubnet testnet testgroup

    """
    result = False
    netconn = __utils__["azurearm.get_client"]("network", **kwargs)
    try:
        subnet = netconn.subnets.delete(
            resource_group_name=resource_group,
            virtual_network_name=virtual_network,
            subnet_name=name,
        )
        subnet.wait()
        result = True
    except CloudError as exc:
        __utils__["azurearm.log_cloud_error"]("network", str(exc), **kwargs)

    return result


def virtual_networks_list_all(**kwargs):
    """
    .. versionadded:: 2019.2.0

    List all virtual networks within a subscription.

    CLI Example:

    .. code-block:: bash

        salt-call azurearm_network.virtual_networks_list_all

    """
    result = {}
    netconn = __utils__["azurearm.get_client"]("network", **kwargs)
    try:
        vnets = __utils__["azurearm.paged_object_to_list"](
            netconn.virtual_networks.list_all()
        )

        for vnet in vnets:
            result[vnet["name"]] = vnet
    except CloudError as exc:
        __utils__["azurearm.log_cloud_error"]("network", str(exc), **kwargs)
        result = {"error": str(exc)}

    return result


def virtual_networks_list(resource_group, **kwargs):
    """
    .. versionadded:: 2019.2.0

    List all virtual networks within a resource group.

    :param resource_group: The resource group name to list virtual networks
        within.

    CLI Example:

    .. code-block:: bash

        salt-call azurearm_network.virtual_networks_list testgroup

    """
    result = {}
    netconn = __utils__["azurearm.get_client"]("network", **kwargs)
    try:
        vnets = __utils__["azurearm.paged_object_to_list"](
            netconn.virtual_networks.list(resource_group_name=resource_group)
        )

        for vnet in vnets:
            result[vnet["name"]] = vnet
    except CloudError as exc:
        __utils__["azurearm.log_cloud_error"]("network", str(exc), **kwargs)
        result = {"error": str(exc)}

    return result


# pylint: disable=invalid-name
def virtual_network_create_or_update(name, address_prefixes, resource_group, **kwargs):
    """
    .. versionadded:: 2019.2.0

    Create or update a virtual network.

    :param name: The name assigned to the virtual network being
        created or updated.

    :param address_prefixes: A list of CIDR blocks which can be used
        by subnets within the virtual network.

    :param resource_group: The resource group name assigned to the
        virtual network.

    CLI Example:

    .. code-block:: bash

        salt-call azurearm_network.virtual_network_create_or_update \
                  testnet ['10.0.0.0/16'] testgroup

    """
    if "location" not in kwargs:
        rg_props = __salt__["azurearm_resource.resource_group_get"](
            resource_group, **kwargs
        )

        if "error" in rg_props:
            log.error("Unable to determine location from resource group specified.")
            return False
        kwargs["location"] = rg_props["location"]

    if not isinstance(address_prefixes, list):
        log.error("Address prefixes must be specified as a list!")
        return False

    netconn = __utils__["azurearm.get_client"]("network", **kwargs)

    address_space = {"address_prefixes": address_prefixes}
    dhcp_options = {"dns_servers": kwargs.get("dns_servers")}

    try:
        vnetmodel = __utils__["azurearm.create_object_model"](
            "network",
            "VirtualNetwork",
            address_space=address_space,
            dhcp_options=dhcp_options,
            **kwargs
        )
    except TypeError as exc:
        result = {
            "error": "The object model could not be built. ({0})".format(str(exc))
        }
        return result

    try:
        vnet = netconn.virtual_networks.create_or_update(
            virtual_network_name=name,
            resource_group_name=resource_group,
            parameters=vnetmodel,
        )
        vnet.wait()
        vnet_result = vnet.result()
        result = vnet_result.as_dict()
    except CloudError as exc:
        __utils__["azurearm.log_cloud_error"]("network", str(exc), **kwargs)
        result = {"error": str(exc)}
    except SerializationError as exc:
        result = {
            "error": "The object model could not be parsed. ({0})".format(str(exc))
        }

    return result


def virtual_network_delete(name, resource_group, **kwargs):
    """
    .. versionadded:: 2019.2.0

    Delete a virtual network.

    :param name: The name of the virtual network to delete.

    :param resource_group: The resource group name assigned to the
        virtual network

    CLI Example:

    .. code-block:: bash

        salt-call azurearm_network.virtual_network_delete testnet testgroup

    """
    result = False
    netconn = __utils__["azurearm.get_client"]("network", **kwargs)
    try:
        vnet = netconn.virtual_networks.delete(
            virtual_network_name=name, resource_group_name=resource_group
        )
        vnet.wait()
        result = True
    except CloudError as exc:
        __utils__["azurearm.log_cloud_error"]("network", str(exc), **kwargs)

    return result


def virtual_network_get(name, resource_group, **kwargs):
    """
    .. versionadded:: 2019.2.0

    Get details about a specific virtual network.

    :param name: The name of the virtual network to query.

    :param resource_group: The resource group name assigned to the
        virtual network.

    CLI Example:

    .. code-block:: bash

        salt-call azurearm_network.virtual_network_get testnet testgroup

    """
    netconn = __utils__["azurearm.get_client"]("network", **kwargs)
    try:
        vnet = netconn.virtual_networks.get(
            virtual_network_name=name, resource_group_name=resource_group
        )
        result = vnet.as_dict()
    except CloudError as exc:
        __utils__["azurearm.log_cloud_error"]("network", str(exc), **kwargs)
        result = {"error": str(exc)}

    return result


def load_balancers_list_all(**kwargs):
    """
    .. versionadded:: 2019.2.0

    List all load balancers within a subscription.

    CLI Example:

    .. code-block:: bash

        salt-call azurearm_network.load_balancers_list_all

    """
    result = {}
    netconn = __utils__["azurearm.get_client"]("network", **kwargs)
    try:
        load_balancers = __utils__["azurearm.paged_object_to_list"](
            netconn.load_balancers.list_all()
        )

        for load_balancer in load_balancers:
            result[load_balancer["name"]] = load_balancer
    except CloudError as exc:
        __utils__["azurearm.log_cloud_error"]("network", str(exc), **kwargs)
        result = {"error": str(exc)}

    return result


def load_balancers_list(resource_group, **kwargs):
    """
    .. versionadded:: 2019.2.0

    List all load balancers within a resource group.

    :param resource_group: The resource group name to list load balancers
        within.

    CLI Example:

    .. code-block:: bash

        salt-call azurearm_network.load_balancers_list testgroup

    """
    result = {}
    netconn = __utils__["azurearm.get_client"]("network", **kwargs)
    try:
        load_balancers = __utils__["azurearm.paged_object_to_list"](
            netconn.load_balancers.list(resource_group_name=resource_group)
        )

        for load_balancer in load_balancers:
            result[load_balancer["name"]] = load_balancer
    except CloudError as exc:
        __utils__["azurearm.log_cloud_error"]("network", str(exc), **kwargs)
        result = {"error": str(exc)}

    return result


def load_balancer_get(name, resource_group, **kwargs):
    """
    .. versionadded:: 2019.2.0

    Get details about a specific load balancer.

    :param name: The name of the load balancer to query.

    :param resource_group: The resource group name assigned to the
        load balancer.

    CLI Example:

    .. code-block:: bash

        salt-call azurearm_network.load_balancer_get testlb testgroup

    """
    netconn = __utils__["azurearm.get_client"]("network", **kwargs)
    try:
        load_balancer = netconn.load_balancers.get(
            load_balancer_name=name, resource_group_name=resource_group
        )
        result = load_balancer.as_dict()
    except CloudError as exc:
        __utils__["azurearm.log_cloud_error"]("network", str(exc), **kwargs)
        result = {"error": str(exc)}

    return result


def load_balancer_create_or_update(name, resource_group, **kwargs):
    """
    .. versionadded:: 2019.2.0

    Create or update a load balancer within a specified resource group.

    :param name: The name of the load balancer to create.

    :param resource_group: The resource group name assigned to the
        load balancer.

    CLI Example:

    .. code-block:: bash

        salt-call azurearm_network.load_balancer_create_or_update testlb testgroup

    """
    if "location" not in kwargs:
        rg_props = __salt__["azurearm_resource.resource_group_get"](
            resource_group, **kwargs
        )

        if "error" in rg_props:
            log.error("Unable to determine location from resource group specified.")
            return False
        kwargs["location"] = rg_props["location"]

    netconn = __utils__["azurearm.get_client"]("network", **kwargs)

    if isinstance(kwargs.get("frontend_ip_configurations"), list):
        for idx in range(0, len(kwargs["frontend_ip_configurations"])):
            # Use Public IP Address name to link to the ID of an existing Public IP
            if "public_ip_address" in kwargs["frontend_ip_configurations"][idx]:
                pub_ip = public_ip_address_get(
                    name=kwargs["frontend_ip_configurations"][idx]["public_ip_address"],
                    resource_group=resource_group,
                    **kwargs
                )
                if "error" not in pub_ip:
                    kwargs["frontend_ip_configurations"][idx]["public_ip_address"] = {
                        "id": str(pub_ip["id"])
                    }
            # Use Subnet name to link to the ID of an existing Subnet
            elif "subnet" in kwargs["frontend_ip_configurations"][idx]:
                vnets = virtual_networks_list(resource_group=resource_group, **kwargs)
                if "error" not in vnets:
                    for vnet in vnets:
                        subnets = subnets_list(
                            virtual_network=vnet,
                            resource_group=resource_group,
                            **kwargs
                        )
                        if (
                            kwargs["frontend_ip_configurations"][idx]["subnet"]
                            in subnets
                        ):
                            kwargs["frontend_ip_configurations"][idx]["subnet"] = {
                                "id": str(
                                    subnets[
                                        kwargs["frontend_ip_configurations"][idx][
                                            "subnet"
                                        ]
                                    ]["id"]
                                )
                            }
                            break

    id_url = "/subscriptions/{0}/resourceGroups/{1}/providers/Microsoft.Network/loadBalancers/{2}/{3}/{4}"

    if isinstance(kwargs.get("load_balancing_rules"), list):
        for idx in range(0, len(kwargs["load_balancing_rules"])):
            # Link to sub-objects which might be created at the same time as the load balancer
            if "frontend_ip_configuration" in kwargs["load_balancing_rules"][idx]:
                kwargs["load_balancing_rules"][idx]["frontend_ip_configuration"] = {
                    "id": id_url.format(
                        kwargs.get("subscription_id"),
                        resource_group,
                        name,
                        "frontendIPConfigurations",
                        kwargs["load_balancing_rules"][idx][
                            "frontend_ip_configuration"
                        ],
                    )
                }
            if "backend_address_pool" in kwargs["load_balancing_rules"][idx]:
                kwargs["load_balancing_rules"][idx]["backend_address_pool"] = {
                    "id": id_url.format(
                        kwargs.get("subscription_id"),
                        resource_group,
                        name,
                        "backendAddressPools",
                        kwargs["load_balancing_rules"][idx]["backend_address_pool"],
                    )
                }
            if "probe" in kwargs["load_balancing_rules"][idx]:
                kwargs["load_balancing_rules"][idx]["probe"] = {
                    "id": id_url.format(
                        kwargs.get("subscription_id"),
                        resource_group,
                        name,
                        "probes",
                        kwargs["load_balancing_rules"][idx]["probe"],
                    )
                }

    if isinstance(kwargs.get("inbound_nat_rules"), list):
        for idx in range(0, len(kwargs["inbound_nat_rules"])):
            # Link to sub-objects which might be created at the same time as the load balancer
            if "frontend_ip_configuration" in kwargs["inbound_nat_rules"][idx]:
                kwargs["inbound_nat_rules"][idx]["frontend_ip_configuration"] = {
                    "id": id_url.format(
                        kwargs.get("subscription_id"),
                        resource_group,
                        name,
                        "frontendIPConfigurations",
                        kwargs["inbound_nat_rules"][idx]["frontend_ip_configuration"],
                    )
                }

    if isinstance(kwargs.get("inbound_nat_pools"), list):
        for idx in range(0, len(kwargs["inbound_nat_pools"])):
            # Link to sub-objects which might be created at the same time as the load balancer
            if "frontend_ip_configuration" in kwargs["inbound_nat_pools"][idx]:
                kwargs["inbound_nat_pools"][idx]["frontend_ip_configuration"] = {
                    "id": id_url.format(
                        kwargs.get("subscription_id"),
                        resource_group,
                        name,
                        "frontendIPConfigurations",
                        kwargs["inbound_nat_pools"][idx]["frontend_ip_configuration"],
                    )
                }

    if isinstance(kwargs.get("outbound_nat_rules"), list):
        for idx in range(0, len(kwargs["outbound_nat_rules"])):
            # Link to sub-objects which might be created at the same time as the load balancer
            if "frontend_ip_configuration" in kwargs["outbound_nat_rules"][idx]:
                kwargs["outbound_nat_rules"][idx]["frontend_ip_configuration"] = {
                    "id": id_url.format(
                        kwargs.get("subscription_id"),
                        resource_group,
                        name,
                        "frontendIPConfigurations",
                        kwargs["outbound_nat_rules"][idx]["frontend_ip_configuration"],
                    )
                }
            if "backend_address_pool" in kwargs["outbound_nat_rules"][idx]:
                kwargs["outbound_nat_rules"][idx]["backend_address_pool"] = {
                    "id": id_url.format(
                        kwargs.get("subscription_id"),
                        resource_group,
                        name,
                        "backendAddressPools",
                        kwargs["outbound_nat_rules"][idx]["backend_address_pool"],
                    )
                }

    try:
        lbmodel = __utils__["azurearm.create_object_model"](
            "network", "LoadBalancer", **kwargs
        )
    except TypeError as exc:
        result = {
            "error": "The object model could not be built. ({0})".format(str(exc))
        }
        return result

    try:
        load_balancer = netconn.load_balancers.create_or_update(
            resource_group_name=resource_group,
            load_balancer_name=name,
            parameters=lbmodel,
        )
        load_balancer.wait()
        lb_result = load_balancer.result()
        result = lb_result.as_dict()
    except CloudError as exc:
        __utils__["azurearm.log_cloud_error"]("network", str(exc), **kwargs)
        result = {"error": str(exc)}
    except SerializationError as exc:
        result = {
            "error": "The object model could not be parsed. ({0})".format(str(exc))
        }

    return result


def load_balancer_delete(name, resource_group, **kwargs):
    """
    .. versionadded:: 2019.2.0

    Delete a load balancer.

    :param name: The name of the load balancer to delete.

    :param resource_group: The resource group name assigned to the
        load balancer.

    CLI Example:

    .. code-block:: bash

        salt-call azurearm_network.load_balancer_delete testlb testgroup

    """
    result = False
    netconn = __utils__["azurearm.get_client"]("network", **kwargs)
    try:
        load_balancer = netconn.load_balancers.delete(
            load_balancer_name=name, resource_group_name=resource_group
        )
        load_balancer.wait()
        result = True
    except CloudError as exc:
        __utils__["azurearm.log_cloud_error"]("network", str(exc), **kwargs)

    return result


def usages_list(location, **kwargs):
    """
    .. versionadded:: 2019.2.0

    List subscription network usage for a location.

    :param location: The Azure location to query for network usage.

    CLI Example:

    .. code-block:: bash

        salt-call azurearm_network.usages_list westus

    """
    netconn = __utils__["azurearm.get_client"]("network", **kwargs)
    try:
        result = __utils__["azurearm.paged_object_to_list"](
            netconn.usages.list(location)
        )
    except CloudError as exc:
        __utils__["azurearm.log_cloud_error"]("network", str(exc), **kwargs)
        result = {"error": str(exc)}

    return result


def network_interface_delete(name, resource_group, **kwargs):
    """
    .. versionadded:: 2019.2.0

    Delete a network interface.

    :param name: The name of the network interface to delete.

    :param resource_group: The resource group name assigned to the
        network interface.

    CLI Example:

    .. code-block:: bash

        salt-call azurearm_network.network_interface_delete test-iface0 testgroup

    """
    result = False

    netconn = __utils__["azurearm.get_client"]("network", **kwargs)
    try:
        nic = netconn.network_interfaces.delete(
            network_interface_name=name, resource_group_name=resource_group
        )
        nic.wait()
        result = True
    except CloudError as exc:
        __utils__["azurearm.log_cloud_error"]("network", str(exc), **kwargs)

    return result


def network_interface_get(name, resource_group, **kwargs):
    """
    .. versionadded:: 2019.2.0

    Get details about a specific network interface.

    :param name: The name of the network interface to query.

    :param resource_group: The resource group name assigned to the
        network interface.

    CLI Example:

    .. code-block:: bash

        salt-call azurearm_network.network_interface_get test-iface0 testgroup

    """
    netconn = __utils__["azurearm.get_client"]("network", **kwargs)
    try:
        nic = netconn.network_interfaces.get(
            network_interface_name=name, resource_group_name=resource_group
        )
        result = nic.as_dict()
    except CloudError as exc:
        __utils__["azurearm.log_cloud_error"]("network", str(exc), **kwargs)
        result = {"error": str(exc)}

    return result


# pylint: disable=invalid-name
def network_interface_create_or_update(
    name, ip_configurations, subnet, virtual_network, resource_group, **kwargs
):
    """
    .. versionadded:: 2019.2.0

    Create or update a network interface within a specified resource group.

    :param name: The name of the network interface to create.

    :param ip_configurations: A list of dictionaries representing valid
        NetworkInterfaceIPConfiguration objects. The 'name' key is required at
        minimum. At least one IP Configuration must be present.

    :param subnet: The name of the subnet assigned to the network interface.

    :param virtual_network: The name of the virtual network assigned to the subnet.

    :param resource_group: The resource group name assigned to the
        virtual network.

    CLI Example:

    .. code-block:: bash

        salt-call azurearm_network.network_interface_create_or_update test-iface0 [{'name': 'testipconfig1'}] \
                  testsubnet testnet testgroup

    """
    if "location" not in kwargs:
        rg_props = __salt__["azurearm_resource.resource_group_get"](
            resource_group, **kwargs
        )

        if "error" in rg_props:
            log.error("Unable to determine location from resource group specified.")
            return False
        kwargs["location"] = rg_props["location"]

    netconn = __utils__["azurearm.get_client"]("network", **kwargs)

    # Use NSG name to link to the ID of an existing NSG.
    if kwargs.get("network_security_group"):
        nsg = network_security_group_get(
            name=kwargs["network_security_group"],
            resource_group=resource_group,
            **kwargs
        )
        if "error" not in nsg:
            kwargs["network_security_group"] = {"id": str(nsg["id"])}

    # Use VM name to link to the ID of an existing VM.
    if kwargs.get("virtual_machine"):
        vm_instance = __salt__["azurearm_compute.virtual_machine_get"](
            name=kwargs["virtual_machine"], resource_group=resource_group, **kwargs
        )
        if "error" not in vm_instance:
            kwargs["virtual_machine"] = {"id": str(vm_instance["id"])}

    # Loop through IP Configurations and build each dictionary to pass to model creation.
    if isinstance(ip_configurations, list):
        subnet = subnet_get(
            name=subnet,
            virtual_network=virtual_network,
            resource_group=resource_group,
            **kwargs
        )
        if "error" not in subnet:
            subnet = {"id": str(subnet["id"])}
            for ipconfig in ip_configurations:
                if "name" in ipconfig:
                    ipconfig["subnet"] = subnet
                    if isinstance(
                        ipconfig.get("application_gateway_backend_address_pools"), list
                    ):
                        # TODO: Add ID lookup for referenced object names
                        pass
                    if isinstance(
                        ipconfig.get("load_balancer_backend_address_pools"), list
                    ):
                        # TODO: Add ID lookup for referenced object names
                        pass
                    if isinstance(
                        ipconfig.get("load_balancer_inbound_nat_rules"), list
                    ):
                        # TODO: Add ID lookup for referenced object names
                        pass
                    if ipconfig.get("public_ip_address"):
                        pub_ip = public_ip_address_get(
                            name=ipconfig["public_ip_address"],
                            resource_group=resource_group,
                            **kwargs
                        )
                        if "error" not in pub_ip:
                            ipconfig["public_ip_address"] = {"id": str(pub_ip["id"])}

    try:
        nicmodel = __utils__["azurearm.create_object_model"](
            "network", "NetworkInterface", ip_configurations=ip_configurations, **kwargs
        )
    except TypeError as exc:
        result = {
            "error": "The object model could not be built. ({0})".format(str(exc))
        }
        return result

    try:
        interface = netconn.network_interfaces.create_or_update(
            resource_group_name=resource_group,
            network_interface_name=name,
            parameters=nicmodel,
        )
        interface.wait()
        nic_result = interface.result()
        result = nic_result.as_dict()
    except CloudError as exc:
        __utils__["azurearm.log_cloud_error"]("network", str(exc), **kwargs)
        result = {"error": str(exc)}
    except SerializationError as exc:
        result = {
            "error": "The object model could not be parsed. ({0})".format(str(exc))
        }

    return result


def network_interfaces_list_all(**kwargs):
    """
    .. versionadded:: 2019.2.0

    List all network interfaces within a subscription.

    CLI Example:

    .. code-block:: bash

        salt-call azurearm_network.network_interfaces_list_all

    """
    result = {}
    netconn = __utils__["azurearm.get_client"]("network", **kwargs)
    try:
        nics = __utils__["azurearm.paged_object_to_list"](
            netconn.network_interfaces.list_all()
        )

        for nic in nics:
            result[nic["name"]] = nic
    except CloudError as exc:
        __utils__["azurearm.log_cloud_error"]("network", str(exc), **kwargs)
        result = {"error": str(exc)}

    return result


def network_interfaces_list(resource_group, **kwargs):
    """
    .. versionadded:: 2019.2.0

    List all network interfaces within a resource group.

    :param resource_group: The resource group name to list network
        interfaces within.

    CLI Example:

    .. code-block:: bash

        salt-call azurearm_network.network_interfaces_list testgroup

    """
    result = {}
    netconn = __utils__["azurearm.get_client"]("network", **kwargs)
    try:
        nics = __utils__["azurearm.paged_object_to_list"](
            netconn.network_interfaces.list(resource_group_name=resource_group)
        )

        for nic in nics:
            result[nic["name"]] = nic
    except CloudError as exc:
        __utils__["azurearm.log_cloud_error"]("network", str(exc), **kwargs)
        result = {"error": str(exc)}

    return result


# pylint: disable=invalid-name
def network_interface_get_effective_route_table(name, resource_group, **kwargs):
    """
    .. versionadded:: 2019.2.0

    Get all route tables for a specific network interface.

    :param name: The name of the network interface to query.

    :param resource_group: The resource group name assigned to the
        network interface.

    CLI Example:

    .. code-block:: bash

        salt-call azurearm_network.network_interface_get_effective_route_table test-iface0 testgroup

    """
    netconn = __utils__["azurearm.get_client"]("network", **kwargs)
    try:
        nic = netconn.network_interfaces.get_effective_route_table(
            network_interface_name=name, resource_group_name=resource_group
        )
        nic.wait()
        tables = nic.result()
        tables = tables.as_dict()
        result = tables["value"]
    except CloudError as exc:
        __utils__["azurearm.log_cloud_error"]("network", str(exc), **kwargs)
        result = {"error": str(exc)}

    return result


# pylint: disable=invalid-name
def network_interface_list_effective_network_security_groups(
    name, resource_group, **kwargs
):
    """
    .. versionadded:: 2019.2.0

    Get all network security groups applied to a specific network interface.

    :param name: The name of the network interface to query.

    :param resource_group: The resource group name assigned to the
        network interface.

    CLI Example:

    .. code-block:: bash

        salt-call azurearm_network.network_interface_list_effective_network_security_groups test-iface0 testgroup

    """
    netconn = __utils__["azurearm.get_client"]("network", **kwargs)
    try:
        nic = netconn.network_interfaces.list_effective_network_security_groups(
            network_interface_name=name, resource_group_name=resource_group
        )
        nic.wait()
        groups = nic.result()
        groups = groups.as_dict()
        result = groups["value"]
    except CloudError as exc:
        __utils__["azurearm.log_cloud_error"]("network", str(exc), **kwargs)
        result = {"error": str(exc)}

    return result


# pylint: disable=invalid-name
def list_virtual_machine_scale_set_vm_network_interfaces(
    scale_set, vm_index, resource_group, **kwargs
):
    """
    .. versionadded:: 2019.2.0

    Get information about all network interfaces in a specific virtual machine within a scale set.

    :param scale_set: The name of the scale set to query.

    :param vm_index: The virtual machine index.

    :param resource_group: The resource group name assigned to the
        scale set.

    CLI Example:

    .. code-block:: bash

        salt-call azurearm_network.list_virtual_machine_scale_set_vm_network_interfaces testset testvm testgroup

    """
    result = {}
    netconn = __utils__["azurearm.get_client"]("network", **kwargs)
    try:
        nics = __utils__["azurearm.paged_object_to_list"](
            netconn.network_interfaces.list_virtual_machine_scale_set_vm_network_interfaces(
                virtual_machine_scale_set_name=scale_set,
                virtualmachine_index=vm_index,
                resource_group_name=resource_group,
            )
        )

        for nic in nics:
            result[nic["name"]] = nic
    except CloudError as exc:
        __utils__["azurearm.log_cloud_error"]("network", str(exc), **kwargs)
        result = {"error": str(exc)}

    return result


# pylint: disable=invalid-name
def list_virtual_machine_scale_set_network_interfaces(
    scale_set, resource_group, **kwargs
):
    """
    .. versionadded:: 2019.2.0

    Get information about all network interfaces within a scale set.

    :param scale_set: The name of the scale set to query.

    :param resource_group: The resource group name assigned to the
        scale set.

    CLI Example:

    .. code-block:: bash

        salt-call azurearm_network.list_virtual_machine_scale_set_vm_network_interfaces testset testgroup

    """
    result = {}
    netconn = __utils__["azurearm.get_client"]("network", **kwargs)
    try:
        nics = __utils__["azurearm.paged_object_to_list"](
            netconn.network_interfaces.list_virtual_machine_scale_set_network_interfaces(
                virtual_machine_scale_set_name=scale_set,
                resource_group_name=resource_group,
            )
        )

        for nic in nics:
            result[nic["name"]] = nic
    except CloudError as exc:
        __utils__["azurearm.log_cloud_error"]("network", str(exc), **kwargs)
        result = {"error": str(exc)}

    return result


# pylint: disable=invalid-name
def get_virtual_machine_scale_set_network_interface(
    name, scale_set, vm_index, resource_group, **kwargs
):
    """
    .. versionadded:: 2019.2.0

    Get information about a specfic network interface within a scale set.

    :param name: The name of the network interface to query.

    :param scale_set: The name of the scale set containing the interface.

    :param vm_index: The virtual machine index.

    :param resource_group: The resource group name assigned to the
        scale set.

    CLI Example:

    .. code-block:: bash

        salt-call azurearm_network.get_virtual_machine_scale_set_network_interface test-iface0 testset testvm testgroup

    """
    expand = kwargs.get("expand")

    netconn = __utils__["azurearm.get_client"]("network", **kwargs)
    try:
        nic = netconn.network_interfaces.list_virtual_machine_scale_set_vm_network_interfaces(
            network_interface_name=name,
            virtual_machine_scale_set_name=scale_set,
            virtualmachine_index=vm_index,
            resource_group_name=resource_group,
            exapnd=expand,
        )

        result = nic.as_dict()
    except CloudError as exc:
        __utils__["azurearm.log_cloud_error"]("network", str(exc), **kwargs)
        result = {"error": str(exc)}

    return result


def public_ip_address_delete(name, resource_group, **kwargs):
    """
    .. versionadded:: 2019.2.0

    Delete a public IP address.

    :param name: The name of the public IP address to delete.

    :param resource_group: The resource group name assigned to the
        public IP address.

    CLI Example:

    .. code-block:: bash

        salt-call azurearm_network.public_ip_address_delete test-pub-ip testgroup

    """
    result = False
    netconn = __utils__["azurearm.get_client"]("network", **kwargs)
    try:
        pub_ip = netconn.public_ip_addresses.delete(
            public_ip_address_name=name, resource_group_name=resource_group
        )
        pub_ip.wait()
        result = True
    except CloudError as exc:
        __utils__["azurearm.log_cloud_error"]("network", str(exc), **kwargs)

    return result


def public_ip_address_get(name, resource_group, **kwargs):
    """
    .. versionadded:: 2019.2.0

    Get details about a specific public IP address.

    :param name: The name of the public IP address to query.

    :param resource_group: The resource group name assigned to the
        public IP address.

    CLI Example:

    .. code-block:: bash

        salt-call azurearm_network.public_ip_address_get test-pub-ip testgroup

    """
    expand = kwargs.get("expand")

    netconn = __utils__["azurearm.get_client"]("network", **kwargs)

    try:
        pub_ip = netconn.public_ip_addresses.get(
            public_ip_address_name=name,
            resource_group_name=resource_group,
            expand=expand,
        )
        result = pub_ip.as_dict()
    except CloudError as exc:
        __utils__["azurearm.log_cloud_error"]("network", str(exc), **kwargs)
        result = {"error": str(exc)}

    return result


def public_ip_address_create_or_update(name, resource_group, **kwargs):
    """
    .. versionadded:: 2019.2.0

    Create or update a public IP address within a specified resource group.

    :param name: The name of the public IP address to create.

    :param resource_group: The resource group name assigned to the
        public IP address.

    CLI Example:

    .. code-block:: bash

        salt-call azurearm_network.public_ip_address_create_or_update test-ip-0 testgroup

    """
    if "location" not in kwargs:
        rg_props = __salt__["azurearm_resource.resource_group_get"](
            resource_group, **kwargs
        )

        if "error" in rg_props:
            log.error("Unable to determine location from resource group specified.")
            return False
        kwargs["location"] = rg_props["location"]

    netconn = __utils__["azurearm.get_client"]("network", **kwargs)

    try:
        pub_ip_model = __utils__["azurearm.create_object_model"](
            "network", "PublicIPAddress", **kwargs
        )
    except TypeError as exc:
        result = {
            "error": "The object model could not be built. ({0})".format(str(exc))
        }
        return result

    try:
        ip = netconn.public_ip_addresses.create_or_update(
            resource_group_name=resource_group,
            public_ip_address_name=name,
            parameters=pub_ip_model,
        )
        ip.wait()
        ip_result = ip.result()
        result = ip_result.as_dict()
    except CloudError as exc:
        __utils__["azurearm.log_cloud_error"]("network", str(exc), **kwargs)
        result = {"error": str(exc)}
    except SerializationError as exc:
        result = {
            "error": "The object model could not be parsed. ({0})".format(str(exc))
        }

    return result


def public_ip_addresses_list_all(**kwargs):
    """
    .. versionadded:: 2019.2.0

    List all public IP addresses within a subscription.

    CLI Example:

    .. code-block:: bash

        salt-call azurearm_network.public_ip_addresses_list_all

    """
    result = {}
    netconn = __utils__["azurearm.get_client"]("network", **kwargs)
    try:
        pub_ips = __utils__["azurearm.paged_object_to_list"](
            netconn.public_ip_addresses.list_all()
        )

        for ip in pub_ips:
            result[ip["name"]] = ip
    except CloudError as exc:
        __utils__["azurearm.log_cloud_error"]("network", str(exc), **kwargs)
        result = {"error": str(exc)}

    return result


def public_ip_addresses_list(resource_group, **kwargs):
    """
    .. versionadded:: 2019.2.0

    List all public IP addresses within a resource group.

    :param resource_group: The resource group name to list public IP
        addresses within.

    CLI Example:

    .. code-block:: bash

        salt-call azurearm_network.public_ip_addresses_list testgroup

    """
    result = {}
    netconn = __utils__["azurearm.get_client"]("network", **kwargs)
    try:
        pub_ips = __utils__["azurearm.paged_object_to_list"](
            netconn.public_ip_addresses.list(resource_group_name=resource_group)
        )

        for ip in pub_ips:
            result[ip["name"]] = ip
    except CloudError as exc:
        __utils__["azurearm.log_cloud_error"]("network", str(exc), **kwargs)
        result = {"error": str(exc)}

    return result


def route_filter_rule_delete(name, route_filter, resource_group, **kwargs):
    """
    .. versionadded:: 2019.2.0

    Delete a route filter rule.

    :param name: The route filter rule to delete.

    :param route_filter: The route filter containing the rule.

    :param resource_group: The resource group name assigned to the
        route filter.

    CLI Example:

    .. code-block:: bash

        salt-call azurearm_network.route_filter_rule_delete test-rule test-filter testgroup

    """
    result = False
    netconn = __utils__["azurearm.get_client"]("network", **kwargs)
    try:
        rule = netconn.route_filter_rules.delete(
            resource_group_name=resource_group,
            route_filter_name=route_filter,
            rule_name=name,
        )
        rule.wait()
        result = True
    except CloudError as exc:
        __utils__["azurearm.log_cloud_error"]("network", str(exc), **kwargs)

    return result


def route_filter_rule_get(name, route_filter, resource_group, **kwargs):
    """
    .. versionadded:: 2019.2.0

    Get details about a specific route filter rule.

    :param name: The route filter rule to query.

    :param route_filter: The route filter containing the rule.

    :param resource_group: The resource group name assigned to the
        route filter.

    CLI Example:

    .. code-block:: bash

        salt-call azurearm_network.route_filter_rule_get test-rule test-filter testgroup

    """
    result = {}
    netconn = __utils__["azurearm.get_client"]("network", **kwargs)
    try:
        rule = netconn.route_filter_rules.get(
            resource_group_name=resource_group,
            route_filter_name=route_filter,
            rule_name=name,
        )

        result = rule.as_dict()
    except CloudError as exc:
        __utils__["azurearm.log_cloud_error"]("network", str(exc), **kwargs)
        result = {"error": str(exc)}

    return result


def route_filter_rule_create_or_update(
    name, access, communities, route_filter, resource_group, **kwargs
):
    """
    .. versionadded:: 2019.2.0

    Create or update a rule within a specified route filter.

    :param name: The name of the rule to create.

    :param access: The access type of the rule. Valid values are 'Allow' and 'Deny'.

    :param communities: A list of BGP communities to filter on.

    :param route_filter: The name of the route filter containing the rule.

    :param resource_group: The resource group name assigned to the
        route filter.

    CLI Example:

    .. code-block:: bash

        salt-call azurearm_network.route_filter_rule_create_or_update \
                  test-rule allow "['12076:51006']" test-filter testgroup

    """
    if not isinstance(communities, list):
        log.error("The communities parameter must be a list of strings!")
        return False

    if "location" not in kwargs:
        rg_props = __salt__["azurearm_resource.resource_group_get"](
            resource_group, **kwargs
        )

        if "error" in rg_props:
            log.error("Unable to determine location from resource group specified.")
            return False
        kwargs["location"] = rg_props["location"]

    netconn = __utils__["azurearm.get_client"]("network", **kwargs)

    try:
        rule_model = __utils__["azurearm.create_object_model"](
            "network",
            "RouteFilterRule",
            access=access,
            communities=communities,
            **kwargs
        )
    except TypeError as exc:
        result = {
            "error": "The object model could not be built. ({0})".format(str(exc))
        }
        return result

    try:
        rule = netconn.route_filter_rules.create_or_update(
            resource_group_name=resource_group,
            route_filter_name=route_filter,
            rule_name=name,
            route_filter_rule_parameters=rule_model,
        )
        rule.wait()
        rule_result = rule.result()
        result = rule_result.as_dict()
    except CloudError as exc:
        message = str(exc)
        if kwargs.get("subscription_id") == str(message).strip():
            message = "Subscription not authorized for this operation!"
        __utils__["azurearm.log_cloud_error"]("network", message, **kwargs)
        result = {"error": message}
    except SerializationError as exc:
        result = {
            "error": "The object model could not be parsed. ({0})".format(str(exc))
        }

    return result


def route_filter_rules_list(route_filter, resource_group, **kwargs):
    """
    .. versionadded:: 2019.2.0

    List all routes within a route filter.

    :param route_filter: The route filter to query.

    :param resource_group: The resource group name assigned to the
        route filter.

    CLI Example:

    .. code-block:: bash

        salt-call azurearm_network.route_filter_rules_list test-filter testgroup

    """
    result = {}
    netconn = __utils__["azurearm.get_client"]("network", **kwargs)
    try:
        rules = __utils__["azurearm.paged_object_to_list"](
            netconn.route_filter_rules.list_by_route_filter(
                resource_group_name=resource_group, route_filter_name=route_filter
            )
        )

        for rule in rules:
            result[rule["name"]] = rule
    except CloudError as exc:
        __utils__["azurearm.log_cloud_error"]("network", str(exc), **kwargs)
        result = {"error": str(exc)}

    return result


def route_filter_delete(name, resource_group, **kwargs):
    """
    .. versionadded:: 2019.2.0

    Delete a route filter.

    :param name: The name of the route filter to delete.

    :param resource_group: The resource group name assigned to the
        route filter.

    CLI Example:

    .. code-block:: bash

        salt-call azurearm_network.route_filter_delete test-filter testgroup

    """
    result = False
    netconn = __utils__["azurearm.get_client"]("network", **kwargs)
    try:
        route_filter = netconn.route_filters.delete(
            route_filter_name=name, resource_group_name=resource_group
        )
        route_filter.wait()
        result = True
    except CloudError as exc:
        __utils__["azurearm.log_cloud_error"]("network", str(exc), **kwargs)

    return result


def route_filter_get(name, resource_group, **kwargs):
    """
    .. versionadded:: 2019.2.0

    Get details about a specific route filter.

    :param name: The name of the route table to query.

    :param resource_group: The resource group name assigned to the
        route filter.

    CLI Example:

    .. code-block:: bash

        salt-call azurearm_network.route_filter_get test-filter testgroup

    """
    expand = kwargs.get("expand")

    netconn = __utils__["azurearm.get_client"]("network", **kwargs)

    try:
        route_filter = netconn.route_filters.get(
            route_filter_name=name, resource_group_name=resource_group, expand=expand
        )
        result = route_filter.as_dict()
    except CloudError as exc:
        __utils__["azurearm.log_cloud_error"]("network", str(exc), **kwargs)
        result = {"error": str(exc)}

    return result


def route_filter_create_or_update(name, resource_group, **kwargs):
    """
    .. versionadded:: 2019.2.0

    Create or update a route filter within a specified resource group.

    :param name: The name of the route filter to create.

    :param resource_group: The resource group name assigned to the
        route filter.

    CLI Example:

    .. code-block:: bash

        salt-call azurearm_network.route_filter_create_or_update test-filter testgroup

    """
    if "location" not in kwargs:
        rg_props = __salt__["azurearm_resource.resource_group_get"](
            resource_group, **kwargs
        )

        if "error" in rg_props:
            log.error("Unable to determine location from resource group specified.")
            return False
        kwargs["location"] = rg_props["location"]

    netconn = __utils__["azurearm.get_client"]("network", **kwargs)

    try:
        rt_filter_model = __utils__["azurearm.create_object_model"](
            "network", "RouteFilter", **kwargs
        )
    except TypeError as exc:
        result = {
            "error": "The object model could not be built. ({0})".format(str(exc))
        }
        return result

    try:
        rt_filter = netconn.route_filters.create_or_update(
            resource_group_name=resource_group,
            route_filter_name=name,
            route_filter_parameters=rt_filter_model,
        )
        rt_filter.wait()
        rt_result = rt_filter.result()
        result = rt_result.as_dict()
    except CloudError as exc:
        __utils__["azurearm.log_cloud_error"]("network", str(exc), **kwargs)
        result = {"error": str(exc)}
    except SerializationError as exc:
        result = {
            "error": "The object model could not be parsed. ({0})".format(str(exc))
        }

    return result


def route_filters_list(resource_group, **kwargs):
    """
    .. versionadded:: 2019.2.0

    List all route filters within a resource group.

    :param resource_group: The resource group name to list route
        filters within.

    CLI Example:

    .. code-block:: bash

        salt-call azurearm_network.route_filters_list testgroup

    """
    result = {}
    netconn = __utils__["azurearm.get_client"]("network", **kwargs)
    try:
        filters = __utils__["azurearm.paged_object_to_list"](
            netconn.route_filters.list_by_resource_group(
                resource_group_name=resource_group
            )
        )

        for route_filter in filters:
            result[route_filter["name"]] = route_filter
    except CloudError as exc:
        __utils__["azurearm.log_cloud_error"]("network", str(exc), **kwargs)
        result = {"error": str(exc)}

    return result


def route_filters_list_all(**kwargs):
    """
    .. versionadded:: 2019.2.0

    List all route filters within a subscription.

    CLI Example:

    .. code-block:: bash

        salt-call azurearm_network.route_filters_list_all

    """
    result = {}
    netconn = __utils__["azurearm.get_client"]("network", **kwargs)
    try:
        filters = __utils__["azurearm.paged_object_to_list"](
            netconn.route_filters.list()
        )

        for route_filter in filters:
            result[route_filter["name"]] = route_filter
    except CloudError as exc:
        __utils__["azurearm.log_cloud_error"]("network", str(exc), **kwargs)
        result = {"error": str(exc)}

    return result


def route_delete(name, route_table, resource_group, **kwargs):
    """
    .. versionadded:: 2019.2.0

    Delete a route from a route table.

    :param name: The route to delete.

    :param route_table: The route table containing the route.

    :param resource_group: The resource group name assigned to the
        route table.

    CLI Example:

    .. code-block:: bash

        salt-call azurearm_network.route_delete test-rt test-rt-table testgroup

    """
    result = False
    netconn = __utils__["azurearm.get_client"]("network", **kwargs)
    try:
        route = netconn.routes.delete(
            resource_group_name=resource_group,
            route_table_name=route_table,
            route_name=name,
        )
        route.wait()
        result = True
    except CloudError as exc:
        __utils__["azurearm.log_cloud_error"]("network", str(exc), **kwargs)

    return result


def route_get(name, route_table, resource_group, **kwargs):
    """
    .. versionadded:: 2019.2.0

    Get details about a specific route.

    :param name: The route to query.

    :param route_table: The route table containing the route.

    :param resource_group: The resource group name assigned to the
        route table.

    CLI Example:

    .. code-block:: bash

        salt-call azurearm_network.route_get test-rt test-rt-table testgroup

    """
    result = {}
    netconn = __utils__["azurearm.get_client"]("network", **kwargs)
    try:
        route = netconn.routes.get(
            resource_group_name=resource_group,
            route_table_name=route_table,
            route_name=name,
        )

        result = route.as_dict()
    except CloudError as exc:
        __utils__["azurearm.log_cloud_error"]("network", str(exc), **kwargs)
        result = {"error": str(exc)}

    return result


def route_create_or_update(
    name,
    address_prefix,
    next_hop_type,
    route_table,
    resource_group,
    next_hop_ip_address=None,
    **kwargs
):
    """
    .. versionadded:: 2019.2.0

    Create or update a route within a specified route table.

    :param name: The name of the route to create.

    :param address_prefix: The destination CIDR to which the route applies.

    :param next_hop_type: The type of Azure hop the packet should be sent to. Possible values are:
        'VirtualNetworkGateway', 'VnetLocal', 'Internet', 'VirtualAppliance', and 'None'.

    :param next_hop_ip_address: Optional IP address to which packets should be forwarded. Next hop
        values are only allowed in routes where the next_hop_type is 'VirtualAppliance'.

    :param route_table: The name of the route table containing the route.

    :param resource_group: The resource group name assigned to the
        route table.

    CLI Example:

    .. code-block:: bash

        salt-call azurearm_network.route_create_or_update test-rt '10.0.0.0/8' test-rt-table testgroup

    """
    netconn = __utils__["azurearm.get_client"]("network", **kwargs)

    try:
        rt_model = __utils__["azurearm.create_object_model"](
            "network",
            "Route",
            address_prefix=address_prefix,
            next_hop_type=next_hop_type,
            next_hop_ip_address=next_hop_ip_address,
            **kwargs
        )
    except TypeError as exc:
        result = {
            "error": "The object model could not be built. ({0})".format(str(exc))
        }
        return result

    try:
        route = netconn.routes.create_or_update(
            resource_group_name=resource_group,
            route_table_name=route_table,
            route_name=name,
            route_parameters=rt_model,
        )
        route.wait()
        rt_result = route.result()
        result = rt_result.as_dict()
    except CloudError as exc:
        __utils__["azurearm.log_cloud_error"]("network", str(exc), **kwargs)
        result = {"error": str(exc)}
    except SerializationError as exc:
        result = {
            "error": "The object model could not be parsed. ({0})".format(str(exc))
        }

    return result


def routes_list(route_table, resource_group, **kwargs):
    """
    .. versionadded:: 2019.2.0

    List all routes within a route table.

    :param route_table: The route table to query.

    :param resource_group: The resource group name assigned to the
        route table.

    CLI Example:

    .. code-block:: bash

        salt-call azurearm_network.routes_list test-rt-table testgroup

    """
    result = {}
    netconn = __utils__["azurearm.get_client"]("network", **kwargs)
    try:
        routes = __utils__["azurearm.paged_object_to_list"](
            netconn.routes.list(
                resource_group_name=resource_group, route_table_name=route_table
            )
        )

        for route in routes:
            result[route["name"]] = route
    except CloudError as exc:
        __utils__["azurearm.log_cloud_error"]("network", str(exc), **kwargs)
        result = {"error": str(exc)}

    return result


def route_table_delete(name, resource_group, **kwargs):
    """
    .. versionadded:: 2019.2.0

    Delete a route table.

    :param name: The name of the route table to delete.

    :param resource_group: The resource group name assigned to the
        route table.

    CLI Example:

    .. code-block:: bash

        salt-call azurearm_network.route_table_delete test-rt-table testgroup

    """
    result = False
    netconn = __utils__["azurearm.get_client"]("network", **kwargs)
    try:
        table = netconn.route_tables.delete(
            route_table_name=name, resource_group_name=resource_group
        )
        table.wait()
        result = True
    except CloudError as exc:
        __utils__["azurearm.log_cloud_error"]("network", str(exc), **kwargs)

    return result


def route_table_get(name, resource_group, **kwargs):
    """
    .. versionadded:: 2019.2.0

    Get details about a specific route table.

    :param name: The name of the route table to query.

    :param resource_group: The resource group name assigned to the
        route table.

    CLI Example:

    .. code-block:: bash

        salt-call azurearm_network.route_table_get test-rt-table testgroup

    """
    expand = kwargs.get("expand")

    netconn = __utils__["azurearm.get_client"]("network", **kwargs)

    try:
        table = netconn.route_tables.get(
            route_table_name=name, resource_group_name=resource_group, expand=expand
        )
        result = table.as_dict()
    except CloudError as exc:
        __utils__["azurearm.log_cloud_error"]("network", str(exc), **kwargs)
        result = {"error": str(exc)}

    return result


def route_table_create_or_update(name, resource_group, **kwargs):
    """
    .. versionadded:: 2019.2.0

    Create or update a route table within a specified resource group.

    :param name: The name of the route table to create.

    :param resource_group: The resource group name assigned to the
        route table.

    CLI Example:

    .. code-block:: bash

        salt-call azurearm_network.route_table_create_or_update test-rt-table testgroup

    """
    if "location" not in kwargs:
        rg_props = __salt__["azurearm_resource.resource_group_get"](
            resource_group, **kwargs
        )

        if "error" in rg_props:
            log.error("Unable to determine location from resource group specified.")
            return False
        kwargs["location"] = rg_props["location"]

    netconn = __utils__["azurearm.get_client"]("network", **kwargs)

    try:
        rt_tbl_model = __utils__["azurearm.create_object_model"](
            "network", "RouteTable", **kwargs
        )
    except TypeError as exc:
        result = {
            "error": "The object model could not be built. ({0})".format(str(exc))
        }
        return result

    try:
        table = netconn.route_tables.create_or_update(
            resource_group_name=resource_group,
            route_table_name=name,
            parameters=rt_tbl_model,
        )
        table.wait()
        tbl_result = table.result()
        result = tbl_result.as_dict()
    except CloudError as exc:
        __utils__["azurearm.log_cloud_error"]("network", str(exc), **kwargs)
        result = {"error": str(exc)}
    except SerializationError as exc:
        result = {
            "error": "The object model could not be parsed. ({0})".format(str(exc))
        }

    return result


def route_tables_list(resource_group, **kwargs):
    """
    .. versionadded:: 2019.2.0

    List all route tables within a resource group.

    :param resource_group: The resource group name to list route
        tables within.

    CLI Example:

    .. code-block:: bash

        salt-call azurearm_network.route_tables_list testgroup

    """
    result = {}
    netconn = __utils__["azurearm.get_client"]("network", **kwargs)
    try:
        tables = __utils__["azurearm.paged_object_to_list"](
            netconn.route_tables.list(resource_group_name=resource_group)
        )

        for table in tables:
            result[table["name"]] = table
    except CloudError as exc:
        __utils__["azurearm.log_cloud_error"]("network", str(exc), **kwargs)
        result = {"error": str(exc)}

    return result


def route_tables_list_all(**kwargs):
    """
    .. versionadded:: 2019.2.0

    List all route tables within a subscription.

    CLI Example:

    .. code-block:: bash

        salt-call azurearm_network.route_tables_list_all

    """
    result = {}
    netconn = __utils__["azurearm.get_client"]("network", **kwargs)
    try:
        tables = __utils__["azurearm.paged_object_to_list"](
            netconn.route_tables.list_all()
        )

        for table in tables:
            result[table["name"]] = table
    except CloudError as exc:
        __utils__["azurearm.log_cloud_error"]("network", str(exc), **kwargs)
        result = {"error": str(exc)}

    return result
