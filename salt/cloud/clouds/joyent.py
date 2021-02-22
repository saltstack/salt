"""
Joyent Cloud Module
===================

The Joyent Cloud module is used to interact with the Joyent cloud system.

Set up the cloud configuration at ``/etc/salt/cloud.providers`` or
``/etc/salt/cloud.providers.d/joyent.conf``:

.. code-block:: yaml

    my-joyent-config:
      driver: joyent
      # The Joyent login user
      user: fred
      # The Joyent user's password
      password: saltybacon
      # The location of the ssh private key that can log into the new VM
      private_key: /root/mykey.pem
      # The name of the private key
      keyname: mykey

When creating your profiles for the joyent cloud, add the location attribute to
the profile, this will automatically get picked up when performing tasks
associated with that vm. An example profile might look like:

.. code-block:: yaml

      joyent_512:
        provider: my-joyent-config
        size: g4-highcpu-512M
        image: centos-6
        location: us-east-1

This driver can also be used with the Joyent SmartDataCenter project. More
details can be found at:

.. _`SmartDataCenter`: https://github.com/joyent/sdc

Using SDC requires that an api_host_suffix is set. The default value for this is
`.api.joyentcloud.com`. All characters, including the leading `.`, should be
included:

.. code-block:: yaml

      api_host_suffix: .api.myhostname.com

:depends: PyCrypto
"""

import base64
import datetime
import http.client
import inspect
import logging
import os
import pprint

import salt.config as config
import salt.utils.cloud
import salt.utils.files
import salt.utils.http
import salt.utils.json
import salt.utils.yaml
from salt.exceptions import (
    SaltCloudExecutionFailure,
    SaltCloudExecutionTimeout,
    SaltCloudNotFound,
    SaltCloudSystemExit,
)

try:
    from M2Crypto import EVP

    HAS_REQUIRED_CRYPTO = True
    HAS_M2 = True
except ImportError:
    HAS_M2 = False
    try:
        from Cryptodome.Hash import SHA256
        from Cryptodome.Signature import PKCS1_v1_5

        HAS_REQUIRED_CRYPTO = True
    except ImportError:
        try:
            from Crypto.Hash import SHA256
            from Crypto.Signature import PKCS1_v1_5

            HAS_REQUIRED_CRYPTO = True
        except ImportError:
            HAS_REQUIRED_CRYPTO = False


# Get logging started
log = logging.getLogger(__name__)

__virtualname__ = "joyent"

JOYENT_API_HOST_SUFFIX = ".api.joyentcloud.com"
JOYENT_API_VERSION = "~7.2"

JOYENT_LOCATIONS = {
    "us-east-1": "North Virginia, USA",
    "us-west-1": "Bay Area, California, USA",
    "us-sw-1": "Las Vegas, Nevada, USA",
    "eu-ams-1": "Amsterdam, Netherlands",
}
DEFAULT_LOCATION = "us-east-1"

# joyent no longer reports on all data centers, so setting this value to true
# causes the list_nodes function to get information on machines from all
# data centers
POLL_ALL_LOCATIONS = True

VALID_RESPONSE_CODES = [
    http.client.OK,
    http.client.ACCEPTED,
    http.client.CREATED,
    http.client.NO_CONTENT,
]


# Only load in this module if the Joyent configurations are in place
def __virtual__():
    """
    Check for Joyent configs
    """
    if HAS_REQUIRED_CRYPTO is False:
        return False, "Either PyCrypto or Cryptodome needs to be installed."
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
    Return the first configured instance.
    """
    return config.is_provider_configured(
        __opts__, _get_active_provider_name() or __virtualname__, ("user", "password")
    )


def get_image(vm_):
    """
    Return the image object to use
    """
    images = avail_images()

    vm_image = config.get_cloud_config_value("image", vm_, __opts__)

    if vm_image and str(vm_image) in images:
        images[vm_image]["name"] = images[vm_image]["id"]
        return images[vm_image]

    raise SaltCloudNotFound(
        "The specified image, '{}', could not be found.".format(vm_image)
    )


def get_size(vm_):
    """
    Return the VM's size object
    """
    sizes = avail_sizes()
    vm_size = config.get_cloud_config_value("size", vm_, __opts__)
    if not vm_size:
        raise SaltCloudNotFound("No size specified for this VM.")

    if vm_size and str(vm_size) in sizes:
        return sizes[vm_size]

    raise SaltCloudNotFound(
        "The specified size, '{}', could not be found.".format(vm_size)
    )


def query_instance(vm_=None, call=None):
    """
    Query an instance upon creation from the Joyent API
    """
    if isinstance(vm_, str) and call == "action":
        vm_ = {"name": vm_, "provider": "joyent"}

    if call == "function":
        # Technically this function may be called other ways too, but it
        # definitely cannot be called with --function.
        raise SaltCloudSystemExit(
            "The query_instance action must be called with -a or --action."
        )

    __utils__["cloud.fire_event"](
        "event",
        "querying instance",
        "salt/cloud/{}/querying".format(vm_["name"]),
        sock_dir=__opts__["sock_dir"],
        transport=__opts__["transport"],
    )

    def _query_ip_address():
        data = show_instance(vm_["name"], call="action")
        if not data:
            log.error("There was an error while querying Joyent. Empty response")
            # Trigger a failure in the wait for IP function
            return False

        if isinstance(data, dict) and "error" in data:
            log.warning("There was an error in the query %s", data.get("error"))
            # Trigger a failure in the wait for IP function
            return False

        log.debug("Returned query data: %s", data)

        if "primaryIp" in data[1]:
            # Wait for SSH to be fully configured on the remote side
            if data[1]["state"] == "running":
                return data[1]["primaryIp"]
        return None

    try:
        data = salt.utils.cloud.wait_for_ip(
            _query_ip_address,
            timeout=config.get_cloud_config_value(
                "wait_for_ip_timeout", vm_, __opts__, default=10 * 60
            ),
            interval=config.get_cloud_config_value(
                "wait_for_ip_interval", vm_, __opts__, default=10
            ),
            interval_multiplier=config.get_cloud_config_value(
                "wait_for_ip_interval_multiplier", vm_, __opts__, default=1
            ),
        )
    except (SaltCloudExecutionTimeout, SaltCloudExecutionFailure) as exc:
        try:
            # destroy(vm_['name'])
            pass
        except SaltCloudSystemExit:
            pass
        finally:
            raise SaltCloudSystemExit(str(exc))

    return data


def create(vm_):
    """
    Create a single VM from a data dict

    CLI Example:

    .. code-block:: bash

        salt-cloud -p profile_name vm_name
    """
    try:
        # Check for required profile parameters before sending any API calls.
        if (
            vm_["profile"]
            and config.is_profile_configured(
                __opts__,
                _get_active_provider_name() or "joyent",
                vm_["profile"],
                vm_=vm_,
            )
            is False
        ):
            return False
    except AttributeError:
        pass

    key_filename = config.get_cloud_config_value(
        "private_key", vm_, __opts__, search_global=False, default=None
    )

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

    log.info(
        "Creating Cloud VM %s in %s", vm_["name"], vm_.get("location", DEFAULT_LOCATION)
    )

    # added . for fqdn hostnames
    salt.utils.cloud.check_name(vm_["name"], "a-zA-Z0-9-.")
    kwargs = {
        "name": vm_["name"],
        "image": get_image(vm_),
        "size": get_size(vm_),
        "location": vm_.get("location", DEFAULT_LOCATION),
    }
    # Let's not assign a default here; only assign a network value if
    # one is explicitly configured
    if "networks" in vm_:
        kwargs["networks"] = vm_.get("networks")

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

    data = create_node(**kwargs)
    if data == {}:
        log.error("Error creating %s on JOYENT", vm_["name"])
        return False

    query_instance(vm_)
    data = show_instance(vm_["name"], call="action")

    vm_["key_filename"] = key_filename
    vm_["ssh_host"] = data[1]["primaryIp"]

    __utils__["cloud.bootstrap"](vm_, __opts__)

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

    return data[1]


def create_node(**kwargs):
    """
    convenience function to make the rest api call for node creation.
    """
    name = kwargs["name"]
    size = kwargs["size"]
    image = kwargs["image"]
    location = kwargs["location"]
    networks = kwargs.get("networks")
    tag = kwargs.get("tag")
    locality = kwargs.get("locality")
    metadata = kwargs.get("metadata")
    firewall_enabled = kwargs.get("firewall_enabled")

    create_data = {
        "name": name,
        "package": size["name"],
        "image": image["name"],
    }
    if networks is not None:
        create_data["networks"] = networks

    if locality is not None:
        create_data["locality"] = locality

    if metadata is not None:
        for key, value in metadata.items():
            create_data["metadata.{}".format(key)] = value

    if tag is not None:
        for key, value in tag.items():
            create_data["tag.{}".format(key)] = value

    if firewall_enabled is not None:
        create_data["firewall_enabled"] = firewall_enabled

    data = salt.utils.json.dumps(create_data)

    ret = query(command="my/machines", data=data, method="POST", location=location)
    if ret[0] in VALID_RESPONSE_CODES:
        return ret[1]
    else:
        log.error("Failed to create node %s: %s", name, ret[1])

    return {}


def destroy(name, call=None):
    """
    destroy a machine by name

    :param name: name given to the machine
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
        "salt/cloud/{}/destroying".format(name),
        args={"name": name},
        sock_dir=__opts__["sock_dir"],
        transport=__opts__["transport"],
    )

    node = get_node(name)
    ret = query(
        command="my/machines/{}".format(node["id"]),
        location=node["location"],
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

    return ret[0] in VALID_RESPONSE_CODES


def reboot(name, call=None):
    """
    reboot a machine by name
    :param name: name given to the machine
    :param call: call value in this case is 'action'
    :return: true if successful

    CLI Example:

    .. code-block:: bash

        salt-cloud -a reboot vm_name
    """
    node = get_node(name)
    ret = take_action(
        name=name,
        call=call,
        method="POST",
        command="my/machines/{}".format(node["id"]),
        location=node["location"],
        data={"action": "reboot"},
    )
    return ret[0] in VALID_RESPONSE_CODES


def stop(name, call=None):
    """
    stop a machine by name
    :param name: name given to the machine
    :param call: call value in this case is 'action'
    :return: true if successful

    CLI Example:

    .. code-block:: bash

        salt-cloud -a stop vm_name
    """
    node = get_node(name)
    ret = take_action(
        name=name,
        call=call,
        method="POST",
        command="my/machines/{}".format(node["id"]),
        location=node["location"],
        data={"action": "stop"},
    )
    return ret[0] in VALID_RESPONSE_CODES


def start(name, call=None):
    """
    start a machine by name
    :param name: name given to the machine
    :param call: call value in this case is 'action'
    :return: true if successful


    CLI Example:

    .. code-block:: bash

        salt-cloud -a start vm_name
    """
    node = get_node(name)
    ret = take_action(
        name=name,
        call=call,
        method="POST",
        command="my/machines/{}".format(node["id"]),
        location=node["location"],
        data={"action": "start"},
    )
    return ret[0] in VALID_RESPONSE_CODES


def take_action(
    name=None,
    call=None,
    command=None,
    data=None,
    method="GET",
    location=DEFAULT_LOCATION,
):

    """
    take action call used by start,stop, reboot
    :param name: name given to the machine
    :param call: call value in this case is 'action'
    :command: api path
    :data: any data to be passed to the api, must be in json format
    :method: GET,POST,or DELETE
    :location: data center to execute the command on
    :return: true if successful
    """
    caller = inspect.stack()[1][3]

    if call != "action":
        raise SaltCloudSystemExit("This action must be called with -a or --action.")

    if data:
        data = salt.utils.json.dumps(data)

    ret = []
    try:

        ret = query(command=command, data=data, method=method, location=location)
        log.info("Success %s for node %s", caller, name)
    except Exception as exc:  # pylint: disable=broad-except
        if "InvalidState" in str(exc):
            ret = [200, {}]
        else:
            log.error(
                "Failed to invoke %s node %s: %s",
                caller,
                name,
                exc,
                # Show the traceback if the debug logging level is enabled
                exc_info_on_loglevel=logging.DEBUG,
            )
            ret = [100, {}]

    return ret


def ssh_interface(vm_):
    """
    Return the ssh_interface type to connect to. Either 'public_ips' (default)
    or 'private_ips'.
    """
    return config.get_cloud_config_value(
        "ssh_interface", vm_, __opts__, default="public_ips", search_global=False
    )


def get_location(vm_=None):
    """
    Return the joyent data center to use, in this order:
        - CLI parameter
        - VM parameter
        - Cloud profile setting
    """
    return __opts__.get(
        "location",
        config.get_cloud_config_value(
            "location",
            vm_ or get_configured_provider(),
            __opts__,
            default=DEFAULT_LOCATION,
            search_global=False,
        ),
    )


def avail_locations(call=None):
    """
    List all available locations
    """
    if call == "action":
        raise SaltCloudSystemExit(
            "The avail_locations function must be called with "
            "-f or --function, or with the --list-locations option"
        )

    ret = {}
    for key in JOYENT_LOCATIONS:
        ret[key] = {"name": key, "region": JOYENT_LOCATIONS[key]}

    # this can be enabled when the bug in the joyent get data centers call is
    # corrected, currently only the European dc (new api) returns the correct
    # values
    # ret = {}
    # rcode, datacenters = query(
    #     command='my/datacenters', location=DEFAULT_LOCATION, method='GET'
    # )
    # if rcode in VALID_RESPONSE_CODES and isinstance(datacenters, dict):
    #     for key in datacenters:
    #     ret[key] = {
    #         'name': key,
    #         'url': datacenters[key]
    #     }
    return ret


def has_method(obj, method_name):
    """
    Find if the provided object has a specific method
    """
    if method_name in dir(obj):
        return True

    log.error("Method '%s' not yet supported!", method_name)
    return False


def key_list(items=None):
    """
    convert list to dictionary using the key as the identifier
    :param items: array to iterate over
    :return: dictionary
    """
    if items is None:
        items = []

    ret = {}
    if items and isinstance(items, list):
        for item in items:
            if "name" in item:
                # added for consistency with old code
                if "id" not in item:
                    item["id"] = item["name"]
                ret[item["name"]] = item
    return ret


def get_node(name):
    """
    gets the node from the full node list by name
    :param name: name of the vm
    :return: node object
    """
    nodes = list_nodes()
    if name in nodes:
        return nodes[name]
    return None


def show_instance(name, call=None):
    """
    get details about a machine
    :param name: name given to the machine
    :param call: call value in this case is 'action'
    :return: machine information

    CLI Example:

    .. code-block:: bash

        salt-cloud -a show_instance vm_name
    """
    node = get_node(name)
    ret = query(
        command="my/machines/{}".format(node["id"]),
        location=node["location"],
        method="GET",
    )

    return ret


def _old_libcloud_node_state(id_):
    """
    Libcloud supported node states
    """
    states_int = {
        0: "RUNNING",
        1: "REBOOTING",
        2: "TERMINATED",
        3: "PENDING",
        4: "UNKNOWN",
        5: "STOPPED",
        6: "SUSPENDED",
        7: "ERROR",
        8: "PAUSED",
    }
    states_str = {
        "running": "RUNNING",
        "rebooting": "REBOOTING",
        "starting": "STARTING",
        "terminated": "TERMINATED",
        "pending": "PENDING",
        "unknown": "UNKNOWN",
        "stopping": "STOPPING",
        "stopped": "STOPPED",
        "suspended": "SUSPENDED",
        "error": "ERROR",
        "paused": "PAUSED",
        "reconfiguring": "RECONFIGURING",
    }
    return states_str[id_] if isinstance(id_, str) else states_int[id_]


def joyent_node_state(id_):
    """
    Convert joyent returned state to state common to other data center return
    values for consistency

    :param id_: joyent state value
    :return: state value
    """
    states = {
        "running": 0,
        "stopped": 2,
        "stopping": 2,
        "provisioning": 3,
        "deleted": 2,
        "unknown": 4,
    }

    if id_ not in states:
        id_ = "unknown"

    return _old_libcloud_node_state(states[id_])


def reformat_node(item=None, full=False):
    """
    Reformat the returned data from joyent, determine public/private IPs and
    strip out fields if necessary to provide either full or brief content.

    :param item: node dictionary
    :param full: full or brief output
    :return: dict
    """
    desired_keys = [
        "id",
        "name",
        "state",
        "public_ips",
        "private_ips",
        "size",
        "image",
        "location",
    ]
    item["private_ips"] = []
    item["public_ips"] = []
    if "ips" in item:
        for ip in item["ips"]:
            if salt.utils.cloud.is_public_ip(ip):
                item["public_ips"].append(ip)
            else:
                item["private_ips"].append(ip)

    # add any undefined desired keys
    for key in desired_keys:
        if key not in item:
            item[key] = None

    # remove all the extra key value pairs to provide a brief listing
    to_del = []
    if not full:
        for key in item.keys():  # iterate over a copy of the keys
            if key not in desired_keys:
                to_del.append(key)

    for key in to_del:
        del item[key]

    if "state" in item:
        item["state"] = joyent_node_state(item["state"])

    return item


def list_nodes(full=False, call=None):
    """
    list of nodes, keeping only a brief listing

    CLI Example:

    .. code-block:: bash

        salt-cloud -Q
    """
    if call == "action":
        raise SaltCloudSystemExit(
            "The list_nodes function must be called with -f or --function."
        )

    ret = {}
    if POLL_ALL_LOCATIONS:
        for location in JOYENT_LOCATIONS:
            result = query(command="my/machines", location=location, method="GET")
            if result[0] in VALID_RESPONSE_CODES:
                nodes = result[1]
                for node in nodes:
                    if "name" in node:
                        node["location"] = location
                        ret[node["name"]] = reformat_node(item=node, full=full)
            else:
                log.error("Invalid response when listing Joyent nodes: %s", result[1])

    else:
        location = get_location()
        result = query(command="my/machines", location=location, method="GET")
        nodes = result[1]
        for node in nodes:
            if "name" in node:
                node["location"] = location
                ret[node["name"]] = reformat_node(item=node, full=full)
    return ret


def list_nodes_full(call=None):
    """
    list of nodes, maintaining all content provided from joyent listings

    CLI Example:

    .. code-block:: bash

        salt-cloud -F
    """
    if call == "action":
        raise SaltCloudSystemExit(
            "The list_nodes_full function must be called with -f or --function."
        )

    return list_nodes(full=True)


def list_nodes_select(call=None):
    """
    Return a list of the VMs that are on the provider, with select fields
    """
    return salt.utils.cloud.list_nodes_select(
        list_nodes_full("function"), __opts__["query.selection"], call,
    )


def _get_proto():
    """
    Checks configuration to see whether the user has SSL turned on. Default is:

    .. code-block:: yaml

        use_ssl: True
    """
    use_ssl = config.get_cloud_config_value(
        "use_ssl",
        get_configured_provider(),
        __opts__,
        search_global=False,
        default=True,
    )
    if use_ssl is True:
        return "https"
    return "http"


def avail_images(call=None):
    """
    Get list of available images

    CLI Example:

    .. code-block:: bash

        salt-cloud --list-images

    Can use a custom URL for images. Default is:

    .. code-block:: yaml

        image_url: images.joyent.com/images
    """
    if call == "action":
        raise SaltCloudSystemExit(
            "The avail_images function must be called with "
            "-f or --function, or with the --list-images option"
        )

    user = config.get_cloud_config_value(
        "user", get_configured_provider(), __opts__, search_global=False
    )

    img_url = config.get_cloud_config_value(
        "image_url",
        get_configured_provider(),
        __opts__,
        search_global=False,
        default="{}{}/{}/images".format(DEFAULT_LOCATION, JOYENT_API_HOST_SUFFIX, user),
    )

    if not img_url.startswith("http://") and not img_url.startswith("https://"):
        img_url = "{}://{}".format(_get_proto(), img_url)

    rcode, data = query(command="my/images", method="GET")
    log.debug(data)

    ret = {}
    for image in data:
        ret[image["name"]] = image
    return ret


def avail_sizes(call=None):
    """
    get list of available packages

    CLI Example:

    .. code-block:: bash

        salt-cloud --list-sizes
    """
    if call == "action":
        raise SaltCloudSystemExit(
            "The avail_sizes function must be called with "
            "-f or --function, or with the --list-sizes option"
        )

    rcode, items = query(command="my/packages")
    if rcode not in VALID_RESPONSE_CODES:
        return {}
    return key_list(items=items)


def list_keys(kwargs=None, call=None):
    """
    List the keys available
    """
    if call != "function":
        log.error("The list_keys function must be called with -f or --function.")
        return False

    if not kwargs:
        kwargs = {}

    ret = {}
    rcode, data = query(command="my/keys", method="GET")
    for pair in data:
        ret[pair["name"]] = pair["key"]
    return {"keys": ret}


def show_key(kwargs=None, call=None):
    """
    List the keys available
    """
    if call != "function":
        log.error("The list_keys function must be called with -f or --function.")
        return False

    if not kwargs:
        kwargs = {}

    if "keyname" not in kwargs:
        log.error("A keyname is required.")
        return False

    rcode, data = query(command="my/keys/{}".format(kwargs["keyname"]), method="GET",)
    return {"keys": {data["name"]: data["key"]}}


def import_key(kwargs=None, call=None):
    """
    List the keys available

    CLI Example:

    .. code-block:: bash

        salt-cloud -f import_key joyent keyname=mykey keyfile=/tmp/mykey.pub
    """
    if call != "function":
        log.error("The import_key function must be called with -f or --function.")
        return False

    if not kwargs:
        kwargs = {}

    if "keyname" not in kwargs:
        log.error("A keyname is required.")
        return False

    if "keyfile" not in kwargs:
        log.error("The location of the SSH keyfile is required.")
        return False

    if not os.path.isfile(kwargs["keyfile"]):
        log.error("The specified keyfile (%s) does not exist.", kwargs["keyfile"])
        return False

    with salt.utils.files.fopen(kwargs["keyfile"], "r") as fp_:
        kwargs["key"] = salt.utils.stringutils.to_unicode(fp_.read())

    send_data = {"name": kwargs["keyname"], "key": kwargs["key"]}
    kwargs["data"] = salt.utils.json.dumps(send_data)

    rcode, data = query(command="my/keys", method="POST", data=kwargs["data"],)
    log.debug(pprint.pformat(data))
    return {"keys": {data["name"]: data["key"]}}


def delete_key(kwargs=None, call=None):
    """
    List the keys available

    CLI Example:

    .. code-block:: bash

        salt-cloud -f delete_key joyent keyname=mykey
    """
    if call != "function":
        log.error("The delete_keys function must be called with -f or --function.")
        return False

    if not kwargs:
        kwargs = {}

    if "keyname" not in kwargs:
        log.error("A keyname is required.")
        return False

    rcode, data = query(
        command="my/keys/{}".format(kwargs["keyname"]), method="DELETE",
    )
    return data


def get_location_path(
    location=DEFAULT_LOCATION, api_host_suffix=JOYENT_API_HOST_SUFFIX
):
    """
    create url from location variable
    :param location: joyent data center location
    :return: url
    """
    return "{}://{}{}".format(_get_proto(), location, api_host_suffix)


def query(action=None, command=None, args=None, method="GET", location=None, data=None):
    """
    Make a web call to Joyent
    """
    user = config.get_cloud_config_value(
        "user", get_configured_provider(), __opts__, search_global=False
    )

    if not user:
        log.error(
            "username is required for Joyent API requests. Please set one in your provider configuration"
        )

    password = config.get_cloud_config_value(
        "password", get_configured_provider(), __opts__, search_global=False
    )

    verify_ssl = config.get_cloud_config_value(
        "verify_ssl",
        get_configured_provider(),
        __opts__,
        search_global=False,
        default=True,
    )

    ssh_keyfile = config.get_cloud_config_value(
        "private_key",
        get_configured_provider(),
        __opts__,
        search_global=False,
        default=True,
    )

    if not ssh_keyfile:
        log.error(
            "ssh_keyfile is required for Joyent API requests.  Please set one in your provider configuration"
        )

    ssh_keyname = config.get_cloud_config_value(
        "keyname",
        get_configured_provider(),
        __opts__,
        search_global=False,
        default=True,
    )

    if not ssh_keyname:
        log.error(
            "ssh_keyname is required for Joyent API requests.  Please set one in your provider configuration"
        )

    if not location:
        location = get_location()

    api_host_suffix = config.get_cloud_config_value(
        "api_host_suffix",
        get_configured_provider(),
        __opts__,
        search_global=False,
        default=JOYENT_API_HOST_SUFFIX,
    )

    path = get_location_path(location=location, api_host_suffix=api_host_suffix)

    if action:
        path += action

    if command:
        path += "/{}".format(command)

    log.debug("User: '%s' on PATH: %s", user, path)

    if (not user) or (not ssh_keyfile) or (not ssh_keyname) or (not location):
        return None

    timenow = datetime.datetime.utcnow()
    timestamp = timenow.strftime("%a, %d %b %Y %H:%M:%S %Z").strip()
    rsa_key = salt.crypt.get_rsa_key(ssh_keyfile, None)
    if HAS_M2:
        md = EVP.MessageDigest("sha256")
        md.update(timestamp.encode(__salt_system_encoding__))
        digest = md.final()
        signed = rsa_key.sign(digest, algo="sha256")
    else:
        rsa_ = PKCS1_v1_5.new(rsa_key)
        hash_ = SHA256.new()
        hash_.update(timestamp.encode(__salt_system_encoding__))
        signed = rsa_.sign(hash_)
    signed = base64.b64encode(signed)
    user_arr = user.split("/")
    if len(user_arr) == 1:
        keyid = "/{}/keys/{}".format(user_arr[0], ssh_keyname)
    elif len(user_arr) == 2:
        keyid = "/{}/users/{}/keys/{}".format(user_arr[0], user_arr[1], ssh_keyname)
    else:
        log.error("Malformed user string")

    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "X-Api-Version": JOYENT_API_VERSION,
        "Date": timestamp,
        "Authorization": 'Signature keyId="{}",algorithm="rsa-sha256" {}'.format(
            keyid, signed.decode(__salt_system_encoding__)
        ),
    }

    if not isinstance(args, dict):
        args = {}

    # post form data
    if not data:
        data = salt.utils.json.dumps({})

    return_content = None
    result = salt.utils.http.query(
        path,
        method,
        params=args,
        header_dict=headers,
        data=data,
        decode=False,
        text=True,
        status=True,
        headers=True,
        verify_ssl=verify_ssl,
        opts=__opts__,
    )
    log.debug("Joyent Response Status Code: %s", result["status"])
    if "headers" not in result:
        return [result["status"], result["error"]]

    if "Content-Length" in result["headers"]:
        content = result["text"]
        return_content = salt.utils.yaml.safe_load(content)

    return [result["status"], return_content]
