"""
Control virtual machines via Salt
"""


import logging
import os.path

import salt.client
import salt.key
import salt.utils.cloud
import salt.utils.files
import salt.utils.stringutils
from salt.exceptions import SaltClientError

log = logging.getLogger(__name__)


def _determine_host(data, omit=""):
    """
    Determine what the most resource free host is based on the given data
    """
    # This is just checking for the host with the most free ram, this needs
    # to be much more complicated.
    host = ""
    bestmem = 0
    for hv_, comps in data.items():
        if hv_ == omit:
            continue
        if not isinstance(comps, dict):
            continue
        if comps.get("freemem", 0) > bestmem:
            bestmem = comps["freemem"]
            host = hv_
    return host


def _find_vm(name, data, quiet=False):
    """
    Scan the query data for the named VM
    """
    for hv_ in data:
        # Check if data is a dict, and not '"virt.full_info" is not available.'
        if not isinstance(data[hv_], dict):
            continue
        if name in data[hv_].get("vm_info", {}):
            ret = {hv_: {name: data[hv_]["vm_info"][name]}}
            if not quiet:
                __jid_event__.fire_event(
                    {"data": ret, "outputter": "nested"}, "progress"
                )
            return ret
    return {}


def query(host=None, quiet=False):
    """
    Query the virtual machines. When called without options all hosts
    are detected and a full query is returned. A single host can be
    passed in to specify an individual host to query.
    """
    if quiet:
        log.warning("'quiet' is deprecated. Please migrate to --quiet")
    ret = {}
    client = salt.client.get_local_client(__opts__["conf_file"])
    try:
        for info in client.cmd_iter(
            "virtual:physical", "virt.full_info", tgt_type="grain"
        ):
            if not info:
                continue
            if not isinstance(info, dict):
                continue
            chunk = {}
            id_ = next(iter(info.keys()))
            if host:
                if host != id_:
                    continue
            if not isinstance(info[id_], dict):
                continue
            if "ret" not in info[id_]:
                continue
            if not isinstance(info[id_]["ret"], dict):
                continue
            chunk[id_] = info[id_]["ret"]
            ret.update(chunk)
            if not quiet:
                __jid_event__.fire_event(
                    {"data": chunk, "outputter": "virt_query"}, "progress"
                )
    except SaltClientError as client_error:
        print(client_error)
    return ret


def list(host=None, quiet=False, hyper=None):  # pylint: disable=redefined-builtin
    """
    List the virtual machines on each host, this is a simplified query,
    showing only the virtual machine names belonging to each host.
    A single host can be passed in to specify an individual host
    to list.
    """
    if quiet:
        log.warning("'quiet' is deprecated. Please migrate to --quiet")
    ret = {}
    client = salt.client.get_local_client(__opts__["conf_file"])
    for info in client.cmd_iter("virtual:physical", "virt.vm_info", tgt_type="grain"):
        if not info:
            continue
        if not isinstance(info, dict):
            continue
        chunk = {}
        id_ = next(iter(info.keys()))
        if host:
            if host != id_:
                continue
        if not isinstance(info[id_], dict):
            continue
        if "ret" not in info[id_]:
            continue
        if not isinstance(info[id_]["ret"], dict):
            continue
        data = {}
        for key, val in info[id_]["ret"].items():
            if val["state"] in data:
                data[val["state"]].append(key)
            else:
                data[val["state"]] = [key]
        chunk[id_] = data
        ret.update(chunk)
        if not quiet:
            __jid_event__.fire_event({"data": chunk, "outputter": "nested"}, "progress")

    return ret


def next_host():
    """
    Return the host to use for the next autodeployed VM. This queries
    the available host and executes some math the determine the most
    "available" next host.
    """
    host = _determine_host(query(quiet=True))
    print(host)
    return host


def host_info(host=None):
    """
    Return information about the host connected to this master
    """
    data = query(host, quiet=True)
    for id_ in data:
        if "vm_info" in data[id_]:
            data[id_].pop("vm_info")
    __jid_event__.fire_event({"data": data, "outputter": "nested"}, "progress")
    return data


def init(
    name,
    cpu,
    mem,
    image,
    hypervisor="kvm",
    host=None,
    seed=True,
    nic="default",
    install=True,
    start=True,
    disk="default",
    saltenv="base",
    enable_vnc=False,
    seed_cmd="seed.apply",
    enable_qcow=False,
    serial_type="None",
):
    """
    This routine is used to create a new virtual machine. This routines takes
    a number of options to determine what the newly created virtual machine
    will look like.

    name
        The mandatory name of the new virtual machine. The name option is
        also the minion id, all minions must have an id.

    cpu
        The number of cpus to allocate to this new virtual machine.

    mem
        The amount of memory to allocate to this virtual machine. The number
        is interpreted in megabytes.

    image
        The network location of the virtual machine image, commonly a location
        on the salt fileserver, but http, https and ftp can also be used.

    hypervisor
        The hypervisor to use for the new virtual machine. Default is `kvm`.

    host
        The host to use for the new virtual machine, if this is omitted
        Salt will automatically detect what host to use.

    seed
        Set to `False` to prevent Salt from seeding the new virtual machine.

    nic
        The nic profile to use, defaults to the "default" nic profile which
        assumes a single network interface per VM associated with the "br0"
        bridge on the master.

    install
        Set to False to prevent Salt from installing a minion on the new VM
        before it spins up.

    disk
        The disk profile to use

    saltenv
        The Salt environment to use

    enable_vnc
        Whether a VNC screen is attached to resulting VM. Default is `False`.

    seed_cmd
        If seed is `True`, use this execution module function to seed new VM.
        Default is `seed.apply`.

    enable_qcow
        Clone disk image as a copy-on-write qcow2 image, using downloaded
        `image` as backing file.

    serial_type
        Enable serial console. Set to 'pty' for serial console or 'tcp' for
        telnet.
        Default is 'None'
    """
    __jid_event__.fire_event({"message": "Searching for hosts"}, "progress")
    data = query(host, quiet=True)
    # Check if the name is already deployed
    for node in data:
        if "vm_info" in data[node]:
            if name in data[node]["vm_info"]:
                __jid_event__.fire_event(
                    {"message": "Virtual machine {} is already deployed".format(name)},
                    "progress",
                )
                return "fail"

    if host is None:
        host = _determine_host(data)

    if host not in data or not host:
        __jid_event__.fire_event(
            {"message": "Host {} was not found".format(host)}, "progress"
        )
        return "fail"

    pub_key = None
    priv_key = None
    if seed:
        __jid_event__.fire_event({"message": "Minion will be preseeded"}, "progress")
        priv_key, pub_key = salt.utils.cloud.gen_keys()
        accepted_key = os.path.join(__opts__["pki_dir"], "minions", name)
        with salt.utils.files.fopen(accepted_key, "w") as fp_:
            fp_.write(salt.utils.stringutils.to_str(pub_key))

    client = salt.client.get_local_client(__opts__["conf_file"])

    __jid_event__.fire_event(
        {"message": "Creating VM {} on host {}".format(name, host)}, "progress"
    )
    try:
        cmd_ret = client.cmd_iter(
            host,
            "virt.init",
            [name, cpu, mem],
            timeout=600,
            kwarg={
                "image": image,
                "nic": nic,
                "hypervisor": hypervisor,
                "start": start,
                "disk": disk,
                "saltenv": saltenv,
                "seed": seed,
                "install": install,
                "pub_key": pub_key,
                "priv_key": priv_key,
                "seed_cmd": seed_cmd,
                "enable_vnc": enable_vnc,
                "enable_qcow": enable_qcow,
                "serial_type": serial_type,
            },
        )
    except SaltClientError as client_error:
        # Fall through to ret error handling below
        print(client_error)

    ret = next(cmd_ret)
    if not ret:
        __jid_event__.fire_event(
            {"message": "VM {} was not initialized.".format(name)}, "progress"
        )
        return "fail"
    for minion_id in ret:
        if ret[minion_id]["ret"] is False:
            print(
                "VM {} initialization failed. Returned error: {}".format(
                    name, ret[minion_id]["ret"]
                )
            )
            return "fail"

    __jid_event__.fire_event(
        {"message": "VM {} initialized on host {}".format(name, host)}, "progress"
    )
    return "good"


def vm_info(name, quiet=False):
    """
    Return the information on the named VM
    """
    data = query(quiet=True)
    return _find_vm(name, data, quiet)


def reset(name):
    """
    Force power down and restart an existing VM
    """
    ret = {}
    client = salt.client.get_local_client(__opts__["conf_file"])
    data = vm_info(name, quiet=True)
    if not data:
        __jid_event__.fire_event(
            {"message": "Failed to find VM {} to reset".format(name)}, "progress"
        )
        return "fail"
    host = next(iter(data.keys()))
    try:
        cmd_ret = client.cmd_iter(host, "virt.reset", [name], timeout=600)
        for comp in cmd_ret:
            ret.update(comp)
        __jid_event__.fire_event({"message": "Reset VM {}".format(name)}, "progress")
    except SaltClientError as client_error:
        print(client_error)
    return ret


def start(name):
    """
    Start a named virtual machine
    """
    ret = {}
    client = salt.client.get_local_client(__opts__["conf_file"])
    data = vm_info(name, quiet=True)
    if not data:
        __jid_event__.fire_event(
            {"message": "Failed to find VM {} to start".format(name)}, "progress"
        )
        return "fail"
    host = next(iter(data.keys()))
    if data[host][name]["state"] == "running":
        print("VM {} is already running".format(name))
        return "bad state"
    try:
        cmd_ret = client.cmd_iter(host, "virt.start", [name], timeout=600)
    except SaltClientError as client_error:
        return "Virtual machine {} not started: {}".format(name, client_error)
    for comp in cmd_ret:
        ret.update(comp)
    __jid_event__.fire_event({"message": "Started VM {}".format(name)}, "progress")
    return "good"


def force_off(name):
    """
    Force power down the named virtual machine
    """
    ret = {}
    client = salt.client.get_local_client(__opts__["conf_file"])
    data = vm_info(name, quiet=True)
    if not data:
        print("Failed to find VM {} to destroy".format(name))
        return "fail"
    host = next(iter(data.keys()))
    if data[host][name]["state"] == "shutdown":
        print("VM {} is already shutdown".format(name))
        return "bad state"
    try:
        cmd_ret = client.cmd_iter(host, "virt.stop", [name], timeout=600)
    except SaltClientError as client_error:
        return "Virtual machine {} could not be forced off: {}".format(
            name, client_error
        )
    for comp in cmd_ret:
        ret.update(comp)
    __jid_event__.fire_event({"message": "Powered off VM {}".format(name)}, "progress")
    return "good"


def purge(name, delete_key=True):
    """
    Destroy the named VM
    """
    ret = {}
    client = salt.client.get_local_client(__opts__["conf_file"])
    data = vm_info(name, quiet=True)
    if not data:
        __jid_event__.fire_event(
            {"error": "Failed to find VM {} to purge".format(name)}, "progress"
        )
        return "fail"
    host = next(iter(data.keys()))
    try:
        cmd_ret = client.cmd_iter(host, "virt.purge", [name, True], timeout=600)
    except SaltClientError as client_error:
        return "Virtual machine {} could not be purged: {}".format(name, client_error)

    for comp in cmd_ret:
        ret.update(comp)

    if delete_key:
        log.debug("Deleting key %s", name)
        skey = salt.key.Key(__opts__)
        skey.delete_key(name)
    __jid_event__.fire_event({"message": "Purged VM {}".format(name)}, "progress")
    return "good"


def pause(name):
    """
    Pause the named VM
    """
    ret = {}
    client = salt.client.get_local_client(__opts__["conf_file"])

    data = vm_info(name, quiet=True)
    if not data:
        __jid_event__.fire_event(
            {"error": "Failed to find VM {} to pause".format(name)}, "progress"
        )
        return "fail"
    host = next(iter(data.keys()))
    if data[host][name]["state"] == "paused":
        __jid_event__.fire_event(
            {"error": "VM {} is already paused".format(name)}, "progress"
        )
        return "bad state"
    try:
        cmd_ret = client.cmd_iter(host, "virt.pause", [name], timeout=600)
    except SaltClientError as client_error:
        return "Virtual machine {} could not be pasued: {}".format(name, client_error)
    for comp in cmd_ret:
        ret.update(comp)
    __jid_event__.fire_event({"message": "Paused VM {}".format(name)}, "progress")
    return "good"


def resume(name):
    """
    Resume a paused VM
    """
    ret = {}
    client = salt.client.get_local_client(__opts__["conf_file"])
    data = vm_info(name, quiet=True)
    if not data:
        __jid_event__.fire_event(
            {"error": "Failed to find VM {} to pause".format(name)}, "progress"
        )
        return "not found"
    host = next(iter(data.keys()))
    if data[host][name]["state"] != "paused":
        __jid_event__.fire_event(
            {"error": "VM {} is not paused".format(name)}, "progress"
        )
        return "bad state"
    try:
        cmd_ret = client.cmd_iter(host, "virt.resume", [name], timeout=600)
    except SaltClientError as client_error:
        return "Virtual machine {} could not be resumed: {}".format(name, client_error)
    for comp in cmd_ret:
        ret.update(comp)
    __jid_event__.fire_event({"message": "Resumed VM {}".format(name)}, "progress")
    return "good"


def migrate(name, target=""):
    """
    Migrate a VM from one host to another. This routine will just start
    the migration and display information on how to look up the progress.
    """
    client = salt.client.get_local_client(__opts__["conf_file"])
    data = query(quiet=True)
    origin_data = _find_vm(name, data, quiet=True)
    try:
        origin_host = next(iter(origin_data))
    except StopIteration:
        __jid_event__.fire_event(
            {"error": "Named VM {} was not found to migrate".format(name)}, "progress"
        )
        return ""
    disks = origin_data[origin_host][name]["disks"]
    if not origin_data:
        __jid_event__.fire_event(
            {"error": "Named VM {} was not found to migrate".format(name)}, "progress"
        )
        return ""
    if not target:
        target = _determine_host(data, origin_host)
    if target not in data:
        __jid_event__.fire_event(
            {"error": "Target host {} not found".format(origin_data)}, "progress"
        )
        return ""
    try:
        client.cmd(target, "virt.seed_non_shared_migrate", [disks, True])
        jid = client.cmd_async(origin_host, "virt.migrate_non_shared", [name, target])
    except SaltClientError as client_error:
        return "Virtual machine {} could not be migrated: {}".format(name, client_error)

    msg = (
        "The migration of virtual machine {} to host {} has begun, "
        "and can be tracked via jid {}. The ``salt-run virt.query`` "
        "runner can also be used, the target VM will be shown as paused "
        "until the migration is complete."
    ).format(name, target, jid)
    __jid_event__.fire_event({"message": msg}, "progress")
