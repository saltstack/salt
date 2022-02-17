"""
Vultr Cloud Module using python-vultr bindings
==============================================

.. versionadded:: 2016.3.0

The Vultr cloud module is used to control access to the Vultr VPS system.

Use of this module only requires the ``api_key`` parameter.

Set up the cloud configuration at ``/etc/salt/cloud.providers`` or
``/etc/salt/cloud.providers.d/vultr.conf``:

.. code-block:: yaml

    my-vultr-config:
      # Vultr account api key
      api_key: <supersecretapi_key>
      driver: vultr

Set up the cloud profile at ``/etc/salt/cloud.profiles`` or
``/etc/salt/cloud.profiles.d/vultr.conf``:

.. code-block:: yaml

    nyc-4gb-4cpu-ubuntu-14-04:
      location: 1
      provider: my-vultr-config
      image: 160
      size: 95
      enable_private_network: True

This driver also supports Vultr's `startup script` feature.  You can list startup
scripts in your account with

.. code-block:: bash

    salt-cloud -f list_scripts <name of vultr provider>

That list will include the IDs of the scripts in your account.  Thus, if you
have a script called 'setup-networking' with an ID of 493234 you can specify
that startup script in a profile like so:

.. code-block:: yaml

    nyc-2gb-1cpu-ubuntu-17-04:
      location: 1
      provider: my-vultr-config
      image: 223
      size: 13
      startup_script_id: 493234

Similarly you can also specify a fiewall group ID using the option firewall_group_id. You can list
firewall groups with

.. code-block:: bash

    salt-cloud -f list_firewall_groups <name of vultr provider>

To specify SSH keys to be preinstalled on the server, use the ssh_key_names setting

.. code-block:: yaml

    nyc-2gb-1cpu-ubuntu-17-04:
      location: 1
      provider: my-vultr-config
      image: 223
      size: 13
      ssh_key_names: dev1,dev2,salt-master

You can list SSH keys available on your account using

.. code-block:: bash

    salt-cloud -f list_keypairs <name of vultr provider>

:depends: requests
"""

import logging
import pprint
import time

import salt.config as config
import salt.utils.cloud
import salt.utils.files
import salt.utils.json
import salt.utils.stringutils
from salt.exceptions import SaltCloudConfigError, SaltCloudSystemExit

# Get logging started
log = logging.getLogger(__name__)

__virtualname__ = "vultr"

DETAILS = {}

try:
    import requests

    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False


def __virtual__():
    """
    Set up the Vultr functions and check for configurations
    """
    if get_configured_provider() is False:
        return False

    if get_dependencies() is False:
        return False

    return __virtualname__


def get_dependencies():
    """
    Warn if dependencies aren't met.
    """
    return config.check_driver_dependencies(__virtualname__, {"requests": HAS_REQUESTS})


def _get_active_provider_name():
    try:
        return __active_provider_name__.value()
    except AttributeError:
        return __active_provider_name__


def get_configured_provider():
    """
    Return the first configured instance
    """
    return config.is_provider_configured(
        __opts__, _get_active_provider_name() or "vultr", ("api_key",)
    )


def _cache_provider_details(conn=None):
    """
    Provide a place to hang onto results of --list-[locations|sizes|images]
    so we don't have to go out to the API and get them every time.
    """
    DETAILS["avail_locations"] = {}
    DETAILS["avail_sizes"] = {}
    DETAILS["avail_images"] = {}
    locations = avail_locations(conn)
    images = avail_images(conn)
    sizes = avail_sizes(conn)

    for key, location in locations.items():
        DETAILS["avail_locations"][location["id"]] = location
        DETAILS["avail_locations"][key] = location

    for key, image in images.items():
        DETAILS["avail_images"][image["name"]] = image
        DETAILS["avail_images"][key] = image

    for key, vm_size in sizes.items():
        DETAILS["avail_sizes"][vm_size["id"]] = vm_size
        DETAILS["avail_sizes"][key] = vm_size


def avail_locations(conn=None):
    """
    return available datacenter locations
    """
    locations = _query("regions")["regions"]
    ret = {}
    for location in locations:
        name = location["id"]
        ret[name] = location.copy()
    return ret


def avail_scripts(conn=None):
    """
    return available startup scripts
    """
    return _query("startup-scripts")["startup-scripts"]


def avail_firewall_groups(conn=None):
    """
    return available firewall groups
    """
    return _query("firewalls")["firewall_groups"]


def avail_keys(conn=None):
    """
    return available SSH keys
    """
    ret = {}
    keys = _query("ssh-keys")["ssh_keys"]
    for key in keys:
        name = key["name"]
        ret[name] = key.copy()
    return ret


def list_scripts(conn=None, call=None):
    """
    return list of Startup Scripts
    """
    return avail_scripts()


def list_firewall_groups(conn=None, call=None):
    """
    return list of firewall groups
    """
    return avail_firewall_groups()


def list_keypairs(conn=None, call=None):
    """
    return list of SSH keys
    """
    return avail_keys()


def show_keypair(kwargs=None, call=None):
    """
    return list of SSH keys
    """
    if not kwargs:
        kwargs = {}

    if "keyname" not in kwargs:
        log.error("A keyname is required.")
        return False

    keys = list_keypairs(call="function")
    keyid = keys[kwargs["keyname"]]["id"]
    log.debug("Key ID is %s", keyid)

    return keys[kwargs["keyname"]]


def avail_sizes(conn=None):
    """
    Return available sizes ("plans" in VultrSpeak)
    """
    sizes = _query("plans")["plans"]
    ret = {}
    for size in sizes:
        name = size["id"]
        ret[name] = size.copy()
    return ret


def avail_images(conn=None):
    """
    Return available images
    """
    images = _query("os")["os"]
    ret = {}
    for image in images:
        name = image["id"]
        ret[name] = image.copy()
    return ret


def list_nodes(**kwargs):
    """
    Return basic data on nodes
    """
    ret = {}

    nodes = list_nodes_full()
    for node in nodes:
        ret[node] = {}
        for prop in "id", "image", "size", "state", "private_ips", "public_ips":
            ret[node][prop] = nodes[node][prop]

    return ret


def list_nodes_full(**kwargs):
    """
    Return all data on nodes
    """

    nodes = _query("instances")
    ret = {}

    for node in nodes["instances"]:
        name = node["label"]
        ret[name] = node.copy()
        ret[name]["id"] = node["id"]
        ret[name]["image"] = node["os"]
        ret[name]["size"] = node["plan"]
        ret[name]["state"] = node["status"]
        ret[name]["private_ips"] = node["internal_ip"]
        ret[name]["public_ips"] = node["main_ip"]
    return ret


def list_nodes_select(conn=None, call=None):
    """
    Return a list of the VMs that are on the provider, with select fields
    """
    return __utils__["cloud.list_nodes_select"](
        list_nodes_full(),
        __opts__["query.selection"],
        call,
    )


def destroy(name, call=None):
    """
    Destroy a VM. Will check termination protection and warn if enabled.

    CLI Example:

    .. code-block:: bash

        salt-cloud --destroy mymachine
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

    node = show_instance(name, call="action")
    result = _query(
        "instances/{instance}".format(instance=node["id"]),
        method="DELETE",
    )

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
            name, _get_active_provider_name().split(":")[0], __opts__
        )

    return node


def stop(name, call=None):
    """
    Execute a "stop" action on a VM

    name
        The vm name

    CLI Example:

    .. code-block:: bash

        salt-cloud -a stop mymachine
    """
    if call != "action":
        raise SaltCloudSystemExit("The stop action must be called with -a or --action.")

    node = show_instance(name, call="action")

    data = {"instance_ids": [node["id"]]}
    return _query("instances/halt", method="POST", data=data)


def start(name, call=None):
    """
    Execute a "stop" action on a VM

    name
        The name of the VM to start.

    CLI Example:

    .. code-block:: bash

        salt-cloud -a start mymachine
    """
    if call != "action":
        raise SaltCloudSystemExit(
            "The start action must be called with -a or --action."
        )

    node = show_instance(name, call="action")

    return _query("instances/{vmid}/start".format(vmid=node["id"]), method="POST")


def show_instance(name, call=None):
    """
    Show the details from the provider concerning an instance
    """
    if call != "action":
        raise SaltCloudSystemExit(
            "The show_instance action must be called with -a or --action."
        )

    nodes = list_nodes_full()
    # Find under which cloud service the name is listed, if any
    if name not in nodes:
        return {}
    __utils__["cloud.cache_node"](nodes[name], _get_active_provider_name(), __opts__)
    return nodes[name]


def _lookup_vultrid(which_key, availkey, keyname):
    """
    Helper function to retrieve a Vultr ID
    """
    if DETAILS == {}:
        _cache_provider_details()

    try:
        return DETAILS[availkey][which_key][keyname]
    except KeyError:
        try:
            return DETAILS[availkey][str(which_key)][keyname]
        except KeyError:
            return False
        return False


def create(vm_):
    """
    Create a single VM from a data dict
    """
    if "driver" not in vm_:
        vm_["driver"] = vm_["provider"]

    private_networking = config.get_cloud_config_value(
        "enable_private_network",
        vm_,
        __opts__,
        search_global=False,
        default=False,
    )

    ssh_key_ids = config.get_cloud_config_value(
        "ssh_key_names", vm_, __opts__, search_global=False, default=None
    )

    startup_script = config.get_cloud_config_value(
        "startup_script_id",
        vm_,
        __opts__,
        search_global=False,
        default=None,
    )

    if startup_script and str(startup_script) not in avail_scripts():
        log.error(
            "Your Vultr account does not have a startup script with ID %s",
            str(startup_script),
        )
        return False

    firewall_group_id = config.get_cloud_config_value(
        "firewall_group_id",
        vm_,
        __opts__,
        search_global=False,
        default=None,
    )

    if firewall_group_id and str(firewall_group_id) not in avail_firewall_groups():
        log.error(
            "Your Vultr account does not have a firewall group with ID %s",
            str(firewall_group_id),
        )
        return False
    ssh_key_list = []
    if ssh_key_ids is not None:
        key_list = ssh_key_ids.split(",")
        available_keys = avail_keys()
        for key in key_list:
            if key and str(key) not in available_keys:
                log.error("Your Vultr account does not have a key with ID %s", str(key))
                return False
            ssh_key_list.append(available_keys[key]["id"])

    if private_networking is not None:
        if not isinstance(private_networking, bool):
            raise SaltCloudConfigError(
                "'private_networking' should be a boolean value."
            )
    if private_networking is True:
        enable_private_network = True
    else:
        enable_private_network = False

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

    osid = _lookup_vultrid(vm_["image"], "avail_images", "id")
    if not osid:
        log.error("Vultr does not have an image with id or name %s", vm_["image"])
        return False

    vpsplanid = _lookup_vultrid(vm_["size"], "avail_sizes", "id")
    if not vpsplanid:
        log.error("Vultr does not have a size with id or name %s", vm_["size"])
        return False

    dcid = _lookup_vultrid(vm_["location"], "avail_locations", "id")
    if not dcid:
        log.error("Vultr does not have a location with id or name %s", vm_["location"])
        return False

    kwargs = {
        "label": vm_["name"],
        "os_id": osid,
        "plan": vpsplanid,
        "region": dcid,
        "hostname": vm_["name"],
        "enable_private_network": enable_private_network,
    }
    if startup_script:
        kwargs["script_id"] = startup_script

    if firewall_group_id:
        kwargs["firewall_group_id"] = firewall_group_id

    if ssh_key_ids:
        kwargs["sshkey_id"] = ssh_key_list

    log.info("Creating Cloud VM %s", vm_["name"])

    __utils__["cloud.fire_event"](
        "event",
        "requesting instance",
        "salt/cloud/{}/requesting".format(vm_["name"]),
        args={
            "kwargs": __utils__["cloud.filter_event"](
                "requesting", kwargs, list(kwargs)
            ),
        },
        sock_dir=__opts__["sock_dir"],
        transport=__opts__["transport"],
    )

    try:
        data = _query("instances", method="post", data=kwargs)
        if int(data.get("status", "200")) >= 300:
            log.error(
                "Error creating %s on Vultr\n\nVultr API returned %s\n",
                vm_["name"],
                data,
            )
            log.error(
                "Status 412 may mean that you are requesting an\n"
                "invalid location, image, or size."
            )

            __utils__["cloud.fire_event"](
                "event",
                "instance request failed",
                "salt/cloud/{}/requesting/failed".format(vm_["name"]),
                args={"kwargs": kwargs},
                sock_dir=__opts__["sock_dir"],
                transport=__opts__["transport"],
            )
            return False
    except Exception as exc:  # pylint: disable=broad-except
        log.error(
            "Error creating %s on Vultr\n\n"
            "The following exception was thrown when trying to "
            "run the initial deployment:\n%s",
            vm_["name"],
            exc,
            # Show the traceback if the debug logging level is enabled
            exc_info_on_loglevel=logging.DEBUG,
        )
        __utils__["cloud.fire_event"](
            "event",
            "instance request failed",
            "salt/cloud/{}/requesting/failed".format(vm_["name"]),
            args={"kwargs": kwargs},
            sock_dir=__opts__["sock_dir"],
            transport=__opts__["transport"],
        )
        return False

    def wait_for_hostname():
        """
        Wait for the IP address to become available
        """
        data = show_instance(vm_["name"], call="action")
        main_ip = str(data.get("main_ip", "0"))
        if main_ip.startswith("0"):
            time.sleep(
                config.get_cloud_config_value(
                    "wait_for_ip_timout", vm_, __opts__, default=1
                )
            )
            return False
        return data["main_ip"]

    def wait_for_status():
        """
        Wait for the server to enter active state
        """
        data = show_instance(vm_["name"], call="action")
        if str(data.get("status", "")) != "active":
            time.sleep(1)
            return False
        return data["id"]

    def wait_for_server_state():
        """
        Wait for the server_state to switch to ok
        """
        data = show_instance(vm_["name"], call="action")
        kwargs = {
            "hostname": vm_["ssh_host"],
            "port": 22,
            "username": "root",
            "password_retries": 1,
            "timeout": 1,
            "display_ssh_output": False,
            "ssh_timeout": 1,
            "password": vm_["password"],
        }
        # During my testing Vultr has shown to be stuck in installingbooting state for a very long
        # time when deploying VM's.
        # Vultr tech support suggested polling if /var/lib/cloud/instance/boot-finished exists as
        # a workaround.
        # Since I'm not sure that every image is using cloud-init we only try when server_status
        # is installingbooting, and will eventually return True when state switches to ok.
        if str(data.get("server_status", "")) == "installingbooting":
            if salt.utils.cloud.wait_for_port(vm_["ssh_host"], port=22, timeout=1):
                if salt.utils.cloud.wait_for_passwd(
                    vm_["ssh_host"],
                    port=22,
                    username="root",
                    ssh_timeout=1,
                    display_ssh_output=False,
                    maxtries=1,
                ):
                    try:
                        return salt.utils.cloud.root_cmd(
                            "test -f /var/lib/cloud/instance/boot-finished",
                            tty=False,
                            sudo=False,
                            **kwargs
                        )
                    except SaltCloudSystemExit:
                        return False
            return False

        if str(data.get("server_status", "")) != "ok":
            time.sleep(1)
            return False
        return data["id"]

    vm_["ssh_host"] = salt.utils.cloud.wait_for_fun(
        wait_for_hostname,
        timeout=config.get_cloud_config_value(
            "wait_for_ip_timout", vm_, __opts__, default=15 * 60
        ),
    )

    vm_["password"] = data["instance"]["default_password"]
    salt.utils.cloud.wait_for_fun(
        wait_for_status,
        timeout=config.get_cloud_config_value(
            "wait_for_fun_timeout", vm_, __opts__, default=15 * 60
        ),
    )

    salt.utils.cloud.wait_for_fun(
        wait_for_server_state,
        timeout=config.get_cloud_config_value(
            "wait_for_fun_timeout", vm_, __opts__, default=15 * 60
        ),
    )
    __opts__["hard_timeout"] = config.get_cloud_config_value(
        "hard_timeout",
        get_configured_provider(),
        __opts__,
        search_global=False,
        default=None,
    )

    # Bootstrap
    ret = __utils__["cloud.bootstrap"](vm_, __opts__)

    ret.update(show_instance(vm_["name"], call="action"))

    log.info("Created Cloud VM '%s'", vm_["name"])
    log.debug("'%s' VM creation details:\n%s", vm_["name"], pprint.pformat(data))

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


def _query(path, method="GET", data=None):
    """
    Perform a query directly against the Vultr REST API
    """
    api_key = config.get_cloud_config_value(
        "api_key",
        get_configured_provider(),
        __opts__,
        search_global=False,
    )
    management_host = config.get_cloud_config_value(
        "management_host",
        get_configured_provider(),
        __opts__,
        search_global=False,
        default="api.vultr.com",
    )
    url = "https://{management_host}/v2/{path}".format(
        management_host=management_host,
        path=path,
    )

    data = salt.utils.json.dumps(data)
    requester = getattr(requests, method.lower())
    request = requester(
        url,
        data=data,
        headers={
            "Authorization": "Bearer " + api_key,
            "Content-Type": "application/json",
        },
    )
    if request.status_code > 299:
        raise SaltCloudSystemExit(
            "An error occurred while querying Vultr. HTTP Code: {}  "
            "Error: '{}'".format(
                request.status_code,
                # request.read()
                request.text,
            )
        )

    log.debug(request.url)

    # success without data
    if request.status_code == 204:
        return True

    content = request.text

    result = salt.utils.json.loads(content)
    if result.get("status", "").lower() == "error":
        raise SaltCloudSystemExit(pprint.pformat(result.get("error_message", {})))

    if "dict" in result:
        return result["dict"]

    return result
