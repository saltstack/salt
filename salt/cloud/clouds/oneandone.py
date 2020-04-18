# -*- coding: utf-8 -*-
"""
1&1 Cloud Server Module
=======================

The 1&1 SaltStack cloud module allows a 1&1 server to be automatically deployed
and bootstrapped with Salt. It also has functions to create block storages and
ssh keys.

:depends: 1and1 >= 1.2.0

The module requires the 1&1 api_token to be provided.  The server should also
be assigned a public LAN, a private LAN, or both along with SSH key pairs.

Set up the cloud configuration at ``/etc/salt/cloud.providers`` or
``/etc/salt/cloud.providers.d/oneandone.conf``:

.. code-block:: yaml

    my-oneandone-config:
      driver: oneandone
      # The 1&1 api token
      api_token: <your-token>
      # SSH private key filename
      ssh_private_key: /path/to/private_key
      # SSH public key filename
      ssh_public_key: /path/to/public_key

.. code-block:: yaml

    my-oneandone-profile:
      provider: my-oneandone-config
      # Either provide fixed_instance_size_id or vcore, cores_per_processor, ram, and hdds.
      # Size of the ID desired for the server
      fixed_instance_size: S
      # Total amount of processors
      vcore: 2
      # Number of cores per processor
      cores_per_processor: 2
      # RAM memory size in GB
      ram: 4
      # Hard disks
      hdds:
      -
        is_main: true
        size: 20
      -
        is_main: false
        size: 20
      # ID of the appliance image that will be installed on server
      appliance_id: <ID>
      # ID of the datacenter where the server will be created
      datacenter_id: <ID>
      # Description of the server
      description: My server description
      # Password of the server. Password must contain more than 8 characters
      # using uppercase letters, numbers and other special symbols.
      password: P4$$w0rD
      # Power on server after creation - default True
      power_on: true
      # Firewall policy ID. If it is not provided, the server will assign
      # the best firewall policy, creating a new one if necessary.
      # If the parameter is sent with a 0 value, the server will be created with all ports blocked.
      firewall_policy_id: <ID>
      # IP address ID
      ip_id: <ID>
      # Load balancer ID
      load_balancer_id: <ID>
      # Monitoring policy ID
      monitoring_policy_id: <ID>

Set ``deploy`` to False if Salt should not be installed on the node.

.. code-block:: yaml

    my-oneandone-profile:
      deploy: False

Create an SSH key

.. code-block:: bash

    sudo salt-cloud -f create_ssh_key my-oneandone-config name='SaltTest' description='SaltTestDescription'

Create a block storage

.. code-block:: bash

    sudo salt-cloud -f create_block_storage my-oneandone-config name='SaltTest2'
    description='SaltTestDescription' size=50 datacenter_id='5091F6D8CBFEF9C26ACE957C652D5D49'

"""

# Import python libs
from __future__ import absolute_import, print_function, unicode_literals

import logging
import os
import pprint
import time

# Import salt libs
import salt.config as config

# Import salt.cloud libs
import salt.utils.cloud
import salt.utils.files
import salt.utils.stringutils
from salt.exceptions import (
    SaltCloudConfigError,
    SaltCloudExecutionFailure,
    SaltCloudExecutionTimeout,
    SaltCloudNotFound,
    SaltCloudSystemExit,
)
from salt.ext import six

try:
    # pylint: disable=no-name-in-module
    from oneandone.client import (
        OneAndOneService,
        Server,
        Hdd,
        BlockStorage,
        SshKey,
    )

    # pylint: enable=no-name-in-module

    HAS_ONEANDONE = True
except ImportError:
    HAS_ONEANDONE = False

# Get logging started
log = logging.getLogger(__name__)

__virtualname__ = "oneandone"


# Only load in this module if the 1&1 configurations are in place
def __virtual__():
    """
    Check for 1&1 configurations.
    """
    if get_configured_provider() is False:
        return False

    if get_dependencies() is False:
        return False

    return __virtualname__


def get_configured_provider():
    """
    Return the first configured instance.
    """
    return config.is_provider_configured(
        __opts__, __active_provider_name__ or __virtualname__, ("api_token",)
    )


def get_dependencies():
    """
    Warn if dependencies are not met.
    """
    return config.check_driver_dependencies(
        __virtualname__, {"oneandone": HAS_ONEANDONE}
    )


def get_conn():
    """
    Return a conn object for the passed VM data
    """
    return OneAndOneService(
        api_token=config.get_cloud_config_value(
            "api_token", get_configured_provider(), __opts__, search_global=False
        )
    )


def get_size(vm_):
    """
    Return the VM's size object
    """
    vm_size = config.get_cloud_config_value(
        "fixed_instance_size", vm_, __opts__, default=None, search_global=False
    )
    sizes = avail_sizes()

    if not vm_size:
        size = next((item for item in sizes if item["name"] == "S"), None)
        return size

    size = next(
        (item for item in sizes if item["name"] == vm_size or item["id"] == vm_size),
        None,
    )
    if size:
        return size

    raise SaltCloudNotFound(
        "The specified size, '{0}', could not be found.".format(vm_size)
    )


def get_image(vm_):
    """
    Return the image object to use
    """
    vm_image = config.get_cloud_config_value("image", vm_, __opts__).encode(
        "ascii", "salt-cloud-force-ascii"
    )

    images = avail_images()
    for key, value in six.iteritems(images):
        if vm_image and vm_image in (images[key]["id"], images[key]["name"]):
            return images[key]

    raise SaltCloudNotFound(
        "The specified image, '{0}', could not be found.".format(vm_image)
    )


def avail_locations(conn=None, call=None):
    """
    List available locations/datacenters for 1&1
    """
    if call == "action":
        raise SaltCloudSystemExit(
            "The avail_locations function must be called with "
            "-f or --function, or with the --list-locations option"
        )

    datacenters = []

    if not conn:
        conn = get_conn()

    for datacenter in conn.list_datacenters():
        datacenters.append({datacenter["country_code"]: datacenter})

    return {"Locations": datacenters}


def create_block_storage(kwargs=None, call=None):
    """
    Create a block storage
    """
    if call == "action":
        raise SaltCloudSystemExit(
            "The avail_locations function must be called with "
            "-f or --function, or with the --list-locations option"
        )

    conn = get_conn()

    # Assemble the composite block storage object.
    block_storage = _get_block_storage(kwargs)

    data = conn.create_block_storage(block_storage=block_storage)

    return {"BlockStorage": data}


def _get_block_storage(kwargs):
    """
    Construct a block storage instance from passed arguments
    """
    if kwargs is None:
        kwargs = {}

    block_storage_name = kwargs.get("name", None)
    block_storage_size = kwargs.get("size", None)
    block_storage_description = kwargs.get("description", None)
    datacenter_id = kwargs.get("datacenter_id", None)
    server_id = kwargs.get("server_id", None)

    block_storage = BlockStorage(name=block_storage_name, size=block_storage_size)

    if block_storage_description:
        block_storage.description = block_storage_description

    if datacenter_id:
        block_storage.datacenter_id = datacenter_id

    if server_id:
        block_storage.server_id = server_id

    return block_storage


def _get_ssh_key(kwargs):
    """
    Construct an SshKey instance from passed arguments
    """
    ssh_key_name = kwargs.get("name", None)
    ssh_key_description = kwargs.get("description", None)
    public_key = kwargs.get("public_key", None)

    return SshKey(
        name=ssh_key_name, description=ssh_key_description, public_key=public_key
    )


def create_ssh_key(kwargs=None, call=None):
    """
    Create an ssh key
    """
    if call == "action":
        raise SaltCloudSystemExit(
            "The avail_locations function must be called with "
            "-f or --function, or with the --list-locations option"
        )

    conn = get_conn()

    # Assemble the composite SshKey object.
    ssh_key = _get_ssh_key(kwargs)

    data = conn.create_ssh_key(ssh_key=ssh_key)

    return {"SshKey": data}


def avail_images(conn=None, call=None):
    """
    Return a list of the server appliances that are on the provider
    """
    if call == "action":
        raise SaltCloudSystemExit(
            "The avail_images function must be called with "
            "-f or --function, or with the --list-images option"
        )

    if not conn:
        conn = get_conn()

    ret = {}

    for appliance in conn.list_appliances():
        ret[appliance["name"]] = appliance

    return ret


def avail_sizes(call=None):
    """
    Return a dict of all available VM sizes on the cloud provider with
    relevant data.
    """
    if call == "action":
        raise SaltCloudSystemExit(
            "The avail_sizes function must be called with "
            "-f or --function, or with the --list-sizes option"
        )

    conn = get_conn()

    sizes = conn.fixed_server_flavors()

    return sizes


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


def list_nodes(conn=None, call=None):
    """
    Return a list of VMs that are on the provider
    """
    if call == "action":
        raise SaltCloudSystemExit(
            "The list_nodes function must be called with -f or --function."
        )

    if not conn:
        conn = get_conn()

    ret = {}
    nodes = conn.list_servers()

    for node in nodes:
        public_ips = []
        private_ips = []
        ret = {}

        size = node.get("hardware").get("fixed_instance_size_id", "Custom size")

        if node.get("private_networks"):
            for private_ip in node["private_networks"]:
                private_ips.append(private_ip)

        if node.get("ips"):
            for public_ip in node["ips"]:
                public_ips.append(public_ip["ip"])

        server = {
            "id": node["id"],
            "image": node["image"]["id"],
            "size": size,
            "state": node["status"]["state"],
            "private_ips": private_ips,
            "public_ips": public_ips,
        }
        ret[node["name"]] = server

    return ret


def list_nodes_full(conn=None, call=None):
    """
    Return a list of the VMs that are on the provider, with all fields
    """
    if call == "action":
        raise SaltCloudSystemExit(
            "The list_nodes_full function must be called with -f or " "--function."
        )

    if not conn:
        conn = get_conn()

    ret = {}
    nodes = conn.list_servers()

    for node in nodes:
        ret[node["name"]] = node

    return ret


def list_nodes_select(conn=None, call=None):
    """
    Return a list of the VMs that are on the provider, with select fields
    """
    if not conn:
        conn = get_conn()

    return salt.utils.cloud.list_nodes_select(
        list_nodes_full(conn, "function"), __opts__["query.selection"], call,
    )


def show_instance(name, call=None):
    """
    Show the details from the provider concerning an instance
    """
    if call != "action":
        raise SaltCloudSystemExit(
            "The show_instance action must be called with -a or --action."
        )

    nodes = list_nodes_full()
    __utils__["cloud.cache_node"](nodes[name], __active_provider_name__, __opts__)
    return nodes[name]


def _get_server(vm_):
    """
    Construct server instance from cloud profile config
    """
    description = config.get_cloud_config_value(
        "description", vm_, __opts__, default=None, search_global=False
    )

    ssh_key = load_public_key(vm_)

    vcore = None
    cores_per_processor = None
    ram = None
    fixed_instance_size_id = None

    if "fixed_instance_size" in vm_:
        fixed_instance_size = get_size(vm_)
        fixed_instance_size_id = fixed_instance_size["id"]
    elif vm_["vcore"] and vm_["cores_per_processor"] and vm_["ram"] and vm_["hdds"]:
        vcore = config.get_cloud_config_value(
            "vcore", vm_, __opts__, default=None, search_global=False
        )
        cores_per_processor = config.get_cloud_config_value(
            "cores_per_processor", vm_, __opts__, default=None, search_global=False
        )
        ram = config.get_cloud_config_value(
            "ram", vm_, __opts__, default=None, search_global=False
        )
    else:
        raise SaltCloudConfigError(
            "'fixed_instance_size' or 'vcore',"
            "'cores_per_processor', 'ram', and 'hdds'"
            "must be provided."
        )

    appliance_id = config.get_cloud_config_value(
        "appliance_id", vm_, __opts__, default=None, search_global=False
    )

    password = config.get_cloud_config_value(
        "password", vm_, __opts__, default=None, search_global=False
    )

    firewall_policy_id = config.get_cloud_config_value(
        "firewall_policy_id", vm_, __opts__, default=None, search_global=False
    )

    ip_id = config.get_cloud_config_value(
        "ip_id", vm_, __opts__, default=None, search_global=False
    )

    load_balancer_id = config.get_cloud_config_value(
        "load_balancer_id", vm_, __opts__, default=None, search_global=False
    )

    monitoring_policy_id = config.get_cloud_config_value(
        "monitoring_policy_id", vm_, __opts__, default=None, search_global=False
    )

    datacenter_id = config.get_cloud_config_value(
        "datacenter_id", vm_, __opts__, default=None, search_global=False
    )

    private_network_id = config.get_cloud_config_value(
        "private_network_id", vm_, __opts__, default=None, search_global=False
    )

    power_on = config.get_cloud_config_value(
        "power_on", vm_, __opts__, default=True, search_global=False
    )

    public_key = config.get_cloud_config_value(
        "public_key_ids", vm_, __opts__, default=True, search_global=False
    )

    # Contruct server object
    return Server(
        name=vm_["name"],
        description=description,
        fixed_instance_size_id=fixed_instance_size_id,
        vcore=vcore,
        cores_per_processor=cores_per_processor,
        ram=ram,
        appliance_id=appliance_id,
        password=password,
        power_on=power_on,
        firewall_policy_id=firewall_policy_id,
        ip_id=ip_id,
        load_balancer_id=load_balancer_id,
        monitoring_policy_id=monitoring_policy_id,
        datacenter_id=datacenter_id,
        rsa_key=ssh_key,
        private_network_id=private_network_id,
        public_key=public_key,
    )


def _get_hdds(vm_):
    """
    Construct VM hdds from cloud profile config
    """
    _hdds = config.get_cloud_config_value(
        "hdds", vm_, __opts__, default=None, search_global=False
    )

    hdds = []

    for hdd in _hdds:
        hdds.append(Hdd(size=hdd["size"], is_main=hdd["is_main"]))

    return hdds


def create(vm_):
    """
    Create a single VM from a data dict
    """
    try:
        # Check for required profile parameters before sending any API calls.
        if (
            vm_["profile"]
            and config.is_profile_configured(
                __opts__, (__active_provider_name__ or "oneandone"), vm_["profile"]
            )
            is False
        ):
            return False
    except AttributeError:
        pass

    data = None
    conn = get_conn()
    hdds = []

    # Assemble the composite server object.
    server = _get_server(vm_)

    if not bool(server.specs["hardware"]["fixed_instance_size_id"]):
        # Assemble the hdds object.
        hdds = _get_hdds(vm_)

    __utils__["cloud.fire_event"](
        "event",
        "requesting instance",
        "salt/cloud/{0}/requesting".format(vm_["name"]),
        args={"name": vm_["name"]},
        sock_dir=__opts__["sock_dir"],
        transport=__opts__["transport"],
    )

    try:
        data = conn.create_server(server=server, hdds=hdds)

        _wait_for_completion(conn, get_wait_timeout(vm_), data["id"])
    except Exception as exc:  # pylint: disable=W0703
        log.error(
            "Error creating %s on 1and1\n\n"
            "The following exception was thrown by the 1and1 library "
            "when trying to run the initial deployment: \n%s",
            vm_["name"],
            exc,
            exc_info_on_loglevel=logging.DEBUG,
        )
        return False

    vm_["server_id"] = data["id"]
    password = data["first_password"]

    def __query_node_data(vm_, data):
        """
        Query node data until node becomes available.
        """
        running = False
        try:
            data = show_instance(vm_["name"], "action")
            if not data:
                return False
            log.debug(
                "Loaded node data for %s:\nname: %s\nstate: %s",
                vm_["name"],
                pprint.pformat(data["name"]),
                data["status"]["state"],
            )
        except Exception as err:  # pylint: disable=broad-except
            log.error(
                "Failed to get nodes list: %s",
                err,
                # Show the trackback if the debug logging level is enabled
                exc_info_on_loglevel=logging.DEBUG,
            )
            # Trigger a failure in the wait for IP function
            return False

        running = data["status"]["state"].lower() == "powered_on"
        if not running:
            # Still not running, trigger another iteration
            return

        vm_["ssh_host"] = data["ips"][0]["ip"]

        return data

    try:
        data = salt.utils.cloud.wait_for_ip(
            __query_node_data,
            update_args=(vm_, data),
            timeout=config.get_cloud_config_value(
                "wait_for_ip_timeout", vm_, __opts__, default=10 * 60
            ),
            interval=config.get_cloud_config_value(
                "wait_for_ip_interval", vm_, __opts__, default=10
            ),
        )
    except (SaltCloudExecutionTimeout, SaltCloudExecutionFailure) as exc:
        try:
            # It might be already up, let's destroy it!
            destroy(vm_["name"])
        except SaltCloudSystemExit:
            pass
        finally:
            raise SaltCloudSystemExit(six.text_type(exc.message))

    log.debug("VM is now running")
    log.info("Created Cloud VM %s", vm_)
    log.debug("%s VM creation details:\n%s", vm_, pprint.pformat(data))

    __utils__["cloud.fire_event"](
        "event",
        "created instance",
        "salt/cloud/{0}/created".format(vm_["name"]),
        args={
            "name": vm_["name"],
            "profile": vm_["profile"],
            "provider": vm_["driver"],
        },
        sock_dir=__opts__["sock_dir"],
        transport=__opts__["transport"],
    )

    if "ssh_host" in vm_:
        vm_["password"] = password
        vm_["key_filename"] = get_key_filename(vm_)
        ret = __utils__["cloud.bootstrap"](vm_, __opts__)
        ret.update(data)
        return ret
    else:
        raise SaltCloudSystemExit("A valid IP address was not found.")


def destroy(name, call=None):
    """
    destroy a server by name

    :param name: name given to the server
    :param call: call value in this case is 'action'
    :return: array of booleans , true if successfully stopped and true if
             successfully removed

    CLI Example:

    .. code-block:: bash

        salt-cloud -d vm_name

    """
    if call == "function":
        raise SaltCloudSystemExit(
            "The destroy action must be called with -d, --destroy, " "-a or --action."
        )

    __utils__["cloud.fire_event"](
        "event",
        "destroying instance",
        "salt/cloud/{0}/destroying".format(name),
        args={"name": name},
        sock_dir=__opts__["sock_dir"],
        transport=__opts__["transport"],
    )

    conn = get_conn()
    node = get_node(conn, name)

    conn.delete_server(server_id=node["id"])

    __utils__["cloud.fire_event"](
        "event",
        "destroyed instance",
        "salt/cloud/{0}/destroyed".format(name),
        args={"name": name},
        sock_dir=__opts__["sock_dir"],
        transport=__opts__["transport"],
    )

    if __opts__.get("update_cachedir", False) is True:
        __utils__["cloud.delete_minion_cachedir"](
            name, __active_provider_name__.split(":")[0], __opts__
        )

    return True


def reboot(name, call=None):
    """
    reboot a server by name
    :param name: name given to the machine
    :param call: call value in this case is 'action'
    :return: true if successful

    CLI Example:

    .. code-block:: bash

        salt-cloud -a reboot vm_name
    """
    conn = get_conn()
    node = get_node(conn, name)

    conn.modify_server_status(server_id=node["id"], action="REBOOT")

    return True


def stop(name, call=None):
    """
    stop a server by name
    :param name: name given to the machine
    :param call: call value in this case is 'action'
    :return: true if successful

    CLI Example:

    .. code-block:: bash

        salt-cloud -a stop vm_name
    """
    conn = get_conn()
    node = get_node(conn, name)

    conn.stop_server(server_id=node["id"])

    return True


def start(name, call=None):
    """
    start a server by name
    :param name: name given to the machine
    :param call: call value in this case is 'action'
    :return: true if successful


    CLI Example:

    .. code-block:: bash

        salt-cloud -a start vm_name
    """
    conn = get_conn()
    node = get_node(conn, name)

    conn.start_server(server_id=node["id"])

    return True


def get_node(conn, name):
    """
    Return a node for the named VM
    """
    for node in conn.list_servers(per_page=1000):
        if node["name"] == name:
            return node


def get_key_filename(vm_):
    """
    Check SSH private key file and return absolute path if exists.
    """
    key_filename = config.get_cloud_config_value(
        "ssh_private_key", vm_, __opts__, search_global=False, default=None
    )
    if key_filename is not None:
        key_filename = os.path.expanduser(key_filename)
        if not os.path.isfile(key_filename):
            raise SaltCloudConfigError(
                "The defined ssh_private_key '{0}' does not exist".format(key_filename)
            )

        return key_filename


def load_public_key(vm_):
    """
    Load the public key file if exists.
    """
    public_key_filename = config.get_cloud_config_value(
        "ssh_public_key", vm_, __opts__, search_global=False, default=None
    )
    if public_key_filename is not None:
        public_key_filename = os.path.expanduser(public_key_filename)
        if not os.path.isfile(public_key_filename):
            raise SaltCloudConfigError(
                "The defined ssh_public_key '{0}' does not exist".format(
                    public_key_filename
                )
            )

        with salt.utils.files.fopen(public_key_filename, "r") as public_key:
            key = salt.utils.stringutils.to_unicode(public_key.read().replace("\n", ""))

            return key


def get_wait_timeout(vm_):
    """
    Return the wait_for_timeout for resource provisioning.
    """
    return config.get_cloud_config_value(
        "wait_for_timeout", vm_, __opts__, default=15 * 60, search_global=False
    )


def _wait_for_completion(conn, wait_timeout, server_id):
    """
    Poll request status until resource is provisioned.
    """
    wait_timeout = time.time() + wait_timeout
    while wait_timeout > time.time():
        time.sleep(5)

        server = conn.get_server(server_id)
        server_state = server["status"]["state"].lower()

        if server_state == "powered_on":
            return
        elif server_state == "failed":
            raise Exception("Server creation failed for {0}".format(server_id))
        elif server_state in ("active", "enabled", "deploying", "configuring"):
            continue
        else:
            raise Exception("Unknown server state {0}".format(server_state))
    raise Exception(
        "Timed out waiting for server create completion for {0}".format(server_id)
    )
