"""
Libvirt Cloud Module
====================

Example provider:

.. code-block:: yaml

    # A provider maps to a libvirt instance
    my-libvirt-config:
      driver: libvirt
      # url: "qemu+ssh://user@remotekvm/system?socket=/var/run/libvirt/libvirt-sock"
      url: qemu:///system

Example profile:

.. code-block:: yaml

    base-itest:
      # points back at provider configuration e.g. the libvirt daemon to talk to
      provider: my-libvirt-config
      base_domain: base-image
      # ip_source = [ ip-learning | qemu-agent ]
      ip_source: ip-learning
      # clone_strategy = [ quick | full ]
      clone_strategy: quick
      ssh_username: vagrant
      # has_ssh_agent: True
      password: vagrant
      # if /tmp is mounted noexec do workaround
      deploy_command: sh /tmp/.saltcloud/deploy.sh
      # -F makes the bootstrap script overwrite existing config
      # which make reprovisioning a box work
      script_args: -F
      grains:
        sushi: more tasty
      # point at the another master at another port
      minion:
        master: 192.168.16.1
        master_port: 5506

Tested on:
- Fedora 26 (libvirt 3.2.1, qemu 2.9.1)
- Fedora 25 (libvirt 1.3.3.2, qemu 2.6.1)
- Fedora 23 (libvirt 1.2.18, qemu 2.4.1)
- Centos 7 (libvirt 1.2.17, qemu 1.5.3)

"""

# TODO: look at event descriptions here:
#       https://docs.saltproject.io/en/latest/topics/cloud/reactor.html
# TODO: support reboot? salt-cloud -a reboot vm1 vm2 vm2
# TODO: by using metadata tags in the libvirt XML we could make provider only
#       manage domains that we actually created

import logging
import os
import uuid
from xml.etree import ElementTree

import salt.config as config
import salt.utils.cloud
from salt.exceptions import (
    SaltCloudConfigError,
    SaltCloudExecutionFailure,
    SaltCloudNotFound,
    SaltCloudSystemExit,
)

try:
    import libvirt  # pylint: disable=import-error

    # pylint: disable=no-name-in-module
    from libvirt import libvirtError

    # pylint: enable=no-name-in-module

    HAS_LIBVIRT = True
except ImportError:
    HAS_LIBVIRT = False


VIRT_STATE_NAME_MAP = {
    0: "running",
    1: "running",
    2: "running",
    3: "paused",
    4: "shutdown",
    5: "shutdown",
    6: "crashed",
}

IP_LEARNING_XML = """<filterref filter='clean-traffic'>
        <parameter name='CTRL_IP_LEARNING' value='any'/>
      </filterref>"""

__virtualname__ = "libvirt"

# Set up logging
log = logging.getLogger(__name__)


def libvirt_error_handler(ctx, error):  # pylint: disable=unused-argument
    """
    Redirect stderr prints from libvirt to salt logging.
    """
    log.debug("libvirt error %s", error)


if HAS_LIBVIRT:
    libvirt.registerErrorHandler(f=libvirt_error_handler, ctx=None)


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
    if not HAS_LIBVIRT:
        return False, "Unable to locate or import python libvirt library."

    if get_configured_provider() is False:
        return False, "The 'libvirt' provider is not configured."

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
        __opts__, _get_active_provider_name() or __virtualname__, ("url",)
    )


def __get_conn(url):
    # This has only been tested on kvm and xen, it needs to be expanded to
    # support all vm layers supported by libvirt
    try:
        conn = libvirt.open(url)
    except Exception:  # pylint: disable=broad-except
        raise SaltCloudExecutionFailure(
            "Sorry, {} failed to open a connection to the hypervisor "
            "software at {}".format(__grains__["fqdn"], url)
        )
    return conn


def list_nodes(call=None):
    """
    Return a list of the VMs

    id (str)
    image (str)
    size (str)
    state (str)
    private_ips (list)
    public_ips (list)

    """
    if call == "action":
        raise SaltCloudSystemExit(
            "The list_nodes function must be called with -f or --function."
        )

    providers = __opts__.get("providers", {})

    ret = {}
    providers_to_check = [
        _f for _f in [cfg.get("libvirt") for cfg in providers.values()] if _f
    ]
    for provider in providers_to_check:
        conn = __get_conn(provider["url"])
        domains = conn.listAllDomains()
        for domain in domains:
            data = {
                "id": domain.UUIDString(),
                "image": "",
                "size": "",
                "state": VIRT_STATE_NAME_MAP[domain.state()[0]],
                "private_ips": [],
                "public_ips": get_domain_ips(
                    domain, libvirt.VIR_DOMAIN_INTERFACE_ADDRESSES_SRC_LEASE
                ),
            }
            # TODO: Annoyingly name is not guaranteed to be unique, but the id will not work in other places
            ret[domain.name()] = data

    return ret


def list_nodes_full(call=None):
    """
    Because this module is not specific to any cloud providers, there will be
    no nodes to list.
    """
    if call == "action":
        raise SaltCloudSystemExit(
            "The list_nodes_full function must be called with -f or --function."
        )

    return list_nodes(call)


def list_nodes_select(call=None):
    """
    Return a list of the VMs that are on the provider, with select fields
    """
    if call == "action":
        raise SaltCloudSystemExit(
            "The list_nodes_select function must be called with -f or --function."
        )

    selection = __opts__.get("query.selection")

    if not selection:
        raise SaltCloudSystemExit("query.selection not found in /etc/salt/cloud")

    # TODO: somewhat doubt the implementation of cloud.list_nodes_select
    return salt.utils.cloud.list_nodes_select(
        list_nodes_full(),
        selection,
        call,
    )


def to_ip_addr_type(addr_type):
    if addr_type == libvirt.VIR_IP_ADDR_TYPE_IPV4:
        return "ipv4"
    elif addr_type == libvirt.VIR_IP_ADDR_TYPE_IPV6:
        return "ipv6"


def get_domain_ips(domain, ip_source):
    ips = []
    state = domain.state(0)
    if state[0] != libvirt.VIR_DOMAIN_RUNNING:
        return ips
    try:
        addresses = domain.interfaceAddresses(ip_source, 0)
    except libvirt.libvirtError as error:
        log.info("Exception polling address %s", error)
        return ips

    for (name, val) in addresses.items():
        if val["addrs"]:
            for addr in val["addrs"]:
                tp = to_ip_addr_type(addr["type"])
                log.info("Found address %s", addr)
                if tp == "ipv4":
                    ips.append(addr["addr"])
    return ips


def get_domain_ip(domain, idx, ip_source, skip_loopback=True):
    ips = get_domain_ips(domain, ip_source)

    if skip_loopback:
        ips = [ip for ip in ips if not ip.startswith("127.")]

    if not ips or len(ips) <= idx:
        return None

    return ips[idx]


def create(vm_):
    """
    Provision a single machine
    """
    clone_strategy = vm_.get("clone_strategy") or "full"

    if clone_strategy not in ("quick", "full"):
        raise SaltCloudSystemExit(
            "'clone_strategy' must be one of quick or full. Got '{}'".format(
                clone_strategy
            )
        )

    ip_source = vm_.get("ip_source") or "ip-learning"

    if ip_source not in ("ip-learning", "qemu-agent"):
        raise SaltCloudSystemExit(
            "'ip_source' must be one of qemu-agent or ip-learning. Got '{}'".format(
                ip_source
            )
        )

    validate_xml = (
        vm_.get("validate_xml") if vm_.get("validate_xml") is not None else True
    )

    log.info(
        "Cloning '%s' with strategy '%s' validate_xml='%s'",
        vm_["name"],
        clone_strategy,
        validate_xml,
    )

    try:
        # Check for required profile parameters before sending any API calls.
        if (
            vm_["profile"]
            and config.is_profile_configured(
                __opts__, _get_active_provider_name() or "libvirt", vm_["profile"]
            )
            is False
        ):
            return False
    except AttributeError:
        pass

    # TODO: check name qemu/libvirt will choke on some characters (like '/')?
    name = vm_["name"]

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

    key_filename = config.get_cloud_config_value(
        "private_key", vm_, __opts__, search_global=False, default=None
    )
    if key_filename is not None and not os.path.isfile(key_filename):
        raise SaltCloudConfigError(
            "The defined key_filename '{}' does not exist".format(key_filename)
        )
    vm_["key_filename"] = key_filename
    # wait_for_instance requires private_key
    vm_["private_key"] = key_filename

    cleanup = []
    try:
        # clone the vm
        base = vm_["base_domain"]
        conn = __get_conn(vm_["url"])

        try:
            # for idempotency the salt-bootstrap needs -F argument
            #  script_args: -F
            clone_domain = conn.lookupByName(name)
        except libvirtError as e:
            domain = conn.lookupByName(base)
            # TODO: ensure base is shut down before cloning
            xml = domain.XMLDesc(0)

            kwargs = {
                "name": name,
                "base_domain": base,
            }

            __utils__["cloud.fire_event"](
                "event",
                "requesting instance",
                "salt/cloud/{}/requesting".format(name),
                args={
                    "kwargs": __utils__["cloud.filter_event"](
                        "requesting", kwargs, list(kwargs)
                    ),
                },
                sock_dir=__opts__["sock_dir"],
                transport=__opts__["transport"],
            )

            log.debug("Source machine XML '%s'", xml)

            domain_xml = ElementTree.fromstring(xml)
            domain_xml.find("./name").text = name
            if domain_xml.find("./description") is None:
                description_elem = ElementTree.Element("description")
                domain_xml.insert(0, description_elem)
            description = domain_xml.find("./description")
            description.text = "Cloned from {}".format(base)
            domain_xml.remove(domain_xml.find("./uuid"))

            for iface_xml in domain_xml.findall("./devices/interface"):
                iface_xml.remove(iface_xml.find("./mac"))
                # enable IP learning, this might be a default behaviour...
                # Don't always enable since it can cause problems through libvirt-4.5
                if (
                    ip_source == "ip-learning"
                    and iface_xml.find(
                        "./filterref/parameter[@name='CTRL_IP_LEARNING']"
                    )
                    is None
                ):
                    iface_xml.append(ElementTree.fromstring(IP_LEARNING_XML))

            # If a qemu agent is defined we need to fix the path to its socket
            # <channel type='unix'>
            #   <source mode='bind' path='/var/lib/libvirt/qemu/channel/target/domain-<dom-name>/org.qemu.guest_agent.0'/>
            #   <target type='virtio' name='org.qemu.guest_agent.0'/>
            #   <address type='virtio-serial' controller='0' bus='0' port='2'/>
            # </channel>
            for agent_xml in domain_xml.findall("""./devices/channel[@type='unix']"""):
                #  is org.qemu.guest_agent.0 an option?
                if (
                    agent_xml.find(
                        """./target[@type='virtio'][@name='org.qemu.guest_agent.0']"""
                    )
                    is not None
                ):
                    source_element = agent_xml.find("""./source[@mode='bind']""")
                    # see if there is a path element that needs rewriting
                    if source_element and "path" in source_element.attrib:
                        path = source_element.attrib["path"]
                        new_path = path.replace(
                            "/domain-{}/".format(base), "/domain-{}/".format(name)
                        )
                        log.debug("Rewriting agent socket path to %s", new_path)
                        source_element.attrib["path"] = new_path

            for disk in domain_xml.findall(
                """./devices/disk[@device='disk'][@type='file']"""
            ):
                # print "Disk: ", ElementTree.tostring(disk)
                # check if we can clone
                driver = disk.find("./driver[@name='qemu']")
                if driver is None:
                    # Err on the safe side
                    raise SaltCloudExecutionFailure(
                        "Non qemu driver disk encountered bailing out."
                    )
                disk_type = driver.attrib.get("type")
                log.info("disk attributes %s", disk.attrib)
                if disk_type == "qcow2":
                    source = disk.find("./source").attrib["file"]
                    pool, volume = find_pool_and_volume(conn, source)
                    if clone_strategy == "quick":
                        new_volume = pool.createXML(
                            create_volume_with_backing_store_xml(volume), 0
                        )
                    else:
                        new_volume = pool.createXMLFrom(
                            create_volume_xml(volume), volume, 0
                        )
                    cleanup.append({"what": "volume", "item": new_volume})

                    disk.find("./source").attrib["file"] = new_volume.path()
                elif disk_type == "raw":
                    source = disk.find("./source").attrib["file"]
                    pool, volume = find_pool_and_volume(conn, source)
                    # TODO: more control on the cloned disk type
                    new_volume = pool.createXMLFrom(
                        create_volume_xml(volume), volume, 0
                    )
                    cleanup.append({"what": "volume", "item": new_volume})

                    disk.find("./source").attrib["file"] = new_volume.path()
                else:
                    raise SaltCloudExecutionFailure(
                        "Disk type '{}' not supported".format(disk_type)
                    )

            clone_xml = salt.utils.stringutils.to_str(ElementTree.tostring(domain_xml))
            log.debug("Clone XML '%s'", clone_xml)

            validate_flags = libvirt.VIR_DOMAIN_DEFINE_VALIDATE if validate_xml else 0
            clone_domain = conn.defineXMLFlags(clone_xml, validate_flags)

            cleanup.append({"what": "domain", "item": clone_domain})
            clone_domain.createWithFlags(libvirt.VIR_DOMAIN_START_FORCE_BOOT)

        log.debug("VM '%s'", vm_)

        if ip_source == "qemu-agent":
            ip_source = libvirt.VIR_DOMAIN_INTERFACE_ADDRESSES_SRC_AGENT
        elif ip_source == "ip-learning":
            ip_source = libvirt.VIR_DOMAIN_INTERFACE_ADDRESSES_SRC_LEASE

        address = salt.utils.cloud.wait_for_ip(
            get_domain_ip,
            update_args=(clone_domain, 0, ip_source),
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

        log.info("Address = %s", address)

        vm_["ssh_host"] = address

        # the bootstrap script needs to be installed first in /etc/salt/cloud.deploy.d/
        # salt-cloud -u is your friend
        ret = __utils__["cloud.bootstrap"](vm_, __opts__)

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
    except Exception:  # pylint: disable=broad-except
        do_cleanup(cleanup)
        # throw the root cause after cleanup
        raise


def do_cleanup(cleanup):
    """
    Clean up clone domain leftovers as much as possible.

    Extra robust clean up in order to deal with some small changes in libvirt
    behavior over time. Passed in volumes and domains are deleted, any errors
    are ignored. Used when cloning/provisioning a domain fails.

    :param cleanup: list containing dictionaries with two keys: 'what' and 'item'.
                    If 'what' is domain the 'item' is a libvirt domain object.
                    If 'what' is volume then the item is a libvirt volume object.

    Returns:
        none

    .. versionadded:: 2017.7.3
    """
    log.info("Cleaning up after exception")
    for leftover in cleanup:
        what = leftover["what"]
        item = leftover["item"]
        if what == "domain":
            log.info("Cleaning up %s %s", what, item.name())
            try:
                item.destroy()
                log.debug("%s %s forced off", what, item.name())
            except libvirtError:
                pass
            try:
                item.undefineFlags(
                    libvirt.VIR_DOMAIN_UNDEFINE_MANAGED_SAVE
                    + libvirt.VIR_DOMAIN_UNDEFINE_SNAPSHOTS_METADATA
                    + libvirt.VIR_DOMAIN_UNDEFINE_NVRAM
                )
                log.debug("%s %s undefined", what, item.name())
            except libvirtError:
                pass
        if what == "volume":
            try:
                item.delete()
                log.debug("%s %s cleaned up", what, item.name())
            except libvirtError:
                pass


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

    if call == "function":
        raise SaltCloudSystemExit(
            "The destroy action must be called with -d, --destroy, -a or --action."
        )

    found = []

    providers = __opts__.get("providers", {})
    providers_to_check = [
        _f for _f in [cfg.get("libvirt") for cfg in providers.values()] if _f
    ]
    for provider in providers_to_check:
        conn = __get_conn(provider["url"])
        log.info("looking at %s", provider["url"])
        try:
            domain = conn.lookupByName(name)
            found.append({"domain": domain, "conn": conn})
        except libvirtError:
            pass

    if not found:
        return "{} doesn't exist and can't be deleted".format(name)

    if len(found) > 1:
        return "{} doesn't identify a unique machine leaving things".format(name)

    __utils__["cloud.fire_event"](
        "event",
        "destroying instance",
        "salt/cloud/{}/destroying".format(name),
        args={"name": name},
        sock_dir=__opts__["sock_dir"],
        transport=__opts__["transport"],
    )

    destroy_domain(found[0]["conn"], found[0]["domain"])

    __utils__["cloud.fire_event"](
        "event",
        "destroyed instance",
        "salt/cloud/{}/destroyed".format(name),
        args={"name": name},
        sock_dir=__opts__["sock_dir"],
        transport=__opts__["transport"],
    )


def destroy_domain(conn, domain):
    log.info("Destroying domain %s", domain.name())
    try:
        domain.destroy()
    except libvirtError:
        pass
    volumes = get_domain_volumes(conn, domain)
    for volume in volumes:
        log.debug("Removing volume %s", volume.name())
        volume.delete()

    log.debug("Undefining domain %s", domain.name())
    domain.undefineFlags(
        libvirt.VIR_DOMAIN_UNDEFINE_MANAGED_SAVE
        + libvirt.VIR_DOMAIN_UNDEFINE_SNAPSHOTS_METADATA
        + libvirt.VIR_DOMAIN_UNDEFINE_NVRAM
    )


def create_volume_xml(volume):
    template = """<volume>
                    <name>n</name>
                    <capacity>c</capacity>
                    <allocation>0</allocation>
                    <target>
                        <path>p</path>
                        <format type='qcow2'/>
                        <compat>1.1</compat>
                    </target>
                </volume>
                """
    volume_xml = ElementTree.fromstring(template)
    # TODO: generate name
    volume_xml.find("name").text = generate_new_name(volume.name())
    log.debug("Volume: %s", dir(volume))
    volume_xml.find("capacity").text = str(volume.info()[1])
    volume_xml.find("./target/path").text = volume.path()
    xml_string = salt.utils.stringutils.to_str(ElementTree.tostring(volume_xml))
    log.debug("Creating %s", xml_string)
    return xml_string


def create_volume_with_backing_store_xml(volume):
    template = """<volume>
                    <name>n</name>
                    <capacity>c</capacity>
                    <allocation>0</allocation>
                    <target>
                        <format type='qcow2'/>
                        <compat>1.1</compat>
                    </target>
                    <backingStore>
                        <format type='qcow2'/>
                        <path>p</path>
                    </backingStore>
                </volume>
                """
    volume_xml = ElementTree.fromstring(template)
    # TODO: generate name
    volume_xml.find("name").text = generate_new_name(volume.name())
    log.debug("volume: %s", dir(volume))
    volume_xml.find("capacity").text = str(volume.info()[1])
    volume_xml.find("./backingStore/path").text = volume.path()
    xml_string = salt.utils.stringutils.to_str(ElementTree.tostring(volume_xml))
    log.debug("Creating %s", xml_string)
    return xml_string


def find_pool_and_volume(conn, path):
    # active and persistent storage pools
    # TODO: should we filter on type?
    for sp in conn.listAllStoragePools(2 + 4):
        for v in sp.listAllVolumes():
            if v.path() == path:
                return sp, v
    raise SaltCloudNotFound("Could not find volume for path {}".format(path))


def generate_new_name(orig_name):
    if "." not in orig_name:
        return "{}-{}".format(orig_name, uuid.uuid1())

    name, ext = orig_name.rsplit(".", 1)
    return "{}-{}.{}".format(name, uuid.uuid1(), ext)


def get_domain_volumes(conn, domain):
    volumes = []
    xml = ElementTree.fromstring(domain.XMLDesc(0))
    for disk in xml.findall("""./devices/disk[@device='disk'][@type='file']"""):
        if disk.find("./driver[@name='qemu'][@type='qcow2']") is not None:
            source = disk.find("./source").attrib["file"]
            try:
                pool, volume = find_pool_and_volume(conn, source)
                volumes.append(volume)
            except libvirtError:
                log.warning("Disk not found '%s'", source)
    return volumes
