"""
A salt cloud provider that lets you use virtualbox on your machine
and act as a cloud.

:depends: vboxapi

For now this will only clone existing VMs. It's best to create a template
from which we will clone.

Followed
https://docs.saltproject.io/en/latest/topics/cloud/cloud.html#non-libcloud-based-modules
to create this.

Dicts provided by salt:
    __opts__ : contains the options used to run Salt Cloud,
        as well as a set of configuration and environment variables
"""

import logging

import salt.config as config
from salt.exceptions import SaltCloudSystemExit

try:
    import vboxapi  # pylint: disable=unused-import

    from salt.utils.virtualbox import (
        treat_machine_dict,
        vb_clone_vm,
        vb_destroy_machine,
        vb_get_machine,
        vb_list_machines,
        vb_machine_exists,
        vb_start_vm,
        vb_stop_vm,
        vb_wait_for_network_address,
    )

    HAS_VBOX = True
except ImportError:
    HAS_VBOX = False

log = logging.getLogger(__name__)

# The name salt will identify the lib by
__virtualname__ = "virtualbox"

# if no clone mode is specified in the virtualbox profile
# then default to 0 which was the old default value
DEFAULT_CLONE_MODE = 0


def __virtual__():
    """
    This function determines whether or not
    to make this cloud module available upon execution.
    Most often, it uses get_configured_provider() to determine
     if the necessary configuration has been set up.
    It may also check for necessary imports decide whether to load the module.
    In most cases, it will return a True or False value.
    If the name of the driver used does not match the filename,
     then that name should be returned instead of True.

    @return True|False|str
    """
    if not HAS_VBOX:
        return (
            False,
            "The virtualbox driver cannot be loaded: 'vboxapi' is not installed.",
        )

    if get_configured_provider() is False:
        return (
            False,
            "The virtualbox driver cannot be loaded: 'virtualbox' provider is not"
            " configured.",
        )

    # If the name of the driver used does not match the filename,
    #  then that name should be returned instead of True.
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
    configured = config.is_provider_configured(
        __opts__,
        _get_active_provider_name() or __virtualname__,
        (),  # keys we need from the provider configuration
    )
    return configured


def map_clonemode(vm_info):
    """
    Convert the virtualbox config file values for clone_mode into the integers the API requires
    """
    mode_map = {"state": 0, "child": 1, "all": 2}

    if not vm_info:
        return DEFAULT_CLONE_MODE

    if "clonemode" not in vm_info:
        return DEFAULT_CLONE_MODE

    if vm_info["clonemode"] in mode_map:
        return mode_map[vm_info["clonemode"]]
    else:
        raise SaltCloudSystemExit(
            "Illegal clonemode for virtualbox profile.  Legal values are: {}".format(
                ",".join(mode_map.keys())
            )
        )


def create(vm_info):
    """
    Creates a virtual machine from the given VM information

    This is what is used to request a virtual machine to be created by the
    cloud provider, wait for it to become available, and then (optionally) log
    in and install Salt on it.

    Events fired:

    This function fires the event ``salt/cloud/vm_name/creating``, with the
    payload containing the names of the VM, profile, and provider.

    @param vm_info

    .. code-block:: text

        {
            name: <str>
            profile: <dict>
            driver: <provider>:<profile>
            clonefrom: <vm_name>
            clonemode: <mode> (default: state, choices: state, child, all)
        }

    @type vm_info dict
    @return dict of resulting vm. !!!Passwords can and should be included!!!
    """
    try:
        # Check for required profile parameters before sending any API calls.
        if (
            vm_info["profile"]
            and config.is_profile_configured(
                __opts__,
                _get_active_provider_name() or "virtualbox",
                vm_info["profile"],
            )
            is False
        ):
            return False
    except AttributeError:
        pass

    vm_name = vm_info["name"]
    deploy = config.get_cloud_config_value(
        "deploy", vm_info, __opts__, search_global=False, default=True
    )
    wait_for_ip_timeout = config.get_cloud_config_value(
        "wait_for_ip_timeout", vm_info, __opts__, default=60
    )
    boot_timeout = config.get_cloud_config_value(
        "boot_timeout", vm_info, __opts__, default=60 * 1000
    )
    power = config.get_cloud_config_value("power_on", vm_info, __opts__, default=False)
    key_filename = config.get_cloud_config_value(
        "private_key", vm_info, __opts__, search_global=False, default=None
    )
    clone_mode = map_clonemode(vm_info)
    wait_for_pattern = (
        vm_info["waitforpattern"] if "waitforpattern" in vm_info.keys() else None
    )
    interface_index = (
        vm_info["interfaceindex"] if "interfaceindex" in vm_info.keys() else 0
    )

    log.debug("Going to fire event: starting create")
    __utils__["cloud.fire_event"](
        "event",
        "starting create",
        "salt/cloud/{}/creating".format(vm_info["name"]),
        args=__utils__["cloud.filter_event"](
            "creating", vm_info, ["name", "profile", "provider", "driver"]
        ),
        sock_dir=__opts__["sock_dir"],
        transport=__opts__["transport"],
    )

    # to create the virtual machine.
    request_kwargs = {
        "name": vm_info["name"],
        "clone_from": vm_info["clonefrom"],
        "clone_mode": clone_mode,
    }

    __utils__["cloud.fire_event"](
        "event",
        "requesting instance",
        "salt/cloud/{}/requesting".format(vm_info["name"]),
        args=__utils__["cloud.filter_event"](
            "requesting", request_kwargs, list(request_kwargs)
        ),
        sock_dir=__opts__["sock_dir"],
        transport=__opts__["transport"],
    )
    vm_result = vb_clone_vm(**request_kwargs)

    # Booting and deploying if needed
    if power:
        vb_start_vm(vm_name, timeout=boot_timeout)
        ips = vb_wait_for_network_address(
            wait_for_ip_timeout, machine_name=vm_name, wait_for_pattern=wait_for_pattern
        )

        if ips:
            ip = ips[interface_index]
            log.info("[ %s ] IPv4 is: %s", vm_name, ip)
            # ssh or smb using ip and install salt only if deploy is True
            if deploy:
                vm_info["key_filename"] = key_filename
                vm_info["ssh_host"] = ip

                res = __utils__["cloud.bootstrap"](vm_info, __opts__)
                vm_result.update(res)

    __utils__["cloud.fire_event"](
        "event",
        "created machine",
        "salt/cloud/{}/created".format(vm_info["name"]),
        args=__utils__["cloud.filter_event"]("created", vm_result, list(vm_result)),
        sock_dir=__opts__["sock_dir"],
        transport=__opts__["transport"],
    )

    # Passwords should be included in this object!!
    return vm_result


def list_nodes_full(kwargs=None, call=None):
    """
    All information available about all nodes should be returned in this function.
    The fields in the list_nodes() function should also be returned,
    even if they would not normally be provided by the cloud provider.

    This is because some functions both within Salt and 3rd party will break if an expected field is not present.
    This function is normally called with the -F option:


    .. code-block:: bash

        salt-cloud -F


    @param kwargs:
    @type kwargs:
    @param call:
    @type call:
    @return:
    @rtype:
    """
    if call == "action":
        raise SaltCloudSystemExit(
            "The list_nodes_full function must be called with -f or --function."
        )

    machines = {}

    # TODO ask for the correct attributes e.g state and private_ips
    for machine in vb_list_machines():
        name = machine.get("name")
        if name:
            machines[name] = treat_machine_dict(machine)
            del machine["name"]

    return machines


def list_nodes(kwargs=None, call=None):
    """
    This function returns a list of nodes available on this cloud provider, using the following fields:

    id (str)
    image (str)
    size (str)
    state (str)
    private_ips (list)
    public_ips (list)

    No other fields should be returned in this function, and all of these fields should be returned, even if empty.
    The private_ips and public_ips fields should always be of a list type, even if empty,
    and the other fields should always be of a str type.
    This function is normally called with the -Q option:

    .. code-block:: bash

        salt-cloud -Q


    @param kwargs:
    @type kwargs:
    @param call:
    @type call:
    @return:
    @rtype:
    """
    if call == "action":
        raise SaltCloudSystemExit(
            "The list_nodes function must be called with -f or --function."
        )

    attributes = [
        "id",
        "image",
        "size",
        "state",
        "private_ips",
        "public_ips",
    ]
    return __utils__["cloud.list_nodes_select"](
        list_nodes_full("function"),
        attributes,
        call,
    )


def list_nodes_select(call=None):
    """
    Return a list of the VMs that are on the provider, with select fields
    """
    return __utils__["cloud.list_nodes_select"](
        list_nodes_full("function"),
        __opts__["query.selection"],
        call,
    )


def destroy(name, call=None):
    """
    This function irreversibly destroys a virtual machine on the cloud provider.
    Before doing so, it should fire an event on the Salt event bus.

    The tag for this event is `salt/cloud/<vm name>/destroying`.
    Once the virtual machine has been destroyed, another event is fired.
    The tag for that event is `salt/cloud/<vm name>/destroyed`.

    Dependencies:
        list_nodes

    @param name:
    @type name: str
    @param call:
    @type call:
    @return: True if all went well, otherwise an error message
    @rtype: bool|str
    """
    log.info("Attempting to delete instance %s", name)
    if not vb_machine_exists(name):
        return f"{name} doesn't exist and can't be deleted"

    __utils__["cloud.fire_event"](
        "event",
        "destroying instance",
        f"salt/cloud/{name}/destroying",
        args={"name": name},
        sock_dir=__opts__["sock_dir"],
        transport=__opts__["transport"],
    )

    vb_destroy_machine(name)

    __utils__["cloud.fire_event"](
        "event",
        "destroyed instance",
        f"salt/cloud/{name}/destroyed",
        args={"name": name},
        sock_dir=__opts__["sock_dir"],
        transport=__opts__["transport"],
    )


def start(name, call=None):
    """
    Start a machine.
    @param name: Machine to start
    @type name: str
    @param call: Must be "action"
    @type call: str
    """
    if call != "action":
        raise SaltCloudSystemExit(
            "The instance action must be called with -a or --action."
        )

    log.info("Starting machine: %s", name)
    vb_start_vm(name)
    machine = vb_get_machine(name)
    del machine["name"]
    return treat_machine_dict(machine)


def stop(name, call=None):
    """
    Stop a running machine.
    @param name: Machine to stop
    @type name: str
    @param call: Must be "action"
    @type call: str
    """
    if call != "action":
        raise SaltCloudSystemExit(
            "The instance action must be called with -a or --action."
        )

    log.info("Stopping machine: %s", name)
    vb_stop_vm(name)
    machine = vb_get_machine(name)
    del machine["name"]
    return treat_machine_dict(machine)


def show_image(kwargs, call=None):
    """
    Show the details of an image
    """
    if call != "function":
        raise SaltCloudSystemExit(
            "The show_image action must be called with -f or --function."
        )

    name = kwargs["image"]
    log.info("Showing image %s", name)
    machine = vb_get_machine(name)

    ret = {machine["name"]: treat_machine_dict(machine)}
    del machine["name"]
    return ret
