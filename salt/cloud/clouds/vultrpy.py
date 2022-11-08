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

"""

import logging
import pprint
import time
import urllib.parse

import salt.config as config
from salt.exceptions import SaltCloudConfigError, SaltCloudSystemExit

# Get logging started
log = logging.getLogger(__name__)

__virtualname__ = "vultr"

DETAILS = {}


def __virtual__():
    """
    Set up the Vultr functions and check for configurations
    """
    if get_configured_provider() is False:
        return False

    return __virtualname__


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
        DETAILS["avail_locations"][location["name"]] = location
        DETAILS["avail_locations"][key] = location

    for key, image in images.items():
        DETAILS["avail_images"][image["name"]] = image
        DETAILS["avail_images"][key] = image

    for key, vm_size in sizes.items():
        DETAILS["avail_sizes"][vm_size["name"]] = vm_size
        DETAILS["avail_sizes"][key] = vm_size


def avail_locations(conn=None):
    """
    return available datacenter locations
    """
    return _query("regions/list")


def avail_scripts(conn=None):
    """
    return available startup scripts
    """
    return _query("startupscript/list")


def avail_firewall_groups(conn=None):
    """
    return available firewall groups
    """
    return _query("firewall/group_list")


def avail_keys(conn=None):
    """
    return available SSH keys
    """
    return _query("sshkey/list")


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
    keyid = keys[kwargs["keyname"]]["SSHKEYID"]
    log.debug("Key ID is %s", keyid)

    return keys[kwargs["keyname"]]


def avail_sizes(conn=None):
    """
    Return available sizes ("plans" in VultrSpeak)
    """
    return _query("plans/list")


def avail_images(conn=None):
    """
    Return available images
    """
    return _query("os/list")


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
    nodes = _query("server/list")
    ret = {}

    for node in nodes:
        name = nodes[node]["label"]
        ret[name] = nodes[node].copy()
        ret[name]["id"] = node
        ret[name]["image"] = nodes[node]["os"]
        ret[name]["size"] = nodes[node]["VPSPLANID"]
        ret[name]["state"] = nodes[node]["status"]
        ret[name]["private_ips"] = nodes[node]["internal_ip"]
        ret[name]["public_ips"] = nodes[node]["main_ip"]

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


def destroy(name):
    """
    Remove a node from Vultr
    """
    node = show_instance(name, call="action")
    params = {"SUBID": node["SUBID"]}
    result = _query(
        "server/destroy",
        method="POST",
        decode=False,
        data=urllib.parse.urlencode(params),
    )

    # The return of a destroy call is empty in the case of a success.
    # Errors are only indicated via HTTP status code. Status code 200
    # effetively therefore means "success".
    if result.get("body") == "" and result.get("text") == "":
        return True
    return result


def stop(*args, **kwargs):
    """
    Execute a "stop" action on a VM
    """
    return _query("server/halt")


def start(*args, **kwargs):
    """
    Execute a "start" action on a VM
    """
    return _query("server/start")


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

    which_key = str(which_key)
    try:
        return DETAILS[availkey][which_key][keyname]
    except KeyError:
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
    if ssh_key_ids is not None:
        key_list = ssh_key_ids.split(",")
        available_keys = avail_keys()
        for key in key_list:
            if key and str(key) not in available_keys:
                log.error("Your Vultr account does not have a key with ID %s", str(key))
                return False

    if private_networking is not None:
        if not isinstance(private_networking, bool):
            raise SaltCloudConfigError(
                "'private_networking' should be a boolean value."
            )
    if private_networking is True:
        enable_private_network = "yes"
    else:
        enable_private_network = "no"

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

    osid = _lookup_vultrid(vm_["image"], "avail_images", "OSID")
    if not osid:
        log.error("Vultr does not have an image with id or name %s", vm_["image"])
        return False

    vpsplanid = _lookup_vultrid(vm_["size"], "avail_sizes", "VPSPLANID")
    if not vpsplanid:
        log.error("Vultr does not have a size with id or name %s", vm_["size"])
        return False

    dcid = _lookup_vultrid(vm_["location"], "avail_locations", "DCID")
    if not dcid:
        log.error("Vultr does not have a location with id or name %s", vm_["location"])
        return False

    kwargs = {
        "label": vm_["name"],
        "OSID": osid,
        "VPSPLANID": vpsplanid,
        "DCID": dcid,
        "hostname": vm_["name"],
        "enable_private_network": enable_private_network,
    }
    if startup_script:
        kwargs["SCRIPTID"] = startup_script

    if firewall_group_id:
        kwargs["FIREWALLGROUPID"] = firewall_group_id

    if ssh_key_ids:
        kwargs["SSHKEYID"] = ssh_key_ids

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
        data = _query(
            "server/create", method="POST", data=urllib.parse.urlencode(kwargs)
        )
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
            time.sleep(3)
            return False
        return data["main_ip"]

    def wait_for_default_password():
        """
        Wait for the IP address to become available
        """
        data = show_instance(vm_["name"], call="action")
        # print("Waiting for default password")
        # pprint.pprint(data)
        default_password = str(data.get("default_password", ""))
        if default_password == "" or default_password == "not supported":
            time.sleep(1)
            return False
        return data["default_password"]

    def wait_for_status():
        """
        Wait for the IP address to become available
        """
        data = show_instance(vm_["name"], call="action")
        # print("Waiting for status normal")
        # pprint.pprint(data)
        if str(data.get("status", "")) != "active":
            time.sleep(1)
            return False
        return data["default_password"]

    def wait_for_server_state():
        """
        Wait for the IP address to become available
        """
        data = show_instance(vm_["name"], call="action")
        # print("Waiting for server state ok")
        # pprint.pprint(data)
        if str(data.get("server_state", "")) != "ok":
            time.sleep(1)
            return False
        return data["default_password"]

    vm_["ssh_host"] = __utils__["cloud.wait_for_fun"](
        wait_for_hostname,
        timeout=config.get_cloud_config_value(
            "wait_for_fun_timeout", vm_, __opts__, default=15 * 60
        ),
    )
    vm_["password"] = __utils__["cloud.wait_for_fun"](
        wait_for_default_password,
        timeout=config.get_cloud_config_value(
            "wait_for_fun_timeout", vm_, __opts__, default=15 * 60
        ),
    )
    __utils__["cloud.wait_for_fun"](
        wait_for_status,
        timeout=config.get_cloud_config_value(
            "wait_for_fun_timeout", vm_, __opts__, default=15 * 60
        ),
    )
    __utils__["cloud.wait_for_fun"](
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


def _query(path, method="GET", data=None, params=None, header_dict=None, decode=True):
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
    url = "https://{management_host}/v1/{path}?api_key={api_key}".format(
        management_host=management_host,
        path=path,
        api_key=api_key,
    )

    if header_dict is None:
        header_dict = {}

    result = __utils__["http.query"](
        url,
        method=method,
        params=params,
        data=data,
        header_dict=header_dict,
        port=443,
        text=True,
        decode=decode,
        decode_type="json",
        hide_fields=["api_key"],
        opts=__opts__,
    )
    if "dict" in result:
        return result["dict"]

    return result
