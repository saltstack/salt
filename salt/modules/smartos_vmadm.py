"""
Module for running vmadm command on SmartOS
"""

import logging
import os

import salt.utils.args
import salt.utils.files
import salt.utils.json
import salt.utils.path
import salt.utils.platform
import salt.utils.stringutils
from salt.utils.odict import OrderedDict

try:
    from shlex import quote as _quote_args  # pylint: disable=E0611
except ImportError:
    from pipes import quote as _quote_args


log = logging.getLogger(__name__)

# Function aliases
__func_alias__ = {"list_vms": "list"}

# Define the module's virtual name
__virtualname__ = "vmadm"


def __virtual__():
    """
    Provides vmadm on SmartOS
    """
    if (
        salt.utils.platform.is_smartos_globalzone()
        and salt.utils.path.which("vmadm")
        and salt.utils.path.which("zfs")
    ):
        return __virtualname__
    return (
        False,
        "{} module can only be loaded on SmartOS compute nodes".format(__virtualname__),
    )


def _exit_status(retcode):
    """
    Translate exit status of vmadm
    """
    ret = {0: "Successful completion.", 1: "An error occurred.", 2: "Usage error."}[
        retcode
    ]
    return ret


def _create_update_from_file(mode="create", uuid=None, path=None):
    """
    Create vm from file
    """
    ret = {}
    if not os.path.isfile(path) or path is None:
        ret["Error"] = "File ({}) does not exists!".format(path)
        return ret
    # vmadm validate create|update [-f <filename>]
    cmd = "vmadm validate {mode} {brand} -f {path}".format(
        mode=mode, brand=get(uuid)["brand"] if uuid is not None else "", path=path
    )
    res = __salt__["cmd.run_all"](cmd)
    retcode = res["retcode"]
    if retcode != 0:
        ret["Error"] = _exit_status(retcode)
        if "stderr" in res:
            if res["stderr"][0] == "{":
                ret["Error"] = salt.utils.json.loads(res["stderr"])
            else:
                ret["Error"] = res["stderr"]
        return ret
    # vmadm create|update [-f <filename>]
    cmd = "vmadm {mode} {uuid} -f {path}".format(
        mode=mode, uuid=uuid if uuid is not None else "", path=path
    )
    res = __salt__["cmd.run_all"](cmd)
    retcode = res["retcode"]
    if retcode != 0:
        ret["Error"] = _exit_status(retcode)
        if "stderr" in res:
            if res["stderr"][0] == "{":
                ret["Error"] = salt.utils.json.loads(res["stderr"])
            else:
                ret["Error"] = res["stderr"]
        return ret
    else:
        if res["stderr"].startswith("Successfully created VM"):
            return res["stderr"][24:]
    return True


def _create_update_from_cfg(mode="create", uuid=None, vmcfg=None):
    """
    Create vm from configuration
    """
    ret = {}

    # write json file
    vmadm_json_file = __salt__["temp.file"](prefix="vmadm-")
    with salt.utils.files.fopen(vmadm_json_file, "w") as vmadm_json:
        salt.utils.json.dump(vmcfg, vmadm_json)

    # vmadm validate create|update [-f <filename>]
    cmd = "vmadm validate {mode} {brand} -f {vmadm_json_file}".format(
        mode=mode,
        brand=get(uuid)["brand"] if uuid is not None else "",
        vmadm_json_file=vmadm_json_file,
    )
    res = __salt__["cmd.run_all"](cmd, python_shell=True)
    retcode = res["retcode"]
    if retcode != 0:
        ret["Error"] = _exit_status(retcode)
        if "stderr" in res:
            if res["stderr"][0] == "{":
                ret["Error"] = salt.utils.json.loads(res["stderr"])
            else:
                ret["Error"] = res["stderr"]
        return ret
    # vmadm create|update [-f <filename>]
    cmd = "vmadm {mode} {uuid} -f {vmadm_json_file}".format(
        mode=mode,
        uuid=uuid if uuid is not None else "",
        vmadm_json_file=vmadm_json_file,
    )
    res = __salt__["cmd.run_all"](cmd, python_shell=True)
    retcode = res["retcode"]
    if retcode != 0:
        ret["Error"] = _exit_status(retcode)
        if "stderr" in res:
            if res["stderr"][0] == "{":
                ret["Error"] = salt.utils.json.loads(res["stderr"])
            else:
                ret["Error"] = res["stderr"]
        return ret
    else:
        # cleanup json file (only when successful to help troubleshooting)
        salt.utils.files.safe_rm(vmadm_json_file)

        # return uuid
        if res["stderr"].startswith("Successfully created VM"):
            return res["stderr"][24:]

    return True


def start(vm, options=None, key="uuid"):
    """
    Start a vm

    vm : string
        vm to be started
    options : string
        optional additional options
    key : string [uuid|alias|hostname]
        value type of 'vm' parameter

    CLI Example:

    .. code-block:: bash

        salt '*' vmadm.start 186da9ab-7392-4f55-91a5-b8f1fe770543
        salt '*' vmadm.start 186da9ab-7392-4f55-91a5-b8f1fe770543 'order=c,once=d cdrom=/path/to/image.iso,ide'
        salt '*' vmadm.start vm=nacl key=alias
        salt '*' vmadm.start vm=nina.example.org key=hostname
    """
    ret = {}
    if key not in ["uuid", "alias", "hostname"]:
        ret["Error"] = "Key must be either uuid, alias or hostname"
        return ret
    vm = lookup("{}={}".format(key, vm), one=True)
    if "Error" in vm:
        return vm
    # vmadm start <uuid> [option=value ...]
    cmd = "vmadm start {uuid} {options}".format(
        uuid=vm, options=options if options else ""
    )
    res = __salt__["cmd.run_all"](cmd)
    retcode = res["retcode"]
    if retcode != 0:
        ret["Error"] = res["stderr"] if "stderr" in res else _exit_status(retcode)
        return ret
    return True


def stop(vm, force=False, key="uuid"):
    """
    Stop a vm

    vm : string
        vm to be stopped
    force : boolean
        force stop of vm if true
    key : string [uuid|alias|hostname]
        value type of 'vm' parameter

    CLI Example:

    .. code-block:: bash

        salt '*' vmadm.stop 186da9ab-7392-4f55-91a5-b8f1fe770543
        salt '*' vmadm.stop 186da9ab-7392-4f55-91a5-b8f1fe770543 True
        salt '*' vmadm.stop vm=nacl key=alias
        salt '*' vmadm.stop vm=nina.example.org key=hostname
    """
    ret = {}
    if key not in ["uuid", "alias", "hostname"]:
        ret["Error"] = "Key must be either uuid, alias or hostname"
        return ret
    vm = lookup("{}={}".format(key, vm), one=True)
    if "Error" in vm:
        return vm
    # vmadm stop <uuid> [-F]
    cmd = "vmadm stop {force} {uuid}".format(force="-F" if force else "", uuid=vm)
    res = __salt__["cmd.run_all"](cmd)
    retcode = res["retcode"]
    if retcode != 0:
        ret["Error"] = _exit_status(retcode)
        return ret
    return True


def reboot(vm, force=False, key="uuid"):
    """
    Reboot a vm

    vm : string
        vm to be rebooted
    force : boolean
        force reboot of vm if true
    key : string [uuid|alias|hostname]
        value type of 'vm' parameter

    CLI Example:

    .. code-block:: bash

        salt '*' vmadm.reboot 186da9ab-7392-4f55-91a5-b8f1fe770543
        salt '*' vmadm.reboot 186da9ab-7392-4f55-91a5-b8f1fe770543 True
        salt '*' vmadm.reboot vm=nacl key=alias
        salt '*' vmadm.reboot vm=nina.example.org key=hostname
    """
    ret = {}
    if key not in ["uuid", "alias", "hostname"]:
        ret["Error"] = "Key must be either uuid, alias or hostname"
        return ret
    vm = lookup("{}={}".format(key, vm), one=True)
    if "Error" in vm:
        return vm
    # vmadm reboot <uuid> [-F]
    cmd = "vmadm reboot {force} {uuid}".format(force="-F" if force else "", uuid=vm)
    res = __salt__["cmd.run_all"](cmd)
    retcode = res["retcode"]
    if retcode != 0:
        ret["Error"] = res["stderr"] if "stderr" in res else _exit_status(retcode)
        return ret
    return True


def list_vms(search=None, sort=None, order="uuid,type,ram,state,alias", keyed=True):
    """
    Return a list of VMs

    search : string
        vmadm filter property
    sort : string
        vmadm sort (-s) property
    order : string
        vmadm order (-o) property -- Default: uuid,type,ram,state,alias
    keyed : boolean
        specified if the output should be an array (False) or dict (True)
            For a dict the key is the first item from the order parameter.
            Note: If key is not unique last vm wins.

    CLI Example:

    .. code-block:: bash

        salt '*' vmadm.list
        salt '*' vmadm.list order=alias,ram,cpu_cap sort=-ram,-cpu_cap
        salt '*' vmadm.list search='type=KVM'
    """
    ret = {}
    # vmadm list [-p] [-H] [-o field,...] [-s field,...] [field=value ...]
    cmd = "vmadm list -p -H {order} {sort} {search}".format(
        order="-o {}".format(order) if order else "",
        sort="-s {}".format(sort) if sort else "",
        search=search if search else "",
    )
    res = __salt__["cmd.run_all"](cmd)
    retcode = res["retcode"]
    result = OrderedDict() if keyed else []
    if retcode != 0:
        ret["Error"] = res["stderr"] if "stderr" in res else _exit_status(retcode)
        return ret

    fields = order.split(",")

    for vm in res["stdout"].splitlines():
        vm_data = OrderedDict()
        vm = vm.split(":")
        if keyed:
            for field in fields:
                if fields.index(field) == 0:
                    continue
                vm_data[field.strip()] = vm[fields.index(field)].strip()
            result[vm[0]] = vm_data
        else:
            if len(vm) > 1:
                for field in fields:
                    vm_data[field.strip()] = vm[fields.index(field)].strip()
            else:
                vm_data = vm[0]
            result.append(vm_data)
    return result


def lookup(search=None, order=None, one=False):
    """
    Return a list of VMs using lookup

    search : string
        vmadm filter property
    order : string
        vmadm order (-o) property -- Default: uuid,type,ram,state,alias
    one : boolean
        return only one result (vmadm's -1)

    CLI Example:

    .. code-block:: bash

        salt '*' vmadm.lookup search='state=running'
        salt '*' vmadm.lookup search='state=running' order=uuid,alias,hostname
        salt '*' vmadm.lookup search='alias=nacl' one=True
    """
    ret = {}
    # vmadm lookup [-j|-1] [-o field,...] [field=value ...]
    cmd = "vmadm lookup {one} {order} {search}".format(
        one="-1" if one else "-j",
        order="-o {}".format(order) if order else "",
        search=search if search else "",
    )
    res = __salt__["cmd.run_all"](cmd)
    retcode = res["retcode"]
    result = []
    if retcode != 0:
        ret["Error"] = res["stderr"] if "stderr" in res else _exit_status(retcode)
        return ret

    if one:
        result = res["stdout"]
    else:
        for vm in salt.utils.json.loads(res["stdout"]):
            result.append(vm)

    return result


def sysrq(vm, action="nmi", key="uuid"):
    """
    Send non-maskable interrupt to vm or capture a screenshot

    vm : string
        vm to be targeted
    action : string
        nmi or screenshot -- Default: nmi
    key : string [uuid|alias|hostname]
        value type of 'vm' parameter

    CLI Example:

    .. code-block:: bash

        salt '*' vmadm.sysrq 186da9ab-7392-4f55-91a5-b8f1fe770543 nmi
        salt '*' vmadm.sysrq 186da9ab-7392-4f55-91a5-b8f1fe770543 screenshot
        salt '*' vmadm.sysrq nacl nmi key=alias
    """
    ret = {}
    if key not in ["uuid", "alias", "hostname"]:
        ret["Error"] = "Key must be either uuid, alias or hostname"
        return ret
    if action not in ["nmi", "screenshot"]:
        ret["Error"] = "Action must be either nmi or screenshot"
        return ret
    vm = lookup("{}={}".format(key, vm), one=True)
    if "Error" in vm:
        return vm
    # vmadm sysrq <uuid> <nmi|screenshot>
    cmd = "vmadm sysrq {uuid} {action}".format(uuid=vm, action=action)
    res = __salt__["cmd.run_all"](cmd)
    retcode = res["retcode"]
    if retcode != 0:
        ret["Error"] = res["stderr"] if "stderr" in res else _exit_status(retcode)
        return ret
    return True


def delete(vm, key="uuid"):
    """
    Delete a vm

    vm : string
        vm to be deleted
    key : string [uuid|alias|hostname]
        value type of 'vm' parameter

    CLI Example:

    .. code-block:: bash

        salt '*' vmadm.delete 186da9ab-7392-4f55-91a5-b8f1fe770543
        salt '*' vmadm.delete nacl key=alias
    """
    ret = {}
    if key not in ["uuid", "alias", "hostname"]:
        ret["Error"] = "Key must be either uuid, alias or hostname"
        return ret
    vm = lookup("{}={}".format(key, vm), one=True)
    if "Error" in vm:
        return vm
    # vmadm delete <uuid>
    cmd = "vmadm delete {}".format(vm)
    res = __salt__["cmd.run_all"](cmd)
    retcode = res["retcode"]
    if retcode != 0:
        ret["Error"] = res["stderr"] if "stderr" in res else _exit_status(retcode)
        return ret
    return True


def get(vm, key="uuid"):
    """
    Output the JSON object describing a VM

    vm : string
        vm to be targeted
    key : string [uuid|alias|hostname]
        value type of 'vm' parameter

    CLI Example:

    .. code-block:: bash

        salt '*' vmadm.get 186da9ab-7392-4f55-91a5-b8f1fe770543
        salt '*' vmadm.get nacl key=alias
    """
    ret = {}
    if key not in ["uuid", "alias", "hostname"]:
        ret["Error"] = "Key must be either uuid, alias or hostname"
        return ret
    vm = lookup("{}={}".format(key, vm), one=True)
    if "Error" in vm:
        return vm
    # vmadm get <uuid>
    cmd = "vmadm get {}".format(vm)
    res = __salt__["cmd.run_all"](cmd)
    retcode = res["retcode"]
    if retcode != 0:
        ret["Error"] = res["stderr"] if "stderr" in res else _exit_status(retcode)
        return ret
    return salt.utils.json.loads(res["stdout"])


def info(vm, info_type="all", key="uuid"):
    """
    Lookup info on running kvm

    vm : string
        vm to be targeted
    info_type : string [all|block|blockstats|chardev|cpus|kvm|pci|spice|version|vnc]
        info type to return
    key : string [uuid|alias|hostname]
        value type of 'vm' parameter

    CLI Example:

    .. code-block:: bash

        salt '*' vmadm.info 186da9ab-7392-4f55-91a5-b8f1fe770543
        salt '*' vmadm.info 186da9ab-7392-4f55-91a5-b8f1fe770543 vnc
        salt '*' vmadm.info nacl key=alias
        salt '*' vmadm.info nacl vnc key=alias
    """
    ret = {}
    if info_type not in [
        "all",
        "block",
        "blockstats",
        "chardev",
        "cpus",
        "kvm",
        "pci",
        "spice",
        "version",
        "vnc",
    ]:
        ret["Error"] = "Requested info_type is not available"
        return ret
    if key not in ["uuid", "alias", "hostname"]:
        ret["Error"] = "Key must be either uuid, alias or hostname"
        return ret
    vm = lookup("{}={}".format(key, vm), one=True)
    if "Error" in vm:
        return vm
    # vmadm info <uuid> [type,...]
    cmd = "vmadm info {uuid} {type}".format(uuid=vm, type=info_type)
    res = __salt__["cmd.run_all"](cmd)
    retcode = res["retcode"]
    if retcode != 0:
        ret["Error"] = res["stderr"] if "stderr" in res else _exit_status(retcode)
        return ret
    return salt.utils.json.loads(res["stdout"])


def create_snapshot(vm, name, key="uuid"):
    """
    Create snapshot of a vm

    vm : string
        vm to be targeted
    name : string
        snapshot name
            The snapname must be 64 characters or less
            and must only contain alphanumeric characters and
            characters in the set [-_.:%] to comply with ZFS restrictions.
    key : string [uuid|alias|hostname]
        value type of 'vm' parameter

    CLI Example:

    .. code-block:: bash

        salt '*' vmadm.create_snapshot 186da9ab-7392-4f55-91a5-b8f1fe770543 baseline
        salt '*' vmadm.create_snapshot nacl baseline key=alias
    """
    ret = {}
    if key not in ["uuid", "alias", "hostname"]:
        ret["Error"] = "Key must be either uuid, alias or hostname"
        return ret
    vm = lookup("{}={}".format(key, vm), one=True)
    if "Error" in vm:
        return vm
    vmobj = get(vm)
    if "datasets" in vmobj:
        ret["Error"] = "VM cannot have datasets"
        return ret
    if vmobj["brand"] in ["kvm"]:
        ret["Error"] = "VM must be of type OS"
        return ret
    if vmobj["zone_state"] not in ["running"]:  # work around a vmadm bug
        ret["Error"] = "VM must be running to take a snapshot"
        return ret
    # vmadm create-snapshot <uuid> <snapname>
    cmd = "vmadm create-snapshot {uuid} {snapshot}".format(snapshot=name, uuid=vm)
    res = __salt__["cmd.run_all"](cmd)
    retcode = res["retcode"]
    if retcode != 0:
        ret["Error"] = res["stderr"] if "stderr" in res else _exit_status(retcode)
        return ret
    return True


def delete_snapshot(vm, name, key="uuid"):
    """
    Delete snapshot of a vm

    vm : string
        vm to be targeted
    name : string
        snapshot name
            The snapname must be 64 characters or less
            and must only contain alphanumeric characters and
            characters in the set [-_.:%] to comply with ZFS restrictions.
    key : string [uuid|alias|hostname]
        value type of 'vm' parameter

    CLI Example:

    .. code-block:: bash

        salt '*' vmadm.delete_snapshot 186da9ab-7392-4f55-91a5-b8f1fe770543 baseline
        salt '*' vmadm.delete_snapshot nacl baseline key=alias
    """
    ret = {}
    if key not in ["uuid", "alias", "hostname"]:
        ret["Error"] = "Key must be either uuid, alias or hostname"
        return ret
    vm = lookup("{}={}".format(key, vm), one=True)
    if "Error" in vm:
        return vm
    vmobj = get(vm)
    if "datasets" in vmobj:
        ret["Error"] = "VM cannot have datasets"
        return ret
    if vmobj["brand"] in ["kvm"]:
        ret["Error"] = "VM must be of type OS"
        return ret
    # vmadm delete-snapshot <uuid> <snapname>
    cmd = "vmadm delete-snapshot {uuid} {snapshot}".format(snapshot=name, uuid=vm)
    res = __salt__["cmd.run_all"](cmd)
    retcode = res["retcode"]
    if retcode != 0:
        ret["Error"] = res["stderr"] if "stderr" in res else _exit_status(retcode)
        return ret
    return True


def rollback_snapshot(vm, name, key="uuid"):
    """
    Rollback snapshot of a vm

    vm : string
        vm to be targeted
    name : string
        snapshot name
            The snapname must be 64 characters or less
            and must only contain alphanumeric characters and
            characters in the set [-_.:%] to comply with ZFS restrictions.
    key : string [uuid|alias|hostname]
        value type of 'vm' parameter

    CLI Example:

    .. code-block:: bash

        salt '*' vmadm.rollback_snapshot 186da9ab-7392-4f55-91a5-b8f1fe770543 baseline
        salt '*' vmadm.rollback_snapshot nacl baseline key=alias
    """
    ret = {}
    if key not in ["uuid", "alias", "hostname"]:
        ret["Error"] = "Key must be either uuid, alias or hostname"
        return ret
    vm = lookup("{}={}".format(key, vm), one=True)
    if "Error" in vm:
        return vm
    vmobj = get(vm)
    if "datasets" in vmobj:
        ret["Error"] = "VM cannot have datasets"
        return ret
    if vmobj["brand"] in ["kvm"]:
        ret["Error"] = "VM must be of type OS"
        return ret
    # vmadm rollback-snapshot <uuid> <snapname>
    cmd = "vmadm rollback-snapshot {uuid} {snapshot}".format(snapshot=name, uuid=vm)
    res = __salt__["cmd.run_all"](cmd)
    retcode = res["retcode"]
    if retcode != 0:
        ret["Error"] = res["stderr"] if "stderr" in res else _exit_status(retcode)
        return ret
    return True


def reprovision(vm, image, key="uuid"):
    """
    Reprovision a vm

    vm : string
        vm to be reprovisioned
    image : string
        uuid of new image
    key : string [uuid|alias|hostname]
        value type of 'vm' parameter

    CLI Example:

    .. code-block:: bash

        salt '*' vmadm.reprovision 186da9ab-7392-4f55-91a5-b8f1fe770543 c02a2044-c1bd-11e4-bd8c-dfc1db8b0182
        salt '*' vmadm.reprovision nacl c02a2044-c1bd-11e4-bd8c-dfc1db8b0182 key=alias
    """
    ret = {}
    if key not in ["uuid", "alias", "hostname"]:
        ret["Error"] = "Key must be either uuid, alias or hostname"
        return ret
    vm = lookup("{}={}".format(key, vm), one=True)
    if "Error" in vm:
        return vm
    if image not in __salt__["imgadm.list"]():
        ret["Error"] = "Image ({}) is not present on this host".format(image)
        return ret
    # vmadm reprovision <uuid> [-f <filename>]
    cmd = "echo {image} | vmadm reprovision {uuid}".format(
        uuid=salt.utils.stringutils.to_unicode(vm),
        image=_quote_args(salt.utils.json.dumps({"image_uuid": image})),
    )
    res = __salt__["cmd.run_all"](cmd, python_shell=True)
    retcode = res["retcode"]
    if retcode != 0:
        ret["Error"] = res["stderr"] if "stderr" in res else _exit_status(retcode)
        return ret
    return True


def create(from_file=None, **kwargs):
    """
    Create a new vm

    from_file : string
        json file to create the vm from -- if present, all other options will be ignored
    kwargs : string|int|...
        options to set for the vm

    CLI Example:

    .. code-block:: bash

        salt '*' vmadm.create from_file=/tmp/new_vm.json
        salt '*' vmadm.create image_uuid='...' alias='...' nics='[{ "nic_tag": "admin", "ip": "198.51.100.123", ...}, {...}]' [...]
    """
    ret = {}
    # prepare vmcfg
    vmcfg = {}
    kwargs = salt.utils.args.clean_kwargs(**kwargs)
    for k, v in kwargs.items():
        vmcfg[k] = v

    if from_file:
        return _create_update_from_file("create", path=from_file)
    else:
        return _create_update_from_cfg("create", vmcfg=vmcfg)


def update(vm, from_file=None, key="uuid", **kwargs):
    """
    Update a new vm

    vm : string
        vm to be updated
    from_file : string
        json file to update the vm with -- if present, all other options will be ignored
    key : string [uuid|alias|hostname]
        value type of 'vm' parameter
    kwargs : string|int|...
        options to update for the vm

    CLI Example:

    .. code-block:: bash

        salt '*' vmadm.update vm=186da9ab-7392-4f55-91a5-b8f1fe770543 from_file=/tmp/new_vm.json
        salt '*' vmadm.update vm=nacl key=alias from_file=/tmp/new_vm.json
        salt '*' vmadm.update vm=186da9ab-7392-4f55-91a5-b8f1fe770543 max_physical_memory=1024
    """
    ret = {}
    # prepare vmcfg
    vmcfg = {}
    kwargs = salt.utils.args.clean_kwargs(**kwargs)
    for k, v in kwargs.items():
        vmcfg[k] = v

    if key not in ["uuid", "alias", "hostname"]:
        ret["Error"] = "Key must be either uuid, alias or hostname"
        return ret
    uuid = lookup("{}={}".format(key, vm), one=True)
    if "Error" in uuid:
        return uuid

    if from_file:
        return _create_update_from_file("update", uuid, path=from_file)
    else:
        return _create_update_from_cfg("update", uuid, vmcfg=vmcfg)


def send(vm, target, key="uuid"):
    """
    Send a vm to a directory

    vm : string
        vm to be sent
    target : string
        target directory
    key : string [uuid|alias|hostname]
        value type of 'vm' parameter

    CLI Example:

    .. code-block:: bash

        salt '*' vmadm.send 186da9ab-7392-4f55-91a5-b8f1fe770543 /opt/backups
        salt '*' vmadm.send vm=nacl target=/opt/backups key=alias
    """
    ret = {}
    if key not in ["uuid", "alias", "hostname"]:
        ret["Error"] = "Key must be either uuid, alias or hostname"
        return ret
    if not os.path.isdir(target):
        ret["Error"] = "Target must be a directory or host"
        return ret
    vm = lookup("{}={}".format(key, vm), one=True)
    if "Error" in vm:
        return vm
    # vmadm send <uuid> [target]
    cmd = "vmadm send {uuid} > {target}".format(
        uuid=vm, target=os.path.join(target, "{}.vmdata".format(vm))
    )
    res = __salt__["cmd.run_all"](cmd, python_shell=True)
    retcode = res["retcode"]
    if retcode != 0:
        ret["Error"] = res["stderr"] if "stderr" in res else _exit_status(retcode)
        return ret
    vmobj = get(vm)
    if "datasets" not in vmobj:
        return True
    log.warning("one or more datasets detected, this is not supported!")
    log.warning("trying to zfs send datasets...")
    for dataset in vmobj["datasets"]:
        name = dataset.split("/")
        name = name[-1]
        cmd = "zfs send {dataset} > {target}".format(
            dataset=dataset,
            target=os.path.join(target, "{}-{}.zfsds".format(vm, name)),
        )
        res = __salt__["cmd.run_all"](cmd, python_shell=True)
        retcode = res["retcode"]
        if retcode != 0:
            ret["Error"] = res["stderr"] if "stderr" in res else _exit_status(retcode)
            return ret
    return True


def receive(uuid, source):
    """
    Receive a vm from a directory

    uuid : string
        uuid of vm to be received
    source : string
        source directory

    CLI Example:

    .. code-block:: bash

        salt '*' vmadm.receive 186da9ab-7392-4f55-91a5-b8f1fe770543 /opt/backups
    """
    ret = {}
    if not os.path.isdir(source):
        ret["Error"] = "Source must be a directory or host"
        return ret
    if not os.path.exists(os.path.join(source, "{}.vmdata".format(uuid))):
        ret["Error"] = "Unknow vm with uuid in {}".format(source)
        return ret
    # vmadm receive
    cmd = "vmadm receive < {source}".format(
        source=os.path.join(source, "{}.vmdata".format(uuid))
    )
    res = __salt__["cmd.run_all"](cmd, python_shell=True)
    retcode = res["retcode"]
    if retcode != 0 and not res["stderr"].endswith("datasets"):
        ret["Error"] = res["stderr"] if "stderr" in res else _exit_status(retcode)
        return ret
    vmobj = get(uuid)
    if "datasets" not in vmobj:
        return True
    log.warning("one or more datasets detected, this is not supported!")
    log.warning("trying to restore datasets, mountpoints will need to be set again...")
    for dataset in vmobj["datasets"]:
        name = dataset.split("/")
        name = name[-1]
        cmd = "zfs receive {dataset} < {source}".format(
            dataset=dataset,
            source=os.path.join(source, "{}-{}.zfsds".format(uuid, name)),
        )
        res = __salt__["cmd.run_all"](cmd, python_shell=True)
        retcode = res["retcode"]
        if retcode != 0:
            ret["Error"] = res["stderr"] if "stderr" in res else _exit_status(retcode)
            return ret
    cmd = "vmadm install {}".format(uuid)
    res = __salt__["cmd.run_all"](cmd, python_shell=True)
    retcode = res["retcode"]
    if retcode != 0 and not res["stderr"].endswith("datasets"):
        ret["Error"] = res["stderr"] if "stderr" in res else _exit_status(retcode)
        return ret
    return True


# vim: tabstop=4 expandtab shiftwidth=4 softtabstop=4
