"""
Proxmox Cloud Module
======================

.. versionadded:: 2014.7.0

The Proxmox cloud module is used to control access to cloud providers using
the Proxmox system (KVM / OpenVZ / LXC).

Set up the cloud configuration at ``/etc/salt/cloud.providers`` or
 ``/etc/salt/cloud.providers.d/proxmox.conf``:

.. code-block:: yaml

    my-proxmox-config:
      # Proxmox account information
      user: myuser@pam or myuser@pve
      password: mypassword
      url: hypervisor.domain.tld
      port: 8006
      driver: proxmox
      verify_ssl: True

:maintainer: Frank Klaassen <frank@cloudright.nl>
:depends: requests >= 2.2.1
:depends: IPy >= 0.81
"""

import logging
import pprint
import re
import time

import salt.config as config
import salt.utils.cloud
import salt.utils.json
from salt.exceptions import (
    SaltCloudExecutionFailure,
    SaltCloudExecutionTimeout,
    SaltCloudSystemExit,
)

try:
    import requests

    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False

try:
    from IPy import IP

    HAS_IPY = True
except ImportError:
    HAS_IPY = False

# Get logging started
log = logging.getLogger(__name__)

__virtualname__ = "proxmox"


def __virtual__():
    """
    Check for PROXMOX configurations
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
        __opts__, _get_active_provider_name() or __virtualname__, ("user",)
    )


def get_dependencies():
    """
    Warn if dependencies aren't met.
    """
    deps = {"requests": HAS_REQUESTS, "IPy": HAS_IPY}
    return config.check_driver_dependencies(__virtualname__, deps)


url = None
port = None
ticket = None
csrf = None
verify_ssl = None
api = None


def _authenticate():
    """
    Retrieve CSRF and API tickets for the Proxmox API
    """
    global url, port, ticket, csrf, verify_ssl
    url = config.get_cloud_config_value(
        "url", get_configured_provider(), __opts__, search_global=False
    )
    port = config.get_cloud_config_value(
        "port", get_configured_provider(), __opts__, default=8006, search_global=False
    )
    username = (
        config.get_cloud_config_value(
            "user", get_configured_provider(), __opts__, search_global=False
        ),
    )
    passwd = config.get_cloud_config_value(
        "password", get_configured_provider(), __opts__, search_global=False
    )
    verify_ssl = config.get_cloud_config_value(
        "verify_ssl",
        get_configured_provider(),
        __opts__,
        default=True,
        search_global=False,
    )

    connect_data = {"username": username, "password": passwd}
    full_url = "https://{}:{}/api2/json/access/ticket".format(url, port)

    returned_data = requests.post(full_url, verify=verify_ssl, data=connect_data).json()

    ticket = {"PVEAuthCookie": returned_data["data"]["ticket"]}
    csrf = str(returned_data["data"]["CSRFPreventionToken"])


def query(conn_type, option, post_data=None):
    """
    Execute the HTTP request to the API
    """
    if ticket is None or csrf is None or url is None:
        log.debug("Not authenticated yet, doing that now..")
        _authenticate()

    full_url = "https://{}:{}/api2/json/{}".format(url, port, option)

    log.debug("%s: %s (%s)", conn_type, full_url, post_data)

    httpheaders = {
        "Accept": "application/json",
        "Content-Type": "application/x-www-form-urlencoded",
        "User-Agent": "salt-cloud-proxmox",
    }

    if conn_type == "post":
        httpheaders["CSRFPreventionToken"] = csrf
        response = requests.post(
            full_url,
            verify=verify_ssl,
            data=post_data,
            cookies=ticket,
            headers=httpheaders,
        )
    elif conn_type == "put":
        httpheaders["CSRFPreventionToken"] = csrf
        response = requests.put(
            full_url,
            verify=verify_ssl,
            data=post_data,
            cookies=ticket,
            headers=httpheaders,
        )
    elif conn_type == "delete":
        httpheaders["CSRFPreventionToken"] = csrf
        response = requests.delete(
            full_url,
            verify=verify_ssl,
            data=post_data,
            cookies=ticket,
            headers=httpheaders,
        )
    elif conn_type == "get":
        response = requests.get(full_url, verify=verify_ssl, cookies=ticket)

    response.raise_for_status()

    try:
        returned_data = response.json()
        if "data" not in returned_data:
            raise SaltCloudExecutionFailure
        return returned_data["data"]
    except Exception:  # pylint: disable=broad-except
        log.error("Error in trying to process JSON")
        log.error(response)


def _get_vm_by_name(name, allDetails=False):
    """
    Since Proxmox works based op id's rather than names as identifiers this
    requires some filtering to retrieve the required information.
    """
    vms = get_resources_vms(includeConfig=allDetails)
    if name in vms:
        return vms[name]

    log.info('VM with name "%s" could not be found.', name)
    return False


def _get_vm_by_id(vmid, allDetails=False):
    """
    Retrieve a VM based on the ID.
    """
    for vm_name, vm_details in get_resources_vms(includeConfig=allDetails).items():
        if str(vm_details["vmid"]) == str(vmid):
            return vm_details

    log.info('VM with ID "%s" could not be found.', vmid)
    return False


def _get_next_vmid():
    """
    Proxmox allows the use of alternative ids instead of autoincrementing.
    Because of that its required to query what the first available ID is.
    """
    return int(query("get", "cluster/nextid"))


def _check_ip_available(ip_addr):
    """
    Proxmox VMs refuse to start when the IP is already being used.
    This function can be used to prevent VMs being created with duplicate
    IP's or to generate a warning.
    """
    for vm_name, vm_details in get_resources_vms(includeConfig=True).items():
        vm_config = vm_details["config"]
        if ip_addr in vm_config["ip_address"] or vm_config["ip_address"] == ip_addr:
            log.debug('IP "%s" is already defined', ip_addr)
            return False

    log.debug("IP '%s' is available to be defined", ip_addr)
    return True


def _parse_proxmox_upid(node, vm_=None):
    """
    Upon requesting a task that runs for a longer period of time a UPID is given.
    This includes information about the job and can be used to lookup information in the log.
    """
    ret = {}

    upid = node
    # Parse node response
    node = node.split(":")
    if node[0] == "UPID":
        ret["node"] = str(node[1])
        ret["pid"] = str(node[2])
        ret["pstart"] = str(node[3])
        ret["starttime"] = str(node[4])
        ret["type"] = str(node[5])
        ret["vmid"] = str(node[6])
        ret["user"] = str(node[7])
        # include the upid again in case we'll need it again
        ret["upid"] = str(upid)

        if vm_ is not None and "technology" in vm_:
            ret["technology"] = str(vm_["technology"])

    return ret


def _lookup_proxmox_task(upid):
    """
    Retrieve the (latest) logs and retrieve the status for a UPID.
    This can be used to verify whether a task has completed.
    """
    log.debug("Getting creation status for upid: %s", upid)
    tasks = query("get", "cluster/tasks")

    if tasks:
        for task in tasks:
            if task["upid"] == upid:
                log.debug("Found upid task: %s", task)
                return task

    return False


def get_resources_nodes(call=None, resFilter=None):
    """
    Retrieve all hypervisors (nodes) available on this environment

    CLI Example:

    .. code-block:: bash

        salt-cloud -f get_resources_nodes my-proxmox-config
    """
    log.debug("Getting resource: nodes.. (filter: %s)", resFilter)
    resources = query("get", "cluster/resources")

    ret = {}
    for resource in resources:
        if "type" in resource and resource["type"] == "node":
            name = resource["node"]
            ret[name] = resource

    if resFilter is not None:
        log.debug("Filter given: %s, returning requested resource: nodes", resFilter)
        return ret[resFilter]

    log.debug("Filter not given: %s, returning all resource: nodes", ret)
    return ret


def get_resources_vms(call=None, resFilter=None, includeConfig=True):
    """
    Retrieve all VMs available on this environment

    CLI Example:

    .. code-block:: bash

        salt-cloud -f get_resources_vms my-proxmox-config
    """
    timeoutTime = time.time() + 60
    while True:
        log.debug("Getting resource: vms.. (filter: %s)", resFilter)
        resources = query("get", "cluster/resources")
        ret = {}
        badResource = False
        for resource in resources:
            if "type" in resource and resource["type"] in ["openvz", "qemu", "lxc"]:
                try:
                    name = resource["name"]
                except KeyError:
                    badResource = True
                    log.debug("No name in VM resource %s", repr(resource))
                    break

                ret[name] = resource

                if includeConfig:
                    # Requested to include the detailed configuration of a VM
                    ret[name]["config"] = get_vmconfig(
                        ret[name]["vmid"], ret[name]["node"], ret[name]["type"]
                    )

        if time.time() > timeoutTime:
            raise SaltCloudExecutionTimeout("FAILED to get the proxmox resources vms")

        # Carry on if there wasn't a bad resource return from Proxmox
        if not badResource:
            break

        time.sleep(0.5)

    if resFilter is not None:
        log.debug("Filter given: %s, returning requested resource: nodes", resFilter)
        return ret[resFilter]

    log.debug("Filter not given: %s, returning all resource: nodes", ret)
    return ret


def script(vm_):
    """
    Return the script deployment object
    """
    script_name = config.get_cloud_config_value("script", vm_, __opts__)
    if not script_name:
        script_name = "bootstrap-salt"

    return salt.utils.cloud.os_script(
        script_name,
        vm_,
        __opts__,
        salt.utils.cloud.salt_config_to_yaml(
            salt.utils.cloud.minion_config(__opts__, vm_)
        ),
    )


def avail_locations(call=None):
    """
    Return a list of the hypervisors (nodes) which this Proxmox PVE machine manages

    CLI Example:

    .. code-block:: bash

        salt-cloud --list-locations my-proxmox-config
    """
    if call == "action":
        raise SaltCloudSystemExit(
            "The avail_locations function must be called with "
            "-f or --function, or with the --list-locations option"
        )

    # could also use the get_resources_nodes but speed is ~the same
    nodes = query("get", "nodes")

    ret = {}
    for node in nodes:
        name = node["node"]
        ret[name] = node

    return ret


def avail_images(call=None, location="local"):
    """
    Return a list of the images that are on the provider

    CLI Example:

    .. code-block:: bash

        salt-cloud --list-images my-proxmox-config
    """
    if call == "action":
        raise SaltCloudSystemExit(
            "The avail_images function must be called with "
            "-f or --function, or with the --list-images option"
        )

    ret = {}
    for host_name, host_details in avail_locations().items():
        for item in query(
            "get", "nodes/{}/storage/{}/content".format(host_name, location)
        ):
            ret[item["volid"]] = item
    return ret


def list_nodes(call=None):
    """
    Return a list of the VMs that are managed by the provider

    CLI Example:

    .. code-block:: bash

        salt-cloud -Q my-proxmox-config
    """
    if call == "action":
        raise SaltCloudSystemExit(
            "The list_nodes function must be called with -f or --function."
        )

    ret = {}
    for vm_name, vm_details in get_resources_vms(includeConfig=True).items():
        log.debug("VM_Name: %s", vm_name)
        log.debug("vm_details: %s", vm_details)

        # Limit resultset on what Salt-cloud demands:
        ret[vm_name] = {}
        ret[vm_name]["id"] = str(vm_details["vmid"])
        ret[vm_name]["image"] = str(vm_details["vmid"])
        ret[vm_name]["size"] = str(vm_details["disk"])
        ret[vm_name]["state"] = str(vm_details["status"])

        # Figure out which is which to put it in the right column
        private_ips = []
        public_ips = []

        if (
            "ip_address" in vm_details["config"]
            and vm_details["config"]["ip_address"] != "-"
        ):
            ips = vm_details["config"]["ip_address"].split(" ")
            for ip_ in ips:
                if IP(ip_).iptype() == "PRIVATE":
                    private_ips.append(str(ip_))
                else:
                    public_ips.append(str(ip_))

        ret[vm_name]["private_ips"] = private_ips
        ret[vm_name]["public_ips"] = public_ips

    return ret


def list_nodes_full(call=None):
    """
    Return a list of the VMs that are on the provider

    CLI Example:

    .. code-block:: bash

        salt-cloud -F my-proxmox-config
    """
    if call == "action":
        raise SaltCloudSystemExit(
            "The list_nodes_full function must be called with -f or --function."
        )

    return get_resources_vms(includeConfig=True)


def list_nodes_select(call=None):
    """
    Return a list of the VMs that are on the provider, with select fields

    CLI Example:

    .. code-block:: bash

        salt-cloud -S my-proxmox-config
    """
    return salt.utils.cloud.list_nodes_select(
        list_nodes_full(),
        __opts__["query.selection"],
        call,
    )


def _stringlist_to_dictionary(input_string):
    """
    Convert a stringlist (comma separated settings) to a dictionary

    The result of the string setting1=value1,setting2=value2 will be a python dictionary:

    {'setting1':'value1','setting2':'value2'}
    """
    return dict(item.strip().split("=") for item in input_string.split(",") if item)


def _dictionary_to_stringlist(input_dict):
    """
    Convert a dictionary to a stringlist (comma separated settings)

    The result of the dictionary {'setting1':'value1','setting2':'value2'} will be:

    setting1=value1,setting2=value2
    """
    return ",".join("{}={}".format(k, input_dict[k]) for k in sorted(input_dict.keys()))


def _reconfigure_clone(vm_, vmid):
    """
    If we cloned a machine, see if we need to reconfigure any of the options such as net0,
    ide2, etc. This enables us to have a different cloud-init ISO mounted for each VM that's brought up
    :param vm_:
    :return:
    """
    if not vm_.get("technology") == "qemu":
        log.warning("Reconfiguring clones is only available under `qemu`")
        return

    # TODO: Support other settings here too as these are not the only ones that can be modified after a clone operation
    log.info("Configuring cloned VM")

    # Modify the settings for the VM one at a time so we can see any problems with the values
    # as quickly as possible
    for setting in vm_:
        if re.match(r"^(ide|sata|scsi)(\d+)$", setting):
            postParams = {setting: vm_[setting]}
            query(
                "post",
                "nodes/{}/qemu/{}/config".format(vm_["host"], vmid),
                postParams,
            )

        elif re.match(r"^net(\d+)$", setting):
            # net strings are a list of comma seperated settings. We need to merge the settings so that
            # the setting in the profile only changes the settings it touches and the other settings
            # are left alone. An example of why this is necessary is because the MAC address is set
            # in here and generally you don't want to alter or have to know the MAC address of the new
            # instance, but you may want to set the VLAN bridge
            data = query("get", "nodes/{}/qemu/{}/config".format(vm_["host"], vmid))

            # Generate a dictionary of settings from the existing string
            new_setting = {}
            if setting in data:
                new_setting.update(_stringlist_to_dictionary(data[setting]))

            # Merge the new settings (as a dictionary) into the existing dictionary to get the
            # new merged settings
            new_setting.update(_stringlist_to_dictionary(vm_[setting]))

            # Convert the dictionary back into a string list
            postParams = {setting: _dictionary_to_stringlist(new_setting)}
            query(
                "post",
                "nodes/{}/qemu/{}/config".format(vm_["host"], vmid),
                postParams,
            )


def create(vm_):
    """
    Create a single VM from a data dict

    CLI Example:

    .. code-block:: bash

        salt-cloud -p proxmox-ubuntu vmhostname
    """
    try:
        # Check for required profile parameters before sending any API calls.
        if (
            vm_["profile"]
            and config.is_profile_configured(
                __opts__,
                _get_active_provider_name() or "proxmox",
                vm_["profile"],
                vm_=vm_,
            )
            is False
        ):
            return False
    except AttributeError:
        pass

    ret = {}

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

    log.info("Creating Cloud VM %s", vm_["name"])

    if "use_dns" in vm_ and "ip_address" not in vm_:
        use_dns = vm_["use_dns"]
        if use_dns:
            from socket import gethostbyname, gaierror

            try:
                ip_address = gethostbyname(str(vm_["name"]))
            except gaierror:
                log.debug("Resolving of %s failed", vm_["name"])
            else:
                vm_["ip_address"] = str(ip_address)

    try:
        newid = _get_next_vmid()
        data = create_node(vm_, newid)
    except Exception as exc:  # pylint: disable=broad-except
        log.error(
            "Error creating %s on PROXMOX\n\n"
            "The following exception was thrown when trying to "
            "run the initial deployment: \n%s",
            vm_["name"],
            exc,
            # Show the traceback if the debug logging level is enabled
            exc_info_on_loglevel=logging.DEBUG,
        )
        return False

    ret["creation_data"] = data
    name = vm_["name"]  # hostname which we know
    if "clone" in vm_ and vm_["clone"] is True:
        vmid = newid
    else:
        vmid = data["vmid"]  # vmid which we have received
    host = data["node"]  # host which we have received
    nodeType = data["technology"]  # VM tech (Qemu / OpenVZ)

    # Determine which IP to use in order of preference:
    if "ip_address" in vm_:
        ip_address = str(vm_["ip_address"])
    elif "public_ips" in data:
        ip_address = str(data["public_ips"][0])  # first IP
    elif "private_ips" in data:
        ip_address = str(data["private_ips"][0])  # first IP
    else:
        raise SaltCloudExecutionFailure("Could not determine an IP address to use")

    log.debug("Using IP address %s", ip_address)

    # wait until the vm has been created so we can start it
    if not wait_for_created(data["upid"], timeout=300):
        return {"Error": "Unable to create {}, command timed out".format(name)}

    if vm_.get("clone") is True:
        _reconfigure_clone(vm_, vmid)

    # VM has been created. Starting..
    if not start(name, vmid, call="action"):
        log.error("Node %s (%s) failed to start!", name, vmid)
        raise SaltCloudExecutionFailure

    # Wait until the VM has fully started
    log.debug('Waiting for state "running" for vm %s on %s', vmid, host)
    if not wait_for_state(vmid, "running"):
        return {"Error": "Unable to start {}, command timed out".format(name)}

    ssh_username = config.get_cloud_config_value(
        "ssh_username", vm_, __opts__, default="root"
    )
    ssh_password = config.get_cloud_config_value(
        "password",
        vm_,
        __opts__,
    )

    ret["ip_address"] = ip_address
    ret["username"] = ssh_username
    ret["password"] = ssh_password

    vm_["ssh_host"] = ip_address
    vm_["password"] = ssh_password
    ret = __utils__["cloud.bootstrap"](vm_, __opts__)

    # Report success!
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
    )

    return ret


def _import_api():
    """
    Download https://<url>/pve-docs/api-viewer/apidoc.js
    Extract content of pveapi var (json formatted)
    Load this json content into global variable "api"
    """
    global api
    full_url = "https://{}:{}/pve-docs/api-viewer/apidoc.js".format(url, port)
    returned_data = requests.get(full_url, verify=verify_ssl)

    re_filter = re.compile("(?<=pveapi =)(.*)(?=^;)", re.DOTALL | re.MULTILINE)
    api_json = re_filter.findall(returned_data.text)[0]
    api = salt.utils.json.loads(api_json)


def _get_properties(path="", method="GET", forced_params=None):
    """
    Return the parameter list from api for defined path and HTTP method
    """
    if api is None:
        _import_api()

    sub = api
    path_levels = [level for level in path.split("/") if level != ""]
    search_path = ""
    props = []
    parameters = set([] if forced_params is None else forced_params)
    # Browse all path elements but last
    for elem in path_levels[:-1]:
        search_path += "/" + elem
        # Lookup for a dictionary with path = "requested path" in list" and return its children
        sub = next(item for item in sub if item["path"] == search_path)["children"]
    # Get leaf element in path
    search_path += "/" + path_levels[-1]
    sub = next(item for item in sub if item["path"] == search_path)
    try:
        # get list of properties for requested method
        props = sub["info"][method]["parameters"]["properties"].keys()
    except KeyError as exc:
        log.error('method not found: "%s"', exc)
    for prop in props:
        numerical = re.match(r"(\w+)\[n\]", prop)
        # generate (arbitrarily) 10 properties for duplicatable properties identified by:
        # "prop[n]"
        if numerical:
            for i in range(10):
                parameters.add(numerical.group(1) + str(i))
        else:
            parameters.add(prop)
    return parameters


def create_node(vm_, newid):
    """
    Build and submit the requestdata to create a new node
    """
    newnode = {}

    if "technology" not in vm_:
        vm_["technology"] = "openvz"  # default virt tech if none is given

    if vm_["technology"] not in ["qemu", "openvz", "lxc"]:
        # Wrong VM type given
        log.error(
            "Wrong VM type. Valid options are: qemu, openvz (proxmox3) or lxc"
            " (proxmox4)"
        )
        raise SaltCloudExecutionFailure

    if "host" not in vm_:
        # Use globally configured/default location
        vm_["host"] = config.get_cloud_config_value(
            "default_host", get_configured_provider(), __opts__, search_global=False
        )

    if vm_["host"] is None:
        # No location given for the profile
        log.error("No host given to create this VM on")
        raise SaltCloudExecutionFailure

    # Required by both OpenVZ and Qemu (KVM)
    vmhost = vm_["host"]
    newnode["vmid"] = newid

    for prop in "cpuunits", "description", "memory", "onboot":
        if prop in vm_:  # if the property is set, use it for the VM request
            newnode[prop] = vm_[prop]

    if vm_["technology"] == "openvz":
        # OpenVZ related settings, using non-default names:
        newnode["hostname"] = vm_["name"]
        newnode["ostemplate"] = vm_["image"]

        # optional VZ settings
        for prop in (
            "cpus",
            "disk",
            "ip_address",
            "nameserver",
            "password",
            "swap",
            "poolid",
            "storage",
        ):
            if prop in vm_:  # if the property is set, use it for the VM request
                newnode[prop] = vm_[prop]

    elif vm_["technology"] == "lxc":
        # LXC related settings, using non-default names:
        newnode["hostname"] = vm_["name"]
        newnode["ostemplate"] = vm_["image"]

        static_props = (
            "cpuunits",
            "cpulimit",
            "rootfs",
            "cores",
            "description",
            "memory",
            "onboot",
            "net0",
            "password",
            "nameserver",
            "swap",
            "storage",
            "rootfs",
        )
        for prop in _get_properties("/nodes/{node}/lxc", "POST", static_props):
            if prop in vm_:  # if the property is set, use it for the VM request
                newnode[prop] = vm_[prop]

        if "pubkey" in vm_:
            newnode["ssh-public-keys"] = vm_["pubkey"]

        # inform user the "disk" option is not supported for LXC hosts
        if "disk" in vm_:
            log.warning(
                'The "disk" option is not supported for LXC hosts and was ignored'
            )

        # LXC specific network config
        # OpenVZ allowed specifying IP and gateway. To ease migration from
        # Proxmox 3, I've mapped the ip_address and gw to a generic net0 config.
        # If you need more control, please use the net0 option directly.
        # This also assumes a /24 subnet.
        if "ip_address" in vm_ and "net0" not in vm_:
            newnode["net0"] = (
                "bridge=vmbr0,ip=" + vm_["ip_address"] + "/24,name=eth0,type=veth"
            )

            # gateway is optional and does not assume a default
            if "gw" in vm_:
                newnode["net0"] = newnode["net0"] + ",gw=" + vm_["gw"]

    elif vm_["technology"] == "qemu":
        # optional Qemu settings
        static_props = (
            "acpi",
            "cores",
            "cpu",
            "pool",
            "storage",
            "sata0",
            "ostype",
            "ide2",
            "net0",
        )
        for prop in _get_properties("/nodes/{node}/qemu", "POST", static_props):
            if prop in vm_:  # if the property is set, use it for the VM request
                newnode[prop] = vm_[prop]

    # The node is ready. Lets request it to be added
    __utils__["cloud.fire_event"](
        "event",
        "requesting instance",
        "salt/cloud/{}/requesting".format(vm_["name"]),
        args={
            "kwargs": __utils__["cloud.filter_event"](
                "requesting", newnode, list(newnode)
            ),
        },
        sock_dir=__opts__["sock_dir"],
    )

    log.debug("Preparing to generate a node using these parameters: %s ", newnode)
    if "clone" in vm_ and vm_["clone"] is True and vm_["technology"] == "qemu":
        postParams = {}
        postParams["newid"] = newnode["vmid"]

        for prop in "description", "format", "full", "name":
            if (
                "clone_" + prop in vm_
            ):  # if the property is set, use it for the VM request
                postParams[prop] = vm_["clone_" + prop]

        try:
            int(vm_["clone_from"])
        except ValueError:
            if ":" in vm_["clone_from"]:
                vmhost = vm_["clone_from"].split(":")[0]
                vm_["clone_from"] = vm_["clone_from"].split(":")[1]

        node = query(
            "post",
            "nodes/{}/qemu/{}/clone".format(vmhost, vm_["clone_from"]),
            postParams,
        )
    else:
        node = query("post", "nodes/{}/{}".format(vmhost, vm_["technology"]), newnode)
    return _parse_proxmox_upid(node, vm_)


def show_instance(name, call=None):
    """
    Show the details from Proxmox concerning an instance
    """
    if call != "action":
        raise SaltCloudSystemExit(
            "The show_instance action must be called with -a or --action."
        )

    nodes = list_nodes_full()
    __utils__["cloud.cache_node"](nodes[name], _get_active_provider_name(), __opts__)
    return nodes[name]


def get_vmconfig(vmid, node=None, node_type="openvz"):
    """
    Get VM configuration
    """
    if node is None:
        # We need to figure out which node this VM is on.
        for host_name, host_details in avail_locations().items():
            for item in query("get", "nodes/{}/{}".format(host_name, node_type)):
                if item["vmid"] == vmid:
                    node = host_name

    # If we reached this point, we have all the information we need
    data = query("get", "nodes/{}/{}/{}/config".format(node, node_type, vmid))

    return data


def wait_for_created(upid, timeout=300):
    """
    Wait until a the vm has been created successfully
    """
    start_time = time.time()
    info = _lookup_proxmox_task(upid)
    if not info:
        log.error(
            "wait_for_created: No task information retrieved based on given criteria."
        )
        raise SaltCloudExecutionFailure

    while True:
        if "status" in info and info["status"] == "OK":
            log.debug("Host has been created!")
            return True
        time.sleep(3)  # Little more patience, we're not in a hurry
        if time.time() - start_time > timeout:
            log.debug("Timeout reached while waiting for host to be created")
            return False
        info = _lookup_proxmox_task(upid)


def wait_for_state(vmid, state, timeout=300):
    """
    Wait until a specific state has been reached on a node
    """
    start_time = time.time()
    node = get_vm_status(vmid=vmid)
    if not node:
        log.error("wait_for_state: No VM retrieved based on given criteria.")
        raise SaltCloudExecutionFailure

    while True:
        if node["status"] == state:
            log.debug('Host %s is now in "%s" state!', node["name"], state)
            return True
        time.sleep(1)
        if time.time() - start_time > timeout:
            log.debug(
                "Timeout reached while waiting for %s to become %s", node["name"], state
            )
            return False
        node = get_vm_status(vmid=vmid)
        log.debug(
            'State for %s is: "%s" instead of "%s"', node["name"], node["status"], state
        )


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

    __utils__["cloud.fire_event"](
        "event",
        "destroying instance",
        "salt/cloud/{}/destroying".format(name),
        args={"name": name},
        sock_dir=__opts__["sock_dir"],
        transport=__opts__["transport"],
    )

    vmobj = _get_vm_by_name(name)
    if vmobj is not None:
        # stop the vm
        if get_vm_status(vmid=vmobj["vmid"])["status"] != "stopped":
            stop(name, vmobj["vmid"], "action")

        # wait until stopped
        if not wait_for_state(vmobj["vmid"], "stopped"):
            return {"Error": "Unable to stop {}, command timed out".format(name)}

        # required to wait a bit here, otherwise the VM is sometimes
        # still locked and destroy fails.
        time.sleep(3)

        query("delete", "nodes/{}/{}".format(vmobj["node"], vmobj["id"]))
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

        return {"Destroyed": "{} was destroyed.".format(name)}


def set_vm_status(status, name=None, vmid=None):
    """
    Convenience function for setting VM status
    """
    log.debug("Set status to %s for %s (%s)", status, name, vmid)

    if vmid is not None:
        log.debug("set_vm_status: via ID - VMID %s (%s): %s", vmid, name, status)
        vmobj = _get_vm_by_id(vmid)
    else:
        log.debug("set_vm_status: via name - VMID %s (%s): %s", vmid, name, status)
        vmobj = _get_vm_by_name(name)

    if not vmobj or "node" not in vmobj or "type" not in vmobj or "vmid" not in vmobj:
        log.error("Unable to set status %s for %s (%s)", status, name, vmid)
        raise SaltCloudExecutionTimeout

    log.debug("VM_STATUS: Has desired info (%s). Setting status..", vmobj)
    data = query(
        "post",
        "nodes/{}/{}/{}/status/{}".format(
            vmobj["node"], vmobj["type"], vmobj["vmid"], status
        ),
    )

    result = _parse_proxmox_upid(data, vmobj)

    if result is not False and result is not None:
        log.debug("Set_vm_status action result: %s", result)
        return True

    return False


def get_vm_status(vmid=None, name=None):
    """
    Get the status for a VM, either via the ID or the hostname
    """
    if vmid is not None:
        log.debug("get_vm_status: VMID %s", vmid)
        vmobj = _get_vm_by_id(vmid)
    elif name is not None:
        log.debug("get_vm_status: name %s", name)
        vmobj = _get_vm_by_name(name)
    else:
        log.debug("get_vm_status: No ID or NAME given")
        raise SaltCloudExecutionFailure

    log.debug("VM found: %s", vmobj)

    if vmobj is not None and "node" in vmobj:
        log.debug("VM_STATUS: Has desired info. Retrieving.. (%s)", vmobj["name"])
        data = query(
            "get",
            "nodes/{}/{}/{}/status/current".format(
                vmobj["node"], vmobj["type"], vmobj["vmid"]
            ),
        )
        return data

    log.error("VM or requested status not found..")
    return False


def start(name, vmid=None, call=None):
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

    log.debug("Start: %s (%s) = Start", name, vmid)
    if not set_vm_status("start", name, vmid=vmid):
        log.error("Unable to bring VM %s (%s) up..", name, vmid)
        raise SaltCloudExecutionFailure

    # xxx: TBD: Check here whether the status was actually changed to 'started'

    return {"Started": "{} was started.".format(name)}


def stop(name, vmid=None, call=None):
    """
    Stop a node ("pulling the plug").

    CLI Example:

    .. code-block:: bash

        salt-cloud -a stop mymachine
    """
    if call != "action":
        raise SaltCloudSystemExit("The stop action must be called with -a or --action.")

    if not set_vm_status("stop", name, vmid=vmid):
        log.error("Unable to bring VM %s (%s) down..", name, vmid)
        raise SaltCloudExecutionFailure

    # xxx: TBD: Check here whether the status was actually changed to 'stopped'

    return {"Stopped": "{} was stopped.".format(name)}


def shutdown(name=None, vmid=None, call=None):
    """
    Shutdown a node via ACPI.

    CLI Example:

    .. code-block:: bash

        salt-cloud -a shutdown mymachine
    """
    if call != "action":
        raise SaltCloudSystemExit(
            "The shutdown action must be called with -a or --action."
        )

    if not set_vm_status("shutdown", name, vmid=vmid):
        log.error("Unable to shut VM %s (%s) down..", name, vmid)
        raise SaltCloudExecutionFailure

    # xxx: TBD: Check here whether the status was actually changed to 'stopped'

    return {"Shutdown": "{} was shutdown.".format(name)}
