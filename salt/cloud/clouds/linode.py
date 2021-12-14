r"""
The Linode Cloud Module
=======================

The Linode cloud module is used to interact with the Linode Cloud.

You can target a specific version of the Linode API with the ``api_version`` parameter. The default is ``v3``.

Provider
--------

The following provider parameters are supported:

- **apikey**: (required) The key to use to authenticate with the Linode API.
- **password**: (required) The default password to set on new VMs. Must be 8 characters with at least one lowercase, uppercase, and numeric.
- **api_version**: (optional) The version of the Linode API to interact with. Defaults to ``v3``.
- **poll_interval**: (optional) The rate of time in milliseconds to poll the Linode API for changes. Defaults to ``500``.
- **ratelimit_sleep**: (optional) The time in seconds to wait before retrying after a ratelimit has been enforced. Defaults to ``0``.

.. note::

    APIv3 usage is deprecated and will be removed in a future release in favor of APIv4. To move to APIv4 now,
    set the ``api_version`` parameter in your provider configuration to ``v4``. See the full migration guide
    here https://docs.saltproject.io/en/latest/topics/cloud/linode.html#migrating-to-apiv4.

Set up the provider configuration at ``/etc/salt/cloud.providers`` or ``/etc/salt/cloud.providers.d/linode.conf``:

.. code-block:: yaml

    my-linode-provider:
        driver: linode
        api_version: v4
        apikey: f4ZsmwtB1c7f85Jdu43RgXVDFlNjuJaeIYV8QMftTqKScEB2vSosFSr...
        password: F00barbaz

For use with APIv3 (deprecated):

.. code-block:: yaml

    my-linode-provider-v3:
        driver: linode
        apikey: f4ZsmwtB1c7f85Jdu43RgXVDFlNjuJaeIYV8QMftTqKScEB2vSosFSr...
        password: F00barbaz

Profile
-------

The following profile parameters are supported:

- **size**: (required) The size of the VM. This should be a Linode instance type ID (i.e. ``g6-standard-2``). For APIv3, this would be a plan ID (i.e. ``Linode 2GB``). Run ``salt-cloud -f avail_sizes my-linode-provider`` for options.
- **location**: (required) The location of the VM. This should be a Linode region (e.g. ``us-east``). For APIv3, this would be a datacenter location (i.e. ``Newark, NJ, USA``). Run ``salt-cloud -f avail_locations my-linode-provider`` for options.
- **image**: (required) The image to deploy the boot disk from. This should be an image ID (e.g. ``linode/ubuntu16.04``); official images start with ``linode/``. For APIv3, this would be an image label (i.e. Ubuntu 16.04). Run ``salt-cloud -f avail_images my-linode-provider`` for more options.
- **password**: (\*required) The default password for the VM. Must be provided at the profile or provider level.
- **assign_private_ip**: (optional) Whether or not to assign a private key to the VM. Defaults to ``False``.
- **ssh_interface**: (optional) The interface with which to connect over SSH. Valid options are ``private_ips`` or ``public_ips``. Defaults to ``public_ips``.
- **ssh_pubkey**: (optional) The public key to authorize for SSH with the VM.
- **swap**: (optional) The amount of disk space to allocate for the swap partition. Defaults to ``256``.
- **clonefrom**: (optional) The name of the Linode to clone from.
- **disk_size**: (deprecated, optional) The amount of disk space to allocate for the OS disk. This has no effect with APIv4; the size of the boot disk will be the remainder of disk space after the swap parition is allocated.

Set up a profile configuration in ``/etc/salt/cloud.profiles.d/``:

.. code-block:: yaml

    my-linode-profile:
        # a minimal configuration
        provider: my-linode-provider
        size: g6-standard-1
        image: linode/alpine3.12
        location: us-east

    my-linode-profile-advanced:
        # an advanced configuration
        provider: my-linode-provider
        size: g6-standard-3
        image: linode/alpine3.10
        location: eu-west
        password: bogus123X
        assign_private_ip: true
        ssh_interface: private_ips
        ssh_pubkey: ssh-rsa AAAAB3NzaC1yc2EAAAADAQAB...
        swap_size: 512

    my-linode-profile-v3:
        # a legacy configuration
        provider: my-linode-provider-v3
        size: Nanode 1GB
        image: Alpine 3.12
        location: Fremont, CA, USA

Migrating to APIv4
------------------

In order to target APIv4, ensure your provider configuration has ``api_version`` set to ``v4``.

You will also need to generate a new token for your account. See https://www.linode.com/docs/platform/api/getting-started-with-the-linode-api/#create-an-api-token

There are a few changes to note:
- There has been a general move from label references to ID references. The profile configuration parameters ``location``, ``size``, and ``image`` have moved from being label based references to IDs. See the profile section for more information. In addition to these inputs being changed, ``avail_sizes``, ``avail_locations``, and ``avail_images`` now output options sorted by ID instead of label.
- The ``disk_size`` profile configuration parameter has been deprecated and will not be taken into account when creating new VMs while targeting APIv4.

:maintainer: Charles Kenney <ckenney@linode.com>
:maintainer: Phillip Campbell <pcampbell@linode.com>
:depends: requests
"""

import abc
import datetime
import json
import logging
import pprint
import re
import time
from pathlib import Path

import salt.config as config
from salt._compat import ipaddress
from salt.exceptions import (
    SaltCloudConfigError,
    SaltCloudException,
    SaltCloudNotFound,
    SaltCloudSystemExit,
)

try:
    import requests

    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False

# Get logging started
log = logging.getLogger(__name__)

HAS_WARNED_FOR_API_V3 = False

# The epoch of the last time a query was made
LASTCALL = int(time.mktime(datetime.datetime.now().timetuple()))

# Human-readable status fields for APIv3 (documentation: https://www.linode.com/api/linode/linode.list)
LINODE_STATUS = {
    "boot_failed": {"code": -2, "descr": "Boot Failed (not in use)"},
    "beeing_created": {"code": -1, "descr": "Being Created"},
    "brand_new": {"code": 0, "descr": "Brand New"},
    "running": {"code": 1, "descr": "Running"},
    "poweroff": {"code": 2, "descr": "Powered Off"},
    "shutdown": {"code": 3, "descr": "Shutting Down (not in use)"},
    "save_to_disk": {"code": 4, "descr": "Saved to Disk (not in use)"},
}

__virtualname__ = "linode"


# Only load in this module if the Linode configurations are in place
def __virtual__():
    """
    Check for Linode configs.
    """
    if get_configured_provider() is False:
        return False

    if _get_dependencies() is False:
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
        ("apikey", "password"),
    )


def _get_dependencies():
    """
    Warn if dependencies aren't met.
    """
    deps = {"requests": HAS_REQUESTS}
    return config.check_driver_dependencies(__virtualname__, deps)


def _get_api_version():
    """
    Return the configured Linode API version.
    """
    return config.get_cloud_config_value(
        "api_version",
        get_configured_provider(),
        __opts__,
        search_global=False,
        default="v3",
    )


def _is_api_v3():
    """
    Return whether the configured Linode API version is ``v3``.
    """
    return _get_api_version() == "v3"


def _get_cloud_interface():
    if _is_api_v3():
        return LinodeAPIv3()
    return LinodeAPIv4()


def _get_api_key():
    """
    Returned the configured Linode API key.
    """
    val = config.get_cloud_config_value(
        "api_key",
        get_configured_provider(),
        __opts__,
        search_global=False,
        default=config.get_cloud_config_value(
            "apikey", get_configured_provider(), __opts__, search_global=False
        ),
    )
    return val


def _get_ratelimit_sleep():
    """
    Return the configured time to wait before retrying after a ratelimit has been enforced.
    """
    return config.get_cloud_config_value(
        "ratelimit_sleep",
        get_configured_provider(),
        __opts__,
        search_global=False,
        default=0,
    )


def _get_poll_interval():
    """
    Return the configured interval in milliseconds to poll the Linode API for changes at.
    """
    return config.get_cloud_config_value(
        "poll_interval",
        get_configured_provider(),
        __opts__,
        search_global=False,
        default=500,
    )


def _get_password(vm_):
    r"""
    Return the password to use for a VM.

    vm\_
        The configuration to obtain the password from.
    """
    return config.get_cloud_config_value(
        "password",
        vm_,
        __opts__,
        default=config.get_cloud_config_value(
            "passwd", vm_, __opts__, search_global=False
        ),
        search_global=False,
    )


def _get_root_disk_size(vm_):
    """
    Return the specified size of the data partition.
    """
    return config.get_cloud_config_value(
        "disk_size", vm_, __opts__, search_global=False
    )


def _get_private_ip(vm_):
    """
    Return True if a private ip address is requested
    """
    return config.get_cloud_config_value(
        "assign_private_ip", vm_, __opts__, default=False
    )


def _get_ssh_key_files(vm_):
    """
    Return the configured file paths of the SSH keys.
    """
    return config.get_cloud_config_value(
        "ssh_key_files", vm_, __opts__, search_global=False, default=[]
    )


def _get_ssh_key(vm_):
    r"""
    Return the SSH pubkey.

    vm\_
        The configuration to obtain the public key from.
    """
    return config.get_cloud_config_value(
        "ssh_pubkey", vm_, __opts__, search_global=False
    )


def _get_swap_size(vm_):
    r"""
    Returns the amount of swap space to be used in MB.

    vm\_
        The VM profile to obtain the swap size from.
    """
    return config.get_cloud_config_value("swap", vm_, __opts__, default=256)


def _get_ssh_keys(vm_):
    """
    Return all SSH keys from ``ssh_pubkey`` and ``ssh_key_files``.
    """
    ssh_keys = set()

    raw_pub_key = _get_ssh_key(vm_)
    if raw_pub_key is not None:
        ssh_keys.add(raw_pub_key)

    key_files = _get_ssh_key_files(vm_)
    for file in map(lambda file: Path(file).resolve(), key_files):
        if not (file.exists() or file.is_file()):
            raise SaltCloudSystemExit("Invalid SSH key file: {}".format(str(file)))
        ssh_keys.add(file.read_text())

    return list(ssh_keys)


def _get_ssh_interface(vm_):
    """
    Return the ssh_interface type to connect to. Either 'public_ips' (default)
    or 'private_ips'.
    """
    return config.get_cloud_config_value(
        "ssh_interface", vm_, __opts__, default="public_ips", search_global=False
    )


def _validate_name(name):
    """
    Checks if the provided name fits Linode's labeling parameters.

    .. versionadded:: 2015.5.6

    name
        The VM name to validate
    """
    name = str(name)
    name_length = len(name)
    regex = re.compile(r"^[a-zA-Z0-9][A-Za-z0-9_-]*[a-zA-Z0-9]$")

    if name_length < 3 or name_length > 48:
        ret = False
    elif not re.match(regex, name):
        ret = False
    else:
        ret = True

    if ret is False:
        log.warning(
            "A Linode label may only contain ASCII letters or numbers, dashes, and "
            "underscores, must begin and end with letters or numbers, and be at least "
            "three characters in length."
        )

    return ret


def _warn_for_api_v3():
    global HAS_WARNED_FOR_API_V3

    if not HAS_WARNED_FOR_API_V3:
        log.warning(
            "Linode APIv3 has been deprecated and support will be removed "
            "in future releases. Please plan to upgrade to APIv4. For more "
            "information, see"
            " https://docs.saltproject.io/en/latest/topics/cloud/linode.html#migrating-to-apiv4."
        )
        HAS_WARNED_FOR_API_V3 = True


class LinodeAPI:
    @abc.abstractmethod
    def avail_images(self):
        """avail_images implementation"""

    @abc.abstractmethod
    def avail_locations(self):
        """avail_locations implementation"""

    @abc.abstractmethod
    def avail_sizes(self):
        """avail_sizes implementation"""

    @abc.abstractmethod
    def boot(self, name=None, kwargs=None):
        """boot implementation"""

    @abc.abstractmethod
    def clone(self, kwargs=None):
        """clone implementation"""

    @abc.abstractmethod
    def create_config(self, kwargs=None):
        """create_config implementation"""

    @abc.abstractmethod
    def create(self, vm_):
        """create implementation"""

    @abc.abstractmethod
    def destroy(self, name):
        """destroy implementation"""

    @abc.abstractmethod
    def get_config_id(self, kwargs=None):
        """get_config_id implementation"""

    @abc.abstractmethod
    def list_nodes(self):
        """list_nodes implementation"""

    @abc.abstractmethod
    def list_nodes_full(self):
        """list_nodes_full implementation"""

    @abc.abstractmethod
    def list_nodes_min(self):
        """list_nodes_min implementation"""

    @abc.abstractmethod
    def reboot(self, name):
        """reboot implementation"""

    @abc.abstractmethod
    def show_instance(self, name):
        """show_instance implementation"""

    @abc.abstractmethod
    def show_pricing(self, kwargs=None):
        """show_pricing implementation"""

    @abc.abstractmethod
    def start(self, name):
        """start implementation"""

    @abc.abstractmethod
    def stop(self, name):
        """stop implementation"""

    @abc.abstractmethod
    def _get_linode_by_name(self, name):
        """_get_linode_by_name implementation"""

    @abc.abstractmethod
    def _get_linode_by_id(self, linode_id):
        """_get_linode_by_id implementation"""

    def get_plan_id(self, kwargs=None):
        """get_plan_id implementation"""
        raise SaltCloudSystemExit(
            "The get_plan_id is not supported by this api_version."
        )

    def get_linode(self, kwargs=None):
        name = kwargs.get("name", None)
        linode_id = kwargs.get("linode_id", None)

        if linode_id is not None:
            return self._get_linode_by_id(linode_id)
        elif name is not None:
            return self._get_linode_by_name(name)

        raise SaltCloudSystemExit(
            "The get_linode function requires either a 'name' or a 'linode_id'."
        )

    def list_nodes_select(self, call):
        return __utils__["cloud.list_nodes_select"](
            self.list_nodes_full(),
            __opts__["query.selection"],
            call,
        )


class LinodeAPIv4(LinodeAPI):
    def _query(self, path=None, method="GET", data=None, headers=None):
        """
        Make a call to the Linode API.
        """
        api_version = _get_api_version()
        api_key = _get_api_key()
        ratelimit_sleep = _get_ratelimit_sleep()

        if headers is None:
            headers = {}
        headers["Authorization"] = "Bearer {}".format(api_key)
        headers["Content-Type"] = "application/json"
        headers["User-Agent"] = "salt-cloud-linode"

        url = "https://api.linode.com/{}{}".format(api_version, path)

        decode = method != "DELETE"
        result = None

        log.debug("Linode API request: %s %s", method, url)

        if data is not None:
            log.trace("Linode API request body: %s", data)

        attempt = 0
        while True:
            try:
                result = requests.request(method, url, json=data, headers=headers)

                log.debug("Linode API response status code: %d", result.status_code)
                log.trace("Linode API response body: %s", result.text)
                result.raise_for_status()
                break
            except requests.exceptions.HTTPError as exc:
                err_response = exc.response
                err_data = self._get_response_json(err_response)
                status_code = err_response.status_code

                if status_code == 429:
                    log.debug(
                        "recieved rate limit; retrying in %d seconds", ratelimit_sleep
                    )
                    time.sleep(ratelimit_sleep)
                    continue

                if err_data is not None:
                    # Build an error from the response JSON
                    if "error" in err_data:
                        raise SaltCloudSystemExit(
                            "Linode API reported error: {}".format(err_data["error"])
                        )
                    elif "errors" in err_data:
                        api_errors = err_data["errors"]

                        # Build Salt exception
                        errors = []
                        for error in err_data["errors"]:
                            if "field" in error:
                                errors.append(
                                    "field '{}': {}".format(
                                        error.get("field"), error.get("reason")
                                    )
                                )
                            else:
                                errors.append(error.get("reason"))

                        raise SaltCloudSystemExit(
                            "Linode API reported error(s): {}".format(", ".join(errors))
                        )

                # If the response is not valid JSON or the error was not included, propagate the
                # human readable status representation.
                raise SaltCloudSystemExit(
                    "Linode API error occurred: {}".format(err_response.reason)
                )
        if decode:
            return self._get_response_json(result)

        return result

    def avail_images(self):
        response = self._query(path="/images")
        ret = {}
        for image in response["data"]:
            ret[image["id"]] = image
        return ret

    def avail_locations(self):
        response = self._query(path="/regions")
        ret = {}
        for region in response["data"]:
            ret[region["id"]] = region
        return ret

    def avail_sizes(self):
        response = self._query(path="/linode/types")
        ret = {}
        for instance_type in response["data"]:
            ret[instance_type["id"]] = instance_type
        return ret

    def boot(self, name=None, kwargs=None):
        instance = self.get_linode(
            kwargs={"linode_id": kwargs.get("linode_id", None), "name": name}
        )
        config_id = kwargs.get("config_id", None)
        check_running = kwargs.get("check_running", True)
        linode_id = instance.get("id", None)
        name = instance.get("label", None)

        if check_running:
            if instance["status"] == "running":
                raise SaltCloudSystemExit(
                    "Cannot boot Linode {0} ({1}). "
                    "Linode {0} is already running.".format(name, linode_id)
                )

        response = self._query(
            "/linode/instances/{}/boot".format(linode_id),
            method="POST",
            data={"config_id": config_id},
        )

        self._wait_for_linode_status(linode_id, "running")
        return True

    def clone(self, kwargs=None):
        linode_id = kwargs.get("linode_id", None)
        location = kwargs.get("location", None)
        size = kwargs.get("size", None)

        if "datacenter_id" in kwargs:
            log.warning(
                "The 'datacenter_id' argument has been deprecated and will be "
                "removed in future releases. Please use 'location' instead."
            )

        if "plan_id" in kwargs:
            log.warning(
                "The 'plan_id' argument has been deprecated and will be "
                "removed in future releases. Please use 'size' instead."
            )

        for item in [linode_id, location, size]:
            if item is None:
                raise SaltCloudSystemExit(
                    "The clone function requires a 'linode_id', 'location',"
                    "and 'size' to be provided."
                )

        return self._query(
            "/linode/instances/{}/clone".format(linode_id),
            method="POST",
            data={"region": location, "type": size},
        )

    def create_config(self, kwargs=None):
        name = kwargs.get("name", None)
        linode_id = kwargs.get("linode_id", None)
        root_disk_id = kwargs.get("root_disk_id", None)
        swap_disk_id = kwargs.get("swap_disk_id", None)
        data_disk_id = kwargs.get("data_disk_id", None)

        if not name and not linode_id:
            raise SaltCloudSystemExit(
                "The create_config function requires either a 'name' or 'linode_id'"
            )

        required_params = [name, linode_id, root_disk_id, swap_disk_id]
        for item in required_params:
            if item is None:
                raise SaltCloudSystemExit(
                    "The create_config functions requires a 'name', 'linode_id', "
                    "'root_disk_id', and 'swap_disk_id'."
                )

        devices = {
            "sda": {"disk_id": int(root_disk_id)},
            "sdb": {"disk_id": int(data_disk_id)} if data_disk_id is not None else None,
            "sdc": {"disk_id": int(swap_disk_id)},
        }

        return self._query(
            "/linode/instances/{}/configs".format(linode_id),
            method="POST",
            data={"label": name, "devices": devices},
        )

    def create(self, vm_):
        name = vm_["name"]

        if not _validate_name(name):
            return False

        __utils__["cloud.fire_event"](
            "event",
            "starting create",
            "salt/cloud/{}/creating".format(name),
            args=__utils__["cloud.filter_event"](
                "creating", vm_, ["name", "profile", "provider", "driver"]
            ),
            sock_dir=__opts__["sock_dir"],
            transport=__opts__["transport"],
        )

        log.info("Creating Cloud VM %s", name)

        result = None

        pub_ssh_keys = _get_ssh_keys(vm_)
        ssh_interface = _get_ssh_interface(vm_)
        use_private_ip = ssh_interface == "private_ips"
        assign_private_ip = _get_private_ip(vm_) or use_private_ip
        password = _get_password(vm_)
        swap_size = _get_swap_size(vm_)

        clonefrom_name = vm_.get("clonefrom", None)
        instance_type = vm_.get("size", None)
        image = vm_.get("image", None)
        should_clone = True if clonefrom_name else False

        if should_clone:
            # clone into new linode
            clone_linode = self.get_linode(kwargs={"name": clonefrom_name})
            result = clone(
                {
                    "linode_id": clone_linode["id"],
                    "location": clone_linode["region"],
                    "size": clone_linode["type"],
                }
            )

            # create private IP if needed
            if assign_private_ip:
                self._query(
                    "/networking/ips",
                    method="POST",
                    data={"type": "ipv4", "public": False, "linode_id": result["id"]},
                )
        else:
            # create new linode
            result = self._query(
                "/linode/instances",
                method="POST",
                data={
                    "label": name,
                    "type": instance_type,
                    "region": vm_.get("location", None),
                    "private_ip": assign_private_ip,
                    "booted": True,
                    "root_pass": password,
                    "authorized_keys": pub_ssh_keys,
                    "image": image,
                    "swap_size": swap_size,
                },
            )

        linode_id = result.get("id", None)

        # wait for linode to be created
        self._wait_for_event("linode_create", "linode", linode_id, "finished")
        log.debug("linode '%s' has been created", name)

        if should_clone:
            self.boot(kwargs={"linode_id": linode_id})

        # wait for linode to finish booting
        self._wait_for_linode_status(linode_id, "running")

        public_ips, private_ips = self._get_ips(linode_id)

        data = {}
        data["id"] = linode_id
        data["name"] = result["label"]
        data["size"] = result["type"]
        data["state"] = result["status"]
        data["ipv4"] = result["ipv4"]
        data["ipv6"] = result["ipv6"]
        data["public_ips"] = public_ips
        data["private_ips"] = private_ips

        if use_private_ip:
            vm_["ssh_host"] = private_ips[0]
        else:
            vm_["ssh_host"] = public_ips[0]

        # Send event that the instance has booted.
        __utils__["cloud.fire_event"](
            "event",
            "waiting for ssh",
            "salt/cloud/{}/waiting_for_ssh".format(name),
            sock_dir=__opts__["sock_dir"],
            args={"ip_address": vm_["ssh_host"]},
            transport=__opts__["transport"],
        )

        ret = __utils__["cloud.bootstrap"](vm_, __opts__)
        ret.update(data)

        log.info("Created Cloud VM '%s'", name)
        log.debug("'%s' VM creation details:\n%s", name, pprint.pformat(data))

        __utils__["cloud.fire_event"](
            "event",
            "created instance",
            "salt/cloud/{}/created".format(name),
            args=__utils__["cloud.filter_event"](
                "created", vm_, ["name", "profile", "provider", "driver"]
            ),
            sock_dir=__opts__["sock_dir"],
            transport=__opts__["transport"],
        )

        return ret

    def destroy(self, name):
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

        instance = self._get_linode_by_name(name)
        linode_id = instance.get("id", None)

        self._query("/linode/instances/{}".format(linode_id), method="DELETE")

    def get_config_id(self, kwargs=None):
        name = kwargs.get("name", None)
        linode_id = kwargs.get("linode_id", None)

        if name is None and linode_id is None:
            raise SaltCloudSystemExit(
                "The get_config_id function requires either a 'name' or a 'linode_id' "
                "to be provided."
            )

        if linode_id is None:
            linode_id = self.get_linode(kwargs=kwargs).get("id", None)

        response = self._query("/linode/instances/{}/configs".format(linode_id))
        configs = response.get("data", [])

        return {"config_id": configs[0]["id"]}

    def list_nodes_min(self):
        result = self._query("/linode/instances")
        instances = result.get("data", [])

        ret = {}
        for instance in instances:
            name = instance["label"]
            ret[name] = {"id": instance["id"], "state": instance["status"]}

        return ret

    def list_nodes_full(self):
        return self._list_linodes(full=True)

    def list_nodes(self):
        return self._list_linodes()

    def reboot(self, name):
        instance = self._get_linode_by_name(name)
        linode_id = instance.get("id", None)

        self._query("/linode/instances/{}/reboot".format(linode_id), method="POST")
        return self._wait_for_linode_status(linode_id, "running")

    def show_instance(self, name):
        instance = self._get_linode_by_name(name)
        linode_id = instance.get("id", None)
        public_ips, private_ips = self._get_ips(linode_id)

        return {
            "id": instance["id"],
            "image": instance["image"],
            "name": instance["label"],
            "size": instance["type"],
            "state": instance["status"],
            "public_ips": public_ips,
            "private_ips": private_ips,
        }

    def show_pricing(self, kwargs=None):
        profile = __opts__["profiles"].get(kwargs["profile"], {})
        if not profile:
            raise SaltCloudNotFound("The requested profile was not found.")

        # Make sure the profile belongs to Linode
        provider = profile.get("provider", "0:0")
        comps = provider.split(":")
        if len(comps) < 2 or comps[1] != "linode":
            raise SaltCloudException("The requested profile does not belong to Linode.")

        instance_type = self._get_linode_type(profile["size"])
        pricing = instance_type.get("price", {})

        per_hour = pricing["hourly"]
        per_day = per_hour * 24
        per_week = per_day * 7
        per_month = pricing["monthly"]
        per_year = per_month * 12

        return {
            profile["profile"]: {
                "per_hour": per_hour,
                "per_day": per_day,
                "per_week": per_week,
                "per_month": per_month,
                "per_year": per_year,
            }
        }

    def start(self, name):
        instance = self._get_linode_by_name(name)
        linode_id = instance.get("id", None)

        if instance["status"] == "running":
            return {
                "success": True,
                "action": "start",
                "state": "Running",
                "msg": "Machine already running",
            }

        self._query("/linode/instances/{}/boot".format(linode_id), method="POST")

        self._wait_for_linode_status(linode_id, "running")
        return {
            "success": True,
            "state": "Running",
            "action": "start",
        }

    def stop(self, name):
        instance = self._get_linode_by_name(name)
        linode_id = instance.get("id", None)

        if instance["status"] == "offline":
            return {
                "success": True,
                "action": "stop",
                "state": "Stopped",
                "msg": "Machine already stopped",
            }

        self._query("/linode/instances/{}/shutdown".format(linode_id), method="POST")

        self._wait_for_linode_status(linode_id, "offline")
        return {"success": True, "state": "Stopped", "action": "stop"}

    def _get_linode_by_id(self, linode_id):
        return self._query("/linode/instances/{}".format(linode_id))

    def _get_linode_by_name(self, name):
        result = self._query("/linode/instances")
        instances = result.get("data", [])

        for instance in instances:
            if instance["label"] == name:
                return instance

        raise SaltCloudNotFound(
            "The specified name, {}, could not be found.".format(name)
        )

    def _list_linodes(self, full=False):
        result = self._query("/linode/instances")
        instances = result.get("data", [])

        ret = {}
        for instance in instances:
            node = {}
            node["id"] = instance["id"]
            node["image"] = instance["image"]
            node["name"] = instance["label"]
            node["size"] = instance["type"]
            node["state"] = instance["status"]

            public_ips, private_ips = self._get_ips(node["id"])
            node["public_ips"] = public_ips
            node["private_ips"] = private_ips

            if full:
                node["extra"] = instance

            ret[instance["label"]] = node

        return ret

    def _get_linode_type(self, linode_type):
        return self._query("/linode/types/{}".format(linode_type))

    def _get_ips(self, linode_id):
        instance = self._get_linode_by_id(linode_id)
        public = []
        private = []

        for addr in instance.get("ipv4", []):
            if ipaddress.ip_address(addr).is_private:
                private.append(addr)
            else:
                public.append(addr)

        return (public, private)

    def _poll(
        self,
        description,
        getter,
        condition,
        timeout=None,
        poll_interval=None,
    ):
        """
        Return true in handler to signal complete.
        """
        if poll_interval is None:
            poll_interval = _get_poll_interval()

        if timeout is None:
            timeout = 120

        times = (timeout * 1000) / poll_interval
        curr = 0

        while True:
            curr += 1
            result = getter()
            if condition(result):
                return True
            elif curr <= times:
                time.sleep(poll_interval / 1000)
                log.info("retrying: polling for %s...", description)
            else:
                raise SaltCloudException(
                    "timed out: polling for {}".format(description)
                )

    def _wait_for_entity_status(
        self, getter, status, entity_name="item", identifier="some", timeout=None
    ):
        return self._poll(
            "{} (id={}) status to be '{}'".format(entity_name, identifier, status),
            getter,
            lambda item: item.get("status") == status,
            timeout=timeout,
        )

    def _wait_for_linode_status(self, linode_id, status, timeout=None):
        return self._wait_for_entity_status(
            lambda: self._get_linode_by_id(linode_id),
            status,
            entity_name="linode",
            identifier=linode_id,
            timeout=timeout,
        )

    def _check_event_status(self, event, desired_status):
        status = event.get("status")
        action = event.get("action")
        entity = event.get("entity")
        if status == "failed":
            raise SaltCloudSystemExit(
                "event {} for {} (id={}) failed".format(
                    action, entity["type"], entity["id"]
                )
            )
        return status == desired_status

    def _wait_for_event(self, action, entity, entity_id, status, timeout=None):
        event_filter = {
            "+order_by": "created",
            "+order": "desc",
            "seen": False,
            "action": action,
            "entity.id": entity_id,
            "entity.type": entity,
        }
        last_event = None
        condition = lambda event: self._check_event_status(event, status)

        while True:
            if last_event is not None:
                event_filter["+gt"] = last_event
            filter_json = json.dumps(event_filter, separators=(",", ":"))
            result = self._query("/account/events", headers={"X-Filter": filter_json})
            events = result.get("data", [])

            if len(events) == 0:
                break

            for event in events:
                event_id = event.get("id")
                event_entity = event.get("entity", None)
                last_event = event_id
                if not event_entity:
                    continue

                if not (
                    event_entity["type"] == entity
                    and event_entity["id"] == entity_id
                    and event.get("action") == action
                ):
                    continue

                if condition(event):
                    return True

                return self._poll(
                    "event {} to be '{}'".format(event_id, status),
                    lambda: self._query("/account/events/{}".format(event_id)),
                    condition,
                    timeout=timeout,
                )

        return False

    def _get_response_json(self, response):
        json = None
        try:
            json = response.json()
        except ValueError:
            pass
        return json


class LinodeAPIv3(LinodeAPI):
    def __init__(self):
        _warn_for_api_v3()

    def _query(
        self,
        action=None,
        command=None,
        args=None,
        method="GET",
        header_dict=None,
        data=None,
        url="https://api.linode.com/",
    ):
        """
        Make a web call to the Linode API.
        """
        global LASTCALL
        ratelimit_sleep = _get_ratelimit_sleep()
        apikey = _get_api_key()

        if not isinstance(args, dict):
            args = {}

        if "api_key" not in args.keys():
            args["api_key"] = apikey
        if action and "api_action" not in args.keys():
            args["api_action"] = "{}.{}".format(action, command)
        if header_dict is None:
            header_dict = {}
        if method != "POST":
            header_dict["Accept"] = "application/json"

        decode = True
        if method == "DELETE":
            decode = False

        now = int(time.mktime(datetime.datetime.now().timetuple()))

        if LASTCALL >= now:
            time.sleep(ratelimit_sleep)

        result = __utils__["http.query"](
            url,
            method,
            params=args,
            data=data,
            header_dict=header_dict,
            decode=decode,
            decode_type="json",
            text=True,
            status=True,
            hide_fields=["api_key", "rootPass"],
            opts=__opts__,
        )

        if "ERRORARRAY" in result["dict"]:
            if result["dict"]["ERRORARRAY"]:
                error_list = []
                for error in result["dict"]["ERRORARRAY"]:
                    msg = error["ERRORMESSAGE"]
                    if msg == "Authentication failed":
                        raise SaltCloudSystemExit(
                            "Linode API Key is expired or invalid"
                        )
                    else:
                        error_list.append(msg)
                raise SaltCloudException(
                    "Linode API reported error(s): {}".format(", ".join(error_list))
                )

        LASTCALL = int(time.mktime(datetime.datetime.now().timetuple()))
        log.debug("Linode Response Status Code: %s", result["status"])

        return result["dict"]

    def avail_images(self):
        response = self._query("avail", "distributions")

        ret = {}
        for item in response["DATA"]:
            name = item["LABEL"]
            ret[name] = item
        return ret

    def avail_locations(self):
        response = self._query("avail", "datacenters")

        ret = {}
        for item in response["DATA"]:
            name = item["LOCATION"]
            ret[name] = item
        return ret

    def avail_sizes(self):
        response = self._query("avail", "LinodePlans")

        ret = {}
        for item in response["DATA"]:
            name = item["LABEL"]
            ret[name] = item
        return ret

    def boot(self, name=None, kwargs=None):
        linode_id = kwargs.get("linode_id", None)
        config_id = kwargs.get("config_id", None)
        check_running = kwargs.get("check_running", True)

        if config_id is None:
            raise SaltCloudSystemExit("The boot function requires a 'config_id'.")

        if linode_id is None:
            linode_id = self._get_linode_id_from_name(name)
            linode_item = name
        else:
            linode_item = linode_id

        # Check if Linode is running first
        if check_running:
            status = get_linode(kwargs={"linode_id": linode_id})["STATUS"]
            if status == "1":
                raise SaltCloudSystemExit(
                    "Cannot boot Linode {0}. "
                    + "Linode {} is already running.".format(linode_item)
                )

        # Boot the VM and get the JobID from Linode
        response = self._query(
            "linode", "boot", args={"LinodeID": linode_id, "ConfigID": config_id}
        )["DATA"]
        boot_job_id = response["JobID"]

        if not self._wait_for_job(linode_id, boot_job_id):
            log.error("Boot failed for Linode %s.", linode_item)
            return False

        return True

    def clone(self, kwargs=None):
        linode_id = kwargs.get("linode_id", None)
        datacenter_id = kwargs.get("datacenter_id", kwargs.get("location"))
        plan_id = kwargs.get("plan_id", kwargs.get("size"))
        required_params = [linode_id, datacenter_id, plan_id]

        for item in required_params:
            if item is None:
                raise SaltCloudSystemExit(
                    "The clone function requires a 'linode_id', 'datacenter_id', "
                    "and 'plan_id' to be provided."
                )

        clone_args = {
            "LinodeID": linode_id,
            "DatacenterID": datacenter_id,
            "PlanID": plan_id,
        }

        return self._query("linode", "clone", args=clone_args)

    def create(self, vm_):
        name = vm_["name"]

        if not _validate_name(name):
            return False

        __utils__["cloud.fire_event"](
            "event",
            "starting create",
            "salt/cloud/{}/creating".format(name),
            args=__utils__["cloud.filter_event"](
                "creating", vm_, ["name", "profile", "provider", "driver"]
            ),
            sock_dir=__opts__["sock_dir"],
            transport=__opts__["transport"],
        )

        log.info("Creating Cloud VM %s", name)

        data = {}
        kwargs = {"name": name}

        plan_id = None
        size = vm_.get("size")
        if size:
            kwargs["size"] = size
            plan_id = self.get_plan_id(kwargs={"label": size})

        datacenter_id = None
        location = vm_.get("location")
        if location:
            try:
                datacenter_id = self._get_datacenter_id(location)
            except KeyError:
                # Linode's default datacenter is Dallas, but we still have to set one to
                # use the create function from Linode's API. Dallas's datacenter id is 2.
                datacenter_id = 2

        clonefrom_name = vm_.get("clonefrom")
        cloning = True if clonefrom_name else False
        if cloning:
            linode_id = self._get_linode_id_from_name(clonefrom_name)
            clone_source = get_linode(kwargs={"linode_id": linode_id})

            kwargs = {
                "clonefrom": clonefrom_name,
                "image": "Clone of {}".format(clonefrom_name),
            }

            if size is None:
                size = clone_source["TOTALRAM"]
                kwargs["size"] = size
                plan_id = clone_source["PLANID"]

            if location is None:
                datacenter_id = clone_source["DATACENTERID"]

            # Create new Linode from cloned Linode
            try:
                result = clone(
                    kwargs={
                        "linode_id": linode_id,
                        "datacenter_id": datacenter_id,
                        "plan_id": plan_id,
                    }
                )
            except Exception as err:  # pylint: disable=broad-except
                log.error(
                    "Error cloning '%s' on Linode.\n\n"
                    "The following exception was thrown by Linode when trying to "
                    "clone the specified machine:\n%s",
                    clonefrom_name,
                    err,
                    exc_info_on_loglevel=logging.DEBUG,
                )
                return False
        else:
            kwargs["image"] = vm_["image"]

            # Create Linode
            try:
                result = self._query(
                    "linode",
                    "create",
                    args={"PLANID": plan_id, "DATACENTERID": datacenter_id},
                )
            except Exception as err:  # pylint: disable=broad-except
                log.error(
                    "Error creating %s on Linode\n\n"
                    "The following exception was thrown by Linode when trying to "
                    "run the initial deployment:\n%s",
                    name,
                    err,
                    exc_info_on_loglevel=logging.DEBUG,
                )
                return False

        if "ERRORARRAY" in result:
            for error_data in result["ERRORARRAY"]:
                log.error(
                    "Error creating %s on Linode\n\n"
                    "The Linode API returned the following: %s\n",
                    name,
                    error_data["ERRORMESSAGE"],
                )
                return False

        __utils__["cloud.fire_event"](
            "event",
            "requesting instance",
            "salt/cloud/{}/requesting".format(name),
            args=__utils__["cloud.filter_event"](
                "requesting", vm_, ["name", "profile", "provider", "driver"]
            ),
            sock_dir=__opts__["sock_dir"],
            transport=__opts__["transport"],
        )

        node_id = self._clean_data(result)["LinodeID"]
        data["id"] = node_id

        if not self._wait_for_status(
            node_id, status=(self._get_status_id_by_name("brand_new"))
        ):
            log.error(
                "Error creating %s on LINODE\n\nwhile waiting for initial ready status",
                name,
                exc_info_on_loglevel=logging.DEBUG,
            )

        # Update the Linode's Label to reflect the given VM name
        self._update_linode(node_id, update_args={"Label": name})
        log.debug("Set name for %s - was linode%s.", name, node_id)

        # Add private IP address if requested
        private_ip_assignment = _get_private_ip(vm_)
        if private_ip_assignment:
            self._create_private_ip(node_id)

        # Define which ssh_interface to use
        ssh_interface = _get_ssh_interface(vm_)

        # If ssh_interface is set to use private_ips, but assign_private_ip
        # wasn't set to True, let's help out and create a private ip.
        if ssh_interface == "private_ips" and private_ip_assignment is False:
            self._create_private_ip(node_id)
            private_ip_assignment = True

        if cloning:
            config_id = get_config_id(kwargs={"linode_id": node_id})["config_id"]
        else:
            # Create disks and get ids
            log.debug("Creating disks for %s", name)
            root_disk_id = self._create_disk_from_distro(vm_, node_id)["DiskID"]
            swap_disk_id = self._create_swap_disk(vm_, node_id)["DiskID"]

            # Create a ConfigID using disk ids
            config_id = create_config(
                kwargs={
                    "name": name,
                    "linode_id": node_id,
                    "root_disk_id": root_disk_id,
                    "swap_disk_id": swap_disk_id,
                }
            )["ConfigID"]

        # Boot the Linode
        self.boot(
            kwargs={
                "linode_id": node_id,
                "config_id": config_id,
                "check_running": False,
            }
        )

        node_data = get_linode(kwargs={"linode_id": node_id})
        ips = self._get_ips(node_id)
        state = int(node_data["STATUS"])

        data["image"] = kwargs["image"]
        data["name"] = name
        data["size"] = size
        data["state"] = self._get_status_descr_by_id(state)
        data["private_ips"] = ips["private_ips"]
        data["public_ips"] = ips["public_ips"]

        # Pass the correct IP address to the bootstrap ssh_host key
        if ssh_interface == "private_ips":
            vm_["ssh_host"] = data["private_ips"][0]
        else:
            vm_["ssh_host"] = data["public_ips"][0]

        # If a password wasn't supplied in the profile or provider config, set it now.
        vm_["password"] = _get_password(vm_)

        # Make public_ips and private_ips available to the bootstrap script.
        vm_["public_ips"] = ips["public_ips"]
        vm_["private_ips"] = ips["private_ips"]

        # Send event that the instance has booted.
        __utils__["cloud.fire_event"](
            "event",
            "waiting for ssh",
            "salt/cloud/{}/waiting_for_ssh".format(name),
            sock_dir=__opts__["sock_dir"],
            args={"ip_address": vm_["ssh_host"]},
            transport=__opts__["transport"],
        )

        # Bootstrap!
        ret = __utils__["cloud.bootstrap"](vm_, __opts__)

        ret.update(data)

        log.info("Created Cloud VM '%s'", name)
        log.debug("'%s' VM creation details:\n%s", name, pprint.pformat(data))

        __utils__["cloud.fire_event"](
            "event",
            "created instance",
            "salt/cloud/{}/created".format(name),
            args=__utils__["cloud.filter_event"](
                "created", vm_, ["name", "profile", "provider", "driver"]
            ),
            sock_dir=__opts__["sock_dir"],
            transport=__opts__["transport"],
        )

        return ret

    def create_config(self, kwargs=None):
        name = kwargs.get("name", None)
        linode_id = kwargs.get("linode_id", None)
        root_disk_id = kwargs.get("root_disk_id", None)
        swap_disk_id = kwargs.get("swap_disk_id", None)
        data_disk_id = kwargs.get("data_disk_id", None)
        kernel_id = kwargs.get("kernel_id", None)

        if kernel_id is None:
            # 138 appears to always be the latest 64-bit kernel for Linux
            kernel_id = 138

        required_params = [name, linode_id, root_disk_id, swap_disk_id]
        for item in required_params:
            if item is None:
                raise SaltCloudSystemExit(
                    "The create_config functions requires a 'name', 'linode_id', "
                    "'root_disk_id', and 'swap_disk_id'."
                )

        if kernel_id is None:
            # 138 appears to always be the latest 64-bit kernel for Linux
            kernel_id = 138

        if not linode_id:
            instance = self._get_linode_by_name(name)
            linode_id = instance.get("id", None)

        disklist = "{},{}".format(root_disk_id, swap_disk_id)
        if data_disk_id is not None:
            disklist = "{},{},{}".format(root_disk_id, swap_disk_id, data_disk_id)

        config_args = {
            "LinodeID": int(linode_id),
            "KernelID": int(kernel_id),
            "Label": name,
            "DiskList": disklist,
        }

        result = self._query("linode", "config.create", args=config_args)

        return result.get("DATA", None)

    def _create_disk_from_distro(self, vm_, linode_id):
        kwargs = {}
        swap_size = _get_swap_size(vm_)
        pub_key = _get_ssh_key(vm_)
        root_password = _get_password(vm_)

        if pub_key:
            kwargs.update({"rootSSHKey": pub_key})
        if root_password:
            kwargs.update({"rootPass": root_password})
        else:
            raise SaltCloudConfigError("The Linode driver requires a password.")

        kwargs.update(
            {
                "LinodeID": linode_id,
                "DistributionID": self._get_distribution_id(vm_),
                "Label": vm_["name"],
                "Size": self._get_disk_size(vm_, swap_size, linode_id),
            }
        )

        result = self._query("linode", "disk.createfromdistribution", args=kwargs)

        return self._clean_data(result)

    def _create_swap_disk(self, vm_, linode_id, swap_size=None):
        r"""
        Creates the disk for the specified Linode.

        vm\_
            The VM profile to create the swap disk for.

        linode_id
            The ID of the Linode to create the swap disk for.

        swap_size
            The size of the disk, in MB.
        """
        kwargs = {}

        if not swap_size:
            swap_size = _get_swap_size(vm_)

        kwargs.update(
            {
                "LinodeID": linode_id,
                "Label": vm_["name"],
                "Type": "swap",
                "Size": swap_size,
            }
        )

        result = self._query("linode", "disk.create", args=kwargs)

        return self._clean_data(result)

    def _create_data_disk(self, vm_=None, linode_id=None, data_size=None):
        kwargs = {}

        kwargs.update(
            {
                "LinodeID": linode_id,
                "Label": vm_["name"] + "_data",
                "Type": "ext4",
                "Size": data_size,
            }
        )

        result = self._query("linode", "disk.create", args=kwargs)
        return self._clean_data(result)

    def _create_private_ip(self, linode_id):
        r"""
        Creates a private IP for the specified Linode.

        linode_id
            The ID of the Linode to create the IP address for.
        """
        kwargs = {"LinodeID": linode_id}
        result = self._query("linode", "ip.addprivate", args=kwargs)

        return self._clean_data(result)

    def destroy(self, name):
        __utils__["cloud.fire_event"](
            "event",
            "destroying instance",
            "salt/cloud/{}/destroying".format(name),
            args={"name": name},
            sock_dir=__opts__["sock_dir"],
            transport=__opts__["transport"],
        )

        linode_id = self._get_linode_id_from_name(name)

        response = self._query(
            "linode", "delete", args={"LinodeID": linode_id, "skipChecks": True}
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

        return response

    def _decode_linode_plan_label(self, label):
        """
        Attempts to decode a user-supplied Linode plan label
        into the format in Linode API output

        label
            The label, or name, of the plan to decode.

        Example:
            `Linode 2048` will decode to `Linode 2GB`
        """
        sizes = self.avail_sizes()

        if label not in sizes:
            if "GB" in label:
                raise SaltCloudException(
                    "Invalid Linode plan ({}) specified - call avail_sizes() for all"
                    " available options".format(label)
                )
            else:
                plan = label.split()

                if len(plan) != 2:
                    raise SaltCloudException(
                        "Invalid Linode plan ({}) specified - call avail_sizes() for"
                        " all available options".format(label)
                    )

                plan_type = plan[0]
                try:
                    plan_size = int(plan[1])
                except TypeError:
                    plan_size = 0
                    log.debug(
                        "Failed to decode Linode plan label in Cloud Profile: %s", label
                    )

                if plan_type == "Linode" and plan_size == 1024:
                    plan_type = "Nanode"

                plan_size = plan_size / 1024
                new_label = "{} {}GB".format(plan_type, plan_size)

                if new_label not in sizes:
                    raise SaltCloudException(
                        "Invalid Linode plan ({}) specified - call avail_sizes() for"
                        " all available options".format(new_label)
                    )

                log.warning(
                    "An outdated Linode plan label was detected in your Cloud "
                    "Profile (%s). Please update the profile to use the new "
                    "label format (%s) for the requested Linode plan size.",
                    label,
                    new_label,
                )

                label = new_label

        return sizes[label]["PLANID"]

    def get_config_id(self, kwargs=None):
        name = kwargs.get("name", None)
        linode_id = kwargs.get("linode_id", None)
        if name is None and linode_id is None:
            raise SaltCloudSystemExit(
                "The get_config_id function requires either a 'name' or a 'linode_id' "
                "to be provided."
            )
        if linode_id is None:
            linode_id = self._get_linode_id_from_name(name)

        response = self._query("linode", "config.list", args={"LinodeID": linode_id})[
            "DATA"
        ]
        config_id = {"config_id": response[0]["ConfigID"]}

        return config_id

    def _get_datacenter_id(self, location):
        """
        Returns the Linode Datacenter ID.

        location
            The location, or name, of the datacenter to get the ID from.
        """
        return avail_locations()[location]["DATACENTERID"]

    def _get_disk_size(self, vm_, swap, linode_id):
        r"""
        Returns the size of of the root disk in MB.

        vm\_
            The VM to get the disk size for.
        """
        disk_size = get_linode(kwargs={"linode_id": linode_id})["TOTALHD"]
        return config.get_cloud_config_value(
            "disk_size", vm_, __opts__, default=disk_size - swap
        )

    def _get_distribution_id(self, vm_):
        r"""
        Returns the distribution ID for a VM

        vm\_
            The VM to get the distribution ID for
        """
        distributions = self._query("avail", "distributions")["DATA"]
        vm_image_name = config.get_cloud_config_value("image", vm_, __opts__)

        distro_id = ""

        for distro in distributions:
            if vm_image_name == distro["LABEL"]:
                distro_id = distro["DISTRIBUTIONID"]
                return distro_id

        if not distro_id:
            raise SaltCloudNotFound(
                "The DistributionID for the '{}' profile could not be found.\nThe '{}'"
                " instance could not be provisioned. The following distributions are"
                " available:\n{}".format(
                    vm_image_name,
                    vm_["name"],
                    pprint.pprint(
                        sorted(
                            [
                                distro["LABEL"].encode(__salt_system_encoding__)
                                for distro in distributions
                            ]
                        )
                    ),
                )
            )

    def get_plan_id(self, kwargs=None):
        label = kwargs.get("label", None)
        if label is None:
            raise SaltCloudException("The get_plan_id function requires a 'label'.")
        return self._decode_linode_plan_label(label)

    def _get_ips(self, linode_id=None):
        """
        Returns public and private IP addresses.

        linode_id
            Limits the IP addresses returned to the specified Linode ID.
        """
        if linode_id:
            ips = self._query("linode", "ip.list", args={"LinodeID": linode_id})
        else:
            ips = self._query("linode", "ip.list")

        ips = ips["DATA"]
        ret = {}

        for item in ips:
            node_id = str(item["LINODEID"])
            if item["ISPUBLIC"] == 1:
                key = "public_ips"
            else:
                key = "private_ips"

            if ret.get(node_id) is None:
                ret.update({node_id: {"public_ips": [], "private_ips": []}})
            ret[node_id][key].append(item["IPADDRESS"])

        # If linode_id was specified, only return the ips, and not the
        # dictionary based on the linode ID as a key.
        if linode_id:
            _all_ips = {"public_ips": [], "private_ips": []}
            matching_id = ret.get(str(linode_id))
            if matching_id:
                _all_ips["private_ips"] = matching_id["private_ips"]
                _all_ips["public_ips"] = matching_id["public_ips"]

            ret = _all_ips

        return ret

    def _wait_for_job(self, linode_id, job_id, timeout=300, quiet=True):
        """
        Wait for a Job to return.

        linode_id
            The ID of the Linode to wait on. Required.

        job_id
            The ID of the job to wait for.

        timeout
            The amount of time to wait for a status to update.

        quiet
            Log status updates to debug logs when True. Otherwise, logs to info.
        """
        interval = 5
        iterations = int(timeout / interval)

        for i in range(0, iterations):
            jobs_result = self._query(
                "linode", "job.list", args={"LinodeID": linode_id}
            )["DATA"]
            if (
                jobs_result[0]["JOBID"] == job_id
                and jobs_result[0]["HOST_SUCCESS"] == 1
            ):
                return True

            time.sleep(interval)
            log.log(
                logging.INFO if not quiet else logging.DEBUG,
                "Still waiting on Job %s for Linode %s.",
                job_id,
                linode_id,
            )
        return False

    def _wait_for_status(self, linode_id, status=None, timeout=300, quiet=True):
        """
        Wait for a certain status from Linode.

        linode_id
            The ID of the Linode to wait on. Required.

        status
            The status to look for to update.

        timeout
            The amount of time to wait for a status to update.

        quiet
            Log status updates to debug logs when False. Otherwise, logs to info.
        """
        if status is None:
            status = self._get_status_id_by_name("brand_new")

        status_desc_waiting = self._get_status_descr_by_id(status)

        interval = 5
        iterations = int(timeout / interval)

        for i in range(0, iterations):
            result = get_linode(kwargs={"linode_id": linode_id})

            if result["STATUS"] == status:
                return True

            status_desc_result = self._get_status_descr_by_id(result["STATUS"])

            time.sleep(interval)
            log.log(
                logging.INFO if not quiet else logging.DEBUG,
                "Status for Linode %s is '%s', waiting for '%s'.",
                linode_id,
                status_desc_result,
                status_desc_waiting,
            )

        return False

    def _list_linodes(self, full=False):
        nodes = self._query("linode", "list")["DATA"]
        ips = self._get_ips()

        ret = {}
        for node in nodes:
            this_node = {}
            linode_id = str(node["LINODEID"])

            this_node["id"] = linode_id
            this_node["image"] = node["DISTRIBUTIONVENDOR"]
            this_node["name"] = node["LABEL"]
            this_node["size"] = node["TOTALRAM"]

            state = int(node["STATUS"])
            this_node["state"] = self._get_status_descr_by_id(state)

            for key, val in ips.items():
                if key == linode_id:
                    this_node["private_ips"] = val["private_ips"]
                    this_node["public_ips"] = val["public_ips"]

            if full:
                this_node["extra"] = node

            ret[node["LABEL"]] = this_node

        return ret

    def list_nodes(self):
        return self._list_linodes()

    def list_nodes_full(self):
        return self._list_linodes(full=True)

    def list_nodes_min(self):
        ret = {}
        nodes = self._query("linode", "list")["DATA"]

        for node in nodes:
            name = node["LABEL"]
            ret[name] = {
                "id": str(node["LINODEID"]),
                "state": self._get_status_descr_by_id(int(node["STATUS"])),
            }
        return ret

    def show_instance(self, name):
        node_id = self._get_linode_id_from_name(name)
        node_data = get_linode(kwargs={"linode_id": node_id})
        ips = self._get_ips(node_id)
        state = int(node_data["STATUS"])

        return {
            "id": node_data["LINODEID"],
            "image": node_data["DISTRIBUTIONVENDOR"],
            "name": node_data["LABEL"],
            "size": node_data["TOTALRAM"],
            "state": self._get_status_descr_by_id(state),
            "private_ips": ips["private_ips"],
            "public_ips": ips["public_ips"],
        }

    def show_pricing(self, kwargs=None):
        profile = __opts__["profiles"].get(kwargs["profile"], {})
        if not profile:
            raise SaltCloudNotFound("The requested profile was not found.")

        # Make sure the profile belongs to Linode
        provider = profile.get("provider", "0:0")
        comps = provider.split(":")
        if len(comps) < 2 or comps[1] != "linode":
            raise SaltCloudException("The requested profile does not belong to Linode.")

        plan_id = self.get_plan_id(kwargs={"label": profile["size"]})
        response = self._query("avail", "linodeplans", args={"PlanID": plan_id})[
            "DATA"
        ][0]

        ret = {}
        ret["per_hour"] = response["HOURLY"]
        ret["per_day"] = ret["per_hour"] * 24
        ret["per_week"] = ret["per_day"] * 7
        ret["per_month"] = response["PRICE"]
        ret["per_year"] = ret["per_month"] * 12
        return {profile["profile"]: ret}

    def _update_linode(self, linode_id, update_args=None):
        update_args.update({"LinodeID": linode_id})
        result = self._query("linode", "update", args=update_args)
        return self._clean_data(result)

    def _get_linode_id_from_name(self, name):
        node = self._get_linode_by_name(name)
        return node.get("LINODEID", None)

    def _get_linode_by_name(self, name):
        nodes = self._query("linode", "list")["DATA"]
        for node in nodes:
            if name == node["LABEL"]:
                return node

        raise SaltCloudNotFound(
            "The specified name, {}, could not be found.".format(name)
        )

    def _get_linode_by_id(self, linode_id):
        result = self._query("linode", "list", args={"LinodeID": linode_id})
        return result["DATA"][0]

    def start(self, name):
        node_id = self._get_linode_id_from_name(name)
        node = get_linode(kwargs={"linode_id": node_id})

        if node["STATUS"] == 1:
            return {
                "success": True,
                "action": "start",
                "state": "Running",
                "msg": "Machine already running",
            }

        response = self._query("linode", "boot", args={"LinodeID": node_id})["DATA"]
        if self._wait_for_job(node_id, response["JobID"]):
            return {"state": "Running", "action": "start", "success": True}
        else:
            return {"action": "start", "success": False}

    def stop(self, name):
        node_id = self._get_linode_id_from_name(name)
        node = get_linode(kwargs={"linode_id": node_id})

        if node["STATUS"] == 2:
            return {
                "success": True,
                "state": "Stopped",
                "msg": "Machine already stopped",
            }

        response = self._query("linode", "shutdown", args={"LinodeID": node_id})["DATA"]

        if self._wait_for_job(node_id, response["JobID"]):
            return {"state": "Stopped", "action": "stop", "success": True}
        return {"action": "stop", "success": False}

    def reboot(self, name):
        node_id = self._get_linode_id_from_name(name)
        response = self._query("linode", "reboot", args={"LinodeID": node_id})
        data = self._clean_data(response)
        reboot_jid = data["JobID"]

        if not self._wait_for_job(node_id, reboot_jid):
            log.error("Reboot failed for %s.", name)
            return False

        return data

    def _clean_data(self, api_response):
        """
        Returns the DATA response from a Linode API query as a single pre-formatted dictionary

        api_response
            The query to be cleaned.
        """
        data = {}
        data.update(api_response["DATA"])

        if not data:
            response_data = api_response["DATA"]
            data.update(response_data)

        return data

    def _get_status_descr_by_id(self, status_id):
        """
        Return linode status by ID

        status_id
            linode VM status ID
        """
        for status_name, status_data in LINODE_STATUS.items():
            if status_data["code"] == int(status_id):
                return status_data["descr"]
        return LINODE_STATUS.get(status_id, None)

    def _get_status_id_by_name(self, status_name):
        """
        Return linode status description by internalstatus name

        status_name
            internal linode VM status name
        """
        return LINODE_STATUS.get(status_name, {}).get("code", None)


def avail_images(call=None):
    """
    Return available Linode images.

    CLI Example:

    .. code-block:: bash

        salt-cloud --list-images my-linode-config
        salt-cloud -f avail_images my-linode-config
    """
    if call == "action":
        raise SaltCloudException(
            "The avail_images function must be called with -f or --function."
        )
    return _get_cloud_interface().avail_images()


def avail_locations(call=None):
    """
    Return available Linode datacenter locations.

    CLI Example:

    .. code-block:: bash

        salt-cloud --list-locations my-linode-config
        salt-cloud -f avail_locations my-linode-config
    """
    if call == "action":
        raise SaltCloudException(
            "The avail_locations function must be called with -f or --function."
        )
    return _get_cloud_interface().avail_locations()


def avail_sizes(call=None):
    """
    Return available Linode sizes.

    CLI Example:

    .. code-block:: bash

        salt-cloud --list-sizes my-linode-config
        salt-cloud -f avail_sizes my-linode-config
    """
    if call == "action":
        raise SaltCloudException(
            "The avail_locations function must be called with -f or --function."
        )
    return _get_cloud_interface().avail_sizes()


def boot(name=None, kwargs=None, call=None):
    """
    Boot a Linode.

    name
        The name of the Linode to boot. Can be used instead of ``linode_id``.

    linode_id
        The ID of the Linode to boot. If provided, will be used as an
        alternative to ``name`` and reduces the number of API calls to
        Linode by one. Will be preferred over ``name``.

    config_id
        The ID of the Config to boot. Required.

    check_running
        Defaults to True. If set to False, overrides the call to check if
        the VM is running before calling the linode.boot API call. Change
        ``check_running`` to True is useful during the boot call in the
        create function, since the new VM will not be running yet.

    Can be called as an action (which requires a name):

    .. code-block:: bash

        salt-cloud -a boot my-instance config_id=10

    ...or as a function (which requires either a name or linode_id):

    .. code-block:: bash

        salt-cloud -f boot my-linode-config name=my-instance config_id=10
        salt-cloud -f boot my-linode-config linode_id=1225876 config_id=10
    """
    if name is None and call == "action":
        raise SaltCloudSystemExit("The boot action requires a 'name'.")

    linode_id = kwargs.get("linode_id", None)
    config_id = kwargs.get("config_id", None)

    if call == "function":
        name = kwargs.get("name", None)

    if name is None and linode_id is None:
        raise SaltCloudSystemExit(
            "The boot function requires either a 'name' or a 'linode_id'."
        )

    return _get_cloud_interface().boot(name=name, kwargs=kwargs)


def clone(kwargs=None, call=None):
    """
    Clone a Linode.

    linode_id
        The ID of the Linode to clone. Required.

    location
        The location of the new Linode. Required.

    size
        The size of the new Linode (must be greater than or equal to the clone source). Required.

    datacenter_id
        The ID of the Datacenter where the Linode will be placed. Required for APIv3 usage.
        Deprecated. Use ``location`` instead.

    plan_id
        The ID of the plan (size) of the Linode. Required. Required for APIv3 usage.
        Deprecated. Use ``size`` instead.

    CLI Example:

    .. code-block:: bash

        salt-cloud -f clone my-linode-config linode_id=1234567 datacenter_id=2 plan_id=5
    """
    if call == "action":
        raise SaltCloudSystemExit(
            "The clone function must be called with -f or --function."
        )

    return _get_cloud_interface().clone(kwargs=kwargs)


def create(vm_):
    """
    Create a single Linode VM.
    """
    try:
        # Check for required profile parameters before sending any API calls.
        if (
            vm_["profile"]
            and config.is_profile_configured(
                __opts__,
                _get_active_provider_name() or "linode",
                vm_["profile"],
                vm_=vm_,
            )
            is False
        ):
            return False
    except AttributeError:
        pass

    return _get_cloud_interface().create(vm_)


def create_config(kwargs=None, call=None):
    """
    Creates a Linode Configuration Profile.

    name
        The name of the VM to create the config for.

    linode_id
        The ID of the Linode to create the configuration for.

    root_disk_id
        The Root Disk ID to be used for this config.

    swap_disk_id
        The Swap Disk ID to be used for this config.

    data_disk_id
        The Data Disk ID to be used for this config.

    .. versionadded:: 2016.3.0

    kernel_id
        The ID of the kernel to use for this configuration profile.
    """
    if call == "action":
        raise SaltCloudSystemExit(
            "The create_config function must be called with -f or --function."
        )
    return _get_cloud_interface().create_config(kwargs=kwargs)


def destroy(name, call=None):
    """
    Destroys a Linode by name.

    name
        The name of VM to be be destroyed.

    CLI Example:

    .. code-block:: bash

        salt-cloud -d vm_name
    """
    if call == "function":
        raise SaltCloudException(
            "The destroy action must be called with -d, --destroy, -a or --action."
        )
    return _get_cloud_interface().destroy(name)


def get_config_id(kwargs=None, call=None):
    """
    Returns a config_id for a given linode.

    .. versionadded:: 2015.8.0

    name
        The name of the Linode for which to get the config_id. Can be used instead
        of ``linode_id``.

    linode_id
        The ID of the Linode for which to get the config_id. Can be used instead
        of ``name``.

    CLI Example:

    .. code-block:: bash

        salt-cloud -f get_config_id my-linode-config name=my-linode
        salt-cloud -f get_config_id my-linode-config linode_id=1234567
    """
    if call == "action":
        raise SaltCloudException(
            "The get_config_id function must be called with -f or --function."
        )
    return _get_cloud_interface().get_config_id(kwargs=kwargs)


def get_linode(kwargs=None, call=None):
    """
    Returns data for a single named Linode.

    name
        The name of the Linode for which to get data. Can be used instead
        ``linode_id``. Note this will induce an additional API call
        compared to using ``linode_id``.

    linode_id
        The ID of the Linode for which to get data. Can be used instead of
        ``name``.

    CLI Example:

    .. code-block:: bash

        salt-cloud -f get_linode my-linode-config name=my-instance
        salt-cloud -f get_linode my-linode-config linode_id=1234567
    """
    if call == "action":
        raise SaltCloudSystemExit(
            "The get_linode function must be called with -f or --function."
        )
    return _get_cloud_interface().get_linode(kwargs=kwargs)


def get_plan_id(kwargs=None, call=None):
    """
    Returns the Linode Plan ID.

    label
        The label, or name, of the plan to get the ID from.

    CLI Example:

    .. code-block:: bash

        salt-cloud -f get_plan_id linode label="Nanode 1GB"
        salt-cloud -f get_plan_id linode label="Linode 2GB"
    """
    if call == "action":
        raise SaltCloudException(
            "The show_instance action must be called with -f or --function."
        )
    return _get_cloud_interface().get_plan_id(kwargs=kwargs)


def list_nodes(call=None):
    """
    Returns a list of linodes, keeping only a brief listing.

    CLI Example:

    .. code-block:: bash

        salt-cloud -Q
        salt-cloud --query
        salt-cloud -f list_nodes my-linode-config

    .. note::

        The ``image`` label only displays information about the VM's distribution vendor,
        such as "Debian" or "RHEL" and does not display the actual image name. This is
        due to a limitation of the Linode API.
    """
    if call == "action":
        raise SaltCloudException(
            "The list_nodes function must be called with -f or --function."
        )
    return _get_cloud_interface().list_nodes()


def list_nodes_full(call=None):
    """
    List linodes, with all available information.

    CLI Example:

    .. code-block:: bash

        salt-cloud -F
        salt-cloud --full-query
        salt-cloud -f list_nodes_full my-linode-config

    .. note::

        The ``image`` label only displays information about the VM's distribution vendor,
        such as "Debian" or "RHEL" and does not display the actual image name. This is
        due to a limitation of the Linode API.
    """
    if call == "action":
        raise SaltCloudException(
            "The list_nodes_full function must be called with -f or --function."
        )
    return _get_cloud_interface().list_nodes_full()


def list_nodes_min(call=None):
    """
    Return a list of the VMs that are on the provider. Only a list of VM names and
    their state is returned. This is the minimum amount of information needed to
    check for existing VMs.

    .. versionadded:: 2015.8.0

    CLI Example:

    .. code-block:: bash

        salt-cloud -f list_nodes_min my-linode-config
        salt-cloud --function list_nodes_min my-linode-config
    """
    if call == "action":
        raise SaltCloudSystemExit(
            "The list_nodes_min function must be called with -f or --function."
        )
    return _get_cloud_interface().list_nodes_min()


def list_nodes_select(call=None):
    """
    Return a list of the VMs that are on the provider, with select fields.
    """
    return _get_cloud_interface().list_nodes_select(call)


def reboot(name, call=None):
    """
    Reboot a linode.

    .. versionadded:: 2015.8.0

    name
        The name of the VM to reboot.

    CLI Example:

    .. code-block:: bash

        salt-cloud -a reboot vm_name
    """
    if call != "action":
        raise SaltCloudException(
            "The show_instance action must be called with -a or --action."
        )
    return _get_cloud_interface().reboot(name)


def show_instance(name, call=None):
    """
    Displays details about a particular Linode VM. Either a name or a linode_id must
    be provided.

    .. versionadded:: 2015.8.0

    name
        The name of the VM for which to display details.

    CLI Example:

    .. code-block:: bash

        salt-cloud -a show_instance vm_name

    .. note::

        The ``image`` label only displays information about the VM's distribution vendor,
        such as "Debian" or "RHEL" and does not display the actual image name. This is
        due to a limitation of the Linode API.
    """
    if call != "action":
        raise SaltCloudException(
            "The show_instance action must be called with -a or --action."
        )
    return _get_cloud_interface().show_instance(name)


def show_pricing(kwargs=None, call=None):
    """
    Show pricing for a particular profile. This is only an estimate, based on
    unofficial pricing sources.

    .. versionadded:: 2015.8.0

    CLI Example:

    .. code-block:: bash

        salt-cloud -f show_pricing my-linode-config profile=my-linode-profile
    """
    if call != "function":
        raise SaltCloudException(
            "The show_instance action must be called with -f or --function."
        )
    return _get_cloud_interface().show_pricing(kwargs=kwargs)


def start(name, call=None):
    """
    Start a VM in Linode.

    name
        The name of the VM to start.

    CLI Example:

    .. code-block:: bash

        salt-cloud -a stop vm_name
    """
    if call != "action":
        raise SaltCloudException("The start action must be called with -a or --action.")
    return _get_cloud_interface().start(name)


def stop(name, call=None):
    """
    Stop a VM in Linode.

    name
        The name of the VM to stop.

    CLI Example:

    .. code-block:: bash

        salt-cloud -a stop vm_name
    """
    if call != "action":
        raise SaltCloudException("The stop action must be called with -a or --action.")
    return _get_cloud_interface().stop(name)
