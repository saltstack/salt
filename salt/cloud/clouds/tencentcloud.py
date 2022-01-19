"""
Tencent Cloud Cloud Module
=============================

.. versionadded:: 3000

The Tencent Cloud Cloud Module is used to control access to the Tencent Cloud instance.
https://intl.cloud.tencent.com/

To use this module, set up the cloud configuration at
 ``/etc/salt/cloud.providers`` or ``/etc/salt/cloud.providers.d/*.conf``:

.. code-block:: yaml

    my-tencentcloud-config:
      driver: tencentcloud
      # Tencent Cloud Secret Id
      id: AKIDA64pOio9BMemkApzevX0HS169S4b750A
      # Tencent Cloud Secret Key
      key: 8r2xmPn0C5FDvRAlmcJimiTZKVRsk260
      # Tencent Cloud Region
      location: ap-guangzhou

:depends: tencentcloud-sdk-python
"""

import logging
import pprint
import time

import salt.config as config
import salt.utils.cloud
import salt.utils.data
import salt.utils.json
from salt.exceptions import (
    SaltCloudExecutionFailure,
    SaltCloudExecutionTimeout,
    SaltCloudNotFound,
    SaltCloudSystemExit,
)

try:
    # Try import tencentcloud sdk
    from tencentcloud.common import credential  # pylint: disable=no-name-in-module

    # pylint: disable=no-name-in-module
    from tencentcloud.common.profile.client_profile import ClientProfile
    from tencentcloud.cvm.v20170312 import cvm_client
    from tencentcloud.cvm.v20170312 import models as cvm_models
    from tencentcloud.vpc.v20170312 import vpc_client
    from tencentcloud.vpc.v20170312 import models as vpc_models

    # pylint: enable=no-name-in-module

    HAS_TENCENTCLOUD_SDK = True
except ImportError:
    HAS_TENCENTCLOUD_SDK = False

# Get logging started
log = logging.getLogger(__name__)

# The default region
DEFAULT_REGION = "ap-guangzhou"

# The Tencent Cloud
__virtualname__ = "tencentcloud"


def __virtual__():
    """
    Only load in this module if the Tencent Cloud configurations are in place
    """
    if get_configured_provider() is False:
        return False

    if get_dependencies() is False:
        return False

    return __virtualname__


def _get_active_provider_name():
    try:
        return __active_provider_name__.value()
    except AttributeError:
        return __active_provider_name__


def get_configured_provider():
    """
    Return the first configured instance.
    """
    return config.is_provider_configured(
        __opts__, _get_active_provider_name() or __virtualname__, ("id", "key")
    )


def get_dependencies():
    """
    Warn if dependencies aren't met.
    """
    return config.check_driver_dependencies(
        __virtualname__, {"tencentcloud-sdk-python": HAS_TENCENTCLOUD_SDK}
    )


def get_provider_client(name=None):
    """
    Return a new provider client
    """
    provider = get_configured_provider()

    secretId = provider.get("id")
    secretKey = provider.get("key")
    region = __get_location(None)

    cpf = ClientProfile()
    cpf.language = "en-US"
    crd = credential.Credential(secretId, secretKey)

    if name == "cvm_client":
        client = cvm_client.CvmClient(crd, region, cpf)
    elif name == "vpc_client":
        client = vpc_client.VpcClient(crd, region, cpf)
    else:
        raise SaltCloudSystemExit("Client name {} is not supported".format(name))

    return client


def avail_locations(call=None):
    """
    Return Tencent Cloud available region

    CLI Example:

    .. code-block:: bash

        salt-cloud --list-locations my-tencentcloud-config
        salt-cloud -f avail_locations my-tencentcloud-config
    """
    if call == "action":
        raise SaltCloudSystemExit(
            "The avail_locations function must be called with "
            "-f or --function, or with the --list-locations option"
        )

    client = get_provider_client("cvm_client")
    req = cvm_models.DescribeRegionsRequest()
    resp = client.DescribeRegions(req)

    ret = {}
    for region in resp.RegionSet:
        if region.RegionState != "AVAILABLE":
            continue
        ret[region.Region] = region.RegionName

    return ret


def avail_images(call=None):
    """
    Return Tencent Cloud available image

    CLI Example:

    .. code-block:: bash

        salt-cloud --list-images my-tencentcloud-config
        salt-cloud -f avail_images my-tencentcloud-config
    """
    if call == "action":
        raise SaltCloudSystemExit(
            "The avail_images function must be called with "
            "-f or --function, or with the --list-images option"
        )

    return _get_images(
        ["PUBLIC_IMAGE", "PRIVATE_IMAGE", "IMPORT_IMAGE", "SHARED_IMAGE"]
    )


def avail_sizes(call=None):
    """
    Return Tencent Cloud available instance type

    CLI Example:

    .. code-block:: bash

        salt-cloud --list-sizes my-tencentcloud-config
        salt-cloud -f avail_sizes my-tencentcloud-config
    """
    if call == "action":
        raise SaltCloudSystemExit(
            "The avail_sizes function must be called with "
            "-f or --function, or with the --list-sizes option"
        )

    client = get_provider_client("cvm_client")
    req = cvm_models.DescribeInstanceTypeConfigsRequest()
    resp = client.DescribeInstanceTypeConfigs(req)

    ret = {}
    for typeConfig in resp.InstanceTypeConfigSet:
        ret[typeConfig.InstanceType] = {
            "Zone": typeConfig.Zone,
            "InstanceFamily": typeConfig.InstanceFamily,
            "Memory": "{}GB".format(typeConfig.Memory),
            "CPU": "{}-Core".format(typeConfig.CPU),
        }
        if typeConfig.GPU:
            ret[typeConfig.InstanceType]["GPU"] = "{}-Core".format(typeConfig.GPU)

    return ret


def list_securitygroups(call=None):
    """
    Return all Tencent Cloud security groups in current region

    CLI Example:

    .. code-block:: bash

        salt-cloud -f list_securitygroups my-tencentcloud-config
    """
    if call == "action":
        raise SaltCloudSystemExit(
            "The list_securitygroups function must be called with -f or --function."
        )

    client = get_provider_client("vpc_client")
    req = vpc_models.DescribeSecurityGroupsRequest()
    req.Offset = 0
    req.Limit = 100
    resp = client.DescribeSecurityGroups(req)

    ret = {}
    for sg in resp.SecurityGroupSet:
        ret[sg.SecurityGroupId] = {
            "SecurityGroupName": sg.SecurityGroupName,
            "SecurityGroupDesc": sg.SecurityGroupDesc,
            "ProjectId": sg.ProjectId,
            "IsDefault": sg.IsDefault,
            "CreatedTime": sg.CreatedTime,
        }

    return ret


def list_custom_images(call=None):
    """
    Return all Tencent Cloud images in current region

    CLI Example:

    .. code-block:: bash

        salt-cloud -f list_custom_images my-tencentcloud-config
    """
    if call == "action":
        raise SaltCloudSystemExit(
            "The list_custom_images function must be called with -f or --function."
        )

    return _get_images(["PRIVATE_IMAGE", "IMPORT_IMAGE"])


def list_availability_zones(call=None):
    """
    Return all Tencent Cloud availability zones in current region

    CLI Example:

    .. code-block:: bash

        salt-cloud -f list_availability_zones my-tencentcloud-config
    """
    if call == "action":
        raise SaltCloudSystemExit(
            "The list_availability_zones function must be called with -f or --function."
        )

    client = get_provider_client("cvm_client")
    req = cvm_models.DescribeZonesRequest()
    resp = client.DescribeZones(req)

    ret = {}
    for zone in resp.ZoneSet:
        if zone.ZoneState != "AVAILABLE":
            continue
        ret[zone.Zone] = (zone.ZoneName,)

    return ret


def list_nodes(call=None):
    """
    Return a list of instances that are on the provider

    CLI Examples:

    .. code-block:: bash

        salt-cloud -Q
    """
    if call == "action":
        raise SaltCloudSystemExit(
            "The list_nodes function must be called with -f or --function."
        )

    ret = {}
    nodes = _get_nodes()
    for instance in nodes:
        ret[instance.InstanceId] = {
            "InstanceId": instance.InstanceId,
            "InstanceName": instance.InstanceName,
            "InstanceType": instance.InstanceType,
            "ImageId": instance.ImageId,
            "PublicIpAddresses": instance.PublicIpAddresses,
            "PrivateIpAddresses": instance.PrivateIpAddresses,
            "InstanceState": instance.InstanceState,
        }

    return ret


def list_nodes_full(call=None):
    """
    Return a list of instances that are on the provider, with full details

    CLI Examples:

    .. code-block:: bash

        salt-cloud -F
    """
    if call == "action":
        raise SaltCloudSystemExit(
            "The list_nodes_full function must be called with -f or --function."
        )

    ret = {}
    nodes = _get_nodes()
    for instance in nodes:
        instanceAttribute = vars(instance)
        ret[instance.InstanceName] = instanceAttribute
        for k in [
            "DataDisks",
            "InternetAccessible",
            "LoginSettings",
            "Placement",
            "SystemDisk",
            "Tags",
            "VirtualPrivateCloud",
        ]:
            ret[instance.InstanceName][k] = str(instanceAttribute[k])

    provider = _get_active_provider_name() or "tencentcloud"
    if ":" in provider:
        comps = provider.split(":")
        provider = comps[0]

    __opts__["update_cachedir"] = True
    __utils__["cloud.cache_node_list"](ret, provider, __opts__)

    return ret


def list_nodes_select(call=None):
    """
    Return a list of instances that are on the provider, with select fields

    CLI Examples:

    .. code-block:: bash

        salt-cloud -S
    """
    return salt.utils.cloud.list_nodes_select(
        list_nodes_full("function"),
        __opts__["query.selection"],
        call,
    )


def list_nodes_min(call=None):
    """
    Return a list of instances that are on the provider, Only names, and their state, is returned.

    CLI Examples:

    .. code-block:: bash

        salt-cloud -f list_nodes_min my-tencentcloud-config
    """
    if call == "action":
        raise SaltCloudSystemExit(
            "The list_nodes_min function must be called with -f or --function."
        )

    ret = {}
    nodes = _get_nodes()
    for instance in nodes:
        ret[instance.InstanceName] = {
            "InstanceId": instance.InstanceId,
            "InstanceState": instance.InstanceState,
        }

    return ret


def create(vm_):
    """
    Create a single Tencent Cloud instance from a data dict.

    Tencent Cloud profiles require a ``provider``, ``availability_zone``, ``image`` and ``size``.
    Set up profile at ``/etc/salt/cloud.profiles`` or ``/etc/salt/cloud.profiles.d/*.conf``:

    .. code-block:: yaml

        tencentcloud-guangzhou-s1sm1:
            provider: my-tencentcloud-config
            availability_zone: ap-guangzhou-3
            image: img-31tjrtph
            size: S1.SMALL1
            allocate_public_ip: True
            internet_max_bandwidth_out: 1
            password: '153e41ec96140152'
            securitygroups:
                - sg-5e90804b

    CLI Examples:

    .. code-block:: bash

        salt-cloud -p tencentcloud-guangzhou-s1 myinstance
    """
    try:
        # Check for required profile parameters before sending any API calls.
        if (
            vm_["profile"]
            and config.is_profile_configured(
                __opts__,
                _get_active_provider_name() or "tencentcloud",
                vm_["profile"],
                vm_=vm_,
            )
            is False
        ):
            return False
    except AttributeError:
        pass

    __utils__["cloud.fire_event"](
        "event",
        "starting create",
        "salt/cloud/{}/creating".format(vm_["name"]),
        args=__utils__["cloud.filter_event"](
            "creating", vm_, ["name", "profile", "provider", "driver"]
        ),
        sock_dir=__opts__["sock_dir"],
        transport=__opts__["transport"],
    )

    log.debug("Try creating instance: %s", pprint.pformat(vm_))

    # Init cvm client
    client = get_provider_client("cvm_client")
    req = cvm_models.RunInstancesRequest()
    req.InstanceName = vm_["name"]

    # Required parameters
    req.InstanceType = __get_size(vm_)
    req.ImageId = __get_image(vm_)

    zone = __get_availability_zone(vm_)
    projectId = vm_.get("project_id", 0)
    req.Placement = {"Zone": zone, "ProjectId": projectId}

    # Optional parameters

    req.SecurityGroupIds = __get_securitygroups(vm_)
    req.HostName = vm_.get("hostname", vm_["name"])

    req.InstanceChargeType = vm_.get("instance_charge_type", "POSTPAID_BY_HOUR")
    if req.InstanceChargeType == "PREPAID":
        period = vm_.get("instance_charge_type_prepaid_period", 1)
        renewFlag = vm_.get(
            "instance_charge_type_prepaid_renew_flag", "NOTIFY_AND_MANUAL_RENEW"
        )
        req.InstanceChargePrepaid = {"Period": period, "RenewFlag": renewFlag}

    allocate_public_ip = vm_.get("allocate_public_ip", False)
    internet_max_bandwidth_out = vm_.get("internet_max_bandwidth_out", 0)
    if allocate_public_ip and internet_max_bandwidth_out > 0:
        req.InternetAccessible = {
            "PublicIpAssigned": allocate_public_ip,
            "InternetMaxBandwidthOut": internet_max_bandwidth_out,
        }
        internet_charge_type = vm_.get("internet_charge_type", "")
        if internet_charge_type != "":
            req.InternetAccessible["InternetChargeType"] = internet_charge_type

    req.LoginSettings = {}
    req.VirtualPrivateCloud = {}
    req.SystemDisk = {}

    keyId = vm_.get("key_name", "")
    if keyId:
        req.LoginSettings["KeyIds"] = [keyId]

    password = vm_.get("password", "")
    if password:
        req.LoginSettings["Password"] = password

    private_ip = vm_.get("private_ip", "")
    if private_ip:
        req.VirtualPrivateCloud["PrivateIpAddresses"] = private_ip

    vpc_id = vm_.get("vpc_id", "")
    if vpc_id:
        req.VirtualPrivateCloud["VpcId"] = vpc_id

    subnetId = vm_.get("subnet_id", "")
    if subnetId:
        req.VirtualPrivateCloud["SubnetId"] = subnetId

    system_disk_size = vm_.get("system_disk_size", 0)
    if system_disk_size:
        req.SystemDisk["DiskSize"] = system_disk_size

    system_disk_type = vm_.get("system_disk_type", "")
    if system_disk_type:
        req.SystemDisk["DiskType"] = system_disk_type

    __utils__["cloud.fire_event"](
        "event",
        "requesting instance",
        "salt/cloud/{}/requesting".format(vm_["name"]),
        args=__utils__["cloud.filter_event"]("requesting", vm_, list(vm_)),
        sock_dir=__opts__["sock_dir"],
        transport=__opts__["transport"],
    )

    try:
        resp = client.RunInstances(req)
        if not resp.InstanceIdSet:
            raise SaltCloudSystemExit("Unexpected error, no instance created")
    except Exception as exc:  # pylint: disable=broad-except
        log.error(
            "Error creating %s on tencentcloud\n\n"
            "The following exception was thrown when trying to "
            "run the initial deployment: %s",
            vm_["name"],
            str(exc),
            # Show the traceback if the debug logging level is enabled
            exc_info_on_loglevel=logging.DEBUG,
        )
        return False

    time.sleep(5)

    def __query_node_data(vm_name):
        data = show_instance(vm_name, call="action")
        if not data:
            return False
        if data["InstanceState"] != "RUNNING":
            return False
        if data["PrivateIpAddresses"]:
            return data

    try:
        data = salt.utils.cloud.wait_for_ip(
            __query_node_data,
            update_args=(vm_["name"],),
            timeout=config.get_cloud_config_value(
                "wait_for_ip_timeout", vm_, __opts__, default=10 * 60
            ),
            interval=config.get_cloud_config_value(
                "wait_for_ip_interval", vm_, __opts__, default=10
            ),
        )
    except (SaltCloudExecutionTimeout, SaltCloudExecutionFailure) as exc:
        try:
            destroy(vm_["name"])
        except SaltCloudSystemExit:
            pass
        finally:
            raise SaltCloudSystemExit(str(exc))

    if data["PublicIpAddresses"]:
        ssh_ip = data["PublicIpAddresses"][0]
    elif data["PrivateIpAddresses"]:
        ssh_ip = data["PrivateIpAddresses"][0]
    else:
        log.error("No available ip: cant connect to salt")
        return False

    log.debug("Instance %s: %s is now running", vm_["name"], ssh_ip)
    vm_["ssh_host"] = ssh_ip

    # The instance is booted and accessible, let's Salt it!
    ret = __utils__["cloud.bootstrap"](vm_, __opts__)
    ret.update(data)

    log.debug("'%s' instance creation details:\n%s", vm_["name"], pprint.pformat(data))

    __utils__["cloud.fire_event"](
        "event",
        "created instance",
        "salt/cloud/{}/created".format(vm_["name"]),
        args=__utils__["cloud.filter_event"](
            "created", vm_, ["name", "profile", "provider", "driver"]
        ),
        sock_dir=__opts__["sock_dir"],
        transport=__opts__["transport"],
    )

    return ret


def start(name, call=None):
    """
    Start a Tencent Cloud instance
    Notice: the instance state must be stopped

    CLI Examples:

    .. code-block:: bash

        salt-cloud -a start myinstance
    """
    if call != "action":
        raise SaltCloudSystemExit("The stop action must be called with -a or --action.")

    node = _get_node(name)

    client = get_provider_client("cvm_client")
    req = cvm_models.StartInstancesRequest()
    req.InstanceIds = [node.InstanceId]
    resp = client.StartInstances(req)

    return resp


def stop(name, force=False, call=None):
    """
    Stop a Tencent Cloud running instance
    Note: use `force=True` to make force stop

    CLI Examples:

    .. code-block:: bash

        salt-cloud -a stop myinstance
        salt-cloud -a stop myinstance force=True
    """
    if call != "action":
        raise SaltCloudSystemExit("The stop action must be called with -a or --action.")

    node = _get_node(name)

    client = get_provider_client("cvm_client")
    req = cvm_models.StopInstancesRequest()
    req.InstanceIds = [node.InstanceId]
    if force:
        req.ForceStop = "TRUE"
    resp = client.StopInstances(req)

    return resp


def reboot(name, call=None):
    """
    Reboot a Tencent Cloud instance

    CLI Examples:

    .. code-block:: bash

        salt-cloud -a reboot myinstance
    """
    if call != "action":
        raise SaltCloudSystemExit("The stop action must be called with -a or --action.")

    node = _get_node(name)

    client = get_provider_client("cvm_client")
    req = cvm_models.RebootInstancesRequest()
    req.InstanceIds = [node.InstanceId]
    resp = client.RebootInstances(req)

    return resp


def destroy(name, call=None):
    """
    Destroy a Tencent Cloud instance

    CLI Example:

    .. code-block:: bash

        salt-cloud -a destroy myinstance
        salt-cloud -d myinstance
    """
    if call == "function":
        raise SaltCloudSystemExit(
            "The destroy action must be called with -d, --destroy, -a or --action."
        )

    __utils__["cloud.fire_event"](
        "event",
        "destroying instance",
        "salt/cloud/{}/destroying".format(name),
        args={"name": name},
        sock_dir=__opts__["sock_dir"],
        transport=__opts__["transport"],
    )

    node = _get_node(name)

    client = get_provider_client("cvm_client")
    req = cvm_models.TerminateInstancesRequest()
    req.InstanceIds = [node.InstanceId]
    resp = client.TerminateInstances(req)

    __utils__["cloud.fire_event"](
        "event",
        "destroyed instance",
        "salt/cloud/{}/destroyed".format(name),
        args={"name": name},
        sock_dir=__opts__["sock_dir"],
        transport=__opts__["transport"],
    )

    return resp


def script(vm_):
    """
    Return the script deployment object
    """
    return salt.utils.cloud.os_script(
        config.get_cloud_config_value("script", vm_, __opts__),
        vm_,
        __opts__,
        salt.utils.cloud.salt_config_to_yaml(
            salt.utils.cloud.minion_config(__opts__, vm_)
        ),
    )


def show_image(kwargs, call=None):
    """
    Show the details of Tencent Cloud image

    CLI Examples:

    .. code-block:: bash

        salt-cloud -f show_image tencentcloud image=img-31tjrtph
    """
    if call != "function":
        raise SaltCloudSystemExit(
            "The show_image function must be called with -f or --function"
        )

    if not isinstance(kwargs, dict):
        kwargs = {}

    if "image" not in kwargs:
        raise SaltCloudSystemExit("No image specified.")

    image = kwargs["image"]

    client = get_provider_client("cvm_client")
    req = cvm_models.DescribeImagesRequest()
    req.ImageIds = [image]
    resp = client.DescribeImages(req)

    if not resp.ImageSet:
        raise SaltCloudNotFound(
            "The specified image '{}' could not be found.".format(image)
        )

    ret = {}
    for image in resp.ImageSet:
        ret[image.ImageId] = {
            "ImageName": image.ImageName,
            "ImageType": image.ImageType,
            "ImageSource": image.ImageSource,
            "Platform": image.Platform,
            "Architecture": image.Architecture,
            "ImageSize": "{}GB".format(image.ImageSize),
            "ImageState": image.ImageState,
        }

    return ret


def show_instance(name, call=None):
    """
    Show the details of Tencent Cloud instance

    CLI Examples:

    .. code-block:: bash

        salt-cloud -a show_instance myinstance
    """
    if call != "action":
        raise SaltCloudSystemExit(
            "The show_instance action must be called with -a or --action."
        )

    node = _get_node(name)
    ret = vars(node)
    for k in [
        "DataDisks",
        "InternetAccessible",
        "LoginSettings",
        "Placement",
        "SystemDisk",
        "Tags",
        "VirtualPrivateCloud",
    ]:
        ret[k] = str(ret[k])

    return ret


def show_disk(name, call=None):
    """
    Show the disk details of Tencent Cloud instance

    CLI Examples:

    .. code-block:: bash

        salt-cloud -a show_disk myinstance
    """
    if call != "action":
        raise SaltCloudSystemExit(
            "The show_disks action must be called with -a or --action."
        )

    node = _get_node(name)

    ret = {}
    ret[node.SystemDisk.DiskId] = {
        "SystemDisk": True,
        "DiskSize": node.SystemDisk.DiskSize,
        "DiskType": node.SystemDisk.DiskType,
        "DeleteWithInstance": True,
        "SnapshotId": "",
    }

    if node.DataDisks:
        for disk in node.DataDisks:
            ret[disk.DiskId] = {
                "SystemDisk": False,
                "DiskSize": disk.DiskSize,
                "DiskType": disk.DiskType,
                "DeleteWithInstance": disk.DeleteWithInstance,
                "SnapshotId": disk.SnapshotId,
            }

    return ret


def _get_node(name):
    """
    Return Tencent Cloud instance detail by name
    """
    attempts = 5
    while attempts >= 0:
        try:
            client = get_provider_client("cvm_client")
            req = cvm_models.DescribeInstancesRequest()
            req.Filters = [{"Name": "instance-name", "Values": [name]}]
            resp = client.DescribeInstances(req)
            return resp.InstanceSet[0]
        except Exception as ex:  # pylint: disable=broad-except
            attempts -= 1
            log.debug(
                "Failed to get data for node '%s': %s. Remaining attempts: %d",
                name,
                ex,
                attempts,
            )
            time.sleep(0.5)

    raise SaltCloudNotFound("Failed to get instance info {}".format(name))


def _get_nodes():
    """
    Return all list of Tencent Cloud instances
    """
    ret = []
    offset = 0
    limit = 100

    while True:
        client = get_provider_client("cvm_client")
        req = cvm_models.DescribeInstancesRequest()
        req.Offset = offset
        req.Limit = limit
        resp = client.DescribeInstances(req)
        for v in resp.InstanceSet:
            ret.append(v)
        if len(ret) >= resp.TotalCount:
            break
        offset += len(resp.InstanceSet)

    return ret


def _get_images(image_type):
    """
    Return all list of Tencent Cloud images
    """
    client = get_provider_client("cvm_client")
    req = cvm_models.DescribeImagesRequest()
    req.Filters = [{"Name": "image-type", "Values": image_type}]
    req.Offset = 0
    req.Limit = 100
    resp = client.DescribeImages(req)

    ret = {}
    for image in resp.ImageSet:
        if image.ImageState != "NORMAL":
            continue
        ret[image.ImageId] = {
            "ImageName": image.ImageName,
            "ImageType": image.ImageType,
            "ImageSource": image.ImageSource,
            "Platform": image.Platform,
            "Architecture": image.Architecture,
            "ImageSize": "{}GB".format(image.ImageSize),
        }

    return ret


def __get_image(vm_):
    vm_image = str(
        config.get_cloud_config_value("image", vm_, __opts__, search_global=False)
    )

    if not vm_image:
        raise SaltCloudNotFound("No image specified.")

    images = avail_images()
    if vm_image in images:
        return vm_image

    raise SaltCloudNotFound(
        "The specified image '{}' could not be found.".format(vm_image)
    )


def __get_size(vm_):
    vm_size = str(
        config.get_cloud_config_value("size", vm_, __opts__, search_global=False)
    )

    if not vm_size:
        raise SaltCloudNotFound("No size specified.")

    sizes = avail_sizes()
    if vm_size in sizes:
        return vm_size

    raise SaltCloudNotFound(
        "The specified size '{}' could not be found.".format(vm_size)
    )


def __get_securitygroups(vm_):
    vm_securitygroups = config.get_cloud_config_value(
        "securitygroups", vm_, __opts__, search_global=False
    )

    if not vm_securitygroups:
        return []

    securitygroups = list_securitygroups()
    for idx, value in enumerate(vm_securitygroups):
        vm_securitygroups[idx] = str(value)
        if vm_securitygroups[idx] not in securitygroups:
            raise SaltCloudNotFound(
                "The specified securitygroups '{}' could not be found.".format(
                    vm_securitygroups[idx]
                )
            )

    return vm_securitygroups


def __get_availability_zone(vm_):
    vm_availability_zone = str(
        config.get_cloud_config_value(
            "availability_zone", vm_, __opts__, search_global=False
        )
    )

    if not vm_availability_zone:
        raise SaltCloudNotFound("No availability_zone specified.")

    availability_zones = list_availability_zones()
    if vm_availability_zone in availability_zones:
        return vm_availability_zone

    raise SaltCloudNotFound(
        "The specified availability_zone '{}' could not be found.".format(
            vm_availability_zone
        )
    )


def __get_location(vm_):
    """
    Return the Tencent Cloud region to use, in this order:
        - CLI parameter
        - VM parameter
        - Cloud profile setting
    """
    vm_location = str(
        __opts__.get(
            "location",
            config.get_cloud_config_value(
                "location",
                vm_ or get_configured_provider(),
                __opts__,
                default=DEFAULT_REGION,
                search_global=False,
            ),
        )
    )

    if not vm_location:
        raise SaltCloudNotFound("No location specified.")

    return vm_location
