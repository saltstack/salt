"""
Azure (ARM) Compute Execution Module

.. versionadded:: 2019.2.0

:maintainer: <devops@decisionlab.io>, <devops@l2web.ca>
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
    * `msrestazure <https://pypi.python.org/pypi/msrestazure>`_ >= 0.6.41
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

import logging

import salt.cloud
import salt.loader
import salt.utils.azurearm

# Azure libs
HAS_LIBS = False
try:
    import azure.mgmt.compute.models  # pylint: disable=unused-import
    from msrest.exceptions import SerializationError
    from msrestazure.azure_exceptions import CloudError

    HAS_LIBS = True
except ImportError:
    pass

__virtualname__ = "azurearm_compute"

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


def get_config_from_cloud(cloud_provider):
    client = salt.cloud.CloudClient(path="/etc/salt/cloud")
    conn_kwargs = client.opts["providers"][cloud_provider]["azurearm"]
    return conn_kwargs


def availability_set_create_or_update(
    name, resource_group=None, cloud_provider=None, **kwargs
):  # pylint: disable=invalid-name
    """
    .. versionadded:: 2019.2.0

    Create or update an availability set.

    :param name: The availability set to create.

    :param resource_group: The resource group name assigned to the
        availability set.

    :param cloud_provider: The Cloud Provider parameter allow you to use a defined
        provider config in /etc/salt/cloud.providers.d/
        with this paramater, you dont have to specify ressource_group as it is already defined in the provider

    CLI Example:

    .. code-block:: bash

        salt-call azurearm_compute.availability_set_create_or_update testset testgroup

    .. code-block:: bash

        salt-call azurearm_compute.availability_set_create_or_update testset cloud_provider=my-azurearm-config

    """
    if cloud_provider is not None:
        conn_config = get_config_from_cloud(cloud_provider)
        resource_group = conn_config["resource_group"]
        kwargs.update(conn_config)

    if "location" not in kwargs:
        rg_props = salt.azurearm_resource.resource_group_get(resource_group, **kwargs)

        if "error" in rg_props:
            log.error("Unable to determine location from resource group specified.")
            return False
        kwargs["location"] = rg_props["location"]

    compconn = salt.utils.azurearm.get_client("compute", **kwargs)

    # Use VM names to link to the IDs of existing VMs.
    if isinstance(kwargs.get("virtual_machines"), list):
        vm_list = []
        for vm_name in kwargs.get("virtual_machines"):
            vm_instance = salt.azurearm_compute.virtual_machine_get(
                name=vm_name, resource_group=resource_group, **kwargs
            )
            if "error" not in vm_instance:
                vm_list.append({"id": str(vm_instance["id"])})
        kwargs["virtual_machines"] = vm_list

    try:
        setmodel = salt.utils.azurearm.create_object_model(
            "compute", "AvailabilitySet", **kwargs
        )
    except TypeError as exc:
        result = {"error": "The object model could not be built. ({})".format(str(exc))}
        return result

    try:
        av_set = compconn.availability_sets.create_or_update(
            resource_group_name=resource_group,
            availability_set_name=name,
            parameters=setmodel,
        )
        result = av_set.as_dict()

    except CloudError as exc:
        salt.utils.azurearm.log_cloud_error("compute", str(exc), **kwargs)
        result = {"error": str(exc)}
    except SerializationError as exc:
        result = {
            "error": "The object model could not be parsed. ({})".format(str(exc))
        }

    return result


def availability_set_delete(name, resource_group=None, cloud_provider=None, **kwargs):
    """
    .. versionadded:: 2019.2.0

    Delete an availability set.

    :param name: The availability set to delete.

    :param resource_group: The resource group name assigned to the
        availability set.

    :param cloud_provider: The Cloud Provider parameter allow you to use a defined
        provider config in /etc/salt/cloud.providers.d/
        with this paramater, you dont have to specify ressource_group as it is already defined in the provider

    CLI Example:

    .. code-block:: bash

        salt-call azurearm_compute.availability_set_delete testset testgroup

    .. code-block:: bash

        salt-call azurearm_compute.availability_set_delete testset cloud_provider=my-azurearm-config

    """
    result = False
    if cloud_provider is not None:
        conn_config = get_config_from_cloud(cloud_provider)
        resource_group = conn_config["resource_group"]
        kwargs.update(conn_config)
    compconn = salt.utils.azurearm.get_client("compute", **kwargs)
    try:
        compconn.availability_sets.delete(
            resource_group_name=resource_group, availability_set_name=name
        )
        result = True

    except CloudError as exc:
        salt.utils.azurearm.log_cloud_error("compute", str(exc), **kwargs)

    return result


def availability_set_get(name, resource_group=None, cloud_provider=None, **kwargs):
    """
    .. versionadded:: 2019.2.0

    Get a dictionary representing an availability set's properties.

    :param name: The availability set to get.

    :param resource_group: The resource group name assigned to the
        availability set.

    :param cloud_provider: The Cloud Provider parameter allow you to use a defined
        provider config in /etc/salt/cloud.providers.d/
        with this paramater, you dont have to specify ressource_group as it is already defined in the provider

    CLI Example:

    .. code-block:: bash

        salt-call azurearm_compute.availability_set_get testset testgroup

    .. code-block:: bash

        salt-call azurearm_compute.availability_set_get testset cloud_provider=my-azurearm-config

    """
    if cloud_provider is not None:
        conn_config = get_config_from_cloud(cloud_provider)
        resource_group = conn_config["resource_group"]
        kwargs.update(conn_config)
    compconn = salt.utils.azurearm.get_client("compute", **kwargs)
    try:
        av_set = compconn.availability_sets.get(
            resource_group_name=resource_group, availability_set_name=name
        )
        result = av_set.as_dict()

    except CloudError as exc:
        salt.utils.azurearm.log_cloud_error("compute", str(exc), **kwargs)
        result = {"error": str(exc)}

    return result


def availability_sets_list(resource_group=None, cloud_provider=None, **kwargs):
    """
    .. versionadded:: 2019.2.0

    List all availability sets within a resource group.

    :param resource_group: The resource group name to list availability
        sets within.

    :param cloud_provider: The Cloud Provider parameter allow you to use a defined
        provider config in /etc/salt/cloud.providers.d/
        with this paramater, you dont have to specify ressource_group as it is already defined in the provider

    CLI Example:

    .. code-block:: bash

        salt-call azurearm_compute.availability_sets_list testgroup

    .. code-block:: bash

        salt-call azurearm_compute.availability_sets_list cloud_provider=my-azurearm-config

    """
    result = {}
    if cloud_provider is not None:
        conn_config = get_config_from_cloud(cloud_provider)
        resource_group = conn_config["resource_group"]
        kwargs.update(conn_config)
    compconn = salt.utils.azurearm.get_client("compute", **kwargs)
    try:
        avail_sets = salt.utils.azurearm.paged_object_to_list(
            compconn.availability_sets.list(resource_group_name=resource_group)
        )

        for avail_set in avail_sets:
            result[avail_set["name"]] = avail_set
    except CloudError as exc:
        salt.utils.azurearm.log_cloud_error("compute", str(exc), **kwargs)
        result = {"error": str(exc)}

    return result


def availability_sets_list_available_sizes(
    name, resource_group=None, cloud_provider=None, **kwargs
):  # pylint: disable=invalid-name
    """
    .. versionadded:: 2019.2.0

    List all available virtual machine sizes that can be used to
    to create a new virtual machine in an existing availability set.

    :param name: The availability set name to list available
        virtual machine sizes within.

    :param resource_group: The resource group name to list available
        availability set sizes within.

    :param cloud_provider: The Cloud Provider parameter allow you to use a defined
        provider config in /etc/salt/cloud.providers.d/
        with this paramater, you dont have to specify ressource_group as it is already defined in the provider

    CLI Example:

    .. code-block:: bash

        salt-call azurearm_compute.availability_sets_list_available_sizes testset testgroup

    .. code-block:: bash

        salt-call azurearm_compute.availability_sets_list_available_sizes testset cloud_provider=my-azurearm-config

    """
    result = {}
    if cloud_provider is not None:
        conn_config = get_config_from_cloud(cloud_provider)
        resource_group = conn_config["resource_group"]
        kwargs.update(conn_config)
    compconn = salt.utils.azurearm.get_client("compute", **kwargs)
    try:
        sizes = salt.utils.azurearm.paged_object_to_list(
            compconn.availability_sets.list_available_sizes(
                resource_group_name=resource_group, availability_set_name=name
            )
        )

        for size in sizes:
            result[size["name"]] = size
    except CloudError as exc:
        salt.utils.azurearm.log_cloud_error("compute", str(exc), **kwargs)
        result = {"error": str(exc)}

    return result


def virtual_machine_capture(
    name,
    destination_name,
    resource_group=None,
    cloud_provider=None,
    prefix="capture-",
    overwrite=False,
    **kwargs
):
    """
    .. versionadded:: 2019.2.0

    Captures the VM by copying virtual hard disks of the VM and outputs
    a template that can be used to create similar VMs.

    :param name: The name of the virtual machine.

    :param destination_name: The destination container name.

    :param resource_group: The resource group name assigned to the
        virtual machine.

    :param prefix: (Default: 'capture-') The captured virtual hard disk's name prefix.

    :param overwrite: (Default: False) Overwrite the destination disk in case of conflict.

    :param cloud_provider: The Cloud Provider parameter allow you to use a defined
        provider config in /etc/salt/cloud.providers.d/
        with this paramater, you dont have to specify ressource_group as it is already defined in the provider

    CLI Example:

    .. code-block:: bash

        salt-call azurearm_compute.virtual_machine_capture testvm testcontainer testgroup

    .. code-block:: bash

        salt-call azurearm_compute.virtual_machine_capture testvm testcontainer cloud_provider=my-azurearm-config

    """
    if cloud_provider is not None:
        conn_config = get_config_from_cloud(cloud_provider)
        resource_group = conn_config["resource_group"]
        kwargs.update(conn_config)
    # pylint: disable=invalid-name
    VirtualMachineCaptureParameters = getattr(
        azure.mgmt.compute.models, "VirtualMachineCaptureParameters"
    )

    compconn = salt.utils.azurearm.get_client("compute", **kwargs)
    try:
        # pylint: disable=invalid-name
        vm = compconn.virtual_machines.capture(
            resource_group_name=resource_group,
            vm_name=name,
            parameters=VirtualMachineCaptureParameters(
                vhd_prefix=prefix,
                destination_container_name=destination_name,
                overwrite_vhds=overwrite,
            ),
        )
        vm.wait()
        vm_result = vm.result()
        result = vm_result.as_dict()
    except CloudError as exc:
        salt.utils.azurearm.log_cloud_error("compute", str(exc), **kwargs)
        result = {"error": str(exc)}

    return result


def virtual_machine_get(name, resource_group=None, cloud_provider=None, **kwargs):
    """
    .. versionadded:: 2019.2.0

    Retrieves information about the model view or the instance view of a
    virtual machine.

    :param name: The name of the virtual machine.

    :param resource_group: The resource group name assigned to the
        virtual machine.

    :param cloud_provider: The Cloud Provider parameter allow you to use a defined
        provider config in /etc/salt/cloud.providers.d/
        with this paramater, you dont have to specify ressource_group as it is already defined in the provider

    CLI Example:

    .. code-block:: bash

        salt-call azurearm_compute.virtual_machine_get testvm testgroup

    .. code-block:: bash

        salt-call azurearm_compute.virtual_machine_get testvm cloud_provider=my-azurearm-config

    """
    if cloud_provider is not None:
        conn_config = get_config_from_cloud(cloud_provider)
        resource_group = conn_config["resource_group"]
        kwargs.update(conn_config)
    expand = kwargs.get("expand")
    compconn = salt.utils.azurearm.get_client("compute", **kwargs)
    try:
        # pylint: disable=invalid-name
        vm = compconn.virtual_machines.get(
            resource_group_name=resource_group, vm_name=name, expand=expand
        )
        result = vm.as_dict()
    except CloudError as exc:
        salt.utils.azurearm.log_cloud_error("compute", str(exc), **kwargs)
        result = {"error": str(exc)}

    return result


def virtual_machine_convert_to_managed_disks(
    name, resource_group=None, cloud_provider=None, **kwargs
):  # pylint: disable=invalid-name
    """
    .. versionadded:: 2019.2.0

    Converts virtual machine disks from blob-based to managed disks. Virtual
    machine must be stop-deallocated before invoking this operation.

    :param name: The name of the virtual machine to convert.

    :param resource_group: The resource group name assigned to the
        virtual machine.

    :param cloud_provider: The Cloud Provider parameter allow you to use a defined
        provider config in /etc/salt/cloud.providers.d/
        with this paramater, you dont have to specify ressource_group as it is already defined in the provider

    CLI Example:

    .. code-block:: bash

        salt-call azurearm_compute.virtual_machine_convert_to_managed_disks testvm testgroup

    .. code-block:: bash

        salt-call azurearm_compute.virtual_machine_convert_to_managed_disks testvm cloud_provider=my-azurearm-config

    """
    if cloud_provider is not None:
        conn_config = get_config_from_cloud(cloud_provider)
        resource_group = conn_config["resource_group"]
        kwargs.update(conn_config)
    compconn = salt.utils.azurearm.get_client("compute", **kwargs)
    try:
        # pylint: disable=invalid-name
        vm = compconn.virtual_machines.convert_to_managed_disks(
            resource_group_name=resource_group, vm_name=name
        )
        vm.wait()
        vm_result = vm.result()
        result = vm_result.as_dict()
    except CloudError as exc:
        salt.utils.azurearm.log_cloud_error("compute", str(exc), **kwargs)
        result = {"error": str(exc)}

    return result


def virtual_machine_deallocate(
    name, resource_group=None, cloud_provider=None, **kwargs
):
    """
    .. versionadded:: 2019.2.0

    Power off a virtual machine and deallocate compute resources.

    :param name: The name of the virtual machine to deallocate.

    :param resource_group: The resource group name assigned to the
        virtual machine.

    :param cloud_provider: The Cloud Provider parameter allow you to use a defined
        provider config in /etc/salt/cloud.providers.d/
        with this paramater, you dont have to specify ressource_group as it is already defined in the provider

    CLI Example:

    .. code-block:: bash

        salt-call azurearm_compute.virtual_machine_deallocate testvm testgroup

    .. code-block:: bash

        salt-call azurearm_compute.virtual_machine_deallocate testvm cloud_provider=my-azurearm-config

    """
    if cloud_provider is not None:
        conn_config = get_config_from_cloud(cloud_provider)
        resource_group = conn_config["resource_group"]
        kwargs.update(conn_config)
    compconn = salt.utils.azurearm.get_client("compute", **kwargs)
    try:
        # pylint: disable=invalid-name
        vm = compconn.virtual_machines.deallocate(
            resource_group_name=resource_group, vm_name=name
        )
        vm.wait()
        vm_result = vm.result()
        result = vm_result.as_dict()
    except CloudError as exc:
        salt.utils.azurearm.log_cloud_error("compute", str(exc), **kwargs)
        result = {"error": str(exc)}

    return result


def virtual_machine_generalize(
    name, resource_group=None, cloud_provider=None, **kwargs
):
    """
    .. versionadded:: 2019.2.0

    Set the state of a virtual machine to 'generalized'.

    :param name: The name of the virtual machine.

    :param resource_group: The resource group name assigned to the
        virtual machine.

    :param cloud_provider: The Cloud Provider parameter allow you to use a defined
        provider config in /etc/salt/cloud.providers.d/
        with this paramater, you dont have to specify ressource_group as it is already defined in the provider

    CLI Example:

    .. code-block:: bash

        salt-call azurearm_compute.virtual_machine_generalize testvm testgroup

    .. code-block:: bash

        salt-call azurearm_compute.virtual_machine_generalize testvm cloud_provider=my-azurearm-config

    """
    result = False
    if cloud_provider is not None:
        conn_config = get_config_from_cloud(cloud_provider)
        resource_group = conn_config["resource_group"]
        kwargs.update(conn_config)
    compconn = salt.utils.azurearm.get_client("compute", **kwargs)
    try:
        compconn.virtual_machines.generalize(
            resource_group_name=resource_group, vm_name=name
        )
        result = True
    except CloudError as exc:
        salt.utils.azurearm.log_cloud_error("compute", str(exc), **kwargs)

    return result


def virtual_machines_list(resource_group=None, cloud_provider=None, **kwargs):
    """
    .. versionadded:: 2019.2.0

    List all virtual machines within a resource group.

    :param resource_group: The resource group name to list virtual
        machines within.

    :param cloud_provider: The Cloud Provider parameter allow you to use a defined
        provider config in /etc/salt/cloud.providers.d/
        with this paramater, you dont have to specify ressource_group as it is already defined in the provider

    CLI Example:

    .. code-block:: bash

        salt-call azurearm_compute.virtual_machines_list testgroup

    .. code-block:: bash

        salt-call azurearm_compute.virtual_machines_list cloud_provider=my-azurearm-config

    """
    result = {}
    if cloud_provider is not None:
        conn_config = get_config_from_cloud(cloud_provider)
        resource_group = conn_config["resource_group"]
        kwargs.update(conn_config)

    compconn = salt.utils.azurearm.get_client("compute", **kwargs)
    try:
        vms = salt.utils.azurearm.paged_object_to_list(
            compconn.virtual_machines.list(resource_group_name=resource_group)
        )
        for vm in vms:  # pylint: disable=invalid-name
            result[vm["name"]] = vm
    except CloudError as exc:
        salt.utils.azurearm.log_cloud_error("compute", str(exc), **kwargs)
        result = {"error": str(exc)}

    return result


def virtual_machines_list_all(cloud_provider=None, **kwargs):
    """
    .. versionadded:: 2019.2.0

    List all virtual machines within a subscription.

    :param cloud_provider: The Cloud Provider parameter allow you to use a defined
        provider config in /etc/salt/cloud.providers.d/
        with this paramater, you dont have to specify ressource_group as it is already defined in the provider

    CLI Example:

    .. code-block:: bash

        salt-call azurearm_compute.virtual_machines_list_all

    .. code-block:: bash

        salt-call azurearm_compute.virtual_machines_list_all cloud_provider=my-azurearm-config

    """
    result = {}
    if cloud_provider is not None:
        conn_config = get_config_from_cloud(cloud_provider)
        resource_group = conn_config["resource_group"]
        kwargs.update(conn_config)
    compconn = salt.utils.azurearm.get_client("compute", **kwargs)
    try:
        vms = salt.utils.azurearm.paged_object_to_list(
            compconn.virtual_machines.list_all()
        )
        for vm in vms:  # pylint: disable=invalid-name
            result[vm["name"]] = vm
    except CloudError as exc:
        salt.utils.azurearm.log_cloud_error("compute", str(exc), **kwargs)
        result = {"error": str(exc)}

    return result


def virtual_machines_list_available_sizes(
    name, resource_group=None, cloud_provider=None, **kwargs
):  # pylint: disable=invalid-name
    """
    .. versionadded:: 2019.2.0

    Lists all available virtual machine sizes to which the specified virtual
    machine can be resized.

    :param name: The name of the virtual machine.

    :param resource_group: The resource group name assigned to the
        virtual machine.

    :param cloud_provider: The Cloud Provider parameter allow you to use a defined
        provider config in /etc/salt/cloud.providers.d/
        with this paramater, you dont have to specify ressource_group as it is already defined in the provider

    CLI Example:

    .. code-block:: bash

        salt-call azurearm_compute.virtual_machines_list_available_sizes testvm testgroup

    .. code-block:: bash

        salt-call azurearm_compute.virtual_machines_list_available_sizes testvm cloud_provider=my-azurearm-config

    """
    result = {}
    if cloud_provider is not None:
        conn_config = get_config_from_cloud(cloud_provider)
        resource_group = conn_config["resource_group"]
        kwargs.update(conn_config)
    compconn = salt.utils.azurearm.get_client("compute", **kwargs)
    try:
        sizes = salt.utils.azurearm.paged_object_to_list(
            compconn.virtual_machines.list_available_sizes(
                resource_group_name=resource_group, vm_name=name
            )
        )
        for size in sizes:
            result[size["name"]] = size
    except CloudError as exc:
        salt.utils.azurearm.log_cloud_error("compute", str(exc), **kwargs)
        result = {"error": str(exc)}

    return result


def virtual_machine_power_off(name, resource_group=None, cloud_provider=None, **kwargs):
    """
    .. versionadded:: 2019.2.0

    Power off (stop) a virtual machine.

    :param name: The name of the virtual machine to stop.

    :param resource_group: The resource group name assigned to the
        virtual machine.

    :param cloud_provider: The Cloud Provider parameter allow you to use a defined
        provider config in /etc/salt/cloud.providers.d/
        with this paramater, you dont have to specify ressource_group as it is already defined in the provider

    CLI Example:

    .. code-block:: bash

        salt-call azurearm_compute.virtual_machine_power_off testvm testgroup

    .. code-block:: bash

        salt-call azurearm_compute.virtual_machine_power_off testvm cloud_provider=my-azurearm-config

    """
    if cloud_provider is not None:
        conn_config = get_config_from_cloud(cloud_provider)
        resource_group = conn_config["resource_group"]
        kwargs.update(conn_config)
    compconn = salt.utils.azurearm.get_client("compute", **kwargs)
    try:
        # pylint: disable=invalid-name
        vm = compconn.virtual_machines.power_off(
            resource_group_name=resource_group, vm_name=name
        )
        vm.wait()
        vm_result = vm.result()
        result = vm_result.as_dict()
    except CloudError as exc:
        salt.utils.azurearm.log_cloud_error("compute", str(exc), **kwargs)
        result = {"error": str(exc)}

    return result


def virtual_machine_restart(name, resource_group=None, cloud_provider=None, **kwargs):
    """
    .. versionadded:: 2019.2.0

    Restart a virtual machine.

    :param name: The name of the virtual machine to restart.

    :param resource_group: The resource group name assigned to the
        virtual machine.

    :param cloud_provider: The Cloud Provider parameter allow you to use a defined
        provider config in /etc/salt/cloud.providers.d/
        with this paramater, you dont have to specify ressource_group as it is already defined in the provider

    CLI Example:

    .. code-block:: bash

        salt-call azurearm_compute.virtual_machine_restart testvm testgroup

    .. code-block:: bash

        salt-call azurearm_compute.virtual_machine_restart testvm cloud_provider=my-azurearm-config

    """
    if cloud_provider is not None:
        conn_config = get_config_from_cloud(cloud_provider)
        resource_group = conn_config["resource_group"]
        kwargs.update(conn_config)
    compconn = salt.utils.azurearm.get_client("compute", **kwargs)
    try:
        # pylint: disable=invalid-name
        vm = compconn.virtual_machines.restart(
            resource_group_name=resource_group, vm_name=name
        )
        vm.wait()
        vm_result = vm.result()
        result = vm_result.as_dict()
    except CloudError as exc:
        salt.utils.azurearm.log_cloud_error("compute", str(exc), **kwargs)
        result = {"error": str(exc)}

    return result


def virtual_machine_start(name, resource_group=None, cloud_provider=None, **kwargs):
    """
    .. versionadded:: 2019.2.0

    Power on (start) a virtual machine.

    :param name: The name of the virtual machine to start.

    :param resource_group: The resource group name assigned to the
        virtual machine.

    :param cloud_provider: The Cloud Provider parameter allow you to use a defined
        provider config in /etc/salt/cloud.providers.d/
        with this paramater, you dont have to specify ressource_group as it is already defined in the provider

    CLI Example:

    .. code-block:: bash

        salt-call azurearm_compute.virtual_machine_start testvm testgroup

    .. code-block:: bash

        salt-call azurearm_compute.virtual_machine_start testvm cloud_provider=my-azurearm-config

    """
    if cloud_provider is not None:
        conn_config = get_config_from_cloud(cloud_provider)
        resource_group = conn_config["resource_group"]
        kwargs.update(conn_config)
    compconn = salt.utils.azurearm.get_client("compute", **kwargs)
    try:
        # pylint: disable=invalid-name
        vm = compconn.virtual_machines.start(
            resource_group_name=resource_group, vm_name=name
        )
        vm.wait()
        vm_result = vm.result()
        result = vm_result.as_dict()
    except CloudError as exc:
        salt.utils.azurearm.log_cloud_error("compute", str(exc), **kwargs)
        result = {"error": str(exc)}

    return result


def virtual_machine_redeploy(name, resource_group=None, cloud_provider=None, **kwargs):
    """
    .. versionadded:: 2019.2.0

    Redeploy a virtual machine.

    :param name: The name of the virtual machine to redeploy.

    :param resource_group: The resource group name assigned to the
        virtual machine.

    CLI Example:

    .. code-block:: bash

        salt-call azurearm_compute.virtual_machine_redeploy testvm testgroup

    """
    if cloud_provider is not None:
        conn_config = get_config_from_cloud(cloud_provider)
        resource_group = conn_config["resource_group"]
        kwargs.update(conn_config)
    compconn = salt.utils.azurearm.get_client("compute", **kwargs)
    try:
        # pylint: disable=invalid-name
        vm = compconn.virtual_machines.redeploy(
            resource_group_name=resource_group, vm_name=name
        )
        vm.wait()
        vm_result = vm.result()
        result = vm_result.as_dict()
    except CloudError as exc:
        salt.utils.azurearm.log_cloud_error("compute", str(exc), **kwargs)
        result = {"error": str(exc)}

    return result
