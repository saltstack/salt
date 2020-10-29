# -*- coding: utf-8 -*-
"""
"Hetzner Cloud (https://hetzner.cloud/)"-driver using the hcloud Python lib
(https://hcloud-python.readthedocs.io/en/latest/index.html).
====================================================================================

This driver is used to control VPS in a specific ``api_key``-defined project in the hetzner cloud.

To use this driver you need to set up at least one provider in ``/etc/salt/cloud.providers`` or e.g.
``/etc/salt/cloud.providers.d/hcloud.conf`` and one profile in ``/etc/salt/cloud.profiles`` or e.g.
``/etc/salt/cloud.profiles.d/hcloud.conf``.

The provider needs to have the attributes ``api_key``, ``ssh_keyfile`` and ``ssh_keyfile_public``. Newly created vps can
only be bootstrapped if the ``ssh_keyfile_public`` is the public key of the servers private key provided with
``ssh_keyfile``. ``api_key`` can be generated in the hetzner cloud webinterface and is project-wide valid.

provider-example:

.. code-block:: yaml

    hcloud-config:
        driver: hcloud
        ssh_keyfile: '/root/.ssh/id_rsa'
        ssh_keyfile_public: '/root/.ssh/id_rsa.pub'
        api_key: '$GENERATED_API_KEY'
        minion:
            master: 'salt-master.example.org'

profile-example:

.. code-block:: yaml

    hcloud-test:
        provider: hcloud-config
        size: cx11
        image: debian-10

"""
from __future__ import absolute_import, print_function, unicode_literals

import functools
import logging
import time

import hcloud
import salt.config as config
import salt.utils.cloud
import salt.utils.files

try:
    # pylint: disable=no-name-in-module
    from hcloud.hcloud import APIException
    from hcloud.images.domain import Image
    from hcloud.networks.domain import NetworkRoute, NetworkSubnet
    from hcloud.server_types.domain import ServerType
    from salt.exceptions import SaltCloudException

    # pylint: enable=no-name-in-module

    HAS_HCLOUD = True
except ImportError:
    HAS_HCLOUD = False

log = logging.getLogger(__name__)

__virtualname__ = "hcloud"

hcloud_client = None


def hcloud_api(func):
    """
    Decorator for all functions which uses the hcloud-api. It refreshes the token if it was changed in the provider
    and wraps the general error handling.
    """

    @functools.wraps(func.__name__)
    def wrapped_hcloud_call(*args, **kwargs):
        global hcloud_client

        vm_ = get_configured_provider()
        api_key = config.get_cloud_config_value(
            "api_key", vm_, __opts__, search_global=False
        )

        if hcloud_client is None:
            hcloud_client = hcloud.Client(token=api_key)

        try:
            return func(*args, **kwargs)
        except APIException as e:
            log.error(e)
            return

    return wrapped_hcloud_call


def saltcloud_function(func):
    """
    Decorator for all salt-cloud functions
    """

    @functools.wraps(func.__name__)
    def wrapped_saltcloud_function(*args, **kwargs):
        if kwargs.get("call") == "action":
            raise SaltCloudException(
                "{0} must be called with -f or --function".format(func.__name__)
            )

        return func(*args, **kwargs)

    return wrapped_saltcloud_function


def saltcloud_action(func):
    """
    Decorator for all salt-cloud functions
    """

    def wrapped_saltcloud_action(*args, **kwargs):
        if kwargs.get("call") == "function":
            raise SaltCloudException(
                "{0} must be called with -a or --action".format(func.__name__)
            )

        return func(*args, **kwargs)

    return wrapped_saltcloud_action


def __virtual__():
    if get_configured_provider() is False:
        return False

    if get_dependencies() is False:
        return False

    return __virtualname__


def get_dependencies():
    """
    Warn if driver dependencies not met
    """
    return config.check_driver_dependencies(__virtualname__, {"hcloud": HAS_HCLOUD})


def get_configured_provider():
    """
    Return the first configured instance.
    """
    return config.is_provider_configured(
        __opts__,
        __active_provider_name__ or __virtualname__,
        ("api_key", "ssh_keyfile_public",),
    )


@hcloud_api
def create(vm_):
    """
    Create a single hetzner cloud instance
    """
    name = vm_["name"]
    try:
        # Check for required profile parameters before sending any API calls.
        if (
            vm_["profile"]
            and config.is_profile_configured(
                __opts__, __active_provider_name__ or "hcloud", vm_["profile"], vm_=vm_
            )
            is False
        ):
            return False
    except AttributeError:
        pass

    log.info("Sending request to create a new hetzner cloud vm.")
    __utils__["cloud.fire_event"](
        "event",
        "starting create",
        "salt/cloud/{0}/creating".format(name),
        args=__utils__["cloud.filter_event"](
            "creating", vm_, ["name", "profile", "provider", "driver"]
        ),
        sock_dir=__opts__["sock_dir"],
        transport=__opts__["transport"],
    )

    ssh_keyfile_public = config.get_cloud_config_value(
        "ssh_keyfile_public", vm_, __opts__
    )

    try:
        with salt.utils.files.fopen(ssh_keyfile_public) as file:
            local_ssh_public_key = file.read()
    except OSError:
        log.error("Could not read ssh keyfile {0}".format(ssh_keyfile_public))
        return False

    hcloud_ssh_public_key = _hcloud_find_matching_ssh_pub_key(local_ssh_public_key)

    if hcloud_ssh_public_key is None:
        log.error("Couldn't find a matching ssh key in your hcloud project.")
        return False

    created_server_response = hcloud_client.servers.create(
        name,
        server_type=ServerType(name=vm_["size"]),
        image=Image(name=vm_["image"]),
        ssh_keys=[hcloud_ssh_public_key],
    )

    __utils__["cloud.fire_event"](
        "event",
        "requesting instance",
        "salt/cloud/{0}/requesting".format(name),
        args=__utils__["cloud.filter_event"](
            "requesting", vm_, ["name", "profile", "provider", "driver"]
        ),
        sock_dir=__opts__["sock_dir"],
        transport=__opts__["transport"],
    )

    while True:
        server = hcloud_client.servers.get_by_id(created_server_response.server.id)

        if server.status == "running":
            log.info("Server {0} is up running now.".format(server.name))
            break
        else:
            log.info(
                "Waiting for server {0} to be running: {1}".format(
                    server.name, server.status
                )
            )
            time.sleep(2)

    vm_["ssh_host"] = server.public_net.ipv4.ip

    __utils__["cloud.fire_event"](
        "event",
        "waiting for ssh",
        "salt/cloud/{0}/waiting_for_ssh".format(name),
        sock_dir=__opts__["sock_dir"],
        args={"ip_address": vm_["ssh_host"]},
        transport=__opts__["transport"],
    )

    # Bootstrap!
    ret = __utils__["cloud.bootstrap"](vm_, __opts__)

    ret.update(_hcloud_format_server(server))

    log.info("Created Cloud VM '{0}'".format(name))

    __utils__["cloud.fire_event"](
        "event",
        "created instance",
        "salt/cloud/{0}/created".format(name),
        args=__utils__["cloud.filter_event"](
            "created", vm_, ["name", "profile", "provider", "driver"]
        ),
        sock_dir=__opts__["sock_dir"],
        transport=__opts__["transport"],
    )

    return ret


@saltcloud_function
@hcloud_api
def avail_locations():
    """
    Return available hcloud locations.
    https://docs.hetzner.cloud/#locations-get-all-locations

    CLI-Example

    .. code-block:: bash

        salt-cloud --list-locations my-hcloud-provider
        salt-cloud -f avail_locations my-hcloud-provider
    """
    return [
        _hcloud_format_location(location)
        for location in hcloud_client.locations.get_all()
    ]


@saltcloud_function
@hcloud_api
def avail_images():
    """
    Return available hcloud images.
    https://docs.hetzner.cloud/#images-get-all-images

    CLI-Example

    .. code-block:: bash

        salt-cloud --list-images my-hcloud-provider
        salt-cloud -f avail_images my-hcloud-provider
    """
    images = hcloud_client.images.get_all()

    formatted_images = {}

    for image in images:
        if image.type == "system":
            identifier = image.name
        else:
            # HCloud backups and snapshots are images without name, so the id is taken as identifier
            identifier = str(image.id)

        if image.status == "available":
            formatted_images[identifier] = _hcloud_format_image(image)

    return formatted_images


@saltcloud_function
@hcloud_api
def avail_sizes():
    """
    Return available hcloud vm sizes
    https://docs.hetzner.cloud/#server-types

    CLI-Example

    .. code-block:: bash

        salt-cloud --list-sizes my-hcloud-provider
        salt-cloud -f avail_sizes my-hlocud-provider
    """
    server_types = hcloud_client.server_types.get_all()

    formatted_server_types = {}

    for server_type in server_types:
        if not server_type.deprecated:
            formatted_server_types[server_type.name] = _hcloud_format_server_type(
                server_type
            )

    return formatted_server_types


@saltcloud_action
@hcloud_api
def destroy(name):
    """
    Destroy a hcloud vm by name.
    https://docs.hetzner.cloud/#servers-delete-a-server

    name
        The name of VM to be be destroyed.

    CLI Example:

    .. code-block:: bash

        salt-cloud -d vm_name
    """
    __utils__["cloud.fire_event"](
        "event",
        "destroying instance",
        "salt/cloud/{0}/destroying".format(name),
        args={"name": name},
        sock_dir=__opts__["sock_dir"],
        transport=__opts__["transport"],
    )

    server = hcloud_client.servers.get_by_name(name)
    delete_action = hcloud_client.servers.delete(server)

    log.info("Action started at {0}".format(delete_action.started.strftime("%c")))

    delete_action_dict = _hcloud_format_action(_hcloud_wait_for_action(delete_action))

    if delete_action_dict["status"] == "success":
        log.info(
            "Executed {0} on {1} at {2} successfully.".format(
                delete_action_dict["command"],
                ", ".join(
                    [
                        "{0} {1}".format(resource["type"], resource["id"])
                        for resource in delete_action_dict["resources"]
                    ]
                ),
                delete_action_dict["finished"],
            )
        )
    else:
        log.error(
            "Execution of {0} on {1} at {2} failed: {3} - {4}".format(
                delete_action_dict["command"],
                ", ".join(
                    [
                        "{0} {1}".format(resource["type"], resource["id"])
                        for resource in delete_action_dict["resources"]
                    ]
                ),
                delete_action_dict["finished"],
                delete_action_dict["error"]["code"],
                delete_action_dict["error"]["message"],
            )
        )

    __utils__["cloud.fire_event"](
        "event",
        "destroyed instance",
        "salt/cloud/{0}/destroyed".format(name),
        args={
            "name": name
            "ip_address": server.public_net.ipv4.ip
        },
        sock_dir=__opts__["sock_dir"],
        transport=__opts__["transport"],
    )

    if __opts__.get("update_cachedir", False) is True:
        __utils__["cloud.delete_minion_cachedir"](
            name, __active_provider_name__.split(":")[0], __opts__
        )

    return delete_action_dict


@saltcloud_function
@hcloud_api
def list_nodes():
    """
    List hcloud vms, keeping only the most important informations.
    https://docs.hetzner.cloud/#servers-get-all-servers

    CLI Example:

    .. code-block:: bash

        salt-cloud -Q
        salt-cloud --query
        salt-cloud -f list_nodes my-hcloud-provider
    """
    return {
        server.name: _hcloud_format_server(server)
        for server in hcloud_client.servers.get_all()
    }


@saltcloud_function
@hcloud_api
def list_nodes_full():
    """
    List full detailed hcloud vms.
    https://docs.hetzner.cloud/#servers-get-all-servers

    CLI Example:

    .. code-block:: bash

        salt-cloud -F
        salt-cloud --full-query
        salt-cloud -f list_nodes_full my-hcloud-provider
    """
    return {
        server.name: _hcloud_format_server(server, full=True)
        for server in hcloud_client.servers.get_all()
    }


@saltcloud_function
@hcloud_api
def list_nodes_select():
    """
    List the VMs that are on the provider, with select fields

    Taken like this from https://docs.saltstack.com/en/latest/topics/cloud/cloud.html#the-list-nodes-select-function
    """
    return salt.utils.cloud.list_nodes_select(
        list_nodes_full(), __opts__["query.selection"], "function",
    )


@saltcloud_action
@hcloud_api
def show_instance(name):
    """
    Return detailed information of a particular vm

    name
        The name of the vm to show

    CLI-Example

    .. code-block:: bash
        salt-cloud -a show_instance vm_name
    """
    server = hcloud_client.servers.get_by_name(name)

    return _hcloud_format_server(server, full=True)


@saltcloud_action
@hcloud_api
def boot_instance(name):
    """
    Start a hcloud vm
    https://docs.hetzner.cloud/#server-actions-power-on-a-server

    name
        name of the vm to start

    CLI-Example

    .. code-block:: bash
        salt-cloud -a boot_instance vm_name
    """
    boot_action = _hcloud_wait_for_action(
        hcloud_client.servers.power_on(hcloud_client.servers.get_by_name(name))
    )

    return _hcloud_format_action(boot_action)


@saltcloud_action
@hcloud_api
def shutdown_instance(name, kwargs=None):
    """
    Hard (power off) or soft (acpi event) stop a hcloud vm
    https://docs.hetzner.cloud/#server-actions-shutdown-a-server
    https://docs.hetzner.cloud/#server-actions-power-off-a-server

    name
        name of the vm to stop
    hard
        True or False, whether to hard stop the vm or not

    CLI-Example

    .. code-block:: bash
        salt-cloud -a shutdown_instance vm_name
        salt-cloud -a shutdown_instance vm_name hard=True
    """
    if kwargs is None:
        kwargs = {"hard": False}

    shutdown_method = hcloud_client.servers.shutdown

    # Give the opportunity to use hard power off via kwargs
    if kwargs.get("hard"):
        shutdown_method = hcloud_client.servers.power_off

    shutdown_action = _hcloud_wait_for_action(
        shutdown_method(hcloud_client.servers.get_by_name(name))
    )

    return _hcloud_format_action(shutdown_action)


@saltcloud_action
@hcloud_api
def reboot_instance(name, kwargs=None):
    """
    Hard (power off) or soft (acpi event) reboot a hcloud vm
    https://docs.hetzner.cloud/#server-actions-soft-reboot-a-server
    https://docs.hetzner.cloud/#server-actions-reset-a-server

    name
        name of the vm to reboot
    hard
        True or False, whether to hard reboot the vm or not

    CLI-Example

    .. code-block:: bash
        salt-cloud -a reboot_instance vm_name
        salt-cloud -a reboot_instance vm_name hard=True
    """
    if kwargs is None:
        kwargs = {"hard": False}

    reboot_method = hcloud_client.servers.reboot

    # Give the opportunity to use hard power off via kwargs
    if kwargs.get("hard"):
        reboot_method = hcloud_client.servers.reset

    reboot_action = _hcloud_wait_for_action(
        reboot_method(hcloud_client.servers.get_by_name(name))
    )

    return _hcloud_format_action(reboot_action)


@saltcloud_function
@hcloud_api
def avail_datacenters():
    """
    List all available datacenters, because hcloud utilizes locations OR datacenters
    https://docs.hetzner.cloud/#datacenters-get-all-datacenters

    CLI-Example

    .. code-block:: bash
        salt-cloud -f avail_datacenters my_hcloud_provider
    """
    fromatted_datacenters = [
        _hcloud_format_datacenter(datacenter)
        for datacenter in hcloud_client.datacenters.get_all()
    ]

    return fromatted_datacenters


@saltcloud_function
@hcloud_api
def avail_ssh_keys():
    """
    List all available ssh keys added to the hcloud project
    https://docs.hetzner.cloud/#ssh-keys-get-all-ssh-keys

    CLI-Exampe

    .. code-block:: bash
        salt-cloud -f avail_ssh_keys my_hcloud_provider
    """
    formatted_ssh_keys = [
        _hcloud_format_ssh_keys(ssh_key) for ssh_key in hcloud_client.ssh_keys.get_all()
    ]

    return formatted_ssh_keys


@saltcloud_function
@hcloud_api
def avail_floating_ips(kwargs=None):
    """
    List all available floating ips
    https://docs.hetzner.cloud/#floating-ips-get-all-floating-ips

    name
        Can be used to filter floating ips by their name
    label_selector
        Can be used to filter floating ips by labels

    CLI-Example

    .. code-block:: bash
        salt-cloud -f avail_floating_ips my_hcloud_provider name='NameFilter' label_selector='LabelFilter'
    """
    if kwargs is None:
        kwargs = {}

    label_selector = kwargs.get("label_selector")
    name = kwargs.get("name")

    floating_ips = hcloud_client.floating_ips.get_all(
        label_selector=label_selector, name=name
    )

    return [_hcloud_format_floating_ip(floating_ip) for floating_ip in floating_ips]


@saltcloud_function
@hcloud_api
def floating_ip_change_dns_ptr(kwargs=None):
    """
    Change reverse dns entry for a floating ip
    https://docs.hetzner.cloud/#floating-ip-actions-change-reverse-dns-entry-for-a-floating-ip

    floating_ip
        (required) Id or name of the floating ip, to change the reverse dns entry of
    ip
        (required) ip address for which to set the reverse dns entry
    dns_ptr
        (optional) hostname to set as a reverse dns ptr entry, will reset to original default if not set

    CLI-Example

    .. code-block:: bash
        salt-cloud -f floating_ip_change_dns_ptr id='FloatingIpId' ip='1.1.1.1'
        salt-cloud -f floating_ip_change_dns_ptr name='FloatingIpName' ip='1.1.1.1' dns_ptr='example.com'
    """
    ret = {}

    if kwargs is None:
        kwargs = {}

    dns_ptr = kwargs.get("dns_ptr")
    ip = kwargs.get("ip")
    if ip is None:
        raise SaltCloudException(
            "You must provide the ip for the reverse dns entry update"
        )

    floating_ip = _hcloud_get_model_by_id_or_name(
        api=hcloud_client.floating_ips, kwargs=kwargs, kwarg_name="floating_ip"
    )

    floating_ip_change_dns_ptr_action = _hcloud_wait_for_action(
        hcloud_client.floating_ips.change_dns_ptr(
            floating_ip=floating_ip, ip=ip, dns_ptr=dns_ptr,
        )
    )

    ret.update(_hcloud_format_action(floating_ip_change_dns_ptr_action))

    return ret


@saltcloud_function
@hcloud_api
def floating_ip_change_protection(kwargs=None):
    """
    Change the protection configuration of the floating ip
    https://docs.hetzner.cloud/#floating-ip-actions-change-floating-ip-protection

    floating_ip
        (required) id or name of the floating ip
    delete
        (optional) If true, prevent the floating ip from being deleted

    CLI-Example

    .. code-block:: bash
        salt-cloud -f floating_ip_change_protection id='FloatingIpId'
        salt-cloud -f floating_ip_change_protection name='FloatingIpName' delete=True
    """
    ret = {}

    if kwargs is None:
        kwargs = {}

    delete = kwargs.get("delete")

    floating_ip = _hcloud_get_model_by_id_or_name(
        api=hcloud_client.floating_ips, kwargs=kwargs, kwarg_name="floating_ip"
    )

    floating_ip_change_protection_action = _hcloud_wait_for_action(
        hcloud_client.floating_ips.change_protection(
            floating_ip=floating_ip, delete=delete
        )
    )

    ret.update(_hcloud_format_action(floating_ip_change_protection_action))

    return ret


@saltcloud_function
@hcloud_api
def floating_ip_create(kwargs=None):
    """
    Creates a new floating ip.
    https://docs.hetzner.cloud/#floating-ips-create-a-floating-ip

    type
        (required) "ipv4" or "ipv6"
    server
        (optional) server to assign the floating ip to
    home_location
        (optional) home location of the floating ip. Only optional if no server is given
    description
        (optional) description for the floating ip
    name
        (optional) name of the floating ip
    labels
        (optional) user-defined labels as key-value pairs (key1:value1,key2:value2 ...)

    CLI-Example

    .. code-block:: bash
        salt-cloud -f floating_ip_create name=floating_ip_example labels=key1:value1,key2:value2 server=my_instance
    """
    if kwargs is None:
        kwargs = {}

    type = kwargs.get("type")
    if type is None:
        raise SaltCloudException(
            "You must provide the type of the floating ip to create as as keyword argument"
        )

    home_location_id_or_name = kwargs.get("home_location")
    server_id_or_name = kwargs.get("server")
    if home_location_id_or_name is None and server_id_or_name is None:
        raise SaltCloudException(
            "You must provide the id or name of a home location or server as a keyword argument"
        )

    description = kwargs.get("description")

    labels = kwargs.get("labels")
    if labels is not None:
        labels = {
            label.split(":")[0]: label.split(":")[1] for label in labels.split(",")
        }

    name = kwargs.get("name")

    ret = {}

    try:
        home_location = hcloud_client.locations.get_by_id(home_location_id_or_name)
    except APIException as e:
        if e.code == "invalid_input":
            home_location = hcloud_client.locations.get_by_name(
                home_location_id_or_name
            )
        else:
            raise e

    try:
        server = hcloud_client.servers.get_by_id(server_id_or_name)
    except APIException as e:
        if e.code == "invalid_input":
            server = hcloud_client.servers.get_by_name(server_id_or_name)
        else:
            raise e

    floating_ip_create_response = hcloud_client.floating_ips.create(
        home_location=home_location,
        server=server,
        type=type,
        description=description,
        labels=labels,
        name=name,
    )

    floating_ip_create_action = _hcloud_wait_for_action(
        floating_ip_create_response.action
    )

    ret.update(_hcloud_format_action(floating_ip_create_action))
    ret.update(
        {
            "floating_ip": _hcloud_format_floating_ip(
                floating_ip_create_response.floating_ip
            )
        }
    )

    return ret


@saltcloud_function
@hcloud_api
def floating_ip_delete(kwargs=None):
    """
    Delete a floating ip
    https://docs.hetzner.cloud/#floating-ips-delete-a-floating-ip

    floating_ip
        (required) name or id of the floating ip to delete

    CLI-Example

    .. code-block:: bash
            salt-cloud -f floating_ip_delete floating_ip=my_floating_ip
    """
    ret = {}

    if kwargs is None:
        kwargs = {}

    floating_ip = _hcloud_get_model_by_id_or_name(
        api=hcloud_client.floating_ips, kwargs=kwargs, kwarg_name="floating_ip"
    )

    floating_ip_deleted = hcloud_client.floating_ips.delete(floating_ip=floating_ip)

    ret.update({"deleted": floating_ip_deleted})

    return ret


@saltcloud_function
@hcloud_api
def floating_ip_unassign(kwargs=None):
    """
    Unassign a floating ip
    https://docs.hetzner.cloud/#floating-ip-actions-unassign-a-floating-ip

    floating_ip
        (required) name or id of the floating ip to unassign

    CLI-Example

    .. code-block:: bash
        salt-cloud -f floating_ip_unassign floating_ip=my_floating_ip
    """
    ret = {}

    if kwargs is None:
        kwargs = {}

    floating_ip = _hcloud_get_model_by_id_or_name(
        api=hcloud_client.floating_ips, kwargs=kwargs, kwarg_name="floating_ip"
    )

    floating_ip_unassign_action = _hcloud_wait_for_action(
        hcloud_client.floating_ips.unassign(floating_ip=floating_ip)
    )

    ret.update(_hcloud_format_action(floating_ip_unassign_action))

    return ret


@saltcloud_function
@hcloud_api
def floating_ip_update(kwargs=None):
    """
    Update a floating ip
    https://docs.hetzner.cloud/#floating-ips-update-a-floating-ip

    floating_ip
        (required) name or id of the floating ip to update
    description
        (optional) updated description of the floating ip
    labels
        (optional) updated labels as key-value pairs of the floating ip

    CLI-Example

    .. code-block:: bash
        salt-cloud -f floating_ip_update \
            floating_ip=my_floating_ip \
            description='New Description' \
            labels=key1:value1,key2:value2
    """
    ret = {}

    if kwargs is None:
        kwargs = {}

    description = kwargs.get("description")

    labels = kwargs.get("labels")
    if labels is not None:
        labels = {
            label.split(":")[0]: label.split(":")[1] for label in labels.split(",")
        }

    updated_name = kwargs.get("updated_name")

    floating_ip = _hcloud_get_model_by_id_or_name(
        api=hcloud_client.floating_ips, kwargs=kwargs, kwarg_name="floating_ip"
    )

    floating_ip_updated = hcloud_client.floating_ips.update(
        floating_ip=floating_ip,
        name=updated_name,
        description=description,
        labels=labels,
    )

    ret.update(_hcloud_format_floating_ip(floating_ip_updated))

    return ret


@saltcloud_function
@hcloud_api
def image_change_protection(kwargs=None):
    """
    Change protection of an image
    https://docs.hetzner.cloud/#image-actions-change-image-protection

    image
        (required) name or id of the image to change the protection of
    delete
        (optional) prevents the snapshot from being deleted if true

    CLI-Example

    .. code-block:: bash
        salt-cloud -f image_change_protection image=my_image delete=True
    """
    ret = {}

    if kwargs is None:
        kwargs = {}

    delete = kwargs.get("delete")

    image = _hcloud_get_model_by_id_or_name(
        api=hcloud_client.images, kwargs=kwargs, kwarg_name="image"
    )

    image_change_protection_action = _hcloud_wait_for_action(
        hcloud_client.images.change_protection(image=image, delete=delete)
    )

    ret.update(_hcloud_format_action(image_change_protection_action))

    return ret


@saltcloud_function
@hcloud_api
def image_delete(kwargs=None):
    """
    Delete an image
    https://docs.hetzner.cloud/#images-delete-an-image

    image
        (required) name or id of the image to delete

    CLI-Example

    .. code-block:: bash
        salt-cloud -f image_delete image=my_image
    """
    ret = {}

    if kwargs is None:
        kwargs = {}

    image = _hcloud_get_model_by_id_or_name(
        api=hcloud_client.images, kwargs=kwargs, kwarg_name="image"
    )

    image_deleted = hcloud_client.images.delete(image=image)

    ret.update({"deleted": image_deleted})

    return ret


@saltcloud_function
@hcloud_api
def image_update(kwargs=None):
    """
    Update an image
    https://docs.hetzner.cloud/#images-update-an-image

    image
        (required) name or id of the image to update
    type
        (optional) type the image should be converted to, only `snapshot` is valid
    description
        (optional) updated description of the image
    labels
        (optional) updated labels of the image as comma seperated key-value pairs

    CLI-Example

    .. code-block:: bash
        salt-cloud -f image_update \
        image=my_image \
        type=snapshot \
        description='Updated description' \
        labels=key1:value1,key2:value2
    """
    ret = {}

    if kwargs is None:
        kwargs = {}

    description = kwargs.get("description")

    labels = kwargs.get("labels")
    if labels is not None:
        labels = {
            label.split(":")[0]: label.split(":")[1] for label in labels.split(",")
        }

    type = kwargs.get("type")

    image = _hcloud_get_model_by_id_or_name(
        api=hcloud_client.images, kwargs=kwargs, kwarg_name="image"
    )

    updated_image = hcloud_client.images.update(
        image=image, type=type, description=description, labels=labels
    )

    ret.update(_hcloud_format_image(updated_image))

    return ret


@saltcloud_function
@hcloud_api
def network_add_route(kwargs=None):
    """
    Add route to network
    https://docs.hetzner.cloud/#network-actions-add-a-route-to-a-network

    network
        (required) id or name of the network
    destination
        (required) destination network or host of this route
    gateway
        (required) gateway for the route

    CLI-Example

    .. code-block:: bash
        salt-cloud -f network_add_route network=my_network destination='10.100.1.0/24' gateway='10.0.1.1'
    """
    ret = {}

    if kwargs is None:
        kwargs = {}

    destination = kwargs.get("destination")
    if destination is None:
        raise SaltCloudException("You must provide a destination as keyword argument")

    gateway = kwargs.get("gateway")
    if gateway is None:
        raise SaltCloudException("You must provide a gateway as keyword argument")

    network_route = NetworkRoute(destination=destination, gateway=gateway)

    network = _hcloud_get_model_by_id_or_name(
        api=hcloud_client.networks, kwargs=kwargs, kwarg_name="network"
    )

    network_add_route_action = _hcloud_wait_for_action(
        hcloud_client.networks.add_route(network=network, route=network_route)
    )

    ret.update(_hcloud_format_action(network_add_route_action))

    return ret


@saltcloud_function
@hcloud_api
def network_add_subnet(kwargs=None):
    """
    Add subnet to network
    https://docs.hetzner.cloud/#network-actions-add-a-subnet-to-a-network

    network
        (required) id or name of the network
    type
        (required) type of subnet
    ip_range
        (optional) range to allocate ips from
    network_zone
        (required) name of network zone

    CLI-Example

    .. code-block:: bash
        salt-cloud -f network_add_subnet network=my_network type=server ip_range='10.0.1.0/24' network_zone='eu-central'
    """
    ret = {}

    if kwargs is None:
        kwargs = {}

    ip_range = kwargs.get("ip_range")
    if ip_range is None:
        raise SaltCloudException("You must provide ip_range as keyword argument")

    type = kwargs.get("type")
    network_zone = kwargs.get("network_zone")
    gateway = kwargs.get("gateway")

    network_subnet = NetworkSubnet(
        ip_range=ip_range, network_zone=network_zone, gateway=gateway, type=type
    )

    network = _hcloud_get_model_by_id_or_name(
        api=hcloud_client.networks, kwargs=kwargs, kwarg_name="network"
    )

    network_add_subnet_action = _hcloud_wait_for_action(
        hcloud_client.networks.add_subnet(network=network, subnet=network_subnet)
    )

    ret.update(_hcloud_format_action(network_add_subnet_action))

    return ret


@saltcloud_function
@hcloud_api
def network_change_ip_range(kwargs=None):
    """
    Change the ip range of a network
    https://docs.hetzner.cloud/#network-actions-change-ip-range-of-a-network

    network
        (required) id or name of the network
    ip_range
        (required) the new prefix for the whole network

    CLI-Example

    .. code-block::bash
        salt-cloud -f network_change_ip_range network=my_network ip_range='10.0.0.0/12'
    """
    ret = {}

    if kwargs is None:
        kwargs = {}

    ip_range = kwargs.get("ip_range")
    if ip_range is None:
        raise SaltCloudException("You must provide ip_range as keyword argument")

    network = _hcloud_get_model_by_id_or_name(
        api=hcloud_client.networks, kwargs=kwargs, kwarg_name="network"
    )

    network_change_ip_range_action = _hcloud_wait_for_action(
        hcloud_client.networks.change_ip_range(network=network, ip_range=ip_range)
    )

    ret.update(_hcloud_format_action(network_change_ip_range_action))

    return ret


@saltcloud_function
@hcloud_api
def network_change_protection(kwargs=None):
    """
    Change the protection configuration of a network
    https://docs.hetzner.cloud/#network-actions-change-network-protection

    network
        (required) id or name of the network
    delete
        (optional) if true, prevents the network from being deleted

    CLI-Example

    .. code-block:: bash
        salt-cloud -f network=my_network delete=True
    """
    ret = {}

    if kwargs is None:
        kwargs = {}

    delete = kwargs.get("delete")

    network = _hcloud_get_model_by_id_or_name(
        api=hcloud_client.networks, kwargs=kwargs, kwarg_name="network"
    )

    network_change_protection_action = _hcloud_wait_for_action(
        hcloud_client.networks.change_protection(network=network, delete=delete)
    )

    ret.update(_hcloud_format_action(network_change_protection_action))

    return ret


@saltcloud_function
@hcloud_api
def network_create(kwargs=None):
    """
    Create a network
    https://docs.hetzner.cloud/#networks-create-a-network
    To add subnets and routes like shown in the documentation, use network_add_route and network_add_subnet functions

    name
        (required) name of the network
    ip_range
        (required) ip range of the network which must span all included subnets
    labels
        (optional) networks labels as comma separated key-value pairs

    CLI-Example

    .. code-block:: bash
        salt-cloud -f network_create name=my_network ip_range='10.0.0.0/16' labels=key1:value1,key2:value2
    """
    ret = {}

    if kwargs is None:
        kwargs = {}

    name = kwargs.get("name")
    if name is None:
        raise SaltCloudException("You must provide name as keyword argument")

    ip_range = kwargs.get("ip_range")
    if name is None:
        raise SaltCloudException("You must provide ip_range as keyword argument")

    # TODO: Write subnets and routes to doc (add them by the endpoint)

    labels = kwargs.get("labels")
    if labels is not None:
        labels = {
            label.split(":")[0]: label.split(":")[1] for label in labels.split(",")
        }

    network_created = hcloud_client.networks.create(
        name=name, ip_range=ip_range, labels=labels
    )

    ret.update(_hcloud_format_network(network_created))

    return ret


@saltcloud_function
@hcloud_api
def network_delete(kwargs=None):
    """
    Delete a network
    https://docs.hetzner.cloud/#networks-delete-a-network

    network
        (required) id or name of the network

    CLI-Example

    .. code-block:: bash
        salt-cloud -f network_delete network=my_network
    """
    ret = {}

    if kwargs is None:
        kwargs = {}

    network = _hcloud_get_model_by_id_or_name(
        api=hcloud_client.networks, kwargs=kwargs, kwarg_name="network"
    )

    network_deleted = hcloud_client.networks.delete(network=network)

    ret.update({"deleted": network_deleted})

    return ret


@saltcloud_function
@hcloud_api
def network_delete_route(kwargs=None):
    """
    Delete a route entry from a network
    https://docs.hetzner.cloud/#network-actions-delete-a-route-from-a-network

    network
        (required) name or id of the network
    destination
        (required) destination network or host of this route
    gateway
        (required) gateway for the route

    CLI-Example

    .. code-block:: bash
        salt-cloud -f network_delete_route network=my_network destination='10.100.1.0/24' gateway='10.0.1.1'
    """
    ret = {}

    if kwargs is None:
        kwargs = {}

    destination = kwargs.get("destination")
    if destination is None:
        raise SaltCloudException("You must provide a destination as keyword argument")

    gateway = kwargs.get("gateway")
    if gateway is None:
        raise SaltCloudException("You must provide a gateway as keyword argument")

    network = _hcloud_get_model_by_id_or_name(
        api=hcloud_client.networks, kwargs=kwargs, kwarg_name="network"
    )

    network_route = NetworkRoute(destination=destination, gateway=gateway)

    network_delete_route_action = _hcloud_wait_for_action(
        hcloud_client.networks.delete_route(network=network, route=network_route)
    )

    ret.update(_hcloud_format_action(network_delete_route_action))

    return ret


@saltcloud_function
@hcloud_api
def network_delete_subnet(kwargs=None):
    """
    Delete a subnet from a network, works only if no servers are attached to the subnet
    https://docs.hetzner.cloud/#network-actions-delete-a-subnet-from-a-network

    network
        (required) id or name of the network
    ip_range
        (required) ip range of subnet to delete

    CLI-Example

    .. code-block:: bash
        salt-cloud -f network_delete_subnet network=my_network ip_range='10.0.1.0/24'
    """
    ret = {}

    if kwargs is None:
        kwargs = {}

    ip_range = kwargs.get("ip_range")
    if ip_range is None:
        raise SaltCloudException("You must provide ip_range as keyword argument")

    network_subnet = NetworkSubnet(ip_range=ip_range)

    network = _hcloud_get_model_by_id_or_name(
        api=hcloud_client.networks, kwargs=kwargs, kwarg_name="network"
    )

    network_delete_subnet_action = _hcloud_wait_for_action(
        hcloud_client.networks.delete_subnet(network=network, subnet=network_subnet)
    )

    ret.update(_hcloud_format_action(network_delete_subnet_action))

    return ret


@saltcloud_function
@hcloud_api
def network_update(kwargs=None):
    """
    Update network properties
    https://docs.hetzner.cloud/#networks-update-a-network

    network
        (required) id or name of the network
    name
        (optional) new network name
    labels
        (optional) updated labels as comma separated key-value pairs

    CLI-Example

    .. code-block:: bash
        salt-cloud -f network_update network=my_network name=my_new_network labels=key1:value1,key2:value2
    """
    ret = {}

    if kwargs is None:
        kwargs = {}

    name = kwargs.get("name")
    labels = kwargs.get("labels")
    if labels is not None:
        labels = {
            label.split(":")[0]: label.split(":")[1] for label in labels.split(",")
        }

    network = _hcloud_get_model_by_id_or_name(
        api=hcloud_client.networks, kwargs=kwargs, kwarg_name="network",
    )

    updated_network = hcloud_client.networks.update(
        network=network, name=name, labels=labels
    )

    ret.update({"updated": _hcloud_format_network(updated_network)})

    return ret


@saltcloud_function
@hcloud_api
def ssh_key_create(kwargs=None):
    """
    Create a ssh key
    https://docs.hetzner.cloud/#ssh-keys-create-an-ssh-key

    name
        (required) the name of the new ssh key
    public_key
        (required) the public ssh key
    labels
        (optional) user-defined labels as comma seperated key-value pairs

    CLI-Example

    .. code-block:: bash
        salt-cloud -f ssh_key_create \
            name=my_ssh_key \
            public_key='ssh-rsa ... test@localhost' \
            labels=key1:value1,key2:value2
    """
    ret = {}

    if kwargs is None:
        kwargs = {}

    name = kwargs.get("name")
    if name is None:
        raise SaltCloudException("You must provide name as keyword argument")

    public_key = kwargs.get("public_key")
    if public_key is None:
        raise SaltCloudException("You must provide public_key as keyword argument")

    labels = kwargs.get("labels")
    if labels is not None:
        labels = {
            label.split(":")[0]: label.split(":")[1] for label in labels.split(",")
        }

    created_ssh_key = hcloud_client.ssh_keys.create(
        name=name, public_key=public_key, labels=labels
    )

    ret.update({"created": _hcloud_format_ssh_keys(created_ssh_key)})

    return ret


@saltcloud_function
@hcloud_api
def ssh_key_update(kwargs=None):
    """
    Update a ssh key
    https://docs.hetzner.cloud/#ssh-keys-update-an-ssh-key

    ssh_key
        (required) name or id of the ssh key
    name
        (optional) new name of the ssh key
    labels
        (optional) user defined labels as comma separated key-value pairs

    CLI-Example

    .. code-block:: bash
        salt-cloud -f ssh_key_update \
            ssh_key=my_ssh_key \
            name=my_updated_ssh_key \
            labels=key1:value1,key2:value2
    """
    ret = {}

    if kwargs is None:
        kwargs = {}

    name = kwargs.get("name")

    labels = kwargs.get("labels")
    if labels is not None:
        labels = {
            label.split(":")[0]: label.split(":")[1] for label in labels.split(",")
        }

    ssh_key = _hcloud_get_model_by_id_or_name(
        api=hcloud_client.ssh_keys, kwargs=kwargs, kwarg_name="ssh_key"
    )

    updated_ssh_key = hcloud_client.ssh_keys.update(
        ssh_key=ssh_key, name=name, labels=labels
    )

    ret.update({"updated": _hcloud_format_ssh_keys(updated_ssh_key)})

    return ret


@saltcloud_function
@hcloud_api
def ssh_key_delete(kwargs=None):
    """
    Delete a ssh key
    https://docs.hetzner.cloud/#ssh-keys-delete-an-ssh-key

    ssh_key
        (required) name or id of the ssh key to delete

    CLI-Example

    .. code-block:: bash
        salt-cloud -f ssh_key_delete ssh_key=my_ssh_key
    """
    ret = {}

    if kwargs is None:
        kwargs = {}

    ssh_key = _hcloud_get_model_by_id_or_name(
        api=hcloud_client.ssh_keys, kwargs=kwargs, kwarg_name="ssh_key"
    )

    deleted_ssh_key = hcloud_client.ssh_keys.delete(ssh_key=ssh_key)

    ret.update({"deleted": deleted_ssh_key})

    return ret


@saltcloud_function
@hcloud_api
def volume_change_protection(kwargs=None):
    """
    Change protection state of a volume
    https://docs.hetzner.cloud/#volume-actions-change-volume-protection

    volume
        (required) name or id of the volume
    delete
        (optional) if true, prevents from deletion

    CLI-Example

    .. code-block:: bash
        salt-cloud -f volume_change_protection volume=my_volume delete=True
    """
    ret = {}

    if kwargs is None:
        kwargs = {}

    delete = kwargs.get("delete")

    volume = _hcloud_get_model_by_id_or_name(
        api=hcloud_client.volumes, kwargs=kwargs, kwarg_name="volume"
    )

    volume_change_protection_action = _hcloud_wait_for_action(
        hcloud_client.volumes.change_protection(volume=volume, delete=delete)
    )

    ret.update(_hcloud_format_action(volume_change_protection_action))

    return ret


@saltcloud_function
@hcloud_api
def volume_create(kwargs=None):
    """
    Create a new volume
    https://docs.hetzner.cloud/#volumes-create-a-volume

    size
        (required) size of the volume in gb, only full numbers
    name
        (required) name of the volume
    labels
        (optional) user defined labels as comma separated key-value pairs
    server
        (optional) name or id of the server the volume should be attached to
    location
        (optional) name or id of the location the volume should be in, omitted if server is already set
    automount
        (optional) if true, the volume is automatically mounted on the provided server
    format
        (optional) xfs or ext4

    CLI-Example

    .. code-block:: bash
        salt-cloud -f volume_create \
            size=10 \
            name=my_volume \
            labels=key1:value1,key2:value2 \
            server=my_instance \
            automount=True \
            format=ext4
    """
    ret = {}

    if kwargs is None:
        kwargs = {}

    size = kwargs.get("size")
    name = kwargs.get("name")

    labels = kwargs.get("labels")
    if labels is not None:
        labels = {
            label.split(":")[0]: label.split(":")[1] for label in labels.split(",")
        }

    server = _hcloud_get_model_by_id_or_name(
        api=hcloud_client.servers, kwargs=kwargs, kwarg_name="server", optional=True
    )
    location = _hcloud_get_model_by_id_or_name(
        api=hcloud_client.locations, kwargs=kwargs, kwarg_name="location", optional=True
    )
    automount = kwargs.get("automount")
    format = kwargs.get("format")

    create_volume_response = hcloud_client.volumes.create(
        size=size,
        name=name,
        labels=labels,
        server=server,
        location=location,
        automount=automount,
        format=format,
    )

    create_volume_action = _hcloud_wait_for_action(create_volume_response.action)

    ret.update({"created": _hcloud_format_volume(create_volume_response.volume)})
    ret.update({"action": _hcloud_format_action(create_volume_action)})

    return ret


@saltcloud_function
@hcloud_api
def volume_delete(kwargs=None):
    """
    Delete a volume
    https://docs.hetzner.cloud/#volumes-delete-a-volume

    volume
        (required) name or id the volume

    CLI-Example

    .. code-block:: bash
        salt-cloud -f volume_delete volume=my_volume
    """
    ret = {}

    if kwargs is None:
        kwargs = {}

    volume = _hcloud_get_model_by_id_or_name(
        api=hcloud_client.volumes, kwargs=kwargs, kwarg_name="volume"
    )

    deleted_volume = hcloud_client.volumes.delete(volume=volume)

    ret.update({"deleted": deleted_volume})

    return ret


@saltcloud_function
@hcloud_api
def volume_detach(kwargs=None):
    """
    Detach a volume
    https://docs.hetzner.cloud/#volume-actions-detach-volume

    volume
        (required) name or id of the volume

    CLI-Example

    .. code-block:: bash
        salt-cloud -f volume_detach volume=my_volume
    """
    ret = {}

    if kwargs is None:
        kwargs = {}

    volume = _hcloud_get_model_by_id_or_name(
        api=hcloud_client.volumes, kwargs=kwargs, kwarg_name="volume"
    )

    detach_volume_action = _hcloud_wait_for_action(
        hcloud_client.volumes.detach(volume=volume)
    )

    ret.update(_hcloud_format_action(detach_volume_action))

    return ret


@saltcloud_function
@hcloud_api
def volume_resize(kwargs=None):
    """
    Resize a volume
    https://docs.hetzner.cloud/#volume-actions-resize-volume

    volume
        (required) name or id of the volume
    size
        (required) new size of the volume as full number in gb, must be greater than it was before

    CLI-Example

    .. code-block:: bash
        salt-cloud -f volume_resize volume=my_volume size=11
    """
    ret = {}

    if kwargs is None:
        kwargs = {}

    size = kwargs.get("size")

    volume = _hcloud_get_model_by_id_or_name(
        api=hcloud_client.volumes, kwargs=kwargs, kwarg_name="volume"
    )

    volume_resize_action = _hcloud_wait_for_action(
        hcloud_client.volumes.resize(volume=volume, size=size)
    )

    ret.update(_hcloud_format_action(volume_resize_action))

    return ret


@saltcloud_function
@hcloud_api
def volume_update(kwargs=None):
    """
    Update a volume
    https://docs.hetzner.cloud/#volumes-update-a-volume

    volume
        (required) name or id of the volume
    name
        (optional) new name of the volume
    labels
        (optional) user defined labels as comma separated key-value pairs

    CLI-Example

    .. code-block:: bash
        salt-cloud -f volume_update volume=my_volume name=my_updated_volume labels=key1:value1,key2:value2
    """
    ret = {}

    if kwargs is None:
        kwargs = {}

    volume = _hcloud_get_model_by_id_or_name(
        api=hcloud_client.volumes, kwargs=kwargs, kwarg_name="volume"
    )

    name = kwargs.get("name")

    labels = kwargs.get("labels")
    if labels is not None:
        labels = {
            label.split(":")[0]: label.split(":")[1] for label in labels.split(",")
        }

    updated_volume = hcloud_client.volumes.update(
        volume=volume, name=name, labels=labels
    )

    ret.update({"updated": _hcloud_format_volume(updated_volume)})

    return ret


@saltcloud_action
@hcloud_api
def enable_rescue_mode(name, kwargs=None):
    """
    Enable the hetzner rescue system, which starts a minimal linux distribution on next boot to repair or reinstall
    a server. It is automatically disabled when you first boot into it or do not use it for 60 minutes.
    https://docs.hetzner.cloud/#server-actions-enable-rescue-mode-for-a-server

    type
        (optional) type of the rescue system to boot, default 'linux64'
    ssh_keys
        (optional) comma separated list of ssh key ids to inject into the rescue system

    CLI-Example

    .. code-block:: bash
        salt-cloud -a enable_rescue_mode my_instance type=linux64 ssh_keys=1,2,3
    """
    ret = {}

    if kwargs is None:
        kwargs = {}

    ssh_keys = kwargs.get("ssh_keys")
    if ssh_keys is not None:
        ssh_keys = [key for key in ssh_keys.split(",")]

    rescue_type = kwargs.get("type")

    server = hcloud_client.servers.get_by_name(name)

    enable_rescue_mode_response = hcloud_client.servers.enable_rescue(
        server=server, type=rescue_type, ssh_keys=ssh_keys
    )

    rescue_mode_action = _hcloud_wait_for_action(enable_rescue_mode_response.action)
    rescue_mode_root_password = enable_rescue_mode_response.root_password

    ret.update(_hcloud_format_action(rescue_mode_action))
    ret.update({"root_password": rescue_mode_root_password})

    return ret


@saltcloud_action
@hcloud_api
def disable_rescue_mode(name):
    """
    Disable the hetzner rescue system on an instance
    https://docs.hetzner.cloud/#server-actions-disable-rescue-mode-for-a-server

    CLI-Example

    .. code-block:: bash
        salt-cloud -a disable_rescue_mode my_instance
    """
    ret = {}

    disable_rescue_mode_action = _hcloud_wait_for_action(
        hcloud_client.servers.disable_rescue(hcloud_client.servers.get_by_name(name))
    )

    ret.update(_hcloud_format_action(disable_rescue_mode_action))

    return ret


@saltcloud_action
@hcloud_api
def create_image(name, kwargs=None):
    """
    Create an image of a server by copying the contents of its disks.
    https://docs.hetzner.cloud/#server-actions-create-image-from-a-server

    description
        (optional) description of the image, will be auto-generated if not set
    type
        (optional) type of the image to create
    labels
        (optional) user defined labels as comma separated key-value pairs

    CLI-Example

    .. code-block:: bash
        salt-cloud -a create_image my_instance description='My Snapshot' type='snapshot' labels=key1:value1,key2:value2
    """
    ret = {}

    if kwargs is None:
        kwargs = {}

    labels = kwargs.get("labels")
    if labels is not None:
        labels = {
            label.split(":")[0]: label.split(":")[1] for label in labels.split(",")
        }

    create_image_response = hcloud_client.servers.create_image(
        hcloud_client.servers.get_by_name(name),
        description=kwargs.get("description"),
        type=kwargs.get("type"),
        labels=labels,
    )

    create_image_action = _hcloud_wait_for_action(create_image_response.action)
    created_image = create_image_response.image

    ret.update({"action": _hcloud_format_action(create_image_action)})
    ret.update({"image": _hcloud_format_image(created_image)})

    return ret


@saltcloud_action
@hcloud_api
def change_type(name, kwargs=None):
    """
    Change the type of a server
    https://docs.hetzner.cloud/#server-actions-change-the-type-of-a-server

    upgrade_disk
        (required) if false, do not upgrade the disk
    server_type
        (required) id or name of server type the server should migrate to

    CLI-Example

    .. code-block:: bash
        salt-cloud -a change_type my_instance upgrade_disk=False server_type='cx21'
    """
    ret = {}

    if kwargs is None:
        kwargs = {}

    if kwargs.get("upgrade_disk") is None:
        raise SaltCloudException("You must provide upgrade_disk as keyword argument")

    server_type = _hcloud_get_model_by_id_or_name(
        api=hcloud_client.server_types, kwargs=kwargs, kwarg_name="server_type"
    )

    change_type_action = _hcloud_wait_for_action(
        hcloud_client.servers.change_type(
            hcloud_client.servers.get_by_name(name),
            server_type=server_type,
            upgrade_disk=kwargs.get("upgrade_disk"),
        )
    )

    ret.update(_hcloud_format_action(change_type_action))

    return ret


@saltcloud_action
@hcloud_api
def enable_backup(name):
    """
    Enable backup for an instance
    https://docs.hetzner.cloud/#server-actions-enable-and-configure-backups-for-a-server

    CLI-Example

    .. code-block:: bash
        salt-cloud -a enable_backup my_instance
    """
    ret = {}

    enable_backup_action = _hcloud_wait_for_action(
        hcloud_client.servers.enable_backup(hcloud_client.servers.get_by_name(name))
    )

    ret.update(_hcloud_format_action(enable_backup_action))

    return ret


@saltcloud_action
@hcloud_api
def disable_backup(name):
    """
    Disable backup for an instance
    https://docs.hetzner.cloud/#server-actions-disable-backups-for-a-server

    CLI-Example

    .. code-block:: bash
        salt-cloud -a disable_backup my_instance
    """
    ret = {}

    disable_backup_action = _hcloud_wait_for_action(
        hcloud_client.servers.disable_backup(hcloud_client.servers.get_by_name(name))
    )

    ret.update(_hcloud_format_action(disable_backup_action))

    return ret


@saltcloud_function
@hcloud_api
def avail_isos(kwargs=None):
    """
    Return all available ISO objects
    https://docs.hetzner.cloud/#isos-get-all-isos

    name
        (optional) can be used to filter ISO objects by their name

    CLI-Example

    .. code-block:: bash
        salt-cloud -f avail_isos name='filter'
    """
    if kwargs is None:
        kwargs = {}

    name = kwargs.get("name")

    if name is not None:
        isos = hcloud_client.isos.get_all(name)
    else:
        isos = hcloud_client.isos.get_all()

    isos = [_hcloud_format_iso(iso) for iso in isos]

    return isos


@saltcloud_function
@hcloud_api
def attach_iso(name, kwargs=None):
    """
    Attach an ISO to an instance
    https://docs.hetzner.cloud/#server-actions-attach-an-iso-to-a-server

    iso
        (required) id or name of the iso to attach

    CLI-Example

    .. code-block:: bash
        salt-cloud -a attach_iso my_instance iso=my_iso
    """
    ret = {}

    if kwargs is None:
        kwargs = {}

    server = hcloud_client.servers.get_by_name(name)

    iso = _hcloud_get_model_by_id_or_name(
        api=hcloud_client.isos, kwargs=kwargs, kwarg_name="iso"
    )

    attach_iso_action = _hcloud_wait_for_action(
        hcloud_client.servers.attach_iso(server=server, iso=iso)
    )

    ret.update(_hcloud_format_action(attach_iso_action))

    return ret


@saltcloud_action
@hcloud_api
def detach_iso(name):
    """
    Detach an ISO from an instance
    https://docs.hetzner.cloud/#server-actions-detach-an-iso-from-a-server

    CLI-Example

    .. code-block:: bash
        salt-cloud -f detach_iso my_instance
    """
    ret = {}

    server = hcloud_client.servers.get_by_name(name)

    detach_iso_action = _hcloud_wait_for_action(
        hcloud_client.servers.detach_iso(server=server)
    )

    ret.update(_hcloud_format_action(detach_iso_action))

    return ret


@saltcloud_action
@hcloud_api
def change_dns_ptr(name, kwargs=None):
    """
    Change reverse DNS entry for an instance
    https://docs.hetzner.cloud/#server-actions-change-reverse-dns-entry-for-this-server

    ip
        (required) primary ip address for which the reverse DNS entry should be set
    dns_ptr
        (optional) hostname to set as a reverse DNS PTR, reset to original value if omitted

    CLI-Example

    .. code-block:: bash
        salt-cloud -a change_dns_ptr my_instance ip='1.2.3.4' dns_ptr='server01.example.com'
    """
    ret = {}

    if kwargs is None:
        kwargs = {}

    # No check, because None is allowed for dns_ptr
    dns_ptr = kwargs.get("dns_ptr")

    ip = kwargs.get("ip")
    if ip is None:
        raise SaltCloudException("Please provide at least ip as keyword argument")

    server = hcloud_client.servers.get_by_name(name)

    change_dns_ptr_action = _hcloud_wait_for_action(
        hcloud_client.servers.change_dns_ptr(server=server, ip=ip, dns_ptr=dns_ptr)
    )

    ret.update(_hcloud_format_action(change_dns_ptr_action))

    return ret


@saltcloud_action
@hcloud_api
def change_protection(name, kwargs=None):
    """
    Change protection configuration of an instances
    https://docs.hetzner.cloud/#server-actions-change-server-protection

    delete
        (optional) if true, prevents the server from being deleted
    rebuild
        (optional) if true, prevents the server from being rebuilt

    CLI-Example

    .. code-block:: bash
        salt-cloud -a change_protection my_instance delete=True rebuild=True
    """
    ret = {}

    if kwargs is None:
        kwargs = {}

    delete = kwargs.get("delete")
    rebuild = kwargs.get("rebuild")

    server = hcloud_client.servers.get_by_name(name)

    change_protection_action = _hcloud_wait_for_action(
        hcloud_client.servers.change_protection(
            server=server, delete=delete, rebuild=rebuild
        )
    )

    ret.update(_hcloud_format_action(change_protection_action))

    return ret


@saltcloud_action
@hcloud_api
def request_console(name):
    """
    Request console for an instance
    https://docs.hetzner.cloud/#server-actions-request-console-for-a-server

    CLI-Example

    .. code-block:: bash
        salt-cloud -a request_console my_instance
    """
    ret = {}

    server = hcloud_client.servers.get_by_name(name)

    request_console_response = hcloud_client.servers.request_console(server=server)

    request_console_wss_url = request_console_response.wss_url
    request_console_password = request_console_response.password

    request_console_action = _hcloud_wait_for_action(request_console_response.action)

    ret.update({"wss_url": request_console_wss_url})
    ret.update({"password": request_console_password})

    ret.update(_hcloud_format_action(request_console_action))

    return ret


@saltcloud_function
@hcloud_api
def avail_networks(kwargs=None):
    """
    Return all available networks
    https://docs.hetzner.cloud/#networks-get-all-networks

    name
        (required) can be used to filter networks by their name
    label_selector
        (required) can be used to filter networks by labels

    CLI-Example

    .. code-block:: bash
        salt-cloud -f avail_networks name='filter' label_selector='label_filter'
    """
    if kwargs is None:
        kwargs = {}

    name = kwargs.get("name")
    label_selector = kwargs.get("label_selector")

    networks = hcloud_client.networks.get_all(name=name, label_selector=label_selector)

    return [_hcloud_format_network(network) for network in networks]


@saltcloud_action
@hcloud_api
def attach_to_network(name, kwargs=None):
    """
    Attach a server to a network
    https://docs.hetzner.cloud/#server-actions-attach-a-server-to-a-network

    network
        (required) id or name of the network to attach
    ip
        (optional) ip to request to be assigned to this server, auto ip is assigned if this is omitted
    alias_ips
        (optional) comma separated additional ips to be assigned to this server

    CLI-Example

    .. code-block:: bash
        salt-cloud -a attach_to_network my_instance network=my_network ip='10.0.1.1' alias_ips='10.0.1.2,10.0.1.3'
    """
    ret = {}

    if kwargs is None:
        kwargs = {}

    ip = kwargs.get("ip")
    alias_ips = kwargs.get("alias_ips")

    if alias_ips is not None:
        alias_ips = [ip for ip in alias_ips.split(",")]

    server = hcloud_client.servers.get_by_name(name)
    network = _hcloud_get_model_by_id_or_name(
        api=hcloud_client.networks, kwargs=kwargs, kwarg_name="network"
    )

    attach_to_network_action = _hcloud_wait_for_action(
        hcloud_client.servers.attach_to_network(
            server=server, network=network, ip=ip, alias_ips=alias_ips
        )
    )

    ret.update(_hcloud_format_action(attach_to_network_action))

    return ret


@saltcloud_action
@hcloud_api
def detach_from_network(name, kwargs=None):
    """
    Detach a network from an instance
    https://docs.hetzner.cloud/#server-actions-detach-a-server-from-a-network

    network
        (required) id or name of the network to detach

    CLI-Example

    .. code-block:: bash
        salt-cloud -a detach_from_network my_instance network=my_network
    """
    ret = {}

    if kwargs is None:
        kwargs = {}

    server = hcloud_client.servers.get_by_name(name)
    network = _hcloud_get_model_by_id_or_name(
        api=hcloud_client.networks, kwargs=kwargs, kwarg_name="network"
    )

    detach_from_network_action = _hcloud_wait_for_action(
        hcloud_client.servers.detach_from_network(server=server, network=network)
    )

    ret.update(_hcloud_format_action(detach_from_network_action))

    return ret


@saltcloud_action
@hcloud_api
def change_alias_ips(name, kwargs=None):
    """
    Change alias ips of a network attached on an instance
    https://docs.hetzner.cloud/#server-actions-change-alias-ips-of-a-network

    network
        (required) id or name of the network
    alias_ips
        (required) new alias ips to set for this server

    CLI-Example

    .. code-block:: bash
        salt-cloud -a change_alias_ips my_instance network=my_network alias_ips='10.0.2.2,10.0.2.3'
    """
    ret = {}

    if kwargs is None:
        kwargs = {}

    alias_ips = kwargs.get("alias_ips")
    if alias_ips is None:
        raise SaltCloudException(
            "Please provide alias ips of the network you want to change as a keyword argument"
        )

    alias_ips = [ip for ip in alias_ips.split(",")]

    network = _hcloud_get_model_by_id_or_name(
        api=hcloud_client.networks, kwargs=kwargs, kwarg_name="network"
    )
    server = hcloud_client.servers.get_by_name(name)

    change_alias_ips_action = _hcloud_wait_for_action(
        hcloud_client.servers.change_alias_ips(
            server=server, network=network, alias_ips=alias_ips
        )
    )

    ret.update(_hcloud_format_action(change_alias_ips_action))

    return ret


@saltcloud_action
@hcloud_api
def assign_floating_ip(name, kwargs=None):
    """
    Assign a floating ip to a server
    https://docs.hetzner.cloud/#floating-ip-actions-assign-a-floating-ip-to-a-server

    floating_ip
        (required) id or name of the floating ip

    CLI-Example

    .. code-block:: bash
        salt-cloud -a assign_floating_ip my_instance floating_ip=my_floating_ip
    """
    ret = {}

    if kwargs is None:
        kwargs = {}

    server = hcloud_client.servers.get_by_name(name)

    floating_ip = _hcloud_get_model_by_id_or_name(
        api=hcloud_client.floating_ips, kwargs=kwargs, kwarg_name="floating_ip"
    )

    assign_floating_ip_action = _hcloud_wait_for_action(
        hcloud_client.floating_ips.assign(server=server, floating_ip=floating_ip)
    )

    ret.update(_hcloud_format_action(assign_floating_ip_action))

    return ret


@saltcloud_action
@hcloud_api
def attach_volume(name, kwargs=None):
    """
    Attach volume to a server
    https://docs.hetzner.cloud/#volume-actions-attach-volume-to-a-server

    volume
        (required) id or name of the volume
    automount
        (optional) auto-mount the volume if true after attaching it

    CLI-Example

    .. code-block::bash
        salt-cloud -a attach_volume my_instance volume=my_volume automount=True
    """
    ret = {}

    if kwargs is None:
        kwargs = {}

    server = hcloud_client.servers.get_by_name(name)

    volume = _hcloud_get_model_by_id_or_name(
        api=hcloud_client.volumes, kwargs=kwargs, kwarg_name="volume"
    )

    automount = kwargs.get("automount")

    attach_volume_action = _hcloud_wait_for_action(
        hcloud_client.volumes.attach(server=server, volume=volume, automount=automount)
    )

    ret.update(_hcloud_format_action(attach_volume_action))

    return ret


def _hcloud_get_model_by_id_or_name(api, kwargs, kwarg_name, optional=False):
    """
    Get a model based on its Hetzner Cloud API by id or name, like it's usual.
    """

    id_or_name = kwargs.get(kwarg_name)
    if id_or_name is None:
        if optional:
            return None
        else:
            raise SaltCloudException(
                "You must provide id or name as {0} in the keyword arguments".format(
                    kwarg_name
                )
            )

    try:
        model = api.get_by_id(id_or_name)
    except APIException as e:
        if e.code == "invalid input":
            model = api.get_by_name(id_or_name)
        else:
            raise e

    return model


def _hcloud_find_matching_ssh_pub_key(local_ssh_public_key):
    """
    Returns the matching public key uploaded to Hetzner Cloud API, or None if there is no matching key.
    """
    (local_algorithm, local_key, *local_host) = local_ssh_public_key.split()

    hcloud_ssh_public_keys = hcloud_client.ssh_keys.get_all()

    matching_pub_key = None
    for key in hcloud_ssh_public_keys:
        (hcloud_algorithm, hcloud_key, *hcloud_host) = key.public_key.split()
        if hcloud_algorithm == local_algorithm and hcloud_key == local_key:
            matching_pub_key = key
            break

    return matching_pub_key


def _hcloud_wait_for_action(action):
    """
    Wait and poll for a Hetzner Cloud API action to finish with some info log while processing and return the finished
    action.
    """
    while action.status == "running":
        action = hcloud_client.actions.get_by_id(action.id)
        log.info("Progress: {0:3d}%".format(action.progress))
        time.sleep(2)
    return action


def _hcloud_format_location(location):
    """
    Return a formatted dict based on a Hetzner Cloud API location
    """
    formatted_location = {
        "id": location.id,
        "name": location.name,
        "description": location.description,
        "country": location.country,
        "city": location.city,
        "latitude": location.latitude,
        "longitude": location.longitude,
        "network_zone": location.network_zone,
    }

    return formatted_location


def _hcloud_format_datacenter(datacenter):
    """
    Return a formatted dict based on a Hetzner Cloud API datacenter
    """
    formatted_datacenter = {
        "id": datacenter.id,
        "name": datacenter.name,
        "description": datacenter.description,
        "location": datacenter.location.name,
        "server_types": {
            "available": [
                server_type.name for server_type in datacenter.server_types.available
            ],
            "supported": [
                server_type.name for server_type in datacenter.server_types.supported
            ],
            "available_for_migration": [
                server_type.name
                for server_type in datacenter.server_types.available_for_migration
            ],
        },
    }

    return formatted_datacenter


def _hcloud_format_action(action):
    """
    Return a formatted dict based on a Hetzner Cloud API action
    """
    salt_dict = {
        "command": action.command,
        "resources": action.resources,
        "status": action.status,
        "started": action.started.strftime("%c"),
        "finished": action.finished.strftime("%c"),
    }

    if action.status == "error":
        salt_dict["error"] = action.error

    return salt_dict


def _hcloud_format_server(server, full=False):
    """
    Return a formatted dict based on a Hetzner Cloud API server
    """
    server_salt = {
        "id": server.id,
        "size": server.server_type.name,
        "state": server.status,
        "private_ips": server.private_net,
        "public_ips": [server.public_net.ipv4.ip, server.public_net.ipv6.ip]
        + [floating_ip.ip for floating_ip in server.public_net.floating_ips],
    }

    if server.image is not None:
        server_salt["image"] = server.image.name
    else:
        # HCloud-API doesn't return an image if it is a backup or snapshot based server
        server_salt["image"] = "unknown"

    if full:
        server_salt["created"] = server.created.strftime("%c")
        server_salt["datacenter"] = server.datacenter.name

        if server.iso is not None:
            # Servers iso name is only set for public iso's
            server_salt["iso"] = (
                server.iso.name if server.iso.name is not None else server.iso.id
            )

        server_salt["rescue_enabled"] = server.rescue_enabled
        server_salt["locked"] = server.locked

        # Backup window is only set if there are backups enabled
        if server.backup_window is not None:
            server_salt["backup_window"] = server.backup_window

        server_salt["outgoing_traffic"] = _get_formatted_bytes_string(
            server.outgoing_traffic if server.outgoing_traffic is not None else 0
        )
        server_salt["ingoing_traffic"] = _get_formatted_bytes_string(
            server.ingoing_traffic if server.ingoing_traffic is not None else 0
        )
        server_salt["included_traffic"] = _get_formatted_bytes_string(
            server.included_traffic
        )

        server_salt["protection"] = server.protection
        server_salt["labels"] = server.labels
        server_salt["volumes"] = [volume.name for volume in server.volumes]

    return server_salt


def _get_formatted_bytes_string(bytes):
    """
    Return a pretty formatted unit based byte size string
    """
    # yotta (10^24) should be big enough for now
    units = ["", "k", "M", "G", "T", "P", "Z", "Y"]

    shrinked_bytes = float(bytes)
    shrink_times = 0

    while shrinked_bytes > 1000:
        shrinked_bytes /= 1000
        shrink_times += 1

    return "{0:.3f} {1}B".format(shrinked_bytes, units[shrink_times])


def _hcloud_format_image(image):
    """
    Return a formatted dict based on a Hetzner Cloud API image
    """
    formatted_image = {
        "id": image.id,
        "type": image.type,
        "name": image.name,
        "description": image.description,
        "status": image.status,
        "image_size_in_gb": image.image_size,
        "disk_size_in_gb": image.image_size,
        "created": image.created.strftime("%c"),
        "created_from": _hcloud_format_server(image.created_from),
        "bound_to": _hcloud_format_server(image.bound_to),
        "os_flavor": image.os_flavor,
        "os_version": image.os_version,
        "rapid_deploy": image.rapid_deploy,
        "protection": image.protection,
        "deprecated": image.deprecated.strftime("%c"),
        "labels": image.labels,
    }

    return formatted_image


def _hcloud_format_server_type(size):
    """
    Return a formatted dict based on a Hetzner Cloud API server type
    """
    formatted_server_type = {
        "id": size.id,
        "name": size.name,
        "desc": size.description,
        "cores": "{0} ({1})".format(size.cores, size.cpu_type),
        "memory": size.memory,
        "disk": "{0} ({1})".format(size.disk, size.storage_type),
    }

    for price in size.prices:
        formatted_server_type[price["location"]] = {
            "hourly": {
                "net": price["price_hourly"]["net"],
                "gross": price["price_hourly"]["gross"],
            },
            "monthly": {
                "net": price["price_monthly"]["net"],
                "gross": price["price_monthly"]["gross"],
            },
        }

    return formatted_server_type


def _hcloud_format_iso(iso):
    """
    Return a formatted dict based on a Hetzner Cloud API iso
    """
    formatted_iso = {
        "id": iso.id,
        "name": iso.name,
        "description": iso.description,
        "type": iso.type,
        "deprecated": None if iso.deprecated is None else iso.deprecated.strftime("%c"),
    }

    return formatted_iso


def _hcloud_format_ssh_keys(ssh_key):
    """
    Return a formatted dict based on a Hetzner Cloud API ssh key
    """
    formatted_ssh_key = {
        "id": ssh_key.id,
        "name": ssh_key.name,
        "fingerprint": ssh_key.fingerprint,
        "public_key": ssh_key.public_key,
        "labels": ssh_key.labels,
        "created": ssh_key.created.strftime("%c"),
    }

    return formatted_ssh_key


def _hcloud_format_network(network):
    """
    Return a formatted dict based on a Hetzner Cloud API network
    """

    def _format_networksubnet(networksubnet):
        formatted_networksubnet = {
            "type": networksubnet.type,
            "ip_range": networksubnet.ip_range,
            "network_zone": networksubnet.network_zone,
            "gateway": networksubnet.gateway,
        }

        return formatted_networksubnet

    def _format_networkroute(networkroute):
        formatted_networkroute = {
            "destination": networkroute.destination,
            "gateway": networkroute.gateway,
        }

        return formatted_networkroute

    formatted_network = {
        "id": network.id,
        "name": network.name,
        "ip_range": network.ip_range,
        "subnets": [
            _format_networksubnet(networksubnet) for networksubnet in network.subnets
        ],
        "routes": [
            _format_networkroute(networkroute) for networkroute in network.routes
        ],
        "servers": [
            _hcloud_format_server(server, full=False) for server in network.servers
        ],
        "protection": network.protection,
        "labels": network.labels,
    }

    return formatted_network


def _hcloud_format_floating_ip(floating_ip):
    """
    Return a formatted dict based on a Hetzner Cloud API floating ip
    """
    formatted_floating_ip = {
        "id": floating_ip.id,
        "description": floating_ip.description,
        "ip": floating_ip.ip,
        "type": floating_ip.type,
        "server": _hcloud_format_server(floating_ip.server)
        if floating_ip.server is not None
        else None,
        "dns_ptr": floating_ip.dns_ptr,
        "home_location": _hcloud_format_location(floating_ip.home_location),
        "blocked": floating_ip.blocked,
        "protection": floating_ip.protection,
        "labels": floating_ip.labels,
        "created": floating_ip.created.strftime("%c"),
        "name": floating_ip.name,
    }

    return formatted_floating_ip


def _hcloud_format_volume(volume):
    """
    Return a formatted dict based on a Hetzner Cloud API volume
    """
    formatted_volume = {
        "id": volume.id,
        "name": volume.name,
        "server": _hcloud_format_server(volume.server),
        "location": _hcloud_format_location(volume.location),
        "created": volume.created.strftime("%c"),
        "size": _get_formatted_bytes_string(volume.size * 1000 * 1000),
        "linux_device": volume.linux_device,
        "protection": volume.protection,
        "labels": volume.labels,
        "status": volume.status,
        "format": volume.format,
    }

    return formatted_volume
