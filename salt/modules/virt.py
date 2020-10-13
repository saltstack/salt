"""
Work with virtual machines managed by libvirt

:depends:
    * libvirt Python module
    * libvirt client
    * qemu-img
    * grep

Connection
==========

The connection to the virtualization host can be either setup in the minion configuration,
pillar data or overridden for each individual call.

By default, the libvirt connection URL will be guessed: the first available libvirt
hypervisor driver will be used. This can be overridden like this:

.. code-block:: yaml

    virt:
      connection:
        uri: lxc:///

If the connection requires an authentication like for ESXi, this can be defined in the
minion pillar data like this:

.. code-block:: yaml

    virt:
      connection:
        uri: esx://10.1.1.101/?no_verify=1&auto_answer=1
        auth:
          username: user
          password: secret

Connecting with SSH protocol
----------------------------

Libvirt can connect to remote hosts using SSH using one of the ``ssh``, ``libssh`` and
``libssh2`` transports. Note that ``libssh2`` is likely to fail as it doesn't read the
``known_hosts`` file. Libvirt may also have been built without ``libssh`` or ``libssh2``
support.

To use the SSH transport, on the minion setup an SSH agent with a key authorized on
the remote libvirt machine.

Per call connection setup
-------------------------

.. versionadded:: 2019.2.0

All the calls requiring the libvirt connection configuration as mentioned above can
override this configuration using ``connection``, ``username`` and ``password`` parameters.

This means that the following will list the domains on the local LXC libvirt driver,
whatever the ``virt:connection`` is.

.. code-block:: bash

    salt 'hypervisor' virt.list_domains connection=lxc:///

The calls not using the libvirt connection setup are:

- ``seed_non_shared_migrate``
- ``virt_type``
- ``is_*hyper``
- all migration functions

- `libvirt ESX URI format <http://libvirt.org/drvesx.html#uriformat>`_
- `libvirt URI format <http://libvirt.org/uri.html#URI_config>`_
- `libvirt authentication configuration <http://libvirt.org/auth.html#Auth_client_config>`_

Units
==========
.. _virt-units:
.. rubric:: Units specification
.. versionadded:: 3002

The string should contain a number optionally followed
by a unit. The number may have a decimal fraction. If
the unit is not given then MiB are set by default.
Units can optionally be given in IEC style (such as MiB),
although the standard single letter style (such as M) is
more convenient.

Valid units include:

========== =====    ==========  ==========  ======
Standard   IEC      Standard    IEC
  Unit     Unit     Name        Name        Factor
========== =====    ==========  ==========  ======
    B               Bytes                   1
    K       KiB     Kilobytes   Kibibytes   2**10
    M       MiB     Megabytes   Mebibytes   2**20
    G       GiB     Gigabytes   Gibibytes   2**30
    T       TiB     Terabytes   Tebibytes   2**40
    P       PiB     Petabytes   Pebibytes   2**50
    E       EiB     Exabytes    Exbibytes   2**60
    Z       ZiB     Zettabytes  Zebibytes   2**70
    Y       YiB     Yottabytes  Yobibytes   2**80
========== =====    ==========  ==========  ======

Additional decimal based units:

======  =======
Unit     Factor
======  =======
KB      10**3
MB      10**6
GB      10**9
TB      10**12
PB      10**15
EB      10**18
ZB      10**21
YB      10**24
======  =======
"""
# Special Thanks to Michael Dehann, many of the concepts, and a few structures
# of his in the virt func module have been used


import base64
import collections
import copy
import datetime
import logging
import os
import re
import shutil
import string  # pylint: disable=deprecated-module
import subprocess
import sys
import time
from xml.etree import ElementTree
from xml.sax import saxutils

import jinja2.exceptions
import salt.utils.data
import salt.utils.files
import salt.utils.json
import salt.utils.path
import salt.utils.stringutils
import salt.utils.templates
import salt.utils.virt
import salt.utils.xmlutil as xmlutil
import salt.utils.yaml
from salt._compat import ipaddress
from salt.exceptions import CommandExecutionError, SaltInvocationError
from salt.ext.six.moves import range  # pylint: disable=import-error,redefined-builtin
from salt.ext.six.moves.urllib.parse import urlparse, urlunparse

try:
    import libvirt  # pylint: disable=import-error

    # pylint: disable=no-name-in-module
    from libvirt import libvirtError

    # pylint: enable=no-name-in-module

    HAS_LIBVIRT = True
except ImportError:
    HAS_LIBVIRT = False


log = logging.getLogger(__name__)

# Set up template environment
JINJA = jinja2.Environment(
    loader=jinja2.FileSystemLoader(
        os.path.join(salt.utils.templates.TEMPLATE_DIRNAME, "virt")
    )
)

CACHE_DIR = "/var/lib/libvirt/saltinst"

VIRT_STATE_NAME_MAP = {
    0: "running",
    1: "running",
    2: "running",
    3: "paused",
    4: "shutdown",
    5: "shutdown",
    6: "crashed",
}


def __virtual__():
    if not HAS_LIBVIRT:
        return (False, "Unable to locate or import python libvirt library.")
    return "virt"


def __get_request_auth(username, password):
    """
    Get libvirt.openAuth callback with username, password values overriding
    the configuration ones.
    """

    # pylint: disable=unused-argument
    def __request_auth(credentials, user_data):
        """Callback method passed to libvirt.openAuth().

        The credentials argument is a list of credentials that libvirt
        would like to request. An element of this list is a list containing
        5 items (4 inputs, 1 output):
          - the credential type, e.g. libvirt.VIR_CRED_AUTHNAME
          - a prompt to be displayed to the user
          - a challenge
          - a default result for the request
          - a place to store the actual result for the request

        The user_data argument is currently not set in the openAuth call.
        """
        for credential in credentials:
            if credential[0] == libvirt.VIR_CRED_AUTHNAME:
                credential[4] = (
                    username
                    if username
                    else __salt__["config.get"](
                        "virt:connection:auth:username", credential[3]
                    )
                )
            elif credential[0] == libvirt.VIR_CRED_NOECHOPROMPT:
                credential[4] = (
                    password
                    if password
                    else __salt__["config.get"](
                        "virt:connection:auth:password", credential[3]
                    )
                )
            else:
                log.info("Unhandled credential type: %s", credential[0])
        return 0


def __get_conn(**kwargs):
    """
    Detects what type of dom this node is and attempts to connect to the
    correct hypervisor via libvirt.

    :param connection: libvirt connection URI, overriding defaults
    :param username: username to connect with, overriding defaults
    :param password: password to connect with, overriding defaults

    """
    # This has only been tested on kvm and xen, it needs to be expanded to
    # support all vm layers supported by libvirt
    # Connection string works on bhyve, but auth is not tested.

    username = kwargs.get("username", None)
    password = kwargs.get("password", None)
    conn_str = kwargs.get("connection", None)
    if not conn_str:
        conn_str = __salt__["config.get"]("virt:connection:uri", conn_str)

    try:
        auth_types = [
            libvirt.VIR_CRED_AUTHNAME,
            libvirt.VIR_CRED_NOECHOPROMPT,
            libvirt.VIR_CRED_ECHOPROMPT,
            libvirt.VIR_CRED_PASSPHRASE,
            libvirt.VIR_CRED_EXTERNAL,
        ]
        conn = libvirt.openAuth(
            conn_str, [auth_types, __get_request_auth(username, password), None], 0
        )
    except Exception:  # pylint: disable=broad-except
        raise CommandExecutionError(
            "Sorry, {} failed to open a connection to the hypervisor "
            "software at {}".format(__grains__["fqdn"], conn_str)
        )
    return conn


def _get_domain(conn, *vms, **kwargs):
    """
    Return a domain object for the named VM or return domain object for all VMs.

    :params conn: libvirt connection object
    :param vms: list of domain names to look for
    :param iterable: True to return an array in all cases
    """
    ret = list()
    lookup_vms = list()

    all_vms = []
    if kwargs.get("active", True):
        for id_ in conn.listDomainsID():
            all_vms.append(conn.lookupByID(id_).name())

    if kwargs.get("inactive", True):
        for id_ in conn.listDefinedDomains():
            all_vms.append(id_)

    if vms and not all_vms:
        raise CommandExecutionError("No virtual machines found.")

    if vms:
        for name in vms:
            if name not in all_vms:
                raise CommandExecutionError(
                    'The VM "{name}" is not present'.format(name=name)
                )
            else:
                lookup_vms.append(name)
    else:
        lookup_vms = list(all_vms)

    for name in lookup_vms:
        ret.append(conn.lookupByName(name))

    return len(ret) == 1 and not kwargs.get("iterable") and ret[0] or ret


def _parse_qemu_img_info(info):
    """
    Parse qemu-img info JSON output into disk infos dictionary
    """
    raw_infos = salt.utils.json.loads(info)
    disks = []
    for disk_infos in raw_infos:
        disk = {
            "file": disk_infos["filename"],
            "file format": disk_infos["format"],
            "disk size": disk_infos["actual-size"],
            "virtual size": disk_infos["virtual-size"],
            "cluster size": disk_infos["cluster-size"]
            if "cluster-size" in disk_infos
            else None,
        }

        if "full-backing-filename" in disk_infos.keys():
            disk["backing file"] = format(disk_infos["full-backing-filename"])

        if "snapshots" in disk_infos.keys():
            disk["snapshots"] = [
                {
                    "id": snapshot["id"],
                    "tag": snapshot["name"],
                    "vmsize": snapshot["vm-state-size"],
                    "date": datetime.datetime.fromtimestamp(
                        float(
                            "{}.{}".format(snapshot["date-sec"], snapshot["date-nsec"])
                        )
                    ).isoformat(),
                    "vmclock": datetime.datetime.utcfromtimestamp(
                        float(
                            "{}.{}".format(
                                snapshot["vm-clock-sec"], snapshot["vm-clock-nsec"]
                            )
                        )
                    )
                    .time()
                    .isoformat(),
                }
                for snapshot in disk_infos["snapshots"]
            ]
        disks.append(disk)

    for disk in disks:
        if "backing file" in disk.keys():
            candidates = [
                info
                for info in disks
                if "file" in info.keys() and info["file"] == disk["backing file"]
            ]
            if candidates:
                disk["backing file"] = candidates[0]

    return disks[0]


def _get_uuid(dom):
    """
    Return a uuid from the named vm

    CLI Example:

    .. code-block:: bash

        salt '*' virt.get_uuid <domain>
    """
    return ElementTree.fromstring(get_xml(dom)).find("uuid").text


def _get_on_poweroff(dom):
    """
    Return `on_poweroff` setting from the named vm

    CLI Example:

    .. code-block:: bash

        salt '*' virt.get_on_restart <domain>
    """
    node = ElementTree.fromstring(get_xml(dom)).find("on_poweroff")
    return node.text if node is not None else ""


def _get_on_reboot(dom):
    """
    Return `on_reboot` setting from the named vm

    CLI Example:

    .. code-block:: bash

        salt '*' virt.get_on_reboot <domain>
    """
    node = ElementTree.fromstring(get_xml(dom)).find("on_reboot")
    return node.text if node is not None else ""


def _get_on_crash(dom):
    """
    Return `on_crash` setting from the named vm

    CLI Example:

    .. code-block:: bash

        salt '*' virt.get_on_crash <domain>
    """
    node = ElementTree.fromstring(get_xml(dom)).find("on_crash")
    return node.text if node is not None else ""


def _get_nics(dom):
    """
    Get domain network interfaces from a libvirt domain object.
    """
    nics = {}
    doc = ElementTree.fromstring(dom.XMLDesc(0))
    for iface_node in doc.findall("devices/interface"):
        nic = {}
        nic["type"] = iface_node.get("type")
        for v_node in iface_node:
            if v_node.tag == "mac":
                nic["mac"] = v_node.get("address")
            if v_node.tag == "model":
                nic["model"] = v_node.get("type")
            if v_node.tag == "target":
                nic["target"] = v_node.get("dev")
            # driver, source, and match can all have optional attributes
            if re.match("(driver|source|address)", v_node.tag):
                temp = {}
                for key, value in v_node.attrib.items():
                    temp[key] = value
                nic[v_node.tag] = temp
            # virtualport needs to be handled separately, to pick up the
            # type attribute of the virtualport itself
            if v_node.tag == "virtualport":
                temp = {}
                temp["type"] = v_node.get("type")
                for key, value in v_node.attrib.items():
                    temp[key] = value
                nic["virtualport"] = temp
        if "mac" not in nic:
            continue
        nics[nic["mac"]] = nic
    return nics


def _get_graphics(dom):
    """
    Get domain graphics from a libvirt domain object.
    """
    out = {
        "autoport": "None",
        "keymap": "None",
        "listen": "None",
        "port": "None",
        "type": "None",
    }
    doc = ElementTree.fromstring(dom.XMLDesc(0))
    for g_node in doc.findall("devices/graphics"):
        for key, value in g_node.attrib.items():
            out[key] = value
    return out


def _get_loader(dom):
    """
    Get domain loader from a libvirt domain object.
    """
    out = {"path": "None"}
    doc = ElementTree.fromstring(dom.XMLDesc(0))
    for g_node in doc.findall("os/loader"):
        out["path"] = g_node.text
        for key, value in g_node.attrib.items():
            out[key] = value
    return out


def _get_disks(conn, dom):
    """
    Get domain disks from a libvirt domain object.
    """
    disks = {}
    doc = ElementTree.fromstring(dom.XMLDesc(0))
    # Get the path, pool, volume name of each volume we can
    all_volumes = _get_all_volumes_paths(conn)
    for elem in doc.findall("devices/disk"):
        source = elem.find("source")
        if source is None:
            continue
        target = elem.find("target")
        driver = elem.find("driver")
        if target is None:
            continue
        qemu_target = None
        extra_properties = None
        if "dev" in target.attrib:
            disk_type = elem.get("type")

            def _get_disk_volume_data(pool_name, volume_name):
                qemu_target = "{}/{}".format(pool_name, volume_name)
                pool = conn.storagePoolLookupByName(pool_name)
                vol = pool.storageVolLookupByName(volume_name)
                vol_info = vol.info()
                extra_properties = {
                    "virtual size": vol_info[1],
                    "disk size": vol_info[2],
                }

                backing_files = [
                    {
                        "file": node.find("source").get("file"),
                        "file format": node.find("format").get("type"),
                    }
                    for node in elem.findall(".//backingStore[source]")
                ]

                if backing_files:
                    # We had the backing files in a flat list, nest them again.
                    extra_properties["backing file"] = backing_files[0]
                    parent = extra_properties["backing file"]
                    for sub_backing_file in backing_files[1:]:
                        parent["backing file"] = sub_backing_file
                        parent = sub_backing_file

                else:
                    # In some cases the backing chain is not displayed by the domain definition
                    # Try to see if we have some of it in the volume definition.
                    vol_desc = ElementTree.fromstring(vol.XMLDesc())
                    backing_path = vol_desc.find("./backingStore/path")
                    backing_format = vol_desc.find("./backingStore/format")
                    if backing_path is not None:
                        extra_properties["backing file"] = {"file": backing_path.text}
                        if backing_format is not None:
                            extra_properties["backing file"][
                                "file format"
                            ] = backing_format.get("type")
                return (qemu_target, extra_properties)

            if disk_type == "file":
                qemu_target = source.get("file", "")
                if qemu_target.startswith("/dev/zvol/"):
                    disks[target.get("dev")] = {"file": qemu_target, "zfs": True}
                    continue

                if qemu_target in all_volumes.keys():
                    # If the qemu_target is a known path, output a volume
                    volume = all_volumes[qemu_target]
                    qemu_target, extra_properties = _get_disk_volume_data(
                        volume["pool"], volume["name"]
                    )
                elif elem.get("device", "disk") != "cdrom":
                    # Extract disk sizes, snapshots, backing files
                    try:
                        stdout = subprocess.Popen(
                            [
                                "qemu-img",
                                "info",
                                "-U",
                                "--output",
                                "json",
                                "--backing-chain",
                                qemu_target,
                            ],
                            shell=False,
                            stdout=subprocess.PIPE,
                        ).communicate()[0]
                        qemu_output = salt.utils.stringutils.to_str(stdout)
                        output = _parse_qemu_img_info(qemu_output)
                        extra_properties = output
                    except TypeError:
                        disk.update({"file": "Does not exist"})
            elif disk_type == "block":
                qemu_target = source.get("dev", "")
                # If the qemu_target is a known path, output a volume
                if qemu_target in all_volumes.keys():
                    volume = all_volumes[qemu_target]
                    qemu_target, extra_properties = _get_disk_volume_data(
                        volume["pool"], volume["name"]
                    )
            elif disk_type == "network":
                qemu_target = source.get("protocol")
                source_name = source.get("name")
                if source_name:
                    qemu_target = "{}:{}".format(qemu_target, source_name)

                # Reverse the magic for the rbd and gluster pools
                if source.get("protocol") in ["rbd", "gluster"]:
                    for pool_i in conn.listAllStoragePools():
                        pool_i_xml = ElementTree.fromstring(pool_i.XMLDesc())
                        name_node = pool_i_xml.find("source/name")
                        if name_node is not None and source_name.startswith(
                            "{}/".format(name_node.text)
                        ):
                            qemu_target = "{}{}".format(
                                pool_i.name(), source_name[len(name_node.text) :]
                            )
                            break

                # Reverse the magic for cdroms with remote URLs
                if elem.get("device", "disk") == "cdrom":
                    host_node = source.find("host")
                    if host_node is not None:
                        hostname = host_node.get("name")
                        port = host_node.get("port")
                        qemu_target = urlunparse(
                            (
                                source.get("protocol"),
                                "{}:{}".format(hostname, port) if port else hostname,
                                source_name,
                                "",
                                saxutils.unescape(source.get("query", "")),
                                "",
                            )
                        )
            elif disk_type == "volume":
                pool_name = source.get("pool")
                volume_name = source.get("volume")
                qemu_target, extra_properties = _get_disk_volume_data(
                    pool_name, volume_name
                )

            if not qemu_target:
                continue

            disk = {
                "file": qemu_target,
                "type": elem.get("device"),
            }
            if driver is not None and "type" in driver.attrib:
                disk["file format"] = driver.get("type")
            if extra_properties:
                disk.update(extra_properties)

            disks[target.get("dev")] = disk
    return disks


def _libvirt_creds():
    """
    Returns the user and group that the disk images should be owned by
    """
    g_cmd = "grep ^\\s*group /etc/libvirt/qemu.conf"
    u_cmd = "grep ^\\s*user /etc/libvirt/qemu.conf"
    try:
        stdout = subprocess.Popen(
            g_cmd, shell=True, stdout=subprocess.PIPE
        ).communicate()[0]
        group = salt.utils.stringutils.to_str(stdout).split('"')[1]
    except IndexError:
        group = "root"
    try:
        stdout = subprocess.Popen(
            u_cmd, shell=True, stdout=subprocess.PIPE
        ).communicate()[0]
        user = salt.utils.stringutils.to_str(stdout).split('"')[1]
    except IndexError:
        user = "root"
    return {"user": user, "group": group}


def _migrate(dom, dst_uri, **kwargs):
    """
    Migrate the domain object from its current host to the destination
    host given by URI.

    :param dom: domain object to migrate
    :param dst_uri: destination URI
    :param kwargs:
        - live:            Use live migration. Default value is True.
        - persistent:      Leave the domain persistent on destination host.
                           Default value is True.
        - undefinesource:  Undefine the domain on the source host.
                           Default value is True.
        - offline:         If set to True it will migrate the domain definition
                           without starting the domain on destination and without
                           stopping it on source host. Default value is False.
        - max_bandwidth:   The maximum bandwidth (in MiB/s) that will be used.
        - max_downtime:    Set maximum tolerable downtime for live-migration.
                           The value represents a number of milliseconds the guest
                           is allowed to be down at the end of live migration.
        - parallel_connections: Specify a number of parallel network connections
                           to be used to send memory pages to the destination host.
        - compressed:      Activate compression.
        - comp_methods:    A comma-separated list of compression methods. Supported
                           methods are "mt" and "xbzrle" and can be  used in any
                           combination. QEMU defaults to "xbzrle".
        - comp_mt_level:   Set compression level. Values are in range from 0 to 9,
                           where 1 is maximum speed and 9 is  maximum compression.
        - comp_mt_threads: Set number of compress threads on source host.
        - comp_mt_dthreads: Set number of decompress threads on target host.
        - comp_xbzrle_cache: Set the size of page cache for xbzrle compression in bytes.
        - copy_storage:    Migrate non-shared storage. It must be one of the following
                           values: all (full disk copy) or incremental (Incremental copy)
        - postcopy:        Enable the use of post-copy migration.
        - postcopy_bandwidth: The maximum bandwidth allowed in post-copy phase. (MiB/s)
        - username:        Username to connect with target host
        - password:        Password to connect with target host
    """
    flags = 0
    params = {}
    migrated_state = libvirt.VIR_DOMAIN_RUNNING_MIGRATED

    if kwargs.get("live", True):
        flags |= libvirt.VIR_MIGRATE_LIVE

    if kwargs.get("persistent", True):
        flags |= libvirt.VIR_MIGRATE_PERSIST_DEST

    if kwargs.get("undefinesource", True):
        flags |= libvirt.VIR_MIGRATE_UNDEFINE_SOURCE

    max_bandwidth = kwargs.get("max_bandwidth")
    if max_bandwidth:
        try:
            bandwidth_value = int(max_bandwidth)
        except ValueError:
            raise SaltInvocationError(
                "Invalid max_bandwidth value: {}".format(max_bandwidth)
            )
        dom.migrateSetMaxSpeed(bandwidth_value)

    max_downtime = kwargs.get("max_downtime")
    if max_downtime:
        try:
            downtime_value = int(max_downtime)
        except ValueError:
            raise SaltInvocationError(
                "Invalid max_downtime value: {}".format(max_downtime)
            )
        dom.migrateSetMaxDowntime(downtime_value)

    if kwargs.get("offline") is True:
        flags |= libvirt.VIR_MIGRATE_OFFLINE
        migrated_state = libvirt.VIR_DOMAIN_RUNNING_UNPAUSED

    if kwargs.get("compressed") is True:
        flags |= libvirt.VIR_MIGRATE_COMPRESSED

    comp_methods = kwargs.get("comp_methods")
    if comp_methods:
        params[libvirt.VIR_MIGRATE_PARAM_COMPRESSION] = comp_methods.split(",")

    comp_options = {
        "comp_mt_level": libvirt.VIR_MIGRATE_PARAM_COMPRESSION_MT_LEVEL,
        "comp_mt_threads": libvirt.VIR_MIGRATE_PARAM_COMPRESSION_MT_THREADS,
        "comp_mt_dthreads": libvirt.VIR_MIGRATE_PARAM_COMPRESSION_MT_DTHREADS,
        "comp_xbzrle_cache": libvirt.VIR_MIGRATE_PARAM_COMPRESSION_XBZRLE_CACHE,
    }

    for (comp_option, param_key) in comp_options.items():
        comp_option_value = kwargs.get(comp_option)
        if comp_option_value:
            try:
                params[param_key] = int(comp_option_value)
            except ValueError:
                raise SaltInvocationError("Invalid {} value".format(comp_option))

    parallel_connections = kwargs.get("parallel_connections")
    if parallel_connections:
        try:
            params[libvirt.VIR_MIGRATE_PARAM_PARALLEL_CONNECTIONS] = int(
                parallel_connections
            )
        except ValueError:
            raise SaltInvocationError("Invalid parallel_connections value")
        flags |= libvirt.VIR_MIGRATE_PARALLEL

    if __salt__["config.get"]("virt:tunnel"):
        if parallel_connections:
            raise SaltInvocationError(
                "Parallel migration isn't compatible with tunneled migration"
            )
        flags |= libvirt.VIR_MIGRATE_PEER2PEER
        flags |= libvirt.VIR_MIGRATE_TUNNELLED

    if kwargs.get("postcopy") is True:
        flags |= libvirt.VIR_MIGRATE_POSTCOPY

    postcopy_bandwidth = kwargs.get("postcopy_bandwidth")
    if postcopy_bandwidth:
        try:
            postcopy_bandwidth_value = int(postcopy_bandwidth)
        except ValueError:
            raise SaltInvocationError("Invalid postcopy_bandwidth value")
        dom.migrateSetMaxSpeed(
            postcopy_bandwidth_value,
            flags=libvirt.VIR_DOMAIN_MIGRATE_MAX_SPEED_POSTCOPY,
        )

    copy_storage = kwargs.get("copy_storage")
    if copy_storage:
        if copy_storage == "all":
            flags |= libvirt.VIR_MIGRATE_NON_SHARED_DISK
        elif copy_storage in ["inc", "incremental"]:
            flags |= libvirt.VIR_MIGRATE_NON_SHARED_INC
        else:
            raise SaltInvocationError("invalid copy_storage value")
    try:
        state = False
        dst_conn = __get_conn(
            connection=dst_uri,
            username=kwargs.get("username"),
            password=kwargs.get("password"),
        )
        new_dom = dom.migrate3(dconn=dst_conn, params=params, flags=flags)
        if new_dom:
            state = new_dom.state()
        dst_conn.close()
        return state and migrated_state in state
    except libvirt.libvirtError as err:
        dst_conn.close()
        raise CommandExecutionError(err.get_error_message())


def _get_volume_path(pool, volume_name):
    """
    Get the path to a volume. If the volume doesn't exist, compute its path from the pool one.
    """
    if volume_name in pool.listVolumes():
        volume = pool.storageVolLookupByName(volume_name)
        volume_xml = ElementTree.fromstring(volume.XMLDesc())
        return volume_xml.find("./target/path").text

    # Get the path from the pool if the volume doesn't exist yet
    pool_xml = ElementTree.fromstring(pool.XMLDesc())
    pool_path = pool_xml.find("./target/path").text
    return pool_path + "/" + volume_name


def _disk_from_pool(conn, pool, pool_xml, volume_name):
    """
    Create a disk definition out of the pool XML and volume name.
    The aim of this function is to replace the volume-based definition when not handled by libvirt.
    It returns the disk Jinja context to be used when creating the VM
    """
    pool_type = pool_xml.get("type")
    disk_context = {}

    # handle dir, fs and netfs
    if pool_type in ["dir", "netfs", "fs"]:
        disk_context["type"] = "file"
        disk_context["source_file"] = _get_volume_path(pool, volume_name)

    elif pool_type in ["logical", "disk", "iscsi", "scsi"]:
        disk_context["type"] = "block"
        disk_context["format"] = "raw"
        disk_context["source_file"] = _get_volume_path(pool, volume_name)

    elif pool_type in ["rbd", "gluster", "sheepdog"]:
        # libvirt can't handle rbd, gluster and sheepdog as volumes
        disk_context["type"] = "network"
        disk_context["protocol"] = pool_type
        # Copy the hosts from the pool definition
        disk_context["hosts"] = [
            {"name": host.get("name"), "port": host.get("port")}
            for host in pool_xml.findall(".//host")
        ]
        dir_node = pool_xml.find("./source/dir")
        # Gluster and RBD need pool/volume name
        name_node = pool_xml.find("./source/name")
        if name_node is not None:
            disk_context["volume"] = "{}/{}".format(name_node.text, volume_name)
        # Copy the authentication if any for RBD
        auth_node = pool_xml.find("./source/auth")
        if auth_node is not None:
            username = auth_node.get("username")
            secret_node = auth_node.find("./secret")
            usage = secret_node.get("usage")
            if not usage:
                # Get the usage from the UUID
                uuid = secret_node.get("uuid")
                usage = conn.secretLookupByUUIDString(uuid).usageID()
            disk_context["auth"] = {
                "type": "ceph",
                "username": username,
                "usage": usage,
            }

    return disk_context


def _handle_unit(s, def_unit="m"):
    """
    Handle the unit conversion, return the value in bytes
    """
    m = re.match(r"(?P<value>[0-9.]*)\s*(?P<unit>.*)$", str(s).strip())
    value = m.group("value")
    # default unit
    unit = m.group("unit").lower() or def_unit
    try:
        value = int(value)
    except ValueError:
        try:
            value = float(value)
        except ValueError:
            raise SaltInvocationError("invalid number")
    # flag for base ten
    dec = False
    if re.match(r"[kmgtpezy]b$", unit):
        dec = True
    elif not re.match(r"(b|[kmgtpezy](ib)?)$", unit):
        raise SaltInvocationError("invalid units")
    p = "bkmgtpezy".index(unit[0])
    value *= 10 ** (p * 3) if dec else 2 ** (p * 10)
    return int(value)


def nesthash():
    """
    create default dict that allows arbitrary level of nesting
    """
    return collections.defaultdict(nesthash)


def _gen_xml(
    conn,
    name,
    cpu,
    mem,
    diskp,
    nicp,
    hypervisor,
    os_type,
    arch,
    graphics=None,
    boot=None,
    boot_dev=None,
    **kwargs
):
    """
    Generate the XML string to define a libvirt VM
    """
    context = {
        "hypervisor": hypervisor,
        "name": name,
        "cpu": str(cpu),
    }

    context["mem"] = nesthash()
    if isinstance(mem, int):
        mem = int(mem) * 1024  # MB
        context["mem"]["boot"] = str(mem)
        context["mem"]["current"] = str(mem)
    elif isinstance(mem, dict):
        for tag, val in mem.items():
            if val:
                if tag == "slots":
                    context["mem"]["slots"] = "{}='{}'".format(tag, val)
                else:
                    context["mem"][tag] = str(int(_handle_unit(val) / 1024))

    if hypervisor in ["qemu", "kvm"]:
        context["controller_model"] = False
    elif hypervisor == "vmware":
        # TODO: make bus and model parameterized, this works for 64-bit Linux
        context["controller_model"] = "lsilogic"

    # By default, set the graphics to listen to all addresses
    if graphics:
        if "listen" not in graphics:
            graphics["listen"] = {"type": "address", "address": "0.0.0.0"}
        elif (
            "address" not in graphics["listen"]
            and graphics["listen"]["type"] == "address"
        ):
            graphics["listen"]["address"] = "0.0.0.0"

        # Graphics of type 'none' means no graphics device at all
        if graphics.get("type", "none") == "none":
            graphics = None
    context["graphics"] = graphics

    context["boot_dev"] = boot_dev.split() if boot_dev is not None else ["hd"]

    context["boot"] = boot if boot else {}

    # if efi parameter is specified, prepare os_attrib
    efi_value = context["boot"].get("efi", None) if boot else None
    if efi_value is True:
        context["boot"]["os_attrib"] = "firmware='efi'"
    elif efi_value is not None and type(efi_value) != bool:
        raise SaltInvocationError("Invalid efi value")

    if os_type == "xen":
        # Compute the Xen PV boot method
        if __grains__["os_family"] == "Suse":
            if not boot or not boot.get("kernel", None):
                context["boot"]["kernel"] = "/usr/lib/grub2/x86_64-xen/grub.xen"
                context["boot_dev"] = []

    if "serial_type" in kwargs:
        context["serial_type"] = kwargs["serial_type"]
    if "serial_type" in context and context["serial_type"] == "tcp":
        if "telnet_port" in kwargs:
            context["telnet_port"] = kwargs["telnet_port"]
        else:
            context["telnet_port"] = 23023  # FIXME: use random unused port
    if "serial_type" in context:
        if "console" in kwargs:
            context["console"] = kwargs["console"]
        else:
            context["console"] = True

    context["disks"] = []
    disk_bus_map = {"virtio": "vd", "xen": "xvd", "fdc": "fd", "ide": "hd"}
    targets = []
    for i, disk in enumerate(diskp):
        prefix = disk_bus_map.get(disk["model"], "sd")
        disk_context = {
            "device": disk.get("device", "disk"),
            "target_dev": _get_disk_target(targets, len(diskp), prefix),
            "disk_bus": disk["model"],
            "format": disk.get("format", "raw"),
            "index": str(i),
        }
        targets.append(disk_context["target_dev"])
        if disk.get("source_file"):
            url = urlparse(disk["source_file"])
            if not url.scheme or not url.hostname:
                disk_context["source_file"] = disk["source_file"]
                disk_context["type"] = "file"
            elif url.scheme in ["http", "https", "ftp", "ftps", "tftp"]:
                disk_context["type"] = "network"
                disk_context["protocol"] = url.scheme
                disk_context["volume"] = url.path
                disk_context["query"] = saxutils.escape(url.query)
                disk_context["hosts"] = [{"name": url.hostname, "port": url.port}]

        elif disk.get("pool"):
            disk_context["volume"] = disk["filename"]
            # If we had no source_file, then we want a volume
            pool = conn.storagePoolLookupByName(disk["pool"])
            pool_xml = ElementTree.fromstring(pool.XMLDesc())
            pool_type = pool_xml.get("type")

            # For Xen VMs convert all pool types (issue #58333)
            if hypervisor == "xen" or pool_type in ["rbd", "gluster", "sheepdog"]:
                disk_context.update(
                    _disk_from_pool(conn, pool, pool_xml, disk_context["volume"])
                )

            else:
                if pool_type in ["disk", "logical"]:
                    # The volume format for these types doesn't match the driver format in the VM
                    disk_context["format"] = "raw"
                disk_context["type"] = "volume"
                disk_context["pool"] = disk["pool"]

        else:
            # No source and no pool is a removable device, use file type
            disk_context["type"] = "file"

        if hypervisor in ["qemu", "kvm", "bhyve", "xen"]:
            disk_context["address"] = False
            disk_context["driver"] = True
        elif hypervisor in ["esxi", "vmware"]:
            disk_context["address"] = True
            disk_context["driver"] = False
        context["disks"].append(disk_context)
    context["nics"] = nicp

    context["os_type"] = os_type
    context["arch"] = arch

    fn_ = "libvirt_domain.jinja"
    try:
        template = JINJA.get_template(fn_)
    except jinja2.exceptions.TemplateNotFound:
        log.error("Could not load template %s", fn_)
        return ""
    return template.render(**context)


def _gen_vol_xml(
    name,
    size,
    format=None,
    allocation=0,
    type=None,
    permissions=None,
    backing_store=None,
    nocow=False,
):
    """
    Generate the XML string to define a libvirt storage volume
    """
    size = int(size) * 1024  # MB
    context = {
        "type": type,
        "name": name,
        "target": {"permissions": permissions, "nocow": nocow},
        "format": format,
        "size": str(size),
        "allocation": str(int(allocation) * 1024),
        "backingStore": backing_store,
    }
    fn_ = "libvirt_volume.jinja"
    try:
        template = JINJA.get_template(fn_)
    except jinja2.exceptions.TemplateNotFound:
        log.error("Could not load template %s", fn_)
        return ""
    return template.render(**context)


def _gen_net_xml(name, bridge, forward, vport, tag=None, ip_configs=None):
    """
    Generate the XML string to define a libvirt network
    """
    context = {
        "name": name,
        "bridge": bridge,
        "forward": forward,
        "vport": vport,
        "tag": tag,
        "ip_configs": [
            {
                "address": ipaddress.ip_network(config["cidr"]),
                "dhcp_ranges": config.get("dhcp_ranges", []),
            }
            for config in ip_configs or []
        ],
    }
    fn_ = "libvirt_network.jinja"
    try:
        template = JINJA.get_template(fn_)
    except jinja2.exceptions.TemplateNotFound:
        log.error("Could not load template %s", fn_)
        return ""
    return template.render(**context)


def _gen_pool_xml(
    name,
    ptype,
    target=None,
    permissions=None,
    source_devices=None,
    source_dir=None,
    source_adapter=None,
    source_hosts=None,
    source_auth=None,
    source_name=None,
    source_format=None,
    source_initiator=None,
):
    """
    Generate the XML string to define a libvirt storage pool
    """
    hosts = [host.split(":") for host in source_hosts or []]
    source = None
    if any(
        [
            source_devices,
            source_dir,
            source_adapter,
            hosts,
            source_auth,
            source_name,
            source_format,
            source_initiator,
        ]
    ):
        source = {
            "devices": source_devices or [],
            "dir": source_dir
            if source_format != "cifs" or not source_dir
            else source_dir.lstrip("/"),
            "adapter": source_adapter,
            "hosts": [
                {"name": host[0], "port": host[1] if len(host) > 1 else None}
                for host in hosts
            ],
            "auth": source_auth,
            "name": source_name,
            "format": source_format,
            "initiator": source_initiator,
        }

    context = {
        "name": name,
        "ptype": ptype,
        "target": {"path": target, "permissions": permissions},
        "source": source,
    }
    fn_ = "libvirt_pool.jinja"
    try:
        template = JINJA.get_template(fn_)
    except jinja2.exceptions.TemplateNotFound:
        log.error("Could not load template %s", fn_)
        return ""
    return template.render(**context)


def _gen_secret_xml(auth_type, usage, description):
    """
    Generate a libvirt secret definition XML
    """
    context = {
        "type": auth_type,
        "usage": usage,
        "description": description,
    }
    fn_ = "libvirt_secret.jinja"
    try:
        template = JINJA.get_template(fn_)
    except jinja2.exceptions.TemplateNotFound:
        log.error("Could not load template %s", fn_)
        return ""
    return template.render(**context)


def _get_images_dir():
    """
    Extract the images dir from the configuration. First attempts to
    find legacy virt.images, then tries virt:images.
    """
    img_dir = __salt__["config.get"]("virt:images")
    log.debug("Image directory from config option `virt:images`" " is %s", img_dir)
    return img_dir


def _zfs_image_create(
    vm_name,
    pool,
    disk_name,
    hostname_property_name,
    sparse_volume,
    disk_size,
    disk_image_name,
):
    """
    Clones an existing image, or creates a new one.

    When cloning an image, disk_image_name refers to the source
    of the clone. If not specified, disk_size is used for creating
    a new zvol, and sparse_volume determines whether to create
    a thin provisioned volume.

    The cloned or new volume can have a ZFS property set containing
    the vm_name. Use hostname_property_name for specifying the key
    of this ZFS property.
    """
    if not disk_image_name and not disk_size:
        raise CommandExecutionError(
            "Unable to create new disk {}, please specify"
            " the disk image name or disk size argument".format(disk_name)
        )

    if not pool:
        raise CommandExecutionError(
            "Unable to create new disk {}, please specify"
            " the disk pool name".format(disk_name)
        )

    destination_fs = os.path.join(pool, "{}.{}".format(vm_name, disk_name))
    log.debug("Image destination will be %s", destination_fs)

    existing_disk = __salt__["zfs.list"](name=pool)
    if "error" in existing_disk:
        raise CommandExecutionError(
            "Unable to create new disk {}. {}".format(
                destination_fs, existing_disk["error"]
            )
        )
    elif destination_fs in existing_disk:
        log.info(
            "ZFS filesystem {} already exists. Skipping creation".format(destination_fs)
        )
        blockdevice_path = os.path.join("/dev/zvol", pool, vm_name)
        return blockdevice_path

    properties = {}
    if hostname_property_name:
        properties[hostname_property_name] = vm_name

    if disk_image_name:
        __salt__["zfs.clone"](
            name_a=disk_image_name, name_b=destination_fs, properties=properties
        )

    elif disk_size:
        __salt__["zfs.create"](
            name=destination_fs,
            properties=properties,
            volume_size=disk_size,
            sparse=sparse_volume,
        )

    blockdevice_path = os.path.join(
        "/dev/zvol", pool, "{}.{}".format(vm_name, disk_name)
    )
    log.debug("Image path will be %s", blockdevice_path)
    return blockdevice_path


def _qemu_image_create(disk, create_overlay=False, saltenv="base"):
    """
    Create the image file using specified disk_size or/and disk_image

    Return path to the created image file
    """
    disk_size = disk.get("size", None)
    disk_image = disk.get("image", None)

    if not disk_size and not disk_image:
        raise CommandExecutionError(
            "Unable to create new disk {}, please specify"
            " disk size and/or disk image argument".format(disk["filename"])
        )

    img_dest = disk["source_file"]
    log.debug("Image destination will be %s", img_dest)
    img_dir = os.path.dirname(img_dest)
    log.debug("Image destination directory is %s", img_dir)
    if not os.path.exists(img_dir):
        os.makedirs(img_dir)

    if disk_image:
        log.debug("Create disk from specified image %s", disk_image)
        sfn = __salt__["cp.cache_file"](disk_image, saltenv)

        qcow2 = False
        if salt.utils.path.which("qemu-img"):
            res = __salt__["cmd.run"]('qemu-img info "{}"'.format(sfn))
            imageinfo = salt.utils.yaml.safe_load(res)
            qcow2 = imageinfo["file format"] == "qcow2"
        try:
            if create_overlay and qcow2:
                log.info("Cloning qcow2 image %s using copy on write", sfn)
                __salt__["cmd.run"](
                    'qemu-img create -f qcow2 -o backing_file="{}" "{}"'.format(
                        sfn, img_dest
                    ).split()
                )
            else:
                log.debug("Copying %s to %s", sfn, img_dest)
                salt.utils.files.copyfile(sfn, img_dest)

            mask = salt.utils.files.get_umask()

            if disk_size and qcow2:
                log.debug("Resize qcow2 image to %sM", disk_size)
                __salt__["cmd.run"](
                    'qemu-img resize "{}" {}M'.format(img_dest, disk_size)
                )

            log.debug("Apply umask and remove exec bit")
            mode = (0o0777 ^ mask) & 0o0666
            os.chmod(img_dest, mode)

        except OSError as err:
            raise CommandExecutionError(
                "Problem while copying image. {} - {}".format(disk_image, err)
            )

    else:
        # Create empty disk
        try:
            mask = salt.utils.files.get_umask()

            if disk_size:
                log.debug("Create empty image with size %sM", disk_size)
                __salt__["cmd.run"](
                    'qemu-img create -f {} "{}" {}M'.format(
                        disk.get("format", "qcow2"), img_dest, disk_size
                    )
                )
            else:
                raise CommandExecutionError(
                    "Unable to create new disk {},"
                    " please specify <size> argument".format(img_dest)
                )

            log.debug("Apply umask and remove exec bit")
            mode = (0o0777 ^ mask) & 0o0666
            os.chmod(img_dest, mode)

        except OSError as err:
            raise CommandExecutionError(
                "Problem while creating volume {} - {}".format(img_dest, err)
            )

    return img_dest


def _seed_image(seed_cmd, img_path, name, config, install, pub_key, priv_key):
    """
    Helper function to seed an existing image. Note that this doesn't
    handle volumes.
    """
    log.debug("Seeding image")
    __salt__[seed_cmd](
        img_path,
        id_=name,
        config=config,
        install=install,
        pub_key=pub_key,
        priv_key=priv_key,
    )


def _disk_volume_create(conn, disk, seeder=None, saltenv="base"):
    """
    Create a disk volume for use in a VM
    """
    if disk.get("overlay_image"):
        raise SaltInvocationError(
            "Disk overlay_image property is not supported when creating volumes,"
            "use backing_store_path and backing_store_format instead."
        )

    pool = conn.storagePoolLookupByName(disk["pool"])

    # Use existing volume if possible
    if disk["filename"] in pool.listVolumes():
        return

    pool_type = ElementTree.fromstring(pool.XMLDesc()).get("type")

    backing_path = disk.get("backing_store_path")
    backing_format = disk.get("backing_store_format")
    backing_store = None
    if (
        backing_path
        and backing_format
        and (disk.get("format") == "qcow2" or pool_type == "logical")
    ):
        backing_store = {"path": backing_path, "format": backing_format}

    if backing_store and disk.get("image"):
        raise SaltInvocationError(
            "Using a template image with a backing store is not possible, "
            "choose either of them."
        )

    vol_xml = _gen_vol_xml(
        disk["filename"],
        disk.get("size", 0),
        format=disk.get("format"),
        backing_store=backing_store,
    )
    _define_vol_xml_str(conn, vol_xml, disk.get("pool"))

    if disk.get("image"):
        log.debug("Caching disk template image: %s", disk.get("image"))
        cached_path = __salt__["cp.cache_file"](disk.get("image"), saltenv)

        if seeder:
            seeder(cached_path)
        _volume_upload(
            conn,
            disk["pool"],
            disk["filename"],
            cached_path,
            sparse=disk.get("format") == "qcow2",
        )


def _disk_profile(conn, profile, hypervisor, disks, vm_name):
    """
    Gather the disk profile from the config or apply the default based
    on the active hypervisor

    This is the ``default`` profile for KVM/QEMU, which can be
    overridden in the configuration:

    .. code-block:: yaml

        virt:
          disk:
            default:
              - system:
                  size: 8192
                  format: qcow2
                  model: virtio

    Example profile for KVM/QEMU with two disks, first is created
    from specified image, the second is empty:

    .. code-block:: yaml

        virt:
          disk:
            two_disks:
              - system:
                  size: 8192
                  format: qcow2
                  model: virtio
                  image: http://path/to/image.qcow2
              - lvm:
                  size: 32768
                  format: qcow2
                  model: virtio

    The ``format`` and ``model`` parameters are optional, and will
    default to whatever is best suitable for the active hypervisor.
    """
    default = [{"system": {"size": 8192}}]
    if hypervisor == "vmware":
        overlay = {"format": "vmdk", "model": "scsi", "device": "disk"}
    elif hypervisor in ["qemu", "kvm"]:
        overlay = {"device": "disk", "model": "virtio"}
    elif hypervisor == "xen":
        overlay = {"device": "disk", "model": "xen"}
    elif hypervisor == "bhyve":
        overlay = {"format": "raw", "model": "virtio", "sparse_volume": False}
    else:
        overlay = {}

    # Get the disks from the profile
    disklist = []
    if profile:
        disklist = copy.deepcopy(
            __salt__["config.get"]("virt:disk", {}).get(profile, default)
        )

        # Transform the list to remove one level of dictionary and add the name as a property
        disklist = [dict(d, name=name) for disk in disklist for name, d in disk.items()]

    # Merge with the user-provided disks definitions
    if disks:
        for udisk in disks:
            if "name" in udisk:
                found = [disk for disk in disklist if udisk["name"] == disk["name"]]
                if found:
                    found[0].update(udisk)
                else:
                    disklist.append(udisk)

    # Get pool capabilities once to get default format later
    pool_caps = _pool_capabilities(conn)

    for disk in disklist:
        # Set default model for cdrom devices before the overlay sets the wrong one
        if disk.get("device", "disk") == "cdrom" and "model" not in disk:
            disk["model"] = "ide"

        # Add the missing properties that have defaults
        for key, val in overlay.items():
            if key not in disk:
                disk[key] = val

        # We may have an already computed source_file (i.e. image not created by our module)
        if disk.get("source_file") and os.path.exists(disk["source_file"]):
            disk["filename"] = os.path.basename(disk["source_file"])
            if not disk.get("format"):
                disk["format"] = (
                    "qcow2" if disk.get("device", "disk") != "cdrom" else "raw"
                )
        elif vm_name and disk.get("device", "disk") == "disk":
            _fill_disk_filename(conn, vm_name, disk, hypervisor, pool_caps)

    return disklist


def _fill_disk_filename(conn, vm_name, disk, hypervisor, pool_caps):
    """
    Compute the disk file name and update it in the disk value.
    """
    # Compute the filename without extension since it may not make sense for some pool types
    disk["filename"] = "{}_{}".format(vm_name, disk["name"])

    # Compute the source file path
    base_dir = disk.get("pool", None)
    if hypervisor in ["qemu", "kvm", "xen"]:
        # Compute the base directory from the pool property. We may have either a path
        # or a libvirt pool name there.
        if not base_dir:
            base_dir = _get_images_dir()

        # If the pool is a known libvirt one, skip the filename since a libvirt volume will be created later
        if base_dir not in conn.listStoragePools():
            # For path-based disks, keep the qcow2 default format
            if not disk.get("format"):
                disk["format"] = "qcow2"
            disk["filename"] = "{}.{}".format(disk["filename"], disk["format"])
            disk["source_file"] = os.path.join(base_dir, disk["filename"])
        else:
            if "pool" not in disk:
                disk["pool"] = base_dir
            pool_obj = conn.storagePoolLookupByName(base_dir)
            pool_xml = ElementTree.fromstring(pool_obj.XMLDesc())
            pool_type = pool_xml.get("type")

            # Disk pools volume names are partition names, they need to be named based on the device name
            if pool_type == "disk":
                device = pool_xml.find("./source/device").get("path")
                all_volumes = pool_obj.listVolumes()
                if disk.get("source_file") not in all_volumes:
                    indexes = [
                        int(re.sub("[a-z]+", "", vol_name)) for vol_name in all_volumes
                    ] or [0]
                    index = min(
                        [
                            idx
                            for idx in range(1, max(indexes) + 2)
                            if idx not in indexes
                        ]
                    )
                    disk["filename"] = "{}{}".format(os.path.basename(device), index)

            # Is the user wanting to reuse an existing volume?
            if disk.get("source_file"):
                if not disk.get("source_file") in pool_obj.listVolumes():
                    raise SaltInvocationError(
                        "{} volume doesn't exist in pool {}".format(
                            disk.get("source_file"), base_dir
                        )
                    )
                disk["filename"] = disk["source_file"]
                del disk["source_file"]

            # Get the default format from the pool capabilities
            if not disk.get("format"):
                volume_options = (
                    [
                        type_caps.get("options", {}).get("volume", {})
                        for type_caps in pool_caps.get("pool_types")
                        if type_caps["name"] == pool_type
                    ]
                    or [{}]
                )[0]
                # Still prefer qcow2 if possible
                if "qcow2" in volume_options.get("targetFormatType", []):
                    disk["format"] = "qcow2"
                else:
                    disk["format"] = volume_options.get("default_format", None)

    elif hypervisor == "bhyve" and vm_name:
        disk["filename"] = "{}.{}".format(vm_name, disk["name"])
        disk["source_file"] = os.path.join(
            "/dev/zvol", base_dir or "", disk["filename"]
        )

    elif hypervisor in ["esxi", "vmware"]:
        if not base_dir:
            base_dir = __salt__["config.get"]("virt:storagepool", "[0] ")
        disk["filename"] = "{}.{}".format(disk["filename"], disk["format"])
        disk["source_file"] = "{}{}".format(base_dir, disk["filename"])


def _complete_nics(interfaces, hypervisor):
    """
    Complete missing data for network interfaces.
    """

    vmware_overlay = {"type": "bridge", "source": "DEFAULT", "model": "e1000"}
    kvm_overlay = {"type": "bridge", "source": "br0", "model": "virtio"}
    xen_overlay = {"type": "bridge", "source": "br0", "model": None}
    bhyve_overlay = {"type": "bridge", "source": "bridge0", "model": "virtio"}
    overlays = {
        "xen": xen_overlay,
        "kvm": kvm_overlay,
        "qemu": kvm_overlay,
        "vmware": vmware_overlay,
        "bhyve": bhyve_overlay,
    }

    def _normalize_net_types(attributes):
        """
        Guess which style of definition:

            bridge: br0

             or

            network: net0

             or

            type: network
            source: net0
        """
        for type_ in ["bridge", "network"]:
            if type_ in attributes:
                attributes["type"] = type_
                # we want to discard the original key
                attributes["source"] = attributes.pop(type_)

        attributes["type"] = attributes.get("type", None)
        attributes["source"] = attributes.get("source", None)

    def _apply_default_overlay(attributes):
        """
        Apply the default overlay to attributes
        """
        for key, value in overlays[hypervisor].items():
            if key not in attributes or not attributes[key]:
                attributes[key] = value

    for interface in interfaces:
        _normalize_net_types(interface)
        if hypervisor in overlays:
            _apply_default_overlay(interface)

    return interfaces


def _nic_profile(profile_name, hypervisor):
    """
    Compute NIC data based on profile
    """
    config_data = __salt__["config.get"]("virt:nic", {}).get(
        profile_name, [{"eth0": {}}]
    )

    interfaces = []

    # pylint: disable=invalid-name
    def append_dict_profile_to_interface_list(profile_dict):
        """
        Append dictionary profile data to interfaces list
        """
        for interface_name, attributes in profile_dict.items():
            attributes["name"] = interface_name
            interfaces.append(attributes)

    # old style dicts (top-level dicts)
    #
    # virt:
    #    nic:
    #        eth0:
    #            bridge: br0
    #        eth1:
    #            network: test_net
    if isinstance(config_data, dict):
        append_dict_profile_to_interface_list(config_data)

    # new style lists (may contain dicts)
    #
    # virt:
    #   nic:
    #     - eth0:
    #         bridge: br0
    #     - eth1:
    #         network: test_net
    #
    # virt:
    #   nic:
    #     - name: eth0
    #       bridge: br0
    #     - name: eth1
    #       network: test_net
    elif isinstance(config_data, list):
        for interface in config_data:
            if isinstance(interface, dict):
                if len(interface) == 1:
                    append_dict_profile_to_interface_list(interface)
                else:
                    interfaces.append(interface)

    return _complete_nics(interfaces, hypervisor)


def _get_merged_nics(hypervisor, profile, interfaces=None):
    """
    Get network devices from the profile and merge uer defined ones with them.
    """
    nicp = _nic_profile(profile, hypervisor) if profile else []
    log.debug("NIC profile is %s", nicp)
    if interfaces:
        users_nics = _complete_nics(interfaces, hypervisor)
        for unic in users_nics:
            found = [nic for nic in nicp if nic["name"] == unic["name"]]
            if found:
                found[0].update(unic)
            else:
                nicp.append(unic)
        log.debug("Merged NICs: %s", nicp)
    return nicp


def _handle_remote_boot_params(orig_boot):
    """
    Checks if the boot parameters contain a remote path. If so, it will copy
    the parameters, download the files specified in the remote path, and return
    a new dictionary with updated paths containing the canonical path to the
    kernel and/or initrd

    :param orig_boot: The original boot parameters passed to the init or update
    functions.
    """
    saltinst_dir = None
    new_boot = orig_boot.copy()
    keys = orig_boot.keys()
    cases = [
        {"efi"},
        {"kernel", "initrd", "efi"},
        {"kernel", "initrd", "cmdline", "efi"},
        {"loader", "nvram"},
        {"kernel", "initrd"},
        {"kernel", "initrd", "cmdline"},
        {"kernel", "initrd", "loader", "nvram"},
        {"kernel", "initrd", "cmdline", "loader", "nvram"},
    ]

    try:
        if keys in cases:
            for key in keys:
                if key == "efi" and type(orig_boot.get(key)) == bool:
                    new_boot[key] = orig_boot.get(key)
                elif orig_boot.get(key) is not None and salt.utils.virt.check_remote(
                    orig_boot.get(key)
                ):
                    if saltinst_dir is None:
                        os.makedirs(CACHE_DIR)
                        saltinst_dir = CACHE_DIR
                    new_boot[key] = salt.utils.virt.download_remote(
                        orig_boot.get(key), saltinst_dir
                    )
            return new_boot
        else:
            raise SaltInvocationError(
                "Invalid boot parameters,It has to follow this combination: [(kernel, initrd) or/and cmdline] or/and [(loader, nvram) or efi]"
            )
    except Exception as err:  # pylint: disable=broad-except
        raise err


def _handle_efi_param(boot, desc):
    """
    Checks if boot parameter contains efi boolean value, if so, handles the firmware attribute.
    :param boot: The boot parameters passed to the init or update functions.
    :param desc: The XML description of that domain.
    :return: A boolean value.
    """
    efi_value = boot.get("efi", None) if boot else None
    parent_tag = desc.find("os")
    os_attrib = parent_tag.attrib

    # newly defined vm without running, loader tag might not be filled yet
    if efi_value is False and os_attrib != {}:
        parent_tag.attrib.pop("firmware", None)
        return True

    # check the case that loader tag might be present. This happens after the vm ran
    elif type(efi_value) == bool and os_attrib == {}:
        if efi_value is True and parent_tag.find("loader") is None:
            parent_tag.set("firmware", "efi")
        if efi_value is False and parent_tag.find("loader") is not None:
            parent_tag.remove(parent_tag.find("loader"))
            parent_tag.remove(parent_tag.find("nvram"))
        return True
    elif type(efi_value) != bool:
        raise SaltInvocationError("Invalid efi value")
    return False


def init(
    name,
    cpu,
    mem,
    nic="default",
    interfaces=None,
    hypervisor=None,
    start=True,  # pylint: disable=redefined-outer-name
    disk="default",
    disks=None,
    saltenv="base",
    seed=True,
    install=True,
    pub_key=None,
    priv_key=None,
    seed_cmd="seed.apply",
    graphics=None,
    os_type=None,
    arch=None,
    boot=None,
    boot_dev=None,
    **kwargs
):
    """
    Initialize a new vm

    :param name: name of the virtual machine to create
    :param cpu: Number of virtual CPUs to assign to the virtual machine
    :param mem: Amount of memory to allocate to the virtual machine in MiB. Since 3002, a dictionary can be used to
        contain detailed configuration which support memory allocation or tuning. Supported parameters are ``boot``,
        ``current``, ``max``, ``slots``, ``hard_limit``, ``soft_limit``, ``swap_hard_limit`` and ``min_guarantee``. The
        structure of the dictionary is documented in  :ref:`init-mem-def`. Both decimal and binary base are supported.
        Detail unit specification is documented  in :ref:`virt-units`. Please note that the value for ``slots`` must be
        an integer.

        .. code-block:: python

            {
                'boot': 1g,
                'current': 1g,
                'max': 1g,
                'slots': 10,
                'hard_limit': '1024'
                'soft_limit': '512m'
                'swap_hard_limit': '1g'
                'min_guarantee': '512mib'
            }

        .. versionchanged:: 3002

    :param nic: NIC profile to use (Default: ``'default'``).
                The profile interfaces can be customized / extended with the interfaces parameter.
                If set to ``None``, no profile will be used.
    :param interfaces:
        List of dictionaries providing details on the network interfaces to create.
        These data are merged with the ones from the nic profile. The structure of
        each dictionary is documented in :ref:`init-nic-def`.

        .. versionadded:: 2019.2.0
    :param hypervisor: the virtual machine type. By default the value will be computed according
                       to the virtual host capabilities.
    :param start: ``True`` to start the virtual machine after having defined it (Default: ``True``)
    :param disk: Disk profile to use (Default: ``'default'``). If set to ``None``, no profile will be used.
    :param disks: List of dictionaries providing details on the disk devices to create.
                  These data are merged with the ones from the disk profile. The structure of
                  each dictionary is documented in :ref:`init-disk-def`.

                  .. versionadded:: 2019.2.0
    :param saltenv: Fileserver environment (Default: ``'base'``).
                    See :mod:`cp module for more details <salt.modules.cp>`
    :param seed: ``True`` to seed the disk image. Only used when the ``image`` parameter is provided.
                 (Default: ``True``)
    :param install: install salt minion if absent (Default: ``True``)
    :param pub_key: public key to seed with (Default: ``None``)
    :param priv_key: public key to seed with (Default: ``None``)
    :param seed_cmd: Salt command to execute to seed the image. (Default: ``'seed.apply'``)
    :param graphics:
        Dictionary providing details on the graphics device to create. (Default: ``None``)
        See :ref:`init-graphics-def` for more details on the possible values.

        .. versionadded:: 2019.2.0
    :param os_type:
        type of virtualization as found in the ``//os/type`` element of the libvirt definition.
        The default value is taken from the host capabilities, with a preference for ``hvm``.

        .. versionadded:: 2019.2.0
    :param arch:
        architecture of the virtual machine. The default value is taken from the host capabilities,
        but ``x86_64`` is prefed over ``i686``.

        .. versionadded:: 2019.2.0
    :param config: minion configuration to use when seeding.
                   See :mod:`seed module for more details <salt.modules.seed>`
    :param boot_dev: String of space-separated devices to boot from (Default: ``'hd'``)
    :param serial_type: Serial device type. One of ``'pty'``, ``'tcp'`` (Default: ``None``)
    :param telnet_port: Telnet port to use for serial device of type ``tcp``.
    :param console: ``True`` to add a console device along with serial one (Default: ``True``)
    :param connection: libvirt connection URI, overriding defaults

                       .. versionadded:: 2019.2.0
    :param username: username to connect with, overriding defaults

                     .. versionadded:: 2019.2.0
    :param password: password to connect with, overriding defaults

                     .. versionadded:: 2019.2.0
    :param boot:
        Specifies kernel, initial ramdisk and kernel command line parameters for the virtual machine.
        This is an optional parameter, all of the keys are optional within the dictionary. The structure of
        the dictionary is documented in :ref:`init-boot-def`. If a remote path is provided to kernel or initrd,
        salt will handle the downloading of the specified remote file and modify the XML accordingly.
        To boot VM with UEFI, specify loader and nvram path or specify 'efi': ``True`` if your libvirtd version
        is >= 5.2.0 and QEMU >= 3.0.0.

        .. versionadded:: 3000

        .. code-block:: python

            {
                'kernel': '/root/f8-i386-vmlinuz',
                'initrd': '/root/f8-i386-initrd',
                'cmdline': 'console=ttyS0 ks=http://example.com/f8-i386/os/',
                'loader': '/usr/share/OVMF/OVMF_CODE.fd',
                'nvram': '/usr/share/OVMF/OVMF_VARS.ms.fd'
            }

    :param boot_dev:
        Space separated list of devices to boot from sorted by decreasing priority.
        Values can be ``hd``, ``fd``, ``cdrom`` or ``network``.

        By default, the value will ``"hd"``.

    .. _init-boot-def:

    .. rubric:: Boot parameters definition

    The boot parameters dictionary can contains the following properties:

    kernel
        The URL or path to the kernel to run the virtual machine with.

    initrd
        The URL or path to the initrd file to run the virtual machine with.

    cmdline
        The parameters to pass to the kernel provided in the `kernel` property.

    loader
        The path to the UEFI binary loader to use.

        .. versionadded:: 3001

    nvram
        The path to the UEFI data template. The file will be copied when creating the virtual machine.

        .. versionadded:: 3001

    efi
       A boolean value.

       .. versionadded:: sodium

    .. _init-mem-def:

    .. rubric:: Memory parameter definition

    Memory parameter can contain the following properties:

    boot
        The maximum allocation of memory for the guest at boot time

    current
        The actual allocation of memory for the guest

    max
        The run time maximum memory allocation of the guest

    slots
         specifies the number of slots available for adding memory to the guest

    hard_limit
        the maximum memory the guest can use

    soft_limit
        memory limit to enforce during memory contention

    swap_hard_limit
        the maximum memory plus swap the guest can use

    min_guarantee
        the guaranteed minimum memory allocation for the guest

    .. _init-nic-def:

    .. rubric:: Network Interfaces Definitions

    Network interfaces dictionaries can contain the following properties:

    name
        Name of the network interface. This is only used as a key to merge with the profile data

    type
        Network type. One of ``'bridge'``, ``'network'``

    source
        The network source, typically the bridge or network name

    mac
        The desired mac address, computed if ``None`` (Default: ``None``).

    model
        The network card model (Default: depends on the hypervisor)

    .. _init-disk-def:

    .. rubric:: Disks Definitions

    Disk dictionaries can contain the following properties:

    name
        Name of the disk. This is mostly used in the name of the disk image and as a key to merge
        with the profile data.

    format
        Format of the disk image, like ``'qcow2'``, ``'raw'``, ``'vmdk'``.
        (Default: depends on the hypervisor)

    size
        Disk size in MiB

    pool
        Path to the folder or name of the pool where disks should be created.
        (Default: depends on hypervisor and the virt:storagepool configuration)

        .. versionchanged:: 3001

        If the value contains no '/', it is considered a pool name where to create a volume.
        Using volumes will be mandatory for some pools types like rdb, iscsi, etc.

    model
        One of the disk busses allowed by libvirt (Default: depends on hypervisor)

        See the libvirt `disk element`_ documentation for the allowed bus types.

    image
        Path to the image to use for the disk. If no image is provided, an empty disk will be created
        (Default: ``None``)

        Note that some pool types do not support uploading an image. This list can evolve with libvirt
        versions.

    overlay_image
        ``True`` to create a QCOW2 disk image with ``image`` as backing file. If ``False``
        the file pointed to by the ``image`` property will simply be copied. (Default: ``False``)

        .. versionchanged:: 3001

        This property is only valid on path-based disks, not on volumes. To create a volume with a
        backing store, set the ``backing_store_path`` and ``backing_store_format`` properties.

    backing_store_path
        Path to the backing store image to use. This can also be the name of a volume to use as
        backing store within the same pool.

        .. versionadded:: 3001

    backing_store_format
        Image format of the disk or volume to use as backing store. This property is mandatory when
        using ``backing_store_path`` to avoid `problems <https://libvirt.org/kbase/backing_chains.html#troubleshooting>`_

        .. versionadded:: 3001

    source_file
        Absolute path to the disk image to use. Not to be confused with ``image`` parameter. This
        parameter is useful to use disk images that are created outside of this module. Can also
        be ``None`` for devices that have no associated image like cdroms.

        .. versionchanged:: 3001

        For volume disks, this can be the name of a volume already existing in the storage pool.

    device
        Type of device of the disk. Can be one of 'disk', 'cdrom', 'floppy' or 'lun'.
        (Default: ``'disk'``)

    hostname_property
        When using ZFS volumes, setting this value to a ZFS property ID will make Salt store the name of the
        virtual machine inside this property. (Default: ``None``)

    sparse_volume
        Boolean to specify whether to use a thin provisioned ZFS volume.

        Example profile for a bhyve VM with two ZFS disks. The first is
        cloned from the specified image. The second disk is a thin
        provisioned volume.

        .. code-block:: yaml

            virt:
              disk:
                two_zvols:
                  - system:
                      image: zroot/bhyve/CentOS-7-x86_64-v1@v1.0.5
                      hostname_property: virt:hostname
                      pool: zroot/bhyve/guests
                  - data:
                      pool: tank/disks
                      size: 20G
                      hostname_property: virt:hostname
                      sparse_volume: True

    .. _init-graphics-def:

    .. rubric:: Graphics Definition

    The graphics dictionary can have the following properties:

    type
        Graphics type. The possible values are ``none``, ``'spice'``, ``'vnc'`` and other values
        allowed as a libvirt graphics type (Default: ``None``)

        See the libvirt `graphics element`_ documentation for more details on the possible types.

    port
        Port to export the graphics on for ``vnc``, ``spice`` and ``rdp`` types.

    tls_port
        Port to export the graphics over a secured connection for ``spice`` type.

    listen
        Dictionary defining on what address to listen on for ``vnc``, ``spice`` and ``rdp``.
        It has a ``type`` property with ``address`` and ``None`` as possible values, and an
        ``address`` property holding the IP or hostname to listen on.

        By default, not setting the ``listen`` part of the dictionary will default to
        listen on all addresses.

    .. rubric:: CLI Example

    .. code-block:: bash

        salt 'hypervisor' virt.init vm_name 4 512 salt://path/to/image.raw
        salt 'hypervisor' virt.init vm_name 4 512 /var/lib/libvirt/images/img.raw
        salt 'hypervisor' virt.init vm_name 4 512 nic=profile disk=profile

    The disk images will be created in an image folder within the directory
    defined by the ``virt:images`` option. Its default value is
    ``/srv/salt-images/`` but this can changed with such a configuration:

    .. code-block:: yaml

        virt:
            images: /data/my/vm/images/

    .. _disk element: https://libvirt.org/formatdomain.html#elementsDisks
    .. _graphics element: https://libvirt.org/formatdomain.html#elementsGraphics
    """
    try:
        conn = __get_conn(**kwargs)
        caps = _capabilities(conn)
        os_types = sorted({guest["os_type"] for guest in caps["guests"]})
        arches = sorted({guest["arch"]["name"] for guest in caps["guests"]})

        virt_hypervisor = hypervisor
        if not virt_hypervisor:
            # Use the machine types as possible values
            # Prefer 'kvm' over the others if available
            hypervisors = sorted(
                {
                    x
                    for y in [
                        guest["arch"]["domains"].keys() for guest in caps["guests"]
                    ]
                    for x in y
                }
            )
            if len(hypervisors) == 0:
                raise SaltInvocationError("No supported hypervisors were found")
            virt_hypervisor = "kvm" if "kvm" in hypervisors else hypervisors[0]

        # esxi used to be a possible value for the hypervisor: map it to vmware since it's the same
        virt_hypervisor = "vmware" if virt_hypervisor == "esxi" else virt_hypervisor

        log.debug("Using hypervisor %s", virt_hypervisor)

        nicp = _get_merged_nics(virt_hypervisor, nic, interfaces)

        # the disks are computed as follows:
        # 1 - get the disks defined in the profile
        # 3 - update the disks from the profile with the ones from the user. The matching key is the name.
        diskp = _disk_profile(conn, disk, virt_hypervisor, disks, name)

        # Create multiple disks, empty or from specified images.
        for _disk in diskp:
            # No need to create an image for cdrom devices
            if _disk.get("device", "disk") == "cdrom":
                continue

            log.debug("Creating disk for VM [ %s ]: %s", name, _disk)

            if virt_hypervisor == "vmware":
                if "image" in _disk:
                    # TODO: we should be copying the image file onto the ESX host
                    raise SaltInvocationError(
                        "virt.init does not support image "
                        "template in conjunction with esxi hypervisor"
                    )
                else:
                    # assume libvirt manages disks for us
                    log.debug("Generating libvirt XML for %s", _disk)
                    volume_name = "{}/{}".format(name, _disk["name"])
                    filename = "{}.{}".format(volume_name, _disk["format"])
                    vol_xml = _gen_vol_xml(
                        filename, _disk["size"], format=_disk["format"]
                    )
                    _define_vol_xml_str(conn, vol_xml, pool=_disk.get("pool"))

            elif virt_hypervisor in ["qemu", "kvm", "xen"]:

                def seeder(path):
                    _seed_image(
                        seed_cmd,
                        path,
                        name,
                        kwargs.get("config"),
                        install,
                        pub_key,
                        priv_key,
                    )

                create_overlay = _disk.get("overlay_image", False)
                format = _disk.get("format")
                if _disk.get("source_file"):
                    if os.path.exists(_disk["source_file"]):
                        img_dest = _disk["source_file"]
                    else:
                        img_dest = _qemu_image_create(_disk, create_overlay, saltenv)
                else:
                    _disk_volume_create(conn, _disk, seeder if seed else None, saltenv)
                    img_dest = None

                # Seed only if there is an image specified
                if seed and img_dest and _disk.get("image", None):
                    seeder(img_dest)

            elif hypervisor in ["bhyve"]:
                img_dest = _zfs_image_create(
                    vm_name=name,
                    pool=_disk.get("pool"),
                    disk_name=_disk.get("name"),
                    disk_size=_disk.get("size"),
                    disk_image_name=_disk.get("image"),
                    hostname_property_name=_disk.get("hostname_property"),
                    sparse_volume=_disk.get("sparse_volume"),
                )

            else:
                # Unknown hypervisor
                raise SaltInvocationError(
                    "Unsupported hypervisor when handling disk image: {}".format(
                        virt_hypervisor
                    )
                )

        log.debug("Generating VM XML")
        if os_type is None:
            os_type = "hvm" if "hvm" in os_types else os_types[0]
        if arch is None:
            arch = "x86_64" if "x86_64" in arches else arches[0]

        if boot is not None:
            boot = _handle_remote_boot_params(boot)

        vm_xml = _gen_xml(
            conn,
            name,
            cpu,
            mem,
            diskp,
            nicp,
            virt_hypervisor,
            os_type,
            arch,
            graphics,
            boot,
            boot_dev,
            **kwargs
        )
        log.debug("New virtual machine definition: %s", vm_xml)
        conn.defineXML(vm_xml)
    except libvirt.libvirtError as err:
        conn.close()
        raise CommandExecutionError(err.get_error_message())

    if start:
        log.debug("Starting VM %s", name)
        _get_domain(conn, name).create()
    conn.close()

    return True


def _disks_equal(disk1, disk2):
    """
    Test if two disk elements should be considered like the same device
    """
    target1 = disk1.find("target")
    target2 = disk2.find("target")
    source1 = (
        disk1.find("source")
        if disk1.find("source") is not None
        else ElementTree.Element("source")
    )
    source2 = (
        disk2.find("source")
        if disk2.find("source") is not None
        else ElementTree.Element("source")
    )

    source1_dict = xmlutil.to_dict(source1, True)
    source2_dict = xmlutil.to_dict(source2, True)

    # Remove the index added by libvirt in the source for backing chain
    if source1_dict:
        source1_dict.pop("index", None)
    if source2_dict:
        source2_dict.pop("index", None)

    return (
        source1_dict == source2_dict
        and target1 is not None
        and target2 is not None
        and target1.get("bus") == target2.get("bus")
        and disk1.get("device", "disk") == disk2.get("device", "disk")
        and target1.get("dev") == target2.get("dev")
    )


def _nics_equal(nic1, nic2):
    """
    Test if two interface elements should be considered like the same device
    """

    def _filter_nic(nic):
        """
        Filter out elements to ignore when comparing nics
        """
        return {
            "type": nic.attrib["type"],
            "source": nic.find("source").attrib[nic.attrib["type"]]
            if nic.find("source") is not None
            else None,
            "model": nic.find("model").attrib["type"]
            if nic.find("model") is not None
            else None,
        }

    def _get_mac(nic):
        return (
            nic.find("mac").attrib["address"].lower()
            if nic.find("mac") is not None
            else None
        )

    mac1 = _get_mac(nic1)
    mac2 = _get_mac(nic2)
    macs_equal = not mac1 or not mac2 or mac1 == mac2
    return _filter_nic(nic1) == _filter_nic(nic2) and macs_equal


def _graphics_equal(gfx1, gfx2):
    """
    Test if two graphics devices should be considered the same device
    """

    def _filter_graphics(gfx):
        """
        When the domain is running, the graphics element may contain additional properties
        with the default values. This function will strip down the default values.
        """
        gfx_copy = copy.deepcopy(gfx)

        defaults = [
            {"node": ".", "attrib": "port", "values": ["5900", "-1"]},
            {"node": ".", "attrib": "address", "values": ["127.0.0.1"]},
            {"node": "listen", "attrib": "address", "values": ["127.0.0.1"]},
        ]

        for default in defaults:
            node = gfx_copy.find(default["node"])
            attrib = default["attrib"]
            if node is not None and (
                attrib in node.attrib and node.attrib[attrib] in default["values"]
            ):
                node.attrib.pop(attrib)
        return gfx_copy

    return xmlutil.to_dict(_filter_graphics(gfx1), True) == xmlutil.to_dict(
        _filter_graphics(gfx2), True
    )


def _diff_lists(old, new, comparator):
    """
    Compare lists to extract the changes

    :param old: old list
    :param new: new list
    :return: a dictionary with ``unchanged``, ``new``, ``deleted`` and ``sorted`` keys

    The sorted list is the union of unchanged and new lists, but keeping the original
    order from the new list.
    """

    def _remove_indent(node):
        """
        Remove the XML indentation to compare XML trees more easily
        """
        node_copy = copy.deepcopy(node)
        node_copy.text = None
        for item in node_copy.iter():
            item.tail = None
        return node_copy

    diff = {"unchanged": [], "new": [], "deleted": [], "sorted": []}
    # We don't want to alter old since it may be used later by caller
    old_devices = copy.deepcopy(old)
    for new_item in new:
        found = [
            item
            for item in old_devices
            if comparator(_remove_indent(item), _remove_indent(new_item))
        ]
        if found:
            old_devices.remove(found[0])
            diff["unchanged"].append(found[0])
            diff["sorted"].append(found[0])
        else:
            diff["new"].append(new_item)
            diff["sorted"].append(new_item)
    diff["deleted"] = old_devices
    return diff


def _get_disk_target(targets, disks_count, prefix):
    """
    Compute the disk target name for a given prefix.

    :param targets: the list of already computed targets
    :param disks: the number of disks
    :param prefix: the prefix of the target name, i.e. "hd"
    """
    for i in range(disks_count):
        ret = "{}{}".format(prefix, string.ascii_lowercase[i])
        if ret not in targets:
            return ret
    return None


def _diff_disk_lists(old, new):
    """
    Compare disk definitions to extract the changes and fix target devices

    :param old: list of ElementTree nodes representing the old disks
    :param new: list of ElementTree nodes representing the new disks
    """
    # Change the target device to avoid duplicates before diffing: this may lead
    # to additional changes. Think of unchanged disk 'hda' and another disk listed
    # before it becoming 'hda' too... the unchanged need to turn into 'hdb'.
    targets = []
    prefixes = ["fd", "hd", "vd", "sd", "xvd", "ubd"]
    for disk in new:
        target_node = disk.find("target")
        target = target_node.get("dev")
        prefix = [item for item in prefixes if target.startswith(item)][0]
        new_target = _get_disk_target(targets, len(new), prefix)
        target_node.set("dev", new_target)
        targets.append(new_target)

    return _diff_lists(old, new, _disks_equal)


def _diff_interface_lists(old, new):
    """
    Compare network interface definitions to extract the changes

    :param old: list of ElementTree nodes representing the old interfaces
    :param new: list of ElementTree nodes representing the new interfaces
    """
    return _diff_lists(old, new, _nics_equal)


def _diff_graphics_lists(old, new):
    """
    Compare graphic devices definitions to extract the changes

    :param old: list of ElementTree nodes representing the old graphic devices
    :param new: list of ElementTree nodes representing the new graphic devices
    """
    return _diff_lists(old, new, _graphics_equal)


def update(
    name,
    cpu=0,
    mem=0,
    disk_profile=None,
    disks=None,
    nic_profile=None,
    interfaces=None,
    graphics=None,
    live=True,
    boot=None,
    test=False,
    boot_dev=None,
    **kwargs
):
    """
    Update the definition of an existing domain.

    :param name: Name of the domain to update
    :param cpu: Number of virtual CPUs to assign to the virtual machine
    :param mem: Amount of memory to allocate to the virtual machine in MiB. Since 3002, a dictionary can be used to
        contain detailed configuration which support memory allocation or tuning. Supported parameters are ``boot``,
        ``current``, ``max``, ``slots``, ``hard_limit``, ``soft_limit``, ``swap_hard_limit`` and ``min_guarantee``. The
        structure of the dictionary is documented in  :ref:`init-mem-def`. Both decimal and binary base are supported.
        Detail unit specification is documented  in :ref:`virt-units`. Please note that the value for ``slots`` must be
        an integer.

        To remove any parameters, pass a None object, for instance: 'soft_limit': ``None``. Please note  that ``None``
        is mapped to ``null`` in sls file, pass ``null`` in sls file instead.

        .. code-block:: yaml

            - mem:
                hard_limit: null
                soft_limit: null

        .. versionchanged:: 3002

    :param disk_profile: disk profile to use
    :param disks:
        Disk definitions as documented in the :func:`init` function.
        If neither the profile nor this parameter are defined, the disk devices
        will not be changed. However to clear disks set this parameter to empty list.

    :param nic_profile: network interfaces profile to use
    :param interfaces:
        Network interface definitions as documented in the :func:`init` function.
        If neither the profile nor this parameter are defined, the interface devices
        will not be changed. However to clear network interfaces set this parameter
        to empty list.

    :param graphics:
        The new graphics definition as defined in :ref:`init-graphics-def`. If not set,
        the graphics will not be changed. To remove a graphics device, set this parameter
        to ``{'type': 'none'}``.

    :param live:
        ``False`` to avoid trying to live update the definition. In such a case, the
        new definition is applied at the next start of the virtual machine. If ``True``,
        not all aspects of the definition can be live updated, but as much as possible
        will be attempted. (Default: ``True``)

    :param connection: libvirt connection URI, overriding defaults
    :param username: username to connect with, overriding defaults
    :param password: password to connect with, overriding defaults

    :param boot:
        Specifies kernel, initial ramdisk and kernel command line parameters for the virtual machine.
        This is an optional parameter, all of the keys are optional within the dictionary.

        Refer to :ref:`init-boot-def` for the complete boot parameter description.

        To update any boot parameters, specify the new path for each. To remove any boot parameters, pass ``None`` object,
        for instance: 'kernel': ``None``. To switch back to BIOS boot, specify ('loader': ``None`` and 'nvram': ``None``)
        or 'efi': ``False``. Please note that ``None`` is mapped to ``null`` in sls file, pass ``null`` in sls file instead.

        SLS file Example:

        .. code-block:: yaml

            - boot:
                loader: null
                nvram: null

        .. versionadded:: 3000

    :param boot_dev:
        Space separated list of devices to boot from sorted by decreasing priority.
        Values can be ``hd``, ``fd``, ``cdrom`` or ``network``.

        By default, the value will ``"hd"``.

        .. versionadded:: 3002

    :param test: run in dry-run mode if set to True

        .. versionadded:: 3001

    :return:

        Returns a dictionary indicating the status of what has been done. It is structured in
        the following way:

        .. code-block:: python

            {
              'definition': True,
              'cpu': True,
              'mem': True,
              'disks': {'attached': [list of actually attached disks],
                        'detached': [list of actually detached disks]},
              'nics': {'attached': [list of actually attached nics],
                       'detached': [list of actually detached nics]},
              'errors': ['error messages for failures']
            }

    .. versionadded:: 2019.2.0

    CLI Example:

    .. code-block:: bash

        salt '*' virt.update domain cpu=2 mem=1024

    """
    status = {
        "definition": False,
        "disk": {"attached": [], "detached": [], "updated": []},
        "interface": {"attached": [], "detached": []},
    }
    conn = __get_conn(**kwargs)
    domain = _get_domain(conn, name)
    desc = ElementTree.fromstring(domain.XMLDesc(0))
    need_update = False

    # Compute the XML to get the disks, interfaces and graphics
    hypervisor = desc.get("type")
    all_disks = _disk_profile(conn, disk_profile, hypervisor, disks, name)

    if boot is not None:
        boot = _handle_remote_boot_params(boot)
        if boot.get("efi", None) is not None:
            need_update = _handle_efi_param(boot, desc)

    new_desc = ElementTree.fromstring(
        _gen_xml(
            conn,
            name,
            cpu or 0,
            mem or 0,
            all_disks,
            _get_merged_nics(hypervisor, nic_profile, interfaces),
            hypervisor,
            domain.OSType(),
            desc.find(".//os/type").get("arch"),
            graphics,
            boot,
            **kwargs
        )
    )

    # Update the cpu
    cpu_node = desc.find("vcpu")
    if cpu and int(cpu_node.text) != cpu:
        cpu_node.text = str(cpu)
        cpu_node.set("current", str(cpu))
        need_update = True

    def _set_loader(node, value):
        salt.utils.xmlutil.set_node_text(node, value)
        if value is not None:
            node.set("readonly", "yes")
            node.set("type", "pflash")

    def _set_nvram(node, value):
        node.set("template", value)

    def _set_with_byte_unit(node, value):
        node.text = str(value)
        node.set("unit", "bytes")

    def _get_with_unit(node):
        unit = node.get("unit", "KiB")
        # _handle_unit treats bytes as invalid unit for the purpose of consistency
        unit = unit if unit != "bytes" else "b"
        value = node.get("memory") or node.text
        return _handle_unit("{}{}".format(value, unit)) if value else None

    old_mem = int(_get_with_unit(desc.find("memory")) / 1024)

    # Update the kernel boot parameters
    params_mapping = [
        {"path": "boot:kernel", "xpath": "os/kernel"},
        {"path": "boot:initrd", "xpath": "os/initrd"},
        {"path": "boot:cmdline", "xpath": "os/cmdline"},
        {"path": "boot:loader", "xpath": "os/loader", "set": _set_loader},
        {"path": "boot:nvram", "xpath": "os/nvram", "set": _set_nvram},
        # Update the memory, note that libvirt outputs all memory sizes in KiB
        {
            "path": "mem",
            "xpath": "memory",
            "convert": _handle_unit,
            "get": _get_with_unit,
            "set": _set_with_byte_unit,
        },
        {
            "path": "mem",
            "xpath": "currentMemory",
            "convert": _handle_unit,
            "get": _get_with_unit,
            "set": _set_with_byte_unit,
        },
        {
            "path": "mem:max",
            "convert": _handle_unit,
            "xpath": "maxMemory",
            "get": _get_with_unit,
            "set": _set_with_byte_unit,
        },
        {
            "path": "mem:boot",
            "convert": _handle_unit,
            "xpath": "memory",
            "get": _get_with_unit,
            "set": _set_with_byte_unit,
        },
        {
            "path": "mem:current",
            "convert": _handle_unit,
            "xpath": "currentMemory",
            "get": _get_with_unit,
            "set": _set_with_byte_unit,
        },
        {
            "path": "mem:slots",
            "xpath": "maxMemory",
            "get": lambda n: n.get("slots"),
            "set": lambda n, v: n.set("slots", str(v)),
            "del": salt.utils.xmlutil.del_attribute("slots", ["unit"]),
        },
        {
            "path": "mem:hard_limit",
            "convert": _handle_unit,
            "xpath": "memtune/hard_limit",
            "get": _get_with_unit,
            "set": _set_with_byte_unit,
        },
        {
            "path": "mem:soft_limit",
            "convert": _handle_unit,
            "xpath": "memtune/soft_limit",
            "get": _get_with_unit,
            "set": _set_with_byte_unit,
        },
        {
            "path": "mem:swap_hard_limit",
            "convert": _handle_unit,
            "xpath": "memtune/swap_hard_limit",
            "get": _get_with_unit,
            "set": _set_with_byte_unit,
        },
        {
            "path": "mem:min_guarantee",
            "convert": _handle_unit,
            "xpath": "memtune/min_guarantee",
            "get": _get_with_unit,
            "set": _set_with_byte_unit,
        },
        {
            "path": "boot_dev:{dev}",
            "xpath": "os/boot[$dev]",
            "get": lambda n: n.get("dev"),
            "set": lambda n, v: n.set("dev", v),
            "del": salt.utils.xmlutil.del_attribute("dev"),
        },
    ]

    data = {k: v for k, v in locals().items() if bool(v)}
    if boot_dev:
        data["boot_dev"] = {i + 1: dev for i, dev in enumerate(boot_dev.split())}
    need_update = (
        salt.utils.xmlutil.change_xml(desc, data, params_mapping) or need_update
    )

    # Update the XML definition with the new disks and diff changes
    devices_node = desc.find("devices")
    parameters = {
        "disk": ["disks", "disk_profile"],
        "interface": ["interfaces", "nic_profile"],
        "graphics": ["graphics"],
    }
    changes = {}
    for dev_type in parameters:
        changes[dev_type] = {}
        func_locals = locals()
        if [
            param
            for param in parameters[dev_type]
            if func_locals.get(param, None) is not None
        ]:
            old = devices_node.findall(dev_type)
            new = new_desc.findall("devices/{}".format(dev_type))
            changes[dev_type] = globals()["_diff_{}_lists".format(dev_type)](old, new)
            if changes[dev_type]["deleted"] or changes[dev_type]["new"]:
                for item in old:
                    devices_node.remove(item)
                devices_node.extend(changes[dev_type]["sorted"])
                need_update = True

    # Set the new definition
    if need_update:
        # Create missing disks if needed
        try:
            if changes["disk"]:
                for idx, item in enumerate(changes["disk"]["sorted"]):
                    source_file = all_disks[idx].get("source_file")
                    # We don't want to create image disks for cdrom devices
                    if all_disks[idx].get("device", "disk") == "cdrom":
                        continue
                    if (
                        item in changes["disk"]["new"]
                        and source_file
                        and not os.path.isfile(source_file)
                    ):
                        _qemu_image_create(all_disks[idx])
                    elif item in changes["disk"]["new"] and not source_file:
                        _disk_volume_create(conn, all_disks[idx])

            if not test:
                xml_desc = ElementTree.tostring(desc)
                log.debug("Update virtual machine definition: %s", xml_desc)
                conn.defineXML(salt.utils.stringutils.to_str(xml_desc))
            status["definition"] = True
        except libvirt.libvirtError as err:
            conn.close()
            raise err

        # Do the live changes now that we know the definition has been properly set
        # From that point on, failures are not blocking to try to live update as much
        # as possible.
        commands = []
        removable_changes = []
        if domain.isActive() and live:
            if cpu:
                commands.append(
                    {
                        "device": "cpu",
                        "cmd": "setVcpusFlags",
                        "args": [cpu, libvirt.VIR_DOMAIN_AFFECT_LIVE],
                    }
                )
            if mem:
                if isinstance(mem, dict):
                    # setMemoryFlags takes memory amount in KiB
                    new_mem = (
                        int(_handle_unit(mem.get("current")) / 1024)
                        if "current" in mem
                        else None
                    )
                elif isinstance(mem, int):
                    new_mem = int(mem * 1024)

                if old_mem != new_mem and new_mem is not None:
                    commands.append(
                        {
                            "device": "mem",
                            "cmd": "setMemoryFlags",
                            "args": [new_mem, libvirt.VIR_DOMAIN_AFFECT_LIVE],
                        }
                    )

            # Look for removable device source changes
            new_disks = []
            for new_disk in changes["disk"].get("new", []):
                device = new_disk.get("device", "disk")
                if device not in ["cdrom", "floppy"]:
                    new_disks.append(new_disk)
                    continue

                target_dev = new_disk.find("target").get("dev")
                matching = [
                    old_disk
                    for old_disk in changes["disk"].get("deleted", [])
                    if old_disk.get("device", "disk") == device
                    and old_disk.find("target").get("dev") == target_dev
                ]
                if not matching:
                    new_disks.append(new_disk)
                else:
                    # libvirt needs to keep the XML exactly as it was before
                    updated_disk = matching[0]
                    changes["disk"]["deleted"].remove(updated_disk)
                    removable_changes.append(updated_disk)
                    source_node = updated_disk.find("source")
                    new_source_node = new_disk.find("source")
                    source_file = (
                        new_source_node.get("file")
                        if new_source_node is not None
                        else None
                    )

                    updated_disk.set("type", "file")
                    # Detaching device
                    if source_node is not None:
                        updated_disk.remove(source_node)

                    # Attaching device
                    if source_file:
                        ElementTree.SubElement(
                            updated_disk, "source", attrib={"file": source_file}
                        )

            changes["disk"]["new"] = new_disks

            for dev_type in ["disk", "interface"]:
                for added in changes[dev_type].get("new", []):
                    commands.append(
                        {
                            "device": dev_type,
                            "cmd": "attachDevice",
                            "args": [
                                salt.utils.stringutils.to_str(
                                    ElementTree.tostring(added)
                                )
                            ],
                        }
                    )

                for removed in changes[dev_type].get("deleted", []):
                    commands.append(
                        {
                            "device": dev_type,
                            "cmd": "detachDevice",
                            "args": [
                                salt.utils.stringutils.to_str(
                                    ElementTree.tostring(removed)
                                )
                            ],
                        }
                    )

        for updated_disk in removable_changes:
            commands.append(
                {
                    "device": "disk",
                    "cmd": "updateDeviceFlags",
                    "args": [
                        salt.utils.stringutils.to_str(
                            ElementTree.tostring(updated_disk)
                        )
                    ],
                }
            )

        for cmd in commands:
            try:
                ret = getattr(domain, cmd["cmd"])(*cmd["args"]) if not test else 0
                device_type = cmd["device"]
                if device_type in ["cpu", "mem"]:
                    status[device_type] = not bool(ret)
                else:
                    actions = {
                        "attachDevice": "attached",
                        "detachDevice": "detached",
                        "updateDeviceFlags": "updated",
                    }
                    status[device_type][actions[cmd["cmd"]]].append(cmd["args"][0])

            except libvirt.libvirtError as err:
                if "errors" not in status:
                    status["errors"] = []
                status["errors"].append(str(err))

    conn.close()
    return status


def list_domains(**kwargs):
    """
    Return a list of available domains.

    :param connection: libvirt connection URI, overriding defaults

        .. versionadded:: 2019.2.0
    :param username: username to connect with, overriding defaults

        .. versionadded:: 2019.2.0
    :param password: password to connect with, overriding defaults

        .. versionadded:: 2019.2.0

    CLI Example:

    .. code-block:: bash

        salt '*' virt.list_domains
    """
    vms = []
    conn = __get_conn(**kwargs)
    for dom in _get_domain(conn, iterable=True):
        vms.append(dom.name())
    conn.close()
    return vms


def list_active_vms(**kwargs):
    """
    Return a list of names for active virtual machine on the minion

    :param connection: libvirt connection URI, overriding defaults

        .. versionadded:: 2019.2.0
    :param username: username to connect with, overriding defaults

        .. versionadded:: 2019.2.0
    :param password: password to connect with, overriding defaults

        .. versionadded:: 2019.2.0

    CLI Example:

    .. code-block:: bash

        salt '*' virt.list_active_vms
    """
    vms = []
    conn = __get_conn(**kwargs)
    for dom in _get_domain(conn, iterable=True, inactive=False):
        vms.append(dom.name())
    conn.close()
    return vms


def list_inactive_vms(**kwargs):
    """
    Return a list of names for inactive virtual machine on the minion

    :param connection: libvirt connection URI, overriding defaults

        .. versionadded:: 2019.2.0
    :param username: username to connect with, overriding defaults

        .. versionadded:: 2019.2.0
    :param password: password to connect with, overriding defaults

        .. versionadded:: 2019.2.0

    CLI Example:

    .. code-block:: bash

        salt '*' virt.list_inactive_vms
    """
    vms = []
    conn = __get_conn(**kwargs)
    for dom in _get_domain(conn, iterable=True, active=False):
        vms.append(dom.name())
    conn.close()
    return vms


def vm_info(vm_=None, **kwargs):
    """
    Return detailed information about the vms on this hyper in a
    list of dicts:

    :param vm_: name of the domain
    :param connection: libvirt connection URI, overriding defaults

        .. versionadded:: 2019.2.0
    :param username: username to connect with, overriding defaults

        .. versionadded:: 2019.2.0
    :param password: password to connect with, overriding defaults

        .. versionadded:: 2019.2.0

    .. code-block:: python

        [
            'your-vm': {
                'cpu': <int>,
                'maxMem': <int>,
                'mem': <int>,
                'state': '<state>',
                'cputime' <int>
                },
            ...
            ]

    If you pass a VM name in as an argument then it will return info
    for just the named VM, otherwise it will return all VMs.

    CLI Example:

    .. code-block:: bash

        salt '*' virt.vm_info
    """

    def _info(conn, dom):
        """
        Compute the infos of a domain
        """
        raw = dom.info()
        return {
            "cpu": raw[3],
            "cputime": int(raw[4]),
            "disks": _get_disks(conn, dom),
            "graphics": _get_graphics(dom),
            "nics": _get_nics(dom),
            "uuid": _get_uuid(dom),
            "loader": _get_loader(dom),
            "on_crash": _get_on_crash(dom),
            "on_reboot": _get_on_reboot(dom),
            "on_poweroff": _get_on_poweroff(dom),
            "maxMem": int(raw[1]),
            "mem": int(raw[2]),
            "state": VIRT_STATE_NAME_MAP.get(raw[0], "unknown"),
        }

    info = {}
    conn = __get_conn(**kwargs)
    if vm_:
        info[vm_] = _info(conn, _get_domain(conn, vm_))
    else:
        for domain in _get_domain(conn, iterable=True):
            info[domain.name()] = _info(conn, domain)
    conn.close()
    return info


def vm_state(vm_=None, **kwargs):
    """
    Return list of all the vms and their state.

    If you pass a VM name in as an argument then it will return info
    for just the named VM, otherwise it will return all VMs.

    :param vm_: name of the domain
    :param connection: libvirt connection URI, overriding defaults

        .. versionadded:: 2019.2.0
    :param username: username to connect with, overriding defaults

        .. versionadded:: 2019.2.0
    :param password: password to connect with, overriding defaults

        .. versionadded:: 2019.2.0

    CLI Example:

    .. code-block:: bash

        salt '*' virt.vm_state <domain>
    """

    def _info(dom):
        """
        Compute domain state
        """
        state = ""
        raw = dom.info()
        state = VIRT_STATE_NAME_MAP.get(raw[0], "unknown")
        return state

    info = {}
    conn = __get_conn(**kwargs)
    if vm_:
        info[vm_] = _info(_get_domain(conn, vm_))
    else:
        for domain in _get_domain(conn, iterable=True):
            info[domain.name()] = _info(domain)
    conn.close()
    return info


def _node_info(conn):
    """
    Internal variant of node_info taking a libvirt connection as parameter
    """
    raw = conn.getInfo()
    info = {
        "cpucores": raw[6],
        "cpumhz": raw[3],
        "cpumodel": str(raw[0]),
        "cpus": raw[2],
        "cputhreads": raw[7],
        "numanodes": raw[4],
        "phymemory": raw[1],
        "sockets": raw[5],
    }
    return info


def node_info(**kwargs):
    """
    Return a dict with information about this node

    :param connection: libvirt connection URI, overriding defaults

        .. versionadded:: 2019.2.0
    :param username: username to connect with, overriding defaults

        .. versionadded:: 2019.2.0
    :param password: password to connect with, overriding defaults

        .. versionadded:: 2019.2.0

    CLI Example:

    .. code-block:: bash

        salt '*' virt.node_info
    """
    conn = __get_conn(**kwargs)
    info = _node_info(conn)
    conn.close()
    return info


def get_nics(vm_, **kwargs):
    """
    Return info about the network interfaces of a named vm

    :param vm_: name of the domain
    :param connection: libvirt connection URI, overriding defaults

        .. versionadded:: 2019.2.0
    :param username: username to connect with, overriding defaults

        .. versionadded:: 2019.2.0
    :param password: password to connect with, overriding defaults

        .. versionadded:: 2019.2.0

    CLI Example:

    .. code-block:: bash

        salt '*' virt.get_nics <domain>
    """
    conn = __get_conn(**kwargs)
    nics = _get_nics(_get_domain(conn, vm_))
    conn.close()
    return nics


def get_macs(vm_, **kwargs):
    """
    Return a list off MAC addresses from the named vm

    :param vm_: name of the domain
    :param connection: libvirt connection URI, overriding defaults

        .. versionadded:: 2019.2.0
    :param username: username to connect with, overriding defaults

        .. versionadded:: 2019.2.0
    :param password: password to connect with, overriding defaults

        .. versionadded:: 2019.2.0

    CLI Example:

    .. code-block:: bash

        salt '*' virt.get_macs <domain>
    """
    doc = ElementTree.fromstring(get_xml(vm_, **kwargs))
    return [node.get("address") for node in doc.findall("devices/interface/mac")]


def get_graphics(vm_, **kwargs):
    """
    Returns the information on vnc for a given vm

    :param vm_: name of the domain
    :param connection: libvirt connection URI, overriding defaults

        .. versionadded:: 2019.2.0
    :param username: username to connect with, overriding defaults

        .. versionadded:: 2019.2.0
    :param password: password to connect with, overriding defaults

        .. versionadded:: 2019.2.0

    CLI Example:

    .. code-block:: bash

        salt '*' virt.get_graphics <domain>
    """
    conn = __get_conn(**kwargs)
    graphics = _get_graphics(_get_domain(conn, vm_))
    conn.close()
    return graphics


def get_loader(vm_, **kwargs):
    """
    Returns the information on the loader for a given vm

    :param vm_: name of the domain
    :param connection: libvirt connection URI, overriding defaults
    :param username: username to connect with, overriding defaults
    :param password: password to connect with, overriding defaults

    CLI Example:

    .. code-block:: bash

        salt '*' virt.get_loader <domain>

    .. versionadded:: Fluorine
    """
    conn = __get_conn(**kwargs)
    try:
        loader = _get_loader(_get_domain(conn, vm_))
        return loader
    finally:
        conn.close()


def get_disks(vm_, **kwargs):
    """
    Return the disks of a named vm

    :param vm_: name of the domain
    :param connection: libvirt connection URI, overriding defaults

        .. versionadded:: 2019.2.0
    :param username: username to connect with, overriding defaults

        .. versionadded:: 2019.2.0
    :param password: password to connect with, overriding defaults

        .. versionadded:: 2019.2.0

    CLI Example:

    .. code-block:: bash

        salt '*' virt.get_disks <domain>
    """
    conn = __get_conn(**kwargs)
    disks = _get_disks(conn, _get_domain(conn, vm_))
    conn.close()
    return disks


def setmem(vm_, memory, config=False, **kwargs):
    """
    Changes the amount of memory allocated to VM. The VM must be shutdown
    for this to work.

    :param vm_: name of the domain
    :param memory: memory amount to set in MB
    :param config: if True then libvirt will be asked to modify the config as well
    :param connection: libvirt connection URI, overriding defaults

        .. versionadded:: 2019.2.0
    :param username: username to connect with, overriding defaults

        .. versionadded:: 2019.2.0
    :param password: password to connect with, overriding defaults

        .. versionadded:: 2019.2.0

    CLI Example:

    .. code-block:: bash

        salt '*' virt.setmem <domain> <size>
        salt '*' virt.setmem my_domain 768
    """
    conn = __get_conn(**kwargs)
    dom = _get_domain(conn, vm_)

    if VIRT_STATE_NAME_MAP.get(dom.info()[0], "unknown") != "shutdown":
        return False

    # libvirt has a funny bitwise system for the flags in that the flag
    # to affect the "current" setting is 0, which means that to set the
    # current setting we have to call it a second time with just 0 set
    flags = libvirt.VIR_DOMAIN_MEM_MAXIMUM
    if config:
        flags = flags | libvirt.VIR_DOMAIN_AFFECT_CONFIG

    ret1 = dom.setMemoryFlags(memory * 1024, flags)
    ret2 = dom.setMemoryFlags(memory * 1024, libvirt.VIR_DOMAIN_AFFECT_CURRENT)

    conn.close()

    # return True if both calls succeeded
    return ret1 == ret2 == 0


def setvcpus(vm_, vcpus, config=False, **kwargs):
    """
    Changes the amount of vcpus allocated to VM. The VM must be shutdown
    for this to work.

    If config is True then we ask libvirt to modify the config as well

    :param vm_: name of the domain
    :param vcpus: integer representing the number of CPUs to be assigned
    :param config: if True then libvirt will be asked to modify the config as well
    :param connection: libvirt connection URI, overriding defaults

        .. versionadded:: 2019.2.0
    :param username: username to connect with, overriding defaults

        .. versionadded:: 2019.2.0
    :param password: password to connect with, overriding defaults

        .. versionadded:: 2019.2.0

    CLI Example:

    .. code-block:: bash

        salt '*' virt.setvcpus <domain> <amount>
        salt '*' virt.setvcpus my_domain 4
    """
    conn = __get_conn(**kwargs)
    dom = _get_domain(conn, vm_)

    if VIRT_STATE_NAME_MAP.get(dom.info()[0], "unknown") != "shutdown":
        return False

    # see notes in setmem
    flags = libvirt.VIR_DOMAIN_VCPU_MAXIMUM
    if config:
        flags = flags | libvirt.VIR_DOMAIN_AFFECT_CONFIG

    ret1 = dom.setVcpusFlags(vcpus, flags)
    ret2 = dom.setVcpusFlags(vcpus, libvirt.VIR_DOMAIN_AFFECT_CURRENT)

    conn.close()

    return ret1 == ret2 == 0


def _freemem(conn):
    """
    Internal variant of freemem taking a libvirt connection as parameter
    """
    mem = conn.getInfo()[1]
    # Take off just enough to sustain the hypervisor
    mem -= 256
    for dom in _get_domain(conn, iterable=True):
        if dom.ID() > 0:
            mem -= dom.info()[2] / 1024
    return mem


def freemem(**kwargs):
    """
    Return an int representing the amount of memory (in MB) that has not
    been given to virtual machines on this node

    :param connection: libvirt connection URI, overriding defaults

        .. versionadded:: 2019.2.0
    :param username: username to connect with, overriding defaults

        .. versionadded:: 2019.2.0
    :param password: password to connect with, overriding defaults

        .. versionadded:: 2019.2.0

    CLI Example:

    .. code-block:: bash

        salt '*' virt.freemem
    """
    conn = __get_conn(**kwargs)
    mem = _freemem(conn)
    conn.close()
    return mem


def _freecpu(conn):
    """
    Internal variant of freecpu taking a libvirt connection as parameter
    """
    cpus = conn.getInfo()[2]
    for dom in _get_domain(conn, iterable=True):
        if dom.ID() > 0:
            cpus -= dom.info()[3]
    return cpus


def freecpu(**kwargs):
    """
    Return an int representing the number of unallocated cpus on this
    hypervisor

    :param connection: libvirt connection URI, overriding defaults

        .. versionadded:: 2019.2.0
    :param username: username to connect with, overriding defaults

        .. versionadded:: 2019.2.0
    :param password: password to connect with, overriding defaults

        .. versionadded:: 2019.2.0

    CLI Example:

    .. code-block:: bash

        salt '*' virt.freecpu
    """
    conn = __get_conn(**kwargs)
    cpus = _freecpu(conn)
    conn.close()
    return cpus


def full_info(**kwargs):
    """
    Return the node_info, vm_info and freemem

    :param connection: libvirt connection URI, overriding defaults

        .. versionadded:: 2019.2.0
    :param username: username to connect with, overriding defaults

        .. versionadded:: 2019.2.0
    :param password: password to connect with, overriding defaults

        .. versionadded:: 2019.2.0

    CLI Example:

    .. code-block:: bash

        salt '*' virt.full_info
    """
    conn = __get_conn(**kwargs)
    info = {
        "freecpu": _freecpu(conn),
        "freemem": _freemem(conn),
        "node_info": _node_info(conn),
        "vm_info": vm_info(),
    }
    conn.close()
    return info


def get_xml(vm_, **kwargs):
    """
    Returns the XML for a given vm

    :param vm_: domain name
    :param connection: libvirt connection URI, overriding defaults

        .. versionadded:: 2019.2.0
    :param username: username to connect with, overriding defaults

        .. versionadded:: 2019.2.0
    :param password: password to connect with, overriding defaults

        .. versionadded:: 2019.2.0

    CLI Example:

    .. code-block:: bash

        salt '*' virt.get_xml <domain>
    """
    conn = __get_conn(**kwargs)
    xml_desc = (
        vm_.XMLDesc(0)
        if isinstance(vm_, libvirt.virDomain)
        else _get_domain(conn, vm_).XMLDesc(0)
    )
    conn.close()
    return xml_desc


def get_profiles(hypervisor=None, **kwargs):
    """
    Return the virt profiles for hypervisor.

    Currently there are profiles for:

    - nic
    - disk

    :param hypervisor: override the default machine type.
    :param connection: libvirt connection URI, overriding defaults

        .. versionadded:: 2019.2.0
    :param username: username to connect with, overriding defaults

        .. versionadded:: 2019.2.0
    :param password: password to connect with, overriding defaults

        .. versionadded:: 2019.2.0

    CLI Example:

    .. code-block:: bash

        salt '*' virt.get_profiles
        salt '*' virt.get_profiles hypervisor=vmware
    """
    # Use the machine types as possible values
    # Prefer 'kvm' over the others if available
    conn = __get_conn(**kwargs)
    caps = _capabilities(conn)
    hypervisors = sorted(
        {
            x
            for y in [guest["arch"]["domains"].keys() for guest in caps["guests"]]
            for x in y
        }
    )
    if len(hypervisors) == 0:
        raise SaltInvocationError("No supported hypervisors were found")

    if not hypervisor:
        hypervisor = "kvm" if "kvm" in hypervisors else hypervisors[0]

    ret = {
        "disk": {"default": _disk_profile(conn, "default", hypervisor, [], None)},
        "nic": {"default": _nic_profile("default", hypervisor)},
    }
    virtconf = __salt__["config.get"]("virt", {})

    for profile in virtconf.get("disk", []):
        ret["disk"][profile] = _disk_profile(conn, profile, hypervisor, [], None)

    for profile in virtconf.get("nic", []):
        ret["nic"][profile] = _nic_profile(profile, hypervisor)

    return ret


def shutdown(vm_, **kwargs):
    """
    Send a soft shutdown signal to the named vm

    :param vm_: domain name
    :param connection: libvirt connection URI, overriding defaults

        .. versionadded:: 2019.2.0
    :param username: username to connect with, overriding defaults

        .. versionadded:: 2019.2.0
    :param password: password to connect with, overriding defaults

        .. versionadded:: 2019.2.0

    CLI Example:

    .. code-block:: bash

        salt '*' virt.shutdown <domain>
    """
    conn = __get_conn(**kwargs)
    dom = _get_domain(conn, vm_)
    ret = dom.shutdown() == 0
    conn.close()
    return ret


def pause(vm_, **kwargs):
    """
    Pause the named vm

    :param vm_: domain name
    :param connection: libvirt connection URI, overriding defaults

        .. versionadded:: 2019.2.0
    :param username: username to connect with, overriding defaults

        .. versionadded:: 2019.2.0
    :param password: password to connect with, overriding defaults

        .. versionadded:: 2019.2.0

    CLI Example:

    .. code-block:: bash

        salt '*' virt.pause <domain>
    """
    conn = __get_conn(**kwargs)
    dom = _get_domain(conn, vm_)
    ret = dom.suspend() == 0
    conn.close()
    return ret


def resume(vm_, **kwargs):
    """
    Resume the named vm

    :param vm_: domain name
    :param connection: libvirt connection URI, overriding defaults

        .. versionadded:: 2019.2.0
    :param username: username to connect with, overriding defaults

        .. versionadded:: 2019.2.0
    :param password: password to connect with, overriding defaults

        .. versionadded:: 2019.2.0

    CLI Example:

    .. code-block:: bash

        salt '*' virt.resume <domain>
    """
    conn = __get_conn(**kwargs)
    dom = _get_domain(conn, vm_)
    ret = dom.resume() == 0
    conn.close()
    return ret


def start(name, **kwargs):
    """
    Start a defined domain

    :param vm_: domain name
    :param connection: libvirt connection URI, overriding defaults

        .. versionadded:: 2019.2.0
    :param username: username to connect with, overriding defaults

        .. versionadded:: 2019.2.0
    :param password: password to connect with, overriding defaults

        .. versionadded:: 2019.2.0

    CLI Example:

    .. code-block:: bash

        salt '*' virt.start <domain>
    """
    conn = __get_conn(**kwargs)
    ret = _get_domain(conn, name).create() == 0
    conn.close()
    return ret


def stop(name, **kwargs):
    """
    Hard power down the virtual machine, this is equivalent to pulling the power.

    :param vm_: domain name
    :param connection: libvirt connection URI, overriding defaults

        .. versionadded:: 2019.2.0
    :param username: username to connect with, overriding defaults

        .. versionadded:: 2019.2.0
    :param password: password to connect with, overriding defaults

        .. versionadded:: 2019.2.0

    CLI Example:

    .. code-block:: bash

        salt '*' virt.stop <domain>
    """
    conn = __get_conn(**kwargs)
    ret = _get_domain(conn, name).destroy() == 0
    conn.close()
    return ret


def reboot(name, **kwargs):
    """
    Reboot a domain via ACPI request

    :param vm_: domain name
    :param connection: libvirt connection URI, overriding defaults

        .. versionadded:: 2019.2.0
    :param username: username to connect with, overriding defaults

        .. versionadded:: 2019.2.0
    :param password: password to connect with, overriding defaults

        .. versionadded:: 2019.2.0

    CLI Example:

    .. code-block:: bash

        salt '*' virt.reboot <domain>
    """
    conn = __get_conn(**kwargs)
    ret = _get_domain(conn, name).reboot(libvirt.VIR_DOMAIN_REBOOT_DEFAULT) == 0
    conn.close()
    return ret


def reset(vm_, **kwargs):
    """
    Reset a VM by emulating the reset button on a physical machine

    :param vm_: domain name
    :param connection: libvirt connection URI, overriding defaults

        .. versionadded:: 2019.2.0
    :param username: username to connect with, overriding defaults

        .. versionadded:: 2019.2.0
    :param password: password to connect with, overriding defaults

        .. versionadded:: 2019.2.0

    CLI Example:

    .. code-block:: bash

        salt '*' virt.reset <domain>
    """
    conn = __get_conn(**kwargs)
    dom = _get_domain(conn, vm_)

    # reset takes a flag, like reboot, but it is not yet used
    # so we just pass in 0
    # see: http://libvirt.org/html/libvirt-libvirt.html#virDomainReset
    ret = dom.reset(0) == 0
    conn.close()
    return ret


def ctrl_alt_del(vm_, **kwargs):
    """
    Sends CTRL+ALT+DEL to a VM

    :param vm_: domain name
    :param connection: libvirt connection URI, overriding defaults

        .. versionadded:: 2019.2.0
    :param username: username to connect with, overriding defaults

        .. versionadded:: 2019.2.0
    :param password: password to connect with, overriding defaults

        .. versionadded:: 2019.2.0

    CLI Example:

    .. code-block:: bash

        salt '*' virt.ctrl_alt_del <domain>
    """
    conn = __get_conn(**kwargs)
    dom = _get_domain(conn, vm_)
    ret = dom.sendKey(0, 0, [29, 56, 111], 3, 0) == 0
    conn.close()
    return ret


def create_xml_str(xml, **kwargs):  # pylint: disable=redefined-outer-name
    """
    Start a transient domain based on the XML passed to the function

    :param xml: libvirt XML definition of the domain
    :param connection: libvirt connection URI, overriding defaults

        .. versionadded:: 2019.2.0
    :param username: username to connect with, overriding defaults

        .. versionadded:: 2019.2.0
    :param password: password to connect with, overriding defaults

        .. versionadded:: 2019.2.0

    CLI Example:

    .. code-block:: bash

        salt '*' virt.create_xml_str <XML in string format>
    """
    conn = __get_conn(**kwargs)
    ret = conn.createXML(xml, 0) is not None
    conn.close()
    return ret


def create_xml_path(path, **kwargs):
    """
    Start a transient domain based on the XML-file path passed to the function

    :param path: path to a file containing the libvirt XML definition of the domain
    :param connection: libvirt connection URI, overriding defaults

        .. versionadded:: 2019.2.0
    :param username: username to connect with, overriding defaults

        .. versionadded:: 2019.2.0
    :param password: password to connect with, overriding defaults

        .. versionadded:: 2019.2.0

    CLI Example:

    .. code-block:: bash

        salt '*' virt.create_xml_path <path to XML file on the node>
    """
    try:
        with salt.utils.files.fopen(path, "r") as fp_:
            return create_xml_str(
                salt.utils.stringutils.to_unicode(fp_.read()), **kwargs
            )
    except OSError:
        return False


def define_xml_str(xml, **kwargs):  # pylint: disable=redefined-outer-name
    """
    Define a persistent domain based on the XML passed to the function

    :param xml: libvirt XML definition of the domain
    :param connection: libvirt connection URI, overriding defaults

        .. versionadded:: 2019.2.0
    :param username: username to connect with, overriding defaults

        .. versionadded:: 2019.2.0
    :param password: password to connect with, overriding defaults

        .. versionadded:: 2019.2.0

    CLI Example:

    .. code-block:: bash

        salt '*' virt.define_xml_str <XML in string format>
    """
    conn = __get_conn(**kwargs)
    ret = conn.defineXML(xml) is not None
    conn.close()
    return ret


def define_xml_path(path, **kwargs):
    """
    Define a persistent domain based on the XML-file path passed to the function

    :param path: path to a file containing the libvirt XML definition of the domain
    :param connection: libvirt connection URI, overriding defaults

        .. versionadded:: 2019.2.0
    :param username: username to connect with, overriding defaults

        .. versionadded:: 2019.2.0
    :param password: password to connect with, overriding defaults

        .. versionadded:: 2019.2.0

    CLI Example:

    .. code-block:: bash

        salt '*' virt.define_xml_path <path to XML file on the node>

    """
    try:
        with salt.utils.files.fopen(path, "r") as fp_:
            return define_xml_str(
                salt.utils.stringutils.to_unicode(fp_.read()), **kwargs
            )
    except OSError:
        return False


def _define_vol_xml_str(conn, xml, pool=None):  # pylint: disable=redefined-outer-name
    """
    Same function than define_vml_xml_str but using an already opened libvirt connection
    """
    default_pool = "default" if conn.getType() != "ESX" else "0"
    poolname = (
        pool if pool else __salt__["config.get"]("virt:storagepool", default_pool)
    )
    pool = conn.storagePoolLookupByName(str(poolname))
    ret = pool.createXML(xml, 0) is not None
    return ret


def define_vol_xml_str(
    xml, pool=None, **kwargs
):  # pylint: disable=redefined-outer-name
    """
    Define a volume based on the XML passed to the function

    :param xml: libvirt XML definition of the storage volume
    :param pool:
        storage pool name to define the volume in.
        If defined, this parameter will override the configuration setting.

        .. versionadded:: 3001
    :param connection: libvirt connection URI, overriding defaults

        .. versionadded:: 2019.2.0
    :param username: username to connect with, overriding defaults

        .. versionadded:: 2019.2.0
    :param password: password to connect with, overriding defaults

        .. versionadded:: 2019.2.0

    CLI Example:

    .. code-block:: bash

        salt '*' virt.define_vol_xml_str <XML in string format>

    The storage pool where the disk image will be defined is ``default``
    unless changed with the pool parameter or a configuration like this:

    .. code-block:: yaml

        virt:
            storagepool: mine
    """
    conn = __get_conn(**kwargs)
    ret = False
    try:
        ret = _define_vol_xml_str(conn, xml, pool=pool)
    except libvirtError as err:
        raise CommandExecutionError(err.get_error_message())
    finally:
        conn.close()
    return ret


def define_vol_xml_path(path, pool=None, **kwargs):
    """
    Define a volume based on the XML-file path passed to the function

    :param path: path to a file containing the libvirt XML definition of the volume
    :param pool:
        storage pool name to define the volume in.
        If defined, this parameter will override the configuration setting.

        .. versionadded:: 3001
    :param connection: libvirt connection URI, overriding defaults

        .. versionadded:: 2019.2.0
    :param username: username to connect with, overriding defaults

        .. versionadded:: 2019.2.0
    :param password: password to connect with, overriding defaults

        .. versionadded:: 2019.2.0

    CLI Example:

    .. code-block:: bash

        salt '*' virt.define_vol_xml_path <path to XML file on the node>

    """
    try:
        with salt.utils.files.fopen(path, "r") as fp_:
            return define_vol_xml_str(
                salt.utils.stringutils.to_unicode(fp_.read()), pool=pool, **kwargs
            )
    except OSError:
        return False


def migrate_non_shared(vm_, target, ssh=False, **kwargs):
    """
    Attempt to execute non-shared storage "all" migration

    :param vm_: domain name
    :param target: target libvirt host name
    :param ssh: True to connect over ssh

        .. deprecated:: 3002

    :param kwargs:
        - live:           Use live migration. Default value is True.
        - persistent:     Leave the domain persistent on destination host.
                          Default value is True.
        - undefinesource: Undefine the domain on the source host.
                          Default value is True.
        - offline:        If set to True it will migrate the domain definition
                          without starting the domain on destination and without
                          stopping it on source host. Default value is False.
        - max_bandwidth:  The maximum bandwidth (in MiB/s) that will be used.
        - max_downtime:   Set maximum tolerable downtime for live-migration.
                          The value represents a number of milliseconds the guest
                          is allowed to be down at the end of live migration.
        - parallel_connections: Specify a number of parallel network connections
                          to be used to send memory pages to the destination host.
        - compressed:      Activate compression.
        - comp_methods:    A comma-separated list of compression methods. Supported
                           methods are "mt" and "xbzrle" and can be  used in any
                           combination. QEMU defaults to "xbzrle".
        - comp_mt_level:   Set compression level. Values are in range from 0 to 9,
                           where 1 is maximum speed and 9 is  maximum compression.
        - comp_mt_threads: Set number of compress threads on source host.
        - comp_mt_dthreads: Set number of decompress threads on target host.
        - comp_xbzrle_cache: Set the size of page cache for xbzrle compression in bytes.
        - postcopy:        Enable the use of post-copy migration.
        - postcopy_bandwidth: The maximum bandwidth allowed in post-copy phase. (MiB/s)
        - username:       Username to connect with target host
        - password:       Password to connect with target host

        .. versionadded:: 3002

    CLI Example:

    .. code-block:: bash

        salt '*' virt.migrate_non_shared <vm name> <target hypervisor>

    A tunnel data migration can be performed by setting this in the
    configuration:

    .. code-block:: yaml

        virt:
            tunnel: True

    For more details on tunnelled data migrations, report to
    https://libvirt.org/migration.html#transporttunnel
    """
    salt.utils.versions.warn_until(
        "Silicon",
        "The 'migrate_non_shared' feature has been deprecated. "
        "Use 'migrate' with copy_storage='all' instead.",
    )
    return migrate(vm_, target, ssh, copy_storage="all", **kwargs)


def migrate_non_shared_inc(vm_, target, ssh=False, **kwargs):
    """
    Attempt to execute non-shared storage "inc" migration

    :param vm_: domain name
    :param target: target libvirt host name
    :param ssh: True to connect over ssh

        .. deprecated:: 3002

    :param kwargs:
        - live:           Use live migration. Default value is True.
        - persistent:     Leave the domain persistent on destination host.
                          Default value is True.
        - undefinesource: Undefine the domain on the source host.
                          Default value is True.
        - offline:        If set to True it will migrate the domain definition
                          without starting the domain on destination and without
                          stopping it on source host. Default value is False.
        - max_bandwidth:  The maximum bandwidth (in MiB/s) that will be used.
        - max_downtime:   Set maximum tolerable downtime for live-migration.
                          The value represents a number of milliseconds the guest
                          is allowed to be down at the end of live migration.
        - parallel_connections: Specify a number of parallel network connections
                          to be used to send memory pages to the destination host.
        - compressed:      Activate compression.
        - comp_methods:    A comma-separated list of compression methods. Supported
                           methods are "mt" and "xbzrle" and can be  used in any
                           combination. QEMU defaults to "xbzrle".
        - comp_mt_level:   Set compression level. Values are in range from 0 to 9,
                           where 1 is maximum speed and 9 is  maximum compression.
        - comp_mt_threads: Set number of compress threads on source host.
        - comp_mt_dthreads: Set number of decompress threads on target host.
        - comp_xbzrle_cache: Set the size of page cache for xbzrle compression in bytes.
        - postcopy:        Enable the use of post-copy migration.
        - postcopy_bandwidth: The maximum bandwidth allowed in post-copy phase. (MiB/s)
        - username:       Username to connect with target host
        - password:       Password to connect with target host

        .. versionadded:: 3002

    CLI Example:

    .. code-block:: bash

        salt '*' virt.migrate_non_shared_inc <vm name> <target hypervisor>

    A tunnel data migration can be performed by setting this in the
    configuration:

    .. code-block:: yaml

        virt:
            tunnel: True

    For more details on tunnelled data migrations, report to
    https://libvirt.org/migration.html#transporttunnel
    """
    salt.utils.versions.warn_until(
        "Silicon",
        "The 'migrate_non_shared_inc' feature has been deprecated. "
        "Use 'migrate' with copy_storage='inc' instead.",
    )
    return migrate(vm_, target, ssh, copy_storage="inc", **kwargs)


def migrate(vm_, target, ssh=False, **kwargs):
    """
    Shared storage migration

    :param vm_: domain name
    :param target: target libvirt URI or host name
    :param ssh: True to connect over ssh

       .. deprecated:: 3002

    :param kwargs:
        - live:            Use live migration. Default value is True.
        - persistent:      Leave the domain persistent on destination host.
                           Default value is True.
        - undefinesource:  Undefine the domain on the source host.
                           Default value is True.
        - offline:         If set to True it will migrate the domain definition
                           without starting the domain on destination and without
                           stopping it on source host. Default value is False.
        - max_bandwidth:   The maximum bandwidth (in MiB/s) that will be used.
        - max_downtime:    Set maximum tolerable downtime for live-migration.
                           The value represents a number of milliseconds the guest
                           is allowed to be down at the end of live migration.
        - parallel_connections: Specify a number of parallel network connections
                           to be used to send memory pages to the destination host.
        - compressed:      Activate compression.
        - comp_methods:    A comma-separated list of compression methods. Supported
                           methods are "mt" and "xbzrle" and can be  used in any
                           combination. QEMU defaults to "xbzrle".
        - comp_mt_level:   Set compression level. Values are in range from 0 to 9,
                           where 1 is maximum speed and 9 is  maximum compression.
        - comp_mt_threads: Set number of compress threads on source host.
        - comp_mt_dthreads: Set number of decompress threads on target host.
        - comp_xbzrle_cache: Set the size of page cache for xbzrle compression in bytes.
        - copy_storage:    Migrate non-shared storage. It must be one of the following
                           values: all (full disk copy) or incremental (Incremental copy)
        - postcopy:        Enable the use of post-copy migration.
        - postcopy_bandwidth: The maximum bandwidth allowed in post-copy phase. (MiB/s)
        - username:        Username to connect with target host
        - password:        Password to connect with target host

        .. versionadded:: 3002

    CLI Example:

    .. code-block:: bash

        salt '*' virt.migrate <domain> <target hypervisor URI>
        salt src virt.migrate guest qemu+ssh://dst/system
        salt src virt.migrate guest qemu+tls://dst/system
        salt src virt.migrate guest qemu+tcp://dst/system

    A tunnel data migration can be performed by setting this in the
    configuration:

    .. code-block:: yaml

        virt:
            tunnel: True

    For more details on tunnelled data migrations, report to
    https://libvirt.org/migration.html#transporttunnel
    """

    if ssh:
        salt.utils.versions.warn_until(
            "Silicon",
            "The 'ssh' argument has been deprecated and "
            "will be removed in a future release. "
            "Use libvirt URI string 'target' instead.",
        )

    conn = __get_conn()
    dom = _get_domain(conn, vm_)

    if not urlparse(target).scheme:
        proto = "qemu"
        if ssh:
            proto += "+ssh"
        dst_uri = "{}://{}/system".format(proto, target)
    else:
        dst_uri = target

    ret = _migrate(dom, dst_uri, **kwargs)
    conn.close()
    return ret


def migrate_start_postcopy(vm_):
    """
    Starts post-copy migration. This function has to be called
    while live migration is in progress and it has been initiated
    with the `postcopy=True` option.

    CLI Example:

    .. code-block:: bash

        salt '*' virt.migrate_start_postcopy <domain>
    """
    conn = __get_conn()
    dom = _get_domain(conn, vm_)
    try:
        dom.migrateStartPostCopy()
    except libvirt.libvirtError as err:
        conn.close()
        raise CommandExecutionError(err.get_error_message())
    conn.close()


def seed_non_shared_migrate(disks, force=False):
    """
    Non shared migration requires that the disks be present on the migration
    destination, pass the disks information via this function, to the
    migration destination before executing the migration.

    :param disks: the list of disk data as provided by virt.get_disks
    :param force: skip checking the compatibility of source and target disk
                  images if True. (default: False)

    CLI Example:

    .. code-block:: bash

        salt '*' virt.seed_non_shared_migrate <disks>
    """
    for _, data in disks.items():
        fn_ = data["file"]
        form = data["file format"]
        size = data["virtual size"].split()[1][1:]
        if os.path.isfile(fn_) and not force:
            # the target exists, check to see if it is compatible
            pre = salt.utils.yaml.safe_load(
                subprocess.Popen(
                    "qemu-img info arch", shell=True, stdout=subprocess.PIPE
                ).communicate()[0]
            )
            if (
                pre["file format"] != data["file format"]
                and pre["virtual size"] != data["virtual size"]
            ):
                return False
        if not os.path.isdir(os.path.dirname(fn_)):
            os.makedirs(os.path.dirname(fn_))
        if os.path.isfile(fn_):
            os.remove(fn_)
        cmd = "qemu-img create -f " + form + " " + fn_ + " " + size
        subprocess.call(cmd, shell=True)
        creds = _libvirt_creds()
        cmd = "chown " + creds["user"] + ":" + creds["group"] + " " + fn_
        subprocess.call(cmd, shell=True)
    return True


def set_autostart(vm_, state="on", **kwargs):
    """
    Set the autostart flag on a VM so that the VM will start with the host
    system on reboot.

    :param vm_: domain name
    :param state: 'on' to auto start the pool, anything else to mark the
                  pool not to be started when the host boots
    :param connection: libvirt connection URI, overriding defaults

        .. versionadded:: 2019.2.0
    :param username: username to connect with, overriding defaults

        .. versionadded:: 2019.2.0
    :param password: password to connect with, overriding defaults

        .. versionadded:: 2019.2.0

    CLI Example:

    .. code-block:: bash

        salt "*" virt.set_autostart <domain> <on | off>
    """
    conn = __get_conn(**kwargs)
    dom = _get_domain(conn, vm_)

    # return False if state is set to something other then on or off
    ret = False

    if state == "on":
        ret = dom.setAutostart(1) == 0

    elif state == "off":
        ret = dom.setAutostart(0) == 0

    conn.close()
    return ret


def undefine(vm_, **kwargs):
    """
    Remove a defined vm, this does not purge the virtual machine image, and
    this only works if the vm is powered down

    :param vm_: domain name
    :param connection: libvirt connection URI, overriding defaults

        .. versionadded:: 2019.2.0
    :param username: username to connect with, overriding defaults

        .. versionadded:: 2019.2.0
    :param password: password to connect with, overriding defaults

        .. versionadded:: 2019.2.0

    CLI Example:

    .. code-block:: bash

        salt '*' virt.undefine <domain>
    """
    conn = __get_conn(**kwargs)
    dom = _get_domain(conn, vm_)
    if getattr(libvirt, "VIR_DOMAIN_UNDEFINE_NVRAM", False):
        # This one is only in 1.2.8+
        ret = dom.undefineFlags(libvirt.VIR_DOMAIN_UNDEFINE_NVRAM) == 0
    else:
        ret = dom.undefine() == 0
    conn.close()
    return ret


def purge(vm_, dirs=False, removables=False, **kwargs):
    """
    Recursively destroy and delete a persistent virtual machine, pass True for
    dir's to also delete the directories containing the virtual machine disk
    images - USE WITH EXTREME CAUTION!

    :param vm_: domain name
    :param dirs: pass True to remove containing directories
    :param removables: pass True to remove removable devices

        .. versionadded:: 2019.2.0
    :param connection: libvirt connection URI, overriding defaults

        .. versionadded:: 2019.2.0
    :param username: username to connect with, overriding defaults

        .. versionadded:: 2019.2.0
    :param password: password to connect with, overriding defaults

        .. versionadded:: 2019.2.0

    CLI Example:

    .. code-block:: bash

        salt '*' virt.purge <domain>
    """
    conn = __get_conn(**kwargs)
    dom = _get_domain(conn, vm_)
    disks = _get_disks(conn, dom)
    if (
        VIRT_STATE_NAME_MAP.get(dom.info()[0], "unknown") != "shutdown"
        and dom.destroy() != 0
    ):
        return False
    directories = set()
    for disk in disks:
        if not removables and disks[disk]["type"] in ["cdrom", "floppy"]:
            continue
        if disks[disk].get("zfs", False):
            # TODO create solution for 'dataset is busy'
            time.sleep(3)
            fs_name = disks[disk]["file"][len("/dev/zvol/") :]
            log.info("Destroying VM ZFS volume {}".format(fs_name))
            __salt__["zfs.destroy"](name=fs_name, force=True)
        elif os.path.exists(disks[disk]["file"]):
            os.remove(disks[disk]["file"])
            directories.add(os.path.dirname(disks[disk]["file"]))
        else:
            # We may have a volume to delete here
            matcher = re.match("^(?P<pool>[^/]+)/(?P<volume>.*)$", disks[disk]["file"],)
            if matcher:
                pool_name = matcher.group("pool")
                pool = None
                if pool_name in conn.listStoragePools():
                    pool = conn.storagePoolLookupByName(pool_name)

                if pool and matcher.group("volume") in pool.listVolumes():
                    volume = pool.storageVolLookupByName(matcher.group("volume"))
                    volume.delete()

    if dirs:
        for dir_ in directories:
            shutil.rmtree(dir_)
    if getattr(libvirt, "VIR_DOMAIN_UNDEFINE_NVRAM", False):
        # This one is only in 1.2.8+
        try:
            dom.undefineFlags(libvirt.VIR_DOMAIN_UNDEFINE_NVRAM)
        except Exception:  # pylint: disable=broad-except
            dom.undefine()
    else:
        dom.undefine()
    conn.close()
    return True


def virt_type():
    """
    Returns the virtual machine type as a string

    CLI Example:

    .. code-block:: bash

        salt '*' virt.virt_type
    """
    return __grains__["virtual"]


def _is_kvm_hyper():
    """
    Returns a bool whether or not this node is a KVM hypervisor
    """
    try:
        with salt.utils.files.fopen("/proc/modules") as fp_:
            if "kvm_" not in salt.utils.stringutils.to_unicode(fp_.read()):
                return False
    except OSError:
        # No /proc/modules? Are we on Windows? Or Solaris?
        return False
    return "libvirtd" in __salt__["cmd.run"](__grains__["ps"])


def _is_xen_hyper():
    """
    Returns a bool whether or not this node is a XEN hypervisor
    """
    try:
        if __grains__["virtual_subtype"] != "Xen Dom0":
            return False
    except KeyError:
        # virtual_subtype isn't set everywhere.
        return False
    try:
        with salt.utils.files.fopen("/proc/modules") as fp_:
            if "xen_" not in salt.utils.stringutils.to_unicode(fp_.read()):
                return False
    except OSError:
        # No /proc/modules? Are we on Windows? Or Solaris?
        return False
    return "libvirtd" in __salt__["cmd.run"](__grains__["ps"])


def get_hypervisor():
    """
    Returns the name of the hypervisor running on this node or ``None``.

    Detected hypervisors:

    - kvm
    - xen
    - bhyve

    CLI Example:

    .. code-block:: bash

        salt '*' virt.get_hypervisor

    .. versionadded:: 2019.2.0
        the function and the ``kvm``, ``xen`` and ``bhyve`` hypervisors support
    """
    # To add a new 'foo' hypervisor, add the _is_foo_hyper function,
    # add 'foo' to the list below and add it to the docstring with a .. versionadded::
    hypervisors = ["kvm", "xen", "bhyve"]
    result = [
        hyper
        for hyper in hypervisors
        if getattr(sys.modules[__name__], "_is_{}_hyper".format(hyper))()
    ]
    return result[0] if result else None


def _is_bhyve_hyper():
    sysctl_cmd = "sysctl hw.vmm.create"
    vmm_enabled = False
    try:
        stdout = subprocess.Popen(
            sysctl_cmd, shell=True, stdout=subprocess.PIPE
        ).communicate()[0]
        vmm_enabled = len(salt.utils.stringutils.to_str(stdout).split('"')[1]) != 0
    except IndexError:
        pass
    return vmm_enabled


def is_hyper():
    """
    Returns a bool whether or not this node is a hypervisor of any kind

    CLI Example:

    .. code-block:: bash

        salt '*' virt.is_hyper
    """
    if HAS_LIBVIRT:
        return _is_xen_hyper() or _is_kvm_hyper() or _is_bhyve_hyper()
    return False


def vm_cputime(vm_=None, **kwargs):
    """
    Return cputime used by the vms on this hyper in a
    list of dicts:

    :param vm_: domain name
    :param connection: libvirt connection URI, overriding defaults

        .. versionadded:: 2019.2.0
    :param username: username to connect with, overriding defaults

        .. versionadded:: 2019.2.0
    :param password: password to connect with, overriding defaults

        .. versionadded:: 2019.2.0

    .. code-block:: python

        [
            'your-vm': {
                'cputime' <int>
                'cputime_percent' <int>
                },
            ...
            ]

    If you pass a VM name in as an argument then it will return info
    for just the named VM, otherwise it will return all VMs.

    CLI Example:

    .. code-block:: bash

        salt '*' virt.vm_cputime
    """
    conn = __get_conn(**kwargs)
    host_cpus = conn.getInfo()[2]

    def _info(dom):
        """
        Compute cputime info of a domain
        """
        raw = dom.info()
        vcpus = int(raw[3])
        cputime = int(raw[4])
        cputime_percent = 0
        if cputime:
            # Divide by vcpus to always return a number between 0 and 100
            cputime_percent = (1.0e-7 * cputime / host_cpus) / vcpus
        return {
            "cputime": int(raw[4]),
            "cputime_percent": int("{:.0f}".format(cputime_percent)),
        }

    info = {}
    if vm_:
        info[vm_] = _info(_get_domain(conn, vm_))
    else:
        for domain in _get_domain(conn, iterable=True):
            info[domain.name()] = _info(domain)
    conn.close()
    return info


def vm_netstats(vm_=None, **kwargs):
    """
    Return combined network counters used by the vms on this hyper in a
    list of dicts:

    :param vm_: domain name
    :param connection: libvirt connection URI, overriding defaults

        .. versionadded:: 2019.2.0
    :param username: username to connect with, overriding defaults

        .. versionadded:: 2019.2.0
    :param password: password to connect with, overriding defaults

        .. versionadded:: 2019.2.0

    .. code-block:: python

        [
            'your-vm': {
                'rx_bytes'   : 0,
                'rx_packets' : 0,
                'rx_errs'    : 0,
                'rx_drop'    : 0,
                'tx_bytes'   : 0,
                'tx_packets' : 0,
                'tx_errs'    : 0,
                'tx_drop'    : 0
                },
            ...
            ]

    If you pass a VM name in as an argument then it will return info
    for just the named VM, otherwise it will return all VMs.

    CLI Example:

    .. code-block:: bash

        salt '*' virt.vm_netstats
    """

    def _info(dom):
        """
        Compute network stats of a domain
        """
        nics = _get_nics(dom)
        ret = {
            "rx_bytes": 0,
            "rx_packets": 0,
            "rx_errs": 0,
            "rx_drop": 0,
            "tx_bytes": 0,
            "tx_packets": 0,
            "tx_errs": 0,
            "tx_drop": 0,
        }
        for attrs in nics.values():
            if "target" in attrs:
                dev = attrs["target"]
                stats = dom.interfaceStats(dev)
                ret["rx_bytes"] += stats[0]
                ret["rx_packets"] += stats[1]
                ret["rx_errs"] += stats[2]
                ret["rx_drop"] += stats[3]
                ret["tx_bytes"] += stats[4]
                ret["tx_packets"] += stats[5]
                ret["tx_errs"] += stats[6]
                ret["tx_drop"] += stats[7]

        return ret

    info = {}
    conn = __get_conn(**kwargs)
    if vm_:
        info[vm_] = _info(_get_domain(conn, vm_))
    else:
        for domain in _get_domain(conn, iterable=True):
            info[domain.name()] = _info(domain)
    conn.close()
    return info


def vm_diskstats(vm_=None, **kwargs):
    """
    Return disk usage counters used by the vms on this hyper in a
    list of dicts:

    :param vm_: domain name
    :param connection: libvirt connection URI, overriding defaults

        .. versionadded:: 2019.2.0
    :param username: username to connect with, overriding defaults

        .. versionadded:: 2019.2.0
    :param password: password to connect with, overriding defaults

        .. versionadded:: 2019.2.0

    .. code-block:: python

        [
            'your-vm': {
                'rd_req'   : 0,
                'rd_bytes' : 0,
                'wr_req'   : 0,
                'wr_bytes' : 0,
                'errs'     : 0
                },
            ...
            ]

    If you pass a VM name in as an argument then it will return info
    for just the named VM, otherwise it will return all VMs.

    CLI Example:

    .. code-block:: bash

        salt '*' virt.vm_blockstats
    """

    def get_disk_devs(dom):
        """
        Extract the disk devices names from the domain XML definition
        """
        doc = ElementTree.fromstring(get_xml(dom, **kwargs))
        return [target.get("dev") for target in doc.findall("devices/disk/target")]

    def _info(dom):
        """
        Compute the disk stats of a domain
        """
        # Do not use get_disks, since it uses qemu-img and is very slow
        # and unsuitable for any sort of real time statistics
        disks = get_disk_devs(dom)
        ret = {"rd_req": 0, "rd_bytes": 0, "wr_req": 0, "wr_bytes": 0, "errs": 0}
        for disk in disks:
            stats = dom.blockStats(disk)
            ret["rd_req"] += stats[0]
            ret["rd_bytes"] += stats[1]
            ret["wr_req"] += stats[2]
            ret["wr_bytes"] += stats[3]
            ret["errs"] += stats[4]

        return ret

    info = {}
    conn = __get_conn(**kwargs)
    if vm_:
        info[vm_] = _info(_get_domain(conn, vm_))
    else:
        # Can not run function blockStats on inactive VMs
        for domain in _get_domain(conn, iterable=True, inactive=False):
            info[domain.name()] = _info(domain)
    conn.close()
    return info


def _parse_snapshot_description(vm_snapshot, unix_time=False):
    """
    Parse XML doc and return a dict with the status values.

    :param xmldoc:
    :return:
    """
    ret = dict()
    tree = ElementTree.fromstring(vm_snapshot.getXMLDesc())
    for node in tree:
        if node.tag == "name":
            ret["name"] = node.text
        elif node.tag == "creationTime":
            ret["created"] = (
                datetime.datetime.fromtimestamp(float(node.text)).isoformat(" ")
                if not unix_time
                else float(node.text)
            )
        elif node.tag == "state":
            ret["running"] = node.text == "running"

    ret["current"] = vm_snapshot.isCurrent() == 1

    return ret


def list_snapshots(domain=None, **kwargs):
    """
    List available snapshots for certain vm or for all.

    :param domain: domain name
    :param connection: libvirt connection URI, overriding defaults

        .. versionadded:: 2019.2.0
    :param username: username to connect with, overriding defaults

        .. versionadded:: 2019.2.0
    :param password: password to connect with, overriding defaults

        .. versionadded:: 2019.2.0

    .. versionadded:: 2016.3.0

    CLI Example:

    .. code-block:: bash

        salt '*' virt.list_snapshots
        salt '*' virt.list_snapshots <domain>
    """
    ret = dict()
    conn = __get_conn(**kwargs)
    for vm_domain in _get_domain(conn, *(domain and [domain] or list()), iterable=True):
        ret[vm_domain.name()] = [
            _parse_snapshot_description(snap) for snap in vm_domain.listAllSnapshots()
        ] or "N/A"

    conn.close()
    return ret


def snapshot(domain, name=None, suffix=None, **kwargs):
    """
    Create a snapshot of a VM.

    :param domain: domain name
    :param name: Name of the snapshot. If the name is omitted, then will be used original domain
                 name with ISO 8601 time as a suffix.

    :param suffix: Add suffix for the new name. Useful in states, where such snapshots
                   can be distinguished from manually created.
    :param connection: libvirt connection URI, overriding defaults

        .. versionadded:: 2019.2.0
    :param username: username to connect with, overriding defaults

        .. versionadded:: 2019.2.0
    :param password: password to connect with, overriding defaults

        .. versionadded:: 2019.2.0

    .. versionadded:: 2016.3.0

    CLI Example:

    .. code-block:: bash

        salt '*' virt.snapshot <domain>
    """
    if name and name.lower() == domain.lower():
        raise CommandExecutionError(
            "Virtual Machine {name} is already defined. "
            "Please choose another name for the snapshot".format(name=name)
        )
    if not name:
        name = "{domain}-{tsnap}".format(
            domain=domain, tsnap=time.strftime("%Y%m%d-%H%M%S", time.localtime())
        )

    if suffix:
        name = "{name}-{suffix}".format(name=name, suffix=suffix)

    doc = ElementTree.Element("domainsnapshot")
    n_name = ElementTree.SubElement(doc, "name")
    n_name.text = name

    conn = __get_conn(**kwargs)
    _get_domain(conn, domain).snapshotCreateXML(
        salt.utils.stringutils.to_str(ElementTree.tostring(doc))
    )
    conn.close()

    return {"name": name}


def delete_snapshots(name, *names, **kwargs):
    """
    Delete one or more snapshots of the given VM.

    :param name: domain name
    :param names: names of the snapshots to remove
    :param connection: libvirt connection URI, overriding defaults

        .. versionadded:: 2019.2.0
    :param username: username to connect with, overriding defaults

        .. versionadded:: 2019.2.0
    :param password: password to connect with, overriding defaults

        .. versionadded:: 2019.2.0

    .. versionadded:: 2016.3.0

    CLI Example:

    .. code-block:: bash

        salt '*' virt.delete_snapshots <domain> all=True
        salt '*' virt.delete_snapshots <domain> <snapshot>
        salt '*' virt.delete_snapshots <domain> <snapshot1> <snapshot2> ...
    """
    deleted = dict()
    conn = __get_conn(**kwargs)
    domain = _get_domain(conn, name)
    for snap in domain.listAllSnapshots():
        if snap.getName() in names or not names:
            deleted[snap.getName()] = _parse_snapshot_description(snap)
            snap.delete()
    conn.close()

    available = {
        name: [_parse_snapshot_description(snap) for snap in domain.listAllSnapshots()]
        or "N/A"
    }

    return {"available": available, "deleted": deleted}


def revert_snapshot(name, vm_snapshot=None, cleanup=False, **kwargs):
    """
    Revert snapshot to the previous from current (if available) or to the specific.

    :param name: domain name
    :param vm_snapshot: name of the snapshot to revert
    :param cleanup: Remove all newer than reverted snapshots. Values: True or False (default False).
    :param connection: libvirt connection URI, overriding defaults

        .. versionadded:: 2019.2.0
    :param username: username to connect with, overriding defaults

        .. versionadded:: 2019.2.0
    :param password: password to connect with, overriding defaults

        .. versionadded:: 2019.2.0

    .. versionadded:: 2016.3.0

    CLI Example:

    .. code-block:: bash

        salt '*' virt.revert <domain>
        salt '*' virt.revert <domain> <snapshot>
    """
    ret = dict()
    conn = __get_conn(**kwargs)
    domain = _get_domain(conn, name)
    snapshots = domain.listAllSnapshots()

    _snapshots = list()
    for snap_obj in snapshots:
        _snapshots.append(
            {
                "idx": _parse_snapshot_description(snap_obj, unix_time=True)["created"],
                "ptr": snap_obj,
            }
        )
    snapshots = [
        w_ptr["ptr"]
        for w_ptr in sorted(_snapshots, key=lambda item: item["idx"], reverse=True)
    ]
    del _snapshots

    if not snapshots:
        conn.close()
        raise CommandExecutionError("No snapshots found")
    elif len(snapshots) == 1:
        conn.close()
        raise CommandExecutionError(
            "Cannot revert to itself: only one snapshot is available."
        )

    snap = None
    for p_snap in snapshots:
        if not vm_snapshot:
            if p_snap.isCurrent() and snapshots[snapshots.index(p_snap) + 1 :]:
                snap = snapshots[snapshots.index(p_snap) + 1 :][0]
                break
        elif p_snap.getName() == vm_snapshot:
            snap = p_snap
            break

    if not snap:
        conn.close()
        raise CommandExecutionError(
            snapshot
            and 'Snapshot "{}" not found'.format(vm_snapshot)
            or "No more previous snapshots available"
        )
    elif snap.isCurrent():
        conn.close()
        raise CommandExecutionError("Cannot revert to the currently running snapshot.")

    domain.revertToSnapshot(snap)
    ret["reverted"] = snap.getName()

    if cleanup:
        delete = list()
        for p_snap in snapshots:
            if p_snap.getName() != snap.getName():
                delete.append(p_snap.getName())
                p_snap.delete()
            else:
                break
        ret["deleted"] = delete
    else:
        ret["deleted"] = "N/A"

    conn.close()

    return ret


def _caps_add_machine(machines, node):
    """
    Parse the <machine> element of the host capabilities and add it
    to the machines list.
    """
    maxcpus = node.get("maxCpus")
    canonical = node.get("canonical")
    name = node.text

    alternate_name = ""
    if canonical:
        alternate_name = name
        name = canonical

    machine = machines.get(name)
    if not machine:
        machine = {"alternate_names": []}
        if maxcpus:
            machine["maxcpus"] = int(maxcpus)
        machines[name] = machine
    if alternate_name:
        machine["alternate_names"].append(alternate_name)


def _parse_caps_guest(guest):
    """
    Parse the <guest> element of the connection capabilities XML
    """
    arch_node = guest.find("arch")
    result = {
        "os_type": guest.find("os_type").text,
        "arch": {"name": arch_node.get("name"), "machines": {}, "domains": {}},
    }

    for child in arch_node:
        if child.tag == "wordsize":
            result["arch"]["wordsize"] = int(child.text)
        elif child.tag == "emulator":
            result["arch"]["emulator"] = child.text
        elif child.tag == "machine":
            _caps_add_machine(result["arch"]["machines"], child)
        elif child.tag == "domain":
            domain_type = child.get("type")
            domain = {"emulator": None, "machines": {}}
            emulator_node = child.find("emulator")
            if emulator_node is not None:
                domain["emulator"] = emulator_node.text
            for machine in child.findall("machine"):
                _caps_add_machine(domain["machines"], machine)
            result["arch"]["domains"][domain_type] = domain

    # Note that some features have no default and toggle attributes.
    # This may not be a perfect match, but represent them as enabled by default
    # without possibility to toggle them.
    # Some guests may also have no feature at all (xen pv for instance)
    features_nodes = guest.find("features")
    if features_nodes is not None:
        result["features"] = {
            child.tag: {
                "toggle": True if child.get("toggle") == "yes" else False,
                "default": True if child.get("default") == "no" else True,
            }
            for child in features_nodes
        }

    return result


def _parse_caps_cell(cell):
    """
    Parse the <cell> nodes of the connection capabilities XML output.
    """
    result = {"id": int(cell.get("id"))}

    mem_node = cell.find("memory")
    if mem_node is not None:
        unit = mem_node.get("unit", "KiB")
        memory = mem_node.text
        result["memory"] = "{} {}".format(memory, unit)

    pages = [
        {
            "size": "{} {}".format(page.get("size"), page.get("unit", "KiB")),
            "available": int(page.text),
        }
        for page in cell.findall("pages")
    ]
    if pages:
        result["pages"] = pages

    distances = {
        int(distance.get("id")): int(distance.get("value"))
        for distance in cell.findall("distances/sibling")
    }
    if distances:
        result["distances"] = distances

    cpus = []
    for cpu_node in cell.findall("cpus/cpu"):
        cpu = {"id": int(cpu_node.get("id"))}
        socket_id = cpu_node.get("socket_id")
        if socket_id:
            cpu["socket_id"] = int(socket_id)

        core_id = cpu_node.get("core_id")
        if core_id:
            cpu["core_id"] = int(core_id)
        siblings = cpu_node.get("siblings")
        if siblings:
            cpu["siblings"] = siblings
        cpus.append(cpu)
    if cpus:
        result["cpus"] = cpus

    return result


def _parse_caps_bank(bank):
    """
    Parse the <bank> element of the connection capabilities XML.
    """
    result = {
        "id": int(bank.get("id")),
        "level": int(bank.get("level")),
        "type": bank.get("type"),
        "size": "{} {}".format(bank.get("size"), bank.get("unit")),
        "cpus": bank.get("cpus"),
    }

    controls = []
    for control in bank.findall("control"):
        unit = control.get("unit")
        result_control = {
            "granularity": "{} {}".format(control.get("granularity"), unit),
            "type": control.get("type"),
            "maxAllocs": int(control.get("maxAllocs")),
        }

        minimum = control.get("min")
        if minimum:
            result_control["min"] = "{} {}".format(minimum, unit)
        controls.append(result_control)
    if controls:
        result["controls"] = controls

    return result


def _parse_caps_host(host):
    """
    Parse the <host> element of the connection capabilities XML.
    """
    result = {}
    for child in host:

        if child.tag == "uuid":
            result["uuid"] = child.text

        elif child.tag == "cpu":
            cpu = {
                "arch": child.find("arch").text
                if child.find("arch") is not None
                else None,
                "model": child.find("model").text
                if child.find("model") is not None
                else None,
                "vendor": child.find("vendor").text
                if child.find("vendor") is not None
                else None,
                "features": [
                    feature.get("name") for feature in child.findall("feature")
                ],
                "pages": [
                    {"size": "{} {}".format(page.get("size"), page.get("unit", "KiB"))}
                    for page in child.findall("pages")
                ],
            }
            # Parse the cpu tag
            microcode = child.find("microcode")
            if microcode is not None:
                cpu["microcode"] = microcode.get("version")

            topology = child.find("topology")
            if topology is not None:
                cpu["sockets"] = int(topology.get("sockets"))
                cpu["cores"] = int(topology.get("cores"))
                cpu["threads"] = int(topology.get("threads"))
            result["cpu"] = cpu

        elif child.tag == "power_management":
            result["power_management"] = [node.tag for node in child]

        elif child.tag == "migration_features":
            result["migration"] = {
                "live": child.find("live") is not None,
                "transports": [
                    node.text for node in child.findall("uri_transports/uri_transport")
                ],
            }

        elif child.tag == "topology":
            result["topology"] = {
                "cells": [
                    _parse_caps_cell(cell) for cell in child.findall("cells/cell")
                ]
            }

        elif child.tag == "cache":
            result["cache"] = {
                "banks": [_parse_caps_bank(bank) for bank in child.findall("bank")]
            }

    result["security"] = [
        {
            "model": secmodel.find("model").text
            if secmodel.find("model") is not None
            else None,
            "doi": secmodel.find("doi").text
            if secmodel.find("doi") is not None
            else None,
            "baselabels": [
                {"type": label.get("type"), "label": label.text}
                for label in secmodel.findall("baselabel")
            ],
        }
        for secmodel in host.findall("secmodel")
    ]

    return result


def _capabilities(conn):
    """
    Return the hypervisor connection capabilities.

    :param conn: opened libvirt connection to use
    """
    caps = ElementTree.fromstring(conn.getCapabilities())

    return {
        "host": _parse_caps_host(caps.find("host")),
        "guests": [_parse_caps_guest(guest) for guest in caps.findall("guest")],
    }


def capabilities(**kwargs):
    """
    Return the hypervisor connection capabilities.

    :param connection: libvirt connection URI, overriding defaults
    :param username: username to connect with, overriding defaults
    :param password: password to connect with, overriding defaults

    .. versionadded:: 2019.2.0

    CLI Example:

    .. code-block:: bash

        salt '*' virt.capabilities
    """
    conn = __get_conn(**kwargs)
    try:
        caps = _capabilities(conn)
    except libvirt.libvirtError as err:
        raise CommandExecutionError(str(err))
    finally:
        conn.close()
    return caps


def _parse_caps_enum(node):
    """
    Return a tuple containing the name of the enum and the possible values
    """
    return (node.get("name"), [value.text for value in node.findall("value")])


def _parse_caps_cpu(node):
    """
    Parse the <cpu> element of the domain capabilities
    """
    result = {}
    for mode in node.findall("mode"):
        if not mode.get("supported") == "yes":
            continue

        name = mode.get("name")
        if name == "host-passthrough":
            result[name] = True

        elif name == "host-model":
            host_model = {}
            model_node = mode.find("model")
            if model_node is not None:
                model = {"name": model_node.text}

                vendor_id = model_node.get("vendor_id")
                if vendor_id:
                    model["vendor_id"] = vendor_id

                fallback = model_node.get("fallback")
                if fallback:
                    model["fallback"] = fallback
                host_model["model"] = model

            vendor = (
                mode.find("vendor").text if mode.find("vendor") is not None else None
            )
            if vendor:
                host_model["vendor"] = vendor

            features = {
                feature.get("name"): feature.get("policy")
                for feature in mode.findall("feature")
            }
            if features:
                host_model["features"] = features

            result[name] = host_model

        elif name == "custom":
            custom_model = {}
            models = {
                model.text: model.get("usable") for model in mode.findall("model")
            }
            if models:
                custom_model["models"] = models
            result[name] = custom_model

    return result


def _parse_caps_devices_features(node):
    """
    Parse the devices or features list of the domain capatilities
    """
    result = {}
    for child in node:
        if child.get("supported") == "yes":
            enums = [_parse_caps_enum(node) for node in child.findall("enum")]
            result[child.tag] = {item[0]: item[1] for item in enums if item[0]}
    return result


def _parse_caps_loader(node):
    """
    Parse the <loader> element of the domain capabilities.
    """
    enums = [_parse_caps_enum(enum) for enum in node.findall("enum")]
    result = {item[0]: item[1] for item in enums if item[0]}

    values = [child.text for child in node.findall("value")]

    if values:
        result["values"] = values

    return result


def _parse_domain_caps(caps):
    """
    Parse the XML document of domain capabilities into a structure.
    """
    result = {
        "emulator": caps.find("path").text if caps.find("path") is not None else None,
        "domain": caps.find("domain").text if caps.find("domain") is not None else None,
        "machine": caps.find("machine").text
        if caps.find("machine") is not None
        else None,
        "arch": caps.find("arch").text if caps.find("arch") is not None else None,
    }

    for child in caps:
        if child.tag == "vcpu" and child.get("max"):
            result["max_vcpus"] = int(child.get("max"))

        elif child.tag == "iothreads":
            result["iothreads"] = child.get("supported") == "yes"

        elif child.tag == "os":
            result["os"] = {}
            loader_node = child.find("loader")
            if loader_node is not None and loader_node.get("supported") == "yes":
                loader = _parse_caps_loader(loader_node)
                result["os"]["loader"] = loader

        elif child.tag == "cpu":
            cpu = _parse_caps_cpu(child)
            if cpu:
                result["cpu"] = cpu

        elif child.tag == "devices":
            devices = _parse_caps_devices_features(child)
            if devices:
                result["devices"] = devices

        elif child.tag == "features":
            features = _parse_caps_devices_features(child)
            if features:
                result["features"] = features

    return result


def domain_capabilities(emulator=None, arch=None, machine=None, domain=None, **kwargs):
    """
    Return the domain capabilities given an emulator, architecture, machine or virtualization type.

    .. versionadded:: 2019.2.0

    :param emulator: return the capabilities for the given emulator binary
    :param arch: return the capabilities for the given CPU architecture
    :param machine: return the capabilities for the given emulated machine type
    :param domain: return the capabilities for the given virtualization type.
    :param connection: libvirt connection URI, overriding defaults
    :param username: username to connect with, overriding defaults
    :param password: password to connect with, overriding defaults

    The list of the possible emulator, arch, machine and domain can be found in
    the host capabilities output.

    If none of the parameters is provided, the libvirt default one is returned.

    CLI Example:

    .. code-block:: bash

        salt '*' virt.domain_capabilities arch='x86_64' domain='kvm'

    """
    conn = __get_conn(**kwargs)
    result = []
    try:
        caps = ElementTree.fromstring(
            conn.getDomainCapabilities(emulator, arch, machine, domain, 0)
        )
        result = _parse_domain_caps(caps)
    finally:
        conn.close()

    return result


def all_capabilities(**kwargs):
    """
    Return the host and domain capabilities in a single call.

    .. versionadded:: 3001

    :param connection: libvirt connection URI, overriding defaults
    :param username: username to connect with, overriding defaults
    :param password: password to connect with, overriding defaults

    CLI Example:

    .. code-block:: bash

        salt '*' virt.all_capabilities

    """
    conn = __get_conn(**kwargs)
    result = {}
    try:
        host_caps = ElementTree.fromstring(conn.getCapabilities())
        domains = [
            [
                (guest.get("arch", {}).get("name", None), key)
                for key in guest.get("arch", {}).get("domains", {}).keys()
            ]
            for guest in [
                _parse_caps_guest(guest) for guest in host_caps.findall("guest")
            ]
        ]
        flattened = [pair for item in (x for x in domains) for pair in item]
        result = {
            "host": {
                "host": _parse_caps_host(host_caps.find("host")),
                "guests": [
                    _parse_caps_guest(guest) for guest in host_caps.findall("guest")
                ],
            },
            "domains": [
                _parse_domain_caps(
                    ElementTree.fromstring(
                        conn.getDomainCapabilities(None, arch, None, domain)
                    )
                )
                for (arch, domain) in flattened
            ],
        }
    finally:
        conn.close()

    return result


def cpu_baseline(full=False, migratable=False, out="libvirt", **kwargs):
    """
    Return the optimal 'custom' CPU baseline config for VM's on this minion

    .. versionadded:: 2016.3.0

    :param full: Return all CPU features rather than the ones on top of the closest CPU model
    :param migratable: Exclude CPU features that are unmigratable (libvirt 2.13+)
    :param out: 'libvirt' (default) for usable libvirt XML definition, 'salt' for nice dict
    :param connection: libvirt connection URI, overriding defaults

        .. versionadded:: 2019.2.0
    :param username: username to connect with, overriding defaults

        .. versionadded:: 2019.2.0
    :param password: password to connect with, overriding defaults

        .. versionadded:: 2019.2.0

    CLI Example:

    .. code-block:: bash

        salt '*' virt.cpu_baseline

    """
    conn = __get_conn(**kwargs)
    caps = ElementTree.fromstring(conn.getCapabilities())
    cpu = caps.find("host/cpu")
    log.debug(
        "Host CPU model definition: %s",
        salt.utils.stringutils.to_str(ElementTree.tostring(cpu)),
    )

    flags = 0
    if migratable:
        # This one is only in 1.2.14+
        if getattr(libvirt, "VIR_CONNECT_BASELINE_CPU_MIGRATABLE", False):
            flags += libvirt.VIR_CONNECT_BASELINE_CPU_MIGRATABLE
        else:
            conn.close()
            raise ValueError

    if full and getattr(libvirt, "VIR_CONNECT_BASELINE_CPU_EXPAND_FEATURES", False):
        # This one is only in 1.1.3+
        flags += libvirt.VIR_CONNECT_BASELINE_CPU_EXPAND_FEATURES

    cpu = ElementTree.fromstring(
        conn.baselineCPU(
            [salt.utils.stringutils.to_str(ElementTree.tostring(cpu))], flags
        )
    )
    conn.close()

    if full and not getattr(libvirt, "VIR_CONNECT_BASELINE_CPU_EXPAND_FEATURES", False):
        # Try do it by ourselves
        # Find the models in cpu_map.xml and iterate over them for as long as entries have submodels
        with salt.utils.files.fopen("/usr/share/libvirt/cpu_map.xml", "r") as cpu_map:
            cpu_map = ElementTree.parse(cpu_map)

        cpu_model = cpu.find("model").text
        while cpu_model:
            cpu_map_models = cpu_map.findall("arch/model")
            cpu_specs = [
                el
                for el in cpu_map_models
                if el.get("name") == cpu_model and bool(len(el))
            ]

            if not cpu_specs:
                raise ValueError("Model {} not found in CPU map".format(cpu_model))
            elif len(cpu_specs) > 1:
                raise ValueError(
                    "Multiple models {} found in CPU map".format(cpu_model)
                )

            cpu_specs = cpu_specs[0]

            # libvirt's cpu map used to nest model elements, to point the parent model.
            # keep this code for compatibility with old libvirt versions
            model_node = cpu_specs.find("model")
            if model_node is None:
                cpu_model = None
            else:
                cpu_model = model_node.get("name")

            cpu.extend([feature for feature in cpu_specs.findall("feature")])

    if out == "salt":
        return {
            "model": cpu.find("model").text,
            "vendor": cpu.find("vendor").text,
            "features": [feature.get("name") for feature in cpu.findall("feature")],
        }
    return ElementTree.tostring(cpu)


def network_define(name, bridge, forward, ipv4_config=None, ipv6_config=None, **kwargs):
    """
    Create libvirt network.

    :param name: Network name
    :param bridge: Bridge name
    :param forward: Forward mode(bridge, router, nat)
    :param vport: Virtualport type
    :param tag: Vlan tag
    :param autostart: Network autostart (default True)
    :param start: Network start (default True)
    :param ipv4_config: IP v4 configuration
        Dictionary describing the IP v4 setup like IP range and
        a possible DHCP configuration. The structure is documented
        in net-define-ip_.

        .. versionadded:: 3000
    :type ipv4_config: dict or None

    :param ipv6_config: IP v6 configuration
        Dictionary describing the IP v6 setup like IP range and
        a possible DHCP configuration. The structure is documented
        in net-define-ip_.

        .. versionadded:: 3000
    :type ipv6_config: dict or None

    :param connection: libvirt connection URI, overriding defaults
    :param username: username to connect with, overriding defaults
    :param password: password to connect with, overriding defaults

    .. _net-define-ip:

    ** IP configuration definition

    Both the IPv4 and IPv6 configuration dictionaries can contain the following properties:

    cidr
        CIDR notation for the network. For example '192.168.124.0/24'

    dhcp_ranges
        A list of dictionary with ``'start'`` and ``'end'`` properties.

    CLI Example:

    .. code-block:: bash

        salt '*' virt.network_define network main bridge openvswitch

    .. versionadded:: 2019.2.0
    """
    conn = __get_conn(**kwargs)
    vport = kwargs.get("vport", None)
    tag = kwargs.get("tag", None)
    autostart = kwargs.get("autostart", True)
    starting = kwargs.get("start", True)

    net_xml = _gen_net_xml(
        name,
        bridge,
        forward,
        vport,
        tag=tag,
        ip_configs=[config for config in [ipv4_config, ipv6_config] if config],
    )
    try:
        conn.networkDefineXML(net_xml)
    except libvirt.libvirtError as err:
        log.warning(err)
        conn.close()
        raise err  # a real error we should report upwards

    try:
        network = conn.networkLookupByName(name)
    except libvirt.libvirtError as err:
        log.warning(err)
        conn.close()
        raise err  # a real error we should report upwards

    if network is None:
        conn.close()
        return False

    if (starting is True or autostart is True) and network.isActive() != 1:
        network.create()

    if autostart is True and network.autostart() != 1:
        network.setAutostart(int(autostart))
    elif autostart is False and network.autostart() == 1:
        network.setAutostart(int(autostart))

    conn.close()

    return True


def list_networks(**kwargs):
    """
    List all virtual networks.

    :param connection: libvirt connection URI, overriding defaults
    :param username: username to connect with, overriding defaults
    :param password: password to connect with, overriding defaults

    .. versionadded:: 2019.2.0

    CLI Example:

    .. code-block:: bash

       salt '*' virt.list_networks
    """
    conn = __get_conn(**kwargs)
    try:
        return [net.name() for net in conn.listAllNetworks()]
    finally:
        conn.close()


def network_info(name=None, **kwargs):
    """
    Return information on a virtual network provided its name.

    :param name: virtual network name
    :param connection: libvirt connection URI, overriding defaults
    :param username: username to connect with, overriding defaults
    :param password: password to connect with, overriding defaults

    If no name is provided, return the infos for all defined virtual networks.

    .. versionadded:: 2019.2.0

    CLI Example:

    .. code-block:: bash

        salt '*' virt.network_info default
    """
    result = {}
    conn = __get_conn(**kwargs)

    def _net_get_leases(net):
        """
        Get all DHCP leases for a network
        """
        leases = net.DHCPLeases()
        for lease in leases:
            if lease["type"] == libvirt.VIR_IP_ADDR_TYPE_IPV4:
                lease["type"] = "ipv4"
            elif lease["type"] == libvirt.VIR_IP_ADDR_TYPE_IPV6:
                lease["type"] = "ipv6"
            else:
                lease["type"] = "unknown"
        return leases

    try:
        nets = [
            net for net in conn.listAllNetworks() if name is None or net.name() == name
        ]
        result = {
            net.name(): {
                "uuid": net.UUIDString(),
                "bridge": net.bridgeName(),
                "autostart": net.autostart(),
                "active": net.isActive(),
                "persistent": net.isPersistent(),
                "leases": _net_get_leases(net),
            }
            for net in nets
        }
    except libvirt.libvirtError as err:
        log.debug("Silenced libvirt error: %s", str(err))
    finally:
        conn.close()
    return result


def network_get_xml(name, **kwargs):
    """
    Return the XML definition of a virtual network

    :param name: libvirt network name
    :param connection: libvirt connection URI, overriding defaults
    :param username: username to connect with, overriding defaults
    :param password: password to connect with, overriding defaults

    .. versionadded:: 3000

    CLI Example:

    .. code-block:: bash

        salt '*' virt.network_get_xml default
    """
    conn = __get_conn(**kwargs)
    try:
        return conn.networkLookupByName(name).XMLDesc()
    finally:
        conn.close()


def network_start(name, **kwargs):
    """
    Start a defined virtual network.

    :param name: virtual network name
    :param connection: libvirt connection URI, overriding defaults
    :param username: username to connect with, overriding defaults
    :param password: password to connect with, overriding defaults

    .. versionadded:: 2019.2.0

    CLI Example:

    .. code-block:: bash

        salt '*' virt.network_start default
    """
    conn = __get_conn(**kwargs)
    try:
        net = conn.networkLookupByName(name)
        return not bool(net.create())
    finally:
        conn.close()


def network_stop(name, **kwargs):
    """
    Stop a defined virtual network.

    :param name: virtual network name
    :param connection: libvirt connection URI, overriding defaults
    :param username: username to connect with, overriding defaults
    :param password: password to connect with, overriding defaults

    .. versionadded:: 2019.2.0

    CLI Example:

    .. code-block:: bash

        salt '*' virt.network_stop default
    """
    conn = __get_conn(**kwargs)
    try:
        net = conn.networkLookupByName(name)
        return not bool(net.destroy())
    finally:
        conn.close()


def network_undefine(name, **kwargs):
    """
    Remove a defined virtual network. This does not stop the virtual network.

    :param name: virtual network name
    :param connection: libvirt connection URI, overriding defaults
    :param username: username to connect with, overriding defaults
    :param password: password to connect with, overriding defaults

    .. versionadded:: 2019.2.0

    CLI Example:

    .. code-block:: bash

        salt '*' virt.network_undefine default
    """
    conn = __get_conn(**kwargs)
    try:
        net = conn.networkLookupByName(name)
        return not bool(net.undefine())
    finally:
        conn.close()


def network_set_autostart(name, state="on", **kwargs):
    """
    Set the autostart flag on a virtual network so that the network
    will start with the host system on reboot.

    :param name: virtual network name
    :param state: 'on' to auto start the network, anything else to mark the
                  virtual network not to be started when the host boots
    :param connection: libvirt connection URI, overriding defaults
    :param username: username to connect with, overriding defaults
    :param password: password to connect with, overriding defaults

    .. versionadded:: 2019.2.0

    CLI Example:

    .. code-block:: bash

        salt "*" virt.network_set_autostart <pool> <on | off>
    """
    conn = __get_conn(**kwargs)
    try:
        net = conn.networkLookupByName(name)
        return not bool(net.setAutostart(1 if state == "on" else 0))
    finally:
        conn.close()


def _parse_pools_caps(doc):
    """
    Parse libvirt pool capabilities XML
    """

    def _parse_pool_caps(pool):
        pool_caps = {
            "name": pool.get("type"),
            "supported": pool.get("supported", "no") == "yes",
        }
        for option_kind in ["pool", "vol"]:
            options = {}
            default_format_node = pool.find(
                "{}Options/defaultFormat".format(option_kind)
            )
            if default_format_node is not None:
                options["default_format"] = default_format_node.get("type")
            options_enums = {
                enum.get("name"): [value.text for value in enum.findall("value")]
                for enum in pool.findall("{}Options/enum".format(option_kind))
            }
            if options_enums:
                options.update(options_enums)
            if options:
                if "options" not in pool_caps:
                    pool_caps["options"] = {}
                kind = option_kind if option_kind != "vol" else "volume"
                pool_caps["options"][kind] = options
        return pool_caps

    return [_parse_pool_caps(pool) for pool in doc.findall("pool")]


def _pool_capabilities(conn):
    """
    Return the hypervisor connection storage pool capabilities.

    :param conn: opened libvirt connection to use
    """
    has_pool_capabilities = bool(getattr(conn, "getStoragePoolCapabilities", None))
    if has_pool_capabilities:
        caps = ElementTree.fromstring(conn.getStoragePoolCapabilities())
        pool_types = _parse_pools_caps(caps)
    else:
        # Compute reasonable values
        all_hypervisors = ["xen", "kvm", "bhyve"]
        images_formats = [
            "none",
            "raw",
            "dir",
            "bochs",
            "cloop",
            "dmg",
            "iso",
            "vpc",
            "vdi",
            "fat",
            "vhd",
            "ploop",
            "cow",
            "qcow",
            "qcow2",
            "qed",
            "vmdk",
        ]
        common_drivers = [
            {
                "name": "fs",
                "default_source_format": "auto",
                "source_formats": [
                    "auto",
                    "ext2",
                    "ext3",
                    "ext4",
                    "ufs",
                    "iso9660",
                    "udf",
                    "gfs",
                    "gfs2",
                    "vfat",
                    "hfs+",
                    "xfs",
                    "ocfs2",
                ],
                "default_target_format": "raw",
                "target_formats": images_formats,
            },
            {
                "name": "dir",
                "default_target_format": "raw",
                "target_formats": images_formats,
            },
            {"name": "iscsi"},
            {"name": "scsi"},
            {
                "name": "logical",
                "default_source_format": "lvm2",
                "source_formats": ["unknown", "lvm2"],
            },
            {
                "name": "netfs",
                "default_source_format": "auto",
                "source_formats": ["auto", "nfs", "glusterfs", "cifs"],
                "default_target_format": "raw",
                "target_formats": images_formats,
            },
            {
                "name": "disk",
                "default_source_format": "unknown",
                "source_formats": [
                    "unknown",
                    "dos",
                    "dvh",
                    "gpt",
                    "mac",
                    "bsd",
                    "pc98",
                    "sun",
                    "lvm2",
                ],
                "default_target_format": "none",
                "target_formats": [
                    "none",
                    "linux",
                    "fat16",
                    "fat32",
                    "linux-swap",
                    "linux-lvm",
                    "linux-raid",
                    "extended",
                ],
            },
            {"name": "mpath"},
            {"name": "rbd", "default_target_format": "raw", "target_formats": []},
            {
                "name": "sheepdog",
                "version": 10000,
                "hypervisors": ["kvm"],
                "default_target_format": "raw",
                "target_formats": images_formats,
            },
            {
                "name": "gluster",
                "version": 1002000,
                "hypervisors": ["kvm"],
                "default_target_format": "raw",
                "target_formats": images_formats,
            },
            {"name": "zfs", "version": 1002008, "hypervisors": ["bhyve"]},
            {
                "name": "iscsi-direct",
                "version": 4007000,
                "hypervisors": ["kvm", "xen"],
            },
        ]

        libvirt_version = conn.getLibVersion()
        hypervisor = get_hypervisor()

        def _get_backend_output(backend):
            output = {
                "name": backend["name"],
                "supported": (
                    not backend.get("version") or libvirt_version >= backend["version"]
                )
                and hypervisor in backend.get("hypervisors", all_hypervisors),
                "options": {
                    "pool": {
                        "default_format": backend.get("default_source_format"),
                        "sourceFormatType": backend.get("source_formats"),
                    },
                    "volume": {
                        "default_format": backend.get("default_target_format"),
                        "targetFormatType": backend.get("target_formats"),
                    },
                },
            }

            # Cleanup the empty members to match the libvirt output
            for option_kind in ["pool", "volume"]:
                if not [
                    value
                    for value in output["options"][option_kind].values()
                    if value is not None
                ]:
                    del output["options"][option_kind]
            if not output["options"]:
                del output["options"]

            return output

        pool_types = [_get_backend_output(backend) for backend in common_drivers]

    return {
        "computed": not has_pool_capabilities,
        "pool_types": pool_types,
    }


def pool_capabilities(**kwargs):
    """
    Return the hypervisor connection storage pool capabilities.

    The returned data are either directly extracted from libvirt or computed.
    In the latter case some pool types could be listed as supported while they
    are not. To distinguish between the two cases, check the value of the ``computed`` property.

    :param connection: libvirt connection URI, overriding defaults
    :param username: username to connect with, overriding defaults
    :param password: password to connect with, overriding defaults

    .. versionadded:: 3000

    CLI Example:

    .. code-block:: bash

        salt '*' virt.pool_capabilities

    """
    try:
        conn = __get_conn(**kwargs)
        return _pool_capabilities(conn)
    finally:
        conn.close()


def pool_define(
    name,
    ptype,
    target=None,
    permissions=None,
    source_devices=None,
    source_dir=None,
    source_initiator=None,
    source_adapter=None,
    source_hosts=None,
    source_auth=None,
    source_name=None,
    source_format=None,
    transient=False,
    start=True,  # pylint: disable=redefined-outer-name
    **kwargs
):
    """
    Create libvirt pool.

    :param name: Pool name
    :param ptype:
        Pool type. See `libvirt documentation <https://libvirt.org/storage.html>`_  for the
        possible values.
    :param target: Pool full path target
    :param permissions:
        Permissions to set on the target folder. This is mostly used for filesystem-based
        pool types. See :ref:`pool-define-permissions` for more details on this structure.
    :param source_devices:
        List of source devices for pools backed by physical devices. (Default: ``None``)

        Each item in the list is a dictionary with ``path`` and optionally ``part_separator``
        keys. The path is the qualified name for iSCSI devices.

        Report to `this libvirt page <https://libvirt.org/formatstorage.html#StoragePool>`_
        for more information on the use of ``part_separator``
    :param source_dir:
        Path to the source directory for pools of type ``dir``, ``netfs`` or ``gluster``.
        (Default: ``None``)
    :param source_initiator:
        Initiator IQN for libiscsi-direct pool types. (Default: ``None``)

        .. versionadded:: 3000
    :param source_adapter:
        SCSI source definition. The value is a dictionary with ``type``, ``name``, ``parent``,
        ``managed``, ``parent_wwnn``, ``parent_wwpn``, ``parent_fabric_wwn``, ``wwnn``, ``wwpn``
        and ``parent_address`` keys.

        The ``parent_address`` value is a dictionary with ``unique_id`` and ``address`` keys.
        The address represents a PCI address and is itself a dictionary with ``domain``, ``bus``,
        ``slot`` and ``function`` properties.
        Report to `this libvirt page <https://libvirt.org/formatstorage.html#StoragePool>`_
        for the meaning and possible values of these properties.
    :param source_hosts:
        List of source for pools backed by storage from remote servers. Each item is the hostname
        optionally followed by the port separated by a colon. (Default: ``None``)
    :param source_auth:
        Source authentication details. (Default: ``None``)

        The value is a dictionary with ``type``, ``username`` and ``secret`` keys. The type
        can be one of ``ceph`` for Ceph RBD or ``chap`` for iSCSI sources.

        The ``secret`` value links to a libvirt secret object. It is a dictionary with
        ``type`` and ``value`` keys. The type value can be either ``uuid`` or ``usage``.

        Examples:

        .. code-block:: python

            source_auth={
                'type': 'ceph',
                'username': 'admin',
                'secret': {
                    'type': 'uuid',
                    'value': '2ec115d7-3a88-3ceb-bc12-0ac909a6fd87'
                }
            }

        .. code-block:: python

            source_auth={
                'type': 'chap',
                'username': 'myname',
                'secret': {
                    'type': 'usage',
                    'value': 'mycluster_myname'
                }
            }

        Since 3000, instead the source authentication can only contain ``username``
        and ``password`` properties. In this case the libvirt secret will be defined and used.
        For Ceph authentications a base64 encoded key is expected.

    :param source_name:
        Identifier of name-based sources.
    :param source_format:
        String representing the source format. The possible values are depending on the
        source type. See `libvirt documentation <https://libvirt.org/storage.html>`_ for
        the possible values.
    :param start: Pool start (default True)
    :param transient:
        When ``True``, the pool will be automatically undefined after being stopped.
        Note that a transient pool will force ``start`` to ``True``. (Default: ``False``)
    :param connection: libvirt connection URI, overriding defaults
    :param username: username to connect with, overriding defaults
    :param password: password to connect with, overriding defaults

    .. _pool-define-permissions:

    .. rubric:: Permissions definition

    The permissions are described by a dictionary containing the following keys:

    mode
        The octal representation of the permissions. (Default: `0711`)

    owner
        the numeric user ID of the owner. (Default: from the parent folder)

    group
        the numeric ID of the group. (Default: from the parent folder)

    label
        the SELinux label. (Default: `None`)


    .. rubric:: CLI Example:

    Local folder pool:

    .. code-block:: bash

        salt '*' virt.pool_define somepool dir target=/srv/mypool \
                                  permissions="{'mode': '0744' 'ower': 107, 'group': 107 }"

    CIFS backed pool:

    .. code-block:: bash

        salt '*' virt.pool_define myshare netfs source_format=cifs \
                                  source_dir=samba_share source_hosts="['example.com']" target=/mnt/cifs

    .. versionadded:: 2019.2.0
    """
    conn = __get_conn(**kwargs)
    auth = _pool_set_secret(conn, ptype, name, source_auth)

    pool_xml = _gen_pool_xml(
        name,
        ptype,
        target,
        permissions=permissions,
        source_devices=source_devices,
        source_dir=source_dir,
        source_adapter=source_adapter,
        source_hosts=source_hosts,
        source_auth=auth,
        source_name=source_name,
        source_format=source_format,
        source_initiator=source_initiator,
    )
    try:
        if transient:
            pool = conn.storagePoolCreateXML(pool_xml)
        else:
            pool = conn.storagePoolDefineXML(pool_xml)
            if start:
                pool.create()
    except libvirt.libvirtError as err:
        raise err  # a real error we should report upwards
    finally:
        conn.close()

    # libvirt function will raise a libvirtError in case of failure
    return True


def _pool_set_secret(
    conn, pool_type, pool_name, source_auth, uuid=None, usage=None, test=False
):
    secret_types = {"rbd": "ceph", "iscsi": "chap", "iscsi-direct": "chap"}
    secret_type = secret_types.get(pool_type)
    auth = source_auth
    if source_auth and "username" in source_auth and "password" in source_auth:
        if secret_type:
            # Get the previously defined secret if any
            secret = None
            try:
                if usage:
                    usage_type = (
                        libvirt.VIR_SECRET_USAGE_TYPE_CEPH
                        if secret_type == "ceph"
                        else libvirt.VIR_SECRET_USAGE_TYPE_ISCSI
                    )
                    secret = conn.secretLookupByUsage(usage_type, usage)
                elif uuid:
                    secret = conn.secretLookupByUUIDString(uuid)
            except libvirt.libvirtError as err:
                # For some reason the secret has been removed. Don't fail since we'll recreate it
                log.info("Secret not found: %s", err.get_error_message())

            # Create secret if needed
            if not secret:
                description = "Passphrase for {} pool created by Salt".format(pool_name)
                if not usage:
                    usage = "pool_{}".format(pool_name)
                secret_xml = _gen_secret_xml(secret_type, usage, description)
                if not test:
                    secret = conn.secretDefineXML(secret_xml)

            # Assign the password to it
            password = auth["password"]
            if pool_type == "rbd":
                # RBD password are already base64-encoded, but libvirt will base64-encode them later
                password = base64.b64decode(salt.utils.stringutils.to_bytes(password))
            if not test:
                secret.setValue(password)

            # update auth with secret reference
            auth["type"] = secret_type
            auth["secret"] = {
                "type": "uuid" if uuid else "usage",
                "value": uuid if uuid else usage,
            }
    return auth


def pool_update(
    name,
    ptype,
    target=None,
    permissions=None,
    source_devices=None,
    source_dir=None,
    source_initiator=None,
    source_adapter=None,
    source_hosts=None,
    source_auth=None,
    source_name=None,
    source_format=None,
    test=False,
    **kwargs
):
    """
    Update a libvirt storage pool if needed.
    If called with test=True, this is also reporting whether an update would be performed.

    :param name: Pool name
    :param ptype:
        Pool type. See `libvirt documentation <https://libvirt.org/storage.html>`_  for the
        possible values.
    :param target: Pool full path target
    :param permissions:
        Permissions to set on the target folder. This is mostly used for filesystem-based
        pool types. See :ref:`pool-define-permissions` for more details on this structure.
    :param source_devices:
        List of source devices for pools backed by physical devices. (Default: ``None``)

        Each item in the list is a dictionary with ``path`` and optionally ``part_separator``
        keys. The path is the qualified name for iSCSI devices.

        Report to `this libvirt page <https://libvirt.org/formatstorage.html#StoragePool>`_
        for more information on the use of ``part_separator``
    :param source_dir:
        Path to the source directory for pools of type ``dir``, ``netfs`` or ``gluster``.
        (Default: ``None``)
    :param source_initiator:
        Initiator IQN for libiscsi-direct pool types. (Default: ``None``)

        .. versionadded:: 3000
    :param source_adapter:
        SCSI source definition. The value is a dictionary with ``type``, ``name``, ``parent``,
        ``managed``, ``parent_wwnn``, ``parent_wwpn``, ``parent_fabric_wwn``, ``wwnn``, ``wwpn``
        and ``parent_address`` keys.

        The ``parent_address`` value is a dictionary with ``unique_id`` and ``address`` keys.
        The address represents a PCI address and is itself a dictionary with ``domain``, ``bus``,
        ``slot`` and ``function`` properties.
        Report to `this libvirt page <https://libvirt.org/formatstorage.html#StoragePool>`_
        for the meaning and possible values of these properties.
    :param source_hosts:
        List of source for pools backed by storage from remote servers. Each item is the hostname
        optionally followed by the port separated by a colon. (Default: ``None``)
    :param source_auth:
        Source authentication details. (Default: ``None``)

        The value is a dictionary with ``type``, ``username`` and ``secret`` keys. The type
        can be one of ``ceph`` for Ceph RBD or ``chap`` for iSCSI sources.

        The ``secret`` value links to a libvirt secret object. It is a dictionary with
        ``type`` and ``value`` keys. The type value can be either ``uuid`` or ``usage``.

        Examples:

        .. code-block:: python

            source_auth={
                'type': 'ceph',
                'username': 'admin',
                'secret': {
                    'type': 'uuid',
                    'uuid': '2ec115d7-3a88-3ceb-bc12-0ac909a6fd87'
                }
            }

        .. code-block:: python

            source_auth={
                'type': 'chap',
                'username': 'myname',
                'secret': {
                    'type': 'usage',
                    'uuid': 'mycluster_myname'
                }
            }

        Since 3000, instead the source authentication can only contain ``username``
        and ``password`` properties. In this case the libvirt secret will be defined and used.
        For Ceph authentications a base64 encoded key is expected.

    :param source_name:
        Identifier of name-based sources.
    :param source_format:
        String representing the source format. The possible values are depending on the
        source type. See `libvirt documentation <https://libvirt.org/storage.html>`_ for
        the possible values.
    :param test: run in dry-run mode if set to True
    :param connection: libvirt connection URI, overriding defaults
    :param username: username to connect with, overriding defaults
    :param password: password to connect with, overriding defaults

    .. rubric:: Example:

    Local folder pool:

    .. code-block:: bash

        salt '*' virt.pool_update somepool dir target=/srv/mypool \
                                  permissions="{'mode': '0744' 'ower': 107, 'group': 107 }"

    CIFS backed pool:

    .. code-block:: bash

        salt '*' virt.pool_update myshare netfs source_format=cifs \
                                  source_dir=samba_share source_hosts="['example.com']" target=/mnt/cifs

    .. versionadded:: 3000
    """
    # Get the current definition to compare the two
    conn = __get_conn(**kwargs)
    needs_update = False
    try:
        pool = conn.storagePoolLookupByName(name)
        old_xml = ElementTree.fromstring(pool.XMLDesc())

        # If we have username and password in source_auth generate a new secret
        # Or change the value of the existing one
        secret_node = old_xml.find("source/auth/secret")
        usage = secret_node.get("usage") if secret_node is not None else None
        uuid = secret_node.get("uuid") if secret_node is not None else None
        auth = _pool_set_secret(
            conn, ptype, name, source_auth, uuid=uuid, usage=usage, test=test
        )

        # Compute new definition
        new_xml = ElementTree.fromstring(
            _gen_pool_xml(
                name,
                ptype,
                target,
                permissions=permissions,
                source_devices=source_devices,
                source_dir=source_dir,
                source_initiator=source_initiator,
                source_adapter=source_adapter,
                source_hosts=source_hosts,
                source_auth=auth,
                source_name=source_name,
                source_format=source_format,
            )
        )

        # Copy over the uuid, capacity, allocation, available elements
        elements_to_copy = ["available", "allocation", "capacity", "uuid"]
        for to_copy in elements_to_copy:
            element = old_xml.find(to_copy)
            new_xml.insert(1, element)

        # Filter out spaces and empty elements like <source/> since those would mislead the comparison
        def visit_xml(node, fn):
            fn(node)
            for child in node:
                visit_xml(child, fn)

        def space_stripper(node):
            if node.tail is not None:
                node.tail = node.tail.strip(" \t\n")
            if node.text is not None:
                node.text = node.text.strip(" \t\n")

        visit_xml(old_xml, space_stripper)
        visit_xml(new_xml, space_stripper)

        def empty_node_remover(node):
            for child in node:
                if (
                    not child.tail
                    and not child.text
                    and not child.items()
                    and not child
                ):
                    node.remove(child)

        visit_xml(old_xml, empty_node_remover)

        needs_update = xmlutil.to_dict(old_xml, True) != xmlutil.to_dict(new_xml, True)
        if needs_update and not test:
            conn.storagePoolDefineXML(
                salt.utils.stringutils.to_str(ElementTree.tostring(new_xml))
            )
    finally:
        conn.close()
    return needs_update


def list_pools(**kwargs):
    """
    List all storage pools.

    :param connection: libvirt connection URI, overriding defaults
    :param username: username to connect with, overriding defaults
    :param password: password to connect with, overriding defaults

    .. versionadded:: 2019.2.0

    CLI Example:

    .. code-block:: bash

        salt '*' virt.list_pools
    """
    conn = __get_conn(**kwargs)
    try:
        return [pool.name() for pool in conn.listAllStoragePools()]
    finally:
        conn.close()


def pool_info(name=None, **kwargs):
    """
    Return information on a storage pool provided its name.

    :param name: libvirt storage pool name
    :param connection: libvirt connection URI, overriding defaults
    :param username: username to connect with, overriding defaults
    :param password: password to connect with, overriding defaults

    If no name is provided, return the infos for all defined storage pools.

    .. versionadded:: 2019.2.0

    CLI Example:

    .. code-block:: bash

        salt '*' virt.pool_info default
    """
    result = {}
    conn = __get_conn(**kwargs)

    def _pool_extract_infos(pool):
        """
        Format the pool info dictionary

        :param pool: the libvirt pool object
        """
        states = ["inactive", "building", "running", "degraded", "inaccessible"]
        infos = pool.info()
        state = states[infos[0]] if infos[0] < len(states) else "unknown"
        desc = ElementTree.fromstring(pool.XMLDesc())
        path_node = desc.find("target/path")
        return {
            "uuid": pool.UUIDString(),
            "state": state,
            "capacity": infos[1],
            "allocation": infos[2],
            "free": infos[3],
            "autostart": pool.autostart(),
            "persistent": pool.isPersistent(),
            "target_path": path_node.text if path_node is not None else None,
            "type": desc.get("type"),
        }

    try:
        pools = [
            pool
            for pool in conn.listAllStoragePools()
            if name is None or pool.name() == name
        ]
        result = {pool.name(): _pool_extract_infos(pool) for pool in pools}
    except libvirt.libvirtError as err:
        log.debug("Silenced libvirt error: %s", str(err))
    finally:
        conn.close()
    return result


def pool_get_xml(name, **kwargs):
    """
    Return the XML definition of a virtual storage pool

    :param name: libvirt storage pool name
    :param connection: libvirt connection URI, overriding defaults
    :param username: username to connect with, overriding defaults
    :param password: password to connect with, overriding defaults

    .. versionadded:: 3000

    CLI Example:

    .. code-block:: bash

        salt '*' virt.pool_get_xml default
    """
    conn = __get_conn(**kwargs)
    try:
        return conn.storagePoolLookupByName(name).XMLDesc()
    finally:
        conn.close()


def pool_start(name, **kwargs):
    """
    Start a defined libvirt storage pool.

    :param name: libvirt storage pool name
    :param connection: libvirt connection URI, overriding defaults
    :param username: username to connect with, overriding defaults
    :param password: password to connect with, overriding defaults

    .. versionadded:: 2019.2.0

    CLI Example:

    .. code-block:: bash

        salt '*' virt.pool_start default
    """
    conn = __get_conn(**kwargs)
    try:
        pool = conn.storagePoolLookupByName(name)
        return not bool(pool.create())
    finally:
        conn.close()


def pool_build(name, **kwargs):
    """
    Build a defined libvirt storage pool.

    :param name: libvirt storage pool name
    :param connection: libvirt connection URI, overriding defaults
    :param username: username to connect with, overriding defaults
    :param password: password to connect with, overriding defaults

    .. versionadded:: 2019.2.0

    CLI Example:

    .. code-block:: bash

        salt '*' virt.pool_build default
    """
    conn = __get_conn(**kwargs)
    try:
        pool = conn.storagePoolLookupByName(name)
        return not bool(pool.build())
    finally:
        conn.close()


def pool_stop(name, **kwargs):
    """
    Stop a defined libvirt storage pool.

    :param name: libvirt storage pool name
    :param connection: libvirt connection URI, overriding defaults
    :param username: username to connect with, overriding defaults
    :param password: password to connect with, overriding defaults

    .. versionadded:: 2019.2.0

    CLI Example:

    .. code-block:: bash

        salt '*' virt.pool_stop default
    """
    conn = __get_conn(**kwargs)
    try:
        pool = conn.storagePoolLookupByName(name)
        return not bool(pool.destroy())
    finally:
        conn.close()


def pool_undefine(name, **kwargs):
    """
    Remove a defined libvirt storage pool. The pool needs to be stopped before calling.

    :param name: libvirt storage pool name
    :param connection: libvirt connection URI, overriding defaults
    :param username: username to connect with, overriding defaults
    :param password: password to connect with, overriding defaults

    .. versionadded:: 2019.2.0

    CLI Example:

    .. code-block:: bash

        salt '*' virt.pool_undefine default
    """
    conn = __get_conn(**kwargs)
    try:
        pool = conn.storagePoolLookupByName(name)
        desc = ElementTree.fromstring(pool.XMLDesc())

        # Is there a secret that we generated and would need to be removed?
        # Don't remove the other secrets
        auth_node = desc.find("source/auth")
        if auth_node is not None:
            auth_types = {
                "ceph": libvirt.VIR_SECRET_USAGE_TYPE_CEPH,
                "iscsi": libvirt.VIR_SECRET_USAGE_TYPE_ISCSI,
            }
            secret_type = auth_types[auth_node.get("type")]
            secret_usage = auth_node.find("secret").get("usage")
            if secret_type and "pool_{}".format(name) == secret_usage:
                secret = conn.secretLookupByUsage(secret_type, secret_usage)
                secret.undefine()

        return not bool(pool.undefine())
    finally:
        conn.close()


def pool_delete(name, **kwargs):
    """
    Delete the resources of a defined libvirt storage pool.

    :param name: libvirt storage pool name
    :param connection: libvirt connection URI, overriding defaults
    :param username: username to connect with, overriding defaults
    :param password: password to connect with, overriding defaults

    .. versionadded:: 2019.2.0

    CLI Example:

    .. code-block:: bash

        salt '*' virt.pool_delete default
    """
    conn = __get_conn(**kwargs)
    try:
        pool = conn.storagePoolLookupByName(name)
        return not bool(pool.delete(libvirt.VIR_STORAGE_POOL_DELETE_NORMAL))
    finally:
        conn.close()


def pool_refresh(name, **kwargs):
    """
    Refresh a defined libvirt storage pool.

    :param name: libvirt storage pool name
    :param connection: libvirt connection URI, overriding defaults
    :param username: username to connect with, overriding defaults
    :param password: password to connect with, overriding defaults

    .. versionadded:: 2019.2.0

    CLI Example:

    .. code-block:: bash

        salt '*' virt.pool_refresh default
    """
    conn = __get_conn(**kwargs)
    try:
        pool = conn.storagePoolLookupByName(name)
        return not bool(pool.refresh())
    finally:
        conn.close()


def pool_set_autostart(name, state="on", **kwargs):
    """
    Set the autostart flag on a libvirt storage pool so that the storage pool
    will start with the host system on reboot.

    :param name: libvirt storage pool name
    :param state: 'on' to auto start the pool, anything else to mark the
                  pool not to be started when the host boots
    :param connection: libvirt connection URI, overriding defaults
    :param username: username to connect with, overriding defaults
    :param password: password to connect with, overriding defaults

    .. versionadded:: 2019.2.0

    CLI Example:

    .. code-block:: bash

        salt "*" virt.pool_set_autostart <pool> <on | off>
    """
    conn = __get_conn(**kwargs)
    try:
        pool = conn.storagePoolLookupByName(name)
        return not bool(pool.setAutostart(1 if state == "on" else 0))
    finally:
        conn.close()


def pool_list_volumes(name, **kwargs):
    """
    List the volumes contained in a defined libvirt storage pool.

    :param name: libvirt storage pool name
    :param connection: libvirt connection URI, overriding defaults
    :param username: username to connect with, overriding defaults
    :param password: password to connect with, overriding defaults

    .. versionadded:: 2019.2.0

    CLI Example:

    .. code-block:: bash

        salt "*" virt.pool_list_volumes <pool>
    """
    conn = __get_conn(**kwargs)
    try:
        pool = conn.storagePoolLookupByName(name)
        return pool.listVolumes()
    finally:
        conn.close()


def _get_storage_vol(conn, pool, vol):
    """
    Helper function getting a storage volume. Will throw a libvirtError
    if the pool or the volume couldn't be found.

    :param conn: libvirt connection object to use
    :param pool: pool name
    :param vol: volume name
    """
    pool_obj = conn.storagePoolLookupByName(pool)
    return pool_obj.storageVolLookupByName(vol)


def _is_valid_volume(vol):
    """
    Checks whether a volume is valid for further use since those may have disappeared since
    the last pool refresh.
    """
    try:
        # Getting info on an invalid volume raises error and libvirt logs an error
        def discarder(ctxt, error):  # pylint: disable=unused-argument
            log.debug("Ignore libvirt error: %s", error[2])

        # Disable the libvirt error logging
        libvirt.registerErrorHandler(discarder, None)
        vol.info()
        # Reenable the libvirt error logging
        libvirt.registerErrorHandler(None, None)
        return True
    except libvirt.libvirtError as err:
        return False


def _get_all_volumes_paths(conn):
    """
    Extract the path, name, pool name and backing stores path of all volumes.

    :param conn: libvirt connection to use
    """
    pools = [
        pool
        for pool in conn.listAllStoragePools()
        if pool.info()[0] == libvirt.VIR_STORAGE_POOL_RUNNING
    ]
    volumes = {}
    for pool in pools:
        pool_volumes = {
            volume.path(): {
                "pool": pool.name(),
                "name": volume.name(),
                "backing_stores": [
                    path.text
                    for path in ElementTree.fromstring(volume.XMLDesc()).findall(
                        ".//backingStore/path"
                    )
                ],
            }
            for volume in pool.listAllVolumes()
            if _is_valid_volume(volume)
        }
        volumes.update(pool_volumes)
    return volumes


def volume_infos(pool=None, volume=None, **kwargs):
    """
    Provide details on a storage volume. If no volume name is provided, the infos
    all the volumes contained in the pool are provided. If no pool is provided,
    the infos of the volumes of all pools are output.

    :param pool: libvirt storage pool name (default: ``None``)
    :param volume: name of the volume to get infos from (default: ``None``)
    :param connection: libvirt connection URI, overriding defaults
    :param username: username to connect with, overriding defaults
    :param password: password to connect with, overriding defaults

    .. versionadded:: 3000

    CLI Example:

    .. code-block:: bash

        salt "*" virt.volume_infos <pool> <volume>
    """
    result = {}
    conn = __get_conn(**kwargs)
    try:
        backing_stores = _get_all_volumes_paths(conn)
        try:
            domains = _get_domain(conn)
            domains_list = domains if isinstance(domains, list) else [domains]
        except CommandExecutionError:
            # Having no VM is not an error here.
            domains_list = []
        disks = {
            domain.name(): {
                node.get("file")
                for node in ElementTree.fromstring(domain.XMLDesc(0)).findall(
                    ".//disk/source/[@file]"
                )
            }
            for domain in domains_list
        }

        def _volume_extract_infos(vol):
            """
            Format the volume info dictionary

            :param vol: the libvirt storage volume object.
            """
            types = ["file", "block", "dir", "network", "netdir", "ploop"]
            infos = vol.info()

            vol_xml = ElementTree.fromstring(vol.XMLDesc())
            backing_store_path = vol_xml.find("./backingStore/path")
            backing_store_format = vol_xml.find("./backingStore/format")
            backing_store = None
            if backing_store_path is not None:
                backing_store = {
                    "path": backing_store_path.text,
                    "format": backing_store_format.get("type")
                    if backing_store_format is not None
                    else None,
                }

            format_node = vol_xml.find("./target/format")

            # If we have a path, check its use.
            used_by = []
            if vol.path():
                as_backing_store = {
                    path
                    for (path, volume) in backing_stores.items()
                    if vol.path() in volume.get("backing_stores")
                }
                used_by = [
                    vm_name
                    for (vm_name, vm_disks) in disks.items()
                    if vm_disks & as_backing_store or vol.path() in vm_disks
                ]

            return {
                "type": types[infos[0]] if infos[0] < len(types) else "unknown",
                "key": vol.key(),
                "path": vol.path(),
                "capacity": infos[1],
                "allocation": infos[2],
                "used_by": used_by,
                "backing_store": backing_store,
                "format": format_node.get("type") if format_node is not None else None,
            }

        pools = [
            obj
            for obj in conn.listAllStoragePools()
            if (pool is None or obj.name() == pool)
            and obj.info()[0] == libvirt.VIR_STORAGE_POOL_RUNNING
        ]
        vols = {
            pool_obj.name(): {
                vol.name(): _volume_extract_infos(vol)
                for vol in pool_obj.listAllVolumes()
                if (volume is None or vol.name() == volume) and _is_valid_volume(vol)
            }
            for pool_obj in pools
        }
        return {pool_name: volumes for (pool_name, volumes) in vols.items() if volumes}
    except libvirt.libvirtError as err:
        log.debug("Silenced libvirt error: %s", str(err))
    finally:
        conn.close()
    return result


def volume_delete(pool, volume, **kwargs):
    """
    Delete a libvirt managed volume.

    :param pool: libvirt storage pool name
    :param volume: name of the volume to delete
    :param connection: libvirt connection URI, overriding defaults
    :param username: username to connect with, overriding defaults
    :param password: password to connect with, overriding defaults

    .. versionadded:: 3000

    CLI Example:

    .. code-block:: bash

        salt "*" virt.volume_delete <pool> <volume>
    """
    conn = __get_conn(**kwargs)
    try:
        vol = _get_storage_vol(conn, pool, volume)
        return not bool(vol.delete())
    finally:
        conn.close()


def volume_define(
    pool,
    name,
    size,
    allocation=0,
    format=None,
    type=None,
    permissions=None,
    backing_store=None,
    nocow=False,
    **kwargs
):
    """
    Create libvirt volume.

    :param pool: name of the pool to create the volume in
    :param name: name of the volume to define
    :param size: capacity of the volume to define in MiB
    :param allocation: allocated size of the volume in MiB. Defaults to 0.
    :param format:
        volume format. The allowed values are depending on the pool type.
        Check the virt.pool_capabilities output for the possible values and the default.
    :param type:
        type of the volume. One of file, block, dir, network, netdiri, ploop or None.
        By default, the type is guessed by libvirt from the pool type.
    :param permissions:
        Permissions to set on the target folder. This is mostly used for filesystem-based
        pool types. See :ref:`pool-define-permissions` for more details on this structure.
    :param backing_store:
        dictionary describing a backing file for the volume. It must contain a ``path``
        property pointing to the base volume and a ``format`` property defining the format
        of the base volume.

        The base volume format will not be guessed for security reasons and is thus mandatory.
    :param nocow: disable COW for the volume.
    :param connection: libvirt connection URI, overriding defaults
    :param username: username to connect with, overriding defaults
    :param password: password to connect with, overriding defaults

    .. rubric:: CLI Example:

    Volume on ESX:

    .. code-block:: bash

        salt '*' virt.volume_define "[local-storage]" myvm/myvm.vmdk vmdk 8192

    QCow2 volume with backing file:

    .. code-block:: bash

        salt '*' virt.volume_define default myvm.qcow2 qcow2 8192 \
                            permissions="{'mode': '0775', 'owner': '123', 'group': '345'"}" \
                            backing_store="{'path': '/path/to/base.img', 'format': 'raw'}" \
                            nocow=True

    .. versionadded:: 3001
    """
    ret = False
    try:
        conn = __get_conn(**kwargs)
        pool_obj = conn.storagePoolLookupByName(pool)
        pool_type = ElementTree.fromstring(pool_obj.XMLDesc()).get("type")
        new_allocation = allocation
        if pool_type == "logical" and size != allocation:
            new_allocation = size
        xml = _gen_vol_xml(
            name,
            size,
            format=format,
            allocation=new_allocation,
            type=type,
            permissions=permissions,
            backing_store=backing_store,
            nocow=nocow,
        )
        ret = _define_vol_xml_str(conn, xml, pool=pool)
    except libvirt.libvirtError as err:
        raise CommandExecutionError(err.get_error_message())
    finally:
        conn.close()
    return ret


def _volume_upload(conn, pool, volume, file, offset=0, length=0, sparse=False):
    """
    Function performing the heavy duty for volume_upload but using an already
    opened libvirt connection.
    """

    def handler(stream, nbytes, opaque):
        return os.read(opaque, nbytes)

    def holeHandler(stream, opaque):
        """
        Taken from the sparsestream.py libvirt-python example.
        """
        fd = opaque
        cur = os.lseek(fd, 0, os.SEEK_CUR)

        try:
            data = os.lseek(fd, cur, os.SEEK_DATA)
        except OSError as e:
            if e.errno != 6:
                raise e
            else:
                data = -1
        if data < 0:
            inData = False
            eof = os.lseek(fd, 0, os.SEEK_END)
            if eof < cur:
                raise RuntimeError("Current position in file after EOF: {}".format(cur))
            sectionLen = eof - cur
        else:
            if data > cur:
                inData = False
                sectionLen = data - cur
            else:
                inData = True

                hole = os.lseek(fd, data, os.SEEK_HOLE)
                if hole < 0:
                    raise RuntimeError("No trailing hole")

                if hole == data:
                    raise RuntimeError("Impossible happened")
                else:
                    sectionLen = hole - data
        os.lseek(fd, cur, os.SEEK_SET)
        return [inData, sectionLen]

    def skipHandler(stream, length, opaque):
        return os.lseek(opaque, length, os.SEEK_CUR)

    stream = None
    fd = None
    ret = False
    try:
        pool_obj = conn.storagePoolLookupByName(pool)
        vol_obj = pool_obj.storageVolLookupByName(volume)

        stream = conn.newStream()
        fd = os.open(file, os.O_RDONLY)
        vol_obj.upload(
            stream,
            offset,
            length,
            libvirt.VIR_STORAGE_VOL_UPLOAD_SPARSE_STREAM if sparse else 0,
        )
        if sparse:
            stream.sparseSendAll(handler, holeHandler, skipHandler, fd)
        else:
            stream.sendAll(handler, fd)
        ret = True
    except libvirt.libvirtError as err:
        raise CommandExecutionError(err.get_error_message())
    finally:
        if fd:
            try:
                os.close(fd)
            except OSError as err:
                if stream:
                    stream.abort()
                if ret:
                    raise CommandExecutionError(
                        "Failed to close file: {}".format(err.strerror)
                    )
        if stream:
            try:
                stream.finish()
            except libvirt.libvirtError as err:
                if ret:
                    raise CommandExecutionError(
                        "Failed to finish stream: {}".format(err.get_error_message())
                    )
    return ret


def volume_upload(pool, volume, file, offset=0, length=0, sparse=False, **kwargs):
    """
    Create libvirt volume.

    :param pool: name of the pool to create the volume in
    :param name: name of the volume to define
    :param file: the file to upload to the volume
    :param offset: where to start writing the data in the volume
    :param length: amount of bytes to transfer to the volume
    :param sparse: set to True to preserve data sparsiness.
    :param connection: libvirt connection URI, overriding defaults
    :param username: username to connect with, overriding defaults
    :param password: password to connect with, overriding defaults

    .. rubric:: CLI Example:

    .. code-block:: bash

        salt '*' virt.volume_upload default myvm.qcow2 /path/to/disk.qcow2

    .. versionadded:: 3001
    """
    conn = __get_conn(**kwargs)

    ret = False
    try:
        ret = _volume_upload(
            conn, pool, volume, file, offset=offset, length=length, sparse=sparse
        )
    finally:
        conn.close()
    return ret
