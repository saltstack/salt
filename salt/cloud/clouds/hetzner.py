"""
Hetzner Cloud Module
====================

The Hetzner cloud module is used to control access to the hetzner cloud.
https://docs.hetzner.cloud/

:depends: hcloud >= 1.10

Use of this module requires the ``key`` parameter to be set.

.. code-block:: yaml

    my-hetzner-cloud-config:
      key: <your api key>
      driver: hetzner

"""
# pylint: disable=invalid-name,function-redefined


import logging
import time

import salt.config as config
from salt.exceptions import SaltCloudException, SaltCloudSystemExit

# hcloud module will be needed
# pylint: disable=import-error
try:
    import hcloud

    HAS_HCLOUD = True
except ImportError:
    HAS_HCLOUD = False


# Get logging started
log = logging.getLogger(__name__)

__virtualname__ = "hetzner"


def __virtual__():
    """
    Check for hetzner configurations
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
        __opts__,
        _get_active_provider_name() or __virtualname__,
        ("key",),
    )


def get_dependencies():
    """
    Warn if dependencies aren't met.
    """
    return config.check_driver_dependencies(
        _get_active_provider_name() or __virtualname__,
        {"hcloud": HAS_HCLOUD},
    )


def _object_to_dict(obj, attrs):
    return {attr: getattr(obj, attr) for attr in attrs}


def _datacenter_to_dict(datacenter):
    return {
        "name": datacenter.name,
        "location": datacenter.location.name,
    }


def _public_network_to_dict(net):
    return {
        "ipv4": getattr(net.ipv4, "ip", None),
        "ipv6": getattr(net.ipv6, "ip", None),
    }


def _private_network_to_dict(net):
    return {
        "ip": getattr(net, "ip", None),
    }


def _connect_client():
    provider = get_configured_provider()
    return hcloud.Client(provider["key"])


def avail_locations(call=None):
    if call == "action":
        raise SaltCloudSystemExit(
            "The list_locations function must be called with -f or --function"
        )

    client = _connect_client()
    locations = {}
    for loc in client.locations.get_all():
        locations[loc.name] = _object_to_dict(loc, loc.model.__slots__)
    return locations


def avail_images(call=None):
    if call == "action":
        raise SaltCloudSystemExit(
            "The avail_images function must be called with -f or --function"
        )

    client = _connect_client()
    images = {}
    for image in client.images.get_all():
        images[image.name] = _object_to_dict(image, image.model.__slots__)
    return images


def avail_sizes(call=None):
    if call == "action":
        raise SaltCloudSystemExit(
            "The avail_sizes function must be called with -f or --function"
        )

    client = _connect_client()
    sizes = {}
    for size in client.server_types.get_all():
        sizes[size.name] = _object_to_dict(size, size.model.__slots__)
    return sizes


def list_ssh_keys(call=None):
    if call == "action":
        raise SaltCloudSystemExit(
            "The list_ssh_keys function must be called with -f or --function"
        )

    client = _connect_client()
    ssh_keys = {}
    for key in client.ssh_keys.get_all():
        ssh_keys[key.name] = _object_to_dict(key, key.model.__slots__)
    return ssh_keys


def list_nodes_full(call=None):
    if call == "action":
        raise SaltCloudSystemExit(
            "The list_nodes_full function must be called with -f or --function"
        )

    client = _connect_client()
    nodes = {}
    for node in client.servers.get_all():
        nodes[node.name] = {
            "id": node.id,
            "name": node.name,
            "image": node.image.name,
            "size": node.server_type.name,
            "state": node.status,
            "public_ips": _public_network_to_dict(node.public_net),
            "private_ips": list(map(_private_network_to_dict, node.private_net)),
            "labels": node.labels,
            "created": str(node.created),
            "datacenter": _datacenter_to_dict(node.datacenter),
            "volumes": [vol.name for vol in node.volumes],
        }
    return nodes


def list_nodes(call=None):
    if call == "action":
        raise SaltCloudSystemExit(
            "The list_nodes function must be called with -f or --function"
        )

    ret = {}

    nodes = list_nodes_full()
    for node in nodes:
        ret[node] = {"name": node}
        for prop in ("id", "image", "size", "state", "private_ips", "public_ips"):
            ret[node][prop] = nodes[node].get(prop)
    return ret


def wait_until(name, state, timeout=300):
    """
    Wait until a specific state has been reached on  a node
    """
    start_time = time.time()
    node = show_instance(name, call="function")
    while True:
        if node["state"] == state:
            return True
        time.sleep(1)
        if time.time() - start_time > timeout:
            return False
        node = show_instance(name, call="function")


def show_instance(name, call=None):
    if call == "action":
        raise SaltCloudSystemExit(
            "The show_instance function must be called with -f or --function"
        )

    try:
        node = list_nodes_full("function")[name]
    except KeyError:
        log.debug("Failed to get data for node '%s'", name)
        node = {}

    __utils__["cloud.cache_node"](
        node,
        _get_active_provider_name() or __virtualname__,
        __opts__,
    )

    return node


def create(vm_):
    """
    Create a single VM from a data dict
    """
    try:
        # Check for required profile parameters before sending any API calls.
        if (
            vm_.get("profile")
            and config.is_profile_configured(
                __opts__,
                _get_active_provider_name() or __virtualname__,
                vm_["profile"],
                vm_=vm_,
            )
            is False
        ):
            return False
    except AttributeError:
        pass

    client = _connect_client()

    name = vm_.get("name")
    if not name:
        raise SaltCloudException("Missing server name")

    # Get the required configuration
    server_type = client.server_types.get_by_name(vm_.get("size"))
    if server_type is None:
        raise SaltCloudException("The server size is not supported")

    image = client.images.get_by_name(vm_.get("image"))
    if image is None:
        raise SaltCloudException("The server image is not supported")

    __utils__["cloud.fire_event"](
        "event",
        "starting create",
        "salt/cloud/{}/creating".format(vm_["name"]),
        args=__utils__["cloud.filter_event"](
            "creating",
            vm_,
            ["name", "profile", "provider", "driver"],
        ),
        sock_dir=__opts__["sock_dir"],
        transport=__opts__["transport"],
    )

    # Get the ssh_keys
    ssh_keys = vm_.get("ssh_keys", None)
    if ssh_keys:
        names, ssh_keys = ssh_keys[:], []
        for n in names:
            ssh_key = client.ssh_keys.get_by_name(n)
            if ssh_key is None:
                log.error("Invalid ssh key %s.", n)
            else:
                ssh_keys.append(ssh_key)

    # Get the location
    location = vm_.get("location", None)
    if location:
        location = client.locations.get_by_name(location)

        if location is None:
            raise SaltCloudException("The server location is not supported")

    # Get the datacenter
    datacenter = vm_.get("datacenter", None)
    if datacenter:
        datacenter = client.datacenters.get_by_name(datacenter)

        if datacenter is None:
            raise SaltCloudException("The server datacenter is not supported")

    # Get the volumes
    volumes = vm_.get("volumes", None)
    if volumes:
        volumes = [vol for vol in client.volumes.get_all() if vol in volumes]

    # Get the networks
    networks = vm_.get("networks", None)
    if networks:
        networks = [vol for vol in client.networks.get_all() if vol in networks]

    # Create the machine
    response = client.servers.create(
        name=name,
        server_type=server_type,
        image=image,
        ssh_keys=ssh_keys,
        volumes=volumes,
        networks=networks,
        location=location,
        user_data=vm_.get("user_data", None),
        labels=vm_.get("labels", None),
        datacenter=datacenter,
        automount=vm_.get("automount", None),
    )

    # Bootstrap if ssh keys are configured
    server = response.server
    vm_.update(
        {
            "ssh_host": server.public_net.ipv4.ip or server.public_net.ipv6.ip,
            "ssh_password": response.root_password,
            "key_filename": config.get_cloud_config_value(
                "private_key", vm_, __opts__, search_global=False, default=None
            ),
        }
    )

    ret = __utils__["cloud.bootstrap"](vm_, __opts__)

    log.info("Created Cloud VM '%s'", vm_["name"])
    ret["created"] = True

    __utils__["cloud.fire_event"](
        "event",
        "created instance",
        "salt/cloud/{}/created".format(vm_["name"]),
        args=__utils__["cloud.filter_event"](
            "created",
            vm_,
            ["name", "profile", "provider", "driver"],
        ),
        sock_dir=__opts__["sock_dir"],
        transport=__opts__["transport"],
    )

    return ret


def start(name, call=None, wait=True):
    """
    Start a node.

    CLI Example:

    .. code-block:: bash

        salt-cloud -a start mymachine
    """
    if call != "action":
        raise SaltCloudSystemExit(
            "The start action must be called with -a or --action."
        )

    client = _connect_client()
    server = client.servers.get_by_name(name)
    if server is None:
        return "Instance {} doesn't exist.".format(name)

    server.power_on()
    if wait and not wait_until(name, "running"):
        return "Instance {} doesn't start.".format(name)

    __utils__["cloud.fire_event"](
        "event",
        "started instance",
        "salt/cloud/{}/started".format(name),
        args={"name": name},
        sock_dir=__opts__["sock_dir"],
        transport=__opts__["transport"],
    )

    return {"Started": "{} was started.".format(name)}


def stop(name, call=None, wait=True):
    """
    Stop a node.

    CLI Example:

    .. code-block:: bash

        salt-cloud -a stop mymachine
    """
    if call != "action":
        raise SaltCloudSystemExit("The stop action must be called with -a or --action.")

    client = _connect_client()
    server = client.servers.get_by_name(name)
    if server is None:
        return "Instance {} doesn't exist.".format(name)

    server.power_off()
    if wait and not wait_until(name, "off"):
        return "Instance {} doesn't stop.".format(name)

    __utils__["cloud.fire_event"](
        "event",
        "stopped instance",
        "salt/cloud/{}/stopped".format(name),
        args={"name": name},
        sock_dir=__opts__["sock_dir"],
        transport=__opts__["transport"],
    )

    return {"Stopped": "{} was stopped.".format(name)}


def reboot(name, call=None, wait=True):
    """
    Reboot a node.

    CLI Example:

    .. code-block:: bash

        salt-cloud -a reboot mymachine
    """
    if call != "action":
        raise SaltCloudSystemExit(
            "The reboot action must be called with -a or --action."
        )

    client = _connect_client()
    server = client.servers.get_by_name(name)
    if server is None:
        return "Instance {} doesn't exist.".format(name)

    server.reboot()

    if wait and not wait_until(name, "running"):
        return "Instance {} doesn't start.".format(name)

    return {"Rebooted": "{} was rebooted.".format(name)}


def destroy(name, call=None):
    """
    Destroy a node.

    CLI Example:

    .. code-block:: bash

        salt-cloud --destroy mymachine
    """
    if call == "function":
        raise SaltCloudSystemExit(
            "The destroy action must be called with -d, --destroy, -a or --action."
        )

    client = _connect_client()
    server = client.servers.get_by_name(name)
    if server is None:
        return "Instance {} doesn't exist.".format(name)

    __utils__["cloud.fire_event"](
        "event",
        "destroying instance",
        "salt/cloud/{}/destroying".format(name),
        args={"name": name},
        sock_dir=__opts__["sock_dir"],
        transport=__opts__["transport"],
    )

    node = show_instance(name, call="function")
    if node["state"] == "running":
        stop(name, call="action", wait=False)
        if not wait_until(name, "off"):
            return {"Error": "Unable to destroy {}, command timed out".format(name)}

    server.delete()

    __utils__["cloud.fire_event"](
        "event",
        "destroyed instance",
        "salt/cloud/{}/destroyed".format(name),
        args={"name": name},
        sock_dir=__opts__["sock_dir"],
        transport=__opts__["transport"],
    )

    if __opts__.get("update_cachedir", False) is True:
        __utils__["cloud.delete_minion_cachedir"](
            name,
            _get_active_provider_name().split(":")[0],
            __opts__,
        )

    return {"Destroyed": "{} was destroyed.".format(name)}


def resize(name, kwargs, call=None):
    """
    Resize a node.

    CLI Example:

    .. code-block:: bash

        salt-cloud -a resize mymachine size=...
    """
    if call != "action":
        raise SaltCloudSystemExit(
            "The resize action must be called with -a or --action."
        )

    client = _connect_client()
    server = client.servers.get_by_name(name)
    if server is None:
        return "Instance {} doesn't exist.".format(name)

    # Check the configuration
    size = kwargs.get("size", None)
    if size is None:
        raise SaltCloudException("The new size is required")

    server_type = client.server_types.get_by_name(size)
    if server_type is None:
        raise SaltCloudException("The server size is not supported")

    __utils__["cloud.fire_event"](
        "event",
        "resizing instance",
        "salt/cloud/{}/resizing".format(name),
        args={"name": name},
        sock_dir=__opts__["sock_dir"],
        transport=__opts__["transport"],
    )

    node = show_instance(name, call="function")
    if node["state"] == "running":
        stop(name, call="action", wait=False)
        if not wait_until(name, "off"):
            return {"Error": "Unable to resize {}, command timed out".format(name)}

    server.change_type(server_type, kwargs.get("upgrade_disk", False))

    __utils__["cloud.fire_event"](
        "event",
        "resizing instance",
        "salt/cloud/{}/resized".format(name),
        args={"name": name},
        sock_dir=__opts__["sock_dir"],
        transport=__opts__["transport"],
    )

    return {"Resized": "{} was resized.".format(name)}
