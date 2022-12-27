"""
Openstack Cloud Driver
======================

:depends: `shade>=1.19.0 <https://pypi.python.org/pypi/shade>`_

OpenStack is an open source project that is in use by a number a cloud
providers, each of which have their own ways of using it.

This OpenStack driver uses a the shade python module which is managed by the
OpenStack Infra team.  This module is written to handle all the different
versions of different OpenStack tools for salt, so most commands are just passed
over to the module to handle everything.

Provider
--------

There are two ways to configure providers for this driver.  The first one is to
just let shade handle everything, and configure using os-client-config_ and
setting up `/etc/openstack/clouds.yml`.

.. code-block:: yaml

    clouds:
      democloud:
        region_name: RegionOne
        auth:
          username: 'demo'
          password: secret
          project_name: 'demo'
          auth_url: 'http://openstack/identity'

And then this can be referenced in the salt provider based on the `democloud`
name.

.. code-block:: yaml

    myopenstack:
      driver: openstack
      cloud: democloud
      region_name: RegionOne

This allows for just using one configuration for salt-cloud and for any other
openstack tools which are all using `/etc/openstack/clouds.yml`

The other method allows for specifying everything in the provider config,
instead of using the extra configuration file.  This will allow for passing
salt-cloud configs only through pillars for minions without having to write a
clouds.yml file on each minion.abs

.. code-block:: yaml

    myopenstack:
      driver: openstack
      region_name: RegionOne
      auth:
        username: 'demo'
        password: secret
        project_name: 'demo'
        user_domain_name: default,
        project_domain_name: default,
        auth_url: 'http://openstack/identity'

Or if you need to use a profile to setup some extra stuff, it can be passed as a
`profile` to use any of the vendor_ config options.

.. code-block:: yaml

    myrackspace:
      driver: openstack
      profile: rackspace
      auth:
        username: rackusername
        api_key: myapikey
      region_name: ORD
      auth_type: rackspace_apikey

And this will pull in the profile for rackspace and setup all the correct
options for the auth_url and different api versions for services.


Profile
-------

Most of the options for building servers are just passed on to the
create_server_ function from shade.

The salt specific ones are:

  - ssh_key_file: The path to the ssh key that should be used to login to the machine to bootstrap it
  - ssh_key_file: The name of the keypair in openstack
  - userdata_template: The renderer to use if the userdata is a file that is templated. Default: False
  - ssh_interface: The interface to use to login for bootstrapping: public_ips, private_ips, floating_ips, fixed_ips
  - ignore_cidr: Specify a CIDR range of unreachable private addresses for salt to ignore when connecting

.. code-block:: yaml

    centos:
      provider: myopenstack
      image: CentOS 7
      size: ds1G
      ssh_key_name: mykey
      ssh_key_file: /root/.ssh/id_rsa

This is the minimum setup required.

If metadata is set to make sure that the host has finished setting up the
`wait_for_metadata` can be set.

.. code-block:: yaml

    centos:
      provider: myopenstack
      image: CentOS 7
      size: ds1G
      ssh_key_name: mykey
      ssh_key_file: /root/.ssh/id_rsa
      meta:
        build_config: rack_user_only
      wait_for_metadata:
        rax_service_level_automation: Complete
        rackconnect_automation_status: DEPLOYED

If your OpenStack instances only have private IP addresses and a CIDR range of
private addresses are not reachable from the salt-master, you may set your
preference to have Salt ignore it:

.. code-block:: yaml

    my-openstack-config:
      ignore_cidr: 192.168.0.0/16

Anything else from the create_server_ docs can be passed through here.

- **image**: Image dict, name or ID to boot with. image is required
  unless boot_volume is given.
- **flavor**: Flavor dict, name or ID to boot onto.
- **auto_ip**: Whether to take actions to find a routable IP for
  the server. (defaults to True)
- **ips**: List of IPs to attach to the server (defaults to None)
- **ip_pool**: Name of the network or floating IP pool to get an
  address from. (defaults to None)
- **root_volume**: Name or ID of a volume to boot from
  (defaults to None - deprecated, use boot_volume)
- **boot_volume**: Name or ID of a volume to boot from
  (defaults to None)
- **terminate_volume**: If booting from a volume, whether it should
  be deleted when the server is destroyed.
  (defaults to False)
- **volumes**: (optional) A list of volumes to attach to the server
- **meta**: (optional) A dict of arbitrary key/value metadata to
  store for this server. Both keys and values must be
  <=255 characters.
- **files**: (optional, deprecated) A dict of files to overwrite
  on the server upon boot. Keys are file names (i.e.
  ``/etc/passwd``) and values
  are the file contents (either as a string or as a
  file-like object). A maximum of five entries is allowed,
  and each file must be 10k or less.
- **reservation_id**: a UUID for the set of servers being requested.
- **min_count**: (optional extension) The minimum number of
  servers to launch.
- **max_count**: (optional extension) The maximum number of
  servers to launch.
- **security_groups**: A list of security group names
- **userdata**: user data to pass to be exposed by the metadata
  server this can be a file type object as well or a
  string.
- **key_name**: (optional extension) name of previously created
  keypair to inject into the instance.
- **availability_zone**: Name of the availability zone for instance
  placement.
- **block_device_mapping**: (optional) A list of dictionaries representing
  legacy block device mappings for this server. See
  `documentation <https://docs.openstack.org/nova/latest/user/block-device-mapping.html#block-device-mapping-v1-aka-legacy>`_
  for details.
- **block_device_mapping_v2**: (optional) A list of dictionaries representing
  block device mappings for this server. See
  `v2 documentation <https://docs.openstack.org/nova/latest/user/block-device-mapping.html#block-device-mapping-v2>`_
  for details.
- **nics**:  (optional extension) an ordered list of nics to be
  added to this server, with information about
  connected networks, fixed IPs, port etc.
- **scheduler_hints**: (optional extension) arbitrary key-value pairs
  specified by the client to help boot an instance
- **config_drive**: (optional extension) value for config drive
  either boolean, or volume-id
- **disk_config**: (optional extension) control how the disk is
  partitioned when the server is created.  possible
  values are 'AUTO' or 'MANUAL'.
- **admin_pass**: (optional extension) add a user supplied admin
  password.
- **timeout**: (optional) Seconds to wait, defaults to 60.
  See the ``wait`` parameter.
- **reuse_ips**: (optional) Whether to attempt to reuse pre-existing
  floating ips should a floating IP be
  needed (defaults to True)
- **network**: (optional) Network dict or name or ID to attach the
  server to.  Mutually exclusive with the nics parameter.
  Can also be be a list of network names or IDs or
  network dicts.
- **boot_from_volume**: Whether to boot from volume. 'boot_volume'
  implies True, but boot_from_volume=True with
  no boot_volume is valid and will create a
  volume from the image and use that.
- **volume_size**: When booting an image from volume, how big should
  the created volume be? Defaults to 50.
- **nat_destination**: Which network should a created floating IP
  be attached to, if it's not possible to
  infer from the cloud's configuration.
  (Optional, defaults to None)
- **group**: ServerGroup dict, name or id to boot the server in.
  If a group is provided in both scheduler_hints and in
  the group param, the group param will win.
  (Optional, defaults to None)

.. note::

    If there is anything added, that is not in this list, it can be added to an `extras`
    dictionary for the profile, and that will be to the create_server function.

.. _create_server: https://docs.openstack.org/shade/latest/user/usage.html#shade.OpenStackCloud.create_server
.. _vendor: https://docs.openstack.org/os-client-config/latest/user/vendor-support.html
.. _os-client-config: https://docs.openstack.org/os-client-config/latest/user/configuration.html#config-files
"""

import copy
import logging
import os
import pprint
import socket

import salt.config as config
from salt.exceptions import (
    SaltCloudConfigError,
    SaltCloudExecutionFailure,
    SaltCloudExecutionTimeout,
    SaltCloudSystemExit,
)
from salt.utils.versions import Version

try:
    import os_client_config
    import shade
    import shade.exc
    import shade.openstackcloud

    HAS_SHADE = (
        Version(shade.__version__) >= Version("1.19.0"),
        "Please install newer version of shade: >= 1.19.0",
    )
except ImportError:
    HAS_SHADE = (False, "Install pypi module shade >= 1.19.0")


log = logging.getLogger(__name__)
__virtualname__ = "openstack"


def __virtual__():
    """
    Check for OpenStack dependencies
    """
    if get_configured_provider() is False:
        return False
    if get_dependencies() is False:
        return HAS_SHADE
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
    provider = config.is_provider_configured(
        __opts__,
        _get_active_provider_name() or __virtualname__,
        ("auth", "region_name"),
    )
    if provider:
        return provider

    return config.is_provider_configured(
        __opts__,
        _get_active_provider_name() or __virtualname__,
        ("cloud", "region_name"),
    )


def get_dependencies():
    """
    Warn if dependencies aren't met.
    """
    if not HAS_SHADE:
        log.warning('"shade" not found')
        return False
    elif hasattr(HAS_SHADE, "__len__") and not HAS_SHADE[0]:
        log.warning(HAS_SHADE[1])
        return False
    deps = {"shade": HAS_SHADE[0], "os_client_config": HAS_SHADE[0]}
    return config.check_driver_dependencies(__virtualname__, deps)


def preferred_ip(vm_, ips):
    """
    Return either an 'ipv4' (default) or 'ipv6' address depending on 'protocol' option.
    The list of 'ipv4' IPs is filtered by ignore_cidr() to remove any unreachable private addresses.
    """
    proto = config.get_cloud_config_value(
        "protocol", vm_, __opts__, default="ipv4", search_global=False
    )

    family = socket.AF_INET
    if proto == "ipv6":
        family = socket.AF_INET6
    for ip in ips:
        ignore_ip = ignore_cidr(vm_, ip)
        if ignore_ip:
            continue
        try:
            socket.inet_pton(family, ip)
            return ip
        except Exception:  # pylint: disable=broad-except
            continue
    return False


def ignore_cidr(vm_, ip):
    """
    Return True if we are to ignore the specified IP.
    """
    from ipaddress import ip_address, ip_network

    cidrs = config.get_cloud_config_value(
        "ignore_cidr", vm_, __opts__, default=[], search_global=False
    )
    if cidrs and isinstance(cidrs, str):
        cidrs = [cidrs]
    for cidr in cidrs or []:
        if ip_address(ip) in ip_network(cidr):
            log.warning("IP %r found within %r; ignoring it.", ip, cidr)
            return True

    return False


def ssh_interface(vm_):
    """
    Return the ssh_interface type to connect to. Either 'public_ips' (default)
    or 'private_ips'.
    """
    return config.get_cloud_config_value(
        "ssh_interface", vm_, __opts__, default="public_ips", search_global=False
    )


def get_conn():
    """
    Return a conn object for the passed VM data
    """
    if _get_active_provider_name() in __context__:
        return __context__[_get_active_provider_name()]
    vm_ = get_configured_provider()
    profile = vm_.pop("profile", None)
    if profile is not None:
        vm_ = __utils__["dictupdate.update"](
            os_client_config.vendors.get_profile(profile), vm_
        )
    conn = shade.openstackcloud.OpenStackCloud(cloud_config=None, **vm_)
    if _get_active_provider_name() is not None:
        __context__[_get_active_provider_name()] = conn
    return conn


def list_nodes(conn=None, call=None):
    """
    Return a list of VMs

    CLI Example

    .. code-block:: bash

        salt-cloud -f list_nodes myopenstack

    """
    if call == "action":
        raise SaltCloudSystemExit(
            "The list_nodes function must be called with -f or --function."
        )
    ret = {}
    for node, info in list_nodes_full(conn=conn).items():
        for key in (
            "id",
            "name",
            "size",
            "state",
            "private_ips",
            "public_ips",
            "floating_ips",
            "fixed_ips",
            "image",
        ):
            ret.setdefault(node, {}).setdefault(key, info.get(key))

    return ret


def list_nodes_min(conn=None, call=None):
    """
    Return a list of VMs with minimal information

    CLI Example

    .. code-block:: bash

        salt-cloud -f list_nodes_min myopenstack

    """
    if call == "action":
        raise SaltCloudSystemExit(
            "The list_nodes_min function must be called with -f or --function."
        )
    if conn is None:
        conn = get_conn()
    ret = {}
    for node in conn.list_servers(bare=True):
        ret[node.name] = {"id": node.id, "state": node.status}
    return ret


def _get_ips(node, addr_type="public"):
    ret = []
    for _, interface in node.addresses.items():
        for addr in interface:
            if addr_type in ("floating", "fixed") and addr_type == addr.get(
                "OS-EXT-IPS:type"
            ):
                ret.append(addr["addr"])
            elif addr_type == "public" and __utils__["cloud.is_public_ip"](
                addr["addr"]
            ):
                ret.append(addr["addr"])
            elif addr_type == "private" and not __utils__["cloud.is_public_ip"](
                addr["addr"]
            ):
                ret.append(addr["addr"])
    return ret


def list_nodes_full(conn=None, call=None):
    """
    Return a list of VMs with all the information about them

    CLI Example

    .. code-block:: bash

        salt-cloud -f list_nodes_full myopenstack

    """
    if call == "action":
        raise SaltCloudSystemExit(
            "The list_nodes_full function must be called with -f or --function."
        )
    if conn is None:
        conn = get_conn()
    ret = {}
    for node in conn.list_servers(detailed=True):
        ret[node.name] = dict(node)
        ret[node.name]["id"] = node.id
        ret[node.name]["name"] = node.name
        ret[node.name]["size"] = node.flavor.name
        ret[node.name]["state"] = node.status
        ret[node.name]["private_ips"] = _get_ips(node, "private")
        ret[node.name]["public_ips"] = _get_ips(node, "public")
        ret[node.name]["floating_ips"] = _get_ips(node, "floating")
        ret[node.name]["fixed_ips"] = _get_ips(node, "fixed")
        if isinstance(node.image, str):
            ret[node.name]["image"] = node.image
        else:
            ret[node.name]["image"] = getattr(
                conn.get_image(node.image.id), "name", node.image.id
            )
    return ret


def list_nodes_select(conn=None, call=None):
    """
    Return a list of VMs with the fields from `query.selection`

    CLI Example

    .. code-block:: bash

        salt-cloud -f list_nodes_full myopenstack

    """
    if call == "action":
        raise SaltCloudSystemExit(
            "The list_nodes_select function must be called with -f or --function."
        )
    return __utils__["cloud.list_nodes_select"](
        list_nodes(conn, "function"), __opts__["query.selection"], call
    )


def show_instance(name, conn=None, call=None):
    """
    Get VM on this OpenStack account

    name

        name of the instance

    CLI Example

    .. code-block:: bash

        salt-cloud -a show_instance myserver

    """
    if call != "action":
        raise SaltCloudSystemExit(
            "The show_instance action must be called with -a or --action."
        )
    if conn is None:
        conn = get_conn()

    node = conn.get_server(name, bare=True)
    ret = dict(node)
    ret["id"] = node.id
    ret["name"] = node.name
    ret["size"] = conn.get_flavor(node.flavor.id).name
    ret["state"] = node.status
    ret["private_ips"] = _get_ips(node, "private")
    ret["public_ips"] = _get_ips(node, "public")
    ret["floating_ips"] = _get_ips(node, "floating")
    ret["fixed_ips"] = _get_ips(node, "fixed")
    if isinstance(node.image, str):
        ret["image"] = node.image
    else:
        ret["image"] = getattr(conn.get_image(node.image.id), "name", node.image.id)
    return ret


def avail_images(conn=None, call=None):
    """
    List available images for OpenStack

    CLI Example

    .. code-block:: bash

        salt-cloud -f avail_images myopenstack
        salt-cloud --list-images myopenstack

    """
    if call == "action":
        raise SaltCloudSystemExit(
            "The avail_images function must be called with "
            "-f or --function, or with the --list-images option"
        )
    if conn is None:
        conn = get_conn()
    return conn.list_images()


def avail_sizes(conn=None, call=None):
    """
    List available sizes for OpenStack

    CLI Example

    .. code-block:: bash

        salt-cloud -f avail_sizes myopenstack
        salt-cloud --list-sizes myopenstack

    """
    if call == "action":
        raise SaltCloudSystemExit(
            "The avail_sizes function must be called with "
            "-f or --function, or with the --list-sizes option"
        )
    if conn is None:
        conn = get_conn()
    return conn.list_flavors()


def list_networks(conn=None, call=None):
    """
    List networks for OpenStack

    CLI Example

    .. code-block:: bash

        salt-cloud -f list_networks myopenstack

    """
    if call == "action":
        raise SaltCloudSystemExit(
            "The list_networks function must be called with -f or --function"
        )
    if conn is None:
        conn = get_conn()
    return conn.list_networks()


def list_subnets(conn=None, call=None, kwargs=None):
    """
    List subnets in a virtual network

    network
        network to list subnets of

    .. code-block:: bash

        salt-cloud -f list_subnets myopenstack network=salt-net

    """
    if call == "action":
        raise SaltCloudSystemExit(
            "The list_subnets function must be called with -f or --function."
        )
    if conn is None:
        conn = get_conn()
    if kwargs is None or (isinstance(kwargs, dict) and "network" not in kwargs):
        raise SaltCloudSystemExit("A `network` must be specified")
    return conn.list_subnets(filters={"network": kwargs["network"]})


def _clean_create_kwargs(**kwargs):
    """
    Sanitize kwargs to be sent to create_server
    """
    VALID_OPTS = {
        "name": (str,),
        "image": (str,),
        "flavor": (str,),
        "auto_ip": bool,
        "ips": list,
        "ip_pool": (str,),
        "root_volume": (str,),
        "boot_volume": (str,),
        "terminate_volume": bool,
        "volumes": list,
        "meta": dict,
        "files": dict,
        "reservation_id": (str,),
        "security_groups": list,
        "key_name": (str,),
        "availability_zone": (str,),
        "block_device_mapping": list,
        "block_device_mapping_v2": list,
        "nics": list,
        "scheduler_hints": dict,
        "config_drive": bool,
        "disk_config": (str,),  # AUTO or MANUAL
        "admin_pass": (str,),
        "wait": bool,
        "timeout": int,
        "reuse_ips": bool,
        "network": (dict, list),
        "boot_from_volume": bool,
        "volume_size": int,
        "nat_destination": (str,),
        "group": (str,),
        "userdata": (str,),
    }
    extra = kwargs.pop("extra", {})
    for key, value in kwargs.copy().items():
        if key in VALID_OPTS:
            if isinstance(value, VALID_OPTS[key]):
                continue
            log.error("Error %s: %s is not of type %s", key, value, VALID_OPTS[key])
        kwargs.pop(key)
    return __utils__["dictupdate.update"](kwargs, extra)


def request_instance(vm_, conn=None, call=None):
    """
    Request an instance to be built
    """
    if call == "function":
        # Technically this function may be called other ways too, but it
        # definitely cannot be called with --function.
        raise SaltCloudSystemExit(
            "The request_instance action must be called with -a or --action."
        )
    kwargs = copy.deepcopy(vm_)
    log.info("Creating Cloud VM %s", vm_["name"])
    __utils__["cloud.check_name"](vm_["name"], "a-zA-Z0-9._-")
    if conn is None:
        conn = get_conn()
    userdata = config.get_cloud_config_value(
        "userdata", vm_, __opts__, search_global=False, default=None
    )
    if userdata is not None and os.path.isfile(userdata):
        try:
            with __utils__["files.fopen"](userdata, "r") as fp_:
                kwargs["userdata"] = __utils__["cloud.userdata_template"](
                    __opts__, vm_, fp_.read()
                )
        except Exception as exc:  # pylint: disable=broad-except
            log.exception("Failed to read userdata from %s: %s", userdata, exc)
    if "size" in kwargs:
        kwargs["flavor"] = kwargs.pop("size")
    kwargs["key_name"] = config.get_cloud_config_value(
        "ssh_key_name", vm_, __opts__, search_global=False, default=None
    )
    kwargs["wait"] = True
    try:
        conn.create_server(**_clean_create_kwargs(**kwargs))
    except shade.exc.OpenStackCloudException as exc:
        log.error("Error creating server %s: %s", vm_["name"], exc)
        destroy(vm_["name"], conn=conn, call="action")
        raise SaltCloudSystemExit(str(exc))

    return show_instance(vm_["name"], conn=conn, call="action")


def create(vm_):
    """
    Create a single VM from a data dict
    """
    deploy = config.get_cloud_config_value("deploy", vm_, __opts__)
    key_filename = config.get_cloud_config_value(
        "ssh_key_file", vm_, __opts__, search_global=False, default=None
    )
    if key_filename is not None and not os.path.isfile(key_filename):
        raise SaltCloudConfigError(
            "The defined ssh_key_file '{}' does not exist".format(key_filename)
        )

    vm_["key_filename"] = key_filename

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
    conn = get_conn()

    if "instance_id" in vm_:
        # This was probably created via another process, and doesn't have
        # things like salt keys created yet, so let's create them now.
        if "pub_key" not in vm_ and "priv_key" not in vm_:
            log.debug("Generating minion keys for '%s'", vm_["name"])
            vm_["priv_key"], vm_["pub_key"] = __utils__["cloud.gen_keys"](
                config.get_cloud_config_value("keysize", vm_, __opts__)
            )
    else:
        # Put together all of the information required to request the instance,
        # and then fire off the request for it
        request_instance(conn=conn, call="action", vm_=vm_)
    data = show_instance(vm_.get("instance_id", vm_["name"]), conn=conn, call="action")
    log.debug("VM is now running")

    def __query_node(vm_):
        data = show_instance(vm_["name"], conn=conn, call="action")
        if "wait_for_metadata" in vm_:
            for key, value in vm_.get("wait_for_metadata", {}).items():
                log.debug("Waiting for metadata: %s=%s", key, value)
                if data["metadata"].get(key, None) != value:
                    log.debug(
                        "Metadata is not ready: %s=%s", key, data["metadata"].get(key)
                    )
                    return False
        return preferred_ip(vm_, data[ssh_interface(vm_)])

    try:
        ip_address = __utils__["cloud.wait_for_fun"](__query_node, vm_=vm_)
    except (SaltCloudExecutionTimeout, SaltCloudExecutionFailure) as exc:
        try:
            # It might be already up, let's destroy it!
            destroy(vm_["name"])
        except SaltCloudSystemExit:
            pass
        finally:
            raise SaltCloudSystemExit(str(exc))
    log.debug("Using IP address %s", ip_address)

    salt_interface = __utils__["cloud.get_salt_interface"](vm_, __opts__)
    salt_ip_address = preferred_ip(vm_, data[salt_interface])
    log.debug("Salt interface set to: %s", salt_ip_address)

    if not ip_address:
        raise SaltCloudSystemExit("A valid IP address was not found")

    vm_["ssh_host"] = ip_address
    vm_["salt_host"] = salt_ip_address

    ret = __utils__["cloud.bootstrap"](vm_, __opts__)
    ret.update(data)

    log.info("Created Cloud VM '%s'", vm_["name"])
    log.debug("'%s' VM creation details:\n%s", vm_["name"], pprint.pformat(data))

    event_data = {
        "name": vm_["name"],
        "profile": vm_["profile"],
        "provider": vm_["driver"],
        "instance_id": data["id"],
        "floating_ips": data["floating_ips"],
        "fixed_ips": data["fixed_ips"],
        "private_ips": data["private_ips"],
        "public_ips": data["public_ips"],
    }

    __utils__["cloud.fire_event"](
        "event",
        "created instance",
        "salt/cloud/{}/created".format(vm_["name"]),
        args=__utils__["cloud.filter_event"]("created", event_data, list(event_data)),
        sock_dir=__opts__["sock_dir"],
        transport=__opts__["transport"],
    )
    __utils__["cloud.cachedir_index_add"](
        vm_["name"], vm_["profile"], "nova", vm_["driver"]
    )
    return ret


def destroy(name, conn=None, call=None):
    """
    Delete a single VM
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

    if not conn:
        conn = get_conn()
    node = show_instance(name, conn=conn, call="action")
    log.info("Destroying VM: %s", name)
    ret = conn.delete_server(name)
    if ret:
        log.info("Destroyed VM: %s", name)
        # Fire destroy action
        __utils__["cloud.fire_event"](
            "event",
            "destroyed instance",
            "salt/cloud/{}/destroyed".format(name),
            args={"name": name},
            sock_dir=__opts__["sock_dir"],
            transport=__opts__["transport"],
        )
        if __opts__.get("delete_sshkeys", False) is True:
            __utils__["cloud.remove_sshkey"](
                getattr(node, __opts__.get("ssh_interface", "public_ips"))[0]
            )
        if __opts__.get("update_cachedir", False) is True:
            __utils__["cloud.delete_minion_cachedir"](
                name, _get_active_provider_name().split(":")[0], __opts__
            )
        __utils__["cloud.cachedir_index_del"](name)
        return True

    log.error("Failed to Destroy VM: %s", name)
    return False


def call(conn=None, call=None, kwargs=None):
    """
    Call function from shade.

    func

        function to call from shade.openstackcloud library

    CLI Example

    .. code-block:: bash

        salt-cloud -f call myopenstack func=list_images
        t sujksalt-cloud -f call myopenstack func=create_network name=mysubnet
    """
    if call == "action":
        raise SaltCloudSystemExit(
            "The call function must be called with -f or --function."
        )

    if "func" not in kwargs:
        raise SaltCloudSystemExit("No `func` argument passed")

    if conn is None:
        conn = get_conn()

    func = kwargs.pop("func")
    for key, value in kwargs.items():
        try:
            kwargs[key] = __utils__["json.loads"](value)
        except ValueError:
            continue
    try:
        return getattr(conn, func)(**kwargs)
    except shade.exc.OpenStackCloudException as exc:
        log.error("Error running %s: %s", func, exc)
        raise SaltCloudSystemExit(str(exc))
