"""
Azure (ARM) DNS Execution Module

.. versionadded:: 3000

:maintainer: <devops@eitr.tech>, <devops@l2web.ca>
:maturity: new
:depends:
    * `azure-core <https://pypi.python.org/pypi/azure-core>`_ >= 1.15.0
    * `azure-batch <https://pypi.python.org/pypi/azure-batch>`_ >= 10.0.0
    * `azure-identity <https://pypi.python.org/pypi/azure-identity>`_ >= 1.6.0
    * `azure-common <https://pypi.python.org/pypi/azure-common>`_ >= 1.1.27
    * `azure-mgmt-core <https://pypi.python.org/pypi/azure-mgmt-core>`_ >= 1.2.2
    * `azure-mgmt-subscription <https://pypi.python.org/pypi/azure-mgmt-subscription>`_ >= 1.0.0
    * `azure-mgmt-compute <https://pypi.python.org/pypi/azure-mgmt-compute>`_ >= 20.0.0
    * `azure-mgmt-network <https://pypi.python.org/pypi/azure-mgmt-network>`_ >= 19.0.0
    * `azure-mgmt-resource <https://pypi.python.org/pypi/azure-mgmt-resource>`_ >= 18.0.0
    * `azure-mgmt-storage <https://pypi.python.org/pypi/azure-mgmt-storage>`_ >= 18.0.0
    * `azure-mgmt-web <https://pypi.python.org/pypi/azure-mgmt-web>`_ >= 2.0.0
    * `azure-storage-common <https://pypi.python.org/pypi/azure-storage-common>`_ >= 1.4.2
    * `azure-storage-blob <https://pypi.python.org/pypi/azure-storage-blob>`_ >= 12.8.1
    * `azure-storage-file <https://pypi.python.org/pypi/azure-storage-file>`_ >= 2.1.0
    * `azure-mgmt-dns <https://pypi.python.org/pypi/azure-mgmt-dns>`_ >= 8.0.0
    * `msrestazure <https://pypi.python.org/pypi/msrestazure>`_ >= 0.6.41

:platform: linux
:configuration:
    This module requires Azure Resource Manager credentials to be passed as keyword arguments
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

import logging

import salt.cloud
import salt.utils.azurearm

# Azure libs
HAS_LIBS = False
try:
    import azure.mgmt.dns.models  # pylint: disable=unused-import
    from msrest.exceptions import SerializationError
    from msrestazure.azure_exceptions import CloudError

    HAS_LIBS = True
except ImportError:
    pass

__virtualname__ = "azurearm_dns"

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


def record_set_create_or_update(
    name, zone_name, record_type, resource_group=None, cloud_provider=None, **kwargs
):
    """
    .. versionadded:: 3000

    Creates or updates a record set within a DNS zone.

    :param name: The name of the record set, relative to the name of the zone.

    :param zone_name: The name of the DNS zone (without a terminating dot).

    :param record_type:
        The type of DNS record in this record set. Record sets of type SOA can be
        updated but not created (they are created when the DNS zone is created).
        Possible values include: 'A', 'AAAA', 'CAA', 'CNAME', 'MX', 'NS', 'PTR', 'SOA', 'SRV', 'TXT'

    :param resource_group: The name of the resource group.

    :param cloud_provider: The Cloud Provider parameter allow you to use a defined
        provider config in /etc/salt/cloud.providers.d/
        with this paramater, you dont have to specify ressource_group as it is already defined in the provider.
        If you specify the ressource_group anyway, it will overwrite the cloud ressource_group value.

    CLI Example:

    .. code-block:: bash

        salt-call azurearm_dns.record_set_create_or_update myhost myzone A
            arecords='[{ipv4_address: 10.0.0.1}]' ttl=300 testgroup=

    .. code-block:: bash

        salt-call azurearm_dns.record_set_create_or_update myhost myzone A
            arecords='[{ipv4_address: 10.0.0.1}]' ttl=300 cloud_provider=my-azurearm-config

    """
    if cloud_provider is not None:
        conn_config = salt.utils.azurearm.get_config_from_cloud(cloud_provider)
        if "error" in conn_config:
            return conn_config
        else:
            if resource_group is None:
                resource_group = conn_config["resource_group"]
            else:
                conn_config["resource_group"] = resource_group
            kwargs.update(conn_config)

    dnsconn = __utils__["azurearm.get_client"]("dns", **kwargs)

    try:
        # This is broken and doesn't return any usefull data
        # parameters=record_set_model,
        record_set_model = __utils__["azurearm.create_object_model"](
            "dns", "RecordSet", **kwargs
        )
    except TypeError as exc:
        result = {"error": "The object model could not be built. ({})".format(str(exc))}
        return result

    try:
        parameters = {}
        parameters["ttl"] = kwargs["ttl"]
        parameters["arecords"] = kwargs["arecords"]
        record_set = dnsconn.record_sets.create_or_update(
            relative_record_set_name=name,
            zone_name=zone_name,
            resource_group_name=resource_group,
            record_type=record_type,
            parameters=parameters,
            if_match=kwargs.get("if_match"),
            if_none_match=kwargs.get("if_none_match"),
        )

        result = record_set.as_dict()
    except CloudError as exc:
        __utils__["azurearm.log_cloud_error"]("dns", str(exc), **kwargs)
        result = {"error": str(exc)}
    except SerializationError as exc:
        result = {
            "error": "The object model could not be parsed. ({})".format(str(exc))
        }

    return result


def record_set_delete(
    name, zone_name, record_type, resource_group=None, cloud_provider=None, **kwargs
):
    """
    .. versionadded:: 3000

    Deletes a record set from a DNS zone. This operation cannot be undone.

    :param name: The name of the record set, relative to the name of the zone.

    :param zone_name: The name of the DNS zone (without a terminating dot).

    :param record_type:
        The type of DNS record in this record set. Record sets of type SOA cannot be
        deleted (they are deleted when the DNS zone is deleted).
        Possible values include: 'A', 'AAAA', 'CAA', 'CNAME', 'MX', 'NS', 'PTR', 'SOA', 'SRV', 'TXT'

    :param resource_group: The name of the resource group.

    :param cloud_provider: The Cloud Provider parameter allow you to use a defined
        provider config in /etc/salt/cloud.providers.d/
        with this paramater, you dont have to specify ressource_group as it is already defined in the provider.
        If you specify the ressource_group anyway, it will overwrite the cloud ressource_group value.

    CLI Example:

    .. code-block:: bash

        salt-call azurearm_dns.record_set_delete myhost myzone A testgroup

    .. code-block:: bash

        salt-call azurearm_dns.record_set_delete myhost myzone A cloud_provider=my-azurearm-config

    """
    result = False

    if cloud_provider is not None:
        conn_config = salt.utils.azurearm.get_config_from_cloud(cloud_provider)
        if "error" in conn_config:
            return conn_config
        else:
            if resource_group is None:
                resource_group = conn_config["resource_group"]
            else:
                conn_config["resource_group"] = resource_group
            kwargs.update(conn_config)

    dnsconn = __utils__["azurearm.get_client"]("dns", **kwargs)
    try:
        record_set = dnsconn.record_sets.delete(
            relative_record_set_name=name,
            zone_name=zone_name,
            resource_group_name=resource_group,
            record_type=record_type,
            if_match=kwargs.get("if_match"),
        )
        result = True
    except CloudError as exc:
        __utils__["azurearm.log_cloud_error"]("dns", str(exc), **kwargs)

    return result


def record_set_get(
    name, zone_name, record_type, resource_group=None, cloud_provider=None, **kwargs
):
    """
    .. versionadded:: 3000

    Get a dictionary representing a record set's properties.

    :param name: The name of the record set, relative to the name of the zone.

    :param zone_name: The name of the DNS zone (without a terminating dot).

    :param record_type:
        The type of DNS record in this record set.
        Possible values include: 'A', 'AAAA', 'CAA', 'CNAME', 'MX', 'NS', 'PTR', 'SOA', 'SRV', 'TXT'

    :param resource_group: The name of the resource group.

    :param cloud_provider: The Cloud Provider parameter allow you to use a defined
        provider config in /etc/salt/cloud.providers.d/
        with this paramater, you dont have to specify ressource_group as it is already defined in the provider.
        If you specify the ressource_group anyway, it will overwrite the cloud ressource_group value.

    CLI Example:

    .. code-block:: bash

        salt-call azurearm_dns.record_set_get '@' myzone SOA testgroup

    .. code-block:: bash

        salt-call azurearm_dns.record_set_get '@' myzone SOA cloud_provider=my-azurearm-config

    """

    if cloud_provider is not None:
        conn_config = salt.utils.azurearm.get_config_from_cloud(cloud_provider)
        if "error" in conn_config:
            return conn_config
        else:
            if resource_group is None:
                resource_group = conn_config["resource_group"]
            else:
                conn_config["resource_group"] = resource_group
            kwargs.update(conn_config)

    dnsconn = __utils__["azurearm.get_client"]("dns", **kwargs)
    try:
        record_set = dnsconn.record_sets.get(
            relative_record_set_name=name,
            zone_name=zone_name,
            resource_group_name=resource_group,
            record_type=record_type,
        )
        result = record_set.as_dict()

    except CloudError as exc:
        __utils__["azurearm.log_cloud_error"]("dns", str(exc), **kwargs)
        result = {"error": str(exc)}

    return result


def record_sets_list_by_type(
    zone_name,
    record_type,
    resource_group=None,
    cloud_provider=None,
    top=None,
    recordsetnamesuffix=None,
    **kwargs
):
    """
    .. versionadded:: 3000

    Lists the record sets of a specified type in a DNS zone.

    :param zone_name: The name of the DNS zone (without a terminating dot).

    :param record_type:
        The type of record sets to enumerate.
        Possible values include: 'A', 'AAAA', 'CAA', 'CNAME', 'MX', 'NS', 'PTR', 'SOA', 'SRV', 'TXT'

    :param top:
        The maximum number of record sets to return. If not specified,
        returns up to 100 record sets.

    :param recordsetnamesuffix:
        The suffix label of the record set name that has
        to be used to filter the record set enumerations.

    :param resource_group: The name of the resource group.

    :param cloud_provider: The Cloud Provider parameter allow you to use a defined
        provider config in /etc/salt/cloud.providers.d/
        with this paramater, you don't have to specify ressource_group as it is already defined in the provider.
        If you specify the ressource_group anyway, it will overwrite the cloud ressource_group value.

    CLI Example:

    .. code-block:: bash

        salt-call azurearm_dns.record_sets_list_by_type myzone SOA testgroup

    .. code-block:: bash

        salt-call azurearm_dns.record_sets_list_by_type myzone SOA cloud_provider=my-azurearm-config

    """
    result = {}

    if cloud_provider is not None:
        conn_config = salt.utils.azurearm.get_config_from_cloud(cloud_provider)
        if "error" in conn_config:
            return conn_config
        else:
            if resource_group is None:
                resource_group = conn_config["resource_group"]
            else:
                conn_config["resource_group"] = resource_group
            kwargs.update(conn_config)

    dnsconn = __utils__["azurearm.get_client"]("dns", **kwargs)
    try:
        record_sets = __utils__["azurearm.paged_object_to_list"](
            dnsconn.record_sets.list_by_type(
                zone_name=zone_name,
                resource_group_name=resource_group,
                record_type=record_type,
                top=top,
                recordsetnamesuffix=recordsetnamesuffix,
            )
        )

        for record_set in record_sets:
            result[record_set["name"]] = record_set
    except CloudError as exc:
        __utils__["azurearm.log_cloud_error"]("dns", str(exc), **kwargs)
        result = {"error": str(exc)}

    return result


def record_sets_list_by_dns_zone(
    zone_name,
    resource_group=None,
    cloud_provider=None,
    top=None,
    recordsetnamesuffix=None,
    **kwargs
):
    """
    .. versionadded:: 3000

    Lists all record sets in a DNS zone.

    :param zone_name: The name of the DNS zone (without a terminating dot).

    :param resource_group: The name of the resource group.

    :param top:
        The maximum number of record sets to return. If not specified,
        returns up to 100 record sets.

    :param recordsetnamesuffix:
        The suffix label of the record set name that has
        to be used to filter the record set enumerations.

    :param cloud_provider: The Cloud Provider parameter allow you to use a defined
        provider config in /etc/salt/cloud.providers.d/
        with this paramater, you dont have to specify ressource_group as it is already defined in the provider.
        If you specify the ressource_group anyway, it will overwrite the cloud ressource_group value.

    CLI Example:

    .. code-block:: bash

        salt-call azurearm_dns.record_sets_list_by_dns_zone myzone testgroup

    .. code-block:: bash

        salt-call azurearm_dns.record_sets_list_by_dns_zone myzone cloud_provider=my-azurearm-config

    """
    result = {}

    if cloud_provider is not None:
        conn_config = salt.utils.azurearm.get_config_from_cloud(cloud_provider)
        if "error" in conn_config:
            return conn_config
        else:
            if resource_group is None:
                resource_group = conn_config["resource_group"]
            else:
                conn_config["resource_group"] = resource_group
            kwargs.update(conn_config)

    dnsconn = __utils__["azurearm.get_client"]("dns", **kwargs)
    try:
        record_sets = __utils__["azurearm.paged_object_to_list"](
            dnsconn.record_sets.list_by_dns_zone(
                zone_name=zone_name,
                resource_group_name=resource_group,
                top=top,
                recordsetnamesuffix=recordsetnamesuffix,
            )
        )

        for record_set in record_sets:
            result[record_set["name"]] = record_set
    except CloudError as exc:
        __utils__["azurearm.log_cloud_error"]("dns", str(exc), **kwargs)
        result = {"error": str(exc)}

    return result


def zone_create_or_update(name, resource_group=None, cloud_provider=None, **kwargs):
    """
    .. versionadded:: 3000

    Creates or updates a DNS zone. Does not modify DNS records within the zone.

    :param name: The name of the DNS zone to create (without a terminating dot).

    :param resource_group: The name of the resource group.

    :param cloud_provider: The Cloud Provider parameter allow you to use a defined
        provider config in /etc/salt/cloud.providers.d/
        with this paramater, you dont have to specify ressource_group as it is already defined in the provider.
        If you specify the ressource_group anyway, it will overwrite the cloud ressource_group value.

    CLI Example:

    .. code-block:: bash

        salt-call azurearm_dns.zone_create_or_update myzone testgroup

    .. code-block:: bash

        salt-call azurearm_dns.zone_create_or_update myzone cloud_provider=my-azurearm-config

    """
    if cloud_provider is not None:
        conn_config = salt.utils.azurearm.get_config_from_cloud(cloud_provider)
        if "error" in conn_config:
            return conn_config
        else:
            if resource_group is None:
                resource_group = conn_config["resource_group"]
            else:
                conn_config["resource_group"] = resource_group
            kwargs.update(conn_config)

    # DNS zones are global objects
    kwargs["location"] = "global"
    dnsconn = __utils__["azurearm.get_client"]("dns", **kwargs)

    # Convert list of ID strings to list of dictionaries with id key.
    if isinstance(kwargs.get("registration_virtual_networks"), list):
        kwargs["registration_virtual_networks"] = [
            {"id": vnet} for vnet in kwargs["registration_virtual_networks"]
        ]

    if isinstance(kwargs.get("resolution_virtual_networks"), list):
        kwargs["resolution_virtual_networks"] = [
            {"id": vnet} for vnet in kwargs["resolution_virtual_networks"]
        ]

    try:
        zone_model = __utils__["azurearm.create_object_model"]("dns", "Zone", **kwargs)
    except TypeError as exc:
        result = {"error": "The object model could not be built. ({})".format(str(exc))}
        return result

    try:
        zone = dnsconn.zones.create_or_update(
            zone_name=name,
            resource_group_name=resource_group,
            parameters=zone_model,
            if_match=kwargs.get("if_match"),
            if_none_match=kwargs.get("if_none_match"),
        )
        result = zone.as_dict()
    except CloudError as exc:
        __utils__["azurearm.log_cloud_error"]("dns", str(exc), **kwargs)
        result = {"error": str(exc)}
    except SerializationError as exc:
        result = {
            "error": "The object model could not be parsed. ({})".format(str(exc))
        }

    return result


def zone_delete(name, resource_group=None, cloud_provider=None, **kwargs):
    """
    .. versionadded:: 3000

    Delete a DNS zone within a resource group.

    :param name: The name of the DNS zone to delete.

    :param resource_group: The name of the resource group.

    :param cloud_provider: The Cloud Provider parameter allow you to use a defined
        provider config in /etc/salt/cloud.providers.d/
        with this paramater, you dont have to specify ressource_group as it is already defined in the provider.
        If you specify the ressource_group anyway, it will overwrite the cloud ressource_group value.

    CLI Example:

    .. code-block:: bash

        salt-call azurearm_dns.zone_delete myzone testgroup

    .. code-block:: bash

        salt-call azurearm_dns.zone_delete myzone cloud_provider=my-azurearm-config

    """
    result = False

    if cloud_provider is not None:
        conn_config = salt.utils.azurearm.get_config_from_cloud(cloud_provider)
        if "error" in conn_config:
            return conn_config
        else:
            if resource_group is None:
                resource_group = conn_config["resource_group"]
            else:
                conn_config["resource_group"] = resource_group
            kwargs.update(conn_config)

    dnsconn = __utils__["azurearm.get_client"]("dns", **kwargs)
    try:
        zone = dnsconn.zones.begin_delete(
            zone_name=name,
            resource_group_name=resource_group,
            if_match=kwargs.get("if_match"),
        )
        zone.wait()
        result = True
    except CloudError as exc:
        __utils__["azurearm.log_cloud_error"]("dns", str(exc), **kwargs)

    return result


def zone_get(name, resource_group=None, cloud_provider=None, **kwargs):
    """
    .. versionadded:: 3000

    Get a dictionary representing a DNS zone's properties, but not the
    record sets within the zone.

    :param name: The DNS zone to get.

    :param resource_group: The name of the resource group.

    :param cloud_provider: The Cloud Provider parameter allow you to use a defined
        provider config in /etc/salt/cloud.providers.d/
        with this paramater, you dont have to specify ressource_group as it is already defined in the provider.
        If you specify the ressource_group anyway, it will overwrite the cloud ressource_group value.

    CLI Example:

    .. code-block:: bash

        salt-call azurearm_dns.zone_get myzone testgroup

    .. code-block:: bash

        salt-call azurearm_dns.zone_get myzone cloud_provider=my-azurearm-config

    """
    if cloud_provider is not None:
        conn_config = salt.utils.azurearm.get_config_from_cloud(cloud_provider)
        if "error" in conn_config:
            return conn_config
        else:
            if resource_group is None:
                resource_group = conn_config["resource_group"]
            else:
                conn_config["resource_group"] = resource_group
            kwargs.update(conn_config)

    dnsconn = __utils__["azurearm.get_client"]("dns", **kwargs)
    try:
        zone = dnsconn.zones.get(zone_name=name, resource_group_name=resource_group)
        result = zone.as_dict()

    except CloudError as exc:
        __utils__["azurearm.log_cloud_error"]("dns", str(exc), **kwargs)
        result = {"error": str(exc)}

    return result


def zones_list_by_resource_group(
    resource_group=None, cloud_provider=None, top=None, **kwargs
):
    """
    .. versionadded:: 3000

    Lists the DNS zones in a resource group.

    :param resource_group: The name of the resource group.

    :param top:
        The maximum number of DNS zones to return. If not specified,
        returns up to 100 zones.

    :param cloud_provider: The Cloud Provider parameter allow you to use a defined
        provider config in /etc/salt/cloud.providers.d/
        with this paramater, you dont have to specify ressource_group as it is already defined in the provider.
        If you specify the ressource_group anyway, it will overwrite the cloud ressource_group value.

    CLI Example:

    .. code-block:: bash

        salt-call azurearm_dns.zones_list_by_resource_group testgroup

    .. code-block:: bash

        salt-call azurearm_dns.zones_list_by_resource_group cloud_provider=my-azurearm-config

    """
    result = {}

    if cloud_provider is not None:
        conn_config = salt.utils.azurearm.get_config_from_cloud(cloud_provider)
        if "error" in conn_config:
            return conn_config
        else:
            if resource_group is None:
                resource_group = conn_config["resource_group"]
            else:
                conn_config["resource_group"] = resource_group
            kwargs.update(conn_config)

    dnsconn = __utils__["azurearm.get_client"]("dns", **kwargs)
    try:
        zones = __utils__["azurearm.paged_object_to_list"](
            dnsconn.zones.list_by_resource_group(
                resource_group_name=resource_group, top=top
            )
        )

        for zone in zones:
            result[zone["name"]] = zone
    except CloudError as exc:
        __utils__["azurearm.log_cloud_error"]("dns", str(exc), **kwargs)
        result = {"error": str(exc)}

    return result


def zones_list(top=None, cloud_provider=None, **kwargs):
    """
    .. versionadded:: 3000

    Lists the DNS zones in all resource groups in a subscription.

    :param top:
        The maximum number of DNS zones to return. If not specified,
        returns up to 100 zones.

    :param cloud_provider: The Cloud Provider parameter allow you to use a defined
        provider config in /etc/salt/cloud.providers.d/
        with this paramater, you dont have to specify / duplicate informations already provided in the cloud
        provider config file.

    CLI Example:

    .. code-block:: bash

        salt-call azurearm_dns.zones_list

    .. code-block:: bash

        salt-call azurearm_dns.zones_list cloud_provider=my-azurearm-config

    """
    result = {}

    if cloud_provider is not None:
        conn_config = salt.utils.azurearm.get_config_from_cloud(cloud_provider)
        if "error" in conn_config:
            return conn_config
        else:
            kwargs.update(conn_config)

    dnsconn = __utils__["azurearm.get_client"]("dns", **kwargs)
    try:
        zones = __utils__["azurearm.paged_object_to_list"](dnsconn.zones.list(top=top))

        for zone in zones:
            result[zone["name"]] = zone
    except CloudError as exc:
        __utils__["azurearm.log_cloud_error"]("dns", str(exc), **kwargs)
        result = {"error": str(exc)}

    return result
