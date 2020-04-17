# -*- coding: utf-8 -*-
"""
Parallels Cloud Module
======================

The Parallels cloud module is used to control access to cloud providers using
the Parallels VPS system.

Set up the cloud configuration at ``/etc/salt/cloud.providers`` or
 ``/etc/salt/cloud.providers.d/parallels.conf``:

.. code-block:: yaml

    my-parallels-config:
      # Parallels account information
      user: myuser
      password: mypassword
      url: https://api.cloud.xmission.com:4465/paci/v1.0/
      driver: parallels

"""

# Import python libs
from __future__ import absolute_import, print_function, unicode_literals

import logging
import pprint
import time

import salt.config as config

# Import salt cloud libs
import salt.utils.cloud

# Import Salt libs
from salt._compat import ElementTree as ET
from salt.exceptions import (
    SaltCloudExecutionFailure,
    SaltCloudExecutionTimeout,
    SaltCloudNotFound,
    SaltCloudSystemExit,
)

# Import 3rd-party libs
from salt.ext import six

# pylint: disable=import-error,no-name-in-module
from salt.ext.six.moves.urllib.error import URLError
from salt.ext.six.moves.urllib.parse import urlencode as _urlencode
from salt.ext.six.moves.urllib.request import (
    HTTPBasicAuthHandler as _HTTPBasicAuthHandler,
)
from salt.ext.six.moves.urllib.request import Request as _Request
from salt.ext.six.moves.urllib.request import build_opener as _build_opener
from salt.ext.six.moves.urllib.request import install_opener as _install_opener
from salt.ext.six.moves.urllib.request import urlopen as _urlopen

# pylint: enable=import-error,no-name-in-module


# Get logging started
log = logging.getLogger(__name__)

__virtualname__ = "parallels"


# Only load in this module if the PARALLELS configurations are in place
def __virtual__():
    """
    Check for PARALLELS configurations
    """
    if get_configured_provider() is False:
        return False

    return __virtualname__


def get_configured_provider():
    """
    Return the first configured instance.
    """
    return config.is_provider_configured(
        __opts__,
        __active_provider_name__ or __virtualname__,
        ("user", "password", "url",),
    )


def avail_images(call=None):
    """
    Return a list of the images that are on the provider
    """
    if call == "action":
        raise SaltCloudSystemExit(
            "The avail_images function must be called with "
            "-f or --function, or with the --list-images option"
        )

    items = query(action="template")
    ret = {}
    for item in items:
        ret[item.attrib["name"]] = item.attrib

    return ret


def list_nodes(call=None):
    """
    Return a list of the VMs that are on the provider
    """
    if call == "action":
        raise SaltCloudSystemExit(
            "The list_nodes function must be called with -f or --function."
        )

    ret = {}
    items = query(action="ve")

    for item in items:
        name = item.attrib["name"]
        node = show_instance(name, call="action")

        ret[name] = {
            "id": node["id"],
            "image": node["platform"]["template-info"]["name"],
            "state": node["state"],
        }
        if "private-ip" in node["network"]:
            ret[name]["private_ips"] = [node["network"]["private-ip"]]
        if "public-ip" in node["network"]:
            ret[name]["public_ips"] = [node["network"]["public-ip"]]

    return ret


def list_nodes_full(call=None):
    """
    Return a list of the VMs that are on the provider
    """
    if call == "action":
        raise SaltCloudSystemExit(
            "The list_nodes_full function must be called with -f or --function."
        )

    ret = {}
    items = query(action="ve")

    for item in items:
        name = item.attrib["name"]
        node = show_instance(name, call="action")

        ret[name] = node
        ret[name]["image"] = node["platform"]["template-info"]["name"]
        if "private-ip" in node["network"]:
            ret[name]["private_ips"] = [node["network"]["private-ip"]["address"]]
        if "public-ip" in node["network"]:
            ret[name]["public_ips"] = [node["network"]["public-ip"]["address"]]

    return ret


def list_nodes_select(call=None):
    """
    Return a list of the VMs that are on the provider, with select fields
    """
    return salt.utils.cloud.list_nodes_select(
        list_nodes_full(), __opts__["query.selection"], call,
    )


def get_image(vm_):
    """
    Return the image object to use
    """
    images = avail_images()
    vm_image = config.get_cloud_config_value(
        "image", vm_, __opts__, search_global=False
    )
    for image in images:
        if six.text_type(vm_image) in (images[image]["name"], images[image]["id"]):
            return images[image]["id"]
    raise SaltCloudNotFound("The specified image could not be found.")


def create_node(vm_):
    """
    Build and submit the XML to create a node
    """
    # Start the tree
    content = ET.Element("ve")

    # Name of the instance
    name = ET.SubElement(content, "name")
    name.text = vm_["name"]

    # Description, defaults to name
    desc = ET.SubElement(content, "description")
    desc.text = config.get_cloud_config_value(
        "desc", vm_, __opts__, default=vm_["name"], search_global=False
    )

    # How many CPU cores, and how fast they are
    cpu = ET.SubElement(content, "cpu")
    cpu.attrib["number"] = config.get_cloud_config_value(
        "cpu_number", vm_, __opts__, default="1", search_global=False
    )
    cpu.attrib["power"] = config.get_cloud_config_value(
        "cpu_power", vm_, __opts__, default="1000", search_global=False
    )

    # How many megabytes of RAM
    ram = ET.SubElement(content, "ram-size")
    ram.text = config.get_cloud_config_value(
        "ram", vm_, __opts__, default="256", search_global=False
    )

    # Bandwidth available, in kbps
    bandwidth = ET.SubElement(content, "bandwidth")
    bandwidth.text = config.get_cloud_config_value(
        "bandwidth", vm_, __opts__, default="100", search_global=False
    )

    # How many public IPs will be assigned to this instance
    ip_num = ET.SubElement(content, "no-of-public-ip")
    ip_num.text = config.get_cloud_config_value(
        "ip_num", vm_, __opts__, default="1", search_global=False
    )

    # Size of the instance disk
    disk = ET.SubElement(content, "ve-disk")
    disk.attrib["local"] = "true"
    disk.attrib["size"] = config.get_cloud_config_value(
        "disk_size", vm_, __opts__, default="10", search_global=False
    )

    # Attributes for the image
    vm_image = config.get_cloud_config_value(
        "image", vm_, __opts__, search_global=False
    )
    image = show_image({"image": vm_image}, call="function")
    platform = ET.SubElement(content, "platform")
    template = ET.SubElement(platform, "template-info")
    template.attrib["name"] = vm_image
    os_info = ET.SubElement(platform, "os-info")
    os_info.attrib["technology"] = image[vm_image]["technology"]
    os_info.attrib["type"] = image[vm_image]["osType"]

    # Username and password
    admin = ET.SubElement(content, "admin")
    admin.attrib["login"] = config.get_cloud_config_value(
        "ssh_username", vm_, __opts__, default="root"
    )
    admin.attrib["password"] = config.get_cloud_config_value(
        "password", vm_, __opts__, search_global=False
    )

    data = ET.tostring(content, encoding="UTF-8")

    __utils__["cloud.fire_event"](
        "event",
        "requesting instance",
        "salt/cloud/{0}/requesting".format(vm_["name"]),
        args={
            "kwargs": __utils__["cloud.filter_event"]("requesting", data, list(data)),
        },
        sock_dir=__opts__["sock_dir"],
        transport=__opts__["transport"],
    )

    node = query(action="ve", method="POST", data=data)
    return node


def create(vm_):
    """
    Create a single VM from a data dict
    """
    try:
        # Check for required profile parameters before sending any API calls.
        if (
            vm_["profile"]
            and config.is_profile_configured(
                __opts__,
                __active_provider_name__ or "parallels",
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
        "salt/cloud/{0}/creating".format(vm_["name"]),
        args=__utils__["cloud.filter_event"](
            "creating", vm_, ["name", "profile", "provider", "driver"]
        ),
        sock_dir=__opts__["sock_dir"],
        transport=__opts__["transport"],
    )

    log.info("Creating Cloud VM %s", vm_["name"])

    try:
        data = create_node(vm_)
    except Exception as exc:  # pylint: disable=broad-except
        log.error(
            "Error creating %s on PARALLELS\n\n"
            "The following exception was thrown when trying to "
            "run the initial deployment: \n%s",
            vm_["name"],
            exc,
            # Show the traceback if the debug logging level is enabled
            exc_info_on_loglevel=logging.DEBUG,
        )
        return False

    name = vm_["name"]
    if not wait_until(name, "CREATED"):
        return {"Error": "Unable to start {0}, command timed out".format(name)}
    start(vm_["name"], call="action")

    if not wait_until(name, "STARTED"):
        return {"Error": "Unable to start {0}, command timed out".format(name)}

    def __query_node_data(vm_name):
        data = show_instance(vm_name, call="action")
        if "public-ip" not in data["network"]:
            # Trigger another iteration
            return
        return data

    try:
        data = salt.utils.cloud.wait_for_ip(
            __query_node_data,
            update_args=(vm_["name"],),
            timeout=config.get_cloud_config_value(
                "wait_for_ip_timeout", vm_, __opts__, default=5 * 60
            ),
            interval=config.get_cloud_config_value(
                "wait_for_ip_interval", vm_, __opts__, default=5
            ),
        )
    except (SaltCloudExecutionTimeout, SaltCloudExecutionFailure) as exc:
        try:
            # It might be already up, let's destroy it!
            destroy(vm_["name"])
        except SaltCloudSystemExit:
            pass
        finally:
            raise SaltCloudSystemExit(six.text_type(exc))

    comps = data["network"]["public-ip"]["address"].split("/")
    public_ip = comps[0]

    vm_["ssh_host"] = public_ip
    ret = __utils__["cloud.bootstrap"](vm_, __opts__)

    log.info("Created Cloud VM '%s'", vm_["name"])
    log.debug("'%s' VM creation details:\n%s", vm_["name"], pprint.pformat(data))

    __utils__["cloud.fire_event"](
        "event",
        "created instance",
        "salt/cloud/{0}/created".format(vm_["name"]),
        args=__utils__["cloud.filter_event"](
            "created", vm_, ["name", "profile", "provider", "driver"]
        ),
        sock_dir=__opts__["sock_dir"],
        transport=__opts__["transport"],
    )

    return data


def query(action=None, command=None, args=None, method="GET", data=None):
    """
    Make a web call to a Parallels provider
    """
    path = config.get_cloud_config_value(
        "url", get_configured_provider(), __opts__, search_global=False
    )
    auth_handler = _HTTPBasicAuthHandler()
    auth_handler.add_password(
        realm="Parallels Instance Manager",
        uri=path,
        user=config.get_cloud_config_value(
            "user", get_configured_provider(), __opts__, search_global=False
        ),
        passwd=config.get_cloud_config_value(
            "password", get_configured_provider(), __opts__, search_global=False
        ),
    )
    opener = _build_opener(auth_handler)
    _install_opener(opener)

    if action:
        path += action

    if command:
        path += "/{0}".format(command)

    if not type(args, dict):
        args = {}

    kwargs = {"data": data}
    if isinstance(data, six.string_types) and "<?xml" in data:
        kwargs["headers"] = {
            "Content-type": "application/xml",
        }

    if args:
        params = _urlencode(args)
        req = _Request(url="{0}?{1}".format(path, params), **kwargs)
    else:
        req = _Request(url=path, **kwargs)

    req.get_method = lambda: method

    log.debug("%s %s", method, req.get_full_url())
    if data:
        log.debug(data)

    try:
        result = _urlopen(req)
        log.debug("PARALLELS Response Status Code: %s", result.getcode())

        if "content-length" in result.headers:
            content = result.read()
            result.close()
            items = ET.fromstring(content)
            return items

        return {}
    except URLError as exc:
        log.error("PARALLELS Response Status Code: %s %s", exc.code, exc.msg)
        root = ET.fromstring(exc.read())
        log.error(root)
        return {"error": root}


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
    Show the details from Parallels concerning an image
    """
    if call != "function":
        raise SaltCloudSystemExit(
            "The show_image function must be called with -f or --function."
        )

    items = query(action="template", command=kwargs["image"])
    if "error" in items:
        return items["error"]

    ret = {}
    for item in items:
        ret.update({item.attrib["name"]: item.attrib})

    return ret


def show_instance(name, call=None):
    """
    Show the details from Parallels concerning an instance
    """
    if call != "action":
        raise SaltCloudSystemExit(
            "The show_instance action must be called with -a or --action."
        )

    items = query(action="ve", command=name)

    ret = {}
    for item in items:
        if "text" in item.__dict__:
            ret[item.tag] = item.text
        else:
            ret[item.tag] = item.attrib

        if item._children:
            ret[item.tag] = {}
            children = item._children
            for child in children:
                ret[item.tag][child.tag] = child.attrib

    __utils__["cloud.cache_node"](ret, __active_provider_name__, __opts__)
    return ret


def wait_until(name, state, timeout=300):
    """
    Wait until a specific state has been reached on  a node
    """
    start_time = time.time()
    node = show_instance(name, call="action")
    while True:
        if node["state"] == state:
            return True
        time.sleep(1)
        if time.time() - start_time > timeout:
            return False
        node = show_instance(name, call="action")


def destroy(name, call=None):
    """
    Destroy a node.

    CLI Example:

    .. code-block:: bash

        salt-cloud --destroy mymachine
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

    node = show_instance(name, call="action")
    if node["state"] == "STARTED":
        stop(name, call="action")
        if not wait_until(name, "STOPPED"):
            return {"Error": "Unable to destroy {0}, command timed out".format(name)}

    data = query(action="ve", command=name, method="DELETE")

    if "error" in data:
        return data["error"]

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

    return {"Destroyed": "{0} was destroyed.".format(name)}


def start(name, call=None):
    """
    Start a node.

    CLI Example:

    .. code-block:: bash

        salt-cloud -a start mymachine
    """
    if call != "action":
        raise SaltCloudSystemExit(
            "The show_instance action must be called with -a or --action."
        )

    data = query(action="ve", command="{0}/start".format(name), method="PUT")

    if "error" in data:
        return data["error"]

    return {"Started": "{0} was started.".format(name)}


def stop(name, call=None):
    """
    Stop a node.

    CLI Example:

    .. code-block:: bash

        salt-cloud -a stop mymachine
    """
    if call != "action":
        raise SaltCloudSystemExit(
            "The show_instance action must be called with -a or --action."
        )

    data = query(action="ve", command="{0}/stop".format(name), method="PUT")

    if "error" in data:
        return data["error"]

    return {"Stopped": "{0} was stopped.".format(name)}
